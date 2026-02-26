from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import json
import uuid
import re
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.agent import app_agent, run_background_extraction_and_emotions

from datetime import datetime

def strip_markdown_from_title(title: str) -> str:
    """Remove common markdown syntax from a title string."""
    # Remove leading # (headers)
    title = re.sub(r'^#+\s*', '', title)
    # Remove bold markers ** or __
    title = re.sub(r'\*\*|__', '', title)
    # Remove italic markers * or _
    title = re.sub(r'(?<!\*)\*(?!\*)|\b_\b', '', title)
    # Remove backticks
    title = title.replace('`', '')
    return title.strip()

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


class CreateThreadWithMessagesRequest(BaseModel):
    workspace_id: str
    title: Optional[str] = "Graph Chat"
    messages: List[Dict]  # List of {role: str, content: str}


@router.post("/with_messages", response_model=Thread)
async def create_thread_with_messages(request: CreateThreadWithMessagesRequest):
    """Creates a new thread with pre-populated messages (for carrying graph chat over)."""
    thread_id = str(uuid.uuid4())[:8]
    thread_data = {
        "id": thread_id,
        "workspace_id": request.workspace_id,
        "title": request.title,
        "created_at": datetime.now().isoformat(),
        "messages": request.messages
    }
    
    path = get_thread_path(request.workspace_id, thread_id)
    with open(path, 'w') as f:
        json.dump(thread_data, f, indent=2)
        
    return Thread(id=thread_id, workspace_id=request.workspace_id, title=request.title, created_at=thread_data["created_at"])

@router.delete("/{workspace_id}/{thread_id}")
async def delete_thread(workspace_id: str, thread_id: str):
    path = get_thread_path(workspace_id, thread_id)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Thread not found")

@router.delete("/{workspace_id}")
async def delete_all_threads(workspace_id: str):
    """Delete all threads in a workspace."""
    thread_dir = get_thread_dir(workspace_id)
    if not os.path.exists(thread_dir):
        return {"status": "deleted", "count": 0}
    
    deleted_count = 0
    for filename in os.listdir(thread_dir):
        if filename.endswith(".json"):
            try:
                os.remove(os.path.join(thread_dir, filename))
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {filename}: {e}")
    
    return {"status": "deleted", "count": deleted_count}

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
        full_raw = ""  # All raw LLM output (for thinking/response separation at end)
        full_extra = ""  # Non-LLM content (tool indicators, token usage)

        from app.llm_config import llm_config as _llm_config
        from app.utils.thinking import strip_thinking, extract_thinking
        thinking_enabled = _llm_config.get_config().thinking_enabled

        # When thinking is disabled, buffer to strip think tags before yielding
        strip_buffer = ""

        try:
            # astream_events yields events from all nodes/tools/llms
            async for event in app_agent.astream_events(initial_state, version="v1", config={"recursion_limit": 100}):
                kind = event["event"]
                name = event.get("name", "")

                # 1. Output LLM Tokens (Chat Response)
                if kind == "on_chat_model_stream":
                    # Only stream tokens from the generate node
                    if event.get("metadata", {}).get("langgraph_node") == "generate":
                        content = event["data"]["chunk"].content
                        if not content:
                            continue

                        if not thinking_enabled:
                            # Strip think tags silently
                            strip_buffer += content
                            # Only buffer if we see an explicit <think> without closing tag yet
                            if "<think>" in strip_buffer and "</think>" not in strip_buffer:
                                continue
                            if "<think>" in strip_buffer or "</think>" in strip_buffer:
                                # Has think tags - strip them
                                clean = strip_thinking(strip_buffer)
                            else:
                                # No think tags - yield as-is (preserves whitespace)
                                clean = strip_buffer
                            if clean:
                                full_raw += strip_buffer
                                yield clean
                            strip_buffer = ""
                            continue

                        # Thinking enabled: yield raw content, frontend handles display
                        full_raw += content
                        yield content

                # 1.5 Capture Token Usage
                elif kind == "on_chat_model_end":
                     if event.get("metadata", {}).get("langgraph_node") == "generate":
                         output_data = event["data"]["output"]
                         usage = None

                         if hasattr(output_data, "usage_metadata"):
                             usage = output_data.usage_metadata
                         elif isinstance(output_data, dict):
                             usage = output_data.get("usage_metadata")

                             if not usage and "generations" in output_data:
                                 try:
                                     gens = output_data["generations"]
                                     if gens and len(gens) > 0 and gens[0]:
                                         first_gen = gens[0][0]
                                         if isinstance(first_gen, dict):
                                              msg = first_gen.get("message")
                                              if hasattr(msg, "usage_metadata"):
                                                  usage = msg.usage_metadata
                                         elif hasattr(first_gen, "message"):
                                              msg = first_gen.message
                                              if hasattr(msg, "usage_metadata"):
                                                  usage = msg.usage_metadata
                                 except Exception as e:
                                     print(f"Error extracting usage from generations: {e}")

                         if usage:
                             input_tokens = usage.get("input_tokens", 0)
                             output_tokens = usage.get("output_tokens", 0)
                             usage_str = f"\n\n*(Tokens: {input_tokens} input, {output_tokens} output)*"
                             full_extra += usage_str
                             yield usage_str

                # 2. Output Tool Usage (Progress Indicators)
                elif kind == "on_tool_start" and name not in ["tools", "__start__"]:
                    yield f"\n> 🛠️ **Usage**: `{name}`\n\n"

        except Exception as e:
            print(f"Streaming Error: {e}")
            import traceback
            traceback.print_exc()
            yield f"\n[Error: {str(e)}]"

        # Flush remaining strip buffer (thinking_disabled path)
        if strip_buffer:
            clean = strip_thinking(strip_buffer)
            if clean:
                full_raw += strip_buffer
                yield clean

        # Separate thinking from response for storage
        thinking, clean_response = extract_thinking(full_raw)
        # Append token usage to the clean response for storage
        full_response = clean_response + full_extra

        # Save History
        thread_data["messages"].append({"role": "user", "content": request.message})
        thread_data["messages"].append({
            "role": "assistant",
            "content": full_response,
            "thinking": thinking if thinking else None
        })
        
        # Update title if needed
        # Logic: If this is the FIRST interaction (2 messages: user + assistant), generate a title.
        # We use a simple LLM call for this.
        if len(thread_data["messages"]) == 2:
             try:
                # Import here to avoid top-level circular issues or just standard practice
                from app.llm_config import llm_config
                
                llm = llm_config.get_ingestion_llm()
                
                title_prompt = f"""Generate a short, concise title (max 5 words) for this conversation based on the first interaction.
                
                User: {request.message}
                AI: {full_response[:200]}...
                
                Title:"""
                
                title_resp = llm.invoke([HumanMessage(content=title_prompt)])
                from app.utils.thinking import strip_thinking
                new_title = strip_markdown_from_title(strip_thinking(title_resp.content).strip('"'))
                thread_data["title"] = new_title
             except Exception as e:
                 print(f"Title Generation Failed: {e}")
                 # Fallback
                 if thread_data["title"] == "New Chat":
                    thread_data["title"] = request.message[:30] + "..."
             
        with open(path, 'w') as f:
            json.dump(thread_data, f, indent=2)

        # Fire background extraction and emotion update (non-blocking)
        import threading
        t = threading.Thread(
            target=run_background_extraction_and_emotions,
            args=(workspace_id, request.message, clean_response),
            daemon=True
        )
        t.start()

    return StreamingResponse(event_generator(), media_type="text/plain")
