#!/usr/bin/env python3
"""
Test suite for Advanced IPFS Operations

This module tests the functionality of the Advanced IPFS Operations
features implemented as part of the MCP Roadmap Phase 1.

It tests:
- DAG operations (get, put, resolve, stat)
- Object manipulation (new, patch, links)
- IPNS functionality with key management
- Network operations (swarm, bootstrap)
"""

import os
import sys
import json
import time
import pytest
import tempfile
import random
import string
from unittest import mock

# Import the modules to test
from ipfs_kit_py.mcp.extensions.ipfs_advanced import get_instance as get_ipfs_advanced
from ipfs_kit_py.ipfs_backend import get_instance as get_ipfs_backend


class MockIPFSResponse:
    """Mock response for IPFS operations."""
    
    @staticmethod
    def success(data=None, **kwargs):
        """Create a successful response."""
        response = {"success": True}
        if data is not None:
            response["data"] = data
        return {**response, **kwargs}
    
    @staticmethod
    def error(error="Mock error", error_type="MockError"):
        """Create an error response."""
        return {
            "success": False,
            "error": error,
            "error_type": error_type
        }


@pytest.fixture
def mock_ipfs():
    """Create a mock IPFS backend."""
    # Create mock IPFS responses
    with mock.patch('ipfs_kit_py.ipfs_backend.IPFSStorageBackend') as mock_backend:
        # Set up mock responses
        instance = mock_backend.return_value
        instance.ipfs = mock.MagicMock()
        
        # Mock DAG operations
        instance.ipfs.ipfs_dag_get = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                data={"value": "test data"},
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            )
        )
        instance.ipfs.ipfs_dag_put = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            )
        )
        instance.ipfs.ipfs_dag_resolve = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                remainder_path=""
            )
        )
        instance.ipfs.ipfs_dag_stat = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                size=123,
                num_blocks=1
            )
        )
        
        # Mock Object operations
        instance.ipfs.ipfs_object_new = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n"
            )
        )
        instance.ipfs.ipfs_object_get = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                data="test object data",
                links=[{"Name": "link1", "Hash": "QmXYZ", "Size": 100}]
            )
        )
        instance.ipfs.ipfs_object_put = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n"
            )
        )
        instance.ipfs.ipfs_object_stat = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                stats={
                    "NumLinks": 1,
                    "BlockSize": 123,
                    "LinksSize": 50,
                    "DataSize": 73,
                    "CumulativeSize": 123
                }
            )
        )
        instance.ipfs.ipfs_object_links = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                links=[{"Name": "link1", "Hash": "QmXYZ", "Size": 100}]
            )
        )
        instance.ipfs.ipfs_object_patch_add_link = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n"
            )
        )
        instance.ipfs.ipfs_object_patch_rm_link = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n"
            )
        )
        instance.ipfs.ipfs_object_patch_set_data = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n"
            )
        )
        instance.ipfs.ipfs_object_patch_append_data = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                cid="QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n"
            )
        )
        
        # Mock IPNS/Key operations
        instance.ipfs.ipfs_name_publish = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                name="/ipns/k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx",
                value="/ipfs/bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            )
        )
        instance.ipfs.ipfs_name_resolve = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                path="/ipfs/bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            )
        )
        instance.ipfs.ipfs_key_gen = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                name="test-key",
                id="k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx"
            )
        )
        instance.ipfs.ipfs_key_list = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                keys=[
                    {"Name": "self", "Id": "k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx"},
                    {"Name": "test-key", "Id": "k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpoabc"}
                ]
            )
        )
        instance.ipfs.ipfs_key_rename = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                was="test-key",
                now="new-key-name",
                id="k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx"
            )
        )
        instance.ipfs.ipfs_key_rm = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                name="test-key",
                id="k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx"
            )
        )
        
        # Mock Swarm/Network operations
        instance.ipfs.ipfs_swarm_peers = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                peers=[
                    "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
                    "/ip4/104.131.131.83/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuK"
                ]
            )
        )
        instance.ipfs.ipfs_swarm_connect = mock.MagicMock(
            return_value=MockIPFSResponse.success()
        )
        instance.ipfs.ipfs_swarm_disconnect = mock.MagicMock(
            return_value=MockIPFSResponse.success()
        )
        instance.ipfs.ipfs_bootstrap_list = mock.MagicMock(
            return_value=MockIPFSResponse.success(
                peers=[
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa"
                ]
            )
        )
        instance.ipfs.ipfs_bootstrap_add = mock.MagicMock(
            return_value=MockIPFSResponse.success()
        )
        instance.ipfs.ipfs_bootstrap_rm = mock.MagicMock(
            return_value=MockIPFSResponse.success()
        )
        
        # Test helper method - allows changing mock responses during tests
        def set_mock_response(method_name, response):
            method = getattr(instance.ipfs, method_name, None)
            if method:
                method.return_value = response
        
        instance.set_mock_response = set_mock_response
        
        yield instance


@pytest.fixture
def ipfs_advanced(mock_ipfs):
    """Create an instance of the advanced IPFS operations with a mock backend."""
    # Replace the global backend instance with our mock
    with mock.patch('ipfs_kit_py.ipfs_backend._instance', mock_ipfs):
        # Get a new instance of the advanced operations
        advanced_ops = get_ipfs_advanced()
        advanced_ops.backend = mock_ipfs
        advanced_ops.ipfs = mock_ipfs.ipfs
        yield advanced_ops


# --- Test DAG Operations ---

def test_dag_get(ipfs_advanced):
    """Test DAG get operation."""
    # Test successful DAG get
    result = ipfs_advanced.dag_get("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
    assert result["success"] is True
    assert "data" in result
    assert result["data"]["value"] == "test data"
    
    # Test with path
    result = ipfs_advanced.dag_get(
        "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        path="/value"
    )
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_dag_get",
        MockIPFSResponse.error("DAG node not found")
    )
    result = ipfs_advanced.dag_get("invalid-cid")
    assert result["success"] is False
    assert "error" in result
    assert "DAG node not found" in result["error"]


def test_dag_put(ipfs_advanced):
    """Test DAG put operation."""
    # Test with JSON data
    data = {"name": "test", "value": 123}
    result = ipfs_advanced.dag_put(data)
    assert result["success"] is True
    assert "cid" in result
    
    # Test with string data
    result = ipfs_advanced.dag_put(json.dumps(data))
    assert result["success"] is True
    
    # Test with different codec
    result = ipfs_advanced.dag_put(data, store_codec="dag-json")
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_dag_put",
        MockIPFSResponse.error("Invalid data format")
    )
    result = ipfs_advanced.dag_put(data)
    assert result["success"] is False
    assert "error" in result


def test_dag_resolve(ipfs_advanced):
    """Test DAG resolve operation."""
    # Test successful resolve
    result = ipfs_advanced.dag_resolve("/ipfs/bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
    assert result["success"] is True
    assert "cid" in result
    assert "remainder_path" in result
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_dag_resolve",
        MockIPFSResponse.error("Path not found")
    )
    result = ipfs_advanced.dag_resolve("/ipfs/invalid-path")
    assert result["success"] is False
    assert "error" in result


def test_dag_stat(ipfs_advanced):
    """Test DAG stat operation."""
    # Test successful stat
    result = ipfs_advanced.dag_stat("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
    assert result["success"] is True
    assert "size" in result
    assert "num_blocks" in result
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_dag_stat",
        MockIPFSResponse.error("CID not found")
    )
    result = ipfs_advanced.dag_stat("invalid-cid")
    assert result["success"] is False
    assert "error" in result


# --- Test Object Operations ---

def test_object_new(ipfs_advanced):
    """Test object new operation."""
    # Test with default template
    result = ipfs_advanced.object_new()
    assert result["success"] is True
    assert "cid" in result
    
    # Test with specific template
    result = ipfs_advanced.object_new("unixfs-dir")
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_object_new",
        MockIPFSResponse.error("Invalid template")
    )
    result = ipfs_advanced.object_new("invalid-template")
    assert result["success"] is False
    assert "error" in result


def test_object_get(ipfs_advanced):
    """Test object get operation."""
    # Test successful get
    result = ipfs_advanced.object_get("QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n")
    assert result["success"] is True
    assert "data" in result
    assert "links" in result
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_object_get",
        MockIPFSResponse.error("Object not found")
    )
    result = ipfs_advanced.object_get("invalid-cid")
    assert result["success"] is False
    assert "error" in result


def test_object_put(ipfs_advanced):
    """Test object put operation."""
    # Test with JSON data
    data = {"Data": "test data", "Links": []}
    result = ipfs_advanced.object_put(data)
    assert result["success"] is True
    assert "cid" in result
    
    # Test with string data
    result = ipfs_advanced.object_put(json.dumps(data))
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_object_put",
        MockIPFSResponse.error("Invalid object format")
    )
    result = ipfs_advanced.object_put(data)
    assert result["success"] is False
    assert "error" in result


def test_object_patch_operations(ipfs_advanced):
    """Test object patch operations."""
    # Test add link
    result = ipfs_advanced.object_patch_add_link(
        "QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n",
        "test-link",
        "QmXYZ"
    )
    assert result["success"] is True
    assert "cid" in result
    
    # Test remove link
    result = ipfs_advanced.object_patch_rm_link(
        "QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n",
        "test-link"
    )
    assert result["success"] is True
    
    # Test set data
    result = ipfs_advanced.object_patch_set_data(
        "QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n",
        "new data"
    )
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_object_patch_add_link",
        MockIPFSResponse.error("Object not found")
    )
    result = ipfs_advanced.object_patch_add_link(
        "invalid-cid",
        "test-link",
        "QmXYZ"
    )
    assert result["success"] is False
    assert "error" in result


# --- Test IPNS/Key Operations ---

def test_name_publish(ipfs_advanced):
    """Test name publish operation."""
    # Test successful publish
    result = ipfs_advanced.name_publish(
        "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        key="self",
        lifetime="24h"
    )
    assert result["success"] is True
    assert "name" in result
    assert "value" in result
    
    # Test with custom key
    result = ipfs_advanced.name_publish(
        "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        key="test-key"
    )
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_name_publish",
        MockIPFSResponse.error("Key not found")
    )
    result = ipfs_advanced.name_publish(
        "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        key="invalid-key"
    )
    assert result["success"] is False
    assert "error" in result


def test_name_resolve(ipfs_advanced):
    """Test name resolve operation."""
    # Test successful resolve
    result = ipfs_advanced.name_resolve(
        "/ipns/k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx"
    )
    assert result["success"] is True
    assert "path" in result
    
    # Test with recursive option
    result = ipfs_advanced.name_resolve(
        "/ipns/k51qzi5uqu5djdczd6zprfvsg8ix52u1w32ylgr716q7rewumwhnz6bpmdunxx",
        recursive=True
    )
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_name_resolve",
        MockIPFSResponse.error("Name not found")
    )
    result = ipfs_advanced.name_resolve("invalid-name")
    assert result["success"] is False
    assert "error" in result


def test_key_operations(ipfs_advanced):
    """Test key operations."""
    # Test key generation
    result = ipfs_advanced.key_gen("test-key")
    assert result["success"] is True
    assert "name" in result
    assert "id" in result
    
    # Test key list
    result = ipfs_advanced.key_list()
    assert result["success"] is True
    assert "keys" in result
    assert len(result["keys"]) == 2
    
    # Test key rename
    result = ipfs_advanced.key_rename("test-key", "new-key-name")
    assert result["success"] is True
    assert result["was"] == "test-key"
    assert result["now"] == "new-key-name"
    
    # Test key removal
    result = ipfs_advanced.key_rm("test-key")
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_key_rm",
        MockIPFSResponse.error("Key not found")
    )
    result = ipfs_advanced.key_rm("invalid-key")
    assert result["success"] is False
    assert "error" in result


# --- Test Swarm/Network Operations ---

def test_swarm_operations(ipfs_advanced):
    """Test swarm operations."""
    # Test swarm peers
    result = ipfs_advanced.swarm_peers()
    assert result["success"] is True
    assert "peers" in result
    assert len(result["peers"]) == 2
    
    # Test swarm connect
    result = ipfs_advanced.swarm_connect(
        "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
    )
    assert result["success"] is True
    
    # Test swarm disconnect
    result = ipfs_advanced.swarm_disconnect(
        "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
    )
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_swarm_connect",
        MockIPFSResponse.error("Connection failed")
    )
    result = ipfs_advanced.swarm_connect("invalid-address")
    assert result["success"] is False
    assert "error" in result


def test_bootstrap_operations(ipfs_advanced):
    """Test bootstrap operations."""
    # Test bootstrap list
    result = ipfs_advanced.bootstrap_list()
    assert result["success"] is True
    assert "peers" in result
    assert len(result["peers"]) == 2
    
    # Test bootstrap add
    result = ipfs_advanced.bootstrap_add(
        "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN"
    )
    assert result["success"] is True
    
    # Test bootstrap remove
    result = ipfs_advanced.bootstrap_rm(
        "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN"
    )
    assert result["success"] is True
    
    # Test error scenario
    ipfs_advanced.backend.set_mock_response(
        "ipfs_bootstrap_add",
        MockIPFSResponse.error("Invalid bootstrap address")
    )
    result = ipfs_advanced.bootstrap_add("invalid-address")
    assert result["success"] is False
    assert "error" in result


# --- Test Statistics ---

def test_get_stats(ipfs_advanced):
    """Test statistics retrieval."""
    # Perform some operations to generate stats
    ipfs_advanced.dag_get("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
    ipfs_advanced.object_new()
    ipfs_advanced.swarm_peers()
    
    # Get statistics
    result = ipfs_advanced.get_stats()
    assert result["success"] is True
    assert "stats" in result
    
    # Check that our operations are recorded
    stats = result["stats"]
    assert "dag_get" in stats
    assert stats["dag_get"]["count"] > 0
    assert "object_new" in stats
    assert stats["object_new"]["count"] > 0
    assert "swarm_peers" in stats
    assert stats["swarm_peers"]["count"] > 0


if __name__ == "__main__":
    # Run the tests
    pytest.main(["-xvs", __file__])