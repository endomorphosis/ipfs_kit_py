"""
Storage Manager for MCP Server (AnyIO Version).

This module provides a unified interface for managing multiple storage backends:
- S3 (AWS S3 and compatible services)
- Hugging Face Hub (model and dataset repository)
- Storacha (Web3.Storage)
- Filecoin (Lotus API integration)
- Lassie (Filecoin/IPFS content retrieval)

It manages the creation and configuration of storage models and their integration
with the MCP server. This version uses AnyIO for backend-agnostic async capabilities.
"""

import logging
import anyio
import sniffio
from typing import Dict, Any, Optional

# Import core components
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.huggingface_kit import huggingface_kit, HUGGINGFACE_HUB_AVAILABLE
from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_KIT_AVAILABLE
from ipfs_kit_py.lassie_kit import lassie_kit, LASSIE_KIT_AVAILABLE

# Import storage models
from ipfs_kit_py.mcp.models.storage import BaseStorageModel
from ipfs_kit_py.mcp.models.storage.s3_model import S3Model
from ipfs_kit_py.mcp.models.storage.huggingface_model import HuggingFaceModel
from ipfs_kit_py.mcp.models.storage.storacha_model import StorachaModel
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
from ipfs_kit_py.mcp.models.storage.lassie_model import LassieModel

# Configure logger
logger = logging.getLogger(__name__)


class StorageManagerAnyIO:
    """Manager for storage backend models with AnyIO support."""
    
    def __init__(self, 
                ipfs_model=None, 
                cache_manager=None, 
                credential_manager=None,
                resources=None,
                metadata=None):
        """Initialize the storage manager with AnyIO support.
        
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
        
        logger.info(f"Storage Manager (AnyIO) initialized with backends: {', '.join(self.storage_models.keys())}")
    
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    async def _init_storage_models_async(self):
        """Initialize storage backend models asynchronously."""
        # Use anyio.to_thread.run_sync for potentially blocking initialization operations
        # Initialize S3 model
        try:
            # Create S3 kit instance
            s3_config = self.metadata.get("s3_config") or {}
            s3_resources = self.resources.get("s3", {})
            logger.info(f"Initializing S3 kit with resources={s3_resources}, config={s3_config}")
            
            # Run potentially blocking initialization in a thread
            s3_kit_instance = await anyio.to_thread.run_sync(
                lambda: s3_kit(resources=s3_resources, meta={"s3cfg": s3_config})
            )
            
            # Create S3 model
            self.storage_models["s3"] = S3Model(
                s3_kit_instance=s3_kit_instance,
                ipfs_model=self.ipfs_model,
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager
            )
            logger.info("S3 Model initialized (AnyIO)")
        except Exception as e:
            logger.error(f"Failed to initialize S3 Model: {e}", exc_info=True)
        
        # Initialize Hugging Face model if available
        if HUGGINGFACE_HUB_AVAILABLE:
            try:
                # Create Hugging Face kit instance
                hf_resources = self.resources.get("huggingface", {})
                hf_metadata = self.metadata.get("huggingface", {})
                
                # Run potentially blocking initialization in a thread
                hf_kit_instance = await anyio.to_thread.run_sync(
                    lambda: huggingface_kit(resources=hf_resources, metadata=hf_metadata)
                )
                
                # Create Hugging Face model
                self.storage_models["huggingface"] = HuggingFaceModel(
                    huggingface_kit_instance=hf_kit_instance,
                    ipfs_model=self.ipfs_model,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                logger.info("Hugging Face Model initialized (AnyIO)")
            except Exception as e:
                logger.warning(f"Failed to initialize Hugging Face Model: {e}")
        else:
            logger.info("Hugging Face Hub not available. Install with: pip install ipfs_kit_py[huggingface]")
        
        # Initialize Storacha model
        try:
            # Create Storacha kit instance
            storacha_resources = self.resources.get("storacha", {})
            storacha_metadata = self.metadata.get("storacha", {})
            
            # Run potentially blocking initialization in a thread
            storacha_kit_instance = await anyio.to_thread.run_sync(
                lambda: storacha_kit(resources=storacha_resources, metadata=storacha_metadata)
            )
            
            # Create Storacha model
            self.storage_models["storacha"] = StorachaModel(
                storacha_kit_instance=storacha_kit_instance,
                ipfs_model=self.ipfs_model,
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager
            )
            logger.info("Storacha Model initialized (AnyIO)")
        except Exception as e:
            logger.warning(f"Failed to initialize Storacha Model: {e}")
            
        # Initialize Filecoin model if available
        if LOTUS_KIT_AVAILABLE:
            try:
                # Create Lotus kit instance
                filecoin_resources = self.resources.get("filecoin", {})
                filecoin_metadata = self.metadata.get("filecoin", {})
                
                # Run potentially blocking initialization in a thread
                lotus_kit_instance = await anyio.to_thread.run_sync(
                    lambda: lotus_kit(resources=filecoin_resources, metadata=filecoin_metadata)
                )
                
                # Create Filecoin model
                self.storage_models["filecoin"] = FilecoinModel(
                    lotus_kit_instance=lotus_kit_instance,
                    ipfs_model=self.ipfs_model,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                logger.info("Filecoin Model initialized (AnyIO)")
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
                
                # Run potentially blocking initialization in a thread
                lassie_kit_instance = await anyio.to_thread.run_sync(
                    lambda: lassie_kit(resources=lassie_resources, metadata=lassie_metadata)
                )
                
                # Create Lassie model
                self.storage_models["lassie"] = LassieModel(
                    lassie_kit_instance=lassie_kit_instance,
                    ipfs_model=self.ipfs_model,
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                logger.info("Lassie Model initialized (AnyIO)")
            except Exception as e:
                logger.warning(f"Failed to initialize Lassie Model: {e}")
        else:
            logger.info("Lassie kit not available. Install with: pip install ipfs_kit_py[filecoin]")
    
    def _init_storage_models(self):
        """Initialize storage backend models synchronously.
        
        This is a compatibility method that delegates to the async method
        if running in an async context.
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, run the async version
            import anyio
            
            async def run_init():
                await self._init_storage_models_async()
                
            # Create a task with anyio instead of trying to create a new event loop
            try:
                # Use anyio.create_task if available (safer in running loop)
                anyio.create_task(run_init())
                logger.info("Created async task for storage model initialization")
            except (AttributeError, RuntimeError) as e:
                logger.warning(f"Could not create async task: {e}")
                # Fall back to synchronous initialization
                self._init_storage_models_sync()
        else:
            # Not in an async context, run synchronously
            self._init_storage_models_sync()
    
    def _init_storage_models_sync(self):
        """Initialize storage backend models synchronously."""
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
            logger.info("Hugging Face Hub not available. Install with: pip install ipfs_kit_py[huggingface]")
        
        # Initialize Storacha model
        try:
            # Create Storacha kit instance
            storacha_resources = self.resources.get("storacha", {})
            storacha_metadata = self.metadata.get("storacha", {})
            storacha_kit_instance = storacha_kit(resources=storacha_resources, metadata=storacha_metadata)
            
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
                lotus_kit_instance = lotus_kit(resources=filecoin_resources, metadata=filecoin_metadata)
                
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
                lassie_kit_instance = lassie_kit(resources=lassie_resources, metadata=lassie_metadata)
                
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
            "s3": "s3" in self.storage_models,
            "huggingface": "huggingface" in self.storage_models,
            "storacha": "storacha" in self.storage_models,
            "filecoin": "filecoin" in self.storage_models,
            "lassie": "lassie" in self.storage_models
        }
        return backends
    
    async def get_stats_async(self) -> Dict[str, Any]:
        """Get storage statistics for all backends asynchronously.
        
        Returns:
            Dictionary with statistics for each backend
        """
        stats = {}
        
        # Get stats from each backend
        for name, model in self.storage_models.items():
            # Check if model has async get_stats method
            if hasattr(model, "get_stats_async") and callable(getattr(model, "get_stats_async")):
                stats[name] = await model.get_stats_async()
            else:
                # Fall back to synchronous method
                stats[name] = await anyio.to_thread.run_sync(model.get_stats)
        
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics for all backends.
        
        This method supports both sync and async contexts.
        In async contexts, it delegates to get_stats_async.
        
        Returns:
            Dictionary with statistics for each backend
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            # Return a placeholder message - caller should use get_stats_async
            return {
                "message": f"In async context ({backend}), use get_stats_async() instead",
                "backend_count": len(self.storage_models)
            }
        
        # Synchronous implementation
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
    
    async def reset_async(self):
        """Reset all storage models asynchronously."""
        for model in self.storage_models.values():
            # Check if model has async reset method
            if hasattr(model, "reset_async") and callable(getattr(model, "reset_async")):
                await model.reset_async()
            else:
                # Fall back to synchronous method
                await anyio.to_thread.run_sync(model.reset)
        logger.info("All storage models reset (async)")
    
    def reset(self):
        """Reset all storage models.
        
        This method supports both sync and async contexts.
        In async contexts, it delegates to reset_async.
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            # Log a warning - caller should use reset_async
            logger.warning(f"Called sync reset() in async context ({backend}). Consider using reset_async() instead")
            # Try our best to handle it anyway
            async def run_async():
                await self.reset_async()
            
            # Run the async function in the appropriate event loop
            if backend == "asyncio":
                import asyncio
                asyncio.create_task(run_async())
            elif backend == "trio":
                import trio
                trio.lowlevel.spawn_system_task(run_async)
            return
        
        # Synchronous implementation
        for model in self.storage_models.values():
            model.reset()
        logger.info("All storage models reset")