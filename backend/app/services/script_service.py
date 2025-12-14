import os
import json
import uuid
import re
from datetime import datetime
from langchain_core.messages import HumanMessage
from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from app.routers.workspaces import get_llm_helper

def get_scripts_dir(workspace_id: str):
    path = os.path.join(MEMORY_BASE_DIR, workspace_id, "scripts")
    os.makedirs(path, exist_ok=True)
    return path

async def generate_script_logic(workspace_id: str, topic: str):
    try:
        # 1. Retrieve Context
        mem = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
        context = mem.retrieve_context(topic, k=5)
        
        # 2. LLM Generation
        # We need the LLM helper. Since it's in workspaces.py (which is a router), 
        # it might be better to duplicate the simple helper or refactor get_llm_helper 
        # to a shared location. 
        # For now, let's just re-implement the simple LLM fetching here to avoid circular imports 
        # if workspaces imports this service.
        
        llm = llm_config.get_chat_llm()
        
        prompt = f"""You are an educational scriptwriter.
        Create a raw text script about "{topic}" that is optimized for Text-to-Speech (TTS).
        
        CONTEXT FROM MEMORY:
        {context}
        
        INSTRUCTIONS:
        - The outputs must be strictly raw text. NO markdown, NO bullet points, NO special formatting.
        - Break the script into logical "parts" (e.g., Introduction, Deep Dive, Conclusion).
        - Each part should be 2-3 sentences long.
        - Tone: Engaging, informative, and clear.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "title": "Title of the Lesson",
            "parts": [
                {{ "title": "Part 1 Title", "text": "Raw text content for part 1." }},
                {{ "title": "Part 2 Title", "text": "Raw text content for part 2." }}
            ]
        }}
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Clean markdown if present
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            
            # Save to disk
            script_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().isoformat()
            
            script_data = {
                "id": script_id,
                "created_at": timestamp,
                "topic": topic,
                "title": data.get("title", topic),
                "parts": data.get("parts", [])
            }
            
            scripts_dir = get_scripts_dir(workspace_id)
            path = os.path.join(scripts_dir, f"{script_id}.json")
            with open(path, 'w') as f:
                json.dump(script_data, f, indent=2)
                
            return script_data
        else:
             raise ValueError("LLM returned invalid JSON.")
             
    except Exception as e:
        print(f"Script Generation Logic Error: {e}")
        raise e
