"""
IPFS Datasets Integration Module

This module provides integration with ipfs_datasets_py for distributed dataset
manipulation services. It enables local-first and decentralized filesystem operations
with proper fallback support for CI/CD environments where the package may not be available.

Key Features:
1. Dataset storage and retrieval via IPFS
2. Content-addressed versioning
3. Distributed dataset loading
4. Filesystem metadata management (event logs, provenance logs)
5. Graceful degradation when ipfs_datasets_py is not available

Usage:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    
    manager = get_ipfs_datasets_manager(enable=True)
    if manager.is_available():
        # Use distributed dataset features
        cid = manager.store_dataset(data, metadata)
    else:
        # Fall back to local operations
        pass
"""

import logging
import os
import sys
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Try to import ipfs_datasets_py with fallback.
#
# NOTE: The published `ipfs_datasets_py` package does not necessarily expose a
# `DatasetManager` symbol. We treat the dependency as available if the package
# itself imports, and keep our own manager abstraction (`IPFSDatasetsManager`).
IPFS_DATASETS_AVAILABLE = False
IPFSDatasetManager = None
_ipfs_datasets_py = None

def _should_skip_datasets_import() -> bool:
    if os.environ.get("IPFS_KIT_FAST_INIT") == "1":
        return True
    if os.environ.get("IPFS_KIT_SKIP_DATASETS") == "1":
        return True
    pytest_env_markers = (
        "PYTEST_CURRENT_TEST",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_VERSION",
        "PYTEST_XDIST_WORKER",
    )
    if any(os.environ.get(key) for key in pytest_env_markers):
        return True
    argv = sys.argv or []
    if any(flag in argv for flag in ("-h", "--help")):
        return True
    return False

def _ensure_ipfs_datasets_loaded() -> None:
    global IPFS_DATASETS_AVAILABLE, IPFSDatasetManager, _ipfs_datasets_py
    if _ipfs_datasets_py is not None or IPFS_DATASETS_AVAILABLE:
        return
    if _should_skip_datasets_import():
        IPFS_DATASETS_AVAILABLE = False
        return
    try:
        import ipfs_datasets_py as _datasets  # noqa: F401

        _ipfs_datasets_py = _datasets
        IPFS_DATASETS_AVAILABLE = True
        IPFSDatasetManager = None
        logger.info("ipfs_datasets_py is available for dataset operations")
    except Exception:
        IPFS_DATASETS_AVAILABLE = False
        IPFSDatasetManager = None
        logger.info("ipfs_datasets_py not available - using fallback implementations")


class DatasetIPFSBackend:
    """
    Adapter class that bridges ipfs_kit_py's DatasetManager with ipfs_datasets_py.
    
    This class provides a unified interface for distributed dataset operations,
    handling IPFS storage, retrieval, and metadata management. When ipfs_datasets_py
    is not available, it provides mock implementations to ensure the system continues
    to function in a degraded mode.
    """
    
    def __init__(self, ipfs_client=None, base_path: str = "~/.ipfs_datasets", 
                 enable_distributed: bool = True):
        """
        Initialize the IPFS dataset backend.
        
        Args:
            ipfs_client: Optional IPFS client instance from ipfs_kit
            base_path: Base directory for local dataset storage
            enable_distributed: Enable distributed operations (requires ipfs_datasets_py)
        """
        _ensure_ipfs_datasets_loaded()
        self.ipfs_client = ipfs_client
        self.base_path = Path(os.path.expanduser(base_path))
        self.enable_distributed = enable_distributed and IPFS_DATASETS_AVAILABLE
        self.backend = None
        
        # Initialize backend if available
        if self.enable_distributed and IPFSDatasetManager:
            try:
                self.backend = IPFSDatasetManager(
                    ipfs_client=ipfs_client,
                    base_path=str(self.base_path)
                )
                logger.info(f"Initialized IPFS dataset backend at {self.base_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize IPFS dataset backend: {e}")
                self.backend = None
                self.enable_distributed = False
        
        # Ensure base path exists for local fallback
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _is_cid(identifier: str) -> bool:
        """
        Check if the identifier looks like an IPFS CID.
        
        Supports common CID formats:
        - CIDv0: Starts with 'Qm'
        - CIDv1: Starts with 'b' (base32), 'z' (base58btc), 'f' (base32), 'u' (base64url)
        
        Args:
            identifier: String to check
        
        Returns:
            True if identifier appears to be a CID
        """
        return identifier.startswith(('Qm', 'b', 'z', 'f', 'u'))
    
    def is_available(self) -> bool:
        """Check if distributed operations are available."""
        return self.enable_distributed and self.backend is not None
    
    def store_dataset(self, dataset_path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Store a dataset in IPFS and return metadata including CID.
        
        Args:
            dataset_path: Path to the dataset file or directory
            metadata: Optional metadata to attach to the dataset
        
        Returns:
            Dictionary containing:
                - success: bool indicating if operation succeeded
                - cid: Content identifier (if distributed mode enabled)
                - local_path: Path to local storage
                - metadata: Associated metadata including provenance info
                - error: Error message if operation failed
        """
        try:
            dataset_path = Path(dataset_path)
            
            if not dataset_path.exists():
                return {
                    "success": False,
                    "error": f"Dataset file or directory does not exist: {dataset_path}"
                }
            
            # Add event log metadata
            if metadata is None:
                metadata = {}
            
            metadata["stored_at"] = datetime.datetime.now().isoformat()
            metadata["original_path"] = str(dataset_path)
            
            # Try distributed storage if available
            if self.is_available():
                try:
                    result = self.backend.store(
                        path=str(dataset_path),
                        metadata=metadata
                    )
                    logger.info(f"Stored dataset in IPFS with CID: {result.get('cid')}")
                    return {
                        "success": True,
                        "cid": result.get("cid"),
                        "local_path": str(dataset_path),
                        "metadata": metadata,
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Distributed storage failed, falling back to local: {e}")
            
            # Fallback to local storage
            logger.info(f"Using local storage for dataset at {dataset_path}")
            return {
                "success": True,
                "local_path": str(dataset_path),
                "metadata": metadata,
                "distributed": False
            }
            
        except Exception as e:
            logger.error(f"Error storing dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def load_dataset(self, identifier: str, target_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Load a dataset from IPFS using its CID or from local storage using a path.
        
        Args:
            identifier: CID for IPFS retrieval or path for local retrieval
            target_path: Optional target path for downloaded content
        
        Returns:
            Dictionary containing:
                - success: bool indicating if operation succeeded
                - path: Path where dataset is available
                - metadata: Associated metadata
                - error: Error message if operation failed
        """
        try:
            # Check if identifier looks like a CID
            is_cid = self._is_cid(identifier)
            
            if is_cid and self.is_available():
                try:
                    result = self.backend.load(
                        cid=identifier,
                        target_path=str(target_path) if target_path else None
                    )
                    logger.info(f"Loaded dataset from IPFS CID: {identifier}")
                    return {
                        "success": True,
                        "path": result.get("path"),
                        "metadata": result.get("metadata", {}),
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Failed to load from IPFS: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to load from IPFS: {str(e)}"
                    }
            else:
                # Local path
                dataset_path = Path(identifier)
                if not dataset_path.exists():
                    return {
                        "success": False,
                        "error": f"Local dataset not found: {identifier}"
                    }
                
                logger.info(f"Loading dataset from local path: {dataset_path}")
                return {
                    "success": True,
                    "path": str(dataset_path),
                    "metadata": {},
                    "distributed": False
                }
                
        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def version_dataset(self, dataset_id: str, version: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new version of a dataset with provenance tracking.
        
        Args:
            dataset_id: Identifier for the dataset
            version: Version string (e.g., "1.0.0")
            metadata: Optional metadata including provenance info
        
        Returns:
            Dictionary with version information and CID if distributed
        """
        try:
            if metadata is None:
                metadata = {}
            
            # Add provenance metadata
            metadata["version"] = version
            metadata["versioned_at"] = datetime.datetime.now().isoformat()
            metadata["dataset_id"] = dataset_id
            
            if self.is_available():
                try:
                    result = self.backend.version(
                        dataset_id=dataset_id,
                        version=version,
                        metadata=metadata
                    )
                    logger.info(f"Created dataset version {version} with CID: {result.get('cid')}")
                    return {
                        "success": True,
                        "version": version,
                        "cid": result.get("cid"),
                        "metadata": metadata,
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Distributed versioning failed: {e}")
            
            # Fallback: just return metadata
            logger.info(f"Created local dataset version {version}")
            return {
                "success": True,
                "version": version,
                "metadata": metadata,
                "distributed": False
            }
            
        except Exception as e:
            logger.error(f"Error versioning dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_metadata(self, identifier: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a dataset by CID or local path.
        
        Args:
            identifier: CID or local path of the dataset
        
        Returns:
            Dictionary containing metadata or error
        """
        try:
            is_cid = self._is_cid(identifier)
            
            if is_cid and self.is_available():
                try:
                    result = self.backend.get_metadata(cid=identifier)
                    return {
                        "success": True,
                        "metadata": result,
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Failed to get metadata from IPFS: {e}")
            
            # Try local metadata file
            metadata_path = Path(identifier).with_suffix('.metadata.json')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                return {
                    "success": True,
                    "metadata": metadata,
                    "distributed": False
                }
            
            return {
                "success": False,
                "error": "Metadata not found"
            }
            
        except Exception as e:
            logger.error(f"Error retrieving metadata: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class IPFSDatasetsManager:
    """
    High-level manager for IPFS datasets integration.
    
    This class provides a simplified interface for working with distributed datasets,
    handling both IPFS operations and local fallbacks automatically.
    """
    
    def __init__(self, ipfs_client=None, enable: bool = True):
        """
        Initialize the IPFS datasets manager.
        
        Args:
            ipfs_client: Optional IPFS client instance
            enable: Enable distributed operations (requires ipfs_datasets_py)
        """
        self.backend = DatasetIPFSBackend(
            ipfs_client=ipfs_client,
            enable_distributed=enable
        )
        self.event_log = []
        self.provenance_log = []
    
    def is_available(self) -> bool:
        """Check if distributed dataset operations are available."""
        return self.backend.is_available()
    
    def store(self, path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a dataset with event logging."""
        result = self.backend.store_dataset(path, metadata)
        
        # Log the event
        self.event_log.append({
            "operation": "store",
            "path": str(path),
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result.get("success", False),
            "cid": result.get("cid")
        })
        
        return result
    
    def load(self, identifier: str, target_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Load a dataset with event logging."""
        result = self.backend.load_dataset(identifier, target_path)
        
        # Log the event
        self.event_log.append({
            "operation": "load",
            "identifier": identifier,
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result.get("success", False)
        })
        
        return result
    
    def version(self, dataset_id: str, version: str, 
                parent_version: Optional[str] = None,
                transformations: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a versioned dataset with provenance tracking.
        
        Args:
            dataset_id: Dataset identifier
            version: New version string
            parent_version: Optional parent version for lineage tracking
            transformations: Optional list of transformations applied
        
        Returns:
            Result dictionary with version info
        """
        metadata = {
            "provenance": {
                "parent_version": parent_version,
                "transformations": transformations or []
            }
        }
        
        result = self.backend.version_dataset(dataset_id, version, metadata)
        
        # Log provenance
        self.provenance_log.append({
            "dataset_id": dataset_id,
            "version": version,
            "parent_version": parent_version,
            "transformations": transformations or [],
            "timestamp": datetime.datetime.now().isoformat(),
            "cid": result.get("cid")
        })
        
        return result
    
    def get_event_log(self) -> List[Dict[str, Any]]:
        """Get the event log for all dataset operations."""
        return self.event_log.copy()
    
    def get_provenance_log(self) -> List[Dict[str, Any]]:
        """Get the provenance log showing dataset lineage."""
        return self.provenance_log.copy()


# Singleton instance for easy access
_manager_instance: Optional[IPFSDatasetsManager] = None


def get_ipfs_datasets_manager(ipfs_client=None, enable: bool = True) -> IPFSDatasetsManager:
    """
    Get or create the singleton IPFS datasets manager instance.
    
    Args:
        ipfs_client: Optional IPFS client instance
        enable: Enable distributed operations
    
    Returns:
        IPFSDatasetsManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = IPFSDatasetsManager(ipfs_client=ipfs_client, enable=enable)
    return _manager_instance


def reset_manager():
    """Reset the singleton manager instance (useful for testing)."""
    global _manager_instance
    _manager_instance = None
