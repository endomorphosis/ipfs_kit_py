"""
Enhanced Migration Controller for MCP Server.

This controller implements the Cross-Backend Data Migration functionality
as specified in the MCP roadmap Q2 2025 priorities:
- Seamless content transfer between storage systems
- Migration policy management and execution
- Cost-optimized storage placement

This is an enhanced implementation that builds upon the migration_extension.py
to provide deeper integration with the MCP architecture.
"""

import logging
import time
import asyncio
import uuid
from typing import Dict, Any, Optional, Tuple

# Internal imports
from ipfs_kit_py.mcp.models.migration import (
    MigrationPolicy,
    MigrationRequest,
    MigrationBatchRequest
)
from ipfs_kit_py.mcp.persistence.migration_store import MigrationStore
from ipfs_kit_py.mcp.persistence.policy_store import PolicyStore

logger = logging.getLogger(__name__)


class MigrationController:
    """Controller for managing cross-backend migrations."""
    def __init__(self, backend_registry, storage_service):
        """
        Initialize the migration controller.

        Args:
            backend_registry: Registry of available storage backends
            storage_service: Service for interacting with storage backends
        """
        self.backend_registry = backend_registry
        self.storage_service = storage_service
        self.migration_store = MigrationStore()
        self.policy_store = PolicyStore()
        self._active_migrations = {}

    async def start(self):
        """Start the migration controller and load existing migrations."""
        logger.info("Starting migration controller")

        # Load stored migrations
        migrations = await self.migration_store.load_all()
        for migration_id, migration in migrations.items():
            # Resume in-progress migrations
            if migration.get("status") == "in_progress":
                migration["status"] = "interrupted"
                await self.migration_store.update(migration_id, migration)

        # Start background cleanup task
        asyncio.create_task(self._cleanup_task())

        logger.info(f"Migration controller started, loaded {len(migrations)} migrations")

    async def _cleanup_task(self):
        """Background task to clean up completed migrations."""
        while True:
            try:
                # Clean up completed migration tasks that are more than 1 hour old
                now = time.time()
                migration_ids = list(self._active_migrations.keys())
                for migration_id in migration_ids:
                    task_info = self._active_migrations[migration_id]
                    if task_info["task"].done() and (now - task_info["updated_at"]) > 3600:
                        # Remove from active migrations
                        del self._active_migrations[migration_id]
                        logger.debug(
                            f"Removed completed migration task {migration_id} from active tasks"
                        )
            except Exception as e:
                logger.error(f"Error in migration cleanup task: {e}")

            # Sleep for 5 minutes
            await asyncio.sleep(300)

    async def verify_backends(self, source_backend: str, target_backend: str) -> Tuple[bool, str]:
        """
        Verify that the requested backends are available.

        Args:
            source_backend: Source storage backend name
            target_backend: Target storage backend name

        Returns:
            Tuple of (success, error_message)
        """
        # Check that backends are registered
        if source_backend not in self.backend_registry.get_backends():
            return False, f"Source backend '{source_backend}' not recognized"
        if target_backend not in self.backend_registry.get_backends():
            return False, f"Target backend '{target_backend}' not recognized"

        # Check that backends are available
        if not self.backend_registry.is_available(source_backend):
            return False, f"Source backend '{source_backend}' is not available"
        if not self.backend_registry.is_available(target_backend):
            return False, f"Target backend '{target_backend}' is not available"

        return True, ""

    async def create_migration(self, request: MigrationRequest) -> Dict[str, Any]:
        """
        Create a new migration between backends.

        Args:
            request: Migration request details

        Returns:
            Dictionary with migration details
        """
        # Verify backends
        success, error = await self.verify_backends(request.source_backend, request.target_backend)
        if not success:
            return {"success": False, "error": error}

        # Generate a unique ID for this migration
        migration_id = f"mig_{uuid.uuid4().hex[:8]}_{int(time.time())}"

        # Apply policy if specified
        if request.policy_name:
            policy = await self.policy_store.get(request.policy_name)
            if policy:
                # Override request settings with policy settings
                if "metadata_sync" in policy:
                    request.metadata_sync = policy["metadata_sync"]
                if "auto_clean" in policy:
                    request.remove_source = policy["auto_clean"]
                if "cost_optimized" in policy:
                    request.cost_optimized = policy["cost_optimized"]

        # Create migration record
        migration = {
            "id": migration_id,
            "source_backend": request.source_backend,
            "target_backend": request.target_backend,
            "cid": request.cid,
            "status": "queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "progress": 0.0,
            "policy_applied": request.policy_name,
            "metadata_sync": request.metadata_sync,
            "remove_source": request.remove_source,
            "cost_optimized": request.cost_optimized,
        }

        # Save to store
        await self.migration_store.create(migration_id, migration)

        # Start migration task
        task = asyncio.create_task(self._perform_migration(migration_id))
        self._active_migrations[migration_id] = {
            "task": task,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

        return {
            "success": True,
            "migration_id": migration_id,
            "status": "queued",
            "source_backend": request.source_backend,
            "target_backend": request.target_backend,
            "cid": request.cid,
        }

    async def create_batch_migration(self, request: MigrationBatchRequest) -> Dict[str, Any]:
        """
        Create a batch migration for multiple CIDs.

        Args:
            request: Batch migration request details

        Returns:
            Dictionary with batch migration details
        """
        # Verify backends
        success, error = await self.verify_backends(request.source_backend, request.target_backend)
        if not success:
            return {"success": False, "error": error}

        # Create batch ID
        batch_id = f"batch_{uuid.uuid4().hex[:8]}_{int(time.time())}"

        # Apply policy if specified
        policy = None
        metadata_sync = request.metadata_sync
        remove_source = request.remove_source
        cost_optimized = request.cost_optimized

        if request.policy_name:
            policy = await self.policy_store.get(request.policy_name)
            if policy:
                # Override request settings with policy settings
                if "metadata_sync" in policy:
                    metadata_sync = policy["metadata_sync"]
                if "auto_clean" in policy:
                    remove_source = policy["auto_clean"]
                if "cost_optimized" in policy:
                    cost_optimized = policy["cost_optimized"]

        # Create migrations for each CID
        migration_ids = []

        for cid in request.cids:
            # Generate a unique ID for this migration
            migration_id = f"{batch_id}_{uuid.uuid4().hex[:6]}"

            # Create migration record
            migration = {
                "id": migration_id,
                "batch_id": batch_id,
                "source_backend": request.source_backend,
                "target_backend": request.target_backend,
                "cid": cid,
                "status": "queued",
                "created_at": time.time(),
                "updated_at": time.time(),
                "progress": 0.0,
                "policy_applied": request.policy_name,
                "metadata_sync": metadata_sync,
                "remove_source": remove_source,
                "cost_optimized": cost_optimized,
            }

            # Save to store
            await self.migration_store.create(migration_id, migration)

            # Start migration task
            task = asyncio.create_task(self._perform_migration(migration_id))
            self._active_migrations[migration_id] = {
                "task": task,
                "created_at": time.time(),
                "updated_at": time.time(),
            }

            migration_ids.append(migration_id)

        return {
            "success": True,
            "batch_id": batch_id,
            "total_migrations": len(migration_ids),
            "migration_ids": migration_ids,
            "source_backend": request.source_backend,
            "target_backend": request.target_backend,
        }

    async def get_migration(self, migration_id: str) -> Dict[str, Any]:
        """
        Get details of a specific migration.

        Args:
            migration_id: ID of the migration

        Returns:
            Dictionary with migration details
        """
        migration = await self.migration_store.get(migration_id)
        if not migration:
            return {
                "success": False,
                "error": f"Migration with ID {migration_id} not found",
            }

        return {"success": True, "migration": migration}

    async def list_migrations(
        self,
        status: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List migrations with optional filtering.

        Args:
            status: Filter by status
            batch_id: Filter by batch ID
            limit: Maximum number of migrations to return
            offset: Offset for pagination

        Returns:
            Dictionary with list of migrations
        """
        # Get all migrations
        all_migrations = await self.migration_store.load_all()
        migrations_list = list(all_migrations.values())

        # Apply filters
        filtered_migrations = []
        for m in migrations_list:
            if status and m.get("status") != status:
                continue
            if batch_id and m.get("batch_id") != batch_id:
                continue
            filtered_migrations.append(m)

        # Sort by creation time, newest first
        filtered_migrations.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        # Apply pagination
        paginated = filtered_migrations[offset : offset + limit]

        return {
            "success": True,
            "total": len(filtered_migrations),
            "offset": offset,
            "limit": limit,
            "migrations": paginated,
        }

    async def create_policy(self, policy: MigrationPolicy) -> Dict[str, Any]:
        """
        Create or update a migration policy.

        Args:
            policy: Migration policy details

        Returns:
            Dictionary with policy creation result
        """
        # Convert to dictionary
        policy_dict = policy.dict()

        # Save to store
        await self.policy_store.create(policy.name, policy_dict)

        return {
            "success": True,
            "policy": policy.name,
            "message": "Policy created successfully",
        }

    async def get_policy(self, name: str) -> Dict[str, Any]:
        """
        Get a specific migration policy.

        Args:
            name: Name of the policy

        Returns:
            Dictionary with policy details
        """
        policy = await self.policy_store.get(name)
        if not policy:
            return {"success": False, "error": f"Policy {name} not found"}

        return {"success": True, "policy": policy}

    async def list_policies(self) -> Dict[str, Any]:
        """
        List all available migration policies.

        Returns:
            Dictionary with list of policies
        """
        policies = await self.policy_store.load_all()

        return {"success": True, "policies": policies}

    async def delete_policy(self, name: str) -> Dict[str, Any]:
        """
        Delete a migration policy.

        Args:
            name: Name of the policy

        Returns:
            Dictionary with deletion result
        """
        policy = await self.policy_store.get(name)
        if not policy:
            return {"success": False, "error": f"Policy {name} not found"}

        await self.policy_store.delete(name)

        return {"success": True, "message": f"Policy {name} deleted successfully"}

    async def estimate_migration(
        self, source_backend: str, target_backend: str, cid: str
    ) -> Dict[str, Any]:
        """
        Estimate cost and resources for a migration.

        Args:
            source_backend: Source storage backend name
            target_backend: Target storage backend name
            cid: Content identifier to migrate

        Returns:
            Dictionary with migration estimate
        """
        # Verify backends
        success, error = await self.verify_backends(source_backend, target_backend)
        if not success:
            return {"success": False, "error": error}

        # Get content information from source backend
        try:
            content_info = await self.storage_service.get_content_info(source_backend, cid)

            # Get size information
            size_bytes = content_info.get("size", 0)

            # Calculate estimated costs
            transfer_cost = size_bytes / (1024 * 1024) * 0.0001  # $0.0001 per MB

            # Calculate target storage cost
            target_cost = 0.0
            if target_backend == "s3":
                # S3 pricing model (simplified)
                target_cost = size_bytes / (1024 * 1024 * 1024) * 0.023  # $0.023 per GB
            elif target_backend == "filecoin":
                # Filecoin pricing model (simplified)
                target_cost = size_bytes / (1024 * 1024 * 1024) * 0.005  # $0.005 per GB
            elif target_backend == "storacha":
                # Storacha pricing model (simplified)
                target_cost = size_bytes / (1024 * 1024 * 1024) * 0.015  # $0.015 per GB
            else:
                # Default pricing model
                target_cost = size_bytes / (1024 * 1024 * 1024) * 0.01  # $0.01 per GB

            # Calculate time estimate (simplified)
            # Assumes 5MB/s transfer rate for simplicity
            time_estimate_seconds = size_bytes / (5 * 1024 * 1024) if size_bytes > 0 else 1

            # Create estimate
            estimate = {
                "estimated_cost": transfer_cost + target_cost,
                "currency": "USD",
                "size_bytes": size_bytes,
                "source_cost": 0.0,  # Source cost is typically 0 for retrieval
                "target_cost": target_cost,
                "transfer_cost": transfer_cost,
                "time_estimate_seconds": time_estimate_seconds,
                "theoretical_bandwidth": "5 MB/s",
                "reliability": "high" if size_bytes < 1073741824 else "medium",  # Less reliable for files over 1GB
            }

            return {
                "success": True,
                "source_backend": source_backend,
                "target_backend": target_backend,
                "cid": cid,
                "estimates": estimate,
            }
        except Exception as e:
            logger.error(f"Error estimating migration: {e}")
            return {"success": False, "error": f"Error estimating migration: {str(e)}"}

    async def _update_migration_status(
        self,
        migration_id: str,
        status: str,
        progress: float = None,
        error: str = None,
        result: Dict[str, Any] = None,
    ) -> None:
        """
        Update the status of a migration.

        Args:
            migration_id: ID of the migration
            status: New status
            progress: Optional progress percentage
            error: Optional error message
            result: Optional result data
        """
        migration = await self.migration_store.get(migration_id)
        if not migration:
            logger.error(f"Cannot update non-existent migration {migration_id}")
            return

        # Update fields
        migration["status"] = status
        migration["updated_at"] = time.time()

        if progress is not None:
            migration["progress"] = progress

        if error is not None:
            migration["error"] = error

        if result is not None:
            migration["result"] = result

        # Save updated migration
        await self.migration_store.update(migration_id, migration)

    async def _perform_migration(self, migration_id: str) -> None:
        """
        Perform the actual migration between backends.

        Args:
            migration_id: ID of the migration
        """
        # Get migration details
        migration = await self.migration_store.get(migration_id)
        if not migration:
            logger.error(f"Cannot perform non-existent migration {migration_id}")
            return

        logger.info(
            f"Starting migration {migration_id}: "
            f"{migration['source_backend']} → {migration['target_backend']} "
            f"for {migration['cid']}"
        )

        # Update migration status to in-progress
        await self._update_migration_status(migration_id, "in_progress", 0.0)

        try:
            # 1. Check if we need to perform cost optimization
            if migration.get("cost_optimized", False):
                # Get cost estimate
                estimate = await self.estimate_migration(
                    migration["source_backend"],
                    migration["target_backend"],
                    migration["cid"],
                )

                if not estimate.get("success", False):
                    await self._update_migration_status(
                        migration_id,
                        "failed",
                        0.0,
                        f"Failed to get cost estimate: {estimate.get('error')}",
                    )
                    return

                # Check if migration is cost-effective
                cost = estimate.get("estimates", {}).get("estimated_cost", 0.0)
                size_bytes = estimate.get("estimates", {}).get("size_bytes", 0)

                # Simple heuristic: If cost is too high for the data size, abort
                cost_efficiency = (size_bytes / (1024 * 1024)) / cost if cost > 0 else float("inf")
                if cost_efficiency < 10:  # Less than 10MB per dollar
                    await self._update_migration_status(
                        migration_id, "aborted", 0.0, "Migration not cost-effective"
                    )
                    return

            # Update progress
            await self._update_migration_status(migration_id, "in_progress", 10.0)

            # 2. Get content from source backend
            try:
                content = await self.storage_service.get_content(
                    migration["source_backend"], migration["cid"]
                )

                if not content:
                    await self._update_migration_status(
                        migration_id,
                        "failed",
                        10.0,
                        f"Failed to get content from {migration['source_backend']}",
                    )
                    return
            except Exception as e:
                await self._update_migration_status(
                    migration_id,
                    "failed",
                    10.0,
                    f"Error getting content from {migration['source_backend']}: {str(e)}",
                )
                return

            # Update progress
            await self._update_migration_status(migration_id, "in_progress", 40.0)

            # 3. Get metadata if needed
            metadata = None
            if migration.get("metadata_sync", True):
                try:
                    metadata = await self.storage_service.get_metadata(
                        migration["source_backend"], migration["cid"]
                    )
                except Exception as e:
                    logger.warning(f"Error getting metadata for {migration_id}: {e}")
                    # Continue without metadata

            # 4. Store in target backend
            try:
                target_result = await self.storage_service.store_content(
                    migration["target_backend"], content, migration["cid"]
                )

                if not target_result:
                    await self._update_migration_status(
                        migration_id,
                        "failed",
                        50.0,
                        f"Failed to store content in {migration['target_backend']}",
                    )
                    return
            except Exception as e:
                await self._update_migration_status(
                    migration_id,
                    "failed",
                    50.0,
                    f"Error storing content in {migration['target_backend']}: {str(e)}",
                )
                return

            # Update progress
            await self._update_migration_status(migration_id, "in_progress", 70.0)

            # 5. Store metadata if available
            if metadata and migration.get("metadata_sync", True):
                try:
                    await self.storage_service.set_metadata(
                        migration["target_backend"],
                        target_result.get("cid", migration["cid"]),
                        metadata,
                    )
                except Exception as e:
                    logger.warning(f"Error setting metadata for {migration_id}: {e}")
                    # Continue without metadata

            # 6. Remove from source if requested
            if migration.get("remove_source", False):
                try:
                    await self.storage_service.remove_content(
                        migration["source_backend"], migration["cid"]
                    )
                except Exception as e:
                    logger.warning(f"Error removing content from source for {migration_id}: {e}")
                    # Continue with migration marked as successful

            # 7. Mark migration as completed
            await self._update_migration_status(
                migration_id,
                "completed",
                100.0,
                None,
                {
                    "source_cid": migration["cid"],
                    "target_cid": target_result.get("cid", migration["cid"]),
                    "target_info": target_result,
                    "completed_at": time.time(),
                },
            )

            logger.info(f"Migration {migration_id} completed successfully")

        except Exception as e:
            logger.error(f"Migration {migration_id} failed with unexpected error: {e}")
            await self._update_migration_status(
                migration_id, "failed", None, f"Unexpected error: {str(e)}"
            )