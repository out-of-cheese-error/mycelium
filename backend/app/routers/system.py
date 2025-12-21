from fastapi import APIRouter
from app.llm_config import llm_config, LLMConfigModel

router = APIRouter(prefix="/system", tags=["system"])

@router.get("/config", response_model=LLMConfigModel)
async def get_system_config():
    return llm_config.get_config()

@router.post("/config", response_model=LLMConfigModel)
async def update_system_config(config: LLMConfigModel):
    llm_config.update_config(config)
    
    # Refresh MCP server connections after config update
    try:
        from app.services.mcp_service import refresh_mcp_servers
        results = await refresh_mcp_servers()
        for name, result in results.items():
            if result.get("connected"):
                print(f"MCP: Connected to '{name}' with {len(result.get('tools', []))} tools")
            else:
                print(f"MCP: Failed to connect to '{name}': {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"MCP: Error refreshing servers: {e}")
    
    return config

import httpx
from fastapi import HTTPException
from typing import List, Dict

@router.get("/models")
async def get_models():
    """Fetches available models from the configured LLM provider."""
    cfg = llm_config.get_config()
    base_url = cfg.chat_base_url.rstrip("/")
    api_key = cfg.chat_api_key
    
    # Handle /v1 suffix if present or missing, usually we want {base}/models
    # If user provided "http://localhost:1234/v1", we want "http://localhost:1234/v1/models"
    # If user provided "http://localhost:1234", we might need "http://localhost:1234/v1/models"
    # Let's assume the user configured the base_url correctly for the client (which usually expects /v1).
    
    target_url = f"{base_url}/models"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            resp = await client.get(target_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Standard OpenAI response format: { "data": [ {"id": "model-1"}, ... ] }
            if "data" in data and isinstance(data["data"], list):
                models = [item["id"] for item in data["data"] if "id" in item]
                return {"models": models}
            else:
                return {"models": []} # Fallback
                
    except Exception as e:
        print(f"Failed to fetch models: {e}")
        # Don't crash, just return empty list so UI doesn't break
        return {"models": [], "error": str(e)}


# --- MCP Server Management Endpoints ---

from app.llm_config import MCPServerConfig

@router.post("/mcp/test")
async def test_mcp_server(server: MCPServerConfig):
    """Tests if an MCP server can be connected and lists its tools."""
    from app.services.mcp_service import mcp_service
    result = await mcp_service.connect_server(server)
    # Disconnect after test (don't keep running)
    await mcp_service.disconnect_server(server.name)
    return result


@router.get("/mcp/tools")
async def get_mcp_tools():
    """Get all tools from connected MCP servers."""
    from app.services.mcp_service import get_mcp_tools
    return await get_mcp_tools()


@router.post("/mcp/refresh")
async def refresh_mcp_servers():
    """Refresh connections to all configured MCP servers."""
    from app.services.mcp_service import refresh_mcp_servers as refresh
    return await refresh()


@router.get("/mcp/status")
async def get_mcp_status():
    """Get connection status of all MCP servers."""
    from app.services.mcp_service import mcp_service
    status = {}
    for name, server in mcp_service._servers.items():
        status[name] = {
            "connected": server.connected,
            "tool_count": len(server.tools)
        }
    return status

