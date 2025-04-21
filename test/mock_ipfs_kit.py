"""Mock IPFSKit for testing.

This module provides a mock implementation of IPFSKit that can be used in tests.
"""

import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class MockIPFSKit:
    """Mock implementation of IPFSKit for testing."""
    
    def __init__(self, resources=None, metadata=None, auto_start_daemons=False, **kwargs):
        """Initialize the mock IPFSKit.
        
        Args:
            resources: Mock resources
            metadata: Mock metadata
            auto_start_daemons: Whether to auto-start daemons
            **kwargs: Additional parameters
        """
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.auto_start_daemons = auto_start_daemons
        self.role = metadata.get("role", "leecher") if metadata else "leecher"
        self.initialized = False
        self.running = False
        self.logger = logger
        
        # Mock components
        self.ipfs = MockIPFS()
        self.storacha_kit = MockStorachaKit()
        self.s3_kit = MockS3Kit()
        
        # Initialize if auto_start_daemons is True
        if auto_start_daemons:
            self.initialize()
            
    def initialize(self, start_daemons=True):
        """Initialize the mock IPFSKit."""
        self.initialized = True
        if start_daemons:
            self._start_required_daemons()
        return {"success": True, "message": "Initialized mock IPFSKit"}
        
    def _start_required_daemons(self):
        """Start required daemons."""
        self.running = True
        return True
        
    def check_daemon_status(self):
        """Check daemon status."""
        return {
            "success": True,
            "daemons": {
                "ipfs": {"running": self.running, "type": "ipfs_daemon"},
            }
        }
        
    def stop_daemons(self):
        """Stop daemons."""
        self.running = False
        return {"success": True, "message": "Stopped mock daemons"}
    
    def ipfs_add(self, file_path, **kwargs):
        """Mock add operation."""
        return {"success": True, "cid": "QmTestCID", "path": file_path}
    
    def ipfs_cat(self, cid, **kwargs):
        """Mock cat operation."""
        return {"success": True, "data": b"Test data", "cid": cid}
    
    def ipfs_pin_add(self, cid, **kwargs):
        """Mock pin add operation."""
        return {"success": True, "cid": cid}
    
    def ipfs_pin_rm(self, cid, **kwargs):
        """Mock pin remove operation."""
        return {"success": True, "cid": cid}
    
    def ipfs_pin_ls(self, **kwargs):
        """Mock pin list operation."""
        return {"success": True, "pins": {"QmTestCID": {"type": "recursive"}}}

    def __call__(self, method, **kwargs):
        """Call a method by name."""
        if hasattr(self, method):
            return getattr(self, method)(**kwargs)
        if method.startswith("ipfs_") and hasattr(self.ipfs, method):
            return getattr(self.ipfs, method)(**kwargs)
        if method.startswith("storacha_") and hasattr(self.storacha_kit, method):
            return getattr(self.storacha_kit, method)(**kwargs)
        if method.startswith("s3_") and hasattr(self.s3_kit, method):
            return getattr(self.s3_kit, method)(**kwargs)
        
        return {"success": False, "error": f"Method not found: {method}"}


class MockIPFS:
    """Mock IPFS implementation."""
    
    def __init__(self):
        self.running = True
        
    def add(self, file_path, **kwargs):
        """Mock add operation."""
        return {"success": True, "cid": "QmTestCID", "path": file_path}
    
    def cat(self, cid, **kwargs):
        """Mock cat operation."""
        return {"success": True, "data": b"Test data", "cid": cid}
    
    def pin_add(self, cid, **kwargs):
        """Mock pin add operation."""
        return {"success": True, "cid": cid}
    
    def pin_rm(self, cid, **kwargs):
        """Mock pin remove operation."""
        return {"success": True, "cid": cid}
    
    def pin_ls(self, **kwargs):
        """Mock pin list operation."""
        return {"success": True, "pins": {"QmTestCID": {"type": "recursive"}}}


class MockStorachaKit:
    """Mock StorachaKit implementation."""
    
    def __init__(self):
        self.endpoint = "https://up.storacha.network/bridge"
        
    def storacha_upload(self, file_path, **kwargs):
        """Mock upload operation."""
        return {"success": True, "cid": "QmTestCID", "path": file_path}
    
    def storacha_download(self, cid, **kwargs):
        """Mock download operation."""
        return {"success": True, "data": b"Test data", "cid": cid}


class MockS3Kit:
    """Mock S3Kit implementation."""
    
    def __init__(self):
        self.bucket = "test-bucket"
        
    def s3_upload(self, file_path, **kwargs):
        """Mock upload operation."""
        return {"success": True, "key": "test/file.txt", "path": file_path}
    
    def s3_download(self, key, **kwargs):
        """Mock download operation."""
        return {"success": True, "data": b"Test data", "key": key}


# Export for convenience
IPFSKit = MockIPFSKit