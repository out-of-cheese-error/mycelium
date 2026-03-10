from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel
from typing import List, Optional
from app.services.article_service import ArticleService

router = APIRouter(prefix="/articles", tags=["articles"])


class GenerateArticleRequest(BaseModel):
    workspace_id: str
    topic: str
    mode: str = "existing"  # "existing" or "research"
    research_sources: Optional[List[str]] = None  # ["wikipedia", "arxiv", "web"]
    resolution: float = 1.0
    min_cluster_size: int = 3
    max_clusters: int = 8


@router.post("/generate")
async def generate_article(request: GenerateArticleRequest):
    """Generate a long-form article using ConvergeWriter pipeline. Streams progress as NDJSON."""
    service = ArticleService(request.workspace_id)

    async def generator():
        async for update in service.generate_article_stream(
            topic=request.topic,
            mode=request.mode,
            research_sources=request.research_sources,
            resolution=request.resolution,
            min_cluster_size=request.min_cluster_size,
            max_clusters=request.max_clusters
        ):
            yield json.dumps(update) + "\n"

    return StreamingResponse(generator(), media_type="application/x-ndjson")
