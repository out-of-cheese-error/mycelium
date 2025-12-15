from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.llm_config import llm_config, LLMConfigModel
from app.services.mcp_service import mcp_service

router = APIRouter(prefix="/mcp", tags=["mcp"])

class MCPServerConfigDTO(BaseModel):
    name: str
    command: str
    args: List[str] = []
    env: Dict[str, str] = {}
    enabled: bool = True

@router.get("/servers", response_model=List[MCPServerConfigDTO])
async def list_servers():
    config = llm_config.get_config()
    servers = []
    for name, data in config.mcp_servers.items():
        servers.append(MCPServerConfigDTO(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            enabled=data.get("enabled", True)
        ))
    return servers

@router.post("/servers")
async def add_server(server: MCPServerConfigDTO):
    config = llm_config.get_config()
    if server.name in config.mcp_servers:
        raise HTTPException(status_code=400, detail="Server with this name already exists.")
    
    # Update Config
    config.mcp_servers[server.name] = {
        "command": server.command,
        "args": server.args,
        "env": server.env,
        "enabled": server.enabled
    }
    llm_config.update_config(config)
    
    # Start Client
    if server.enabled:
        client = mcp_service.get_client(server.name)
        if not client:
            # Need to re-init service check? No, just manually start.
            # Ideally service watches config, but manual trigger is fine.
            # We add it to the services clients
            from app.services.mcp_service import MCPServerClient
            new_client = MCPServerClient(server.name, config.mcp_servers[server.name])
            mcp_service.clients[server.name] = new_client
            await new_client.start()
            
    return {"status": "success", "message": f"Server {server.name} added."}

@router.put("/servers/{name}")
async def update_server(name: str, server: MCPServerConfigDTO):
    config = llm_config.get_config()
    if name not in config.mcp_servers:
        raise HTTPException(status_code=404, detail="Server not found.")
    
    # Stop existing if running
    existing_client = mcp_service.get_client(name)
    if existing_client:
        await existing_client.stop()
        del mcp_service.clients[name]
    
    # Update Config
    # Handle rename? NO, assume name matches path param for simplicity or forbid rename.
    # If server.name != name, it's a rename.
    target_name = server.name
    
    if target_name != name:
        # Rename logic
        del config.mcp_servers[name]
        
    config.mcp_servers[target_name] = {
        "command": server.command,
        "args": server.args,
        "env": server.env,
        "enabled": server.enabled
    }
    llm_config.update_config(config)
    
    # Restart if enabled
    if server.enabled:
        from app.services.mcp_service import MCPServerClient
        new_client = MCPServerClient(target_name, config.mcp_servers[target_name])
        mcp_service.clients[target_name] = new_client
        await new_client.start()
        
    return {"status": "success"}

@router.delete("/servers/{name}")
async def delete_server(name: str):
    config = llm_config.get_config()
    if name not in config.mcp_servers:
        raise HTTPException(status_code=404, detail="Server not found.")
        
    # Stop client
    client = mcp_service.get_client(name)
    if client:
        await client.stop()
        del mcp_service.clients[name]
        
    # Remove from config
    del config.mcp_servers[name]
    llm_config.update_config(config)
    
    return {"status": "success"}

@router.post("/restart")
async def restart_services():
    """Forces a restart of all enabled MCP services."""
    await mcp_service.stop_all()
    await mcp_service.start_all_configured()
    return {"status": "restarted"}
