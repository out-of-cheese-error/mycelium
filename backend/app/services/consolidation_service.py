"""
Sleep-time graph consolidation service.

Inspired by LightMem's offline parallel update mechanism (Light3).
More sophisticated than collapse_redundancy: uses embedding similarity
across ALL nodes (not just high-degree ones), applies time-aware filtering,
and supports merge/update/delete decisions via LLM.

Architecture mirrors redundancy_service.py (job registry, cancellation, logging).
"""

import datetime
import json
import os
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from langchain_core.messages import HumanMessage

from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config

# ---------------------------------------------------------------------------
# Job registry for cancellation + progress support
# ---------------------------------------------------------------------------
consolidation_jobs: Dict[str, dict] = {}


def _init_job(job_id: str):
    consolidation_jobs[job_id] = {
        "cancelled": False,
        "status": "running",
        "phase": "starting",
        "progress": 0,       # 0-100
        "current": 0,
        "total": 0,
        "logs": [],
        "result": None,
    }


def stop_consolidation(job_id: str) -> bool:
    if job_id in consolidation_jobs:
        consolidation_jobs[job_id]["cancelled"] = True
        return True
    return False


def get_consolidation_progress(job_id: str) -> Optional[dict]:
    job = consolidation_jobs.get(job_id)
    if not job:
        return None
    return {
        "status": job["status"],
        "phase": job["phase"],
        "progress": job["progress"],
        "current": job["current"],
        "total": job["total"],
        "logs": list(job["logs"]),
        "result": job["result"],
    }


def _cleanup_job(job_id: Optional[str]):
    """Mark job as done but keep it around so the frontend can fetch the final result."""
    pass


# ---------------------------------------------------------------------------
# Consolidation prompt
# ---------------------------------------------------------------------------
CONSOLIDATION_PROMPT = """You are a knowledge graph memory manager performing offline consolidation.

Given a TARGET node and CANDIDATE nodes that are semantically similar, decide what action to take.

Actions:
- "merge": The candidates represent the SAME entity/concept as the target. Merge them into one node. Provide the merged description.
- "update": The target and candidates are the same entity but the candidates have additional information. Update the target's description. Provide the new description.
- "delete": The target is fully redundant — a candidate already captures all its information more completely. The target should be removed.
- "ignore": The nodes are different entities that happen to be similar. Do nothing.

TARGET NODE:
{target_summary}

CANDIDATE NODES (similar, created more recently):
{candidates_summary}

Return ONLY a JSON object:
{{
    "action": "merge" | "update" | "delete" | "ignore",
    "reason": "Brief explanation",
    "new_description": "Merged/updated description (only for merge/update actions)",
    "merge_ids": ["candidate_id_1", ...] (only for merge action - which candidates to merge into target)
}}

IMPORTANT: Only choose "merge" if you are CONFIDENT the nodes refer to the same entity. When in doubt, choose "ignore".
JSON:"""


def start_consolidation_background(
    workspace_id: str,
    similarity_threshold: float = 0.85,
    max_workers: int = 4,
    job_id: str = "consolidate",
):
    """Start consolidation in a background thread. Returns immediately."""
    _init_job(job_id)
    t = threading.Thread(
        target=_run_consolidation,
        args=(workspace_id, similarity_threshold, max_workers, job_id),
        daemon=True,
    )
    t.start()


def _run_consolidation(
    workspace_id: str,
    similarity_threshold: float,
    max_workers: int,
    job_id: str,
):
    """Synchronous consolidation that updates job progress in-place."""
    job = consolidation_jobs[job_id]

    def log(msg, log_type="info"):
        print(f"DEBUG [Consolidation]: {msg}")
        job["logs"].append({
            "type": log_type,
            "text": msg,
            "timestamp": datetime.datetime.now().isoformat(),
        })

    def check_cancelled():
        if job.get("cancelled"):
            log("Consolidation cancelled by user.", log_type="warning")
            return True
        return False

    def finish(result: dict):
        job["result"] = result
        job["status"] = result.get("status", "done")
        job["progress"] = 100
        job["phase"] = "done"

    try:
        job["phase"] = "fetching"
        log(f"Starting graph consolidation for {workspace_id}. "
            f"similarity_threshold={similarity_threshold}, max_workers={max_workers}")

        mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)

        # Step 1: Get all entities and their embeddings
        try:
            all_data = mem.collection.get(
                include=["embeddings", "documents", "metadatas"]
            )
        except Exception as e:
            log(f"Failed to fetch embeddings ({e}), attempting reindex...", log_type="warning")
            try:
                mem.reindex_graph()
                all_data = mem.collection.get(
                    include=["embeddings", "documents", "metadatas"]
                )
                log("Reindex successful, continuing consolidation.")
            except Exception as e2:
                log(f"Reindex also failed: {e2}", log_type="error")
                finish({"status": "error", "message": str(e2), "logs": list(job["logs"])})
                return

        node_ids = all_data.get("ids")
        if node_ids is None:
            node_ids = []
        embeddings = all_data.get("embeddings")
        if embeddings is None:
            embeddings = []

        if len(node_ids) < 2:
            log("Too few nodes for consolidation.")
            finish({"status": "too_few_nodes", "message": "Need at least 2 nodes.", "logs": list(job["logs"])})
            return

        log(f"Found {len(node_ids)} nodes with embeddings.")

        if check_cancelled():
            finish({"status": "cancelled", "logs": list(job["logs"])})
            return

        # Step 2: Build update queues using embedding similarity
        job["phase"] = "similarity"
        job["total"] = len(node_ids)
        update_queues: Dict[str, List[dict]] = {}

        for i, node_id in enumerate(node_ids):
            job["current"] = i + 1
            job["progress"] = int((i + 1) / len(node_ids) * 40)  # 0-40% for similarity phase

            if check_cancelled():
                finish({"status": "cancelled", "logs": list(job["logs"])})
                return

            if not mem.graph.has_node(node_id):
                continue

            node_created = mem.graph.nodes[node_id].get("created_at", "")
            embedding = embeddings[i] if embeddings is not None and i < len(embeddings) else None

            if embedding is None:
                continue

            try:
                results = mem.collection.query(
                    query_embeddings=[embedding],
                    n_results=min(20, len(node_ids)),
                    include=["distances"],
                )
            except Exception:
                continue

            candidates = []
            for j, candidate_id in enumerate(results["ids"][0]):
                if candidate_id == node_id:
                    continue
                if not mem.graph.has_node(candidate_id):
                    continue

                distance = results["distances"][0][j]
                similarity = 1.0 - distance

                if similarity < similarity_threshold:
                    continue

                candidate_created = mem.graph.nodes[candidate_id].get("created_at", "")
                if candidate_created and node_created:
                    if candidate_created < node_created:
                        continue
                    # For equal timestamps, use ID as tiebreaker so exactly one direction is kept
                    if candidate_created == node_created and candidate_id <= node_id:
                        continue

                candidates.append({
                    "id": candidate_id,
                    "score": round(similarity, 4),
                })

            if candidates:
                candidates.sort(key=lambda x: x["score"], reverse=True)
                update_queues[node_id] = candidates[:10]

        log(f"Built update queues for {len(update_queues)} nodes.")

        if not update_queues:
            log("No nodes need consolidation.")
            finish({"status": "success", "message": "No consolidation needed.", "logs": list(job["logs"])})
            return

        if check_cancelled():
            finish({"status": "cancelled", "logs": list(job["logs"])})
            return

        # Step 3: LLM-driven decisions (parallel)
        job["phase"] = "llm"
        job["total"] = len(update_queues)
        job["current"] = 0
        llm = llm_config.get_ingestion_llm()
        decisions = []
        llm_done = 0

        def process_node(target_id: str, candidates: List[dict]) -> Optional[dict]:
            target_summary = mem.get_node_summary(target_id, include_neighbors=True)
            candidates_text = "\n".join([
                f"  - {c['id']} (similarity: {c['score']}): "
                f"{mem.get_node_summary(c['id'], include_neighbors=True)}"
                for c in candidates
            ])

            prompt = CONSOLIDATION_PROMPT.format(
                target_summary=target_summary,
                candidates_summary=candidates_text,
            )

            try:
                from app.utils.thinking import strip_thinking
                response = llm.invoke([HumanMessage(content=prompt)])
                content = strip_thinking(response.content)

                match = re.search(r"\{.*\}", content, re.DOTALL)
                if not match:
                    return None

                data = json.loads(match.group(0))
                action = data.get("action", "ignore")
                if action == "ignore":
                    return None

                return {
                    "target": target_id,
                    "action": action,
                    "reason": data.get("reason", ""),
                    "new_description": data.get("new_description", ""),
                    "merge_ids": data.get("merge_ids", []),
                    "candidates": candidates,
                }
            except Exception as e:
                print(f"DEBUG [Consolidation]: LLM error for {target_id}: {e}")
                return None

        log(f"Running LLM consolidation decisions for {len(update_queues)} nodes...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_node, nid, cands): nid
                for nid, cands in update_queues.items()
            }
            for future in as_completed(futures):
                if check_cancelled():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    decision = future.result()
                    if decision:
                        decisions.append(decision)
                except Exception as e:
                    log(f"Worker error: {e}", log_type="error")

                llm_done += 1
                job["current"] = llm_done
                # 40-90% for LLM phase
                job["progress"] = 40 + int(llm_done / len(update_queues) * 50)

        if check_cancelled():
            finish({"status": "cancelled", "logs": list(job["logs"])})
            return

        log(f"LLM returned {len(decisions)} actionable decision(s).")

        # Step 4: Execute decisions
        job["phase"] = "applying"
        job["progress"] = 90
        merge_count = 0
        update_count = 0
        delete_count = 0
        processed_nodes = set()

        for decision in decisions:
            target = decision["target"]

            if target in processed_nodes:
                continue
            if not mem.graph.has_node(target):
                continue

            action = decision["action"]

            if action == "merge":
                merge_ids = [
                    mid for mid in decision.get("merge_ids", [])
                    if mid not in processed_nodes and mem.graph.has_node(mid)
                ]
                if merge_ids:
                    if decision.get("new_description"):
                        mem.update_entity(target, description=decision["new_description"])
                    result = mem.merge_nodes(target, merge_ids, merge_descriptions=True)
                    merge_count += result.get("nodes_removed", 0)
                    processed_nodes.add(target)
                    processed_nodes.update(merge_ids)
                    log(f"Merged {merge_ids} into '{target}': {decision.get('reason', '')}")

            elif action == "update":
                if decision.get("new_description"):
                    mem.update_entity(target, description=decision["new_description"])
                    update_count += 1
                    processed_nodes.add(target)
                    log(f"Updated '{target}': {decision.get('reason', '')}")

            elif action == "delete":
                mem.delete_entity(target)
                delete_count += 1
                processed_nodes.add(target)
                log(f"Deleted '{target}': {decision.get('reason', '')}")

        summary = (
            f"Consolidation complete. "
            f"Analyzed: {len(update_queues)}, "
            f"Merges: {merge_count}, Updates: {update_count}, Deletes: {delete_count}"
        )
        log(summary, log_type="success")

        finish({
            "status": "success",
            "message": summary,
            "nodes_analyzed": len(update_queues),
            "merges": merge_count,
            "updates": update_count,
            "deletes": delete_count,
            "decisions": decisions,
            "logs": list(job["logs"]),
        })

    except Exception as e:
        print(f"DEBUG [Consolidation]: Unhandled error: {traceback.format_exc()}")
        job["logs"].append({"type": "error", "text": str(e), "timestamp": datetime.datetime.now().isoformat()})
        job["result"] = {"status": "error", "message": str(e), "logs": list(job["logs"])}
        job["status"] = "error"
        job["progress"] = 100
        job["phase"] = "done"
