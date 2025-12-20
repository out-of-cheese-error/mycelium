"""
Workspace Tool Service

Handles operations for exposing workspaces as expert tools that can be
consulted by other workspaces.
"""
import os
import json
from app.memory_store import GraphMemory
from app.llm_config import llm_config
from langchain_core.messages import HumanMessage
from app.services.concept_service import ConceptService

MEMORY_BASE_DIR = "./memory_data"


def get_config_path(workspace_id: str):
    return os.path.join(MEMORY_BASE_DIR, workspace_id, "config.json")


def get_workspace_settings(workspace_id: str):
    """Load workspace settings from disk."""
    config_path = get_config_path(workspace_id)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def get_exposed_workspace_tools():
    """
    Returns list of workspaces that are exposed as tools.
    Each entry contains: workspace_id, tool_name, tool_description
    """
    exposed = []
    
    if not os.path.exists(MEMORY_BASE_DIR):
        return exposed
    
    for item in os.listdir(MEMORY_BASE_DIR):
        item_path = os.path.join(MEMORY_BASE_DIR, item)
        if os.path.isdir(item_path):
            settings = get_workspace_settings(item)
            if settings.get("is_tool_enabled") and settings.get("tool_name"):
                exposed.append({
                    "workspace_id": item,
                    "tool_name": f"ask_{settings['tool_name']}",
                    "tool_description": settings.get("tool_description", f"Consult the {item} workspace for expert knowledge.")
                })
    
    return exposed


def consult_workspace(workspace_id: str, query: str, k: int = 5, depth: int = 2):
    """
    Consults a workspace's knowledge graph and returns relevant context.
    
    Args:
        workspace_id: The workspace to query
        query: The question or topic to search for
        k: Number of top nodes to retrieve
        depth: Traversal depth from matched nodes
    
    Returns:
        A formatted string with the retrieved knowledge
    """
    workspace_path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(workspace_path):
        return f"Error: Workspace '{workspace_id}' not found."
    
    try:
        memory = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
        context = memory.retrieve_context(query, k=k, depth=depth, include_descriptions=True)
        
        if not context or context.strip() == "":
            return f"No relevant information found in workspace '{workspace_id}' for query: {query}"
        
        return context
    except Exception as e:
        return f"Error consulting workspace '{workspace_id}': {str(e)}"


async def generate_tool_description(workspace_id: str):
    """
    Uses LLM to generate a tool description based on workspace concepts.
    
    Returns:
        A concise description suitable for an AI tool
    """
    workspace_path = os.path.join(MEMORY_BASE_DIR, workspace_id)
    if not os.path.exists(workspace_path):
        raise ValueError(f"Workspace '{workspace_id}' not found")
    
    # Get concepts
    concept_service = ConceptService(workspace_id)
    concepts = concept_service.get_concepts()
    
    # Get some node stats for context
    memory = GraphMemory(workspace_id=workspace_id, base_dir=MEMORY_BASE_DIR)
    stats = memory.get_stats()
    
    # Build context for LLM
    concept_titles = [c.get("title", "Unknown") for c in concepts[:10]]
    concept_summaries = [c.get("summary", "") for c in concepts[:5]]
    
    if not concepts:
        # Fallback: get some hot topics from the graph
        hot_topics = memory.get_hot_topics(limit=10)
        topic_names = [t.get("id", "") for t in hot_topics]
        context_text = f"Main topics in this workspace: {', '.join(topic_names)}"
    else:
        context_text = f"""
Concepts in this workspace:
- Titles: {', '.join(concept_titles)}
- Sample summaries: {' | '.join(concept_summaries[:3])}
"""
    
    llm = llm_config.get_chat_llm()
    
    prompt = f"""You are helping create a tool description for an AI assistant.

This workspace contains knowledge about specific domains. Based on the following information, write a concise, 1-2 sentence description that explains what kind of questions this knowledge base can answer.

Workspace: "{workspace_id}"
Stats: {stats['node_count']} nodes, {stats['edge_count']} edges
{context_text}

Write a tool description in this format:
"Consult this expert for questions about [domain]. Specializes in [specific topics]."

Output ONLY the description, no quotes or extra text:"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        description = response.content.strip()
        # Clean up any quotes
        description = description.strip('"\'')
        return description
    except Exception as e:
        # Fallback description
        return f"Consult the {workspace_id} workspace for specialized knowledge on its stored topics."
