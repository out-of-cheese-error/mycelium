from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from app.agent import app_agent, run_background_extraction_and_emotions
from app.memory_store import GraphMemory
from app.routers import workspaces, threads, system, audio, concepts, hot_topics, connectors, graph_chat, skills, call, terminal
import os
import uvicorn

from app.memory_store import MEMORY_BASE_DIR

app = FastAPI(title="MyCelium")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces.router)
app.include_router(threads.router)
app.include_router(system.router)
app.include_router(audio.router)
app.include_router(concepts.router)
app.include_router(hot_topics.router)
app.include_router(connectors.router)
app.include_router(graph_chat.router)
app.include_router(skills.router)
app.include_router(call.router)
app.include_router(terminal.router)


# --- MCP Server Lifecycle ---
@app.on_event("startup")
async def startup_event():
    """Connect to configured MCP servers and restore extraction buffers on startup."""
    # Restore any persisted extraction buffers from previous session
    try:
        from app.services.extraction_buffer import restore_buffers_from_disk
        restore_buffers_from_disk()
    except Exception as e:
        print(f"Buffer restore: {e}")

    # Generate OpenCode TUI config from LLM settings
    try:
        from app.services.opencode_config_service import sync_opencode_config
        sync_opencode_config()
        print("OpenCode: Config synced from llm_config.json")
    except Exception as e:
        print(f"OpenCode: Config sync failed: {e}")

    # Connect to MCP servers
    try:
        from app.services.mcp_service import refresh_mcp_servers
        results = await refresh_mcp_servers()
        for name, result in results.items():
            if result.get("connected"):
                print(f"MCP: Connected to '{name}' with {len(result.get('tools', []))} tools")
            else:
                print(f"MCP: Failed to connect to '{name}': {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"MCP: Error during startup: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Save extraction buffers and disconnect MCP servers on shutdown."""
    # Save any pending extraction buffers to disk
    try:
        from app.services.extraction_buffer import save_all_buffers
        save_all_buffers()
        print("Buffer: All buffers saved to disk")
    except Exception as e:
        print(f"Buffer save: {e}")

    # Disconnect MCP servers
    try:
        from app.services.mcp_service import mcp_service
        await mcp_service.disconnect_all()
        print("MCP: All servers disconnected")
    except Exception as e:
        print(f"MCP: Error during shutdown: {e}")

class ChatRequest(BaseModel):
    message: str
    workspace_id: str = "default"
    # Thread support could be added here, currently single thread per workspace logical session

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Prepare state
        # In a real app complexity, we'd load history from DB based on a thread_id
        # For now, we are stateless regarding chat history in this endpoint (it resets per request unless we pass history)
        # LangGraph defaults to new state if not persistent checkpointer used.
        # Implication: The bot remembers *facts* via GraphMemory, but might forget immediate conversation context if not passed.
        # To fix this properly for v2 "open multiple chats", we'd need a checkpointer.
        # Staying simple: We assume the client sends the *last* message, and we rely on graph context.
        # Improvement: Pass history from frontend or just rely on graph.
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "context": "",
            "workspace_id": request.workspace_id
        }
        
        # Run agent
        final_state = app_agent.invoke(initial_state)
        
        # Get last AI message
        ai_message = final_state["messages"][-1]
        
        # Fire background extraction and emotion update
        import threading
        t = threading.Thread(
            target=run_background_extraction_and_emotions,
            args=(request.workspace_id, request.message, ai_message.content),
            daemon=True
        )
        t.start()

        return ChatResponse(response=ai_message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph/{workspace_id}")
async def get_graph(workspace_id: str):
    memory = GraphMemory(workspace_id=workspace_id)
    return memory.get_graph_data()

@app.get("/debug/graph_check/{workspace_id}")
async def debug_graph_check(workspace_id: str, node_id: str = None):
    """Debug endpoint to check if a node exists in the graph."""
    memory = GraphMemory(workspace_id=workspace_id)
    graph_data = memory.get_graph_data()
    node_ids_in_graph = [n['id'] for n in graph_data.get('nodes', [])]
    
    # Get connectors
    connectors = memory.get_connectors(limit=20, normalize=False)
    connector_ids = [c['id'] for c in connectors]
    
    # Find mismatches
    connectors_not_in_graph = [cid for cid in connector_ids if cid not in node_ids_in_graph]
    
    result = {
        "workspace_id": workspace_id,
        "total_nodes_in_graph_api": len(node_ids_in_graph),
        "total_nodes_in_networkx": memory.graph.number_of_nodes(),
        "connectors_not_in_graph_api": connectors_not_in_graph,
        "graph_path": memory.graph_path,
    }
    
    if node_id:
        result["node_id_searched"] = node_id
        result["exists_in_graph_api"] = node_id in node_ids_in_graph
        result["exists_in_networkx"] = memory.graph.has_node(node_id)
        # Check for similar names (case insensitive)
        similar = [n for n in node_ids_in_graph if node_id.lower() in n.lower()]
        result["similar_nodes"] = similar[:10]
    
    return result

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
