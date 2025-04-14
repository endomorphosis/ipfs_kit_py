"""
Migration API router for MCP server.

This module provides REST API endpoints for the cross-backend migration functionality
as specified in the MCP roadmap Q2 2025 priorities.
"""

import logging
from fastapi import (
from fastapi.responses import JSONResponse
from typing import Optional
from ...models.migration import (

APIRouter,
    Body,
    Query)





    MigrationPolicy,
    MigrationRequest,
    MigrationBatchRequest,
)

logger = logging.getLogger(__name__)


def create_migration_router(migration_controller):
    """
    Create a FastAPI router for migration endpoints.

    Args:
        migration_controller: Migration controller instance

    Returns:
        FastAPI router for migration endpoints
    """
    router = APIRouter(prefix="/api/v0/migration", tags=["migration"])

    @router.get("/status")
    async def migration_service_status():
        """Get migration service status."""
        try:
            # Get migration summary
            summary = await migration_controller.migration_store.get_summary()

            # Get available backends
            available_backends = migration_controller.backend_registry.get_available_backends()

            return {
                "success": True,
                "service": "migration",
                "status": "active",
                "available_backends": available_backends,
                "migrations": summary,
                "version": "1.0.0",
            }
        except Exception as e:
            logger.error(f"Error getting migration service status: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.post("/start")
    async def start_migration(request: MigrationRequest):
        """Start a new migration between backends."""
        try:
            result = await migration_controller.create_migration(request)

            if not result.get("success", False):
                return JSONResponse(status_code=400, content=result)

            return result
        except Exception as e:
            logger.error(f"Error starting migration: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.post("/batch")
    async def batch_migration(request: MigrationBatchRequest):
        """Start a batch migration of multiple CIDs."""
        try:
            result = await migration_controller.create_batch_migration(request)

            if not result.get("success", False):
                return JSONResponse(status_code=400, content=result)

            return result
        except Exception as e:
            logger.error(f"Error starting batch migration: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.get("/status/{migration_id}")
    async def get_migration_status(migration_id: str):
        """Get status of a specific migration."""
        try:
            result = await migration_controller.get_migration(migration_id)

            if not result.get("success", False):
                return JSONResponse(status_code=404, content=result)

            return result
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.get("/list")
    async def list_migrations(
        status: Optional[str] = Query(None, description="Filter by status"),
        batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
        limit: int = Query(100, description="Maximum number of migrations to return"),
        offset: int = Query(0, description="Offset for pagination"),
    ):
        """List migrations with optional filtering."""
        try:
            result = await migration_controller.list_migrations(
                status=status, batch_id=batch_id, limit=limit, offset=offset
            )

            return result
        except Exception as e:
            logger.error(f"Error listing migrations: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.post("/policies")
    async def create_policy(policy: MigrationPolicy):
        """Create or update a migration policy."""
        try:
            result = await migration_controller.create_policy(policy)

            return result
        except Exception as e:
            logger.error(f"Error creating policy: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.get("/policies")
    async def list_policies():
        """List all available migration policies."""
        try:
            result = await migration_controller.list_policies()

            return result
        except Exception as e:
            logger.error(f"Error listing policies: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.get("/policies/{name}")
    async def get_policy(name: str):
        """Get a specific migration policy."""
        try:
            result = await migration_controller.get_policy(name)

            if not result.get("success", False):
                return JSONResponse(status_code=404, content=result)

            return result
        except Exception as e:
            logger.error(f"Error getting policy: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.delete("/policies/{name}")
    async def delete_policy(name: str):
        """Delete a migration policy."""
        try:
            result = await migration_controller.delete_policy(name)

            if not result.get("success", False):
                return JSONResponse(status_code=404, content=result)

            return result
        except Exception as e:
            logger.error(f"Error deleting policy: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.post("/estimate")
    async def estimate_migration(
        source_backend: str = Body(..., description="Source storage backend"),
        target_backend: str = Body(..., description="Target storage backend"),
        cid: str = Body(..., description="Content identifier to migrate"),
    ):
        """Estimate cost and resources for a migration."""
        try:
            result = await migration_controller.estimate_migration(
                source_backend=source_backend, target_backend=target_backend, cid=cid
            )

            if not result.get("success", False):
                return JSONResponse(status_code=400, content=result)

            return result
        except Exception as e:
            logger.error(f"Error estimating migration: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.post("/cancel/{migration_id}")
    async def cancel_migration(migration_id: str):
        """Cancel an in-progress or queued migration."""
        try:
            # Check if migration exists
            migration = await migration_controller.get_migration(migration_id)

            if not migration.get("success", False):
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False,
                        "error": f"Migration {migration_id} not found",
                    },
                )

            # Check if migration can be canceled
            status = migration.get("migration", {}).get("status")
            if status not in ["queued", "in_progress"]:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": f"Cannot cancel migration with status '{status}'",
                    },
                )

            # Update migration status to canceled
            await migration_controller._update_migration_status(
                migration_id=migration_id,
                status="canceled",
                error="Migration canceled by user",
            )

            return {
                "success": True,
                "migration_id": migration_id,
                "message": "Migration canceled successfully",
            }
        except Exception as e:
            logger.error(f"Error canceling migration: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.get("/backends/capabilities")
    async def get_backend_capabilities():
        """Get migration capabilities of all available backends."""
        try:
            backends = migration_controller.backend_registry.get_available_backends()
            capabilities = {}

            for backend in backends:
                # Get backend capabilities for migration
                capabilities[backend] = {
                    "backend_id": backend,
                    "supports_metadata": migration_controller.backend_registry.supports_feature(,
                        backend, "metadata"
                    ),
                    "supports_removal": migration_controller.backend_registry.supports_feature(,
                        backend, "removal"
                    ),
                    "supports_bulk_operations": migration_controller.backend_registry.supports_feature(,
                        backend, "bulk_operations"
                    ),
                    "cost_per_gb": 0.01,  # Default value, can be customized per backend
                    "retrieval_cost_per_gb": 0.0,  # Default value
                    "availability": 0.99,  # Default value
                    "average_latency_ms": 100,  # Default value
                }

            return {"success": True, "backends": capabilities}
        except Exception as e:
            logger.error(f"Error getting backend capabilities: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.get("/summary")
    async def get_migration_summary():
        """Get a summary of all migrations."""
        try:
            summary = await migration_controller.migration_store.get_summary()

            return {"success": True, "summary": summary}
        except Exception as e:
            logger.error(f"Error getting migration summary: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    @router.post("/cleanup")
    async def cleanup_old_migrations(
        days: int = Body(30, description="Number of days to keep records for"),
    ):
        """Clean up migration records older than specified days."""
        try:
            cleanup_count = await migration_controller.migration_store.cleanup_old_migrations(days)

            return {
                "success": True,
                "cleanup_count": cleanup_count,
                "message": f"Cleaned up {cleanup_count} old migration records",
            }
        except Exception as e:
            logger.error(f"Error cleaning up old migrations: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Internal server error: {str(e)}"},
            )

    return router
