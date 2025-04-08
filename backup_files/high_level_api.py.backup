"""
High-level API for IPFS Kit.

This module provides a high-level API for interacting with IPFS through
a simplified interface focused on common operations and use cases.
It includes methods for content management, filesystem access, AI/ML integration,
role-based operations, and ecosystem connectivity.
"""

import logging
import os
import sys
import time
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, BinaryIO, TypeVar, Callable, Literal

# Initialize logger
logger = logging.getLogger(__name__)

# Define initial values for FSSpec integration
FSSPEC_AVAILABLE = False
try:
    import fsspec
    FSSPEC_AVAILABLE = True
except ImportError:
    FSSPEC_AVAILABLE = False

# Flag to track if AI/ML integration is available
AI_ML_AVAILABLE = False
try:
    import numpy as np
    # Check for tensor libraries
    try:
        import torch
        AI_ML_AVAILABLE = True
    except ImportError:
        try:
            import tensorflow as tf
            AI_ML_AVAILABLE = True
        except ImportError:
            # Fall back to scikit-learn
            try:
                import sklearn
                AI_ML_AVAILABLE = True
            except ImportError:
                AI_ML_AVAILABLE = False
except ImportError:
    AI_ML_AVAILABLE = False

class IPFSSimpleAPI:
    """
    High-level API for IPFS operations.
    
    This class provides a simplified interface for working with IPFS,
    focusing on common operations and ease of use.
    """
    
    def __init__(self, config=None):
        """
        Initialize the high-level API with the given configuration.
        
        Args:
            config: Configuration dictionary (optional)
        """
        # Initialize configuration
        self.config = config or {}
        
        # Initialize underlying kit
        self.kit = self._initialize_kit()
        
        # Initialize filesystem access through the get_filesystem method
        self.fs = self.get_filesystem()
        
        # Load plugins
        self.plugins = {}
        if "plugins" in self.config:
            self._load_plugins(self.config["plugins"])
            
        # Initialize extension registry
        self.extensions = {}
        
        logger.info(f"IPFSSimpleAPI initialized with role: {self.config.get('role', 'leecher')}")
    
    def _initialize_kit(self):
        """Initialize the IPFS kit with the current configuration."""
        # Import here to avoid circular imports
        try:
            from .ipfs_kit import ipfs_kit
            return ipfs_kit(self.config)
        except ImportError:
            # Fallback to module import 
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            return ipfs_kit(self.config)
    
    def _load_plugins(self, plugin_config):
        """Load plugins based on configuration."""
        # Implementation would load and initialize plugins
        pass
        
    def _check_fsspec_available(self):
        """
        Check if fsspec is available by trying to import it.
        
        This method allows for better testing and mocking of the import check.
        
        Returns:
            bool: True if fsspec is available, False otherwise
        """
        try:
            import fsspec
            return True
        except ImportError:
            return False
    
    def _import_ipfs_filesystem(self):
        """
        Import the IPFSFileSystem class from the ipfs_fsspec module.
        
        This method allows for better testing and mocking of the import.
        
        Returns:
            IPFSFileSystem class
            
        Raises:
            ImportError: If the import fails
        """
        try:
            # Try relative import first
            from .ipfs_fsspec import IPFSFileSystem
            return IPFSFileSystem
        except ImportError:
            # Try absolute import next
            from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
            return IPFSFileSystem
    
    def get_filesystem(
        self,
        *,
        gateway_urls: Optional[List[str]] = None,
        use_gateway_fallback: Optional[bool] = None, 
        gateway_only: Optional[bool] = None,
        cache_config: Optional[Dict[str, Any]] = None,
        enable_metrics: Optional[bool] = None,
        return_mock: bool = False,  # For backward compatibility and testing
        **kwargs
    ) -> Optional[Any]:
        """
        Get an FSSpec-compatible filesystem for IPFS.

        This method returns a filesystem object that implements the fsspec interface,
        allowing standard filesystem operations on IPFS content.

        Args:
            gateway_urls: List of IPFS gateway URLs to use (e.g., ["https://ipfs.io", "https://cloudflare-ipfs.com"])
            use_gateway_fallback: Whether to use gateways as fallback when local daemon is unavailable
            gateway_only: Whether to use only gateways (no local daemon)
            cache_config: Configuration for the cache system (dict with memory_size, disk_size, disk_path etc.)
            enable_metrics: Whether to enable performance metrics
            return_mock: If True, return a mock filesystem when dependencies are missing instead of raising an error
            **kwargs: Additional parameters to pass to the filesystem

        Returns:
            FSSpec-compatible filesystem interface for IPFS, or a mock filesystem if dependencies are missing
            and return_mock is True

        Raises:
            ImportError: If FSSpec or IPFSFileSystem are not available and return_mock is False
            IPFSConfigurationError: If there's a problem with the configuration
        """
        # Return cached filesystem instance if available
        if hasattr(self, "_filesystem") and self._filesystem is not None:
            return self._filesystem
        
        # Define MockIPFSFileSystem for testing and backward compatibility
        class MockIPFSFileSystem:
            def __init__(self, **kwargs):
                self.protocol = "ipfs"
                self.kwargs = kwargs
                logger.debug(f"Created MockIPFSFileSystem with {len(kwargs)} parameters")
                
            def __call__(self, *args, **kwargs):
                return None
                
            def cat(self, path, **kwargs):
                return b""
                
            def ls(self, path, **kwargs):
                return []
                
            def info(self, path, **kwargs):
                return {"name": path, "size": 0, "type": "file"}
                
            def open(self, path, mode="rb", **kwargs):
                from io import BytesIO
                return BytesIO(b"")
        
        # Check if fsspec is available
        fsspec_available = self._check_fsspec_available()
        if not fsspec_available:
            logger.warning("FSSpec is not available. Please install fsspec to use the filesystem interface.")
            if not return_mock:
                raise ImportError("fsspec is not available. Please install fsspec to use this feature.")
        
        # Try to import IPFSFileSystem if fsspec is available
        have_ipfsfs = False
        if fsspec_available:
            try:
                IPFSFileSystem = self._import_ipfs_filesystem()
                have_ipfsfs = True
            except ImportError:
                have_ipfsfs = False
                logger.warning(
                    "ipfs_fsspec.IPFSFileSystem is not available. Please ensure your installation is complete."
                )
                if not return_mock:
                    raise ImportError("ipfs_fsspec.IPFSFileSystem is not available. Please ensure your installation is complete.")
        
        # If dependencies are missing and return_mock is True, return the mock filesystem
        if not fsspec_available or not have_ipfsfs:
            if return_mock:
                logger.info("Using mock filesystem due to missing dependencies")
                return MockIPFSFileSystem(**kwargs)
            else:
                # This should never be reached due to the earlier raises, but included for safety
                raise ImportError("Required dependencies for filesystem interface are not available")

        # Prepare configuration with clear precedence:
        # 1. Explicit parameters to this method
        # 2. Values from kwargs
        # 3. Values from config
        # 4. Default values
        fs_kwargs = {}
        
        # Process each parameter with the same pattern to maintain clarity
        param_mapping = {
            "gateway_urls": gateway_urls,
            "use_gateway_fallback": use_gateway_fallback,
            "gateway_only": gateway_only,
            "cache_config": cache_config,
            "enable_metrics": enable_metrics,
            "ipfs_path": kwargs.get("ipfs_path"),
            "socket_path": kwargs.get("socket_path"),
            "use_mmap": kwargs.get("use_mmap")
        }
        
        config_mapping = {
            "cache_config": "cache",  # Handle special case where config key differs
        }
        
        default_values = {
            "role": "leecher",
            "use_mmap": True
        }
        
        # Build configuration with proper precedence
        for param, value in param_mapping.items():
            if value is not None:
                # Explicit parameter was provided
                fs_kwargs[param] = value
            elif param in kwargs:
                # Value is in kwargs
                fs_kwargs[param] = kwargs[param]
            elif param in config_mapping and config_mapping[param] in self.config:
                # Special case for differently named config keys
                fs_kwargs[param] = self.config[config_mapping[param]]
            elif param in self.config:
                # Regular config parameter
                fs_kwargs[param] = self.config[param]
            elif param in default_values:
                # Use default value if available
                fs_kwargs[param] = default_values[param]
        
        # Special case for role which needs a slightly different logic
        if "role" not in fs_kwargs:
            if "role" in kwargs:
                fs_kwargs["role"] = kwargs["role"]
            else:
                fs_kwargs["role"] = self.config.get("role", "leecher")
        
        # Add any remaining kwargs that weren't explicitly handled
        for key, value in kwargs.items():
            if key not in fs_kwargs:
                fs_kwargs[key] = value

        # Try to create the filesystem
        try:
            # Create the filesystem
            self._filesystem = IPFSFileSystem(**fs_kwargs)
            logger.info("IPFSFileSystem initialized successfully")
            return self._filesystem
        except Exception as e:
            logger.error(f"Failed to initialize IPFSFileSystem: {e}")
            if return_mock:
                # Return the mock implementation as fallback for backward compatibility
                logger.warning("Falling back to mock filesystem due to initialization error")
                return MockIPFSFileSystem(**kwargs)
            else:
                # Re-raise the exception with context to help with debugging
                raise Exception(f"Failed to initialize IPFSFileSystem: {str(e)}") from e
    
    def open_file(self, path, mode="rb", **kwargs):
        """
        Open a file from IPFS.
        
        Args:
            path: IPFS path or CID
            mode: File mode ('rb' or 'r')
            **kwargs: Additional parameters for the filesystem
            
        Returns:
            File-like object
        """
        if not self.fs:
            raise RuntimeError("Filesystem interface not available")
        return self.fs.open(path, mode=mode, **kwargs)
    
    def read_file(self, path, **kwargs):
        """
        Read a file from IPFS.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters for the filesystem
            
        Returns:
            Binary content of the file
        """
        if not self.fs:
            raise RuntimeError("Filesystem interface not available")
        return self.fs.cat(path, **kwargs)
    
    def read_text(self, path, encoding="utf-8", **kwargs):
        """
        Read a text file from IPFS.
        
        Args:
            path: IPFS path or CID
            encoding: Text encoding to use
            **kwargs: Additional parameters for the filesystem
            
        Returns:
            Text content of the file
        """
        content = self.read_file(path, **kwargs)
        return content.decode(encoding)
    
    def list_directory(self, path, **kwargs):
        """
        List contents of a directory in IPFS.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters for the filesystem
            
        Returns:
            List of directory contents
        """
        if not self.fs:
            raise RuntimeError("Filesystem interface not available")
        return self.fs.ls(path, **kwargs)
    
    def exists(self, path, **kwargs):
        """
        Check if a file exists in IPFS.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters for the filesystem
            
        Returns:
            True if the file exists, False otherwise
        """
        if not self.fs:
            raise RuntimeError("Filesystem interface not available")
        return self.fs.exists(path, **kwargs)
    
    def get_info(self, path, **kwargs):
        """
        Get information about a file in IPFS.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters for the filesystem
            
        Returns:
            Information about the file
        """
        if not self.fs:
            raise RuntimeError("Filesystem interface not available")
        return self.fs.info(path, **kwargs)
    
    def add_file(self, file_path, **kwargs):
        """
        Add a file to IPFS.
        
        Args:
            file_path: Local file path to add
            **kwargs: Additional parameters for the IPFS add operation
            
        Returns:
            Result dictionary with CID
        """
        return self.kit.ipfs_add_file(file_path, **kwargs)
    
    def add_directory(self, dir_path, recursive=True, **kwargs):
        """
        Add a directory to IPFS.
        
        Args:
            dir_path: Local directory path to add
            recursive: Whether to add recursively
            **kwargs: Additional parameters for the IPFS add operation
            
        Returns:
            Result dictionary with root CID
        """
        return self.kit.ipfs_add_directory(dir_path, recursive=recursive, **kwargs)
    
    def get_content(self, cid, **kwargs):
        """
        Get content from IPFS by CID.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters for the IPFS get operation
            
        Returns:
            Content as bytes
        """
        return self.kit.ipfs_cat(cid, **kwargs)
    
    def pin_content(self, cid, **kwargs):
        """
        Pin content to the local node.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters for the IPFS pin operation
            
        Returns:
            Result dictionary with pin status
        """
        return self.kit.ipfs_pin_add(cid, **kwargs)
    
    def unpin_content(self, cid, **kwargs):
        """
        Unpin content from the local node.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters for the IPFS unpin operation
            
        Returns:
            Result dictionary with unpin status
        """
        return self.kit.ipfs_pin_rm(cid, **kwargs)
    
    def list_pins(self, **kwargs):
        """
        List pinned content.
        
        Args:
            **kwargs: Additional parameters for the IPFS pin list operation
            
        Returns:
            Dictionary with pinned CIDs
        """
        return self.kit.ipfs_pin_ls(**kwargs)
    
    def add_content(self, content, **kwargs):
        """
        Add content to IPFS.
        
        Args:
            content: Content to add (bytes, string, or file-like object)
            **kwargs: Additional parameters for the IPFS add operation
            
        Returns:
            Result dictionary with CID
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        return self.kit.ipfs_add(content, **kwargs)
    
    def publish_to_ipns(self, cid, key="self", **kwargs):
        """
        Publish content to IPNS.
        
        Args:
            cid: Content identifier to publish
            key: IPNS key to use
            **kwargs: Additional parameters for the IPFS name publish operation
            
        Returns:
            Result dictionary with IPNS name
        """
        return self.kit.ipfs_name_publish(cid, key=key, **kwargs)
    
    def resolve_ipns(self, name, **kwargs):
        """
        Resolve an IPNS name to a CID.
        
        Args:
            name: IPNS name to resolve
            **kwargs: Additional parameters for the IPFS name resolve operation
            
        Returns:
            Result dictionary with CID
        """
        return self.kit.ipfs_name_resolve(name, **kwargs)
    
    def get_peers(self, **kwargs):
        """
        Get connected peers.
        
        Args:
            **kwargs: Additional parameters for the IPFS swarm peers operation
            
        Returns:
            List of connected peers
        """
        return self.kit.ipfs_swarm_peers(**kwargs)
    
    def connect_to_peer(self, peer_address, **kwargs):
        """
        Connect to a peer.
        
        Args:
            peer_address: Peer address to connect to
            **kwargs: Additional parameters for the IPFS swarm connect operation
            
        Returns:
            Result dictionary with connection status
        """
        return self.kit.ipfs_swarm_connect(peer_address, **kwargs)
    
    def save_config(self, config_path=None):
        """
        Save current configuration to a file.
        
        Args:
            config_path: Path to save configuration to
            
        Returns:
            True if successful, False otherwise
        """
        if config_path is None:
            config_path = os.path.expanduser("~/.ipfs_kit_config.yaml")
        
        try:
            with open(config_path, "w") as f:
                yaml.dump(self.config, f)
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    @classmethod
    def load_config(cls, config_path=None):
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to load configuration from
            
        Returns:
            Configuration dictionary
        """
        # Default config locations to check
        config_paths = [
            config_path,
            os.path.expanduser("~/.ipfs_kit_config.yaml"),
            os.path.expanduser("~/.ipfs_kit_config.json"),
            os.path.expanduser("~/.config/ipfs_kit/config.yaml"),
            "./ipfs_kit_config.yaml",
            "./config.yaml"
        ]
        
        # Filter out None values
        config_paths = [p for p in config_paths if p is not None]
        
        # Try each path
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        if path.endswith(".json"):
                            return json.load(f)
                        else:
                            return yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"Failed to load configuration from {path}: {e}")
        
        # Return empty config if no file found
        return {}
    
    # AI/ML Integration Methods
    # These are simplified examples that would be implemented in a real application
    
    def ai_register_model(self, model_cid, metadata, *, allow_simulation=True, **kwargs):
        """Register a model."""
        result = {
            "success": True,
            "operation": "ai_register_model",
            "model_id": "model_123456",
            "registry_cid": "QmSimRegistryCID",
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
    
    def ai_test_inference(self, model_cid, test_data_cid, *, batch_size=32, max_samples=None, metrics=None, output_format="json", compute_metrics=True, save_predictions=True, device=None, precision="float32", timeout=300, allow_simulation=True, **kwargs):
        """Run inference on a test dataset."""
        result = {
            "success": True,
            "operation": "ai_test_inference",
            "metrics": {"accuracy": 0.95, "f1": 0.94},
            "predictions_cid": "QmSimPredictionsCID",
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
        
    def ai_update_deployment(self, deployment_id, *, model_cid=None, config=None, allow_simulation=True, **kwargs):
        """Update a model deployment."""
        result = {
            "success": True,
            "operation": "ai_update_deployment",
            "deployment_id": deployment_id,
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
        
    def ai_list_models(self, *, framework=None, model_type=None, limit=100, offset=0, order_by="created_at", order_dir="desc", allow_simulation=True, **kwargs):
        """List available models."""
        result = {
            "success": True,
            "operation": "ai_list_models",
            "models": [{"id": "model_1", "name": "Test Model"}],
            "count": 1,
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
        
    def ai_create_embeddings(self, docs_cid, *, embedding_model="default", recursive=True, filter_pattern=None, chunk_size=1000, chunk_overlap=0, max_docs=None, save_index=True, allow_simulation=True, **kwargs):
        """Create vector embeddings."""
        result = {
            "success": True,
            "operation": "ai_create_embeddings",
            "cid": "QmSimEmbeddingCID",
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
        
    def ai_create_vector_index(self, embedding_cid, *, index_type="hnsw", params=None, save_index=True, allow_simulation=True, **kwargs):
        """Create a vector index."""
        result = {
            "success": True,
            "operation": "ai_create_vector_index",
            "cid": "QmSimVectorIndexCID",
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
        
    def ai_hybrid_search(self, query, *, vector_index_cid, keyword_index_cid=None, vector_weight=0.7, keyword_weight=0.3, top_k=10, rerank=False, allow_simulation=True, **kwargs):
        """Perform hybrid search."""
        result = {
            "success": True,
            "operation": "ai_hybrid_search",
            "results": [{"content": "Simulated result", "score": 0.95}],
            "count": 1,
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result
        
    def ai_langchain_query(self, *, vectorstore_cid, query, top_k=5, allow_simulation=True, **kwargs):
        """Query a Langchain vectorstore."""
        result = {
            "success": True,
            "operation": "ai_langchain_query",
            "results": [{"content": "Simulated result", "score": 0.95}],
            "count": 1,
            "simulation_note": "AI/ML integration not available, using simulated response"
        }
        return result