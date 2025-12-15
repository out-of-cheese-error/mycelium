import asyncio
import os
import shutil
import logging
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, create_model

logger = logging.getLogger(__name__)

class MCPServerClient:
    """
    Manages a single persistent connection to an MCP server.
    """
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self._task: Optional[asyncio.Task] = None
        self._exit_event = asyncio.Event()
        self.status = "stopped"
        self.error = None

    async def start(self):
        """Starts the background task to maintain connection."""
        if self.status in ["starting", "running"]:
            return
        
        self.status = "starting"
        self.error = None
        self._exit_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stops the connection."""
        if self.status == "stopped":
            return
            
        self.status = "stopping"
        self._exit_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout stopping MCP server {self.name}, cancelling...")
                self._task.cancel()
            except Exception as e:
                logger.error(f"Error stopping MCP server {self.name}: {e}")
        
        self.status = "stopped"
        self.session = None

    async def _run_loop(self):
        """Detailed connection loop that maintains the session."""
        command = self.config.get("command")
        args = self.config.get("args", [])
        env = self.config.get("env", {})
        
        full_env = os.environ.copy()
        full_env.update(env)
        
        if not shutil.which(command):
            self.status = "error"
            self.error = f"Command not found: {command}"
            logger.error(self.error)
            return

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=full_env
        )

        try:
            async with AsyncExitStack() as stack:
                # 1. Start Transport
                try:
                    read, write = await stack.enter_async_context(stdio_client(server_params))
                except Exception as e:
                    raise RuntimeError(f"Failed to start process: {e}")

                # 2. Start Session
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                self.session = session
                self.status = "running"
                logger.info(f"MCP Server {self.name} connected.")

                # 3. Wait until told to simple
                await self._exit_event.wait()
                
        except asyncio.CancelledError:
            logger.info(f"MCP Server task {self.name} cancelled.")
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            logger.error(f"MCP Server {self.name} crashed: {e}")
        finally:
            self.session = None
            if self.status != "error":
                self.status = "stopped"

class MCPService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPService, cls).__new__(cls)
            cls._instance.clients: Dict[str, MCPServerClient] = {}
        return cls._instance

    def get_client(self, name: str) -> Optional[MCPServerClient]:
        return self.clients.get(name)

    async def start_all_configured(self):
        """Reads config and starts all enabled servers."""
        from app.llm_config import llm_config
        servers = llm_config.get_config().mcp_servers
        
        for name, config in servers.items():
            if config.get("enabled", True):
                if name not in self.clients:
                    client = MCPServerClient(name, config)
                    self.clients[name] = client
                    await client.start()

    async def stop_all(self):
        for client in self.clients.values():
            await client.stop()

    async def get_all_tools(self) -> List[Tool]:
        """Discovery and creation of LangChain-compatible tools from all active clients."""
        all_tools = []
        
        for name, client in self.clients.items():
            if client.status != "running" or not client.session:
                continue
                
            try:
                # List tools from MCP
                result = await client.session.list_tools()
                
                for mcp_tool in result.tools:
                    # Create dynamic Pydantic model for args
                    fields = {}
                    for prop_name, prop_schema in mcp_tool.inputSchema.get("properties", {}).items():
                        # Simplification: assume string for now or use Any. 
                        # Ideally we map JSON schema types to Pydantic types.
                        # For robustness in this MVP, we'll allow Any or default to str.
                        fields[prop_name] = (Any, ...) # required? check schema "required" list
                    
                    # Create model (if fields exist, otherwise empty model)
                    if fields:
                        ArgsModel = create_model(f"{mcp_tool.name}Args", **fields)
                    else:
                        ArgsModel = None
                        
                    # Define the async callable
                    async def _tool_func(client_ref=client, tool_name=mcp_tool.name, **kwargs):
                        if not client_ref.session:
                            return "Error: MCP Server disconnected."
                        try:
                            res = await client_ref.session.call_tool(tool_name, arguments=kwargs)
                            # Format result
                            output = ""
                            if hasattr(res, 'content'):
                                for content in res.content:
                                    if content.type == 'text':
                                        output += content.text + "\n"
                                    elif content.type == 'image':
                                        output += f"[Image: {content.mimeType}]\n"
                                    elif content.type == 'resource':
                                         output += f"[Resource: {content.uri}]\n"
                            return output.strip()
                        except Exception as e:
                            return f"Tool execution error: {e}"

                    # Create StructuredTool or Tool
                    lang_tool = StructuredTool.from_function(
                        func=None,
                        coroutine=_tool_func,
                        name=mcp_tool.name, # Global uniqueness might be issue, maybe prefix?
                        description=mcp_tool.description or f"Tool provided by {name}",
                        args_schema=ArgsModel
                    )
                    
                    all_tools.append(lang_tool)
                    
            except Exception as e:
                logger.error(f"Failed to fetch tools from {name}: {e}")
                
        return all_tools

mcp_service = MCPService()
