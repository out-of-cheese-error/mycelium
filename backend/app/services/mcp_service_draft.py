from typing import List, Dict, Any
import asyncio
import os
import shutil
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import Tool

class MCPService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPService, cls).__new__(cls)
            cls._instance.clients = {} # { server_name: session }
            cls._instance.tools = {} # { server_name: [tools] }
        return cls._instance

    async def connect_server(self, name: str, config: Dict[str, Any]):
        """
        Connects to an MCP server using stdio.
        config: { "command": str, "args": List[str], "env": Dict[str, str] }
        """
        try:
            command = config.get("command")
            args = config.get("args", [])
            env = config.get("env", {})
            
            # Merge with current environment to ensure PATH etc are preset
            full_env = os.environ.copy()
            full_env.update(env)
            
            # Resolve command path if needed
            if shutil.which(command):
                 command_path = shutil.which(command)
            else:
                 command_path = command

            server_params = StdioServerParameters(
                command=command_path,
                args=args,
                env=full_env
            )

            # We need to maintain the context manager or session.
            # The mcp library uses context managers for connection.
            # This makes a long-lived connection tricky in a simple dict.
            # We might need to spawn a background task or use a different pattern.
            # For now, let's try to adapt the context manager to a long-lived object
            # strictly for this proof of concept, or re-connect on demand (slow).
            
            # BETTER APPROACH:
            # We'll implementation valid "LangChain" tools that wrap the MCP calls.
            # Those tools will need access to an active session.
            
            # Let's start the connection block and keep it running? 
            # That blocks the event loop.
            # We need `stdio_client` to yield a read/write stream and then `ClientSession` uses it.
            
            # Actually, `stdio_client` is an async context manager. 
            # We can't easily "store" it without being inside an async function that awaits it.
            # This is a common issue integrating async context managers into global state.
            
            # Alternative: The LangGraph agent runs in a short request context usually,
            # but we want persistent tools.
            # Let's try to connect ONCE when the service starts? No, config changes.
            
            pass

        except Exception as e:
            print(f"Failed to connect to MCP server {name}: {e}")
            raise e

    async def get_tools_from_server(self, name: str, config: Dict[str, Any]) -> List[Tool]:
        """
        Connects to the server, lists tools, and returns LangChain wrappers.
        Note: This currently connects/disconnects PER CALL which is inefficient but safe.
        Real persistent connections require a background loop or managing the context stack.
        """
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})
        full_env = os.environ.copy()
        full_env.update(env)
        
        # Verify command exists
        if not shutil.which(command):
             print(f"Command not found: {command}")
             return []

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=full_env
        )

        tools_list = []

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List tools
                    mcp_tools = await session.list_tools()
                    
                    for tool in mcp_tools.tools:
                        # Create a wrapper function that captures the session?
                        # NO, session closes after this block.
                        # WE CANNOT return a tool that uses a closed session.
                        # This means we MUST execute the tool call inside this block.
                        # But we are returning tools to the agent to call LATER.
                        
                        # CONCLUSION:
                        # We cannot use transient connections for the Agent's tool LIST.
                        # We need a Persistent MCP Client Manager that holds the sessions open.
                        pass
                        
        except Exception as e:
            print(f"Error fetching tools from {name}: {e}")
            return []
            
        return tools_list

    # Revised Architecture for Async Persistence
    # 1. Start a background task for each server that maintains the connection.
    # 2. Store the 'session' object.
    # 3. Tools just reference `MCPService.get_session(name).call_tool(...)`
    
    pass
