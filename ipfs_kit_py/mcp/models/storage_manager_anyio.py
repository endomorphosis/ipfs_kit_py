"""
Storage Manager for MCP Server (AnyIO version).

This module provides the business logic for managing multiple storage backends
in the MCP server using AnyIO for backend-agnostic async capabilities.
"""

import logging
import time
import sniffio
import uuid

# Configure logger
logger = logging.getLogger(__name__)


class StorageManagerAnyIO:
    """Storage Manager with AnyIO support for backend-agnostic async capabilities."""
    def __init__(self, models = None, metadata = None):
        """Initialize the storage manager with models.

        Args:
            models: Dictionary of storage models to manage
            metadata: Additional metadata for configuration
        """
        self.models = models or {}
        self.metadata = metadata or {}
        self.initialized = True
        self.correlation_id = str(uuid.uuid4())
        logger.info(f"Storage Manager (AnyIO) initialized with ID: {self.correlation_id}")

    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    def _initialize_stats(self):
        """Initialize operation statistics."""
        return {
            "operations": 0,
            "operations_success": 0,
            "operations_failed": 0,
            "bytes_processed": 0,
            "start_time": time.time(),
            "last_operation": None,
            "models": {},
        }

    def _update_stats(self, model_id, result, bytes_processed = None):
        """Update operation statistics.

        Args:
            model_id: ID of the model that performed the operation
            result: Operation result
            bytes_processed: Number of bytes processed (optional)
        """
        # Ensure model exists in stats
        if model_id not in self.operation_stats["models"]:
            self.operation_stats["models"][model_id] = {
                "operations": 0,
                "operations_success": 0,
                "operations_failed": 0,
                "bytes_processed": 0,
                "last_operation": None,
            }

        # Update model stats
        model_stats = self.operation_stats["models"][model_id]
        model_stats["operations"] += 1
        self.operation_stats["operations"] += 1

        if result.get("success", False):
            model_stats["operations_success"] += 1
            self.operation_stats["operations_success"] += 1
        else:
            model_stats["operations_failed"] += 1
            self.operation_stats["operations_failed"] += 1

        if bytes_processed:
            model_stats["bytes_processed"] += bytes_processed
            self.operation_stats["bytes_processed"] += bytes_processed

        # Record last operation
        model_stats["last_operation"] = {
            "timestamp": time.time(),
            "success": result.get("success", False),
            "operation": result.get("operation", "unknown"),
        }
        self.operation_stats["last_operation"] = model_stats["last_operation"]

    async def shutdown_async(self):
        """Properly shut down all storage models and clean up resources asynchronously."""
        logger.info("Shutting down storage manager (async)")

        errors = []
        models_shutdown = 0
        models_failed = 0

        # Shut down each model
        for model_id, model in self.models.items():
            try:
                logger.info(f"Shutting down model: {model_id}")

                # Check for async shutdown method
                if hasattr(model, "shutdown_async") and callable(getattr(model, "shutdown_async")):
                    await model.shutdown_async()
                    models_shutdown += 1
                # Check for sync shutdown method
                elif hasattr(model, "shutdown") and callable(getattr(model, "shutdown")):
                    model.shutdown()
                    models_shutdown += 1
                else:
                    logger.warning(f"Model {model_id} has no shutdown method")

            except Exception as e:
                logger.error(f"Error shutting down model {model_id}: {e}")
                errors.append(f"{model_id}: {str(e)}")
                models_failed += 1

        logger.info("Storage manager async shutdown completed")

        return {
            "success": len(errors) == 0,
            "component": "storage_manager",
            "errors": errors,
            "models_shutdown": models_shutdown,
            "models_failed": models_failed,
        }

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
            "sync_fallback": True,
        }

        # Check if we can run the async method directly
        backend = self.get_backend()
        if backend:
            # We're in an async context, but being called synchronously
            logger.warning(
                f"Storage Manager shutdown called synchronously in async context ({backend})"

            if backend == "asyncio":
                # For asyncio, we can use run_until_complete
                try:
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        logger.warning(
                            "Cannot use run_until_complete in a running loop, using manual shutdown"
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

            # Define a helper function for async shutdown
            def run_async_in_background():
                import asyncio

                async def _run_async():
                    try:
                        await self.shutdown_async()
                    except Exception as e:
                        logger.error(f"Error in async shutdown: {e}")

                if backend == "asyncio":
                    asyncio.create_task(_run_async())
                elif backend == "trio":
                    import trio

                    # For trio, use system task as it doesn't require a nursery
                    trio.lowlevel.spawn_system_task(_run_async)

            # Try to run the async shutdown in the background
            try:
                run_async_in_background()
                logger.info(f"Started background {backend} task for shutdown")
            except Exception as e:
                logger.error(f"Failed to start background shutdown: {e}")

        # Perform manual synchronous cleanup
        logger.info("Performing manual synchronous cleanup")

        # Manually shut down each model
        errors = []
        models_shutdown = 0
        models_failed = 0

        for model_id, model in self.models.items():
            try:
                logger.info(f"Manually shutting down model: {model_id}")

                # Try to use synchronous shutdown method
                if hasattr(model, "shutdown") and callable(getattr(model, "shutdown")):
                    model.shutdown()
                    models_shutdown += 1
                else:
                    logger.warning(f"Model {model_id} has no synchronous shutdown method")

            except Exception as e:
                logger.error(f"Error manually shutting down model {model_id}: {e}")
                errors.append(f"{model_id}: {str(e)}")
                models_failed += 1

        result = {
            "success": len(errors) == 0,
            "component": "storage_manager",
            "errors": errors,
            "models_shutdown": models_shutdown,
            "models_failed": models_failed,
            "sync_fallback": True,
        }

        logger.info("Storage manager sync shutdown completed")
        return result

    async def reset_async(self):
        """Reset all storage models asynchronously."""
        logger.info("Resetting all storage models (async)")

        for model_id, model in self.models.items():
            try:
                # Check for async reset method
                if hasattr(model, "reset_async") and callable(getattr(model, "reset_async")):
                    await model.reset_async()
                # Check for sync reset method
                elif hasattr(model, "reset") and callable(getattr(model, "reset")):
                    model.reset()
                else:
                    logger.warning(f"Model {model_id} has no reset method")
            except Exception as e:
                logger.error(f"Error resetting model {model_id}: {e}")

        logger.info("All storage models reset")

    def reset(self):
        """Reset all storage models synchronously."""
        logger.info("Resetting all storage models")

        for model_id, model in self.models.items():
            try:
                if hasattr(model, "reset") and callable(getattr(model, "reset")):
                    model.reset()
                else:
                    logger.warning(f"Model {model_id} has no reset method")
            except Exception as e:
                logger.error(f"Error resetting model {model_id}: {e}")

        logger.info("All storage models reset")

    async def get_stats_async(self):
        """Get statistics for all storage models asynchronously."""
        stats = {
            "storage_manager": {
                "models": list(self.models.keys()),
                "model_count": len(self.models),
                "correlation_id": self.correlation_id,
}
            "models": {},
        }

        # Get stats from each model
        for model_id, model in self.models.items():
            try:
                # Check for async stats method
                if hasattr(model, "get_stats_async") and callable(
                    getattr(model, "get_stats_async")
                    model_stats = await model.get_stats_async()
                # Check for sync stats method
                elif hasattr(model, "get_stats") and callable(getattr(model, "get_stats")):
                    model_stats = model.get_stats()
                else:
                    model_stats = {"warning": "Model does not provide statistics"}

                stats["models"][model_id] = model_stats
            except Exception as e:
                logger.error(f"Error getting stats from model {model_id}: {e}")
                stats["models"][model_id] = {"error": str(e)}

        return stats

    def get_stats(self):
        """Get statistics for all storage models synchronously."""
        stats = {
            "storage_manager": {
                "models": list(self.models.keys()),
                "model_count": len(self.models),
                "correlation_id": self.correlation_id,
}
            "models": {},
        }

        # Get stats from each model
        for model_id, model in self.models.items():
            try:
                if hasattr(model, "get_stats") and callable(getattr(model, "get_stats")):
                    model_stats = model.get_stats()
                else:
                    model_stats = {"warning": "Model does not provide statistics"}

                stats["models"][model_id] = model_stats
            except Exception as e:
                logger.error(f"Error getting stats from model {model_id}: {e}")
                stats["models"][model_id] = {"error": str(e)}

        return stats
