import networkx as nx
import chromadb
from chromadb.config import Settings
from langchain_core.documents import Document
import json
import os
import uuid
from app.llm_config import llm_config

MEMORY_BASE_DIR = "./memory_data"

class GraphMemory:
    def __init__(self, workspace_id: str = "default", base_dir: str = "./memory_data"):
        self.workspace_id = workspace_id
        self.base_dir = base_dir
        self.workspace_dir = os.path.join(base_dir, workspace_id)
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # 1. Initialize Graph
        self.graph_path = os.path.join(self.workspace_dir, "graph.json")
        self.graph = nx.Graph()
        self.load_graph()
        
        # 2. Initialize Vector Store (ChromaDB)
        # ChromaDB requires a specific path. We will use a subfolder per workspace.
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.workspace_dir, "chroma"))
        
        # Use embedding model based on configured provider (OpenAI, Ollama, or LM Studio)
        self.embedding_fn = llm_config.get_embeddings()
        self.collection = self.chroma_client.get_or_create_collection(
            name="entity_embeddings",
            metadata={"hnsw:space": "cosine"}
        )
        self.note_collection = self.chroma_client.get_or_create_collection(
            name="note_embeddings",
            metadata={"hnsw:space": "cosine"}
        )
        self.concept_collection = self.chroma_client.get_or_create_collection(
            name="concept_embeddings",
            metadata={"hnsw:space": "cosine"}
        )
        self.skill_collection = self.chroma_client.get_or_create_collection(
            name="skill_embeddings",
            metadata={"hnsw:space": "cosine"}
        )

    def load_graph(self):
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, 'r') as f:
                    data = json.load(f)
                    # Normalize 'edges' vs 'links' for NetworkX compatibility
                    if 'links' not in data:
                        if 'edges' in data:
                            data['links'] = data['edges']
                        else:
                            data['links'] = []
                            
                    # Ensure 'nodes' exists
                    if 'nodes' not in data:
                        data['nodes'] = []
                        
                    self.graph = nx.node_link_graph(data)
            except json.JSONDecodeError as e:
                print(f"ERROR: Graph file {self.graph_path} is corrupted: {e}")
                print("Backing up corrupted file and starting fresh.")
                try:
                    os.rename(self.graph_path, self.graph_path + ".bak")
                except OSError:
                    pass # Best effort
                self.graph = nx.Graph()
            except Exception as e:
                print(f"ERROR: Failed to load graph from {self.graph_path}: {e}")
                import traceback
                traceback.print_exc()
                self.graph = nx.Graph()
    
    # ... rest of methods assume self.graph is correct ...

    def save_graph(self):
        data = nx.node_link_data(self.graph)
        tmp_path = self.graph_path + ".tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.graph_path)
        except Exception as e:
            print(f"Error saving graph: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            
    # --- Note Embedding Methods ---
    def index_note(self, note_id: str, title: str, content: str):
        """Upserts a note's embedding."""
        text = f"Title: {title}\n\nContent:\n{content}"
        embedding = self.embedding_fn.embed_query(text)
        
        self.note_collection.upsert(
            ids=[note_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"title": title}]
        )
        
    def delete_note_embedding(self, note_id: str):
        """Deletes a note's embedding."""
        try:
            self.note_collection.delete(ids=[note_id])
        except:
            pass
            
    def search_notes(self, query: str, k: int = 5):
        """Searches notes by semantic similarity."""
        query_embedding = self.embedding_fn.embed_query(query)
        results = self.note_collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        hits = []
        if results['ids'] and results['ids'][0]:
            for i, note_id in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i]
                doc = results['documents'][0][i]
                hits.append(f"Note ID: {note_id} (Title: {meta.get('title')})\n---\n{doc}\n---")
        
        return "\n\n".join(hits) if hits else "No relevant notes found."

    def upsert_concepts(self, concepts: list):
        """Indexes concepts in the vector store."""
        if not concepts:
            return
            
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for c in concepts:
            # Create a rich text representation for embedding
            text = f"Concept: {c['title']}\nSummary: {c['summary']}\nEntities: {', '.join(c['nodes'][:10])}..."
            embedding = self.embedding_fn.embed_query(text)
            
            ids.append(c['id'])
            embeddings.append(embedding)
            documents.append(text)
            metadatas.append({
                "title": c['title'],
                "node_count": len(c['nodes'])
            })
            
        self.concept_collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search_concepts(self, query: str, k: int = 3):
        """Searches concepts by semantic similarity."""
        query_embedding = self.embedding_fn.embed_query(query)
        results = self.concept_collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        hits = []
        if results['ids'] and results['ids'][0]:
            for i, concept_id in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i]
                doc = results['documents'][0][i]
                hits.append(f"Concept: {meta.get('title')} (ID: {concept_id})\n{doc}")
                
        return "\n---\n".join(hits) if hits else "No relevant concepts found."

    # --- Skill Embedding Methods ---
    def index_skill(self, skill_id: str, title: str, summary: str, explanation: str):
        """Upserts a skill's embedding based on title and summary for search."""
        # Embed title + summary for semantic search
        text = f"Skill: {title}\nSummary: {summary}"
        embedding = self.embedding_fn.embed_query(text)
        
        self.skill_collection.upsert(
            ids=[skill_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "title": title,
                "summary": summary,
                "explanation": explanation  # Store full explanation in metadata
            }]
        )
        
    def delete_skill_embedding(self, skill_id: str):
        """Deletes a skill's embedding."""
        try:
            self.skill_collection.delete(ids=[skill_id])
        except:
            pass
            
    def search_skills(self, query: str, k: int = 3) -> str:
        """
        Searches skills by semantic similarity and returns the full explanation.
        Used by the LLM tool to find and apply learned skills.
        """
        query_embedding = self.embedding_fn.embed_query(query)
        results = self.skill_collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        hits = []
        if results['ids'] and results['ids'][0]:
            for i, skill_id in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i]
                title = meta.get('title', 'Unknown')
                summary = meta.get('summary', '')
                explanation = meta.get('explanation', '')
                hits.append(f"### Skill: {title}\n**Summary**: {summary}\n\n**Instructions**:\n{explanation}")
        
        return "\n\n---\n\n".join(hits) if hits else "No matching skills found."
    
    def get_skill_by_id(self, skill_id: str) -> dict:
        """Gets a specific skill by ID from the vector store."""
        try:
            results = self.skill_collection.get(ids=[skill_id])
            if results['ids'] and results['ids'][0]:
                meta = results['metadatas'][0]
                return {
                    "id": skill_id,
                    "title": meta.get('title', ''),
                    "summary": meta.get('summary', ''),
                    "explanation": meta.get('explanation', '')
                }
        except:
            pass
        return None

    def add_entity(self, name: str, type: str, description: str):

        """Adds or updates an entity in the graph and vector store."""
        
        # Add to Graph
        if not self.graph.has_node(name):
            self.graph.add_node(name, type=type, description=description)
        else:
            # Update description (simple append for now, could be smarter)
            old_desc = self.graph.nodes[name].get('description', '')
            if description not in old_desc:
                self.graph.nodes[name]['description'] = old_desc + "; " + description
        
        # Add to Vector Store (Embedding the description + name for context)
        text_representation = f"{name} ({type}): {description}"
        embedding = self.embedding_fn.embed_query(text_representation)
        
        self.collection.upsert(
            ids=[name], # ID is the entity name for uniqueness
            embeddings=[embedding],
            documents=[text_representation],
            metadatas=[{"name": name, "type": type}]
        )
        self.save_graph()

    def update_entity(self, name: str, type: str = None, description: str = None):
        """Updates an existing entity's properties (overwrite)."""
        if not self.graph.has_node(name):
            return False
            
        if type:
            self.graph.nodes[name]['type'] = type
        if description:
            self.graph.nodes[name]['description'] = description
            
        # Re-embed
        node_data = self.graph.nodes[name]
        current_type = node_data.get('type', 'Unknown')
        current_desc = node_data.get('description', '')
        
        text_representation = f"{name} ({current_type}): {current_desc}"
        embedding = self.embedding_fn.embed_query(text_representation)
        
        self.collection.upsert(
            ids=[name],
            embeddings=[embedding],
            documents=[text_representation],
            metadatas=[{"name": name, "type": current_type}]
        )
        self.save_graph()
        return True

    def add_relation(self, source: str, target: str, relation: str):
        """Adds a relationship between two entities."""
        # Ensure nodes exist
        if not self.graph.has_node(source):
            self.add_entity(source, "Unknown", "Inferred entity")
        if not self.graph.has_node(target):
            self.add_entity(target, "Unknown", "Inferred entity")
            
        self.graph.add_edge(source, target, relation=relation)
        self.save_graph()

    def update_relation(self, source: str, target: str, new_relation: str):
        """Updates an existing relationship (edge)."""
        if not self.graph.has_edge(source, target):
            return False
            
        self.graph[source][target]['relation'] = new_relation
        self.save_graph()
        return True

    def delete_entity(self, name: str):
        """Deletes an entity from the graph and vector store."""
        # 1. Remove from Graph
        if self.graph.has_node(name):
            self.graph.remove_node(name)
            self.save_graph()
            
        # 2. Remove from Vector Store
        try:
            self.collection.delete(ids=[name])
        except Exception as e:
            print(f"Warning: Failed to delete embedding for {name}: {e}")

    def delete_relation(self, source: str, target: str):
        """Deletes a relationship between two entities."""
        if self.graph.has_edge(source, target):
            self.graph.remove_edge(source, target)
            self.save_graph()

    def retrieve_context(self, query: str, k: int = 3, depth: int = 1, include_descriptions: bool = False) -> str:
        """Retrieves relevant subgraph context based on vector similarity and traversal depth."""
        query_embedding = self.embedding_fn.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        if not results['ids'][0]:
            print("DEBUG: No relevant embeddings found.")
            return ""

        print(f"DEBUG: Found {len(results['ids'][0])} relevant nodes in vector store. Traversal Depth: {depth}")
        
        # BFS Traversal
        visited = set()
        queue = []
        
        # Initialize queue with found entities (Depth 0)
        for entity_id in results['ids'][0]:
            if self.graph.has_node(entity_id):
                queue.append((entity_id, 0))
                visited.add(entity_id)

        context_lines = []
        
        # Process Queue
        while queue:
            current_id, current_dist = queue.pop(0)
            
            # 1. Expand current node
            node_data = self.graph.nodes[current_id]
            desc = f" - {node_data.get('description')}" if (current_dist == 0 or include_descriptions) else ""
            context_lines.append(f"Entity (Depth {current_dist}): {current_id} ({node_data.get('type')}){desc}")
            
            # Stop if we reached max depth
            if current_dist >= depth:
                continue
            
            # 2. Get Neighbors
            neighbors = list(self.graph.neighbors(current_id))
            for neighbor in neighbors:
                edge_data = self.graph.get_edge_data(current_id, neighbor)
                relation = edge_data.get('relation')
                
                # Add relationship context
                context_lines.append(f"  - Related to {neighbor} via '{relation}'")
                
                # Add to queue if not visited
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_dist + 1))

        return "\n".join(context_lines)

    def retrieve_context_with_nodes(self, query: str, k: int = 3, depth: int = 1, 
                                     include_descriptions: bool = False, 
                                     focused_node: str = None) -> dict:
        """
        Retrieves relevant subgraph context and returns both context text AND node/edge metadata.
        Used by graph chat to highlight retrieved nodes on the visualization.
        
        Returns:
            dict with keys:
                - context: str (text context for LLM)
                - retrieved_nodes: list[str] (all visited node IDs)
                - retrieved_edges: list[dict] (all traversed edges as {source, target, relation})
        """
        retrieved_nodes = []
        retrieved_edges = []
        
        # If a focused node is provided, use it as a starting point
        if focused_node and self.graph.has_node(focused_node):
            starting_nodes = [focused_node]
        else:
            # Vector similarity search
            query_embedding = self.embedding_fn.embed_query(query)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k
            )
            
            if not results['ids'][0]:
                print("DEBUG: No relevant embeddings found.")
                return {"context": "", "retrieved_nodes": [], "retrieved_edges": []}
            
            starting_nodes = [eid for eid in results['ids'][0] if self.graph.has_node(eid)]
        
        if not starting_nodes:
            return {"context": "", "retrieved_nodes": [], "retrieved_edges": []}
            
        print(f"DEBUG: Starting graph traversal from {len(starting_nodes)} nodes. Depth: {depth}")
        
        # BFS Traversal
        visited = set()
        queue = []
        
        # Initialize queue with found entities (Depth 0)
        for entity_id in starting_nodes:
            queue.append((entity_id, 0))
            visited.add(entity_id)

        context_lines = []
        
        # Process Queue
        while queue:
            current_id, current_dist = queue.pop(0)
            
            # Track this node
            retrieved_nodes.append(current_id)
            
            # 1. Expand current node
            node_data = self.graph.nodes[current_id]
            desc = f" - {node_data.get('description')}" if (current_dist == 0 or include_descriptions) else ""
            context_lines.append(f"Entity (Depth {current_dist}): {current_id} ({node_data.get('type')}){desc}")
            
            # Stop if we reached max depth
            if current_dist >= depth:
                continue
            
            # 2. Get Neighbors
            neighbors = list(self.graph.neighbors(current_id))
            for neighbor in neighbors:
                edge_data = self.graph.get_edge_data(current_id, neighbor)
                relation = edge_data.get('relation', 'related')
                
                # Track this edge
                retrieved_edges.append({
                    "source": current_id,
                    "target": neighbor,
                    "relation": relation
                })
                
                # Add relationship context
                context_lines.append(f"  - Related to {neighbor} via '{relation}'")
                
                # Add to queue if not visited
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_dist + 1))

        return {
            "context": "\n".join(context_lines),
            "retrieved_nodes": retrieved_nodes,
            "retrieved_edges": retrieved_edges
        }

    def get_graph_data(self):
        """Returns graph data in a format suitable for visualization."""
        return nx.node_link_data(self.graph)

    def clear(self):
        self.graph.clear()
        self.save_graph()
        self.chroma_client.delete_collection("entity_embeddings")
        self.collection = self.chroma_client.get_or_create_collection(
            name="entity_embeddings",
            metadata={"hnsw:space": "cosine"}
        )

    def get_stats(self):
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "workspace_id": self.workspace_id
        }
        
    def get_related_nodes(self, topic: str, n: int = 5):
        """Returns n nodes semantically related to the topic."""
        query_embedding = self.embedding_fn.embed_query(topic)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n
        )
        
        if results['ids'] and results['ids'][0]:
            return results['ids'][0]
        return []

    def get_random_nodes(self, n: int = 3):
        """Returns n random nodes from the graph."""
        nodes = list(self.graph.nodes())
        if not nodes:
             return []
        import random
        # Ensure we don't pick more than exist
        if n > len(nodes):
            n = len(nodes)
        return random.sample(nodes, n)



    def reindex_graph(self):
        """
        Re-indexes the entire current NetworkX graph into the ChromaDB vector store.
        Useful after importing a graph file externally.
        """
        print(f"Re-indexing graph for workspace {self.workspace_id}...")
        
        # 1. Clear existing collection
        try:
            # Get all IDs to delete
            existing = self.collection.get()
            if existing and existing['ids']:
                print(f"Deleting {len(existing['ids'])} existing embeddings...")
                self.collection.delete(ids=existing['ids'])
        except Exception as e:
            print(f"Error clearing collection (might be empty): {e}")

        # 2. Re-embed all nodes
        nodes_to_add = []
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        # Batch preparation
        # We'll do it in one go for small graphs, or chunk it?
        # Graph size < 2000 nodes usually. One go is fine?
        # Chroma handles batching internally mostly, but let's be safe.
        
        nodes = list(self.graph.nodes(data=True))
        print(f"Found {len(nodes)} nodes to index.")
        
        if not nodes:
            return

        for name, data in nodes:
            desc = data.get('description', '')
            type_ = data.get('type', 'Unknown')
            
            text_representation = f"{name} ({type_}): {desc}"
            # We defer embedding to the batch call? 
            # `embedding_fn.embed_documents` takes a list.
            
            ids.append(name)
            documents.append(text_representation)
            metadatas.append({"name": name, "type": type_})
        
        # Generate Embeddings in batch (faster)
        try:
            embeddings = self.embedding_fn.embed_documents(documents)
            
            # Upsert
            # Chroma max batch size is usually ~5000+. 
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            print("Re-indexing complete.")
        except Exception as e:
            print(f"Failed to re-index: {e}")

    def get_node_neighbors(self, node_id: str) -> dict:
        """
        Returns full details of a node and its direct neighbors.
        Useful for traversing the graph.
        """
        if not self.graph.has_node(node_id):
            return None
            
        # Node Data
        node_data = self.graph.nodes[node_id]
        
        # Neighbors
        neighbors = []
        
        # Use .neighbors() which works for both Graph and DiGraph (for DiGraph it implies successors)
        # Since our graph is initialized as nx.Graph() (Undirected), we parse all connections.
        if hasattr(self.graph, 'neighbors'):
            for neighbor in self.graph.neighbors(node_id):
                edge_data = self.graph.get_edge_data(node_id, neighbor)
                relation = edge_data.get('relation', 'related') if edge_data else "related"
                neighbors.append({"id": neighbor, "relation": relation})
            
        return {
            "id": node_id,
            "type": node_data.get("type", "Unknown"),
            "description": node_data.get("description", ""),
            "neighbors": neighbors
        }

    def get_clusters(self, resolution: float = 1.0):
        """
        Divides the graph into clusters using Greedy Modularity Communities.
        Returns a list of sets, where each set contains node IDs.
        """
        if self.graph.number_of_nodes() < 2:
            return [set(self.graph.nodes())]
            
        from networkx.algorithms import community
        try:
            # Resolution > 1 makes smaller clusters, < 1 makes larger clusters
            communities = community.greedy_modularity_communities(self.graph, resolution=resolution)
            return communities
        except Exception as e:
            print(f"Clustering failed: {e}")
            # Fallback to connected components
            import networkx as nx
            return list(nx.connected_components(self.graph.to_undirected()))

    def get_subgraph_context(self, node_ids: list) -> str:
        """
        Generates a text description of a subgraph (nodes + internal edges).
        Used for LLM summarization.
        """
        subgraph = self.graph.subgraph(node_ids)
        lines = []
        
        # Describe Nodes
        for node in subgraph.nodes():
            data = subgraph.nodes[node]
            lines.append(f"Entity: {node} ({data.get('type', 'Unknown')}) - {data.get('description', '')}")
            
        # Describe Edges
        lines.append("\nRelationships:")
        for u, v, data in subgraph.edges(data=True):
            lines.append(f"- {u} is related to {v} via '{data.get('relation', 'related')}'")
            
        return "\n".join(lines)

    def get_hot_topics(self, limit: int = 10):
        """
        Returns top nodes sorted by degree centrality.
        """
        if self.graph.number_of_nodes() == 0:
            return []

        # Calculate degree centrality
        centrality = nx.degree_centrality(self.graph)
        
        # Sort by centrality (descending)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        # Take top N
        top_nodes = sorted_nodes[:limit]
        
        results = []
        for node_id, score in top_nodes:
            node_data = self.graph.nodes[node_id]
            degree = self.graph.degree[node_id]
            results.append({
                "id": node_id,
                "type": node_data.get("type", "Unknown"),
                "description": node_data.get("description", ""),
                "centrality": score,
                "degree": degree
            })
            
        return results

    def get_connectors(self, limit: int = 10, sample_size: int = None):
        """
        Returns top nodes sorted by betweenness centrality (connectors).
        :param limit: Number of top nodes to return.
        :param sample_size: Number of nodes to sample for centrality calculation (k). 
                            If None or larger than graph, use full graph.
        """
        if self.graph.number_of_nodes() == 0:
            return []

        # Validate sample_size
        k = sample_size
        if k is not None and k >= self.graph.number_of_nodes():
            k = None

        # Calculate betweenness centrality
        # k=None means exact, k=int means approximation
        centrality = nx.betweenness_centrality(self.graph, k=k)
        
        # Sort by centrality (descending)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        # Take top N
        top_nodes = sorted_nodes[:limit]
        
        results = []
        for node_id, score in top_nodes:
            node_data = self.graph.nodes[node_id]
            degree = self.graph.degree[node_id]
            results.append({
                "id": node_id,
                "type": node_data.get("type", "Unknown"),
                "description": node_data.get("description", ""),
                "centrality": score,
                "degree": degree
            })
            
        return results

    def get_knowledge_gaps(self, limit: int = 10, max_degree: int = 2, min_nodes: int = 5):
        """
        Returns nodes with low connectivity (potential knowledge gaps).
        These are "orphan" or "stub" entities that could benefit from expansion.
        
        :param limit: Number of gaps to return
        :param max_degree: Maximum degree to consider as a "gap" (nodes with <= this many connections)
        :param min_nodes: Minimum graph size before analysis makes sense
        """
        node_count = self.graph.number_of_nodes()
        
        if node_count < min_nodes:
            return []
        
        # Get all nodes with their degrees
        node_degrees = [(node_id, self.graph.degree[node_id]) for node_id in self.graph.nodes()]
        
        # Filter to only low-connectivity nodes
        low_connectivity = [(node_id, degree) for node_id, degree in node_degrees if degree <= max_degree]
        
        # Sort by degree (ascending) - lowest connectivity first
        low_connectivity.sort(key=lambda x: x[1])
        
        # Take top N gaps
        gaps = low_connectivity[:limit]
        
        results = []
        for node_id, degree in gaps:
            node_data = self.graph.nodes[node_id]
            results.append({
                "id": node_id,
                "type": node_data.get("type", "Unknown"),
                "description": node_data.get("description", ""),
                "degree": degree
            })
        
        return results
