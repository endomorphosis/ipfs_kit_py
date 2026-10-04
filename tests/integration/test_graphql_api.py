"""
Test suite for the GraphQL API functionality.

Tests the GraphQL schema and endpoint operations.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import GraphQL components - will be skipped if not available
try:
    import graphene
    from fastapi.testclient import TestClient
    from graphene.test import Client

    from ipfs_kit_py import graphql_schema
    from ipfs_kit_py.api import app

    GRAPHQL_AVAILABLE = True
except ImportError:
    GRAPHQL_AVAILABLE = False


@unittest.skipIf(not GRAPHQL_AVAILABLE, "GraphQL or FastAPI dependencies not available")
class TestGraphQLSchema(unittest.TestCase):
    """Tests for the GraphQL schema functionality."""

    def setUp(self):
        """Set up the test environment."""
        # Create a mock API for testing
        self.mock_api = MagicMock()

        # Mock version response
        self.mock_api.kit.ipfs_version.return_value = {"Version": "0.18.0"}

        # Mock pin listing response
        self.mock_api.kit.ipfs_pin_ls.return_value = {
            "Keys": {"QmTest1": {"Type": "recursive"}, "QmTest2": {"Type": "direct"}}
        }

        # Create a test client for the schema
        self.client = Client(graphql_schema.schema)

    def test_query_version(self):
        """Test querying the IPFS version."""
        query = """
        query {
          version
        }
        """

        # Execute query with mocked context
        result = graphql_schema.execute_graphql(query, context={"api": self.mock_api})

        # Check results
        self.assertIn("data", result)
        self.assertIn("version", result["data"])
        self.assertEqual(result["data"]["version"], "0.18.0")

    def test_query_pins(self):
        """Test querying pinned content."""
        query = """
        query {
          pins {
            cid
            pinInfo {
              type
            }
          }
        }
        """

        # Execute query with mocked context
        result = graphql_schema.execute_graphql(query, context={"api": self.mock_api})

        # Check results
        self.assertIn("data", result)
        self.assertIn("pins", result["data"])
        self.assertEqual(len(result["data"]["pins"]), 2)

        # Check that pins contain expected data
        pin_cids = [pin["cid"] for pin in result["data"]["pins"]]
        self.assertIn("QmTest1", pin_cids)
        self.assertIn("QmTest2", pin_cids)

        # Check pin types
        pin_types = [
            pin["pinInfo"]["type"] for pin in result["data"]["pins"] if pin["cid"] == "QmTest1"
        ]
        self.assertGreater(len(pin_types), 0)
        self.assertEqual(pin_types[0], "recursive")

    def test_add_content_mutation(self):
        """Test adding content mutation."""
        # Mock the API's add method
        self.mock_api.add.return_value = {"Hash": "QmTestAdded", "Size": 42}

        # Content to add (base64 encoded "test content")
        content_base64 = "dGVzdCBjb250ZW50"

        mutation = (
            """
        mutation {
          addContent(content: "%s", pin: true) {
            success
            cid
            size
          }
        }
        """
            % content_base64
        )

        # Execute mutation with mocked context
        result = graphql_schema.execute_graphql(mutation, context={"api": self.mock_api})

        # Check results
        self.assertIn("data", result)
        self.assertIn("addContent", result["data"])
        self.assertTrue(result["data"]["addContent"]["success"])
        self.assertEqual(result["data"]["addContent"]["cid"], "QmTestAdded")
        self.assertEqual(result["data"]["addContent"]["size"], 42)

        # Verify the API was called correctly
        self.mock_api.add.assert_called_once()
        args, kwargs = self.mock_api.add.call_args
        self.assertTrue(len(args) > 0)
        self.assertEqual(kwargs.get("pin"), True)


@unittest.skipIf(not GRAPHQL_AVAILABLE, "GraphQL or FastAPI dependencies not available")
class TestGraphQLEndpoint(unittest.TestCase):
    """Tests for the GraphQL API endpoint."""

    def setUp(self):
        """Set up the test environment."""
        # Create a mock API for testing
        self.mock_api = MagicMock()

        # Set up FastAPI test client
        self.client = TestClient(app)

        # Mock app state to use our mock API
        app.state.ipfs_api = self.mock_api

    def test_graphql_endpoint_query(self):
        """Test GraphQL endpoint with a query."""
        # Mock version response
        self.mock_api.kit.ipfs_version.return_value = {"Version": "0.18.0"}

        # Set up query
        query = {
            "query": """
            query {
              version
            }
            """
        }

        # Make request to GraphQL endpoint
        response = self.client.post("/graphql", json=query)

        # Check response
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("data", result)
        self.assertIn("version", result["data"])
        self.assertEqual(result["data"]["version"], "0.18.0")

    def test_graphql_endpoint_mutation(self):
        """Test GraphQL endpoint with a mutation."""
        # Mock add response
        self.mock_api.add.return_value = {"Hash": "QmTestAdded", "Size": 42}

        # Set up mutation
        mutation = {
            "query": """
            mutation {
              addContent(content: "dGVzdCBjb250ZW50", pin: true) {
                success
                cid
                size
              }
            }
            """
        }

        # Make request to GraphQL endpoint
        response = self.client.post("/graphql", json=mutation)

        # Check response
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("data", result)
        self.assertIn("addContent", result["data"])
        self.assertTrue(result["data"]["addContent"]["success"])
        self.assertEqual(result["data"]["addContent"]["cid"], "QmTestAdded")

    def test_graphql_error_handling(self):
        """Test GraphQL error handling."""
        # Set up invalid query
        query = {
            "query": """
            query {
              invalidField
            }
            """
        }

        # Make request to GraphQL endpoint
        response = self.client.post("/graphql", json=query)

        # Check response
        self.assertEqual(response.status_code, 200)  # GraphQL returns 200 even for query errors
        result = response.json()
        self.assertIn("errors", result)
        self.assertGreater(len(result["errors"]), 0)


if __name__ == "__main__":
    unittest.main()
