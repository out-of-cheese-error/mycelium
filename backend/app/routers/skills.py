from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import uuid
import time
from app.memory_store import GraphMemory

router = APIRouter(prefix="/workspaces", tags=["skills"])

MEMORY_BASE_DIR = "./memory_data"


class Skill(BaseModel):
    id: str
    title: str
    summary: str
    explanation: str
    updated_at: float


class CreateSkillRequest(BaseModel):
    title: str
    summary: str
    explanation: str


class UpdateSkillRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    explanation: Optional[str] = None


def get_skills_dir(workspace_id: str):
    """Returns the skills directory for a workspace, creating it if needed."""
    base_path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    skills_dir = os.path.join(base_path, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    return skills_dir


@router.get("/{workspace_id}/skills", response_model=List[Skill])
async def list_skills(workspace_id: str):
    """List all skills in a workspace."""
    skills_dir = get_skills_dir(workspace_id)
    skills = []
    
    for filename in os.listdir(skills_dir):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(skills_dir, filename), 'r') as f:
                    data = json.load(f)
                    skills.append(Skill(**data))
            except:
                continue
    
    # Sort by updated_at desc
    skills.sort(key=lambda s: s.updated_at, reverse=True)
    return skills


@router.post("/{workspace_id}/skills", response_model=Skill)
async def create_skill(workspace_id: str, request: CreateSkillRequest):
    """Create a new skill."""
    skills_dir = get_skills_dir(workspace_id)
    skill_id = str(uuid.uuid4())[:8]
    
    skill = Skill(
        id=skill_id,
        title=request.title or "Untitled Skill",
        summary=request.summary or "",
        explanation=request.explanation or "",
        updated_at=time.time()
    )
    
    with open(os.path.join(skills_dir, f"{skill_id}.json"), 'w') as f:
        json.dump(skill.dict(), f, indent=2)

    # Sync Embedding
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
        mem.index_skill(skill_id, skill.title, skill.summary, skill.explanation)
    except Exception as e:
        print(f"Skill embedding sync failed: {e}")
        
    return skill


@router.get("/{workspace_id}/skills/{skill_id}", response_model=Skill)
async def get_skill(workspace_id: str, skill_id: str):
    """Get a specific skill by ID."""
    skills_dir = get_skills_dir(workspace_id)
    path = os.path.join(skills_dir, f"{skill_id}.json")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Skill not found")
        
    with open(path, 'r') as f:
        data = json.load(f)
        return Skill(**data)


@router.put("/{workspace_id}/skills/{skill_id}", response_model=Skill)
async def update_skill(workspace_id: str, skill_id: str, request: UpdateSkillRequest):
    """Update an existing skill."""
    skills_dir = get_skills_dir(workspace_id)
    path = os.path.join(skills_dir, f"{skill_id}.json")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Skill not found")
        
    with open(path, 'r') as f:
        data = json.load(f)
        
    if request.title is not None:
        data["title"] = request.title
    if request.summary is not None:
        data["summary"] = request.summary
    if request.explanation is not None:
        data["explanation"] = request.explanation
    
    data["updated_at"] = time.time()
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

    # Sync Embedding
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
        mem.index_skill(skill_id, data["title"], data["summary"], data["explanation"])
    except Exception as e:
        print(f"Skill embedding sync failed: {e}")
        
    return Skill(**data)


@router.delete("/{workspace_id}/skills/{skill_id}")
async def delete_skill(workspace_id: str, skill_id: str):
    """Delete a skill."""
    skills_dir = get_skills_dir(workspace_id)
    path = os.path.join(skills_dir, f"{skill_id}.json")
    
    if os.path.exists(path):
        os.remove(path)
        
        # Sync Embedding
        try:
            mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
            mem.delete_skill_embedding(skill_id)
        except Exception as e:
            print(f"Skill embedding sync failed: {e}")
            
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Skill not found")
