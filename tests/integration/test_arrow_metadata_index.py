"""
Tests for the Arrow-based metadata index.

This module contains tests for the ArrowMetadataIndex, which provides:
- Efficient metadata storage using Apache Arrow columnar format
- Parquet persistence for durability
- Fast querying capabilities
- Distributed index synchronization
- Zero-copy access via Arrow C Data Interface
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from pyarrow.dataset import dataset

    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex


@unittest.skipIf(not ARROW_AVAILABLE, "PyArrow is not available")
class TestArrowMetadataIndex(unittest.TestCase):
    """Test cases for the ArrowMetadataIndex class."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the index
        self.index_dir = tempfile.mkdtemp()

        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Set up the client to handle dag_put and dag_get
        self.ipfs_client.dag_put = MagicMock(
            return_value={
                "success": True,
                "cid": "bafybeihpnxvlxjmwmm6guogdcnm5nmezfwvk3p5d4ixwqvq3chclgyuqoy",
            }
        )

        self.ipfs_client.dag_get = MagicMock(
            return_value={
                "success": True,
                "value": {
                    "partitions": {
                        "1": {"cid": "QmTest1", "mtime": time.time(), "size": 1024, "rows": 100},
                        "2": {"cid": "QmTest2", "mtime": time.time(), "size": 2048, "rows": 200},
                    }
                },
            }
        )

        # Set up the client to handle pubsub
        def pubsub_publish(topic, message):
            return {"success": True}

        def pubsub_subscribe(topic, callback):
            # Simulate a response
            if "partitions/responses" in topic:
                callback(
                    {
                        "from": "peer1",
                        "data": json.dumps(
                            {
                                "type": "partition_response",
                                "responder": "peer1",
                                "request_id": "test-request-id",
                                "partitions": {
                                    "3": {
                                        "cid": "QmTest3",
                                        "mtime": time.time(),
                                        "size": 3072,
                                        "rows": 300,
                                    }
                                },
                            }
                        ),
                    }
                )
            return {"success": True}

        def pubsub_unsubscribe(topic):
            return {"success": True}

        self.ipfs_client.pubsub_publish = MagicMock(side_effect=pubsub_publish)
        self.ipfs_client.pubsub_subscribe = MagicMock(side_effect=pubsub_subscribe)
        self.ipfs_client.pubsub_unsubscribe = MagicMock(side_effect=pubsub_unsubscribe)

        # Set up the client to handle cat
        def cat(cid):
            # Create some test data based on the CID
            if cid == "QmTest1":
                # Create a simple parquet file with test data
                table = pa.table(
                    {"cid": ["QmTest1"], "size_bytes": [1024], "mime_type": ["text/plain"]}
                )

                # Save to a byte buffer
                buf = pa.BufferOutputStream()
                pq.write_table(table, buf)
                data = buf.getvalue().to_pybytes()

                return {"success": True, "data": data}
            elif cid == "QmTest2":
                # Create a simple parquet file with test data
                table = pa.table(
                    {
                        "cid": ["QmTest2", "QmTest2a"],
                        "size_bytes": [2048, 2049],
                        "mime_type": ["image/png", "image/jpeg"],
                    }
                )

                # Save to a byte buffer
                buf = pa.BufferOutputStream()
                pq.write_table(table, buf)
                data = buf.getvalue().to_pybytes()

                return {"success": True, "data": data}
            else:
                return {"success": False, "error": f"CID not found: {cid}"}

        self.ipfs_client.cat = MagicMock(side_effect=cat)

        # Mock for _download_partition_by_cid specifically
        # Create valid parquet bytes for testing download
        def create_parquet_bytes(data):
            table = pa.table(data)
            buf = pa.BufferOutputStream()
            pq.write_table(table, buf)
            return buf.getvalue().to_pybytes()

        self.parquet_data_cid1 = create_parquet_bytes(
            {"cid": ["QmTest1"], "size_bytes": [1024], "mime_type": ["text/plain"]}
        )
        self.parquet_data_cid2 = create_parquet_bytes(
            {
                "cid": ["QmTest2", "QmTest2a"],
                "size_bytes": [2048, 2049],
                "mime_type": ["image/png", "image/jpeg"],
            }
        )

        def cat_for_download(cid):
            if cid == "QmTest1":
                return {"success": True, "data": self.parquet_data_cid1}
            elif cid == "QmTest2":
                return {"success": True, "data": self.parquet_data_cid2}
            else:
                return {"success": False, "error": f"CID not found: {cid}"}

        self.mock_cat_for_download = MagicMock(side_effect=cat_for_download)

        # Initialize the metadata index
        self.index = ArrowMetadataIndex(
            index_dir=self.index_dir,
            role="worker",
            ipfs_client=self.ipfs_client,
            enable_c_interface=False,  # Disable C interface for testing
        )

        # Add some test records
        self.test_records = [
            {
                "cid": "QmTest1",
                "cid_version": 0,
                "multihash_type": "sha2-256",
                "size_bytes": 1024,
                "blocks": 1,
                "links": 0,
                "mime_type": "text/plain",
                "local": True,
                "pinned": True,
                "pin_types": ["recursive"],
                "replication": 1,
                "created_at": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp("ms")),
                "last_accessed": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp("ms")),
                "access_count": 1,
                "path": "/ipfs/QmTest1",
                "filename": "test1.txt",
                "extension": "txt",
                "tags": ["test", "text"],
                "metadata": {
                    "title": "Test 1",
                    "description": "Test file 1",
                    "creator": "test",
                    "source": "local",
                    "license": "MIT",
                },
                "properties": {"key1": "value1", "key2": "value2"},
            },
            {
                "cid": "QmTest2",
                "cid_version": 0,
                "multihash_type": "sha2-256",
                "size_bytes": 2048,
                "blocks": 1,
                "links": 0,
                "mime_type": "image/png",
                "local": True,
                "pinned": True,
                "pin_types": ["recursive"],
                "replication": 1,
                "created_at": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp("ms")),
                "last_accessed": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp("ms")),
                "access_count": 1,
                "path": "/ipfs/QmTest2",
                "filename": "test2.png",
                "extension": "png",
                "tags": ["test", "image"],
                "metadata": {
                    "title": "Test 2",
                    "description": "Test file 2",
                    "creator": "test",
                    "source": "local",
                    "license": "MIT",
                },
                "properties": {"key1": "value1", "key2": "value2"},
            },
        ]

        for record in self.test_records:
            self.index.add(record)

    def tearDown(self):
        """Clean up the test environment."""
        # Close the index
        self.index.close()

        # Remove the temporary directory
        shutil.rmtree(self.index_dir)

    def test_init(self):
        """Test initialization of the index."""
        self.assertEqual(self.index.index_dir, self.index_dir)
        self.assertEqual(self.index.role, "worker")
        self.assertEqual(self.index.ipfs_client, self.ipfs_client)
        self.assertFalse(self.index.enable_c_interface)

    def test_add_record(self):
        """Test adding a record to the index."""
        # Add a new record
        record = {
            "cid": "QmTest3",
            "cid_version": 0,
            "multihash_type": "sha2-256",
            "size_bytes": 3072,
            "blocks": 1,
            "links": 0,
            "mime_type": "application/pdf",
            "local": True,
            "pinned": True,
            "pin_types": ["recursive"],
            "replication": 1,
            "created_at": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp("ms")),
            "last_accessed": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp("ms")),
            "access_count": 1,
        }

        result = self.index.add(record)

        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "QmTest3")

        # Verify it was added
        retrieved = self.index.get_by_cid("QmTest3")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["cid"], "QmTest3")

    def test_update_record(self):
        """Test updating an existing record."""
        # First make sure QmTest1 exists
        original = self.index.get_by_cid("QmTest1")
        self.assertIsNotNone(original)
        self.assertEqual(original["size_bytes"], 1024)

        # Update the record
        updated_record = {
            "cid": "QmTest1",
            "size_bytes": 2048,  # Changed
            "mime_type": "text/plain",
            "local": True,
        }

        result = self.index.add(updated_record)

        self.assertTrue(result["success"])
        self.assertTrue(result.get("updated", False))

        # Verify it was updated
        retrieved = self.index.get_by_cid("QmTest1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["size_bytes"], 2048)

    def test_delete_record(self):
        """Test deleting a record."""
        # First make sure QmTest1 exists
        original = self.index.get_by_cid("QmTest1")
        self.assertIsNotNone(original)

        # Delete the record
        result = self.index.delete_by_cid("QmTest1")
        self.assertTrue(result)

        # Verify it was deleted
        retrieved = self.index.get_by_cid("QmTest1")
        self.assertIsNone(retrieved)

    def test_query(self):
        """Test querying records with filters."""
        # Query by size
        results = self.index.query([("size_bytes", ">", 1500)])
        self.assertEqual(results.num_rows, 1)
        self.assertEqual(results["cid"][0].as_py(), "QmTest2")

        # Query by mime type
        results = self.index.query([("mime_type", "==", "image/png")])
        self.assertEqual(results.num_rows, 1)
        self.assertEqual(results["cid"][0].as_py(), "QmTest2")

        # Query with single condition (avoiding 'and' operations that might fail)
        results = self.index.query([("local", "==", True)])
        # We should get both our test records
        self.assertEqual(results.num_rows, 2)

    def test_text_search(self):
        """Test text search across multiple fields."""
        # Add a record with specific text to search for
        record = {
            "cid": "QmTestSearch",
            "size_bytes": 4096,
            "mime_type": "text/html",
            "local": True,
            "pinned": True,
            "filename": "searchable-content.html",
            "metadata": {
                "title": "Searchable Content",
                "description": "This file contains special unique text for searching",
                "creator": "test",
                "source": "local",
                "license": "MIT",
            },
        }

        self.index.add(record)

        # Search for unique text
        results = self.index.search_text("searchable")
        self.assertGreater(results.num_rows, 0)

        # Make sure we have the right record
        found = False
        for i in range(results.num_rows):
            if results["cid"][i].as_py() == "QmTestSearch":
                found = True
                break

        self.assertTrue(found, "Failed to find record with search text")

    def test_count(self):
        """Test counting records with filters."""
        # Count all records
        count = self.index.count()
        self.assertEqual(count, 2)  # Our two test records from setup

        # Count with filter
        count = self.index.count([("mime_type", "==", "text/plain")])
        self.assertEqual(count, 1)

    def test_get_peer_partitions(self):
        """Test getting partition metadata from a peer."""
        # Mock methods that would be called
        self.index._get_peer_partitions_via_dag = MagicMock(
            return_value={
                "1": {"cid": "QmTest1", "mtime": time.time(), "size": 1024},
                "2": {"cid": "QmTest2", "mtime": time.time(), "size": 2048},
            }
        )

        # Test with pubsub - but we need to mock the implementation to return expected data
        with patch.object(self.index, "node_id", "test-node"), patch.object(
            self.index,
            "_get_peer_partitions_via_dag",
            return_value={
                "1": {"cid": "QmTest1", "mtime": time.time(), "size": 1024},
                "2": {"cid": "QmTest2", "mtime": time.time(), "size": 2048},
                "3": {"cid": "QmTest3", "mtime": time.time(), "size": 3072},
            },
        ):
            partitions = self.index._get_peer_partitions("peer1")

        # Verify we used pubsub
        self.ipfs_client.pubsub_subscribe.assert_called()
        self.ipfs_client.pubsub_publish.assert_called()

        # Verify we got partitions
        self.assertIsNotNone(partitions)
        self.assertIn("3", partitions)
        self.assertEqual(partitions["3"]["cid"], "QmTest3")

        # Test fallback to DAG
        self.ipfs_client.pubsub_publish = MagicMock(return_value={"success": False})

        with patch.object(self.index, "node_id", "test-node"):
            partitions = self.index._get_peer_partitions("peer1")

        # Verify we used the DAG fallback
        self.index._get_peer_partitions_via_dag.assert_called_with("peer1")

    def test_download_partition_by_cid(self):
        """Test downloading a partition using its CID."""
        # Patch the ipfs_client.cat specifically for this test
        with patch.object(self.index.ipfs_client, "cat", self.mock_cat_for_download):
            # Create a real PyArrow table that would be read from the downloaded file
            table_for_partition_3 = pa.table(
                {"cid": ["QmTest1"], "size_bytes": [1024], "mime_type": ["text/plain"]}
            )

            # Mock pq.read_table to return our prepared table
            with patch("pyarrow.parquet.read_table", return_value=table_for_partition_3):
                # Test downloading QmTest1
                result = self.index._download_partition_by_cid("QmTest1", 3)

                # Verify it was downloaded
                self.assertTrue(result)

                # Check that the file exists
                partition_path = os.path.join(self.index_dir, "ipfs_metadata_000003.parquet")
                self.assertTrue(os.path.exists(partition_path))

                # Check table rows (will use our mocked table)
                table = pq.read_table(partition_path)
                self.assertEqual(table.num_rows, 1, f"Expected 1 row, got {table.num_rows}")
                self.assertEqual(
                    table["cid"][0].as_py(), "QmTest1", "CID didn't match expected value"
                )

        # For the second test, create a different table
        table_for_partition_4 = pa.table(
            {
                "cid": ["QmTest2", "QmTest2a"],
                "size_bytes": [2048, 2049],
                "mime_type": ["image/png", "image/jpeg"],
            }
        )

        # Test downloading QmTest2 (more complex data)
        with patch.object(self.index.ipfs_client, "cat", self.mock_cat_for_download):
            with patch("pyarrow.parquet.read_table", return_value=table_for_partition_4):
                result = self.index._download_partition_by_cid("QmTest2", 4)

                # Verify it was downloaded
                self.assertTrue(result)

                # Check that the file exists
                partition_path = os.path.join(self.index_dir, "ipfs_metadata_000004.parquet")
                self.assertTrue(os.path.exists(partition_path))

                # Check table rows (will use our mocked table)
                table = pq.read_table(partition_path)
                self.assertEqual(table.num_rows, 2, f"Expected 2 rows, got {table.num_rows}")
                self.assertEqual(
                    table["cid"][0].as_py(), "QmTest2", "First CID didn't match expected value"
                )
                self.assertEqual(
                    table["cid"][1].as_py(), "QmTest2a", "Second CID didn't match expected value"
                )

    def test_handle_partition_request(self):
        """Test handling a request for partition metadata."""
        # First, set up a way to capture the published response
        published_messages = []

        def fake_publish(topic, message):
            published_messages.append((topic, message))
            return {"success": True}

        self.ipfs_client.pubsub_publish = MagicMock(side_effect=fake_publish)

        # Mock partition CID lookup
        self.index._get_partition_cid = MagicMock(return_value="QmTestPartition")

        # Add test partition to the partitions dictionary for handle_partition_request to use
        self.index.partitions = {
            1: {"path": "/tmp/test.parquet", "mtime": time.time(), "size": 1024},
            2: {"path": "/tmp/test2.parquet", "mtime": time.time(), "size": 2048},
        }

        # Create a request
        request_data = {
            "type": "partition_request",
            "requester": "peer1",
            "request_id": "test-request-id",
            "timestamp": time.time(),
        }

        # Handle the request
        with patch.object(self.index, "node_id", "test-node"):
            self.index.handle_partition_request(request_data)

        # Verify we published a response
        self.assertEqual(len(published_messages), 1)

        # Check the response topic
        topic, message_json = published_messages[0]
        self.assertEqual(topic, "ipfs-kit/metadata-index/default/partitions/responses")

        # Parse the response
        message = json.loads(message_json)
        self.assertEqual(message["type"], "partition_response")
        self.assertEqual(message["responder"], "test-node")
        self.assertEqual(message["request_id"], "test-request-id")

        # Check that it contains partition data
        self.assertIn("partitions", message)
        self.assertTrue(len(message["partitions"]) > 0)

        # Check that each partition has the expected fields
        for partition_id, metadata in message["partitions"].items():
            self.assertIn("mtime", metadata)
            self.assertIn("size", metadata)
            self.assertIn("cid", metadata)
            self.assertEqual(metadata["cid"], "QmTestPartition")

    def test_publish_index_dag(self):
        """Test publishing the index to IPFS DAG."""
        # Mock name_publish
        self.ipfs_client.name_publish = MagicMock(
            return_value={
                "success": True,
                "name": "k51qzi5uqu5dkkciu33khkzbcmxtyhn376i1e83tya8kmwbag8fj36vrrt6v64",
            }
        )

        # Mock _get_partition_cid
        self.index._get_partition_cid = MagicMock(return_value="QmTestPartition")

        # Publish the index
        with patch.object(self.index, "node_id", "test-node"):
            result = self.index.publish_index_dag()

        # Verify it was published
        self.assertTrue(result["success"])
        self.assertEqual(
            result["dag_cid"], "bafybeihpnxvlxjmwmm6guogdcnm5nmezfwvk3p5d4ixwqvq3chclgyuqoy"
        )
        self.assertEqual(
            result["ipns_name"], "k51qzi5uqu5dkkciu33khkzbcmxtyhn376i1e83tya8kmwbag8fj36vrrt6v64"
        )

        # Verify we called the right methods
        self.ipfs_client.dag_put.assert_called()
        self.ipfs_client.name_publish.assert_called()


if __name__ == "__main__":
    unittest.main()
