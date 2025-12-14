import json
import os
from app.memory_store import GraphMemory
from app.llm_config import llm_config
from langchain_core.messages import SystemMessage, HumanMessage

class ConceptService:
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.memory = GraphMemory(workspace_id=workspace_id)
        self.concepts_path = os.path.join(self.memory.workspace_dir, "concepts.json")

    def get_concepts(self):
        """Returns cached concepts."""
        if os.path.exists(self.concepts_path):
            with open(self.concepts_path, 'r') as f:
                return json.load(f)
        return []

    async def generate_concepts_stream(
        self, 
        resolution: float = 1.0,
        max_clusters: int = 5,
        min_cluster_size: int = 5
    ):
        """
        Generator that yields concepts one by one as they are created.
        """
        # 1. Cluster the graph
        print(f"DEBUG: Starting clustering for workspace {self.workspace_id} with resolution={resolution}...")
        clusters = self.memory.get_clusters(resolution=resolution)
        print(f"DEBUG: Found {len(clusters)} clusters.")
        
        # 2. Setup LLM
        llm = llm_config.get_chat_llm()
        
        concepts = [] # To accumulate all concepts for final save/index
        
        # 3. Process clusters
        # Filter small clusters first
        valid_clusters = [c for c in clusters if len(c) >= min_cluster_size]
        print(f"DEBUG: {len(valid_clusters)} clusters >= size {min_cluster_size}.")

        # Sort by size (largest first)
        valid_clusters.sort(key=len, reverse=True)
        
        # Take top N
        top_clusters = valid_clusters[:max_clusters]
        print(f"DEBUG: Processing top {len(top_clusters)} clusters.")

        import asyncio
        import re

        for i, cluster in enumerate(top_clusters):
            node_ids = list(cluster)
            # Limit context size: take first 50 nodes
            context_nodes = node_ids[:50]
            context = self.memory.get_subgraph_context(context_nodes)
            
            if len(node_ids) > 50:
                context += f"\n... (+{len(node_ids)-50} more entities)"
            
            prompt = f"""Analyze the following subgraph data and synthesize it into a single "Concept".
            
            Subgraph Data:
            {context}
            
            Task:
            1. Provide a short, catchy 'Title' (max 5 words) that represents this group of entities.
            2. Provide a 'Summary' (2-3 sentences) explaining how these entities are related and what this concept represents.
            
            Output strictly as JSON:
            {{
                "title": "...",
                "summary": "..."
            }}
            """
            
            try:
                # Add 30s timeout per concept
                print(f"DEBUG: Invoking LLM for cluster {i}...")
                response = await asyncio.wait_for(
                    llm.ainvoke([HumanMessage(content=prompt)]),
                    timeout=30.0
                )
                print(f"DEBUG: LLM response received for cluster {i}.")
                content = response.content
                
                # Basic JSON parsing
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    concept = {
                        "id": f"c_{i}_{os.urandom(4).hex()}", # Unique ID
                        "title": data.get("title", "Untitled Concept"),
                        "summary": data.get("summary", "No summary generated."),
                        "nodes": node_ids
                    }
                    concepts.append(concept)
                    print(f"DEBUG: Successfully parsed concept for cluster {i}.")
                    yield concept
                else:
                    print(f"DEBUG: Failed to parse JSON from LLM response for cluster {i}. Content: {content[:100]}...")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error generating concept for cluster {i}: {e}")
                
        # 4. Save and Index (Final Step)
        if concepts:
            # Save to disk
            with open(self.concepts_path, 'w') as f:
                json.dump(concepts, f)

            # Index
            print(f"DEBUG: Indexing {len(concepts)} concepts in vector store...")
            try:
                self.memory.upsert_concepts(concepts)
            except Exception as e:
                print(f"Error indexing concepts: {e}")
    
    # Legacy wrapper if needed, but router will use stream
    async def generate_concepts(self, **kwargs):
        concepts = []
        async for concept in self.generate_concepts_stream(**kwargs):
            concepts.append(concept)
        return concepts
