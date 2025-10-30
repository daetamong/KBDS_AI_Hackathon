#!/usr/bin/env python3
"""
Simple test script to verify MCP integration works
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_service import MCPService

async def test_mcp_integration():
    """Test MCP service integration"""
    print("Testing MCP Service Integration...")
    
    # Create MCP service instance
    mcp_service = MCPService()
    
    try:
        # Initialize the service
        print("Initializing MCP service...")
        await mcp_service.initialize()
        print("✓ MCP service initialized successfully")
        
        # Get available tools
        tools = mcp_service.get_tools_for_openai()
        print(f"✓ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['function']['name']}: {tool['function']['description']}")
        
        # Test a simple tool call (if any tools are available)
        if tools:
            tool_name = tools[0]['function']['name']
            print(f"\nTesting tool call: {tool_name}")
            
            # Try a simple call with empty parameters
            result = await mcp_service.get_tool_response(tool_name, {}, "test_call_1")
            print(f"✓ Tool call successful: {result}")
        
        print("\n✓ All tests passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        await mcp_service.shutdown()
        print("✓ MCP service shut down")

if __name__ == "__main__":
    asyncio.run(test_mcp_integration())
