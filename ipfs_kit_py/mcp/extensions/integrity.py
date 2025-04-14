"""
Data Integrity Extension for MCP Server

This extension integrates the Data Integrity Manager with the MCP server,
providing endpoints for verifying and monitoring content integrity across
various storage backends.
"""

import logging
import os
import sys
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Form, Query

# Configure logging
logger = logging.getLogger(__name__)

# Import our integrity manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_integrity import DataIntegrityManager

    INTEGRITY_MANAGER_AVAILABLE = True
    logger.info("Data Integrity Manager successfully imported")
except ImportError as e:
    INTEGRITY_MANAGER_AVAILABLE = False
    logger.error(f"Error importing Data Integrity Manager: {e}")

# Initialize manager
integrity_manager = None
if INTEGRITY_MANAGER_AVAILABLE:
    try:
        integrity_manager = DataIntegrityManager(
            enable_background_verification=True,
            verification_interval=43200,  # 12 hours
        )
        logger.info("Data Integrity Manager initialized")
    except Exception as e:
        logger.error(f"Error initializing Data Integrity Manager: {e}")


def create_integrity_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with integrity verification endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/integrity")

    @router.get("/status")
    async def integrity_status():
        """Get the status of the integrity verification system."""
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "status": "unavailable",
                "error": "Data Integrity Manager is not available",
            }

        stats = integrity_manager.get_statistics()
        return {"success": True, "status": "available", "statistics": stats}

    @router.post("/register")
    async def register_content(cid: str = Form(...), background_tasks: BackgroundTasks = None):
        """
        Register content for integrity tracking.

        Args:
            cid: Content ID to register
            background_tasks: Background tasks queue
        """
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "error": "Data Integrity Manager is not available",
            }

        # Fetch content from IPFS
        content_data = integrity_manager._fetch_content_from_ipfs(cid)
        if content_data is None:
            return {
                "success": False,
                "error": f"Failed to fetch content with CID {cid} from IPFS",
            }

        # Register content
        result = integrity_manager.register_content(cid, content_data)
        return result

    @router.post("/verify/{cid}")
    async def verify_content(
        cid: str, repair: bool = Form(False), background_tasks: BackgroundTasks = None
    ):
        """
        Verify content integrity.

        Args:
            cid: Content ID to verify
            repair: Whether to attempt repair if verification fails
            background_tasks: Background tasks queue
        """
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "error": "Data Integrity Manager is not available",
            }

        # Check if we should run in background
        if background_tasks is not None:
            background_tasks.add_task(integrity_manager.verify_content_integrity, cid, None, repair)
            return {
                "success": True,
                "message": f"Verification of {cid} scheduled in background",
                "cid": cid,
                "repair": repair,
                "background": True,
            }

        # Perform verification
        result = integrity_manager.verify_content_integrity(cid, repair=repair)
        return result

    @router.get("/info/{cid}")
    async def get_content_info(cid: str):
        """
        Get information about tracked content.

        Args:
            cid: Content ID
        """
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "error": "Data Integrity Manager is not available",
            }

        result = integrity_manager.get_content_info(cid)
        return result

    @router.post("/backend/register")
    async def register_backend_storage(
        cid: str = Form(...),
        backend_name: str = Form(...),
        backend_reference: str = Form(...),
    ):
        """
        Register content storage in a backend.

        Args:
            cid: Content ID
            backend_name: Backend name
            backend_reference: Backend reference
        """
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "error": "Data Integrity Manager is not available",
            }

        result = integrity_manager.register_backend_storage(cid, backend_name, backend_reference)
        return result

    @router.get("/verify/queue")
    async def get_verification_queue(max_items: int = Query(100)):
        """
        Get the list of content IDs needing verification.

        Args:
            max_items: Maximum number of items to return
        """
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "error": "Data Integrity Manager is not available",
            }

        queue = integrity_manager.get_content_needing_verification(max_items=max_items)
        return {"success": True, "queue_length": len(queue), "queue": queue}

    @router.post("/verify/batch")
    async def verify_batch(
        max_items: int = Form(50),
        repair: bool = Form(False),
        background_tasks: BackgroundTasks = None,
    ):
        """
        Schedule verification for a batch of content.

        Args:
            max_items: Maximum number of items to verify
            repair: Whether to attempt repair if verification fails
            background_tasks: Background tasks queue
        """
        if not INTEGRITY_MANAGER_AVAILABLE or integrity_manager is None:
            return {
                "success": False,
                "error": "Data Integrity Manager is not available",
            }

        queue = integrity_manager.get_content_needing_verification(max_items=max_items)

        if not queue:
            return {
                "success": True,
                "message": "No content needs verification",
                "count": 0,
            }

        # Add verification tasks to background queue
        if background_tasks is not None:
            for cid in queue:
                background_tasks.add_task(
                    integrity_manager.verify_content_integrity, cid, None, repair
                )

            return {
                "success": True,
                "message": f"Verification of {len(queue)} items scheduled in background",
                "count": len(queue),
                "repair": repair,
                "background": True,
            }
        else:
            # Start verification immediately for a few items
            results = []
            for cid in queue[:5]:  # Limit to 5 for immediate verification
                result = integrity_manager.verify_content_integrity(cid, repair=repair)
                results.append(result)

            return {
                "success": True,
                "message": f"Verified {len(results)} items immediately, {len(queue) - len(results)} more need verification",
                "count": len(queue),
                "verified_count": len(results),
                "results": results,
                "repair": repair,
                "background": False,
            }

    return router


def update_integrity_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends dictionary with integrity manager status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    available = INTEGRITY_MANAGER_AVAILABLE and integrity_manager is not None

    # Add integrity as a component
    storage_backends["integrity"] = {
        "available": available,
        "simulation": False,
        "features": (,
            {
                "content_verification": True,
                "background_verification": True,
                "data_repair": True,
                "backend_tracking": True,
            }
            if available
            else {}
        ),
    }

    # Add statistics if available
    if available:
        try:
            stats = integrity_manager.get_statistics()
            if stats.get("success", False):
                storage_backends["integrity"]["statistics"] = {
                    "total_content": stats.get("total_content", 0),
                    "verified_content": stats.get("verified_content", 0),
                    "content_with_issues": stats.get("content_with_issues", 0),
                    "integrity_percentage": stats.get("integrity_percentage", 100),
                }
        except Exception as e:
            logger.error(f"Error getting integrity statistics: {e}")

    logger.debug("Updated integrity status in storage backends")
