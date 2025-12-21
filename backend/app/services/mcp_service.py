"""
MCP (Model Context Protocol) Service

Manages MCP server connections and provides tools from configured MCP servers.
Uses subprocess-based communication with MCP servers.
"""

import asyncio
import json
import subprocess
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


@dataclass
class MCPServerInstance:
    """Represents a running MCP server instance."""
    name: str
    process: Optional[subprocess.Popen] = None
    tools: List[Dict[str, Any]] = field(default_factory=list)
    connected: bool = False


class MCPService:
    """Service for managing MCP server connections and tools."""
    
    _instance = None
    _servers: Dict[str, MCPServerInstance] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPService, cls).__new__(cls)
            cls._instance._servers = {}
        return cls._instance
    
    def _get_config(self):
        """Get MCP server configurations from llm_config."""
        from app.llm_config import llm_config
        return llm_config.get_config().mcp_servers
    
    async def connect_server(self, server_config) -> Dict[str, Any]:
        """
        Connect to an MCP server and retrieve its available tools.
        
        Args:
            server_config: MCPServerConfig with name, command, args, env
            
        Returns:
            Dict with connection status and available tools
        """
        name = server_config.name
        
        try:
            # Build environment with server-specific env vars
            env = os.environ.copy()
            env.update(server_config.env or {})
            
            # Start the MCP server process
            cmd = [server_config.command] + (server_config.args or [])
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=0
            )
            
            # Send initialization request (MCP protocol)
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True}
                    },
                    "clientInfo": {
                        "name": "mycelium",
                        "version": "1.0.0"
                    }
                }
            }
            
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()
            
            # Read initialization response with timeout
            try:
                response_line = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, process.stdout.readline),
                    timeout=10.0
                )
                init_response = json.loads(response_line) if response_line else {}
            except asyncio.TimeoutError:
                process.terminate()
                return {"connected": False, "error": "Server initialization timeout", "tools": []}
            except json.JSONDecodeError:
                process.terminate()
                return {"connected": False, "error": "Invalid JSON response from server", "tools": []}
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            process.stdin.write(json.dumps(initialized_notification) + "\n")
            process.stdin.flush()
            
            # List available tools
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            process.stdin.write(json.dumps(list_tools_request) + "\n")
            process.stdin.flush()
            
            # Read responses - server might send requests we need to handle first
            tools_response = None
            max_attempts = 5
            
            for attempt in range(max_attempts):
                try:
                    response_line = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, process.stdout.readline),
                        timeout=10.0
                    )
                    print(f"MCP DEBUG [{name}]: Response {attempt}: {response_line[:500] if response_line else 'None'}")
                    
                    if not response_line:
                        continue
                        
                    response = json.loads(response_line)
                    
                    # Check if this is a server request (has "method" but no "result")
                    if "method" in response and "result" not in response:
                        # Handle server requests
                        if response.get("method") == "roots/list":
                            # Respond with empty roots list
                            roots_response = {
                                "jsonrpc": "2.0",
                                "id": response.get("id"),
                                "result": {"roots": []}
                            }
                            process.stdin.write(json.dumps(roots_response) + "\n")
                            process.stdin.flush()
                            print(f"MCP DEBUG [{name}]: Responded to roots/list")
                            continue
                        else:
                            print(f"MCP DEBUG [{name}]: Unknown server request: {response.get('method')}")
                            continue
                    
                    # Check if this is our tools/list response
                    if response.get("id") == 2 and "result" in response:
                        tools_response = response
                        break
                        
                except asyncio.TimeoutError:
                    print(f"MCP DEBUG [{name}]: Timeout on attempt {attempt}")
                    break
                except json.JSONDecodeError as e:
                    print(f"MCP DEBUG [{name}]: JSON decode error: {e}")
                    continue
            
            if not tools_response:
                process.terminate()
                return {"connected": False, "error": "Could not get tools list response", "tools": []}
            
            tools = tools_response.get("result", {}).get("tools", [])
            print(f"MCP DEBUG [{name}]: Extracted {len(tools)} tools")
            
            # Store server instance
            self._servers[name] = MCPServerInstance(
                name=name,
                process=process,
                tools=tools,
                connected=True
            )
            
            return {
                "connected": True,
                "tools": tools,
                "server_info": init_response.get("result", {}).get("serverInfo", {})
            }
            
        except FileNotFoundError:
            return {"connected": False, "error": f"Command not found: {server_config.command}", "tools": []}
        except Exception as e:
            return {"connected": False, "error": str(e), "tools": []}
    
    async def disconnect_server(self, name: str) -> bool:
        """Disconnect from an MCP server."""
        if name in self._servers:
            server = self._servers[name]
            if server.process:
                server.process.terminate()
                try:
                    server.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.process.kill()
            del self._servers[name]
            return True
        return False
    
    async def disconnect_all(self):
        """Disconnect all MCP servers."""
        for name in list(self._servers.keys()):
            await self.disconnect_server(name)
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on a specific MCP server.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if server_name not in self._servers:
            return {"error": f"Server '{server_name}' not connected"}
        
        server = self._servers[server_name]
        if not server.connected or not server.process:
            return {"error": f"Server '{server_name}' not connected"}
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            server.process.stdin.write(json.dumps(request) + "\n")
            server.process.stdin.flush()
            
            response_line = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, server.process.stdout.readline),
                timeout=30.0
            )
            response = json.loads(response_line) if response_line else {}
            
            if "error" in response:
                return {"error": response["error"].get("message", "Unknown error")}
            
            result = response.get("result", {})
            content = result.get("content", [])
            
            # Extract text content
            text_parts = []
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            
            return "\n".join(text_parts) if text_parts else str(result)
            
        except asyncio.TimeoutError:
            return {"error": "Tool call timeout"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tools from all connected MCP servers.
        
        Returns:
            List of tools with server metadata
        """
        all_tools = []
        
        for name, server in self._servers.items():
            if server.connected:
                for tool in server.tools:
                    all_tools.append({
                        "server_name": name,
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("inputSchema", {})
                    })
        
        return all_tools
    
    async def refresh_connections(self):
        """Refresh connections to all configured MCP servers."""
        await self.disconnect_all()
        
        configs = self._get_config()
        results = {}
        
        for config in configs:
            result = await self.connect_server(config)
            results[config.name] = result
        
        return results
    
    def get_langchain_tools(self) -> List[StructuredTool]:
        """
        Create LangChain tools from all connected MCP servers.
        
        Returns:
            List of StructuredTool instances
        """
        langchain_tools = []
        
        for server_name, server in self._servers.items():
            if not server.connected:
                continue
                
            for tool_def in server.tools:
                tool_name = tool_def.get("name", "")
                description = tool_def.get("description", f"MCP tool from {server_name}")
                input_schema = tool_def.get("inputSchema", {})
                
                # Create a unique function name
                func_name = f"mcp_{server_name}_{tool_name}".replace("-", "_").replace(".", "_")
                
                # Create the tool function
                def make_tool_func(sname, tname):
                    async def tool_func(**kwargs) -> str:
                        result = await mcp_service.call_tool(sname, tname, kwargs)
                        if isinstance(result, dict) and "error" in result:
                            return f"Error: {result['error']}"
                        return str(result)
                    return tool_func
                
                # Build Pydantic model for input if schema provided
                tool_fields = {}
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])
                
                for prop_name, prop_def in properties.items():
                    prop_type = prop_def.get("type", "string")
                    prop_desc = prop_def.get("description", "")
                    is_required = prop_name in required
                    
                    # Map JSON schema types to Python types
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": float,
                        "boolean": bool,
                        "array": list,
                        "object": dict
                    }
                    python_type = type_map.get(prop_type, str)
                    
                    if is_required:
                        tool_fields[prop_name] = (python_type, Field(description=prop_desc))
                    else:
                        tool_fields[prop_name] = (Optional[python_type], Field(default=None, description=prop_desc))
                
                # Create structured tool
                try:
                    if tool_fields:
                        # Create input model dynamically
                        from pydantic import create_model
                        InputModel = create_model(f"{func_name}_Input", **tool_fields)
                        
                        structured_tool = StructuredTool.from_function(
                            coroutine=make_tool_func(server_name, tool_name),
                            name=func_name,
                            description=f"[MCP:{server_name}] {description}",
                            args_schema=InputModel
                        )
                    else:
                        # No arguments
                        structured_tool = StructuredTool.from_function(
                            coroutine=make_tool_func(server_name, tool_name),
                            name=func_name,
                            description=f"[MCP:{server_name}] {description}"
                        )
                    
                    langchain_tools.append(structured_tool)
                except Exception as e:
                    print(f"Failed to create LangChain tool for {tool_name}: {e}")
                    continue
        
        return langchain_tools


# Global service instance
mcp_service = MCPService()


async def get_mcp_tools() -> List[Dict[str, Any]]:
    """Get all available MCP tools."""
    return await mcp_service.get_all_tools()


async def refresh_mcp_servers():
    """Refresh all MCP server connections."""
    return await mcp_service.refresh_connections()


def get_mcp_langchain_tools() -> List[StructuredTool]:
    """Get LangChain-compatible tools from MCP servers."""
    return mcp_service.get_langchain_tools()
