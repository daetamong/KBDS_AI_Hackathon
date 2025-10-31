'''
코드 설명
- 여러 MCP 서버를 개별 프로세스로 띄우고 관리하는 서비스
- 각 서버가 노출하는 tool 목록을 수집/등록
- tool을 JSON-RPC로 호출
- 적절한 MCP 서버로 요청을 전달하고 응답을 받아옴
'''
import uuid
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
    '''
    하위 레벨
    - 프로세스 생성
    - 초기화 요청
    - tools 조회/등록
    '''
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

        # 출처 추적용 trace id 생성
        trace_id = str(uuid.uuid4())

        # 요청 로그 기록
        logger.info(f"[TRACE {trace_id}] Calling tool '{tool_name}' on server '{server_name}' with params: {parameters}")

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

            # 응답 로그 기록
            logger.info(f"[TRACE {trace_id}] Response from '{server_name}/{tool_name}': {json.dumps(response)[:300]}")

            if response and "result" in response:
                # provenance 필드를 추가해 출처 메타데이터 포함
                result = response["result"]
                result["_provenance"] = {
                    "trace_id": trace_id,
                    "server": server_name,
                    "tool": tool_name
                }
                return result
            elif response and "error" in response:
                raise Exception(f"Tool call error: {response['error']}")
            else:
                raise Exception("No response from tool call")

        except Exception as e:
            logger.error(f"[TRACE {trace_id}] Failed to call tool {tool_name}: {e}")
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
    '''
    상위 레벨
    - 초기화/종료
    - 외부에 제공할 tool 호출 인터페이스
    '''
    def __init__(self):
        self.client = MCPServerClient()
        self.initialized = False
    
    async def initialize(self):
        """Initialize MCP service with configured servers"""
        if self.initialized:
            return
        
        # Load MCP server configuration
        config = {
            "naver-maps-mcp": {
                "command": "npx.cmd",
                "args": [
                    "/c",
                    "npx",
                    "-y",
                    "@smithery/cli@latest",
                    "run",
                    "@Chaeyun06/naver-maps-mcp",
                    "--key",
                    "e9390fb3-2166-4957-8a22-23163539572f",
                    "--profile",
                    "social-piranha-4RfCKK"
                ]
            },
            "fdc-mcp": {
                "command": "npx.cmd",
                "args": ["-y", "food-data-central-mcp-server"],
                "env": {"FDC_API_KEY": "CwkJTDMSLLomgslEVQN80VL3opCsaX6opn614GkY"}
            },
            "openfoodfacts-standard": {
                "command": "node",
                "args": ["KBDS_AI_Hackathon/mcp-server/dist/cli.js"],
                "env": {"TRANSPORT": "stdio"}
            },
            "nutritionix-mcp": {
                "command": "python",
                "args": ["-m", "nutritionix_mcp_server"],
                "env": {
                "NIX_APP_ID": "42236539",
                "NIX_APP_KEY": "4164887fe912013bf343e27b658e4d3c"
                }
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