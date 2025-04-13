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
            
            # Create and immediately run the initialization function
            try:
                # Using anyio.run is not appropriate here as it tries to start a new event loop
                # Instead, schedule the task properly in the current event loop
                if backend == "asyncio":
                    import asyncio
                    # Get the current event loop and create a task
                    loop = asyncio.get_event_loop()
                    loop.create_task(run_init())
                    logger.info("Created asyncio task for storage model initialization")
                elif backend == "trio":
                    # For trio, we need to use the nursery pattern, but since we don't have
                    # access to a nursery here, we'll use a background task
                    import trio
                    
                    # Track the task to prevent "coroutine was never awaited" warnings
                    if not hasattr(self, '_background_tasks'):
                        self._background_tasks = set()
                        
                    async def background_init():
                        """Run in background to avoid blocking."""
                        try:
                            async with trio.open_nursery() as nursery:
                                nursery.start_soon(run_init)
                        except Exception as e:
                            logger.error(f"Error in trio background_init: {e}")
                        finally:
                            # Remove task reference once complete
                            if hasattr(self, '_background_tasks'):
                                self._background_tasks.discard(background_init)
                    
                    # Add to tracking set
                    self._background_tasks.add(background_init)
                    
                    try:
                        # Use trio's low-level API to start this as a "system task"
                        # This is not the ideal way to do it in trio, but works as a fallback
                        # when we don't have access to a proper nursery
                        trio_token = trio.lowlevel.current_trio_token()
                        task = trio.lowlevel.spawn_system_task(
                            background_init,
                            run_sync_soon_threadsafe=trio_token.run_sync_soon
                        )
                        # Store the task for proper cleanup during shutdown
                        if not hasattr(self, '_task_tokens'):
                            self._task_tokens = []
                        self._task_tokens.append((trio_token, task))
                        logger.info("Created trio task for storage model initialization")
                    except Exception as e:
                        logger.error(f"Failed to create trio system task: {e}")
                        # Remove from tracking set on error
                        if hasattr(self, '_background_tasks'):
                            self._background_tasks.discard(background_init)
                        # Fallback to synchronous initialization
                        logger.warning("Falling back to synchronous initialization")
                        self._init_storage_models_sync()
                else:
                    # Unknown async backend, fallback to sync
                    logger.warning(f"Unknown async backend: {backend}, falling back to sync initialization")
                    self._init_storage_models_sync()
            except (AttributeError, RuntimeError, ImportError) as e:
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
        # Track any tasks created during reset
        reset_tasks = []
        backend = self.get_backend()
        
        for model_name, model in list(self.storage_models.items()):
            try:
                # Check if model has async reset method
                if hasattr(model, "reset_async") and callable(getattr(model, "reset_async")):
                    if backend == "asyncio":
                        # For asyncio, create and track tasks
                        import asyncio
                        task = asyncio.create_task(model.reset_async())
                        reset_tasks.append(task)
                    else:
                        # For other backends or unknown, await directly
                        await model.reset_async()
                else:
                    # Fall back to synchronous method
                    await anyio.to_thread.run_sync(model.reset)
                
                logger.debug(f"Reset storage model {model_name}")
            except Exception as e:
                logger.warning(f"Error resetting storage model {model_name}: {e}")
        
        # Wait for all asyncio tasks to complete if needed
        if reset_tasks and backend == "asyncio":
            import asyncio
            try:
                # Wait for all reset tasks to complete with timeout
                await asyncio.gather(*reset_tasks, return_exceptions=True)
                logger.debug(f"All {len(reset_tasks)} async reset tasks completed")
            except Exception as e:
                logger.error(f"Error waiting for reset tasks: {e}")
    
    async def shutdown_async(self):
        """
        Asynchronously shut down the storage manager and all models.
        
        This method performs comprehensive cleanup of all storage models,
        cancels any running tasks, and releases resources. It should be
        used during graceful shutdown of the MCP server.
        
        Returns:
            Dict with shutdown status information
        """
        logger.info("Shutting down Storage Manager asynchronously")
        
        result = {
            "success": True,
            "component": "storage_manager",
            "errors": [],
            "models_shutdown": 0,
            "models_failed": 0
        }
        
        # Stop any background processing tasks
        backend = self.get_backend()
        
        # Clean up asyncio background tasks if any
        if backend == "asyncio":
            if hasattr(self, '_background_tasks') and self._background_tasks:
                import asyncio
                for task in list(self._background_tasks):
                    if isinstance(task, asyncio.Task) and not task.done() and not task.cancelled():
                        try:
                            logger.debug(f"Cancelling asyncio background task: {task}")
                            task.cancel()
                        except Exception as e:
                            logger.debug(f"Non-critical error cancelling task: {e}")
                
                # Clear the set to help with garbage collection
                self._background_tasks.clear()
                
        # Handle trio tasks if any
        elif backend == "trio":
            if hasattr(self, '_task_tokens') and self._task_tokens:
                import trio
                for token, task in self._task_tokens:
                    try:
                        # There's no direct way to cancel trio system tasks
                        # Just log that we're aware of them
                        logger.debug(f"Noted trio task with token {token} for cleanup")
                    except Exception as e:
                        logger.debug(f"Non-critical error handling trio task: {e}")
                
                # Clear the list to help with garbage collection
                self._task_tokens.clear()
        
        # Clear reference to any background coroutines (for both asyncio and trio)
        if hasattr(self, '_background_tasks'):
            try:
                self._background_tasks.clear()
                logger.debug("Cleared background tasks set")
            except Exception as e:
                logger.debug(f"Non-critical error clearing background tasks: {e}")
        
        # Shut down all storage models
        for model_name, model in list(self.storage_models.items()):
            try:
                logger.debug(f"Shutting down storage model: {model_name}")
                
                # Try different shutdown methods in order of preference
                if hasattr(model, "shutdown_async") and callable(getattr(model, "shutdown_async")):
                    # Preferred: Use async shutdown
                    await model.shutdown_async()
                    logger.debug(f"Successfully shut down {model_name} model with shutdown_async")
                elif hasattr(model, "close_async") and callable(getattr(model, "close_async")):
                    # Alternative: Use async close method
                    await model.close_async()
                    logger.debug(f"Successfully shut down {model_name} model with close_async")
                elif hasattr(model, "reset_async") and callable(getattr(model, "reset_async")):
                    # Fallback: Use async reset method
                    await model.reset_async()
                    logger.debug(f"Successfully reset {model_name} model with reset_async")
                elif hasattr(model, "shutdown") and callable(getattr(model, "shutdown")):
                    # Fallback: Use sync shutdown method in async manner
                    await anyio.to_thread.run_sync(model.shutdown)
                    logger.debug(f"Successfully shut down {model_name} model with sync shutdown")
                elif hasattr(model, "close") and callable(getattr(model, "close")):
                    # Fallback: Use sync close method in async manner
                    await anyio.to_thread.run_sync(model.close)
                    logger.debug(f"Successfully shut down {model_name} model with sync close")
                elif hasattr(model, "reset") and callable(getattr(model, "reset")):
                    # Last resort: Use sync reset method in async manner
                    await anyio.to_thread.run_sync(model.reset)
                    logger.debug(f"Successfully reset {model_name} model with sync reset")
                else:
                    # No suitable method found, just log a warning
                    logger.warning(f"No shutdown method found for {model_name} model")
                
                # Count successful shutdown
                result["models_shutdown"] += 1
                
            except Exception as e:
                error_msg = f"Error shutting down {model_name} model: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                result["models_failed"] += 1
        
        # Clear all references to models to aid garbage collection
        self.storage_models.clear()
        
        # Update overall success status
        if result["errors"]:
            result["success"] = False
        
        logger.info(f"Storage Manager shutdown completed with {result['models_shutdown']} models shut down and {result['models_failed']} failures")
        return result
    
    def shutdown(self):
        """
        Synchronously shut down the storage manager and all models.
        
        This is a convenience wrapper for shutdown_async that works
        in non-async contexts. For async contexts, use shutdown_async directly.
        
        Returns:
            Dict with shutdown status information
        """
        logger.info("Shutting down Storage Manager synchronously")
        
        # Default result in case we can't run the async method
        result = {
            "success": False,
            "component": "storage_manager",
            "errors": ["Async shutdown could not be executed"],
            "models_shutdown": 0,
            "models_failed": 0,
            "sync_fallback": True
        }
        
        # Check if we can run the async method directly
        backend = self.get_backend()
        if backend:
            # We're in an async context, but being called synchronously
            logger.warning(f"Storage Manager shutdown called synchronously in async context ({backend})")
            
            if backend == "asyncio":
                # For asyncio, we can use run_until_complete
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        logger.warning("Cannot use run_until_complete in a running loop, using manual shutdown")
                        # Fall through to manual cleanup
                    else:
                        # We can use run_until_complete
                        result = loop.run_until_complete(self.shutdown_async())
                        return result
                except (RuntimeError, ImportError) as e:
                    logger.error(f"Error running asyncio shutdown: {e}")
                    # Fall through to manual cleanup
            elif backend == "trio":
                # For trio, we need a different approach
                try:
                    import trio
                    # Try to run directly if possible
                    result = trio.run(self.shutdown_async)
                    return result
                except (RuntimeError, ImportError) as e:
                    logger.error(f"Error running trio shutdown: {e}")
                    # Fall through to manual cleanup
        
        # Perform manual synchronous cleanup
        logger.info("Performing manual synchronous cleanup")
        
        # Reset result for manual process
        result = {
            "success": True,
            "component": "storage_manager",
            "errors": [],
            "models_shutdown": 0,
            "models_failed": 0,
            "sync_manual": True
        }
        
        # Clean up each model
        for model_name, model in list(self.storage_models.items()):
            try:
                logger.debug(f"Manually shutting down storage model: {model_name}")
                
                # Try different methods in order of preference
                if hasattr(model, "shutdown") and callable(getattr(model, "shutdown")):
                    model.shutdown()
                    logger.debug(f"Successfully shut down {model_name} model with shutdown")
                elif hasattr(model, "close") and callable(getattr(model, "close")):
                    model.close()
                    logger.debug(f"Successfully shut down {model_name} model with close")
                elif hasattr(model, "reset") and callable(getattr(model, "reset")):
                    model.reset()
                    logger.debug(f"Successfully reset {model_name} model with reset")
                else:
                    # No suitable method found, just log a warning
                    logger.warning(f"No shutdown method found for {model_name} model")
                
                # Count successful shutdown
                result["models_shutdown"] += 1
                
            except Exception as e:
                error_msg = f"Error shutting down {model_name} model: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                result["models_failed"] += 1
        
        # Clear all references to models
        self.storage_models.clear()
        
        # Update overall success status
        if result["errors"]:
            result["success"] = False
        
        logger.info(f"Manual storage manager shutdown completed with {result['models_shutdown']} models shut down and {result['models_failed']} failures")
        return result
    
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
            # Store task reference to prevent "coroutine was never awaited" warnings
            task_ref = None
            
            if backend == "asyncio":
                import asyncio
                task_ref = asyncio.create_task(run_async())
            elif backend == "trio":
                import trio
                # For trio, we use system task as it doesn't require a nursery
                # Get a reference to current trio token to ensure proper context
                token = trio.lowlevel.current_trio_token()
                trio.lowlevel.spawn_system_task(run_async)
            return
        
        # Synchronous implementation - directly call reset on each model
        for model_name, model in list(self.storage_models.items()):
            try:
                model.reset()
                logger.debug(f"Reset storage model {model_name}")
            except Exception as e:
                logger.warning(f"Error resetting storage model {model_name}: {e}")
        
        logger.info("All storage models reset")
        
    async def shutdown_async(self):
        """Properly shut down all storage models and clean up resources asynchronously."""
        logger.info("Shutting down storage manager (async)")
        
        # Reset all models first to ensure proper cleanup
        await self.reset_async()
        
        # Perform additional cleanup for specific model types if needed
        for model_name, model in list(self.storage_models.items()):
            try:
                # Check if model has specialized shutdown methods
                if hasattr(model, "shutdown_async") and callable(getattr(model, "shutdown_async")):
                    await model.shutdown_async()
                elif hasattr(model, "shutdown") and callable(getattr(model, "shutdown")):
                    await anyio.to_thread.run_sync(model.shutdown)
                elif hasattr(model, "close") and callable(getattr(model, "close")):
                    await anyio.to_thread.run_sync(model.close)
                    
                logger.debug(f"Shut down storage model {model_name}")
            except Exception as e:
                logger.warning(f"Error shutting down storage model {model_name}: {e}")
        
        # Clear all references to help with garbage collection
        self.storage_models.clear()
        
        logger.info("Storage manager async shutdown completed")
        
    def shutdown(self):
        """Properly shut down all storage models and clean up resources.
        
        This method supports both sync and async contexts.
        In async contexts, it delegates to shutdown_async.
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            # Log a warning - caller should use shutdown_async
            logger.warning(f"Called sync shutdown() in async context ({backend}). Consider using shutdown_async() instead")
            
            # Try our best to handle it anyway
            async def run_async():
                await self.shutdown_async()
            
            # Run the async function in the appropriate event loop
            # Store task reference to prevent "coroutine was never awaited" warnings
            task_ref = None
            
            if backend == "asyncio":
                import asyncio
                task_ref = asyncio.create_task(run_async())
            elif backend == "trio":
                import trio
                # For trio, we use system task as it doesn't require a nursery
                trio.lowlevel.spawn_system_task(run_async)
            return
            
        # Synchronous implementation
        logger.info("Shutting down storage manager")
        
        # Reset all models first (this includes basic model shutdown)
        self.reset()
        
        # Perform additional cleanup for specific model types
        for model_name, model in list(self.storage_models.items()):
            try:
                # Check for various shutdown methods
                if hasattr(model, "shutdown") and callable(getattr(model, "shutdown")):
                    model.shutdown()
                elif hasattr(model, "close") and callable(getattr(model, "close")):
                    model.close()
                    
                logger.debug(f"Shut down storage model {model_name}")
            except Exception as e:
                logger.warning(f"Error shutting down storage model {model_name}: {e}")
                
        # Clear all references to help with garbage collection
        self.storage_models.clear()
        
        logger.info("Storage manager shutdown completed")