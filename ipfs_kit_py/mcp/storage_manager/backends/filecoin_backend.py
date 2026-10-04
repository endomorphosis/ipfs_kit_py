"""
Filecoin backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Filecoin,
allowing the Unified Storage Manager to interact with the Filecoin network.
"""

import logging
import time
import os
import tempfile
from typing import Dict, Any, Optional, Union, BinaryIO
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class FilecoinBackend(BackendStorage):
    """Filecoin backend implementation."""
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize Filecoin backend."""
        super().__init__(StorageBackendType.FILECOIN, resources, metadata)

        # Import dependencies
        try:
            from ipfs_kit_py.lotus_kit import lotus_kit

            self.lotus = lotus_kit(resources, metadata)
            self.mode = "lotus"
            logger.info("Initialized Filecoin backend with Lotus mode")
        except ImportError:
            logger.warning("Failed to initialize Lotus client, trying Filecoin Storage")
            try:
                from ipfs_kit_py.filecoin_storage import filecoin_storage

                self.filecoin = filecoin_storage(resources, metadata)
                self.mode = "filecoin_storage"
                logger.info("Initialized Filecoin backend with filecoin_storage mode")
            except ImportError:
                self.mode = "unavailable"
                logger.error(
                    "Failed to initialize Filecoin backend: lotus_kit and filecoin_storage not available"
                )
                raise ImportError("No Filecoin client implementation available")

        # Configuration
        self.default_miner = metadata.get("default_miner")
        self.replication_count = metadata.get("replication_count", 1)
        self.verify_deals = metadata.get("verify_deals", True)
        self.max_price = metadata.get("max_price")
        self.deal_duration = metadata.get("deal_duration", 518400)  # Default: 180 days
        
    def get_name(self) -> str:
        """Get the name of this backend implementation.
        
        Returns:
            String representation of the backend name
        """
        return "filecoin"

    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store data in Filecoin.

        Args:
            data: Data to store (bytes, file-like object, or string)
            container: Optional miner to use for storage (overrides default_miner)
            path: Optional path/name for the stored content
            options: Additional options for storage

        Returns:
            Dictionary with operation result
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return {
                "success": False,
                "error": "Filecoin backend unavailable",
                "backend": self.get_name(),
            }

        # Get storage parameters
        miner = container or self.default_miner or options.get("miner")
        replication = options.get("replication_count", self.replication_count)
        max_price = options.get("max_price", self.max_price)
        duration = options.get("deal_duration", self.deal_duration)

        # Use temporary file for data
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                temp_file = tmp.name

                if isinstance(data, str):
                    # If data is a string, encode to bytes first
                    tmp.write(data.encode("utf-8"))
                elif isinstance(data, bytes):
                    # Write bytes to temporary file
                    tmp.write(data)
                else:
                    # Write file-like object to temporary file
                    data.seek(0)
                    while True:
                        chunk = data.read(8192)
                        if not chunk:
                            break
                        tmp.write(chunk)
                    data.seek(0)  # Reset file pointer

            # Store data in Filecoin
            if self.mode == "lotus":
                # Use Lotus client
                if miner:
                    # Store with specific miner
                    result = self.lotus.lotus_client_deal(
                        file_path=temp_file,
                        miner=miner,
                        duration=duration,
                        max_price=max_price,
                    )
                else:
                    # Store with automatically selected miners
                    result = self.lotus.lotus_client_deal_auto(
                        file_path=temp_file,
                        replication=replication,
                        duration=duration,
                        max_price=max_price,
                    )
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_store_file(
                    file_path=temp_file,
                    miner=miner,
                    replication=replication,
                    duration=duration,
                    max_price=max_price,
                )

            if result.get("success", False):
                # Extract CID and deal info
                cid = result.get("cid") or result.get("payload_cid")
                deals = result.get("deals", [])

                # Add MCP metadata if supported
                if options.get("add_metadata", True):
                    metadata = {
                        "mcp_added": time.time(),
                        "mcp_backend": self.get_name(),
                        "deals": deals,
                    }
                    # Add metadata (implementation may vary)
                    if self.mode == "lotus":
                        self.lotus.lotus_add_metadata(cid, metadata)
                    else:
                        self.filecoin.filecoin_add_metadata(cid, metadata)

                return {
                    "success": True,
                    "identifier": cid,
                    "backend": self.get_name(),
                    "deals": deals,
                    "details": result,
                }

            return {
                "success": False,
                "error": result.get("error", "Failed to store data in Filecoin"),
                "backend": self.get_name(),
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Error storing data in Filecoin: {e}")
            return {"success": False, "error": str(e), "backend": self.get_name()}
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")

    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from Filecoin.

        Args:
            identifier: CID of the content to retrieve
            container: Not used for Filecoin but included for interface compatibility
            options: Additional options for retrieval

        Returns:
            Dictionary with operation result and data
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return {
                "success": False,
                "error": "Filecoin backend unavailable",
                "backend": self.get_name(),
            }

        # Use temporary file for download
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                temp_file = tmp.name

            # Retrieve data from Filecoin
            if self.mode == "lotus":
                # Use Lotus client
                result = self.lotus.lotus_client_retrieve(cid=identifier, output_path=temp_file)
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_retrieve_file(cid=identifier, output_path=temp_file)

            if result.get("success", False):
                # Read the data
                with open(temp_file, "rb") as f:
                    data = f.read()

                return {
                    "success": True,
                    "data": data,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": result,
                }

            return {
                "success": False,
                "error": result.get("error", "Failed to retrieve data from Filecoin"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Error retrieving data from Filecoin: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier,
            }
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")

    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete data from Filecoin.

        Note: Filecoin deals cannot be deleted once confirmed, so this operation has limitations.
        It may cancel pending deals but cannot remove sealed deals.

        Args:
            identifier: CID of the content to delete
            container: Not used for Filecoin but included for interface compatibility
            options: Additional options for deletion

        Returns:
            Dictionary with operation result
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return {
                "success": False,
                "error": "Filecoin backend unavailable",
                "backend": self.get_name(),
            }

        try:
            # Attempt to cancel any pending deals
            if self.mode == "lotus":
                # Use Lotus client to cancel pending deals
                result = self.lotus.lotus_client_cancel_pending_deals(identifier)
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_cancel_deals(identifier)

            if (
                not result.get("success", False)
                and "sealed deals cannot be cancelled" in result.get("error", "").lower()
            ):
                # Content is in sealed deals which cannot be deleted
                logger.warning(
                    f"Content {identifier} has sealed deals which cannot be cancelled in Filecoin"
                )
                return {
                    "success": True,  # Report success to avoid errors in the calling code
                    "warning": "Content has sealed deals that cannot be deleted from Filecoin",
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "cancelled_deals": result.get("cancelled_deals", []),
                    "remaining_deals": result.get("remaining_deals", []),
                }

            return {
                "success": result.get("success", False),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Error deleting data from Filecoin: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier,
            }

    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List items in Filecoin.

        Args:
            container: Optional miner ID to filter by
            prefix: Optional CID prefix filter
            options: Additional listing options

        Returns:
            Dictionary with operation result and items
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return {
                "success": False,
                "error": "Filecoin backend unavailable",
                "backend": self.get_name(),
            }

        try:
            # List deals
            miner = container  # Use container parameter as miner filter

            if self.mode == "lotus":
                # Use Lotus client
                result = self.lotus.lotus_client_list_deals(miner)
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_list_deals(miner)

            if result.get("success", False):
                items = []
                deals = result.get("deals", [])

                # Process and filter deals
                for deal in deals:
                    cid = deal.get("payload_cid") or deal.get("cid")

                    # Filter by prefix if provided
                    if prefix and cid and not cid.startswith(prefix):
                        continue

                    items.append(
                        {
                            "identifier": cid,
                            "deal_id": deal.get("deal_id"),
                            "state": deal.get("state"),
                            "miner": deal.get("miner"),
                            "size": deal.get("size", 0),
                            "price": deal.get("price"),
                            "duration": deal.get("duration"),
                            "start_time": deal.get("start_time"),
                            "backend": self.get_name(),
                        }
                    )

                return {
                    "success": True,
                    "items": items,
                    "backend": self.get_name(),
                    "details": result,
                }

            return {
                "success": False,
                "error": result.get("error", "Failed to list deals in Filecoin"),
                "backend": self.get_name(),
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Error listing deals in Filecoin: {e}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if content exists in Filecoin.

        Args:
            identifier: CID to check
            container: Optional miner ID to check specifically
            options: Additional options

        Returns:
            True if content exists in at least one active deal
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return False

        try:
            # Check if content exists in deals
            miner = container  # Use container parameter as miner filter

            if self.mode == "lotus":
                # Use Lotus client
                result = self.lotus.lotus_client_find_deal(identifier, miner)
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_check_deal(identifier, miner)

            return result.get("success", False) and result.get("active_deals", 0) > 0

        except Exception as e:
            logger.exception(f"Error checking if content exists in Filecoin: {e}")
            return False

    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get metadata for Filecoin content.

        Args:
            identifier: CID to get metadata for
            container: Optional miner ID to filter by
            options: Additional options

        Returns:
            Dictionary with metadata information
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return {
                "success": False,
                "error": "Filecoin backend unavailable",
                "backend": self.get_name(),
            }

        try:
            # Get deal information
            miner = container  # Use container parameter as miner filter

            if self.mode == "lotus":
                # Use Lotus client
                result = self.lotus.lotus_client_find_deal(identifier, miner)
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_check_deal(identifier, miner)

            if result.get("success", False):
                deals = result.get("deals", [])
                active_deals = result.get("active_deals", 0)

                # Extract metadata from deals
                deal_metadata = []
                total_size = 0
                active_miners = set()

                for deal in deals:
                    deal_metadata.append(
                        {
                            "deal_id": deal.get("deal_id"),
                            "state": deal.get("state"),
                            "miner": deal.get("miner"),
                            "size": deal.get("size", 0),
                            "price": deal.get("price"),
                            "duration": deal.get("duration"),
                            "start_time": deal.get("start_time"),
                            "end_time": deal.get("end_time"),
                            "sector": deal.get("sector"),
                        }
                    )

                    if deal.get("state") in ["active", "sealed"]:
                        active_miners.add(deal.get("miner"))
                        if total_size == 0:  # Only count size once
                            total_size = deal.get("size", 0)

                # Create metadata summary
                metadata = {
                    "size": total_size,
                    "active_deals": active_deals,
                    "total_deals": len(deals),
                    "active_miners": list(active_miners),
                    "deals": deal_metadata,
                    "backend": self.get_name(),
                }

                # Try to get additional metadata if available
                try:
                    if self.mode == "lotus":
                        custom_metadata = self.lotus.lotus_get_metadata(identifier) or {}
                        if custom_metadata.get("success", False):
                            metadata.update(custom_metadata.get("metadata", {}))
                    else:
                        custom_metadata = self.filecoin.filecoin_get_metadata(identifier) or {}
                        if custom_metadata.get("success", False):
                            metadata.update(custom_metadata.get("metadata", {}))
                except Exception as e:
                    logger.warning(f"Failed to get custom metadata for {identifier}: {e}")

                return {
                    "success": True,
                    "metadata": metadata,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": result,
                }

            return {
                "success": False,
                "error": result.get("error", "Failed to get metadata from Filecoin"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Error getting metadata from Filecoin: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier,
            }

    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for Filecoin content.

        Note: Filecoin doesn't natively support metadata updates for immutable content,
        so this implementation has limitations.

        Args:
            identifier: CID to update metadata for
            metadata: New metadata to set
            container: Not used for Filecoin but included for interface compatibility
            options: Additional options

        Returns:
            Dictionary with operation result
        """
        options = options or {}

        # Check if the backend is available
        if self.mode == "unavailable":
            return {
                "success": False,
                "error": "Filecoin backend unavailable",
                "backend": self.get_name(),
            }

        try:
            # Update metadata (implementation varies)
            if self.mode == "lotus":
                # Use Lotus client
                result = self.lotus.lotus_add_metadata(identifier, metadata)
            else:
                # Use Filecoin Storage client
                result = self.filecoin.filecoin_add_metadata(identifier, metadata)

            return {
                "success": result.get("success", False),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Error updating metadata in Filecoin: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier,
            }
            
    # BackendStorage interface implementations
    def add_content(self, content: Union[str, bytes, BinaryIO], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add content to the storage backend.
        
        Args:
            content: Content to store (can be a path, bytes, or file-like object)
            metadata: Optional metadata for the content
            
        Returns:
            Dict with operation result including content ID
        """
        # Convert metadata format if needed
        options = {}
        if metadata:
            options.update(metadata)
            
        # Delegate to the underlying store method
        return self.store(content, options=options)
        
    def get_content(self, content_id: str) -> Dict[str, Any]:
        """Retrieve content from the storage backend.
        
        Args:
            content_id: ID of the content to retrieve
            
        Returns:
            Dict with operation result including content data
        """
        # Delegate to the underlying retrieve method
        return self.retrieve(content_id)
        
    def remove_content(self, content_id: str) -> Dict[str, Any]:
        """Remove content from the storage backend.
        
        Args:
            content_id: ID of the content to remove
            
        Returns:
            Dict with operation result
        """
        # Delegate to the underlying delete method
        return self.delete(content_id)