from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from langchain_core.messages import HumanMessage, AIMessage
from app.memory_store import GraphMemory
from app.llm_config import llm_config

router = APIRouter(prefix="/graph", tags=["graph_chat"])


class GraphChatRequest(BaseModel):
    message: str
    focused_node_id: Optional[str] = None
    k: Optional[int] = None  # Number of nodes to retrieve
    depth: Optional[int] = None  # Traversal depth


@router.post("/{workspace_id}/chat")
async def graph_chat(workspace_id: str, request: GraphChatRequest):
    """
    Chat endpoint specifically for graph view.
    Returns streaming response with retrieved node/edge metadata at the end.
    
    The stream format is:
    - Regular text chunks for the LLM response
    - Final line: ###GRAPH_CONTEXT###{"retrieved_nodes": [...], "retrieved_edges": [...]}
    """
    
    # Initialize memory store for this workspace
    memory_store = GraphMemory(workspace_id=workspace_id)
    
    # Use request params if provided, else load from workspace config, else defaults
    import os
    k = request.k if request.k is not None else 3
    depth = request.depth if request.depth is not None else 1
    include_descriptions = True  # More verbose for graph chat
    
    try:
        config_path = os.path.join("memory_data", workspace_id, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                ws_config = json.load(f)
                # Only use config values if not overridden by request
                if request.k is None:
                    k = ws_config.get("graph_k", k)
                if request.depth is None:
                    depth = ws_config.get("graph_depth", depth)
                include_descriptions = ws_config.get("graph_include_descriptions", True)
    except Exception as e:
        print(f"Error loading workspace config: {e}")
    
    # Retrieve context with node tracking
    retrieval_result = memory_store.retrieve_context_with_nodes(
        query=request.message,
        k=k,
        depth=depth,
        include_descriptions=include_descriptions,
        focused_node=request.focused_node_id
    )
    
    context = retrieval_result["context"]
    retrieved_nodes = retrieval_result["retrieved_nodes"]
    retrieved_edges = retrieval_result["retrieved_edges"]
    
    # Build system prompt with context
    system_prompt = f"""You are an AI assistant helping the user explore their knowledge graph.
The user is viewing the graph and asking about specific nodes or relationships.

RELEVANT CONTEXT FROM KNOWLEDGE GRAPH:
{context if context else "No relevant context found in the graph."}

Answer the user's question based on the context above. Be specific about the entities and relationships.
If you don't have enough information, say so clearly."""

    # Build messages
    messages = [
        HumanMessage(content=f"{system_prompt}\n\nUser Question: {request.message}")
    ]
    
    async def event_generator():
        full_response = ""
        
        try:
            llm = llm_config.get_chat_llm()
            
            # Stream the response
            for chunk in llm.stream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            
            # After streaming completes, append the metadata
            metadata = {
                "retrieved_nodes": retrieved_nodes,
                "retrieved_edges": retrieved_edges
            }
            yield f"\n###GRAPH_CONTEXT###{json.dumps(metadata)}"
            
        except Exception as e:
            print(f"Graph chat error: {e}")
            import traceback
            traceback.print_exc()
            yield f"\n[Error: {str(e)}]"
    
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.get("/{workspace_id}/node/{node_id}")
async def get_node_context(workspace_id: str, node_id: str, depth: int = 1):
    """
    Get context for a specific node and its neighbors.
    Returns node details and surrounding subgraph for display.
    """
    memory_store = GraphMemory(workspace_id=workspace_id)
    
    if not memory_store.graph.has_node(node_id):
        return {"error": "Node not found", "node_id": node_id}
    
    # Get node details
    node_data = memory_store.graph.nodes[node_id]
    
    # Get neighbors up to depth
    neighbors = []
    edges = []
    visited = {node_id}
    queue = [(node_id, 0)]
    
    while queue:
        current_id, current_depth = queue.pop(0)
        
        if current_depth >= depth:
            continue
            
        for neighbor in memory_store.graph.neighbors(current_id):
            edge_data = memory_store.graph.get_edge_data(current_id, neighbor)
            edges.append({
                "source": current_id,
                "target": neighbor,
                "relation": edge_data.get("relation", "related")
            })
            
            if neighbor not in visited:
                visited.add(neighbor)
                neighbor_data = memory_store.graph.nodes[neighbor]
                neighbors.append({
                    "id": neighbor,
                    "type": neighbor_data.get("type", "Unknown"),
                    "description": neighbor_data.get("description", "")
                })
                queue.append((neighbor, current_depth + 1))
    
    return {
        "node": {
            "id": node_id,
            "type": node_data.get("type", "Unknown"),
            "description": node_data.get("description", "")
        },
        "neighbors": neighbors,
        "edges": edges
    }
