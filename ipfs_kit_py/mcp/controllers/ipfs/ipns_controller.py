"""
IPNS Controller for the MCP server.

This controller provides an interface to the IPNS functionality of IPFS through the MCP API.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Body, Path, Query

# Import the IPNS operations
import ipfs_ipns_operations

# Configure logger
logger = logging.getLogger(__name__)

class IPNSController:
    """
    Controller for IPNS operations.

    Handles HTTP requests related to IPNS operations and delegates
    the business logic to the IPNS operations model.
    """

    def __init__(self, ipns_operations=None, key_manager=None):
        """
        Initialize the IPNS controller.

        Args:
            ipns_operations: IPNS operations model to use for operations
            key_manager: Key manager to use for key operations
        """
        self.ipns_operations = ipns_operations or ipfs_ipns_operations.get_instance()
        self.key_manager = key_manager or self.ipns_operations.key_manager
        logger.info("IPNS Controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Add key management routes
        router.add_api_route(
            "/ipfs/key/list",
            self.list_keys,
            methods=["GET"],
            summary="List IPNS keys",
            description="List all available IPNS keys",
        )

        router.add_api_route(
            "/ipfs/key/gen",
            self.create_key,
            methods=["POST"],
            summary="Create a new IPNS key",
            description="Create a new IPNS key with the specified properties",
        )

        router.add_api_route(
            "/ipfs/key/import",
            self.import_key,
            methods=["POST"],
            summary="Import an existing key for IPNS",
            description="Import an existing key for IPNS use",
        )

        router.add_api_route(
            "/ipfs/key/export/{name}",
            self.export_key,
            methods=["GET"],
            summary="Export an IPNS key",
            description="Export an IPNS key in the specified format",
        )

        router.add_api_route(
            "/ipfs/key/rename",
            self.rename_key,
            methods=["POST"],
            summary="Rename an IPNS key",
            description="Rename an IPNS key from old name to new name",
        )

        router.add_api_route(
            "/ipfs/key/rm",
            self.remove_key,
            methods=["POST"],
            summary="Remove an IPNS key",
            description="Remove an IPNS key by name",
        )

        router.add_api_route(
            "/ipfs/key/rotate",
            self.rotate_key,
            methods=["POST"],
            summary="Rotate an IPNS key",
            description="Rotate an IPNS key by creating a new one and updating records",
        )

        router.add_api_route(
            "/ipfs/key/metrics",
            self.get_key_metrics,
            methods=["GET"],
            summary="Get key operation metrics",
            description="Get performance metrics for key operations",
        )

        # Add IPNS publishing and resolution routes
        router.add_api_route(
            "/ipfs/name/publish",
            self.publish,
            methods=["POST"],
            summary="Publish an IPNS name",
            description="Publish an IPFS path to IPNS with the specified key",
        )

        router.add_api_route(
            "/ipfs/name/resolve/{name}",
            self.resolve,
            methods=["GET"],
            summary="Resolve an IPNS name",
            description="Resolve an IPNS name to its value (typically an IPFS path)",
        )

        router.add_api_route(
            "/ipfs/name/republish",
            self.republish,
            methods=["POST"],
            summary="Republish an IPNS record",
            description="Republish an IPNS record to extend its lifetime",
        )

        router.add_api_route(
            "/ipfs/name/records",
            self.get_records,
            methods=["GET"],
            summary="Get all IPNS records",
            description="Get all IPNS records published by this node",
        )

        router.add_api_route(
            "/ipfs/name/metrics",
            self.get_ipns_metrics,
            methods=["GET"],
            summary="Get IPNS metrics",
            description="Get performance metrics for IPNS operations",
        )

        # Unified metrics endpoint
        router.add_api_route(
            "/ipfs/ipns/metrics",
            self.get_metrics,
            methods=["GET"],
            summary="Get all IPNS-related metrics",
            description="Get combined performance metrics for all IPNS and key operations",
        )

        logger.info("IPNS Controller routes registered")

    async def list_keys(self, force_refresh: bool = Query(False)) -> Dict[str, Any]:
        """
        List all available IPNS keys.

        Args:
            force_refresh: Whether to force a refresh of the key cache

        Returns:
            Dictionary with list of keys
        """
        logger.debug("Listing IPNS keys")
        try:
            result = self.key_manager.list_keys(force_refresh=force_refresh)
            return result
        except Exception as e:
            logger.error(f"Error listing IPNS keys: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error listing IPNS keys: {str(e)}"
            )

    async def create_key(
        self,
        name: str = Body(...),
        key_type: str = Body("ed25519"),
        size: int = Body(2048),
        protection: str = Body("standard"),
        password: Optional[str] = Body(None),
    ) -> Dict[str, Any]:
        """
        Create a new IPNS key.

        Args:
            name: Name for the new key
            key_type: Type of key to create (RSA, ED25519, etc.)
            size: Key size (for RSA keys)
            protection: Protection level for the key
            password: Optional password for protected keys

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Creating IPNS key: {name}, type: {key_type}")
        try:
            result = self.key_manager.create_key(
                name=name,
                key_type=key_type,
                size=size,
                protection=protection,
                password=password,
            )
            return result
        except Exception as e:
            logger.error(f"Error creating IPNS key: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating IPNS key: {str(e)}"
            )

    async def import_key(
        self,
        name: str = Body(...),
        private_key: str = Body(...),
        format_type: str = Body("pem"),
        protection: str = Body("standard"),
        password: Optional[str] = Body(None),
    ) -> Dict[str, Any]:
        """
        Import an existing key for IPNS.

        Args:
            name: Name for the imported key
            private_key: Private key data (PEM string)
            format_type: Format of the key ('pem' or 'raw')
            protection: Protection level for the key
            password: Optional password for protected keys

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Importing IPNS key: {name}")
        try:
            result = self.key_manager.import_key(
                name=name,
                private_key=private_key,
                format_type=format_type,
                protection=protection,
                password=password,
            )
            return result
        except Exception as e:
            logger.error(f"Error importing IPNS key: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error importing IPNS key: {str(e)}"
            )

    async def export_key(
        self,
        name: str,
        output_format: str = Query("pem"),
        password: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        """
        Export an IPNS key.

        Args:
            name: Name of the key to export
            output_format: Format for the exported key ('pem' or 'raw')
            password: Optional password for protected keys

        Returns:
            Dictionary with the exported key
        """
        logger.debug(f"Exporting IPNS key: {name}")
        try:
            result = self.key_manager.export_key(
                name=name,
                output_format=output_format,
                password=password,
            )
            return result
        except Exception as e:
            logger.error(f"Error exporting IPNS key: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error exporting IPNS key: {str(e)}"
            )

    async def rename_key(
        self,
        old_name: str = Body(...),
        new_name: str = Body(...),
        force: bool = Body(False),
    ) -> Dict[str, Any]:
        """
        Rename an IPNS key.

        Args:
            old_name: Current name of the key
            new_name: New name for the key
            force: Whether to overwrite if new_name already exists

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Renaming IPNS key: {old_name} to {new_name}")
        try:
            result = self.key_manager.rename_key(
                old_name=old_name,
                new_name=new_name,
                force=force,
            )
            return result
        except Exception as e:
            logger.error(f"Error renaming IPNS key: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error renaming IPNS key: {str(e)}"
            )

    async def remove_key(self, name: str = Body(...)) -> Dict[str, Any]:
        """
        Remove an IPNS key.

        Args:
            name: Name of the key to remove

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Removing IPNS key: {name}")
        try:
            result = self.key_manager.remove_key(name=name)
            return result
        except Exception as e:
            logger.error(f"Error removing IPNS key: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error removing IPNS key: {str(e)}"
            )

    async def rotate_key(
        self,
        name: str = Body(...),
        new_key_type: Optional[str] = Body(None),
        size: Optional[int] = Body(None),
        preserve_old: bool = Body(True),
    ) -> Dict[str, Any]:
        """
        Rotate an IPNS key by creating a new one and updating records.

        Args:
            name: Name of the key to rotate
            new_key_type: Type for the new key (default: same as old)
            size: Size for the new key (default: same as old)
            preserve_old: Whether to preserve the old key with a timestamp suffix

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Rotating IPNS key: {name}")
        try:
            result = self.key_manager.rotate_key(
                name=name,
                new_key_type=new_key_type,
                size=size,
                preserve_old=preserve_old,
            )
            return result
        except Exception as e:
            logger.error(f"Error rotating IPNS key: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error rotating IPNS key: {str(e)}"
            )

    async def get_key_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for key operations.

        Returns:
            Dictionary with performance metrics
        """
        logger.debug("Getting key operation metrics")
        try:
            result = self.key_manager.get_metrics()
            return result
        except Exception as e:
            logger.error(f"Error getting key metrics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting key metrics: {str(e)}"
            )

    async def publish(
        self,
        cid: str = Body(...),
        key_name: str = Body("self"),
        lifetime: Optional[str] = Body(None),
        ttl: Optional[str] = Body(None),
        resolve: bool = Body(True),
    ) -> Dict[str, Any]:
        """
        Publish an IPNS name.

        Args:
            cid: The CID to publish (what the name will point to)
            key_name: Name of the key to use for publishing
            lifetime: How long the record will be valid (e.g., "24h")
            ttl: Time-to-live for caching (e.g., "15m")
            resolve: Whether to resolve the CID before publishing

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Publishing IPNS name with key: {key_name} for CID: {cid}")
        try:
            result = self.ipns_operations.publish(
                cid=cid,
                key_name=key_name,
                lifetime=lifetime,
                ttl=ttl,
                resolve=resolve,
            )
            return result
        except Exception as e:
            logger.error(f"Error publishing IPNS name: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error publishing IPNS name: {str(e)}"
            )

    async def resolve(
        self,
        name: str,
        recursive: bool = Query(True),
        dht_record: bool = Query(False),
        nocache: bool = Query(False),
    ) -> Dict[str, Any]:
        """
        Resolve an IPNS name to its value.

        Args:
            name: The IPNS name to resolve (can be a peer ID or domain with dnslink)
            recursive: Whether to recursively resolve until reaching a non-IPNS result
            dht_record: Whether to fetch the complete DHT record
            nocache: Whether to bypass cache for resolution

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Resolving IPNS name: {name}, recursive: {recursive}")
        try:
            result = self.ipns_operations.resolve(
                name=name,
                recursive=recursive,
                dht_record=dht_record,
                nocache=nocache,
            )
            return result
        except Exception as e:
            logger.error(f"Error resolving IPNS name: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error resolving IPNS name: {str(e)}"
            )

    async def republish(
        self,
        name: Optional[str] = Body(None),
        key_name: Optional[str] = Body(None),
    ) -> Dict[str, Any]:
        """
        Republish an IPNS record to extend its lifetime.

        Args:
            name: The IPNS name to republish (if None, uses key_name)
            key_name: Key name to use for republishing (if None, uses 'self')

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Republishing IPNS record: {name or key_name or 'self'}")
        try:
            result = self.ipns_operations.republish(
                name=name,
                key_name=key_name,
            )
            return result
        except Exception as e:
            logger.error(f"Error republishing IPNS record: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error republishing IPNS record: {str(e)}"
            )

    async def get_records(self) -> Dict[str, Any]:
        """
        Get all IPNS records published by this node.

        Returns:
            Dictionary with published records
        """
        logger.debug("Getting all IPNS records")
        try:
            result = self.ipns_operations.get_records()
            return result
        except Exception as e:
            logger.error(f"Error getting IPNS records: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting IPNS records: {str(e)}"
            )

    async def get_ipns_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for IPNS operations.

        Returns:
            Dictionary with performance metrics
        """
        logger.debug("Getting IPNS performance metrics")
        try:
            # Get just the IPNS metrics, not the key metrics
            all_metrics = self.ipns_operations.get_metrics()
            if isinstance(all_metrics, dict) and "metrics" in all_metrics:
                return {"success": True, "metrics": all_metrics["metrics"]}
            return all_metrics
        except Exception as e:
            logger.error(f"Error getting IPNS metrics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting IPNS metrics: {str(e)}"
            )

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get combined performance metrics for all IPNS and key operations.

        Returns:
            Dictionary with all performance metrics
        """
        logger.debug("Getting all IPNS-related metrics")
        try:
            result = self.ipns_operations.get_metrics()
            return result
        except Exception as e:
            logger.error(f"Error getting all IPNS metrics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting all IPNS metrics: {str(e)}"
            )
