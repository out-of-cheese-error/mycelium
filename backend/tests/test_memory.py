import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory_store import GraphMemory
from langchain_core.messages import AIMessage

class TestGraphMemory(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for tests
        self.memory = GraphMemory(workspace_id="test", base_dir="./tests/test_memory_data")
        self.memory.clear()

    def test_add_and_retrieve_entity(self):
        """Test adding an entity and retrieving it."""
        self.memory.add_entity("TestUser", "Person", "Loves testing.")
        
        # Verify Graph
        self.assertTrue(self.memory.graph.has_node("TestUser"))
        self.assertEqual(self.memory.graph.nodes["TestUser"]["description"], "Loves testing.")
        
        # Verify Retrieval (Mocking embedding for simplicity or relying on local all-MiniLM being fast)
        # We rely on real embeddings here since we installed sentence-transformers
        context = self.memory.retrieve_context("Who is TestUser?")
        self.assertIn("TestUser", context)
        self.assertIn("Loves testing", context)

    def test_add_relation(self):
        self.memory.add_entity("Alice", "Person", "A developer")
        self.memory.add_entity("Bob", "Person", "A manager")
        self.memory.add_relation("Alice", "Bob", "reports_to")
        
        self.assertTrue(self.memory.graph.has_edge("Alice", "Bob"))
        self.assertEqual(self.memory.graph.edges["Alice", "Bob"]["relation"], "reports_to")

if __name__ == '__main__':
    unittest.main()

