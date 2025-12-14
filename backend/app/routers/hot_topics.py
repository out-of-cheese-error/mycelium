from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.memory_store import GraphMemory

router = APIRouter(prefix="/hot_topics", tags=["hot_topics"])

@router.get("/{workspace_id}")
async def get_hot_topics(
    workspace_id: str,
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get top nodes sorted by degree centrality.
    """
    memory = GraphMemory(workspace_id=workspace_id)
    try:
        return memory.get_hot_topics(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
