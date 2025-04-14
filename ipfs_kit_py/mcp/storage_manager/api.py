"""
API endpoints for the Unified Storage Manager.

This module provides RESTful API endpoints for interacting with the
Unified Storage Manager, allowing applications to utilize the multi-backend
storage capabilities of the MCP system.
"""

import logging
import json
import base64
from typing import Dict, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)


class UnifiedStorageAPI:
    """API interface for the Unified Storage Manager."""
    def __init__(self, storage_manager):
        """
        Initialize the API with a storage manager instance.

        Args:
            storage_manager: Initialized UnifiedStorageManager instance
        """
        self.storage_manager = storage_manager

    def handle_request(
        self,
        method: str,
        path: str,
        params: Dict[str, Any],
        data: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Handle API requests and route them to appropriate methods.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Request path
            params: Request parameters
            data: Request body data

        Returns:
            Response dictionary
        """
        try:
            # Split path into components
            path_parts = path.strip("/").split("/")
            if not path_parts or path_parts[0] != "storage":
                return {
                    "success": False,
                    "error": "Invalid storage API endpoint",
                    "status_code": 404,
                }

            # Route request to appropriate handler
            if len(path_parts) == 1:
                # /storage endpoint - general info
                if method == "GET":
                    return self.get_storage_info()
                else:
                    return {
                        "success": False,
                        "error": "Method not allowed",
                        "status_code": 405,
                    }

            # /storage/backends endpoint
            elif len(path_parts) == 2 and path_parts[1] == "backends":
                if method == "GET":
                    return self.get_backends()
                else:
                    return {
                        "success": False,
                        "error": "Method not allowed",
                        "status_code": 405,
                    }

            # /storage/content endpoint
            elif len(path_parts) == 2 and path_parts[1] == "content":
                if method == "GET":
                    return self.list_content(params)
                elif method == "POST":
                    return self.store_content(params, data)
                else:
                    return {
                        "success": False,
                        "error": "Method not allowed",
                        "status_code": 405,
                    }

            # /storage/content/{content_id} endpoint
            elif len(path_parts) == 3 and path_parts[1] == "content":
                content_id = path_parts[2]
                if method == "GET":
                    return self.get_content(content_id, params)
                elif method == "DELETE":
                    return self.delete_content(content_id, params)
                elif method == "PUT":
                    return self.update_content_metadata(content_id, params)
                else:
                    return {
                        "success": False,
                        "error": "Method not allowed",
                        "status_code": 405,
                    }

            # /storage/content/{content_id}/replicate endpoint
            elif (
                len(path_parts) == 4 and path_parts[1] == "content" and path_parts[3] == "replicate"
            ):
                content_id = path_parts[2]
                if method == "POST":
                    return self.replicate_content(content_id, params)
                else:
                    return {
                        "success": False,
                        "error": "Method not allowed",
                        "status_code": 405,
                    }

            # /storage/stats endpoint
            elif len(path_parts) == 2 and path_parts[1] == "stats":
                if method == "GET":
                    return self.get_statistics()
                else:
                    return {
                        "success": False,
                        "error": "Method not allowed",
                        "status_code": 405,
                    }

            # Unknown endpoint
            return {
                "success": False,
                "error": f"Unknown storage API endpoint: {path}",
                "status_code": 404,
            }

        except Exception as e:
            logger.exception(f"Error handling storage API request: {e}")
            return {
                "success": False,
                "error": f"Internal server error: {str(e)}",
                "status_code": 500,
            }

    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get general information about the storage system.

        Returns:
            Response dictionary
        """
        try:
            backends = self.storage_manager.get_backends()
            stats = self.storage_manager.get_statistics()

            return {
                "success": True,
                "name": "MCP Unified Storage Manager",
                "version": "1.0.0",
                "backends_count": len(backends),
                "backends": [b["type"] for b in backends],
                "content_count": stats["content_count"],
                "total_content_size": stats["total_content_size"],
                "status_code": 200,
            }
        except Exception as e:
            logger.exception(f"Error getting storage info: {e}")
            return {
                "success": False,
                "error": f"Failed to get storage info: {str(e)}",
                "status_code": 500,
            }

    def get_backends(self) -> Dict[str, Any]:
        """
        Get information about available storage backends.

        Returns:
            Response dictionary
        """
        try:
            backends = self.storage_manager.get_backends()

            return {"success": True, "backends": backends, "status_code": 200}
        except Exception as e:
            logger.exception(f"Error getting backends: {e}")
            return {
                "success": False,
                "error": f"Failed to get backends: {str(e)}",
                "status_code": 500,
            }

    def list_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available content.

        Args:
            params: Request parameters including:
                - backend: Optional backend filter
                - prefix: Optional content ID prefix filter
                - container: Optional container filter
                - limit: Maximum number of items to return
                - offset: Number of items to skip

        Returns:
            Response dictionary
        """
        try:
            # Parse parameters
            backend = params.get("backend")
            prefix = params.get("prefix")
            container = params.get("container")
            limit = int(params.get("limit", 100))
            offset = int(params.get("offset", 0))

            # List content
            result = self.storage_manager.list_content(
                backend=backend,
                prefix=prefix,
                container=container,
                limit=limit,
                offset=offset,
            )

            if result.get("success", False):
                return {
                    "success": True,
                    "items": result.get("items", []),
                    "total": result.get("total", 0),
                    "limit": limit,
                    "offset": offset,
                    "status_code": 200,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to list content"),
                    "status_code": 400,
                }
        except Exception as e:
            logger.exception(f"Error listing content: {e}")
            return {
                "success": False,
                "error": f"Failed to list content: {str(e)}",
                "status_code": 500,
            }

    def store_content(self, params: Dict[str, Any], data: Optional[bytes]) -> Dict[str, Any]:
        """
        Store content in the optimal backend.

        Args:
            params: Request parameters including:
                - backend: Optional preferred backend
                - container: Optional container to store in
                - path: Optional path within container
                - metadata: Optional JSON string with metadata
            data: Content data to store

        Returns:
            Response dictionary
        """
        try:
            if not data:
                return {
                    "success": False,
                    "error": "No content data provided",
                    "status_code": 400,
                }

            # Parse parameters
            backend = params.get("backend")
            container = params.get("container")
            path = params.get("path")
            metadata_str = params.get("metadata")

            # Parse metadata if provided
            metadata = {}
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid metadata JSON format",
                        "status_code": 400,
                    }

            # Add content-type if provided
            content_type = params.get("content_type")
            if content_type:
                metadata["content_type"] = content_type

            # Store content
            result = self.storage_manager.store(
                data=data,
                backend_preference=backend,
                container=container,
                path=path,
                metadata=metadata,
            )

            if result.get("success", False):
                return {
                    "success": True,
                    "content_id": result.get("content_id"),
                    "backend": result.get("backend"),
                    "identifier": result.get("identifier"),
                    "container": result.get("container"),
                    "status_code": 201,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to store content"),
                    "status_code": 400,
                }
        except Exception as e:
            logger.exception(f"Error storing content: {e}")
            return {
                "success": False,
                "error": f"Failed to store content: {str(e)}",
                "status_code": 500,
            }

    def get_content(self, content_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve content by ID.

        Args:
            content_id: Content ID to retrieve
            params: Request parameters including:
                - backend: Optional preferred backend
                - info_only: If true, return only content info without data

        Returns:
            Response dictionary
        """
        try:
            # Check if only info is requested
            info_only = params.get("info_only", "").lower() in ("true", "1", "yes")

            if info_only:
                # Get content info
                result = self.storage_manager.get_content_info(content_id)

                if result.get("success", False):
                    return {
                        "success": True,
                        "content_id": content_id,
                        "content_reference": result.get("content_reference"),
                        "backend_metadata": result.get("backend_metadata", {}),
                        "status_code": 200,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", f"Content not found: {content_id}"),
                        "status_code": (,
                            404 if "not found" in result.get("error", "").lower() else 400
                        ),
                    }
            else:
                # Parse parameters
                backend = params.get("backend")

                # Retrieve content
                result = self.storage_manager.retrieve(
                    content_id=content_id, backend_preference=backend
                )

                if result.get("success", False):
                    # Convert binary data to base64 for JSON response
                    data_base64 = base64.b64encode(result.get("data", b"")).decode("utf-8")

                    return {
                        "success": True,
                        "content_id": content_id,
                        "backend": result.get("backend"),
                        "identifier": result.get("identifier"),
                        "container": result.get("container"),
                        "data_base64": data_base64,
                        "status_code": 200,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", f"Content not found: {content_id}"),
                        "status_code": (,
                            404 if "not found" in result.get("error", "").lower() else 400
                        ),
                    }
        except Exception as e:
            logger.exception(f"Error retrieving content: {e}")
            return {
                "success": False,
                "error": f"Failed to retrieve content: {str(e)}",
                "status_code": 500,
            }

    def delete_content(self, content_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete content by ID.

        Args:
            content_id: Content ID to delete
            params: Request parameters including:
                - backend: Optional specific backend to delete from

        Returns:
            Response dictionary
        """
        try:
            # Parse parameters
            backend = params.get("backend")

            # Delete content
            result = self.storage_manager.delete(content_id=content_id, backend=backend)

            if result.get("success", False):
                return {
                    "success": True,
                    "content_id": content_id,
                    "message": "Content deleted successfully",
                    "backends": result.get("backends", {}),
                    "status_code": 200,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", f"Failed to delete content: {content_id}"),
                    "status_code": 404 if "not found" in result.get("error", "").lower() else 400,
                }
        except Exception as e:
            logger.exception(f"Error deleting content: {e}")
            return {
                "success": False,
                "error": f"Failed to delete content: {str(e)}",
                "status_code": 500,
            }

    def update_content_metadata(self, content_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update content metadata.

        Args:
            content_id: Content ID to update
            params: Request parameters including:
                - metadata: JSON string with metadata to update
                - update_backends: Whether to update backend-specific metadata

        Returns:
            Response dictionary
        """
        try:
            # Parse metadata
            metadata_str = params.get("metadata")
            if not metadata_str:
                return {
                    "success": False,
                    "error": "No metadata provided",
                    "status_code": 400,
                }

            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "Invalid metadata JSON format",
                    "status_code": 400,
                }

            # Parse update_backends flag
            update_backends = params.get("update_backends", "").lower() in (
                "true",
                "1",
                "yes",
            )

            # Update metadata
            result = self.storage_manager.update_metadata(
                content_id=content_id,
                metadata=metadata,
                options={"update_backends": update_backends},
            )

            if result.get("success", False):
                return {
                    "success": True,
                    "content_id": content_id,
                    "updated_metadata": result.get("updated_metadata", {}),
                    "backend_results": result.get("backend_results", {}),
                    "status_code": 200,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", f"Failed to update metadata: {content_id}"),
                    "status_code": 404 if "not found" in result.get("error", "").lower() else 400,
                }
        except Exception as e:
            logger.exception(f"Error updating content metadata: {e}")
            return {
                "success": False,
                "error": f"Failed to update metadata: {str(e)}",
                "status_code": 500,
            }

    def replicate_content(self, content_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replicate content to another backend.

        Args:
            content_id: Content ID to replicate
            params: Request parameters including:
                - target_backend: Target backend for replication
                - container: Optional container for target backend
                - path: Optional path for target backend

        Returns:
            Response dictionary
        """
        try:
            # Parse parameters
            target_backend = params.get("target_backend")
            if not target_backend:
                return {
                    "success": False,
                    "error": "No target_backend specified",
                    "status_code": 400,
                }

            container = params.get("container")
            path = params.get("path")

            # Replicate content
            result = self.storage_manager.replicate(
                content_id=content_id,
                target_backend=target_backend,
                options={"container": container, "path": path},
            )

            if result.get("success", False):
                return {
                    "success": True,
                    "content_id": content_id,
                    "target_backend": result.get("target_backend"),
                    "location": result.get("location"),
                    "message": result.get("message", "Content replicated successfully"),
                    "status_code": 200,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", f"Failed to replicate content: {content_id}"),
                    "status_code": 404 if "not found" in result.get("error", "").lower() else 400,
                }
        except Exception as e:
            logger.exception(f"Error replicating content: {e}")
            return {
                "success": False,
                "error": f"Failed to replicate content: {str(e)}",
                "status_code": 500,
            }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Response dictionary
        """
        try:
            stats = self.storage_manager.get_statistics()

            return {"success": True, "statistics": stats, "status_code": 200}
        except Exception as e:
            logger.exception(f"Error getting statistics: {e}")
            return {
                "success": False,
                "error": f"Failed to get statistics: {str(e)}",
                "status_code": 500,
            }
