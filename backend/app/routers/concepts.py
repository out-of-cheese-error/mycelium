from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel
from typing import List, Optional
from app.services.concept_service import ConceptService

router = APIRouter(prefix="/concepts", tags=["concepts"])

class GenerateRequest(BaseModel):
    workspace_id: str
    resolution: float = 1.0
    max_clusters: int = 5
    min_cluster_size: int = 5

@router.get("/{workspace_id}")
async def get_concepts(workspace_id: str):
    """Get existing concepts for a workspace."""
    service = ConceptService(workspace_id)
    return service.get_concepts()

@router.post("/generate")
async def generate_concepts(request: GenerateRequest):
    """Trigger generation of concepts, streaming results as NDJSON."""
    service = ConceptService(request.workspace_id)
    
    async def generator():
        async for concept in service.generate_concepts_stream(
            resolution=request.resolution,
            max_clusters=request.max_clusters,
            min_cluster_size=request.min_cluster_size
        ):
            yield json.dumps(concept) + "\n"

    return StreamingResponse(generator(), media_type="application/x-ndjson")
