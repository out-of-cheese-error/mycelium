from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Form
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import json
import uuid
from app.memory_store import GraphMemory, get_memory_base_dir
from app.llm_config import llm_config
from datetime import datetime
# Postponing import of document_processor to avoid circular deps if any, but should be fine.

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Set at import time from config (restart required for changes to take effect)
MEMORY_BASE_DIR = get_memory_base_dir()

class Workspace(BaseModel):
    id: str
    node_count: int
    edge_count: int

class CreateWorkspaceRequest(BaseModel):
    workspace_id: str

@router.get("/", response_model=List[Workspace])
async def list_workspaces():
    workspaces = []
    if not os.path.exists(MEMORY_BASE_DIR):
        return []
    
    for item in os.listdir(MEMORY_BASE_DIR):
        item_path = os.path.join(MEMORY_BASE_DIR, item)
        if os.path.isdir(item_path):
            try:
                mem = GraphMemory(workspace_id=item, base_dir=MEMORY_BASE_DIR)
                stats = mem.get_stats()
                workspaces.append(Workspace(
                    id=item,
                    node_count=stats["node_count"],
                    edge_count=stats["edge_count"]
                ))
            except Exception:
                continue
    return workspaces

@router.post("/", response_model=Workspace)
async def create_workspace(request: CreateWorkspaceRequest):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\s]+$', request.workspace_id):
         raise HTTPException(status_code=400, detail="Workspace ID must be alphanumeric (spaces, dashes, and underscores allowed)")
    
    path = os.path.join(MEMORY_BASE_DIR, request.workspace_id)
    if os.path.exists(path):
         raise HTTPException(status_code=400, detail="Workspace already exists")
    
    mem = GraphMemory(workspace_id=request.workspace_id, base_dir=MEMORY_BASE_DIR)
    stats = mem.get_stats()
    return Workspace(id=request.workspace_id, node_count=stats["node_count"], edge_count=stats["edge_count"])

@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str):
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if os.path.exists(path):
        shutil.rmtree(path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Workspace not found")

class RenameWorkspaceRequest(BaseModel):
    new_workspace_id: str

@router.post("/{workspace_id}/rename")
async def rename_workspace(workspace_id: str, request: RenameWorkspaceRequest):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\s]+$', request.new_workspace_id):
         raise HTTPException(status_code=400, detail="New Workspace ID must be alphanumeric (spaces, dashes, and underscores allowed)")

    base_path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    new_path = os.path.join(MEMORY_BASE_DIR, request.new_workspace_id)
    
    if not os.path.exists(base_path):
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Workspace with new name already exists")
        
    try:
        shutil.move(base_path, new_path)
        return {"status": "success", "old_id": workspace_id, "new_id": request.new_workspace_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rename failed: {str(e)}")

@router.get("/{workspace_id}/stats")
async def get_workspace_stats(workspace_id: str):
    mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    return mem.get_stats()

class WorkspaceSettings(BaseModel):
    system_prompt: str = "You are a helpful assistant with a long-term memory."
    allow_search: bool = True
    # Default enabled tools - MCP and other categories disabled by default
    enabled_tools: Optional[List[str]] = [
        # Search & Web
        "duckduckgo_search", "visit_page", "search_images", "search_books", "search_authors",
        # Knowledge & Notes
        "create_note", "read_note", "update_note", "list_notes", "delete_note", "search_notes",
        # Graph Operations
        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", 
        "search_graph_nodes", "traverse_graph_node", "search_concepts",
        # Ingestion
        "search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia", 
        "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page",
        # Science / Research
        "search_biorxiv", "read_biorxiv_abstract", "search_arxiv", "read_arxiv_abstract", "ingest_arxiv_paper",
        # Utility
        "generate_lesson"
    ]
    
    # Context Settings (Per Workspace)
    chat_message_limit: int = 20
    graph_k: int = 3
    graph_depth: int = 1
    graph_include_descriptions: bool = False
    
    # Workspace-as-Tool Settings
    is_tool_enabled: bool = False
    tool_name: Optional[str] = None  # e.g., "physics_expert" -> becomes "ask_physics_expert"
    tool_description: Optional[str] = None

def get_config_path(workspace_id: str):
    return os.path.join(MEMORY_BASE_DIR, workspace_id, "config.json")

@router.get("/available_tools")
async def get_available_tools():
    """Returns a categorized list of all available tools."""
    from app.agent import tools
    from app.services.mcp_service import mcp_service
    
    # Get builtin tool names
    builtin_tools = [t.name for t in tools]
    
    # Get MCP tools (if any servers are connected)
    mcp_tools = []
    for server_name, server in mcp_service._servers.items():
        if server.connected:
            for tool in server.tools:
                mcp_tools.append({
                    "name": f"mcp_{server_name}_{tool.get('name', '')}".replace("-", "_").replace(".", "_"),
                    "server": server_name,
                    "original_name": tool.get("name", ""),
                    "description": tool.get("description", "")
                })
    
    return {
        "builtin": builtin_tools,
        "mcp": mcp_tools
    }

@router.get("/exposed_tools")
async def get_exposed_tools():
    """Returns list of workspaces exposed as tools."""
    from app.services.workspace_tool_service import get_exposed_workspace_tools
    return get_exposed_workspace_tools()

@router.post("/{workspace_id}/generate_tool_description")
async def generate_tool_description_endpoint(workspace_id: str):
    """Generates a tool description based on workspace concepts using LLM."""
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    from app.services.workspace_tool_service import generate_tool_description
    try:
        description = await generate_tool_description(workspace_id)
        return {"description": description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate description: {str(e)}")

@router.get("/{workspace_id}/settings", response_model=WorkspaceSettings)
async def get_workspace_settings(workspace_id: str):
    config_path = get_config_path(workspace_id)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return WorkspaceSettings(**data)
        except:
            pass
    # Default: return definition with enabled_tools=None (implies all)
    return WorkspaceSettings()

@router.post("/{workspace_id}/settings", response_model=WorkspaceSettings)
async def update_workspace_settings(workspace_id: str, settings: WorkspaceSettings):
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(path):
         raise HTTPException(status_code=404, detail="Workspace not found")
    
    config_path = get_config_path(workspace_id)
    with open(config_path, 'w') as f:
        json.dump(settings.dict(), f, indent=2)
        
    return settings

class EmotionScale(BaseModel):
    name: str 
    value: int # 0-100
    frozen: bool = False

class EmotionState(BaseModel):
    motive: str = "Help the user"
    scales: List[EmotionScale] = []  # Empty by default - user adds their own

def get_emotion_path(workspace_id: str):
    return os.path.join(MEMORY_BASE_DIR, workspace_id, "emotion.json")

@router.get("/{workspace_id}/emotions", response_model=EmotionState)
async def get_workspace_emotions(workspace_id: str):
    path = get_emotion_path(workspace_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            # Migration logic for old flat format -> convert to scales array
            if 'happiness' in data and 'scales' not in data:
                # Old format detected, migrate dynamically
                migrated_scales = []
                for key, value in data.items():
                    if key == 'motive':
                        continue
                    if isinstance(value, (int, float)):
                        migrated_scales.append(
                            EmotionScale(name=key.capitalize(), value=int(value), frozen=False)
                        )
                return EmotionState(
                    motive=data.get('motive', "Help the user"),
                    scales=migrated_scales
                )
            
            return EmotionState(**data)
        except Exception as e:
            print(f"Error loading emotions: {e}")
            pass
    return EmotionState()

@router.post("/{workspace_id}/emotions", response_model=EmotionState)
async def update_workspace_emotions(workspace_id: str, emotions: EmotionState):
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(path):
         raise HTTPException(status_code=404, detail="Workspace not found")
    
    emotion_path = get_emotion_path(workspace_id)
    with open(emotion_path, 'w') as f:
        json.dump(emotions.dict(), f, indent=2)
    return emotions

@router.post("/{workspace_id}/upload")
async def upload_document(
    workspace_id: str, 
    file: UploadFile = File(...),
    chunk_size: int = 4800,
    chunk_overlap: int = 400
):
    from fastapi import Form
    # Note: When using File(...), other params must be Form(...) implicitly if simple types, 
    # but explicit Form() is safer mixed with File
    
    # Save file temporarily
    temp_dir = f"temp/{workspace_id}"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Process
    try:
        from app.document_processor import process_file
        import uuid
        job_id = str(uuid.uuid4())
        # We can fire and forget, OR await. 
        # Since the UI now polls for jobs, we might want to just start it?
        # But this function returns "result" (extraction count). This implies awaiting.
        # So we await it, but we also pass job_id so it shows up in the status list.
        result = await process_file(file_path, workspace_id, chunk_size, chunk_overlap, job_id=job_id)
        os.remove(file_path) # Cleanup
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workspace_id}/ingest_status")
async def get_ingest_status(workspace_id: str):
    from app.document_processor import get_status
    return get_status(workspace_id)

@router.post("/{workspace_id}/ingest/stop")
async def stop_ingest(workspace_id: str, job_id: str):
    from app.document_processor import stop_ingestion
    stopped = stop_ingestion(workspace_id, job_id)
    return {"status": "stopped" if stopped else "not_running"}

class IngestUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None

@router.post("/{workspace_id}/ingest-url")
async def ingest_url(workspace_id: str, request: IngestUrlRequest, background_tasks: BackgroundTasks):
    """
    Ingest a web page or PDF URL into the knowledge graph.
    Used by the Chrome extension for quick ingestion.
    """
    import httpx
    from bs4 import BeautifulSoup
    
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(path):
        # Create workspace if it doesn't exist
        GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        
        # Check if URL is a PDF (by extension, query params, or common patterns)
        url_lower = request.url.lower()
        is_pdf = url_lower.endswith('.pdf') or '.pdf?' in url_lower or '/pdf/' in url_lower
        
        # Also check content-type for PDFs that don't have .pdf extension
        if not is_pdf:
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
                    head_resp = await client.head(request.url)
                    content_type = head_resp.headers.get('content-type', '').lower()
                    is_pdf = 'application/pdf' in content_type
            except Exception:
                pass  # If HEAD fails, assume not PDF
        
        # Prepare temp directory
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        safe_name = "".join(x for x in request.url.split("//")[-1] if x.isalnum() or x in "-_.")[:50]
        
        if is_pdf:
            # PDF: Download the file directly
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(request.url)
                resp.raise_for_status()
                
                filename = f"pdf_{safe_name}_{uuid.uuid4().hex[:6]}.pdf"
                file_path = os.path.join(temp_dir, filename)
                
                with open(file_path, "wb") as f:
                    f.write(resp.content)
                    
                print(f"Downloaded PDF: {file_path} ({len(resp.content)} bytes)")
        else:
            # HTML: Extract text content
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(request.url)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                # Remove scripts and styles
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                    
                text = soup.get_text(separator="\n")
                
                # Clean
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
            if not text:
                raise HTTPException(status_code=400, detail="Extracted text is empty")
            
            filename = f"web_{safe_name}_{uuid.uuid4().hex[:6]}.txt"
            file_path = os.path.join(temp_dir, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"URL: {request.url}\n\n{text}")
            
        # Ingest in background with appropriate chunk size
        from app.document_processor import process_file
        job_id = str(uuid.uuid4())
        
        # Use larger chunks for PDFs to reduce total chunk count
        chunk_size = 6000 if is_pdf else 4000
        
        async def do_ingest():
            try:
                await process_file(file_path, workspace_id, chunk_size=chunk_size, job_id=job_id)
                os.remove(file_path)
            except Exception as e:
                print(f"Ingestion error: {e}")
        
        # Run in background
        import asyncio
        asyncio.create_task(do_ingest())
        
        return {
            "status": "started",
            "job_id": job_id,
            "message": f"Ingesting {'PDF' if is_pdf else 'page'}: {request.url}",
            "url": request.url,
            "title": request.title,
            "is_pdf": is_pdf
        }
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

import time

class Note(BaseModel):
    id: str
    title: str
    content: str
    updated_at: float

class CreateNoteRequest(BaseModel):
    title: str
    content: str

class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

def get_notes_dir(workspace_id: str):
    base_path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    notes_dir = os.path.join(base_path, "notes")
    
    # Migration: If notes.md exists but notes/ doesn't, migrate it.
    old_notes_path = os.path.join(base_path, "notes.md")
    if os.path.exists(old_notes_path) and not os.path.exists(notes_dir):
        os.makedirs(notes_dir, exist_ok=True)
        with open(old_notes_path, 'r') as f:
            content = f.read()
        
        # Create a "General" note from the old file
        note_id = str(uuid.uuid4())[:8]
        new_note_path = os.path.join(notes_dir, f"{note_id}.json")
        note_data = {
            "id": note_id,
            "title": "General",
            "content": content,
            "updated_at": time.time()
        }
        with open(new_note_path, 'w') as f:
            json.dump(note_data, f, indent=2)
            
        # Rename old file to backup/hidden to avoid confusion? Or just leave it.
        # Let's rename it to notes.md.bak
        os.rename(old_notes_path, os.path.join(base_path, "notes.md.bak"))
    
    os.makedirs(notes_dir, exist_ok=True)
    return notes_dir

@router.get("/{workspace_id}/notes", response_model=List[Note])
async def list_notes(workspace_id: str):
    notes_dir = get_notes_dir(workspace_id)
    notes = []
    
    for filename in os.listdir(notes_dir):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(notes_dir, filename), 'r') as f:
                    data = json.load(f)
                    notes.append(Note(**data))
            except:
                continue
    
    # Sort by updated_at desc
    notes.sort(key=lambda n: n.updated_at, reverse=True)
    return notes

@router.post("/{workspace_id}/notes", response_model=Note)
async def create_note(workspace_id: str, request: CreateNoteRequest):
    notes_dir = get_notes_dir(workspace_id)
    note_id = str(uuid.uuid4())[:8]
    
    note = Note(
        id=note_id,
        title=request.title or "Untitled Note",
        content=request.content or "",
        updated_at=time.time()
    )
    
    with open(os.path.join(notes_dir, f"{note_id}.json"), 'w') as f:
        json.dump(note.dict(), f, indent=2)

    # Sync Embedding
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
        mem.index_note(note_id, note.title, note.content)
    except Exception as e:
        print(f"Embedding sync failed: {e}")
        
    return note

@router.get("/{workspace_id}/notes/{note_id}", response_model=Note)
async def get_note(workspace_id: str, note_id: str):
    notes_dir = get_notes_dir(workspace_id)
    path = os.path.join(notes_dir, f"{note_id}.json")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Note not found")
        
    with open(path, 'r') as f:
        data = json.load(f)
        return Note(**data)

@router.put("/{workspace_id}/notes/{note_id}", response_model=Note)
async def update_note(workspace_id: str, note_id: str, request: UpdateNoteRequest):
    notes_dir = get_notes_dir(workspace_id)
    path = os.path.join(notes_dir, f"{note_id}.json")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Note not found")
        
    with open(path, 'r') as f:
        data = json.load(f)
        
    if request.title is not None:
        data["title"] = request.title
    if request.content is not None:
        data["content"] = request.content
    
    data["updated_at"] = time.time()
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

    # Sync Embedding
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
        mem.index_note(note_id, data["title"], data["content"])
    except Exception as e:
        print(f"Embedding sync failed: {e}")
        
    return Note(**data)

@router.delete("/{workspace_id}/notes/{note_id}")
async def delete_note(workspace_id: str, note_id: str):
    notes_dir = get_notes_dir(workspace_id)
    path = os.path.join(notes_dir, f"{note_id}.json")
    
    if os.path.exists(path):
        os.remove(path)
        
        # Sync Embedding
        try:
            mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
            mem.delete_note_embedding(note_id)
        except Exception as e:
            print(f"Embedding sync failed: {e}")
            
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Note not found")

class GeneratePersonaRequest(BaseModel):
    cues: str

# Helper to avoid circular imports
def get_llm_helper():
    from app.llm_config import llm_config
    return llm_config.get_chat_llm()

from langchain_core.messages import HumanMessage

@router.post("/{workspace_id}/generate_persona")
async def generate_persona(workspace_id: str, request: GeneratePersonaRequest):
    """Generates a persona (system prompt, emotion, memories) based on cues."""
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(path):
         raise HTTPException(status_code=404, detail="Workspace not found")
         
    llm = get_llm_helper()
    
    prompt = f"""You are a creative writer and psychologist. 
    Your task is to create a detailed persona for an AI assistant based on the following cues.
    
    CUES: "{request.cues}"
    
    You must output a valid JSON object with the following structure:
    {{
        "system_prompt": "A detailed system prompt describing the AI's role, tone, style, and constraints. Used for 'Base System Prompt'.",
        "emotions": {{
             "emotion_name_1": 0-100,
             "emotion_name_2": 0-100,
             ... (add any relevant emotions for this persona, e.g. happiness, curiosity, anger, melancholy, etc.)
             "motive": "A primary driving goal or motive string."
        }},
        "memories": {{
             "entities": [
                 {{ "name": "Name", "type": "Type", "description": "Backstory fact" }}
             ],
             "relations": [
                 {{ "source": "Entity1", "target": "Entity2", "relation": "relationship" }}
             ]
        }}
    }}
    
    GUIDELINES:
    - Create a rich backstory.
    - For emotions, include 3-6 relevant emotional dimensions that fit the persona (e.g., curiosity, fear, joy, anger, trust).
    - Generate at least 5-10 initial memory entities (friends, enemies, locations, past events relevant to the persona).
    - The system prompt should be immersive.
    - Output ONLY the JSON.
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Clean markdown
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            
            # 1. Update System Prompt (config.json)
            config_path = get_config_path(workspace_id)
            current_config = {"allow_search": True}
            if os.path.exists(config_path):
                 with open(config_path, 'r') as f:
                     current_config = json.load(f)
            
            current_config["system_prompt"] = data.get("system_prompt", "You are a helpful assistant.")
            with open(config_path, 'w') as f:
                json.dump(current_config, f, indent=2)
                
            # 2. Update Emotions (emotion.json)
            emotion_path = get_emotion_path(workspace_id)
            
            # Load existing to preserve frozen scales
            existing_emotions = EmotionState()
            if os.path.exists(emotion_path):
                try:
                    with open(emotion_path, 'r') as f:
                        existing_data = json.load(f)
                        # Handle new format
                        if 'scales' in existing_data:
                            existing_emotions = EmotionState(**existing_data)
                        # Migration from old flat format
                        elif 'happiness' in existing_data:
                            migrated_scales = []
                            for key, value in existing_data.items():
                                if key == 'motive':
                                    continue
                                if isinstance(value, (int, float)):
                                    migrated_scales.append(
                                        EmotionScale(name=key.capitalize(), value=int(value), frozen=False)
                                    )
                            existing_emotions = EmotionState(
                                motive=existing_data.get('motive', ""),
                                scales=migrated_scales
                            )
                except:
                    pass

            # Parse new emotions from LLM (expecting object with keys as emotion names -> values)
            new_emotions_dict = data.get("emotions", {})
            new_motive = new_emotions_dict.get("motive", "Help the user")
            
            # Build final scales list
            # Strategy: Keep frozen scales, update non-frozen if LLM provided value, add new ones from LLM
            final_scales = []
            existing_map = {s.name.lower(): s for s in existing_emotions.scales}
            processed_names = set()
            
            # First, process existing scales
            for scale in existing_emotions.scales:
                processed_names.add(scale.name.lower())
                if scale.frozen:
                    # Keep frozen scales as-is
                    final_scales.append(scale)
                else:
                    # Update with LLM value if provided
                    val = None
                    for k, v in new_emotions_dict.items():
                        if k.lower() == scale.name.lower() and isinstance(v, (int, float)):
                            val = int(v)
                            break
                    
                    if val is not None:
                        final_scales.append(EmotionScale(name=scale.name, value=val, frozen=False))
                    else:
                        # Keep existing value
                        final_scales.append(scale)

            # Add new emotions from LLM that don't exist yet
            for k, v in new_emotions_dict.items():
                if k.lower() == "motive":
                    continue
                if k.lower() not in processed_names and isinstance(v, (int, float)):
                    final_scales.append(EmotionScale(name=k.capitalize(), value=int(v), frozen=False))

            with open(emotion_path, 'w') as f:
                json.dump({
                    "motive": new_motive,
                    "scales": [s.dict() for s in final_scales]
                }, f, indent=2)
                
            # 3. Seed Memories
            memories = data.get("memories", {})
            mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
            
            # Clear existing memory? Maybe not. Just append.
            # Actually, for a fresh persona, we might want to clear, but "Generate" implies adding or setting.
            # Let's just add to be safe, user can clear workspace if they want.
            
            count = 0
            for entity in memories.get("entities", []):
                mem.add_entity(entity["name"], entity["type"], entity["description"])
                count += 1
                
            for rel in memories.get("relations", []):
                mem.add_relation(rel["source"], rel["target"], rel["relation"])
            
            return {
                "status": "success", 
                "message": f"Persona generated. Updated system prompt, emotions, and added {count} memory entities."
            }
            
        else:
            raise ValueError("LLM returned invalid JSON format.")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

# --- Script / Learn Tab Endpoints ---

class GenerateScriptRequest(BaseModel):
    topic: str

from app.services.script_service import generate_script_logic, get_scripts_dir
from app.services.contemplation_service import contemplate_logic, stop_contemplation

@router.post("/{workspace_id}/contemplate")
async def contemplate_workspace(workspace_id: str, n: int = 3, topic: str = None, save_to_notes: bool = False, depth: int = 1, job_id: str = None):
    print(f"DEBUG RODUTER: Received contemplate request. ws={workspace_id}, n={n}, depth={depth}, topic={topic}, job_id={job_id}")
    return await contemplate_logic(workspace_id, n, topic, save_to_notes, depth, job_id)

@router.post("/{workspace_id}/contemplate/stop")
async def stop_contemplate_workspace(workspace_id: str, job_id: str):
    stopped = stop_contemplation(job_id)
    return {"status": "stopped" if stopped else "not_found"}

@router.get("/{workspace_id}/knowledge_gaps")
async def get_knowledge_gaps(
    workspace_id: str, 
    limit: int = 10, 
    max_degree: int = 2
):
    """
    Returns nodes with low connectivity (knowledge gaps).
    These are topics that could benefit from expansion.
    """
    path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    return mem.get_knowledge_gaps(limit=limit, max_degree=max_degree)


@router.post("/{workspace_id}/scripts/generate")
async def generate_script(workspace_id: str, request: GenerateScriptRequest):
    try:
        return await generate_script_logic(workspace_id, request.topic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workspace_id}/scripts")
async def list_scripts(workspace_id: str):
    scripts_dir = get_scripts_dir(workspace_id)
    scripts = []
    if os.path.exists(scripts_dir):
        for filename in os.listdir(scripts_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(scripts_dir, filename), 'r') as f:
                        scripts.append(json.load(f))
                except:
                    continue
    # Sort by created_at desc
    scripts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return scripts

@router.delete("/{workspace_id}/scripts/{script_id}")
async def delete_script(workspace_id: str, script_id: str):
    scripts_dir = get_scripts_dir(workspace_id)
    path = os.path.join(scripts_dir, f"{script_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return {"status": "deleted", "id": script_id}
    else:
        raise HTTPException(status_code=404, detail="Script not found")

# --- Graph Import/Export ---
from fastapi.responses import FileResponse
from networkx.readwrite import json_graph

@router.get("/{workspace_id}/graph/export")
async def export_graph(workspace_id: str):
    path = os.path.join(MEMORY_BASE_DIR, workspace_id, "graph.json")
    if not os.path.exists(path):
         raise HTTPException(status_code=404, detail="No graph found for this workspace")
    
    filename = f"graph_export_{workspace_id}_{int(time.time())}.json"
    return FileResponse(path, media_type='application/json', filename=filename)

@router.post("/{workspace_id}/graph/import")
async def import_graph(workspace_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # 1. Validate File
    try:
        content = await file.read()
        data = json.loads(content)
        # Basic validation: try to parse as graph
        import networkx as nx
        # Ensure 'links' key exists for compatibility if missing
        if 'links' not in data and 'edges' in data:
            data['links'] = data['edges']
        elif 'links' not in data:
            data['links'] = []
            
        g = nx.node_link_graph(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid graph JSON file: {e}")
        
    # 2. Backup Existing
    base_path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(base_path):
        os.makedirs(base_path, exist_ok=True)
        
    graph_path = os.path.join(base_path, "graph.json")
    if os.path.exists(graph_path):
        backup_path = os.path.join(base_path, f"graph.json.bak_{int(time.time())}")
        shutil.copy(graph_path, backup_path)
        
    # 3. Save New Graph
    with open(graph_path, 'w') as f:
        json.dump(data, f)
        
    # 4. Trigger Re-indexing
    # We define a helper task wrapper
    def run_reindex(wid):
        try:
            mem = GraphMemory(workspace_id=wid, base_dir=MEMORY_BASE_DIR)
            mem.reindex_graph()
        except Exception as e:
            print(f"Background reindex failed: {e}")

    background_tasks.add_task(run_reindex, workspace_id)
    
    return {"status": "success", "message": "Graph imported. Re-indexing in background.", "node_count": len(g.nodes)}
