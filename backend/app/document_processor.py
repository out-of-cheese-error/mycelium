import os
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage
from app.memory_store import GraphMemory
from app.agent import get_llm
import re
import json

# In-memory status store: { workspace_id: { job_id: { "status": "processing"|"idle", "current": 0, "total": 0, "filename": "", "updated_at": timestamp } } }
ingest_status = {}
# In-memory control flags: { workspace_id: { job_id: "stop" } }
ingest_control = {}

import time
import uuid
import asyncio

def get_status(workspace_id: str):
    """Returns all jobs for a workspace, cleaning up old ones."""
    if workspace_id not in ingest_status:
        return {"jobs": []}
    
    workspace_jobs = ingest_status[workspace_id]
    now = time.time()
    active_jobs = []
    keys_to_remove = []
    
    for job_id, job in workspace_jobs.items():
        # Check TTL (30 seconds) for terminal states
        if job["status"] in ["completed", "cancelled", "error"]:
            if now - job.get("updated_at", 0) > 30:
                keys_to_remove.append(job_id)
                continue
        
        # Add job_id to the object for frontend convenience
        job_copy = job.copy()
        job_copy["job_id"] = job_id
        active_jobs.append(job_copy)
        
    # Cleanup
    for k in keys_to_remove:
        del workspace_jobs[k]
        
    return {"jobs": active_jobs}

def stop_ingestion(workspace_id: str, job_id: str):
    """Signals a specific ingestion job to stop."""
    if workspace_id in ingest_status and job_id in ingest_status[workspace_id]:
        if ingest_status[workspace_id][job_id]["status"] == "processing":
            if workspace_id not in ingest_control:
                ingest_control[workspace_id] = {}
            ingest_control[workspace_id][job_id] = "stop"
            return True
    return False

async def process_file(file_path: str, workspace_id: str, chunk_size: int = 4800, chunk_overlap: int = 400, job_id: str = None):
    """Reads a file, extracting entities and relations into the graph."""
    
    if not job_id:
        job_id = str(uuid.uuid4())
        
    print(f"DEBUG: process_file called for workspace='{workspace_id}', job_id='{job_id}', file='{file_path}'")
        
    # Init Status
    if workspace_id not in ingest_status:
        ingest_status[workspace_id] = {}
        
    ingest_status[workspace_id][job_id] = {
        "status": "processing",
        "current": 0,
        "total": 0,
        "filename": os.path.basename(file_path),
        "updated_at": time.time()
    }
    
    # 1. Reset control flag for this job
    if workspace_id in ingest_control and job_id in ingest_control[workspace_id]:
         del ingest_control[workspace_id][job_id]

    try:
        # 1. Load File (Run in executor to avoid blocking event loop)
        import asyncio
        loop = asyncio.get_event_loop()
        
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            # Default to text
            loader = TextLoader(file_path)
        
        docs = await loop.run_in_executor(None, loader.load)
        
        # 2. Split Text
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.split_documents(docs)
        
        # Update Total
        ingest_status[workspace_id][job_id]["total"] = len(chunks)
        ingest_status[workspace_id][job_id]["updated_at"] = time.time()
        
        memory = GraphMemory(workspace_id=workspace_id)
        
        # 3. Extract Knowledge per Chunk
        count_entities = 0
        count_relations = 0
    
        for i, chunk in enumerate(chunks):
            # Check for cancellation
            # Safe get
            stop_signal = False
            if workspace_id in ingest_control and ingest_control[workspace_id].get(job_id) == "stop":
                stop_signal = True
                
            if stop_signal:
                print(f"Ingestion stopped for {workspace_id} job {job_id}")
                ingest_status[workspace_id][job_id]["status"] = "cancelled"
                ingest_status[workspace_id][job_id]["updated_at"] = time.time()
                return {"entities_extracted": count_entities, "relations_extracted": count_relations}

            # Update Current
            ingest_status[workspace_id][job_id]["current"] = i + 1
            ingest_status[workspace_id][job_id]["updated_at"] = time.time()
            
            text = chunk.page_content
            
            extraction_prompt = f"""Analyze the following text from a document and extract meaningful entities and relationships to build a knowledge graph.
            
            Text: {text}
            
            Return the output strictly as a JSON object with two keys: "entities" and "relations".
            
            1. "entities": A list of objects {{ "name": "Exact Name", "type": "Category", "description": "Brief facts" }}
            2. "relations": A list of objects {{ "source": "Entity Name", "target": "Entity Name", "relation": "relationship label" }}
            
            JSON:
            """
            
            try:
                llm = get_llm()
                
                # Run LLM in a task so we can monitor cancellation while waiting
                llm_task = asyncio.create_task(llm.ainvoke([HumanMessage(content=extraction_prompt)]))
                
                while not llm_task.done():
                    # Check cancellation
                    if workspace_id in ingest_control and ingest_control[workspace_id].get(job_id) == "stop":
                        llm_task.cancel()
                        print(f"Ingestion stopped during LLM call for {workspace_id} job {job_id}")
                        ingest_status[workspace_id][job_id]["status"] = "cancelled"
                        ingest_status[workspace_id][job_id]["updated_at"] = time.time()
                        return {"entities_extracted": count_entities, "relations_extracted": count_relations}
                    
                    # Wait 1s then check again
                    done, pending = await asyncio.wait([llm_task], timeout=1.0)
                
                response = llm_task.result()
                content = response.content
                
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    data = json.loads(json_str)
                    
                    entities = data.get("entities", [])
                    relations = data.get("relations", [])
                    
                    for entity in entities:
                        memory.add_entity(entity["name"], entity["type"], entity["description"])
                        count_entities += 1
                    
                    for rel in relations:
                        memory.add_relation(rel["source"], rel["target"], rel["relation"])
                        count_relations += 1
                        
            except Exception as e:
                print(f"Error extracting chunk: {e}")
                
        # Final Success Status
        ingest_status[workspace_id][job_id] = {
            "status": "completed",
            "current": len(chunks),
            "total": len(chunks),
            "filename": ingest_status[workspace_id][job_id]["filename"],
            "updated_at": time.time()
        }
                
        return {"entities_extracted": count_entities, "relations_extracted": count_relations}
        
    except Exception as e:
        if workspace_id not in ingest_status: ingest_status[workspace_id] = {}
        ingest_status[workspace_id][job_id] = {
            "status": "error", 
            "error": str(e),
            "current": 0,
            "total": 0,
            "updated_at": time.time()
        }
        raise e
