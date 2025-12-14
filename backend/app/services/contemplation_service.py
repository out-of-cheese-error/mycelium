from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from langchain_core.messages import HumanMessage
from langchain_community.tools import DuckDuckGoSearchRun
import json
import asyncio
import os
import uuid
from app.services.wikipedia_service import wikipedia_service
from app.services.gutendex_service import gutendex_service

import datetime

# Global registry for cancellation flags
contemplation_jobs = {}

def stop_contemplation(job_id: str):
    if job_id in contemplation_jobs:
        contemplation_jobs[job_id]["cancelled"] = True
        return True
    return False

async def contemplate_logic(workspace_id: str, n: int = 3, topic: str = None, save_to_notes: bool = False, depth: int = 1, job_id: str = None):
    logs = []
    
    # Register job
    if job_id:
        contemplation_jobs[job_id] = {"cancelled": False}

    def log(msg, type="info"):
        print(f"DEBUG: {msg}")
        logs.append({"type": type, "text": msg, "timestamp": datetime.datetime.now().isoformat()})

    def check_cancelled():
        if job_id and contemplation_jobs.get(job_id, {}).get("cancelled"):
            log("Contemplation cancelled by user.", type="warning")
            return True
        return False

    log(f"Starting contemplation. n={n}, topic={topic}, save_to_notes={save_to_notes}, depth={depth}")
    mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    
    # 1. Pick nodes (Random or Related)
    if topic:
        nodes = mem.get_related_nodes(topic, n)
        mode_desc = f"focused on '{topic}'"
    else:
        nodes = mem.get_random_nodes(n)
        mode_desc = "random selection"
        
    if not nodes:
        return {"status": "no_nodes", "message": "Not enough memories to contemplate.", "logs": logs}
    
    # Collect Subgraph via BFS
    subgraph_nodes = set(nodes)
    subgraph_edges = []
    
    # Queue for BFS: (node_id, current_depth)
    queue = [(node, 0) for node in nodes]
    visited = set(nodes)
    
    max_nodes_limit = 100
    
    while queue:
        if check_cancelled(): break
        current_node, current_depth = queue.pop(0)
        
        # If we reached max depth, don't expand further, but we still process the node itself
        if current_depth >= depth:
            # print(f"DEBUG: Node {current_node} at depth {current_depth} reached max depth {depth}. Not expanding.")
            continue
            
        try:
            neighbors = list(mem.graph.neighbors(current_node))
            print(f"DEBUG: Expanding {current_node} (Depth {current_depth}/{depth}). Neighbors: {len(neighbors)}")
            
            for nb in neighbors:
                # Add Edge
                edge_data = mem.graph.get_edge_data(current_node, nb)
                relation = edge_data.get('relation', 'related')
                subgraph_edges.append((current_node, nb, relation))
                
                # Expand Node
                if nb not in visited:
                    if len(visited) >= max_nodes_limit:
                        print("DEBUG: BFS hit max nodes limit")
                        continue # Hit safety limit
                    visited.add(nb)
                    subgraph_nodes.add(nb)
                    queue.append((nb, current_depth + 1))
        except Exception as e:
            print(f"DEBUG: Error traversing {current_node}: {e}")
            
    print(f"DEBUG: BFS Complete. Subgraph has {len(subgraph_nodes)} nodes and {len(subgraph_edges)} edges.")

    # Format Output
    context_lines = ["--- Knowledge Graph Context ---", "Entities:"]
    for n_id in subgraph_nodes:
        data = mem.graph.nodes[n_id]
        desc = data.get('description', 'No description')
        context_lines.append(f"  - {n_id} ({data.get('type')}): {desc}")
        
    context_lines.append("Relationships:")
    # Deduplicate edges (A-B and B-A might appear depending on traversal, though strictly BFS visits edge once per direction usually? 
    # Actually iterate edges in subgraph_edges. undirected graph edge data is same.)
    # We'll just setify them by sorting nodes to ensure uniqueness of textual representation
    seen_edges = set()
    for u, v, rel in subgraph_edges:
        key = tuple(sorted((u, v)))
        if key not in seen_edges:
            seen_edges.add(key)
            context_lines.append(f"  - {u} --[{rel}]--> {v}")

    joined_nodes = "\n".join(context_lines)
    joined_nodes = "\n".join(context_lines)
    log(f"Context gathered ({len(subgraph_nodes)} nodes). Formulating execution plan with LLM...")
    
    if check_cancelled():
        if job_id: del contemplation_jobs[job_id] 
        return {"status": "cancelled", "message": "Contemplation cancelled.", "logs": logs}
    
    # 2. Formulate Search Queries with LLM
    llm = llm_config.get_chat_llm()
    
    # Load System Prompt / Persona
    system_prompt = "You are a helpful assistant with a long-term memory."
    config_path = os.path.join(mem.workspace_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                system_prompt = data.get("system_prompt", system_prompt)
        except:
            pass

    prompt = f"""System Persona: {system_prompt}
    
    You are iterating on your internal knowledge graph to grow your understanding.
    
    ### WHAT YOU CURRENTLY KNOW (Memory Context):
    The following is a retrieval from your long-term memory (Knowledge Graph) regarding {mode_desc}. 
    This is your *established knowledge*:
    {joined_nodes}
    
    ### WHAT YOU WANT TO KNOW (Curiosity):
    Based on your persona and what you already know, identify gaps in your knowledge or interesting connections you want to explore.
    What are you curious about regarding these topics?
    
    You have access to 3 research tools:
    1. "web": General search (DuckDuckGo).
    2. "wikipedia": Search for encyclopedia articles.
    3. "gutenberg": Search for free public domain books (titles, authors).
    
    Generate {n} diverse search ACTIONS to find NEW, interesting relationships or updated information.
    Return JSON list of objects: [ {{"tool": "web|wikipedia|gutenberg", "query": "..."}} ]
    """
    
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        log(f"Phase 1 - Curiosity (LLM Thought):\n{resp.content}", type="thought")
        
        # Robust JSON extraction
        import re
        content = resp.content.strip()
        # Try to find JSON list or object
        match = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
        if match:
             content = match.group(0)
             
        parsed = json.loads(content)
        # Normalize to list of objects
        queries = []
        if isinstance(parsed, dict): 
            # If it wrapped in "queries": [...]
            if "queries" in parsed: 
                queries = parsed["queries"]
            else:
                # heuristic fallback if flat dict? unlikely based on prompt
                pass
        elif isinstance(parsed, list):
            queries = parsed
            
        # Migrate old format ["q1", "q2"] to [{"tool": "web", "query": "q1"}] just in case
        normalized_queries = []
        for q in queries:
            if isinstance(q, str):
                normalized_queries.append({"tool": "web", "query": q})
            elif isinstance(q, dict) and "tool" in q and "query" in q:
                normalized_queries.append(q)
        queries = normalized_queries

    except Exception as e:
        log(f"Query Generation Error: {e}", type="error")
        queries = [{"tool": "web", "query": f"recent developments {node}"} for node in nodes]
        
    # 3. Search Loop
    search = DuckDuckGoSearchRun()
    findings = []
    
    for item in queries:
        if check_cancelled(): break
        tool = item.get("tool", "web")
        q = item.get("query", "")
        
        # Internal check (Skip for now to keep logic simple for new tools, 
        # or apply only for "web" / general queries. Wikipedia search is specific.)
        # Let's keep the internal memory retrieval because it's good context regardless.
        
        found_internally = False
        internal_context = ""
        
        try:
            # print(f"DEBUG: Checking internal memory for: '{q}'")
            internal_nodes = mem.get_related_nodes(q, n=3)
            if internal_nodes:
                details = []
                for node in internal_nodes:
                    # Retrieve node data safely
                    if node in mem.graph.nodes:
                        d = mem.graph.nodes[node]
                        details.append(f"- {node} ({d.get('type')}): {d.get('description', '')}")
                internal_context = "\n".join(details)
                
                # We won't skip external search entirely for wikipedia/gutenberg requests 
                # because user specifically asked for those sources usually.
                # But for 'web', we might validity check.
                if tool == "web":
                     # Ask LLM if this is sufficient
                    check_prompt = f"""Query: {q}
                    
                    My Status: I am checking my internal memory before searching the web.
                    Found Internal Records:
                    {internal_context}
                    
                    Does this internal information ALREADY adequately answer the query?
                    Reply ONLY with "YES" or "NO".
                    """
                    check_resp = await llm.ainvoke([HumanMessage(content=check_prompt)])
                    answer = check_resp.content.strip().upper()
                    # print(f"DEBUG: Internal check for '{q}': {answer}")
                    
                    if "YES" in answer:
                        findings.append(f"Query: {q}\nSource: Internal Memory\nResult: {internal_context}")
                        found_internally = True
                        print(f"DEBUG: Skipping web search for '{q}' (found in memory).")

        except Exception as e:
            print(f"DEBUG: Internal memory check failed: {e}")

        # If not found internally (or if we force tool use), execute tool
        if not found_internally:
            try:
                print(f"DEBUG: Executing '{tool}' search for: '{q}'")
                result_text = ""
                
                if tool == "wikipedia":
                    # Search pages first
                    pages_list = wikipedia_service.search_pages(q, limit=3)
                    # Use the first result to get a summary? Or just present the list?
                    # Presenting the list is safer. But Agent might want content.
                    # Let's try to get content of first result if it looks unique?
                    # For now, just return the list so the synthesis step sees titles.
                    result_text = f"Wikipedia Search Results:\n{pages_list}"
                    
                elif tool == "gutenberg":
                    # Search books
                    books_list = gutendex_service.search_books(q) # returns formatted string or list
                    # It returns a string in agent logic. Let's verify service returns string? 
                    # Yes, gutendex_service.search_books usually returns formatted string based on my memory of agent.py
                    # Wait, agent.py calls `gutendex_service.search_books`.
                    result_text = f"Gutenberg Search Results:\n{books_list}"
                    
                else: # web
                    # Synchronous search in async loop -> using asyncio.to_thread
                    result_text = await asyncio.to_thread(search.invoke, q)
                
                log(f"Tool '{tool}' executed for '{q}'", type="tool")
                log(f"Results: {str(result_text)[:200]}...", type="debug")
                findings.append(f"Query: {q}\nSource: {tool}\nResult: {str(result_text)[:2000]}") # Increased limit
                
            except Exception as e:
                findings.append(f"Query: {q}\nSource: {tool}\nError: {e}")
            
    joined_findings = "\n\n".join(findings)
    
    # 4. Synthesize & Update Memory
    synthesis_prompt = f"""System Persona: {system_prompt}

    We are contemplating these topics:
    {joined_nodes}
    
    We found this new information:
    {joined_findings}
    
    Analyze the new information and:
    1. Extract meaningful entities and relationships for the knowledge graph.
    2. Suggest INGESTION commands if you found specific Wikipedia pages or Gutenberg books that seem highly relevant and should be read in full.
    
    Output A SINGLE JSON object with keys: "entities", "relations", "ingest_commands" (optional), and "summary" (optional).
    
    Format:
    {{
        "entities": [
            {{"name": "EntityName", "type": "EntityType", "description": "Entity Description"}}
        ],
        "relations": [
            {{"source": "EntityName", "target": "OtherEntityName", "relation": "relationship_type"}}
        ],
        "ingest_commands": [
             {{"type": "wikipedia", "title": "Exact Page Title"}},
             {{"type": "gutenberg", "book_id": 12345}}
        ],
        "summary": "First person inner dialogue summary..."
    }}
    
    IMPORTANT: The "name" field is REQUIRED for every entity.
    """
    
    if check_cancelled():
        if job_id: del contemplation_jobs[job_id] 
        return {"status": "cancelled", "message": "Contemplation cancelled.", "logs": logs}

    try:
        log("Phase 2 - Synthesis: Analyzing new information...")
        synthesis_resp = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
        log(f"Synthesis (LLM Analysis):\n{synthesis_resp.content}", type="thought")
        import re
        match = re.search(r"\{.*\}", synthesis_resp.content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                print("DEBUG: Failed to parse JSON from synthesis response")
                return {"status": "error", "message": "Failed to parse AI response."}

            entities = data.get("entities", [])
            relations = data.get("relations", [])
            ingest_commands = data.get("ingest_commands", [])
            summary = data.get("summary", "")
            
            # Fallback for summary
            if save_to_notes and not summary:
                summary = f"Contemplation on {topic if topic else 'random topics'}. No specific summary provided by AI."

            new_entity_count = 0
            for e in entities:
                if "name" not in e:
                    continue
                mem.add_entity(e["name"], e.get("type", "Unknown"), e.get("description", ""))
                new_entity_count += 1
            
            new_relation_count = 0
            for r in relations:
                if "source" in r and "target" in r and "relation" in r:
                    mem.add_relation(r["source"], r["target"], r["relation"])
                    new_relation_count += 1
                    
            # Handle Ingestion Commands
            ingest_msg = ""
            if ingest_commands:
                triggered_count = 0
                from app.document_processor import process_file
                # We need to use the agent tool logic to fetch/save then process.
                # Re-using logic from agent.py is hard without circular deps or duplicating.
                # Let's duplicate the fetch-and-trigger logic cleanly here or import the specific helper.
                # Actually, simply calling the services + process_file is best.
                
                for cmd in ingest_commands:
                    try:
                        cmd_type = cmd.get("type")
                        if cmd_type == "wikipedia" and "title" in cmd:
                            title = cmd["title"]
                            content = wikipedia_service.get_page_content(title)
                            if not content.startswith("Error"):
                                # Save temp
                                temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
                                os.makedirs(temp_dir, exist_ok=True)
                                safe_title = "".join(x for x in title if x.isalnum() or x in " -_").strip()
                                fpath = os.path.join(temp_dir, f"wiki_{safe_title}.txt")
                                with open(fpath, "w", encoding="utf-8") as f: f.write(content)
                                # Ingest
                                jid = str(uuid.uuid4())
                                asyncio.create_task(process_file(fpath, workspace_id, chunk_size=4000, job_id=jid))
                                triggered_count += 1
                                print(f"DEBUG: Auto-ingesting Wiki: {title}")

                        elif cmd_type == "gutenberg" and "book_id" in cmd:
                            bid = cmd["book_id"]
                            fpath = gutendex_service.download_book(bid, workspace_id)
                            if fpath and not fpath.startswith("Error"):
                                jid = str(uuid.uuid4())
                                asyncio.create_task(process_file(fpath, workspace_id, chunk_size=8000, job_id=jid))
                                triggered_count += 1
                                print(f"DEBUG: Auto-ingesting Book: {bid}")
                                
                    except Exception as ex:
                        print(f"DEBUG: Failed auto-ingest cmd {cmd}: {ex}")
                
                if triggered_count > 0:
                    ingest_msg = f" Triggered {triggered_count} new ingestion jobs."
            
            note_msg = ""
            if save_to_notes and summary:
                # Save as a note
                note_id = str(uuid.uuid4())
                timestamp_iso = datetime.datetime.now().isoformat()
                timestamp_float = datetime.datetime.now().timestamp()
                note_title = f"Contemplation: {topic if topic else 'Random'} - {timestamp_iso[:10]}"
                
                note_data = {
                    "id": note_id,
                    "title": note_title,
                    "content": f"# Insights from Contemplation\n**Mode**: {mode_desc}\n\n## Summary\n{summary}\n\n## Findings\n{joined_findings}",
                    "tags": ["contemplation", "auto-generated"],
                    "created_at": timestamp_iso,
                    "updated_at": timestamp_float, # Must be float for Note model
                    "workspace_id": workspace_id
                }
                
                note_file = os.path.join(mem.workspace_dir, "notes", f"{note_id}.json")
                print(f"DEBUG: Saving note to {note_file}")
                
                try:
                    os.makedirs(os.path.dirname(note_file), exist_ok=True)
                    with open(note_file, 'w') as f:
                        json.dump(note_data, f)
                    
                    # Index it
                    mem.index_note(note_id, note_title, note_data["content"])
                    note_msg = "Summary saved to notes."
                    print("DEBUG: Note saved and indexed successfully.")
                except Exception as e:
                    print(f"DEBUG: Failed to save note: {e}")
                    note_msg = f"Failed to save note: {e}"

            return {
                "status": "success",
                "contemplated_nodes": nodes,
                "new_entities": new_entity_count,
                "new_relations": new_relation_count,
                "message": f"Contemplated {len(nodes)} topics ({mode_desc}). Added {new_entity_count} entities, {new_relation_count} relations. {note_msg}{ingest_msg}",
                "logs": logs
            }
            
    except Exception as e:
        log(f"Contemplation Synthesis Failed: {e}", type="error")
        return {"status": "error", "message": f"Synthesis Error: {str(e)}", "logs": logs}

    if job_id and job_id in contemplation_jobs:
        del contemplation_jobs[job_id]

    return {"status": "success", "message": "Contemplation finished but yielded no structural updates.", "logs": logs}
