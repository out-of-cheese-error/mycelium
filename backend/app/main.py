from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from app.agent import app_agent
from app.memory_store import GraphMemory
from app.routers import workspaces, threads, system, audio, concepts, hot_topics, connectors, mcp
import uvicorn

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
app.include_router(mcp.router)

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
        
        return ChatResponse(response=ai_message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph/{workspace_id}")
async def get_graph(workspace_id: str):
    memory = GraphMemory(workspace_id=workspace_id)
    return memory.get_graph_data()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
