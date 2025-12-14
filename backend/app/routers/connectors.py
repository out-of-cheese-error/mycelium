from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.memory_store import GraphMemory

router = APIRouter(prefix="/connectors", tags=["connectors"])

@router.get("/{workspace_id}")
async def get_connectors(
    workspace_id: str,
    limit: int = Query(10, ge=1, le=100),
    sample_size: Optional[int] = Query(None, ge=1, le=5000, description="Approximate with k nodes to improve speed")
):
    """
    Get top nodes sorted by betweenness centrality (connectors).
    """
    memory = GraphMemory(workspace_id=workspace_id)
    try:
        return memory.get_connectors(limit=limit, sample_size=sample_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
