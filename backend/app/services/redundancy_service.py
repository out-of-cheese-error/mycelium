from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from langchain_core.messages import HumanMessage
import json
import datetime

# Global registry for cancellation flags
redundancy_jobs = {}

def stop_redundancy(job_id: str):
    if job_id in redundancy_jobs:
        redundancy_jobs[job_id]["cancelled"] = True
        return True
    return False


async def collapse_redundancy(
    workspace_id: str, 
    n: int = 20, 
    include_neighbors: bool = True, 
    preview: bool = True,
    job_id: str = None
):
    """
    Identifies semantically duplicate nodes and optionally merges them.
    
    Args:
        workspace_id: Target workspace
        n: Number of top nodes (by degree centrality) to analyze
        include_neighbors: Whether to include neighbor info in summaries
        preview: If True, only return proposed groups without modifying graph
        job_id: Optional job ID for cancellation support
    
    Returns:
        dict with status, groups, and logs
    """
    logs = []
    
    if job_id:
        redundancy_jobs[job_id] = {"cancelled": False}
    
    def log(msg, log_type="info"):
        print(f"DEBUG [Redundancy]: {msg}")
        logs.append({"type": log_type, "text": msg, "timestamp": datetime.datetime.now().isoformat()})
    
    def check_cancelled():
        if job_id and redundancy_jobs.get(job_id, {}).get("cancelled"):
            log("Collapse redundancy cancelled by user.", log_type="warning")
            return True
        return False
    
    log(f"Starting collapse redundancy. n={n}, include_neighbors={include_neighbors}, preview={preview}")
    mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    
    # 1. Get top-n nodes by degree centrality
    top_nodes = mem.get_hot_topics(limit=n)
    
    if not top_nodes:
        return {"status": "no_nodes", "message": "No nodes to analyze.", "groups": [], "logs": logs}
    
    log(f"Analyzing {len(top_nodes)} top nodes by degree centrality...")
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "groups": [], "logs": logs}
    
    # 2. Build summaries for each node
    summaries = []
    for node_info in top_nodes:
        node_id = node_info["id"]
        summary = mem.get_node_summary(node_id, include_neighbors=include_neighbors)
        summaries.append({"id": node_id, "summary": summary, "degree": node_info["degree"]})
    
    summaries_text = "\n".join([f"- {s['id']}: {s['summary']}" for s in summaries])
    log(f"Generated summaries for {len(summaries)} nodes.")
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "groups": [], "logs": logs}
    
    # 3. Ask LLM to group semantically equivalent nodes
    llm = llm_config.get_chat_llm()
    
    prompt = f"""You are analyzing a knowledge graph to find redundant/duplicate nodes that represent the same concept.

Here are summaries of the top {n} nodes by connectivity:

{summaries_text}

Identify groups of nodes that represent the SAME entity or concept (e.g., "John" and "John Smith" might be the same person, "AI" and "Artificial Intelligence" are the same concept).

Only group nodes if you are CONFIDENT they refer to the same entity. When in doubt, do NOT group them.

Return a JSON object with this structure:
{{
    "groups": [
        {{
            "nodes": ["node_id_1", "node_id_2"],
            "reason": "Brief explanation of why these are duplicates"
        }}
    ]
}}

If no duplicates are found, return: {{"groups": []}}

IMPORTANT: Only include groups with 2+ nodes. Output ONLY valid JSON.
"""
    
    try:
        log("Querying LLM to identify duplicate groups...")
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        from app.utils.thinking import strip_thinking
        content = strip_thinking(response.content)

        # Extract JSON from response
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            log("LLM did not return valid JSON.", log_type="error")
            return {"status": "error", "message": "Failed to parse LLM response.", "groups": [], "logs": logs}
        
        data = json.loads(match.group(0))
        groups = data.get("groups", [])
        
        log(f"LLM identified {len(groups)} potential duplicate group(s).", log_type="success")
        
    except Exception as e:
        log(f"LLM error: {e}", log_type="error")
        return {"status": "error", "message": f"LLM error: {str(e)}", "groups": [], "logs": logs}
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "groups": [], "logs": logs}
    
    # 4. Enrich groups with degree info and determine canonical node
    enriched_groups = []
    for group in groups:
        node_ids = group.get("nodes", [])
        reason = group.get("reason", "")
        
        # Validate nodes exist
        valid_nodes = [nid for nid in node_ids if mem.graph.has_node(nid)]
        if len(valid_nodes) < 2:
            continue
        
        # Find node with highest degree as canonical
        node_degrees = [(nid, mem.graph.degree[nid]) for nid in valid_nodes]
        node_degrees.sort(key=lambda x: x[1], reverse=True)
        
        canonical = node_degrees[0][0]
        duplicates = [nid for nid, _ in node_degrees[1:]]
        
        enriched_groups.append({
            "canonical": canonical,
            "canonical_degree": node_degrees[0][1],
            "duplicates": duplicates,
            "reason": reason
        })
    
    if not enriched_groups:
        log("No valid duplicate groups found after validation.")
        return {"status": "success", "message": "No duplicates found.", "groups": [], "logs": logs}
    
    # 5. If preview mode, just return the groups
    if preview:
        log(f"Preview mode: {len(enriched_groups)} group(s) would be merged.")
        _cleanup_job(job_id)
        return {
            "status": "preview",
            "message": f"Found {len(enriched_groups)} duplicate group(s). Review and execute to merge.",
            "groups": enriched_groups,
            "logs": logs
        }
    
    # 6. Execute merge
    log("Executing merge...")
    total_edges = 0
    total_nodes = 0
    
    for group in enriched_groups:
        canonical = group["canonical"]
        duplicates = group["duplicates"]
        
        log(f"Merging {duplicates} into '{canonical}'...")
        result = mem.merge_nodes(canonical, duplicates, merge_descriptions=True)
        
        total_edges += result.get("edges_transferred", 0)
        total_nodes += result.get("nodes_removed", 0)
    
    log(f"Merge complete. Removed {total_nodes} nodes, transferred {total_edges} edges.", log_type="success")
    
    _cleanup_job(job_id)
    return {
        "status": "success",
        "message": f"Merged {total_nodes} duplicate nodes into {len(enriched_groups)} canonical nodes.",
        "groups": enriched_groups,
        "nodes_removed": total_nodes,
        "edges_transferred": total_edges,
        "logs": logs
    }


def _cleanup_job(job_id):
    if job_id and job_id in redundancy_jobs:
        del redundancy_jobs[job_id]
