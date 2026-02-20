from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from langchain_core.messages import HumanMessage
import json
import datetime
import uuid

# Global registry for cancellation flags
singleton_jobs = {}

def stop_singleton_assignment(job_id: str):
    if job_id in singleton_jobs:
        singleton_jobs[job_id]["cancelled"] = True
        return True
    return False


async def assign_singletons(
    workspace_id: str, 
    n: int = 10, 
    preview: bool = True,
    job_id: str = None
):
    """
    Analyzes singleton nodes and proposes relationships or merges with established nodes.
    
    Args:
        workspace_id: Target workspace
        n: Number of singletons to analyze
        preview: If True, only return proposals without modifying graph
        job_id: Optional job ID for cancellation support
    
    Returns:
        dict with status, proposals, and logs
    """
    logs = []
    
    if job_id:
        singleton_jobs[job_id] = {"cancelled": False}
    
    def log(msg, log_type="info"):
        print(f"DEBUG [Singletons]: {msg}")
        logs.append({"type": log_type, "text": msg, "timestamp": datetime.datetime.now().isoformat()})
    
    def check_cancelled():
        if job_id and singleton_jobs.get(job_id, {}).get("cancelled"):
            log("Singleton assignment cancelled by user.", log_type="warning")
            return True
        return False
    
    log(f"Starting singleton assignment. n={n}, preview={preview}")
    mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    
    # 1. Get singleton nodes
    singletons = mem.get_singletons(n=n, max_degree=1)
    
    if not singletons:
        return {"status": "no_singletons", "message": "No singleton nodes found.", "proposals": [], "logs": logs}
    
    log(f"Found {len(singletons)} singleton nodes to analyze...")
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "proposals": [], "logs": logs}
    
    # 2. Get established nodes as potential targets
    established = mem.get_established_nodes(n=15, min_degree=3)
    
    if not established:
        # Fallback: use top nodes by degree if no "established" nodes exist
        established = mem.get_hot_topics(limit=15)
    
    if not established:
        return {"status": "no_targets", "message": "No established nodes to connect to.", "proposals": [], "logs": logs}
    
    log(f"Using {len(established)} established nodes as potential targets.")
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "proposals": [], "logs": logs}
    
    # 3. Build context for LLM
    singleton_summaries = []
    for s in singletons:
        summary = mem.get_node_summary(s["id"], include_neighbors=True)
        singleton_summaries.append({"id": s["id"], "summary": summary})
    
    established_summaries = []
    for e in established:
        node_id = e.get("id") or e  # Handle both dict and string formats
        summary = mem.get_node_summary(node_id, include_neighbors=False)
        established_summaries.append({"id": node_id, "summary": summary})
    
    singletons_text = "\n".join([f"- {s['id']}: {s['summary']}" for s in singleton_summaries])
    established_text = "\n".join([f"- {e['id']}: {e['summary']}" for e in established_summaries])
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "proposals": [], "logs": logs}
    
    # 4. Query LLM for proposals
    llm = llm_config.get_chat_llm()
    
    prompt = f"""You are analyzing a knowledge graph to help integrate orphaned nodes (singletons with few or no connections).

Here are the SINGLETON NODES that need to be integrated:

{singletons_text}

Here are ESTABLISHED NODES (well-connected) that could be potential targets:

{established_text}

For each singleton, propose ONE of:
1. **merge**: The singleton is a duplicate/alias of an established node (e.g., "ML" duplicates "Machine Learning")
2. **relate**: The singleton should connect to an established node via a specific relationship
3. **skip**: No clear connection exists - leave as-is

Return a JSON object with this structure:
{{
    "proposals": [
        {{
            "singleton_id": "orphan_node_name",
            "action": "merge" | "relate" | "skip",
            "target_id": "established_node_name",  // Required for merge/relate, null for skip
            "relation": "relationship_name",  // Required for relate, null for others
            "reason": "Brief explanation",
            "confidence": "high" | "medium" | "low"
        }}
    ]
}}

GUIDELINES:
- Only propose merge if you are CONFIDENT they represent the same concept
- For relate, choose the most meaningful relationship
- It's okay to skip if no good connection exists
- Output ONLY valid JSON
"""
    
    try:
        log("Querying LLM to generate proposals...")
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        from app.utils.thinking import strip_thinking
        content = strip_thinking(response.content)

        # Extract JSON from response
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            log("LLM did not return valid JSON.", log_type="error")
            return {"status": "error", "message": "Failed to parse LLM response.", "proposals": [], "logs": logs}
        
        data = json.loads(match.group(0))
        proposals = data.get("proposals", [])
        
        # Assign unique IDs to each proposal
        for p in proposals:
            p["id"] = str(uuid.uuid4())[:8]
        
        log(f"LLM generated {len(proposals)} proposal(s).", log_type="success")
        
    except Exception as e:
        log(f"LLM error: {e}", log_type="error")
        return {"status": "error", "message": f"LLM error: {str(e)}", "proposals": [], "logs": logs}
    
    if check_cancelled():
        _cleanup_job(job_id)
        return {"status": "cancelled", "message": "Cancelled.", "proposals": [], "logs": logs}
    
    # 5. Preview mode - just return proposals
    if preview:
        log(f"Preview mode: {len(proposals)} proposal(s) generated.")
        _cleanup_job(job_id)
        return {
            "status": "preview",
            "message": f"Generated {len(proposals)} proposal(s). Review and select to execute.",
            "proposals": proposals,
            "logs": logs
        }
    
    # 6. Execute all proposals (non-preview mode)
    log("Executing all proposals...")
    results = await _execute_proposals(mem, proposals, log)
    
    _cleanup_job(job_id)
    return {
        "status": "success",
        "message": f"Executed {results['executed']} proposal(s). Merged: {results['merged']}, Related: {results['related']}, Skipped: {results['skipped']}",
        "proposals": proposals,
        "results": results,
        "logs": logs
    }


async def execute_selected_proposals(
    workspace_id: str,
    proposal_ids: list,
    proposals: list
):
    """
    Execute only the selected proposals by ID.
    
    Args:
        workspace_id: Target workspace
        proposal_ids: List of proposal IDs to execute
        proposals: Full list of proposals (to look up details)
    
    Returns:
        dict with status and results
    """
    logs = []
    
    def log(msg, log_type="info"):
        print(f"DEBUG [Singletons]: {msg}")
        logs.append({"type": log_type, "text": msg, "timestamp": datetime.datetime.now().isoformat()})
    
    mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    
    # Filter to only selected proposals
    selected = [p for p in proposals if p.get("id") in proposal_ids]
    
    if not selected:
        return {"status": "error", "message": "No valid proposals selected.", "logs": logs}
    
    log(f"Executing {len(selected)} selected proposal(s)...")
    results = await _execute_proposals(mem, selected, log)
    
    return {
        "status": "success",
        "message": f"Executed {results['executed']} proposal(s). Merged: {results['merged']}, Related: {results['related']}, Skipped: {results['skipped']}",
        "results": results,
        "logs": logs
    }


async def _execute_proposals(mem: GraphMemory, proposals: list, log) -> dict:
    """
    Execute a list of proposals against the graph.
    Uses graph lock for thread safety.
    """
    merged = 0
    related = 0
    skipped = 0
    executed = 0
    
    for p in proposals:
        action = p.get("action", "skip")
        singleton_id = p.get("singleton_id")
        target_id = p.get("target_id")
        relation = p.get("relation", "related_to")
        
        if action == "skip" or not singleton_id:
            skipped += 1
            continue
        
        if action == "merge" and target_id:
            # Merge singleton into target
            if mem.graph.has_node(singleton_id) and mem.graph.has_node(target_id):
                result = mem.merge_nodes(target_id, [singleton_id], merge_descriptions=True)
                log(f"Merged '{singleton_id}' into '{target_id}'")
                merged += 1
                executed += 1
            else:
                log(f"Skipped merge: node not found", log_type="warning")
                skipped += 1
                
        elif action == "relate" and target_id:
            # Add relation from singleton to target
            if mem.graph.has_node(singleton_id):
                mem.add_relation(singleton_id, target_id, relation)
                log(f"Related '{singleton_id}' -> '{target_id}' ({relation})")
                related += 1
                executed += 1
            else:
                log(f"Skipped relate: singleton not found", log_type="warning")
                skipped += 1
        else:
            skipped += 1
    
    return {
        "executed": executed,
        "merged": merged,
        "related": related,
        "skipped": skipped
    }


def _cleanup_job(job_id):
    if job_id and job_id in singleton_jobs:
        del singleton_jobs[job_id]
