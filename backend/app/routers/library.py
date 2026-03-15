from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
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


class CrawlDiscoverRequest(BaseModel):
    seed_url: str
    topic: str
    include_web_search: bool = False
    max_depth: int = 1
    depth_min_score: float = 0.7
    max_links: int = 200


class CrawlIngestItem(BaseModel):
    url: str
    source_name: str


class CrawlIngestRequest(BaseModel):
    urls: List[CrawlIngestItem]
    chunk_size: int = 4800
    chunk_overlap: int = 400


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


def _extract_links_with_context(soup, base_url, max_links=200):
    """Extract links from parsed HTML with anchor text and surrounding context."""
    from urllib.parse import urljoin, urlparse

    seen_urls = set()
    links = []
    skip_patterns = [
        'mailto:', 'javascript:', 'tel:',
        '/login', '/signin', '/signup', '/register',
        '/privacy', '/terms', '/cookie', '/legal',
        'facebook.com/sharer', 'twitter.com/intent', 'linkedin.com/share',
        'reddit.com/submit', 'wa.me/', 't.me/share',
    ]

    base_parsed = urlparse(base_url)

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        if not href or href.startswith('#'):
            continue

        # Skip filtered patterns
        href_lower = href.lower()
        if any(pat in href_lower for pat in skip_patterns):
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Only http/https
        if parsed.scheme not in ('http', 'https'):
            continue

        # Normalize: remove fragment, trailing slash
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"

        # Skip self-links
        base_norm = f"{base_parsed.scheme}://{base_parsed.netloc}{base_parsed.path.rstrip('/')}"
        if normalized == base_norm:
            continue

        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        # Extract context
        anchor_text = a_tag.get_text(strip=True)[:200]
        parent_text = ""
        parent = a_tag.find_parent(['p', 'li', 'div', 'td', 'section', 'article'])
        if parent:
            parent_text = parent.get_text(strip=True)[:150]

        links.append({
            "url": full_url,
            "anchor_text": anchor_text,
            "context": parent_text,
        })

        if len(links) >= max_links:
            break

    return links


async def _fetch_and_parse(url):
    """Fetch a URL and return (soup, title, summary). Raises on failure."""
    import httpx
    from bs4 import BeautifulSoup

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MyCelium/1.0)"
        })
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    body_soup = BeautifulSoup(resp.text, "html.parser")
    for tag in body_soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    summary = body_soup.get_text(separator="\n", strip=True)[:2000]

    return soup, title, summary


async def _score_links(all_links, page_link_count, topic, page_title, page_summary):
    """Use LLM to score a list of links for relevance to a topic. Batches concurrently."""
    import asyncio
    import re
    import json as json_mod
    from langchain_core.messages import HumanMessage
    from app.llm_config import llm_config
    from app.utils.thinking import strip_thinking

    BATCH_SIZE = 50
    batches = []
    for batch_start in range(0, len(all_links), BATCH_SIZE):
        batches.append((batch_start, all_links[batch_start:batch_start + BATCH_SIZE]))

    print(f"[crawl] Scoring {len(all_links)} links in {len(batches)} concurrent batches of {BATCH_SIZE}")

    async def _score_batch(batch_start, batch):
        links_text = ""
        for i, link in enumerate(batch):
            links_text += f"{i+1}. URL: {link['url']}\n   Anchor: {link['anchor_text']}\n   Context: {link['context']}\n\n"

        eval_prompt = f"""You are evaluating web links for relevance to a research topic.

Topic: {topic}

Page title: {page_title}
Page summary (first 2000 chars):
{page_summary}

Here are the discovered links. For each, evaluate how relevant it is to the topic.

Links:
{links_text}

Return a JSON object with key "links" containing an array. For each link include:
- "index": the link number (1-based)
- "score": relevance score from 0.0 (irrelevant) to 1.0 (highly relevant)
- "title": a brief descriptive title for the link
- "reasoning": one sentence explaining relevance or irrelevance

Only include links with score >= 0.2. Omit clearly irrelevant links.

JSON:"""

        try:
            llm = llm_config.get_chat_llm()
            response = await asyncio.to_thread(llm.invoke, [HumanMessage(content=eval_prompt)])
            content = strip_thinking(response.content)

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json_mod.loads(match.group(0))
                scored_links = data.get("links", [])
            else:
                scored_links = [
                    {"index": i+1, "score": 0.5, "title": l["anchor_text"] or l["url"], "reasoning": "Could not evaluate"}
                    for i, l in enumerate(batch)
                ]
        except Exception as e:
            print(f"[crawl] LLM evaluation failed for batch at {batch_start}: {e}")
            scored_links = [
                {"index": i+1, "score": 0.5, "title": l["anchor_text"] or l["url"], "reasoning": "Could not evaluate"}
                for i, l in enumerate(batch)
            ]

        batch_results = []
        for scored in scored_links:
            idx = scored.get("index", 0) - 1
            if 0 <= idx < len(batch):
                global_idx = batch_start + idx
                source = "web_search" if global_idx >= page_link_count else "page"
                batch_results.append({
                    "url": batch[idx]["url"],
                    "title": scored.get("title", batch[idx]["anchor_text"]),
                    "score": scored.get("score", 0.5),
                    "reasoning": scored.get("reasoning", ""),
                    "source": source,
                })
        return batch_results

    # Run all batches concurrently
    batch_results = await asyncio.gather(*[_score_batch(bs, b) for bs, b in batches])

    all_result_links = []
    for br in batch_results:
        all_result_links.extend(br)

    return all_result_links


@router.post("/{workspace_id}/crawl-discover")
async def crawl_discover(workspace_id: str, request: CrawlDiscoverRequest):
    """Fetch a seed URL, extract links, and use LLM to score them for relevance to a topic."""
    import networkx as nx

    max_depth = max(1, min(request.max_depth, 5))

    # Build a directed graph of the crawl
    G = nx.DiGraph()

    # 1. Fetch seed page
    try:
        soup, seed_title, seed_summary = await _fetch_and_parse(request.seed_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch seed URL: {e}")

    G.add_node(request.seed_url, title=seed_title, score=1.0, type="seed")

    # 2. Extract links from seed
    max_links = max(10, min(request.max_links, 500))
    page_links = _extract_links_with_context(soup, request.seed_url, max_links=max_links)

    # 3. Optional web search
    web_search_links = []
    if request.include_web_search:
        try:
            from duckduckgo_search import DDGS
            page_urls = {l["url"] for l in page_links}
            with DDGS() as ddgs:
                search_results = list(ddgs.text(request.topic, max_results=10))
            for sr in search_results:
                url = sr.get("href", "")
                if url and url not in page_urls:
                    web_search_links.append({
                        "url": url,
                        "anchor_text": sr.get("title", ""),
                        "context": sr.get("body", ""),
                    })
        except Exception as e:
            print(f"Web search failed (non-fatal): {e}")

    all_links = page_links + web_search_links
    if not all_links:
        return {"seed_title": seed_title, "seed_summary": seed_summary[:500], "links": [], "graph": nx.node_link_data(G)}

    # 4. Score depth-1 links
    result_links = await _score_links(all_links, len(page_links), request.topic, seed_title, seed_summary)

    # Add scored links to graph
    for link in result_links:
        G.add_node(link["url"], title=link["title"], score=link["score"], type=link["source"])
        G.add_edge(request.seed_url, link["url"], relation="links_to")

    # Track all discovered URLs to avoid revisiting
    seen_urls = {request.seed_url}
    for link in result_links:
        seen_urls.add(link["url"])

    # 5. Deeper crawling (depth 2+)
    import asyncio as _asyncio

    for depth in range(2, max_depth + 1):
        # Follow high-scoring links from the previous depth
        urls_to_crawl = [
            l for l in result_links
            if l["score"] >= request.depth_min_score and l["source"] != "web_search"
        ]
        if not urls_to_crawl:
            break

        # Cap pages to crawl per depth level to keep things bounded
        urls_to_crawl = urls_to_crawl[:10]

        async def _crawl_child(parent_link, depth=depth):
            """Fetch, extract, and score links from a single child page."""
            try:
                child_soup, child_title, child_summary = await _fetch_and_parse(parent_link["url"])
                child_page_links = _extract_links_with_context(child_soup, parent_link["url"], max_links=max_links)

                # Filter out already-seen URLs
                novel_links = [l for l in child_page_links if l["url"] not in seen_urls]
                if not novel_links:
                    return []

                for l in novel_links:
                    seen_urls.add(l["url"])

                scored = await _score_links(novel_links, len(novel_links), request.topic, child_title, child_summary)
                for s in scored:
                    s["source"] = f"depth_{depth}"
                return [(parent_link["url"], s) for s in scored]
            except Exception as e:
                print(f"Depth {depth} crawl failed for {parent_link['url']}: {e}")
                return []

        # Crawl all child pages concurrently
        child_results = await _asyncio.gather(*[_crawl_child(pl) for pl in urls_to_crawl])

        new_links_this_depth = []
        for child_scored in child_results:
            for parent_url, s in child_scored:
                G.add_node(s["url"], title=s["title"], score=s["score"], type=s["source"])
                G.add_edge(parent_url, s["url"], relation="links_to")
                new_links_this_depth.append(s)

        result_links.extend(new_links_this_depth)

    # 6. Sort by score descending and return
    result_links.sort(key=lambda x: x["score"], reverse=True)

    return {
        "seed_title": seed_title,
        "seed_summary": seed_summary[:500],
        "links": result_links,
        "graph": nx.node_link_data(G),
    }


@router.post("/{workspace_id}/crawl-ingest")
async def crawl_ingest(
    workspace_id: str,
    request: CrawlIngestRequest,
    background_tasks: BackgroundTasks,
):
    """Fetch selected URLs, convert to markdown, and ingest into library."""
    import httpx
    import re as re_mod
    from bs4 import BeautifulSoup
    import markdownify
    from app.document_processor import process_file_library

    upload_dir = f"./memory_data/{workspace_id}/uploads"
    os.makedirs(upload_dir, exist_ok=True)

    jobs = []
    for item in request.urls:
        job_id = str(uuid.uuid4())
        jobs.append({"url": item.url, "job_id": job_id, "status": "started"})

        async def do_ingest(url=item.url, name=item.source_name, jid=job_id):
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; MyCelium/1.0)"
                    })
                    resp.raise_for_status()

                is_pdf = url.lower().endswith(".pdf")

                if is_pdf:
                    file_path = os.path.join(upload_dir, f"{jid}.pdf")
                    with open(file_path, "wb") as f:
                        f.write(resp.content)
                else:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style"]):
                        tag.decompose()

                    md_text = markdownify.markdownify(
                        str(soup),
                        heading_style="ATX",
                        strip=['nav', 'footer', 'header', 'aside'],
                    )
                    # Clean excessive blank lines
                    md_text = re_mod.sub(r'\n{3,}', '\n\n', md_text)
                    md_text = f"Source URL: {url}\n\n{md_text}"

                    file_path = os.path.join(upload_dir, f"{jid}.md")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(md_text)

                chunk_size = 6000 if is_pdf else request.chunk_size
                await process_file_library(
                    file_path, workspace_id, chunk_size=chunk_size,
                    chunk_overlap=request.chunk_overlap, job_id=jid,
                    source_name=name,
                )
                os.remove(file_path)
            except Exception as e:
                print(f"Crawl ingestion error for {url}: {e}")

        background_tasks.add_task(do_ingest)

    return {"jobs": jobs}
