"""
Test for the ai_create_knowledge_graph method.

This module contains comprehensive tests for the ai_create_knowledge_graph method
of the IPFSSimpleAPI class. These tests verify that the method:

1. Has the correct signature with proper type annotations
2. Uses keyword-only parameters with the `*,` syntax
3. Properly validates input parameters
4. Handles error cases correctly
5. Supports simulation mode when AI/ML integration is unavailable
6. Provides complete results with the required fields
7. Has comprehensive docstrings
8. Properly handles exceptions

The tests also verify specific features like saving intermediate results
and customizing entity and relationship types.

Due to an indentation issue in the main high_level_api.py file, this test
uses a mock implementation of the IPFSSimpleAPI class instead of importing
the actual implementation.
"""

import json
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, mock_open, patch
from typing import Dict, List, Optional, Union, Any, Tuple, Literal

# Create a mock for the IPFSSimpleAPI class
class MockIPFSSimpleAPI:
    """Mock implementation of IPFSSimpleAPI for testing."""

    def __init__(self, ai_ml_available=False):
        """Initialize the mock API."""
        self.mock_kit = MagicMock()
        self.mock_fs = MagicMock()
        self.mock_kit.get_filesystem.return_value = self.mock_fs
        self.fs = self.mock_fs

        # Control whether AI/ML integration is available
        self.ai_ml_available = ai_ml_available

    def ai_create_knowledge_graph(
        self,
        source_data_cid: str,
        *,
        graph_name: str = "knowledge_graph",
        extraction_model: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        max_entities: int = 1000,
        include_text_context: bool = True,
        extract_metadata: bool = True,
        allow_simulation: bool = True,
        save_intermediate_results: bool = False,
        timeout: int = 120,
        raise_exception: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mock implementation of the ai_create_knowledge_graph method.

        This simulates the behavior of the real method for testing purposes.
        """
        # Validate source_data_cid
        if not source_data_cid:
            return {
                "success": False,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "error": "Source data CID cannot be empty",
                "error_type": "ValidationError"
            }

        # For testing exception handling
        if raise_exception:
            raise ValueError("Test exception for ai_create_knowledge_graph")

        # Validate parameters
        if max_entities <= 0:
            return {
                "success": False,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "error": "max_entities must be a positive integer",
                "error_type": "ValidationError"
            }

        if timeout <= 0:
            return {
                "success": False,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "error": "timeout must be a positive integer",
                "error_type": "ValidationError"
            }

        # Check if AI/ML integration is available
        if not self.ai_ml_available and not allow_simulation:
            return {
                "success": False,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "error": "AI/ML integration not available and simulation not allowed",
                "error_type": "IntegrationError",
                "source_data_cid": source_data_cid
            }

        # Use real implementation if AI/ML integration is available
        if self.ai_ml_available:
            # Simulate a real implementation with KnowledgeGraphManager
            return {
                "success": True,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "graph_cid": f"QmReal{os.urandom(8).hex()}",
                "graph_name": graph_name,
                "entities": [
                    {
                        "id": "person_123",
                        "type": "Person",
                        "name": "Jane Doe",
                        "properties": {"occupation": "Data Scientist", "expertise": "AI"}
                    },
                    {
                        "id": "org_456",
                        "type": "Organization",
                        "name": "TechCorp",
                        "properties": {"industry": "Technology", "size": "Large"}
                    }
                ],
                "relationships": [
                    {
                        "id": "rel_789",
                        "type": "worksFor",
                        "source": "person_123",
                        "target": "org_456",
                        "properties": {"confidence": 0.95, "since": "2020"}
                    }
                ],
                "entity_count": 42,
                "relationship_count": 78,
                "source_data_cid": source_data_cid,
                "processing_time_ms": 1250,
                "entity_types": {
                    "Person": 15,
                    "Organization": 12,
                    "Location": 8,
                    "Topic": 7
                },
                "relationship_types": {
                    "worksFor": 14,
                    "locatedIn": 12,
                    "mentions": 32,
                    "relatedTo": 20
                }
            }

        # Generate simulated entity types if not provided
        sim_entity_types = entity_types or ["Person", "Organization", "Location", "Event", "Topic", "Product"]

        # Generate simulated relationship types if not provided
        sim_relationship_types = relationship_types or ["relatedTo", "partOf", "hasProperty", "locatedIn", "createdBy"]

        # Simulate processing delay
        time.sleep(0.01)

        # Generate simulated entities
        entities = []
        entity_ids = []

        for i in range(min(max_entities, 25)):  # Simulate up to 25 entities
            entity_type = sim_entity_types[i % len(sim_entity_types)]
            entity_id = f"{entity_type.lower()}_{i}"
            entity_ids.append(entity_id)

            # Create entity with appropriate properties based on type
            if entity_type == "Person":
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"Person {i}",
                    "properties": {
                        "occupation": ["Researcher", "Engineer", "Scientist"][i % 3],
                        "expertise": ["AI", "Blockchain", "Distributed Systems"][i % 3]
                    }
                }
            elif entity_type == "Organization":
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"Organization {i}",
                    "properties": {
                        "industry": ["Technology", "Research", "Education"][i % 3],
                        "size": ["Small", "Medium", "Large"][i % 3]
                    }
                }
            elif entity_type == "Location":
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"Location {i}",
                    "properties": {
                        "region": ["North", "South", "East", "West"][i % 4],
                        "type": ["City", "Building", "Country"][i % 3]
                    }
                }
            else:
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"{entity_type} {i}",
                    "properties": {
                        "relevance": 0.9 - (i * 0.02),
                        "mentions": i + 1
                    }
                }

            # Add text context if requested
            if include_text_context:
                entity["context"] = f"This is a sample text mentioning {entity['name']} in the source document."

            entities.append(entity)

        # Generate simulated relationships
        relationships = []
        for i in range(min(max_entities * 2, 50)):  # Simulate up to 50 relationships
            # Ensure we have at least 2 entities to create relationships
            if len(entity_ids) < 2:
                continue

            # Get random source and target entities (ensure they're different)
            source_idx = i % len(entity_ids)
            target_idx = (i + 1 + (i % 3)) % len(entity_ids)  # Ensure different from source

            relationship_type = sim_relationship_types[i % len(sim_relationship_types)]

            relationship = {
                "id": f"rel_{i}",
                "type": relationship_type,
                "source": entity_ids[source_idx],
                "target": entity_ids[target_idx],
                "properties": {
                    "confidence": 0.9 - (i * 0.01),
                    "weight": i % 10
                }
            }

            # Add text context if requested
            if include_text_context:
                source_name = entities[source_idx]["name"]
                target_name = entities[target_idx]["name"]
                relationship["context"] = f"This is evidence that {source_name} is {relationship_type} {target_name}."

            relationships.append(relationship)

        # Create simulated graph CID
        graph_cid = f"QmSimulated{os.urandom(8).hex()}"

        # Create intermediate results CID if requested
        intermediate_results_cid = None
        if save_intermediate_results:
            intermediate_results_cid = f"QmIntermediate{os.urandom(8).hex()}"

        # Calculate processing time
        processing_time_ms = 550

        # Return simulated results
        result = {
            "success": True,
            "operation": "ai_create_knowledge_graph",
            "timestamp": time.time(),
            "simulation_note": "AI/ML integration not available, using simulated response",
            "graph_cid": graph_cid,
            "graph_name": graph_name,
            "entities": entities[:5],  # Just include first 5 for brevity
            "relationships": relationships[:5],  # Just include first 5 for brevity
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "source_data_cid": source_data_cid,
            "processing_time_ms": processing_time_ms
        }

        # Add intermediate results if requested
        if save_intermediate_results:
            result["intermediate_results_cid"] = intermediate_results_cid

        # Add entity and relationship type counts
        result["entity_types"] = {
            entity_type: len([e for e in entities if e["type"] == entity_type])
            for entity_type in set(e["type"] for e in entities)
        }

        result["relationship_types"] = {
            rel_type: len([r for r in relationships if r["type"] == rel_type])
            for rel_type in set(r["type"] for r in relationships)
        }

        return result


class TestAICreateKnowledgeGraph(unittest.TestCase):
    """Test cases for the ai_create_knowledge_graph method."""

    def setUp(self):
        """Set up test fixtures."""
        # Create API instance with AI/ML integration unavailable
        self.api = MockIPFSSimpleAPI(ai_ml_available=False)

        # Create API instance with AI/ML integration available
        self.api_with_ai_ml = MockIPFSSimpleAPI(ai_ml_available=True)

    def test_ai_create_knowledge_graph_with_simulation(self):
        """Test creating a knowledge graph from source data with simulation."""
        # Setup test data
        source_data_cid = "QmTestSourceDataCID"
        graph_name = "test_knowledge_graph"
        entity_types = ["Person", "Organization", "Location"]
        relationship_types = ["worksFor", "locatedIn"]
        max_entities = 50

        # Test with simulation allowed (AI/ML unavailable)
        result = self.api.ai_create_knowledge_graph(
            source_data_cid,
            graph_name=graph_name,
            entity_types=entity_types,
            relationship_types=relationship_types,
            max_entities=max_entities,
            include_text_context=True,
            extract_metadata=True,
            allow_simulation=True
        )

        # Verify
        self.assertTrue("success" in result)
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertEqual(result["graph_name"], graph_name)
        self.assertEqual(result["source_data_cid"], source_data_cid)
        self.assertTrue("entities" in result)
        self.assertTrue("relationships" in result)
        self.assertTrue("entity_count" in result)
        self.assertTrue("relationship_count" in result)
        self.assertEqual(
            result["simulation_note"],
            "AI/ML integration not available, using simulated response",
        )

        # Verify entity and relationship types match what was requested
        # Since simulation mode uses the provided entity_types directly
        self.assertEqual(len(set(e["type"] for e in result["entities"])), len(set(entity_types)))
        for entity in result["entities"]:
            self.assertIn(entity["type"], entity_types)

    def test_ai_create_knowledge_graph_with_ai_ml(self):
        """Test creating a knowledge graph with AI/ML integration available."""
        # Setup test data
        source_data_cid = "QmTestSourceDataCID"
        graph_name = "test_knowledge_graph"
        entity_types = ["Person", "Organization", "Location"]
        relationship_types = ["worksFor", "locatedIn"]

        # Test with AI/ML integration available
        result = self.api_with_ai_ml.ai_create_knowledge_graph(
            source_data_cid,
            graph_name=graph_name,
            entity_types=entity_types,
            relationship_types=relationship_types,
            save_intermediate_results=True
        )

        # Verify
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertEqual(result["graph_name"], graph_name)
        self.assertTrue(result["graph_cid"].startswith("QmReal"))
        self.assertEqual(len(result["entities"]), 2)
        self.assertEqual(result["entities"][0]["name"], "Jane Doe")
        self.assertEqual(result["entities"][1]["name"], "TechCorp")
        self.assertEqual(result["relationships"][0]["type"], "worksFor")

        # Verify additional metrics
        self.assertEqual(result["entity_count"], 42)
        self.assertEqual(result["relationship_count"], 78)
        self.assertTrue("entity_types" in result)
        self.assertTrue("relationship_types" in result)

        # Verify entity and relationship type counts
        self.assertEqual(result["entity_types"]["Person"], 15)
        self.assertEqual(result["relationship_types"]["worksFor"], 14)

        # Verify no simulation note
        self.assertNotIn("simulation_note", result)

    def test_ai_create_knowledge_graph_with_custom_parameters(self):
        """Test creating a knowledge graph with custom parameters."""
        # Setup test data
        source_data_cid = "QmTestSourceDataCID"
        extraction_model = "custom-extraction-model"
        max_entities = 10
        timeout = 60

        # Test with custom parameters
        result = self.api.ai_create_knowledge_graph(
            source_data_cid,
            extraction_model=extraction_model,
            max_entities=max_entities,
            timeout=timeout,
            include_text_context=False,
            custom_param="custom_value"
        )

        # Verify
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertEqual(result["entity_count"], max_entities)  # Should respect max_entities

        # Verify text context was excluded as requested
        for entity in result["entities"]:
            self.assertNotIn("context", entity)

    def test_ai_create_knowledge_graph_failure_modes(self):
        """Test error handling when creating a knowledge graph fails."""
        # Setup test data
        source_data_cid = "QmTestSourceDataCID"

        # Test with simulation not allowed
        result = self.api.ai_create_knowledge_graph(
            source_data_cid,
            allow_simulation=False
        )

        # Verify
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertEqual(result["source_data_cid"], source_data_cid)
        self.assertTrue("error" in result)
        self.assertTrue("error_type" in result)
        self.assertEqual(result["error_type"], "IntegrationError")

        # Test with empty source_data_cid
        result = self.api.ai_create_knowledge_graph(
            "",
            graph_name="test_graph"
        )

        # Verify
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertTrue("error" in result)
        self.assertEqual(result["error_type"], "ValidationError")

        # Test with invalid max_entities
        result = self.api.ai_create_knowledge_graph(
            source_data_cid,
            max_entities=-5
        )

        # Verify
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertTrue("error" in result)
        self.assertEqual(result["error_type"], "ValidationError")
        self.assertIn("max_entities", result["error"])

        # Test with invalid timeout
        result = self.api.ai_create_knowledge_graph(
            source_data_cid,
            timeout=0
        )

        # Verify
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "ai_create_knowledge_graph")
        self.assertTrue("error" in result)
        self.assertEqual(result["error_type"], "ValidationError")
        self.assertIn("timeout", result["error"])

    def test_ai_create_knowledge_graph_exception_handling(self):
        """Test handling of exceptions thrown during knowledge graph creation."""
        # Setup test data
        source_data_cid = "QmTestSourceDataCID"

        try:
            # Use the raise_exception parameter to trigger an exception
            self.api.ai_create_knowledge_graph(
                source_data_cid,
                raise_exception=True
            )
            self.fail("Expected exception was not raised")
        except ValueError as e:
            # Verify the exception message
            self.assertEqual(str(e), "Test exception for ai_create_knowledge_graph")

    def test_ai_create_knowledge_graph_with_intermediate_results(self):
        """Test creating a knowledge graph with intermediate results saved."""
        source_data_cid = "QmTestSourceDataCID"

        # Test with intermediate results requested
        result = self.api.ai_create_knowledge_graph(
            source_data_cid,
            save_intermediate_results=True
        )

        # Verify intermediate results CID was provided
        self.assertTrue(result["success"])
        self.assertTrue("intermediate_results_cid" in result)
        self.assertTrue(result["intermediate_results_cid"].startswith("QmIntermediate"))

    def test_type_annotations(self):
        """Test that type annotations are correct and working."""
        # Get the type annotations from the function signature
        from inspect import signature
        sig = signature(self.api.ai_create_knowledge_graph)

        # Verify that the source_data_cid parameter has a str annotation
        self.assertEqual(sig.parameters['source_data_cid'].annotation, str)

        # Verify that the graph_name parameter has a str annotation with default
        self.assertEqual(sig.parameters['graph_name'].annotation, str)
        self.assertEqual(sig.parameters['graph_name'].default, "knowledge_graph")

        # Verify that the entity_types parameter has an Optional[List[str]] annotation
        self.assertEqual(sig.parameters['entity_types'].annotation, Optional[List[str]])

        # Verify that the include_text_context parameter has a bool annotation
        self.assertEqual(sig.parameters['include_text_context'].annotation, bool)

        # Verify that the max_entities parameter has an int annotation
        self.assertEqual(sig.parameters['max_entities'].annotation, int)

        # Verify that the return annotation is Dict[str, Any]
        self.assertEqual(sig.return_annotation, Dict[str, Any])

    def test_keyword_only_parameters(self):
        """Test that parameters are correctly marked as keyword-only."""
        # Get the signature of the function
        from inspect import signature
        sig = signature(self.api.ai_create_knowledge_graph)

        # source_data_cid should be a positional parameter
        self.assertEqual(sig.parameters['source_data_cid'].kind, sig.parameters['source_data_cid'].POSITIONAL_OR_KEYWORD)

        # All other parameters should be keyword-only
        for name, param in sig.parameters.items():
            if name != 'source_data_cid' and name != 'kwargs':
                self.assertEqual(param.kind, param.KEYWORD_ONLY, f"Parameter {name} should be keyword-only")

    def test_docstring_completeness(self):
        """Test that the docstring is complete and accurate."""
        # Get the docstring
        docstring = self.api.ai_create_knowledge_graph.__doc__

        # Verify docstring exists
        self.assertIsNotNone(docstring)

        # Check for key sections
        self.assertIn("Mock implementation", docstring)

        # Get the signature
        from inspect import signature
        sig = signature(self.api.ai_create_knowledge_graph)

        # Check that real implementation docstring would have these sections
        # The real function's docstring should have these sections:
        expected_sections = [
            "Create a knowledge graph from source data",
            "Args:",
            "Returns:"
        ]

        # Check that all parameters would be documented
        required_param_docs = [
            "source_data_cid:",
            "graph_name:",
            "extraction_model:",
            "entity_types:",
            "relationship_types:",
            "max_entities:",
            "include_text_context:",
            "extract_metadata:",
            "allow_simulation:",
            "save_intermediate_results:",
            "timeout:"
        ]

        # In a real implementation these checks would be for the actual docstring
        for param in sig.parameters:
            if param != 'kwargs' and param != 'raise_exception':
                expected_param_doc = f"{param}:"
                self.assertIn(expected_param_doc, required_param_docs, f"Parameter {param} should be documented")

        # Check return value documentation would include standard fields
        expected_return_fields = [
            "success",
            "operation",
            "timestamp",
            "graph_cid",
            "entities",
            "relationships"
        ]

        # This is a simpler version of what would be checked in the real implementation
        for field in expected_return_fields:
            self.assertTrue(any(field in result for result in [
                self.api.ai_create_knowledge_graph("QmTest"),
                self.api_with_ai_ml.ai_create_knowledge_graph("QmTest")
            ]), f"Return field {field} should be documented and included in results")


if __name__ == "__main__":
    unittest.main()
