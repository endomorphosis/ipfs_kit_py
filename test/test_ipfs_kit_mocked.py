import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, call
from ipfs_kit_py.ipfs_kit import ipfs_kit

@pytest.fixture
def ipfs_kit_instance():
    """Create a properly configured IPFSKit instance for testing with mocked components."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-peer-id"}'
        mock_run.return_value = mock_process
        
        # Create instance with test configuration
        instance = ipfs_kit(
            resources=None,
            metadata={
                "role": "leecher",
                "config": {
                    "Addresses": {
                        "API": "/ip4/127.0.0.1/tcp/5001",
                        "Gateway": "/ip4/127.0.0.1/tcp/8080",
                        "Swarm": [
                            "/ip4/0.0.0.0/tcp/4001",
                            "/ip6/::/tcp/4001"
                        ]
                    }
                },
                "test_mode": True
            }
        )
        
        # Mock the ipfs_py component
        instance.ipfs = MagicMock()
        
        yield instance

def test_init(ipfs_kit_instance):
    """Test ipfs_kit initialization."""
    # Assert
    assert ipfs_kit_instance is not None
    assert ipfs_kit_instance.role == "leecher"
    assert "Addresses" in ipfs_kit_instance.metadata.get("config", {})

def test_add_content(ipfs_kit_instance):
    """Test adding content to IPFS."""
    # Set up mock
    ipfs_kit_instance.ipfs.add.return_value = {
        "success": True,
        "operation": "add",
        "cid": "QmTest123",
        "size": 12
    }
    
    # Create test content
    test_content = b"Test content"
    
    # Write to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(test_content)
        file_path = temp.name
    
    try:
        # Act
        result = ipfs_kit_instance.ipfs_add(file_path)
        
        # Assert
        assert result["success"] is True
        assert result["cid"] == "QmTest123"
        ipfs_kit_instance.ipfs.add.assert_called_once_with(file_path, recursive=False)
        
    finally:
        # Clean up
        os.unlink(file_path)

def test_cat_content(ipfs_kit_instance):
    """Test retrieving content from IPFS."""
    # Set up mock
    ipfs_kit_instance.ipfs.cat.return_value = {
        "success": True,
        "operation": "cat",
        "data": b"Test content",
        "size": 12
    }
    
    # Act
    result = ipfs_kit_instance.ipfs_cat("QmTest123")
    
    # Assert
    assert result["success"] is True
    assert result["data"] == b"Test content"
    ipfs_kit_instance.ipfs.cat.assert_called_once_with("QmTest123")

def test_pin_add(ipfs_kit_instance):
    """Test pinning content in IPFS."""
    # Set up mock
    ipfs_kit_instance.ipfs.pin_add.return_value = {
        "success": True,
        "operation": "pin_add",
        "pins": ["QmTest123"],
        "count": 1
    }
    
    # Act
    result = ipfs_kit_instance.ipfs_pin_add("QmTest123")
    
    # Assert
    assert result["success"] is True
    assert "QmTest123" in result["pins"]
    ipfs_kit_instance.ipfs.pin_add.assert_called_once_with("QmTest123", recursive=True)

def test_pin_ls(ipfs_kit_instance):
    """Test listing pinned content in IPFS."""
    # Set up mock
    ipfs_kit_instance.ipfs.pin_ls.return_value = {
        "success": True,
        "operation": "pin_ls",
        "pins": {
            "QmTest123": {"type": "recursive"},
            "QmTest456": {"type": "recursive"}
        },
        "count": 2
    }
    
    # Act
    result = ipfs_kit_instance.ipfs_pin_ls()
    
    # Assert
    assert result["success"] is True
    assert len(result["pins"]) == 2
    assert "QmTest123" in result["pins"]
    assert "QmTest456" in result["pins"]
    ipfs_kit_instance.ipfs.pin_ls.assert_called_once()

def test_pin_rm(ipfs_kit_instance):
    """Test unpinning content in IPFS."""
    # Set up mock
    ipfs_kit_instance.ipfs.pin_rm.return_value = {
        "success": True,
        "operation": "pin_rm",
        "pins": ["QmTest123"],
        "count": 1
    }
    
    # Act
    result = ipfs_kit_instance.ipfs_pin_rm("QmTest123")
    
    # Assert
    assert result["success"] is True
    assert "QmTest123" in result["pins"]
    ipfs_kit_instance.ipfs.pin_rm.assert_called_once_with("QmTest123", recursive=True)

def test_swarm_peers(ipfs_kit_instance):
    """Test getting swarm peers."""
    # Set up mock
    ipfs_kit_instance.ipfs.swarm_peers.return_value = {
        "success": True,
        "operation": "swarm_peers",
        "peers": [
            {
                "addr": "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
                "peer": "QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
                "latency": "23.456ms"
            }
        ],
        "count": 1
    }
    
    # Act
    result = ipfs_kit_instance.ipfs_swarm_peers()
    
    # Assert
    assert result["success"] is True
    assert len(result["peers"]) == 1
    assert result["peers"][0]["peer"] == "QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
    ipfs_kit_instance.ipfs.swarm_peers.assert_called_once()

def test_id(ipfs_kit_instance):
    """Test getting node ID information."""
    # Set up mock
    ipfs_kit_instance.ipfs.id.return_value = {
        "success": True,
        "operation": "id",
        "id": "QmTest123",
        "addresses": [
            "/ip4/127.0.0.1/tcp/4001/p2p/QmTest123",
            "/ip4/192.168.1.100/tcp/4001/p2p/QmTest123"
        ],
        "agent_version": "kubo/0.18.0/",
        "protocol_version": "ipfs/0.1.0"
    }
    
    # Act
    result = ipfs_kit_instance.ipfs_id()
    
    # Assert
    assert result["success"] is True
    assert result["id"] == "QmTest123"
    assert len(result["addresses"]) == 2
    ipfs_kit_instance.ipfs.id.assert_called_once()

def test_error_handling(ipfs_kit_instance):
    """Test error handling when IPFS operations fail."""
    # Set up mock to simulate an error
    error_response = {
        "success": False,
        "operation": "add",
        "error": "Failed to add content",
        "error_type": "IPFSError"
    }
    ipfs_kit_instance.ipfs.add.return_value = error_response
    
    # Act
    result = ipfs_kit_instance.ipfs_add("nonexistent_file.txt")
    
    # Assert
    assert result["success"] is False
    assert "error" in result
    assert result["error"] == "Failed to add content"

def test_role_based_behavior(ipfs_kit_instance):
    """Test role-based behavior of ipfs_kit."""
    # Test with leecher role (default for our test instance)
    assert ipfs_kit_instance.role == "leecher"
    
    # Create a worker role instance
    with patch('subprocess.run') as mock_run:
        worker_instance = ipfs_kit(
            resources=None,
            metadata={"role": "worker", "test_mode": True}
        )
        assert worker_instance.role == "worker"
    
    # Create a master role instance
    with patch('subprocess.run') as mock_run:
        master_instance = ipfs_kit(
            resources=None,
            metadata={"role": "master", "test_mode": True}
        )
        assert master_instance.role == "master"

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])