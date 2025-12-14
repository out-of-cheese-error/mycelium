import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent import traverse_graph_node
from app.memory_store import GraphMemory

def test_traversal():
    """Test graph traversal on available workspace data."""
    # Try different workspaces
    for workspace in ["games", "research", "test"]:
        mem = GraphMemory(workspace_id=workspace)
        nodes = mem.graph.nodes()
        if nodes:
            valid_node = list(nodes)[0]
            print(f"Testing traversal on node: {valid_node} (workspace: {workspace})")
            result = traverse_graph_node.invoke({"node_id": valid_node, "workspace_id": workspace})
            print("Result:")
            print(result)
            return
    
    print("No nodes found in any workspace to test.")

if __name__ == '__main__':
    test_traversal()

