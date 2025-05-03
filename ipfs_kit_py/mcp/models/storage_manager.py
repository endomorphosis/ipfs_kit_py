"""
Storage Manager Model for MCP Server.

This model manages storage backends and operations for the MCP server.
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional, Union, Set

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.lassie_kit import lassie_kit
from ipfs_kit_py.huggingface_kit import huggingface_kit
from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.mcp.models.storage.base_storage_model import BaseStorageModel
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
from ipfs_kit_py.mcp.models.storage.huggingface_model import HuggingFaceModel
from ipfs_kit_py.mcp.models.storage.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.models.storage.lassie_model import LassieModel
from ipfs_kit_py.mcp.models.storage.s3_model import S3Model
from ipfs_kit_py.mcp.models.storage.storacha_model import StorachaModel
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class StorageManager:
    """Storage Manager for MCP Server."""

    def __init__(self, ipfs_model=None, debug_mode: bool = False, isolation_mode: bool = True,
                 log_level: str = "INFO", resources: Optional[Dict[str, Any]] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """Initialize the storage manager."""
        self.debug_mode = debug_mode
        self.isolation_mode = isolation_mode
        self.log_level = log_level
        self.ipfs_model = ipfs_model
        self.resources = resources or {}  # Store resources for potential use by storage models
        self.metadata = metadata or {}    # Store metadata for potential use by storage models
        self.storage_models: Dict[str, BaseStorageModel] = {}
        
        # Initialize storage backends
        self._init_storage_models()

    def _init_storage_models(self):
        """Initialize all storage backend models."""
        # Always register IPFS model
        if self.ipfs_model:
            logger.info("Using provided IPFS Model")
            self.storage_models['ipfs'] = self.ipfs_model
            # Ensure isolation_mode is set even if using a provided model
            if not hasattr(self.ipfs_model, 'isolation_mode'):
                self.ipfs_model.isolation_mode = self.isolation_mode
        else:
            # Create a new IPFSModel with isolation_mode
            ipfs_model = IPFSModel(debug_mode=self.debug_mode, 
                                 log_level=self.log_level)
            # Add isolation_mode attribute to IPFSModel
            ipfs_model.isolation_mode = self.isolation_mode
            self.storage_models['ipfs'] = ipfs_model

        # Initialize S3 model
        try:
            # Get S3 configuration from environment or use default
            s3_config = {
                "accessKey": os.environ.get("S3_ACCESS_KEY", ""),
                "secretKey": os.environ.get("S3_SECRET_KEY", ""),
                "endpoint": os.environ.get("S3_ENDPOINT", ""),
                "region": os.environ.get("S3_REGION", "us-east-1"),
                "bucket": os.environ.get("S3_BUCKET", "ipfs-storage")
            }
            
            s3_resources = {}
            
            logger.info(f"Initializing S3 kit with resources={s3_resources}, config={s3_config}")
            
            if not s3_config["accessKey"] or not s3_config["secretKey"] or not s3_config["endpoint"]:
                logger.warning("s3_config is incomplete; skipping S3 configuration.")
                s3_kit_instance = None
            else:
                s3_kit_instance = s3_kit(resources=s3_resources, meta={"s3cfg": s3_config})
                        
            if s3_kit_instance:
                # S3Model might accept different parameter names, simplifying initialization
                self.storage_models['s3'] = S3Model()
                logger.info("S3 Model initialized")
            else:
                logger.warning("Skipping S3 Model initialization due to missing configuration")
        except Exception as e:
            logger.error(f"Failed to initialize S3 Model: {e}")

        # Initialize Hugging Face model
        try:
            # HuggingFaceModel only accepts api_token parameter
            api_token = os.environ.get("HUGGINGFACE_TOKEN", "")
            self.storage_models['huggingface'] = HuggingFaceModel(api_token=api_token)
            logger.info("Hugging Face Model initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Hugging Face Model: {e}")

        # Initialize Storacha model
        try:
            # StorachaModel likely takes configuration parameters rather than an instance
            self.storage_models['storacha'] = StorachaModel()
            logger.info("Storacha Model initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Storacha Model: {e}")

        # Initialize Filecoin model
        try:
            # FilecoinModel takes different parameters
            self.storage_models['filecoin'] = FilecoinModel()
            logger.info("Filecoin Model initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Filecoin Model: {e}")

        # Initialize Lassie model
        try:
            # LassieModel takes different parameters
            self.storage_models['lassie'] = LassieModel()
            logger.info("Lassie Model initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Lassie Model: {e}")

        logger.info(f"Storage Manager initialized with backends: {', '.join(self.storage_models.keys())}")

    def get_model(self, backend_name: str) -> Optional[BaseStorageModel]:
        """Get a storage model by name.

        Args:
            backend_name: Name of the storage backend

        Returns:
            Storage model or None if not found
        """
        return self.storage_models.get(backend_name)

    def get_all_models(self) -> Dict[str, BaseStorageModel]:
        """Get all storage models.

        Returns:
            Dictionary of storage models
        """
        return self.storage_models

    def get_available_backends(self) -> Dict[str, bool]:
        """Get the availability status of all backends.

        Returns:
            Dictionary mapping backend names to availability status
        """
        backends = {
            "ipfs": "ipfs" in self.storage_models,
            "s3": "s3" in self.storage_models,
            "huggingface": "huggingface" in self.storage_models,
            "storacha": "storacha" in self.storage_models,
            "filecoin": "filecoin" in self.storage_models,
            "lassie": "lassie" in self.storage_models,
        }
        return backends

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics for all backends.

        Returns:
            Dictionary with statistics for each backend
        """
        stats = {}

        # Get stats from each backend
        for name, model in self.storage_models.items():
            stats[name] = model.get_stats()

        # Add aggregate stats
        total_uploaded = 0
        total_downloaded = 0
        total_operations = 0

        for backend_stats in stats.values():
            op_stats = backend_stats.get("operation_stats", {})
            total_uploaded += op_stats.get("bytes_uploaded", 0)
            total_downloaded += op_stats.get("bytes_downloaded", 0)
            total_operations += op_stats.get("total_operations", 0)

        stats["aggregate"] = {
            "total_operations": total_operations,
            "bytes_uploaded": total_uploaded,
            "bytes_downloaded": total_downloaded,
            "backend_count": len(self.storage_models)
        }

        return stats

    def reset(self):
        """Reset all storage models."""
        for model in self.storage_models.values():
            model.reset()
        logger.info("All storage models reset")
