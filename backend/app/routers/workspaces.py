from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Form
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import json
import uuid
from app.memory_store import GraphMemory
from app.llm_config import llm_config
from datetime import datetime
# Postponing import of document_processor to avoid circular deps if any, but should be fine.

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

MEMORY_BASE_DIR = "./memory_data"

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
    enabled_tools: Optional[List[str]] = None
    
    # Context Settings (Per Workspace)
    chat_message_limit: int = 20
    graph_k: int = 3
    graph_depth: int = 1
    graph_include_descriptions: bool = False

def get_config_path(workspace_id: str):
    return os.path.join(MEMORY_BASE_DIR, workspace_id, "config.json")

@router.get("/available_tools")
async def get_available_tools():
    """Returns a list of all available tool names."""
    from app.agent import tools
    return [t.name for t in tools]

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
    scales: List[EmotionScale] = [
        EmotionScale(name="Happiness", value=75, frozen=True),
        EmotionScale(name="Trust", value=75, frozen=True),
        EmotionScale(name="Anger", value=0)
    ]

def get_emotion_path(workspace_id: str):
    return os.path.join(MEMORY_BASE_DIR, workspace_id, "emotion.json")

@router.get("/{workspace_id}/emotions", response_model=EmotionState)
async def get_workspace_emotions(workspace_id: str):
    path = get_emotion_path(workspace_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            # Migration logic for old format
            if 'happiness' in data:
                return EmotionState(
                    motive=data.get('motive', "Help the user"),
                    scales=[
                        EmotionScale(name="Happiness", value=data.get('happiness', 75), frozen=True),
                        EmotionScale(name="Trust", value=data.get('trust', 75), frozen=True),
                        EmotionScale(name="Anger", value=data.get('anger', 0))
                    ]
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
             "happiness": 0-100,
             "trust": 0-100,
             "anger": 0-100,
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
            
            # Load existing to preserve frozen
            existing_emotions = EmotionState()
            if os.path.exists(emotion_path):
                try:
                    with open(emotion_path, 'r') as f:
                        existing_data = json.load(f)
                        if 'happiness' in existing_data: # Migration on load
                             existing_emotions = EmotionState(
                                motive=existing_data.get('motive', ""),
                                scales=[
                                    EmotionScale(name="Happiness", value=existing_data.get('happiness', 50)),
                                    EmotionScale(name="Trust", value=existing_data.get('trust', 50)),
                                    EmotionScale(name="Anger", value=existing_data.get('anger', 0))
                                ]
                            )
                        else:
                            existing_emotions = EmotionState(**existing_data)
                except:
                    pass

            # Parse new emotions from LLM (expecting object with keys as names)
            new_emotions_dict = data.get("emotions", {})
            new_motive = new_emotions_dict.get("motive", "Help the user")
            
            # Construct new scales list
            # We want to keep frozen scales from existing, and update others or add new ones?
            # Strategy: 
            # 1. Map existing scales by name.
            # 2. Iterate new keys (except motive). Update if not frozen.
            # 3. If standard keys (Happiness etc) are missing in new, keep old?
            
            # Actually, the prompt asks for specific structure. Let's update the PROMPT too to be dynamic.
            # But here, let's assume LLM returns a dict mapping Name -> Value.
            
            final_scales = []
            existing_map = {s.name: s for s in existing_emotions.scales}
            
            # We will use the existing scales as the base Source of Truth for *what* scales exist, 
            # OR we allow LLM to invent new ones? User said "allow USER to introduce own sliders".
            # So LLM should probably stick to what exists + maybe standard ones?
            # Or maybe we just update the ones that match?
            
            # For "Generate Persona", it's a reset. So we might redefine the standard set.
            # But if user made a custom "Curiosity" and froze it, we should keep it.
            
            # Let's start with all existing scales
            processed_names = set()
            
            for scale in existing_emotions.scales:
                processed_names.add(scale.name)
                if scale.frozen:
                    final_scales.append(scale)
                else:
                    # Update if present in new data
                    # Check for lower case match too?
                    # new_emotions_dict keys might be lowercase
                    val = None
                    for k, v in new_emotions_dict.items():
                        if k.lower() == scale.name.lower() and isinstance(v, (int, float)):
                            val = int(v)
                            break
                    
                    if val is not None:
                        final_scales.append(EmotionScale(name=scale.name, value=val, frozen=False))
                    else:
                        # Keep old value or reset? Persona generation usually resets. 
                        # Let's keep old value if not mentioned, or reset to 50?
                        # Let's keep old to be safe.
                         final_scales.append(scale)

            # If it's a fresh generation (no existing), we might want to add defaults if empty?
            if not final_scales:
                # Add from new_emotions_dict
                for k, v in new_emotions_dict.items():
                    if k == "motive": continue
                    if isinstance(v, (int, float)):
                        final_scales.append(EmotionScale(name=k.capitalize(), value=int(v)))
            
            # If standard ones are missing in `final_scales` but present in `new_emotions_dict` (and weren't in existing), add them?
            # (Case: Adding a new standard emotion via prompt)
            for k, v in new_emotions_dict.items():
                if k == "motive": continue
                # check if we already processed this name
                name_found = False
                for s in final_scales:
                    if s.name.lower() == k.lower():
                        name_found = True
                        break
                if not name_found and isinstance(v, (int, float)):
                     final_scales.append(EmotionScale(name=k.capitalize(), value=int(v)))

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
