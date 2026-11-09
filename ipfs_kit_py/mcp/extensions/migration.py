"""
Migration extension for MCP server.

This module provides functionality for Cross-Backend Data Migration as specified
in the MCP roadmap Q2 2025 priorities.

Features:
- Seamless content transfer between storage systems
- Migration policy management and execution
- Cost-optimized storage placement
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Migration status tracking
migrations = {}


# Migration policy definitions
class MigrationPolicy(BaseModel):
    """Migration policy definition."""

    name: str = Field(..., description="Name of the migration policy")
    description: str = Field(None, description="Description of the policy")
    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    content_filter: Dict[str, Any] = Field({}, description="Content filter criteria")
    priority: int = Field(1, description="Priority level (1-5)")
    cost_optimized: bool = Field(False, description="Enable cost optimization")
    metadata_sync: bool = Field(True, description="Synchronize metadata")
    auto_clean: bool = Field(False, description="Remove from source after migration")


# Migration request model
class MigrationRequest(BaseModel):
    """Migration request definition."""

    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    cid: str = Field(..., description="Content identifier to migrate")
    policy_name: Optional[str] = Field(None, description="Migration policy to apply")
    metadata_sync: bool = Field(True, description="Synchronize metadata")
    remove_source: bool = Field(False, description="Remove from source after migration")


# Migration status model
class MigrationStatus(BaseModel):
    """Migration status information."""

    id: str = Field(..., description="Migration job ID")
    source_backend: str = Field(..., description="Source storage backend")
    target_backend: str = Field(..., description="Target storage backend")
    cid: str = Field(..., description="Content identifier")
    status: str = Field(..., description="Migration status")
    created_at: float = Field(..., description="Creation timestamp")
    updated_at: float = Field(..., description="Last update timestamp")
    progress: float = Field(0.0, description="Migration progress percentage")
    error: Optional[str] = Field(None, description="Error message if failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Migration result")


# Storage backends reference - this will be populated when extension is loaded
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True},
    "s3": {"available": False, "simulation": True},
    "filecoin": {"available": False, "simulation": True},
    "storacha": {"available": False, "simulation": True},
    "lassie": {"available": False, "simulation": True},
}

# Migration policies storage
policies = {}


# Helper functions
def get_backend_module(backend_name: str):
    """Get the backend module by name."""
    try:
        if backend_name == "huggingface": # Removed comma
            from .huggingface import huggingface_operations # Relative import

            return huggingface_operations
        elif backend_name == "s3": # Removed comma
            from .s3 import s3_operations # Relative import

            return s3_operations
        elif backend_name == "filecoin": # Removed comma
            from .filecoin import filecoin_operations # Relative import

            return filecoin_operations
        elif backend_name == "storacha": # Removed comma
            from .storacha import storacha_operations # Relative import

            return storacha_operations
        elif backend_name == "lassie": # Removed comma
            from .lassie import lassie_operations # Relative import

            return lassie_operations
        elif backend_name == "ipfs": # Removed comma
            # Use the native IPFS functions from the enhanced MCP server
            # We'll need to implement this in the context where this module is used
            return None
        else:
            logger.error(f"Unknown backend: {backend_name}")
            return None
    except ImportError as e:
        logger.error(f"Failed to import backend module {backend_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting backend module {backend_name}: {e}")
        return None


async def estimate_migration_cost(
    source_backend: str, target_backend: str, cid: str
) -> Dict[str, Any]:
    """Estimate the cost of migration between backends."""
    # Default cost estimation
    cost_estimate = {
        "estimated_cost": 0.0,
        "currency": "USD",
        "size_bytes": 0,
        "source_cost": 0.0,
        "target_cost": 0.0,
        "transfer_cost": 0.0,
        "time_estimate_seconds": 0,
    }

    try:
        # Get content size from source backend
        source_module = get_backend_module(source_backend)
        if source_module and hasattr(source_module, "get_content_info"):
            content_info = await source_module.get_content_info(cid)
            if content_info and "size" in content_info:
                size_bytes = content_info["size"]
                cost_estimate["size_bytes"] = size_bytes

                # Calculate transfer cost (simplified model)
                # More complex cost models would be implemented here in a real system
                transfer_cost = size_bytes / (1024 * 1024) * 0.0001  # $0.0001 per MB
                cost_estimate["transfer_cost"] = transfer_cost

                # Calculate target storage cost
                if target_backend == "s3": # Removed comma
                    # S3 pricing model (simplified)
                    target_cost = size_bytes / (1024 * 1024 * 1024) * 0.023  # $0.023 per GB
                    cost_estimate["target_cost"] = target_cost
                elif target_backend == "filecoin": # Removed comma
                    # Filecoin pricing model (simplified)
                    target_cost = size_bytes / (1024 * 1024 * 1024) * 0.005  # $0.005 per GB
                    cost_estimate["target_cost"] = target_cost
                elif target_backend == "storacha": # Removed comma
                    # Storacha pricing model (simplified)
                    target_cost = size_bytes / (1024 * 1024 * 1024) * 0.015  # $0.015 per GB
                    cost_estimate["target_cost"] = target_cost
                else:
                    # Default pricing model
                    target_cost = size_bytes / (1024 * 1024 * 1024) * 0.01  # $0.01 per GB
                    cost_estimate["target_cost"] = target_cost

                # Total estimated cost
                cost_estimate["estimated_cost"] = transfer_cost + target_cost

                # Time estimate (simplified)
                # Assumes 5MB/s transfer rate for simplicity
                cost_estimate["time_estimate_seconds"] = size_bytes / (5 * 1024 * 1024)
    except Exception as e:
        logger.error(f"Error estimating migration cost: {e}")

    return cost_estimate


async def perform_migration(
    migration_id: str,
    source_backend: str,
    target_backend: str,
    cid: str,
    metadata_sync: bool,
    remove_source: bool
):
    """
    Perform the actual migration between backends.

    This is run as a background task.
    """
    logger.info(f"Starting migration {migration_id}: {source_backend} → {target_backend} for {cid}")

    # Update migration status to in-progress
    migrations[migration_id]["status"] = "in_progress"
    migrations[migration_id]["updated_at"] = time.time()
    migrations[migration_id]["progress"] = 0.0

    try:
        # 1. Get content from source backend
        source_module = get_backend_module(source_backend)
        if not source_module:
            raise Exception(f"Source backend module not available: {source_backend}")

        # Update progress
        migrations[migration_id]["progress"] = 10.0
        migrations[migration_id]["updated_at"] = time.time()

        # Get content
        content = None
        if hasattr(source_module, "get_content"):
            content = await source_module.get_content(cid) # This await is correct as perform_migration is async
        elif source_backend == "ipfs": # Removed comma
            # Use IPFS cat functionality
            from subprocess import PIPE, run

            result = run(["ipfs", "cat", cid], stdout=PIPE)
            if result.returncode == 0:
                content = result.stdout
            else:
                raise Exception(f"Failed to get content from IPFS: {result.stderr}")

        if not content:
            raise Exception(f"Failed to get content from {source_backend}")

        # Update progress
        migrations[migration_id]["progress"] = 40.0
        migrations[migration_id]["updated_at"] = time.time()

        # 2. Upload to target backend
        target_module = get_backend_module(target_backend)
        if not target_module:
            raise Exception(f"Target backend module not available: {target_backend}")

        # Upload content
        target_result = None
        if hasattr(target_module, "store_content"):
            target_result = await target_module.store_content(content, cid=cid) # This await is correct
        elif target_backend == "ipfs": # Removed comma
            # Use IPFS add functionality
            import os
            import tempfile

            # Write content to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            # Add to IPFS
            from subprocess import PIPE, run

            result = run(["ipfs", "add", "-q", tmp_path], stdout=PIPE)
            os.unlink(tmp_path)

            if result.returncode == 0:
                new_cid = result.stdout.decode("utf-8").strip()
                target_result = {"cid": new_cid}
            else:
                raise Exception(f"Failed to add content to IPFS: {result.stderr}")

        if not target_result:
            raise Exception(f"Failed to store content in {target_backend}")

        # Update progress
        migrations[migration_id]["progress"] = 70.0
        migrations[migration_id]["updated_at"] = time.time()

        # 3. Sync metadata if requested
        if metadata_sync:
            # Get metadata from source
            metadata = None
            if hasattr(source_module, "get_metadata"):
                metadata = await source_module.get_metadata(cid) # This await is correct

            # Store metadata in target if available
            if metadata and hasattr(target_module, "set_metadata"):
                await target_module.set_metadata(target_result["cid"], metadata) # This await is correct

        # Update progress
        migrations[migration_id]["progress"] = 90.0
        migrations[migration_id]["updated_at"] = time.time()

        # 4. Remove from source if requested
        if remove_source:
            if hasattr(source_module, "remove_content"):
                await source_module.remove_content(cid) # This await is correct
            elif source_backend == "ipfs": # Removed comma
                # Use IPFS pin rm functionality
                from subprocess import run

                run(["ipfs", "pin", "rm", cid])

        # 5. Mark migration as completed
        migrations[migration_id]["status"] = "completed"
        migrations[migration_id]["progress"] = 100.0
        migrations[migration_id]["updated_at"] = time.time()
        migrations[migration_id]["result"] = {
            "source_cid": cid,
            "target_cid": target_result.get("cid", cid),
            "target_info": target_result,
        }

        logger.info(f"Migration {migration_id} completed successfully")

    except Exception as e:
        logger.error(f"Migration {migration_id} failed: {e}")
        migrations[migration_id]["status"] = "failed"
        migrations[migration_id]["error"] = str(e)
        migrations[migration_id]["updated_at"] = time.time()


# Create router
def create_migration_router(api_prefix: str) -> APIRouter:
    """Create FastAPI router for migration endpoints."""
    router = APIRouter(prefix=f"{api_prefix}/migration", tags=["migration"])

    # Dependency for checking backend availability
    async def verify_backends(source_backend: str, target_backend: str):
        """Verify that the requested backends are available."""
        if source_backend not in storage_backends:
            raise HTTPException(
                status_code=400,
                detail=f"Source backend '{source_backend}' not recognized",
            )
        if target_backend not in storage_backends:
            raise HTTPException(
                status_code=400,
                detail=f"Target backend '{target_backend}' not recognized",
            )

        if not storage_backends.get(source_backend, {}).get("available", False):
            raise HTTPException(
                status_code=400,
                detail=f"Source backend '{source_backend}' is not available",
            )
        if not storage_backends.get(target_backend, {}).get("available", False):
            raise HTTPException(
                status_code=400,
                detail=f"Target backend '{target_backend}' is not available",
            )

        return {"source_backend": source_backend, "target_backend": target_backend}

    @router.get("/status")
    async def migration_service_status():
        """Get migration service status."""
        # Count migrations by status
        status_counts = {"completed": 0, "in_progress": 0, "failed": 0, "queued": 0}
        for m in migrations.values():
            status = m.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1

        # Count available backends
        available_backends = [
            name for name, info in storage_backends.items() if info.get("available", False)
        ]

        return {
            "success": True,
            "service": "migration",
            "status": "active",
            "available_backends": available_backends,
            "migrations": status_counts,
            "policies": len(policies),
        }

    @router.post("/start")
    async def start_migration(
        request: MigrationRequest,
        background_tasks: BackgroundTasks,
        backends: Dict = Depends(verify_backends),
    ):
        """Start a new migration between backends."""
        # Generate a unique ID for this migration
        migration_id = f"mig_{int(time.time())}_{request.source_backend}_{request.target_backend}"

        # Apply policy if specified
        policy = None
        if request.policy_name and request.policy_name in policies:
            policy = policies[request.policy_name]
            # Override request settings with policy settings
            if policy.get("metadata_sync") is not None:
                request.metadata_sync = policy["metadata_sync"]
            if policy.get("auto_clean") is not None:
                request.remove_source = policy["auto_clean"]

        # Create migration record
        migrations[migration_id] = {
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
        }

        # Schedule the migration as a background task
        background_tasks.add_task(
            perform_migration,
            migration_id,
            request.source_backend,
            request.target_backend,
            request.cid,
            request.metadata_sync,
            request.remove_source,
        )

        return {
            "success": True,
            "migration_id": migration_id,
            "status": "queued",
            "source_backend": request.source_backend,
            "target_backend": request.target_backend,
            "cid": request.cid,
        }

    @router.get("/status/{migration_id}")
    async def get_migration_status(migration_id: str):
        """Get status of a specific migration."""
        if migration_id not in migrations:
            raise HTTPException(
                status_code=404, detail=f"Migration with ID {migration_id} not found"
            )

        return {"success": True, "migration": migrations[migration_id]}

    @router.get("/list")
    async def list_migrations(
        status: Optional[str] = Query(None, description="Filter by status"),
        limit: int = Query(100, description="Maximum number of migrations to return"),
        offset: int = Query(0, description="Offset for pagination"),
    ):
        """List migrations with optional filtering."""
        filtered_migrations = []

        for m in migrations.values():
            if status and m.get("status") != status:
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

    @router.post("/policies")
    async def create_policy(policy: MigrationPolicy):
        """Create or update a migration policy."""
        policies[policy.name] = policy.dict()

        return {
            "success": True,
            "policy": policy.name,
            "message": "Policy created successfully",
        }

    @router.get("/policies")
    async def list_policies():
        """List all available migration policies."""
        return {"success": True, "policies": policies}

    @router.get("/policies/{name}")
    async def get_policy(name: str):
        """Get a specific migration policy."""
        if name not in policies:
            raise HTTPException(status_code=404, detail=f"Policy {name} not found")

        return {"success": True, "policy": policies[name]}

    @router.delete("/policies/{name}")
    async def delete_policy(name: str):
        """Delete a migration policy."""
        if name not in policies:
            raise HTTPException(status_code=404, detail=f"Policy {name} not found")

        del policies[name]

        return {"success": True, "message": f"Policy {name} deleted successfully"}

    @router.post("/estimate")
    async def estimate_migration(
        source_backend: str,
        target_backend: str,
        cid: str,
        backends: Dict = Depends(verify_backends),
    ):
        """Estimate cost and resources for a migration."""
        cost_estimate = await estimate_migration_cost(source_backend, target_backend, cid)

        return {
            "success": True,
            "source_backend": source_backend,
            "target_backend": target_backend,
            "cid": cid,
            "estimates": cost_estimate,
        }

    @router.post("/batch")
    async def batch_migration(
        background_tasks: BackgroundTasks,
        source_backend: str,
        target_backend: str,
        cids: List[str] = Body(..., description="List of CIDs to migrate"),
        policy_name: Optional[str] = Body(None, description="Migration policy to apply"),
        metadata_sync: bool = Body(True, description="Synchronize metadata"),
        remove_source: bool = Body(False, description="Remove from source after migration"),
        backends: Dict = Depends(verify_backends),
    ):
        """Start batch migration of multiple CIDs."""
        # Verify backends
        if source_backend not in storage_backends or not storage_backends.get(
            source_backend, {}
        ).get("available", False):
            raise HTTPException(
                status_code=400,
                detail=f"Source backend '{source_backend}' not available",
            )
        if target_backend not in storage_backends or not storage_backends.get(
            target_backend, {}
        ).get("available", False):
            raise HTTPException(
                status_code=400,
                detail=f"Target backend '{target_backend}' not available",
            )

        # Apply policy if specified
        policy = None
        if policy_name and policy_name in policies:
            policy = policies[policy_name]
            # Override request settings with policy settings
            if policy.get("metadata_sync") is not None:
                metadata_sync = policy["metadata_sync"]
            if policy.get("auto_clean") is not None:
                remove_source = policy["auto_clean"]

        # Create batch migration record with a unique batch ID
        batch_id = f"batch_{int(time.time())}_{source_backend}_{target_backend}"
        migration_ids = []

        # Create individual migration jobs for each CID
        for cid in cids:
            migration_id = f"{batch_id}_{cid[:10]}"
            migrations[migration_id] = {
                "id": migration_id,
                "batch_id": batch_id,
                "source_backend": source_backend,
                "target_backend": target_backend,
                "cid": cid,
                "status": "queued",
                "created_at": time.time(),
                "updated_at": time.time(),
                "progress": 0.0,
                "policy_applied": policy_name,
                "metadata_sync": metadata_sync,
                "remove_source": remove_source,
            }

            # Schedule the migration as a background task
            background_tasks.add_task(
                perform_migration,
                migration_id,
                source_backend,
                target_backend,
                cid,
                metadata_sync,
                remove_source,
            )

            migration_ids.append(migration_id)

        return {
            "success": True,
            "batch_id": batch_id,
            "total_migrations": len(migration_ids),
            "migration_ids": migration_ids,
            "source_backend": source_backend,
            "target_backend": target_backend,
        }

    return router


# Update storage backends status
def update_migration_status(storage_backends_info: Dict[str, Any]) -> None:
    """Update the reference to storage backends status."""
    global storage_backends
    storage_backends = storage_backends_info
