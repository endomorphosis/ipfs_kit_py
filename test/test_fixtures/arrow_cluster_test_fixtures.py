"""
Test fixtures for PyArrow-based cluster state testing.

This module provides specialized fixtures for testing cluster state management
with PyArrow, addressing common mocking challenges and enabling more reliable tests.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq

# Create path if it doesn't exist
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)


class ArrowMockHelper:
    """Helper class for creating properly mocked PyArrow objects."""

    @staticmethod
    def create_mock_schema():
        """Create a mock PyArrow schema with proper attribute access."""
        schema = MagicMock(spec=pa.Schema)
        schema.names = ["cluster_id", "master_id", "updated_at", "nodes", "tasks", "content"]

        # Create field mocks with proper type attributes
        fields = {}
        for name in schema.names:
            field = MagicMock(spec=pa.Field)
            field.name = name
            if name in ["cluster_id", "master_id"]:
                field.type = pa.string()
            elif name == "updated_at":
                field.type = pa.timestamp("ms")
            elif name in ["nodes", "tasks", "content"]:
                # Create list type with struct value_type
                struct_type = MagicMock(spec=pa.StructType)
                struct_type.names = ["id", "role"] if name == "nodes" else ["id", "type"]
                list_type = MagicMock(spec=pa.ListType)
                list_type.value_type = struct_type
                field.type = list_type
            fields[name] = field

        # Add field accessor
        schema.__getitem__ = lambda self, key: fields[key]
        schema.field = lambda name: fields[name]

        return schema

    @staticmethod
    def create_mock_table(schema=None, num_rows=1):
        """Create a mock PyArrow table with proper column access."""
        if schema is None:
            schema = ArrowMockHelper.create_mock_schema()

        table = MagicMock(spec=pa.Table)
        table.schema = schema
        table.num_rows = num_rows
        table.column_names = schema.names

        # Add columns
        columns = {}
        for name in schema.names:
            column = MagicMock()

            # Configure column data based on name
            if name == "cluster_id":
                column.as_py.return_value = "test-cluster"
            elif name == "master_id":
                column.as_py.return_value = "test-master"
            elif name == "updated_at":
                column.as_py.return_value = 1234567890000  # timestamp in ms
            elif name == "nodes":
                column.as_py.return_value = [
                    {
                        "id": "node1",
                        "peer_id": "QmNode1",
                        "role": "master",
                        "status": "online",
                        "resources": {"cpu_count": 4, "memory_total": 16000000000}
                    },
                    {
                        "id": "node2",
                        "peer_id": "QmNode2",
                        "role": "worker",
                        "status": "online",
                        "resources": {"cpu_count": 8, "memory_total": 32000000000}
                    }
                ]
            elif name == "tasks":
                column.as_py.return_value = [
                    {
                        "id": "task1",
                        "type": "model_training",
                        "status": "pending",
                        "priority": 5
                    },
                    {
                        "id": "task2",
                        "type": "embedding_generation",
                        "status": "running",
                        "priority": 3,
                        "assigned_to": "node2"
                    }
                ]
            elif name == "content":
                column.as_py.return_value = [
                    {
                        "cid": "QmContent1",
                        "size": 1024,
                        "providers": ["node1"]
                    },
                    {
                        "cid": "QmContent2",
                        "size": 2048,
                        "providers": ["node1", "node2"]
                    }
                ]

            columns[name] = column

        # Define column accessor
        table.column = lambda name: columns[name]

        return table

    @staticmethod
    def create_mock_array_function():
        """Create a mock function that simulates pa.array for testing."""
        def mock_array(data, type=None):
            """Simulate PyArrow array creation."""
            mock_arr = MagicMock(spec=pa.Array)
            mock_arr._data = data  # Store data for inspection
            mock_arr._type = type  # Store type for inspection
            return mock_arr
        return mock_array

    @staticmethod
    def create_mock_table_function():
        """Create a mock function that simulates pa.Table.from_arrays."""
        def mock_from_arrays(arrays, schema=None):
            """Simulate PyArrow table creation from arrays."""
            mock_tbl = MagicMock(spec=pa.Table)
            mock_tbl._arrays = arrays  # Store arrays for inspection
            mock_tbl._schema = schema  # Store schema for inspection
            mock_tbl.schema = schema
            return mock_tbl
        return mock_from_arrays


class ArrowClusterStateFixture(unittest.TestCase):
    """Base test fixture for testing Arrow-based cluster state."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for state files
        self.test_dir = tempfile.mkdtemp()

        # Define common test parameters
        self.cluster_id = "test-cluster"
        self.node_id = "test-node"

        # Create patchers for PyArrow functions
        self.pa_array_patcher = patch("pyarrow.array", ArrowMockHelper.create_mock_array_function())
        self.pa_table_from_arrays_patcher = patch(
            "pyarrow.Table.from_arrays", ArrowMockHelper.create_mock_table_function()
        )

        # Start patchers
        self.mock_pa_array = self.pa_array_patcher.start()
        self.mock_pa_table_from_arrays = self.pa_table_from_arrays_patcher.start()

        # Create a mock schema
        self.mock_schema = ArrowMockHelper.create_mock_schema()

        # Create a mock table
        self.mock_table = ArrowMockHelper.create_mock_table(self.mock_schema)

        # Mock plasma store if needed
        self.plasma_mock = None
        if hasattr(pa, "plasma"):
            self.plasma_patcher = patch("pyarrow.plasma")
            self.plasma_mock = self.plasma_patcher.start()
            self.plasma_mock.connect.return_value = MagicMock()
            self.plasma_mock.ObjectID.return_value = MagicMock()

        # Import actual module under test (delayed until after patchers are in place)
        from ipfs_kit_py.cluster_state import ArrowClusterState

        # Create the state manager
        self.state = ArrowClusterState(
            cluster_id=self.cluster_id,
            node_id=self.node_id,
            state_path=self.test_dir,
            memory_size=10000000,  # 10MB
            enable_persistence=True,
            plasma_socket="mock_socket"  # Mock socket path
        )

        # Replace the state's schema with our mock schema
        self.state.schema = self.mock_schema

        # Replace state's table with our mock table (if needed for tests)
        # Uncomment the following line if your tests need a pre-populated table
        # self.state.state_table = self.mock_table

    def tearDown(self):
        """Clean up after tests."""
        # Stop patchers
        self.pa_array_patcher.stop()
        self.pa_table_from_arrays_patcher.stop()

        if self.plasma_mock is not None:
            self.plasma_patcher.stop()

        # Remove the temporary directory
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)


class NodeFixture:
    """Factory for creating test node data."""

    @staticmethod
    def create_worker_node(node_id="worker1", online=True, resources=None):
        """Create a worker node test fixture."""
        if resources is None:
            resources = {
                "cpu_count": 8,
                "cpu_usage": 0.2,
                "memory_total": 16 * 1024 * 1024 * 1024,  # 16GB
                "memory_available": 8 * 1024 * 1024 * 1024,  # 8GB
                "disk_total": 500 * 1024 * 1024 * 1024,  # 500GB
                "disk_free": 200 * 1024 * 1024 * 1024,  # 200GB
                "gpu_count": 2,
                "gpu_available": True
            }

        return {
            "id": node_id,
            "peer_id": f"Qm{node_id}PeerId",
            "role": "worker",
            "status": "online" if online else "offline",
            "address": f"192.168.1.{int(node_id[-1])+100}",
            "last_seen": int(os.path.getmtime(__file__) * 1000),  # Current timestamp in ms
            "resources": resources,
            "tasks": [],
            "capabilities": ["model_training", "embedding_generation"]
        }

    @staticmethod
    def create_master_node(node_id="master", online=True):
        """Create a master node test fixture."""
        resources = {
            "cpu_count": 16,
            "cpu_usage": 0.1,
            "memory_total": 64 * 1024 * 1024 * 1024,  # 64GB
            "memory_available": 32 * 1024 * 1024 * 1024,  # 32GB
            "disk_total": 2000 * 1024 * 1024 * 1024,  # 2TB
            "disk_free": 1000 * 1024 * 1024 * 1024,  # 1TB
            "gpu_count": 4,
            "gpu_available": True
        }

        node = NodeFixture.create_worker_node(node_id, online, resources)
        node["role"] = "master"
        node["capabilities"].extend(["cluster_management", "data_orchestration"])
        return node


class TaskFixture:
    """Factory for creating test task data."""

    @staticmethod
    def create_training_task(task_id=None, status="pending", priority=5, assigned_to=None):
        """Create a model training task fixture."""
        import uuid
        if task_id is None:
            task_id = f"task-{uuid.uuid4()}"

        return {
            "id": task_id,
            "type": "model_training",
            "status": status,
            "priority": priority,
            "created_at": int(os.path.getmtime(__file__) * 1000),  # Current timestamp in ms
            "updated_at": int(os.path.getmtime(__file__) * 1000),  # Current timestamp in ms
            "assigned_to": assigned_to or "",
            "parameters": {
                "model": "resnet50",
                "epochs": "10",
                "batch_size": "32"
            },
            "result_cid": ""
        }

    @staticmethod
    def create_embedding_task(task_id=None, status="pending", assigned_to=None):
        """Create an embedding generation task fixture."""
        import uuid
        if task_id is None:
            task_id = f"task-{uuid.uuid4()}"

        return {
            "id": task_id,
            "type": "embedding_generation",
            "status": status,
            "priority": 3,
            "created_at": int(os.path.getmtime(__file__) * 1000),  # Current timestamp in ms
            "updated_at": int(os.path.getmtime(__file__) * 1000),  # Current timestamp in ms
            "assigned_to": assigned_to or "",
            "parameters": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "batch_size": "64"
            },
            "result_cid": ""
        }


# Example usage of fixtures:
if __name__ == "__main__":
    # Create a node fixture
    worker = NodeFixture.create_worker_node()
    print(f"Worker node: {worker['id']}, Role: {worker['role']}")

    # Create a task fixture
    task = TaskFixture.create_training_task()
    print(f"Task: {task['id']}, Type: {task['type']}")

    # Demonstrate helper class
    schema = ArrowMockHelper.create_mock_schema()
    print(f"Schema fields: {schema.names}")

    table = ArrowMockHelper.create_mock_table()
    print(f"Table rows: {table.num_rows}")
    print(f"Node count: {len(table.column('nodes').as_py())}")
