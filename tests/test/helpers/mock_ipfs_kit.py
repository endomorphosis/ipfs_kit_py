"""
Mock implementation of IPFSKit for testing.

This module provides a mock implementation of IPFSKit for testing purposes.
"""

import time
from unittest.mock import MagicMock


class MockIPFSKit:
    """
    Mock implementation of IPFSKit for testing.
    """

    def __init__(self, role="leecher", resources=None, metadata=None):
        """
        Initialize the mock IPFSKit.

        Args:
            role: Node role
            resources: Resource constraints
            metadata: Additional metadata
        """
        self.role = role
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.filesystem = MagicMock()

        # Create mock methods for common operations
        self.ipfs_add = MagicMock(return_value={"success": True, "cid": "QmTest"})
        self.ipfs_add_file = MagicMock(return_value={"success": True, "cid": "QmTest"})
        self.ipfs_cat = MagicMock(return_value=b"Test content")
        self.ipfs_pin_add = MagicMock(return_value={"success": True})
        self.ipfs_pin_rm = MagicMock(return_value={"success": True})
        self.ipfs_pin_ls = MagicMock(return_value={"success": True, "pins": ["QmTest"]})
        self.ipfs_name_publish = MagicMock(return_value={"success": True, "name": "QmName"})
        self.ipfs_name_resolve = MagicMock(return_value={"success": True, "path": "/ipfs/QmTest"})
        self.ipfs_swarm_connect = MagicMock(return_value={"success": True})
        self.ipfs_swarm_peers = MagicMock(
            return_value={"success": True, "peers": ["/ip4/1.2.3.4/tcp/4001/p2p/QmPeer"]}
        )

        # Cluster methods
        self.cluster_add = MagicMock(return_value={"success": True, "cid": "QmTest"})
        self.cluster_add_file = MagicMock(return_value={"success": True, "cid": "QmTest"})
        self.cluster_pin_add = MagicMock(return_value={"success": True})
        self.cluster_status = MagicMock(
            return_value={"success": True, "cid": "QmTest", "status": "pinned"}
        )
        self.cluster_status_all = MagicMock(
            return_value={"success": True, "pins": [{"cid": "QmTest", "status": "pinned"}]}
        )
        self.cluster_peers = MagicMock(
            return_value={
                "success": True,
                "peers": [{"id": "QmPeer", "addresses": ["/ip4/1.2.3.4/tcp/9096"]}],
            }
        )

        # AI/ML methods
        self.ai_model_add = MagicMock(
            return_value={"success": True, "model_id": "model1", "cid": "QmTest"}
        )
        self.ai_model_get = MagicMock(return_value={"success": True, "model": MagicMock()})
        self.ai_dataset_add = MagicMock(
            return_value={"success": True, "dataset_id": "dataset1", "cid": "QmTest"}
        )
        self.ai_dataset_get = MagicMock(return_value={"success": True, "dataset": MagicMock()})

    def get_filesystem(self):
        """
        Get the filesystem interface.

        Returns:
            Mock filesystem object
        """
        return self.filesystem
