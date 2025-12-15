from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import json
import uuid
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.agent import app_agent

from datetime import datetime

router = APIRouter(prefix="/threads", tags=["threads"])

MEMORY_BASE_DIR = "./memory_data"

class Thread(BaseModel):
    id: str
    workspace_id: str
    title: str
    created_at: str # ISO string or timestamp

class CreateThreadRequest(BaseModel):
    workspace_id: str
    title: Optional[str] = "New Chat"

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    thread_id: str

def get_thread_dir(workspace_id: str):
    path = os.path.join(MEMORY_BASE_DIR, workspace_id, "threads")
    os.makedirs(path, exist_ok=True)
    return path

def get_thread_path(workspace_id: str, thread_id: str):
    return os.path.join(get_thread_dir(workspace_id), f"{thread_id}.json")

@router.get("/{workspace_id}", response_model=List[Thread])
async def list_threads(workspace_id: str):
    thread_dir = get_thread_dir(workspace_id)
    threads = []
    if not os.path.exists(thread_dir):
        return []
    
    for filename in os.listdir(thread_dir):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(thread_dir, filename), 'r') as f:
                    data = json.load(f)
                    threads.append(Thread(
                        id=data["id"],
                        workspace_id=data["workspace_id"],
                        title=data.get("title", "Untitled"),
                        created_at=data.get("created_at", "")
                    ))
            except:
                continue
    # Sort by created_at desc (if available, else name)
    # threads.sort(key=lambda t: t.created_at, reverse=True) 
    return threads

@router.post("/", response_model=Thread)
async def create_thread(request: CreateThreadRequest):
    thread_id = str(uuid.uuid4())[:8]
    thread_data = {
        "id": thread_id,
        "workspace_id": request.workspace_id,
        "title": request.title,
        "created_at": datetime.now().isoformat(),
        "messages": []
    }
    
    path = get_thread_path(request.workspace_id, thread_id)
    with open(path, 'w') as f:
        json.dump(thread_data, f, indent=2)
        
    return Thread(id=thread_id, workspace_id=request.workspace_id, title=request.title, created_at="")

@router.delete("/{workspace_id}/{thread_id}")
async def delete_thread(workspace_id: str, thread_id: str):
    path = get_thread_path(workspace_id, thread_id)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Thread not found")

@router.get("/{workspace_id}/{thread_id}/history")
async def get_thread_history(workspace_id: str, thread_id: str):
    path = get_thread_path(workspace_id, thread_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Thread not found")
        
    with open(path, 'r') as f:
        data = json.load(f)
    
    return data.get("messages", [])

from fastapi.responses import StreamingResponse

@router.post("/{workspace_id}/{thread_id}/chat")
async def chat_in_thread(workspace_id: str, thread_id: str, request: ChatRequest):
    path = get_thread_path(workspace_id, thread_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Thread not found")
        
    # 1. Load History
    with open(path, 'r') as f:
        thread_data = json.load(f)
        
    stored_messages = thread_data.get("messages", [])
    
    # Convert stored dicts to LangChain messages
    langchain_messages = []
    for m in stored_messages:
        if m["role"] == "user":
            langchain_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            langchain_messages.append(AIMessage(content=m["content"]))
            
    # 2. Add New Message
    new_human_msg = HumanMessage(content=request.message)
    langchain_messages.append(new_human_msg)
    
    initial_state = {
        "messages": langchain_messages,
        "context": "",
        "workspace_id": workspace_id
    }
    
    async def event_generator():
        full_response = ""
        try:
            # astream_events yields events from all nodes/tools/llms
            async for event in app_agent.astream_events(initial_state, version="v1", config={"recursion_limit": 100}):
                kind = event["event"]
                name = event.get("name", "")
                
                # 1. Output LLM Tokens (Chat Response)
                if kind == "on_chat_model_stream":
                    # Only stream tokens from the final generation node (avoid internal LLM calls like json extraction)
                    if event.get("metadata", {}).get("langgraph_node") == "generate":
                        content = event["data"]["chunk"].content
                        if content:
                            full_response += content
                            yield content

                # 1.5 Capture Token Usage
                elif kind == "on_chat_model_end":
                     if event.get("metadata", {}).get("langgraph_node") == "generate":
                         # Only final node
                         output_data = event["data"]["output"]
                         # output_data might be an AIMessage object OR a dict depending on serializer
                         usage = None
                         
                         if hasattr(output_data, "usage_metadata"):
                             usage = output_data.usage_metadata
                         elif isinstance(output_data, dict):
                             usage = output_data.get("usage_metadata")
                             
                         if usage:
                             input_tokens = usage.get("input_tokens", 0)
                             output_tokens = usage.get("output_tokens", 0)
                             usage_str = f"\n\n*(Tokens: {input_tokens} input, {output_tokens} output)*"
                             
                             # Append to full response for storage
                             full_response += usage_str
                             # Stream via yield
                             yield usage_str

                # 2. Output Tool Usage (Progress Indicators)
                elif kind == "on_tool_start" and name not in ["tools", "__start__"]:
                    # We want to show real tools, not the "tools" node itself
                    # Format as a distinct block
                    yield f"\n> 🛠️ **Usage**: `{name}`\n\n"
                    
                # 3. Output Tool Result (Optional, maybe for debugging or verbose mode?)
                # For now, let's just show start.
                        
        except Exception as e:
            print(f"Streaming Error: {e}")
            import traceback
            traceback.print_exc()
            yield f"\n[Error: {str(e)}]"
            
        # 4. Save History (After stream completes)
        # Re-read to minimize race conditions? Ideally yes, but single user for now.
        # We append the user message and the full AI response.
        thread_data["messages"].append({"role": "user", "content": request.message})
        thread_data["messages"].append({"role": "assistant", "content": full_response})
        
        # Update title if needed
        # Logic: If this is the FIRST interaction (2 messages: user + assistant), generate a title.
        # We use a simple LLM call for this.
        if len(thread_data["messages"]) == 2:
             try:
                # Import here to avoid top-level circular issues or just standard practice
                from app.llm_config import llm_config
                
                llm = llm_config.get_chat_llm()
                
                title_prompt = f"""Generate a short, concise title (max 5 words) for this conversation based on the first interaction.
                
                User: {request.message}
                AI: {full_response[:200]}...
                
                Title:"""
                
                title_resp = llm.invoke([HumanMessage(content=title_prompt)])
                new_title = title_resp.content.strip().strip('"')
                thread_data["title"] = new_title
             except Exception as e:
                 print(f"Title Generation Failed: {e}")
                 # Fallback
                 if thread_data["title"] == "New Chat":
                    thread_data["title"] = request.message[:30] + "..."
             
        with open(path, 'w') as f:
            json.dump(thread_data, f, indent=2)

    return StreamingResponse(event_generator(), media_type="text/plain")
