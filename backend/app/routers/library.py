from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os
import shutil
import uuid

from app.memory_store import GraphMemory

router = APIRouter(prefix="/library", tags=["library"])


class SearchRequest(BaseModel):
    query: str
    k: int = 10


class PromoteRequest(BaseModel):
    query: str
    k: int = 5
    min_score: float = 0.5


class IngestUrlRequest(BaseModel):
    url: str
    chunk_size: int = 4800
    chunk_overlap: int = 400
    source_name: Optional[str] = None


@router.post("/{workspace_id}/search")
async def search_library(workspace_id: str, request: SearchRequest):
    """Semantic search over library chunks."""
    memory = GraphMemory(workspace_id=workspace_id)
    results = memory.search_library(request.query, request.k)
    return {"results": results}


@router.get("/{workspace_id}/sources")
async def get_sources(workspace_id: str):
    """List all library sources with chunk counts."""
    memory = GraphMemory(workspace_id=workspace_id)
    sources = memory.get_library_sources()
    return {"sources": sources}


@router.get("/{workspace_id}/source/{source_id}/chunks")
async def get_chunks(workspace_id: str, source_id: str):
    """Get all chunks for a specific source, ordered by chunk_index."""
    memory = GraphMemory(workspace_id=workspace_id)
    chunks = memory.get_library_chunks_by_source(source_id)
    return {"chunks": chunks}


@router.delete("/{workspace_id}/source/{source_id}")
async def delete_source(workspace_id: str, source_id: str):
    """Delete a source and all its chunks."""
    memory = GraphMemory(workspace_id=workspace_id)
    memory.delete_library_source(source_id)
    return {"status": "deleted", "source_id": source_id}


@router.get("/{workspace_id}/stats")
async def get_stats(workspace_id: str):
    """Get library statistics."""
    memory = GraphMemory(workspace_id=workspace_id)
    return memory.get_library_stats()


@router.post("/{workspace_id}/upload")
async def upload_to_library(
    workspace_id: str,
    file: UploadFile = File(...),
    chunk_size: int = 4800,
    chunk_overlap: int = 400,
):
    """Upload a file and ingest into library (chunk + embed, no entity extraction)."""
    from app.document_processor import process_file_library

    upload_dir = f"./memory_data/{workspace_id}/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        job_id = str(uuid.uuid4())
        result = await process_file_library(
            file_path, workspace_id, chunk_size, chunk_overlap,
            job_id=job_id, source_name=file.filename
        )
        os.remove(file_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/ingest-url")
async def ingest_url_to_library(
    workspace_id: str,
    request: IngestUrlRequest,
    background_tasks: BackgroundTasks,
):
    """Fetch a URL and ingest its content into the library."""
    import httpx
    from bs4 import BeautifulSoup
    from app.document_processor import process_file_library

    job_id = str(uuid.uuid4())
    source_name = request.source_name or request.url

    upload_dir = f"./memory_data/{workspace_id}/uploads"
    os.makedirs(upload_dir, exist_ok=True)

    is_pdf = request.url.lower().endswith(".pdf")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(request.url)
            resp.raise_for_status()

        if is_pdf:
            file_path = os.path.join(upload_dir, f"{job_id}.pdf")
            with open(file_path, "wb") as f:
                f.write(resp.content)
        else:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            file_path = os.path.join(upload_dir, f"{job_id}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"URL: {request.url}\n\n{text}")

        chunk_size = 6000 if is_pdf else request.chunk_size

        async def do_ingest():
            try:
                await process_file_library(
                    file_path, workspace_id, chunk_size=chunk_size,
                    chunk_overlap=request.chunk_overlap, job_id=job_id,
                    source_name=source_name,
                )
                os.remove(file_path)
            except Exception as e:
                print(f"Library URL ingestion error: {e}")

        background_tasks.add_task(do_ingest)
        return {"job_id": job_id, "status": "started", "source_name": source_name}

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")


@router.post("/{workspace_id}/promote")
async def promote_to_graph(workspace_id: str, request: PromoteRequest):
    """Search library and extract entities from relevant chunks into the knowledge graph."""
    import asyncio
    import re
    import json as json_mod
    from langchain_core.messages import HumanMessage
    from app.llm_config import llm_config
    from app.utils.thinking import strip_thinking

    memory = GraphMemory(workspace_id=workspace_id)

    # Load workspace defaults
    k = request.k
    min_score = request.min_score
    try:
        config_path = f"./memory_data/{workspace_id}/config.json"
        if os.path.exists(config_path):
            import json as json_lib
            with open(config_path, 'r') as f:
                ws_config = json_lib.load(f)
                if k == 5:
                    k = ws_config.get("library_k", 5)
                if min_score == 0.5:
                    min_score = ws_config.get("library_min_score", 0.5)
    except Exception:
        pass

    # 1. Search
    results = memory.search_library(request.query, k)
    if not results:
        return {"entities": 0, "relations": 0, "chunks_used": 0, "filtered": 0, "message": "No results found."}

    # 2. Filter
    relevant = [r for r in results if r["score"] >= min_score]
    filtered_count = len(results) - len(relevant)

    if not relevant:
        scores = [r["score"] for r in results]
        return {
            "entities": 0, "relations": 0, "chunks_used": 0,
            "filtered": filtered_count,
            "message": f"All {len(results)} chunks scored below threshold ({min_score}). Top score: {max(scores):.2f}",
        }

    # 3. Extract entities
    combined_text = "\n\n---\n\n".join(
        f"[Source: {r['source_name']}]\n{r['text']}" for r in relevant
    )

    extraction_prompt = f"""Analyze the following text passages and extract meaningful entities and relationships to build a knowledge graph.

Text passages:
{combined_text}

Return the output strictly as a JSON object with two keys: "entities" and "relations".

1. "entities": A list of objects {{ "name": "Exact Name", "type": "Category", "description": "Brief facts" }}
2. "relations": A list of objects {{ "source": "Entity Name", "target": "Entity Name", "relation": "relationship label" }}

JSON:
"""

    try:
        llm = llm_config.get_ingestion_llm()
        response = await asyncio.to_thread(llm.invoke, [HumanMessage(content=extraction_prompt)])
        content = strip_thinking(response.content)

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {
                "entities": 0, "relations": 0, "chunks_used": len(relevant),
                "filtered": filtered_count, "message": "LLM could not extract entities.",
            }

        data = json_mod.loads(match.group(0))
        entities = data.get("entities", [])
        relations = data.get("relations", [])

        for entity in entities:
            await asyncio.to_thread(
                memory.add_entity, entity["name"], entity["type"], entity["description"]
            )
        for rel in relations:
            await asyncio.to_thread(
                memory.add_relation, rel["source"], rel["target"], rel["relation"]
            )

        source_names = list(set(r["source_name"] for r in relevant))
        return {
            "entities": len(entities),
            "relations": len(relations),
            "chunks_used": len(relevant),
            "filtered": filtered_count,
            "sources": source_names,
            "message": f"Extracted {len(entities)} entities, {len(relations)} relations from {len(relevant)} chunks.",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Promotion failed: {e}")
