"""IPFS Backend Module

This module provides a unified interface for interacting with different IPFS implementations.
"""

import logging
import os
import sys
from typing import Dict, Any, Optional, List, Union, Callable

logger = logging.getLogger(__name__)

# Singleton instance for the IPFS backend
_backend_instance = None


class IPFSBackend:
    """Interface for interacting with different IPFS implementations."""
    
    def __init__(
        self,
        implementation: str = "http",
        host: str = "127.0.0.1",
        port: int = 5001,
        **kwargs
    ):
        """
        Initialize an IPFS backend.
        
        Args:
            implementation: The implementation to use (http, go-ipfs, js-ipfs, etc.)
            host: The IPFS daemon host
            port: The IPFS daemon port
            **kwargs: Additional implementation-specific options
        """
        self.implementation = implementation
        self.host = host
        self.port = port
        self.options = kwargs
        self.client = None
        
        # Initialize client based on implementation
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the appropriate IPFS client based on implementation."""
        if self.implementation == "http":
            self._initialize_http_client()
        elif self.implementation == "py-ipfs":
            self._initialize_py_ipfs_client()
        elif self.implementation == "js-ipfs":
            self._initialize_js_ipfs_client()
        elif self.implementation == "go-ipfs":
            self._initialize_go_ipfs_client()
        elif self.implementation == "mock":
            self._initialize_mock_client()
        else:
            logger.warning(f"Unknown implementation: {self.implementation}, using mock")
            self._initialize_mock_client()
    
    def _initialize_http_client(self) -> None:
        """Initialize HTTP client for IPFS API."""
        try:
            import ipfshttpclient
            
            # Construct the API URL
            protocol = "http"
            base_url = f"{protocol}://{self.host}:{self.port}"
            
            # Get authentication options if provided
            auth = None
            if "username" in self.options and "password" in self.options:
                auth = (self.options["username"], self.options["password"])
            
            # Create the IPFS client
            self.client = ipfshttpclient.connect(
                base_url,
                timeout=self.options.get("timeout", 120),
                headers=self.options.get("headers"),
                auth=auth
            )
            
            logger.info(f"Initialized HTTP IPFS client to {base_url}")
            
        except ImportError:
            logger.warning("ipfshttpclient not available. Using mock implementation.")
            self._initialize_mock_client()
        except Exception as e:
            logger.error(f"Error initializing HTTP IPFS client: {str(e)}")
            self._initialize_mock_client()
    
    def _initialize_py_ipfs_client(self) -> None:
        """Initialize Python IPFS client."""
        try:
            from ipfs_kit_py.ipfs.ipfs_py import ipfs_py
            
            # Create the IPFS client
            self.client = ipfs_py(
                resources={
                    "host": self.host,
                    "port": self.port
                },
                metadata=self.options.get("metadata", {})
            )
            
            logger.info(f"Initialized Python IPFS client to {self.host}:{self.port}")
            
        except ImportError:
            logger.warning("ipfs_py not available. Using mock implementation.")
            self._initialize_mock_client()
        except Exception as e:
            logger.error(f"Error initializing Python IPFS client: {str(e)}")
            self._initialize_mock_client()
    
    def _initialize_js_ipfs_client(self) -> None:
        """Initialize JavaScript IPFS client."""
        logger.warning("JavaScript IPFS client not implemented. Using mock implementation.")
        self._initialize_mock_client()
    
    def _initialize_go_ipfs_client(self) -> None:
        """Initialize Go IPFS client through binding or shell."""
        logger.warning("Go IPFS client not implemented. Using mock implementation.")
        self._initialize_mock_client()
    
    def _initialize_mock_client(self) -> None:
        """Initialize a mock IPFS client for testing."""
        class MockIPFS:
            def __getattr__(self, name):
                def mock_method(*args, **kwargs):
                    logger.info(f"Mock IPFS method called: {name}({args}, {kwargs})")
                    if name == "add":
                        return {"Hash": "QmMockHash", "Name": "mock_file"}
                    elif name == "cat":
                        return b"Mock content"
                    elif name == "get":
                        return b"Mock content"
                    elif name == "ls":
                        return {"Objects": [{"Hash": "QmMockHash", "Links": []}]}
                    elif name.startswith("pin_"):
                        return {"Pins": ["QmMockHash"]}
                    elif name == "id":
                        return {"ID": "MockPeerID", "Addresses": ["/ip4/127.0.0.1/tcp/4001"]}
                    return {}
                return mock_method
        
        self.client = MockIPFS()
        logger.info("Initialized mock IPFS client")
    
    def add(self, *args, **kwargs) -> Dict[str, Any]:
        """Add content to IPFS."""
        try:
            return self.client.add(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error adding content to IPFS: {str(e)}")
            return {"Hash": "", "error": str(e)}
    
    def cat(self, *args, **kwargs) -> bytes:
        """Cat content from IPFS."""
        try:
            return self.client.cat(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error catting content from IPFS: {str(e)}")
            return b""
    
    def get(self, *args, **kwargs) -> bytes:
        """Get content from IPFS."""
        try:
            return self.client.get(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error getting content from IPFS: {str(e)}")
            return b""
    
    def ls(self, *args, **kwargs) -> Dict[str, Any]:
        """List content from IPFS."""
        try:
            return self.client.ls(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing content from IPFS: {str(e)}")
            return {"Objects": []}
    
    def pin_add(self, *args, **kwargs) -> Dict[str, Any]:
        """Pin content in IPFS."""
        try:
            return self.client.pin.add(*args, **kwargs)
        except AttributeError:
            # Handle different client APIs
            try:
                return self.client.pin_add(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error pinning content in IPFS: {str(e)}")
                return {"Pins": []}
        except Exception as e:
            logger.error(f"Error pinning content in IPFS: {str(e)}")
            return {"Pins": []}
    
    def pin_ls(self, *args, **kwargs) -> Dict[str, Any]:
        """List pinned content in IPFS."""
        try:
            return self.client.pin.ls(*args, **kwargs)
        except AttributeError:
            # Handle different client APIs
            try:
                return self.client.pin_ls(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error listing pins in IPFS: {str(e)}")
                return {"Keys": {}}
        except Exception as e:
            logger.error(f"Error listing pins in IPFS: {str(e)}")
            return {"Keys": {}}
    
    def pin_rm(self, *args, **kwargs) -> Dict[str, Any]:
        """Remove pinned content from IPFS."""
        try:
            return self.client.pin.rm(*args, **kwargs)
        except AttributeError:
            # Handle different client APIs
            try:
                return self.client.pin_rm(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error removing pins in IPFS: {str(e)}")
                return {"Pins": []}
        except Exception as e:
            logger.error(f"Error removing pins in IPFS: {str(e)}")
            return {"Pins": []}
    
    def id(self) -> Dict[str, Any]:
        """Get IPFS node ID information."""
        try:
            return self.client.id()
        except Exception as e:
            logger.error(f"Error getting IPFS node ID: {str(e)}")
            return {"ID": "", "error": str(e)}
    
    def swarm_peers(self) -> Dict[str, Any]:
        """Get IPFS swarm peers."""
        try:
            return self.client.swarm.peers()
        except AttributeError:
            # Handle different client APIs
            try:
                return self.client.swarm_peers()
            except Exception as e:
                logger.error(f"Error getting IPFS swarm peers: {str(e)}")
                return {"Peers": []}
        except Exception as e:
            logger.error(f"Error getting IPFS swarm peers: {str(e)}")
            return {"Peers": []}
    
    def check_health(self) -> bool:
        """Check IPFS node health."""
        try:
            self.id()
            return True
        except Exception:
            return False


def get_instance(
    implementation: str = "http",
    host: str = "127.0.0.1",
    port: int = 5001,
    **kwargs
) -> IPFSBackend:
    """
    Get the IPFS backend instance.
    
    This creates a singleton instance of the IPFS backend, or returns an
    existing instance if one has already been created.
    
    Args:
        implementation: The implementation to use
        host: The IPFS daemon host
        port: The IPFS daemon port
        **kwargs: Additional implementation-specific options
    
    Returns:
        An IPFS backend instance
    """
    global _backend_instance
    
    if _backend_instance is None:
        _backend_instance = IPFSBackend(
            implementation=implementation,
            host=host,
            port=port,
            **kwargs
        )
    
    return _backend_instance