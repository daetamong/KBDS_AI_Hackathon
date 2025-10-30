# MCP 서버들을 별도 프로세스로 띄우고 관리하는 서비스
import json
import asyncio
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@dataclass
class MCPTool:
    '''
    MCP 서버가 제공하는 메타데이터를 담는 클래스
    '''
    name: str
    description: str
    parameters: Dict[str, Any]

class MCPServerClient:
    def __init__(self):
        self.servers = {}
        self.tools = {}
        # tools : {"tool_name": {서버, 설명, 스키마}, ...}
        self.processes = {}
    
    async def start_server(self, server_name: str, config: Dict[str, Any]):
        """Start an MCP server process"""
        try:
            command = config.get("command", "")
            args = config.get("args", [])
            
            # create_subprocess_exec : MCP 서버를 띄우고 stdn/stdout/stderr 파이프를 연다
            process = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.processes[server_name] = process
            logger.info(f"Started MCP server: {server_name}")
            
            # Initialize server and get available tools
            await self._initialize_server(server_name, process)
            
        except Exception as e:
            logger.error(f"Failed to start MCP server {server_name}: {e}")
            raise
    
    async def _initialize_server(self, server_name: str, process):
        """Initialize MCP server and get available tools"""
        try:
            # Send initialization request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "realtime-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            await self._send_request(process, init_request)
            response = await self._read_response(process)
            
            if response and "result" in response:
                # Get available tools
                tools_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {}
                }
                
                await self._send_request(process, tools_request)
                tools_response = await self._read_response(process)
                
                if tools_response and "result" in tools_response:
                    tools = tools_response["result"].get("tools", [])
                    for tool in tools:
                        tool_name = tool.get("name")
                        if tool_name:
                            self.tools[tool_name] = {
                                "server": server_name,
                                "name": tool_name,
                                "description": tool.get("description", ""),
                                "parameters": tool.get("inputSchema", {})
                            }
                            logger.debug(f"Registered tool: {tool_name} from server {server_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP server {server_name}: {e}")
    
    async def _send_request(self, process, request):
        """Send a JSON-RPC request to the MCP server"""
        request_json = json.dumps(request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()
    
    async def _read_response(self, process):
        """Read a JSON-RPC response from the MCP server"""
        try:
            line = await process.stdout.readline()
            if line:
                return json.loads(line.decode().strip())
        except Exception as e:
            logger.error(f"Failed to read response: {e}")
        return None
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any], call_id: str):
        """Call a tool on the appropriate MCP server"""
        if tool_name not in self.tools:
            raise Exception(f"Tool {tool_name} not found")
        
        tool_info = self.tools[tool_name]
        server_name = tool_info["server"]
        
        if server_name not in self.processes:
            raise Exception(f"Server {server_name} not running")
        
        process = self.processes[server_name]
        
        # Send tool call request
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters
            }
        }
        
        try:
            await self._send_request(process, request)
            response = await self._read_response(process)
            
            if response and "result" in response:
                return response["result"]
            elif response and "error" in response:
                raise Exception(f"Tool call error: {response['error']}")
            else:
                raise Exception("No response from tool call")
                
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise
    
    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI Realtime format"""
        openai_tools = []
        for tool_name, tool_info in self.tools.items():
            openai_tools.append({
                "name": tool_name,
                "description": tool_info["description"],
                "parameters": tool_info["parameters"]
            })
        return openai_tools
    
    async def shutdown(self):
        """Shutdown all MCP servers"""
        for server_name, process in self.processes.items():
            try:
                process.terminate()
                await process.wait()
                logger.info(f"Shutdown MCP server: {server_name}")
            except Exception as e:
                logger.error(f"Failed to shutdown server {server_name}: {e}")
        
        self.processes.clear()
        self.tools.clear()

class MCPService:
    def __init__(self):
        self.client = MCPServerClient()
        self.initialized = False
    
    async def initialize(self):
        """Initialize MCP service with configured servers"""
        if self.initialized:
            return
        
        # Load MCP server configuration
        config = {
            "airbnb": {
                "command": "npx.cmd",
                "args": [
                    "-y",
                    "@openbnb/mcp-server-airbnb",
                    "--ignore-robots-txt"
                ]
            },
            "naver": {
                "command": "npx.cmd",
                "args": [
                    "-y", "@kbds/mcp-server-naver"
                ]
            }
        }
        
        for server_name, server_config in config.items():
            await self.client.start_server(server_name, server_config)
        
        self.initialized = True
        logger.info("MCP service initialized")
    
    async def get_tool_response(self, tool_name: str, parameters: Dict[str, Any], call_id: str):
        """Get tool response from MCP server"""
        if not self.initialized:
            await self.initialize()
        
        try:
            result = await self.client.call_tool(tool_name, parameters, call_id)
            return result
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return {"error": str(e)}
    
    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """Get all available tools in OpenAI format"""
        if not self.initialized:
            return []
        return self.client.get_tools_for_openai()
    
    async def shutdown(self):
        """Shutdown MCP service"""
        await self.client.shutdown()
        self.initialized = False
