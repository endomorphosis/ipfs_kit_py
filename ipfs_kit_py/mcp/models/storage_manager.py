"""
Storage Manager for MCP Server.

This module provides a unified interface for managing multiple storage backends:
- IPFS (InterPlanetary File System)
- S3 (AWS S3 and compatible services)
- Hugging Face Hub (model and dataset repository)
- Storacha (Web3.Storage)
- Filecoin (Lotus API integration)
- Lassie (Filecoin/IPFS content retrieval)

It manages the creation and configuration of storage models and their integration
with the MCP server.
"""

import logging
import importlib
import sys
from typing import Dict, Any, Optional
from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.huggingface_kit import huggingface_kit, HUGGINGFACE_HUB_AVAILABLE
from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_KIT_AVAILABLE
from ipfs_kit_py.lassie_kit import lassie_kit, LASSIE_KIT_AVAILABLE
from ipfs_kit_py.mcp.models.storage import BaseStorageModel
from ipfs_kit_py.mcp.models.storage.s3_model import S3Model
from ipfs_kit_py.mcp.models.storage.huggingface_model import HuggingFaceModel
from ipfs_kit_py.mcp.models.storage.storacha_model import StorachaModel
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
from ipfs_kit_py.mcp.models.storage.lassie_model import LassieModel

# Try to import IPFSModel - we'll handle it gracefully if not available
try:
    from ipfs_kit_py.mcp.models.storage.ipfs_model import IPFSModel
    IPFS_MODEL_AVAILABLE = True
except ImportError:
    IPFS_MODEL_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)


class StorageManager:
    """Manager for storage backend models."""
    
    def __init__(
        self,
        ipfs_model=None,
        cache_manager=None,
        credential_manager=None,
        resources=None,
        metadata=None
    ):
        """Initialize the storage manager.

        Args:
            ipfs_model: IPFS model for cross-backend operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
            resources: Dictionary with resources and configuration
            metadata: Additional metadata
        """
        # Store core dependencies
        self.ipfs_model = ipfs_model
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Initialize storage backends
        self.storage_models = {}
        self._init_storage_models()

        logger.info(
            f"Storage Manager initialized with backends: {', '.join(self.storage_models.keys())}"
        )

    def _init_storage_models(self):
        """Initialize storage backend models."""
        # Initialize IPFS model if it's not already passed to constructor
        if not self.ipfs_model and IPFS_MODEL_AVAILABLE:
            try:
                # Import ipfs_py class from the storage manager backends
                from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
                
                # Create resources for IPFS
                ipfs_resources = self.resources.get("ipfs", {})
                ipfs_metadata = self.metadata.get("ipfs", {})
                
                # Initialize backend adapter
                ipfs_backend = IPFSBackend(ipfs_resources, ipfs_metadata)
                
                # Create IPFS model
                self.ipfs_model = IPFSModel(
                    ipfs_backend=ipfs_backend,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                
                # Add to storage models
                self.storage_models["ipfs"] = self.ipfs_model
                logger.info("IPFS Model initialized and added to storage models")
            except Exception as e:
                logger.warning(f"Failed to initialize IPFS Model: {e}")
                logger.info("IPFS Model initialization failed, but will continue with other backends")
        elif self.ipfs_model:
            # If ipfs_model was provided in constructor, add it to storage models
            self.storage_models["ipfs"] = self.ipfs_model
            logger.info("Using provided IPFS Model")
        else:
            logger.info("IPFS Model not available. Some cross-backend operations may be limited.")

        # Initialize S3 model
        try:
            # Create S3 kit instance
            s3_config = self.metadata.get("s3_config") or {}
            s3_resources = self.resources.get("s3", {})
            logger.info(f"Initializing S3 kit with resources={s3_resources}, config={s3_config}")
            s3_kit_instance = s3_kit(resources=s3_resources, meta={"s3cfg": s3_config})

            # Create S3 model
            self.storage_models["s3"] = S3Model(
                s3_kit_instance=s3_kit_instance,
                ipfs_model=self.ipfs_model,
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager
            )
            logger.info("S3 Model initialized")
        except Exception as e:
            logger.error(f"Failed to initialize S3 Model: {e}", exc_info=True)

        # Initialize Hugging Face model if available
        if HUGGINGFACE_HUB_AVAILABLE:
            try:
                # Create Hugging Face kit instance
                hf_resources = self.resources.get("huggingface", {})
                hf_metadata = self.metadata.get("huggingface", {})
                hf_kit_instance = huggingface_kit(resources=hf_resources, metadata=hf_metadata)

                # Create Hugging Face model
                self.storage_models["huggingface"] = HuggingFaceModel(
                    huggingface_kit_instance=hf_kit_instance,
                    ipfs_model=self.ipfs_model,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                logger.info("Hugging Face Model initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Hugging Face Model: {e}")
        else:
            logger.info(
                "Hugging Face Hub not available. Install with: pip install ipfs_kit_py[huggingface]"
            )

        # Initialize Storacha model
        try:
            # Create Storacha kit instance
            storacha_resources = self.resources.get("storacha", {})
            storacha_metadata = self.metadata.get("storacha", {})
            storacha_kit_instance = storacha_kit(
                resources=storacha_resources, metadata=storacha_metadata
            )

            # Create Storacha model
            self.storage_models["storacha"] = StorachaModel(
                storacha_kit_instance=storacha_kit_instance,
                ipfs_model=self.ipfs_model,
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager
            )
            logger.info("Storacha Model initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Storacha Model: {e}")

        # Initialize Filecoin model if available
        if LOTUS_KIT_AVAILABLE:
            try:
                # Create Lotus kit instance
                filecoin_resources = self.resources.get("filecoin", {})
                filecoin_metadata = self.metadata.get("filecoin", {})
                lotus_kit_instance = lotus_kit(
                    resources=filecoin_resources, metadata=filecoin_metadata
                )

                # Create Filecoin model
                self.storage_models["filecoin"] = FilecoinModel(
                    lotus_kit_instance=lotus_kit_instance,
                    ipfs_model=self.ipfs_model,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                logger.info("Filecoin Model initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Filecoin Model: {e}")
        else:
            logger.info("Lotus kit not available. Install with: pip install ipfs_kit_py[filecoin]")

        # Initialize Lassie model if available
        if LASSIE_KIT_AVAILABLE:
            try:
                # Create Lassie kit instance
                lassie_resources = self.resources.get("lassie", {})
                lassie_metadata = self.metadata.get("lassie", {})
                lassie_kit_instance = lassie_kit(
                    resources=lassie_resources, metadata=lassie_metadata
                )

                # Create Lassie model
                self.storage_models["lassie"] = LassieModel(
                    lassie_kit_instance=lassie_kit_instance,
                    ipfs_model=self.ipfs_model,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                logger.info("Lassie Model initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Lassie Model: {e}")
        else:
            logger.info("Lassie kit not available. Install with: pip install ipfs_kit_py[filecoin]")

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