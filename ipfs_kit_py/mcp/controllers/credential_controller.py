"""
Credential Controller for the MCP server.

This controller handles HTTP requests related to credential management for
various storage services like IPFS, S3, Storacha, and Filecoin.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import Pydantic models for request/response validation


# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class CredentialBaseRequest(BaseModel):
    """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Base request model for credential operations."""

    name: str = Field(
        ..., description="Name for this credential set (e.g., 'default', 'production')"
    )


class GenericCredentialRequest(BaseModel):
    """Generic request model for credential operations."""

    service: str = Field(..., description="Service identifier (ipfs, s3, storacha, filecoin)")
    name: str = Field(
        ..., description="Name for this credential set (e.g., 'default', 'production')"
    )
    values: Dict[str, Any] = Field(..., description="Credential values appropriate for the service")


class S3CredentialRequest(CredentialBaseRequest):
    """Request model for S3 credentials."""

    aws_access_key_id: str = Field(..., description="AWS access key ID")
    aws_secret_access_key: str = Field(..., description="AWS secret access key")
    endpoint_url: Optional[str] = Field(
        None, description="Optional endpoint URL for custom S3 services"
    )
    region: Optional[str] = Field(None, description="Optional AWS region")


class StorachaCredentialRequest(CredentialBaseRequest):
    """Request model for Storacha/W3 credentials."""

    api_token: str = Field(..., description="W3/Storacha API token")
    space_did: Optional[str] = Field(None, description="Optional space DID for scoped access")


class FilecoinCredentialRequest(CredentialBaseRequest):
    """Request model for Filecoin credentials."""

    api_key: str = Field(..., description="Filecoin API key")
    api_secret: Optional[str] = Field(None, description="Optional API secret for some services")
    wallet_address: Optional[str] = Field(None, description="Optional Filecoin wallet address")
    provider: Optional[str] = Field(
        None, description="Optional provider name (e.g., 'estuary', 'lotus', 'glif')"
    )


class IPFSCredentialRequest(CredentialBaseRequest):
    """Request model for IPFS credentials."""

    identity: Optional[str] = Field(None, description="IPFS identity")
    api_address: Optional[str] = Field(None, description="IPFS API address")
    cluster_secret: Optional[str] = Field(None, description="IPFS Cluster secret")


class CredentialResponse(BaseModel):
    """Response model for credential operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    operation: str = Field(..., description="Operation performed")
    name: str = Field(..., description="Name of the credential set")
    service: str = Field(..., description="Service identifier (ipfs, s3, storacha, filecoin)")
    timestamp: float = Field(..., description="Timestamp of the operation")


class CredentialInfoResponse(BaseModel):
    """Response model for credential information."""

    success: bool = Field(..., description="Whether the operation was successful")
    credentials: List[Dict[str, Any]] = Field(
        ..., description="List of credential information without secrets"
    )
    count: int = Field(..., description="Number of credentials found")
    timestamp: float = Field(..., description="Timestamp of the operation")


class CredentialController:
    """
    Controller for credential management operations.

    Handles HTTP requests related to credential management for various storage services.
    """

    def __init__(self, credential_manager):
        """
        Initialize the credential controller.

        Args:
            credential_manager: Credential manager to use for operations
        """
        self.credential_manager = credential_manager
        self.is_shutting_down = False
        logger.info("Credential Controller initialized")

    async def shutdown(self):
        """
        Safely shut down the Credential Controller.

        This method ensures proper cleanup of credential-related resources.
        """
        logger.info("Credential Controller shutdown initiated")

        # Signal that we're shutting down to prevent new operations
        self.is_shutting_down = True

        # Track any errors during shutdown
        errors = []

        # 1. Secure credentials in memory
        try:
            # If credential manager has a shutdown method, call it
            if hasattr(self.credential_manager, "shutdown"):
                logger.debug("Calling credential_manager.shutdown()")
                self.credential_manager.shutdown()
            elif hasattr(self.credential_manager, "close"):
                logger.debug("Calling credential_manager.close()")
                self.credential_manager.close()
            elif hasattr(self.credential_manager, "flush"):
                # If there's a flush method, ensure all credentials are saved
                logger.debug("Calling credential_manager.flush()")
                self.credential_manager.flush()
        except Exception as e:
            error_msg = f"Error shutting down credential manager: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        # 2. Clear any sensitive data in memory
        try:
            # Clear any stored credentials from memory (if any)
            if hasattr(self, "_temp_credentials"):
                logger.debug("Clearing temporary credentials from memory")
                self._temp_credentials.clear()
        except Exception as e:
            error_msg = f"Error clearing temporary credentials: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        # Log shutdown status
        if errors:
            logger.warning(f"Credential Controller shutdown completed with {len(errors)} errors")
        else:
            logger.info("Credential Controller shutdown completed successfully")

    def sync_shutdown(self):
        """
        Synchronous version of shutdown for backward compatibility.

        This method provides a synchronous way to shut down the controller
        for contexts where async/await cannot be used directly.
        """
        logger.info("Running synchronous shutdown for Credential Controller")

        # Signal that we're shutting down
        self.is_shutting_down = True

        # Check for interpreter shutdown
        import sys

        is_interpreter_shutdown = hasattr(sys, "is_finalizing") and sys.is_finalizing()

        # Fast path for interpreter shutdown
        if is_interpreter_shutdown:
            logger.warning("Detected interpreter shutdown, using simplified cleanup")
            try:
                # Since credential controller doesn't have heavy resources to clean up,
                # we can just signal shutdown and return
                self.is_shutting_down = True
                logger.info(
                    "Simplified Credential Controller shutdown completed during interpreter shutdown"
                )
                return
            except Exception as e:
                logger.error(f"Error during simplified shutdown: {e}")

        try:
            # Try using anyio
            try:
                import anyio

                anyio.run(self.shutdown)
                return
            except ImportError:
                logger.warning("anyio not available, falling back to asyncio")
            except Exception as e:
                logger.warning(f"Error using anyio.run for shutdown: {e}, falling back to asyncio")

            # Fallback to asyncio
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # Create a new event loop if needed and not in shutdown
                if is_interpreter_shutdown:
                    logger.warning("Cannot get event loop during interpreter shutdown")
                    return

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the shutdown method
            try:
                loop.run_until_complete(self.shutdown())
            except RuntimeError as e:
                if "This event loop is already running" in str(e):
                    logger.warning("Cannot use run_until_complete in a running event loop")
                elif "can't create new thread" in str(e):
                    logger.warning("Thread creation failed during interpreter shutdown")
                else:
                    raise
        except Exception as e:
            logger.error(f"Error in sync_shutdown for Credential Controller: {e}")

        logger.info("Synchronous shutdown for Credential Controller completed")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # List credentials route
        router.add_api_route(
            "/credentials",
            self.list_credentials,
            methods=["GET"],
            response_model=CredentialInfoResponse,
            summary="List available credentials",
            description="List available credentials, optionally filtered by service",
        )

        # Generic credential route for test_mcp_comprehensive.py compatibility
        router.add_api_route(
            "/credentials",
            self.add_generic_credential,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add generic credentials",
            description="Add new credentials for any service",
        )

        # Service-specific credential routes
        router.add_api_route(
            "/credentials/s3",
            self.add_s3_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add S3 credentials",
            description="Add new S3 credentials or update existing ones",
        )

        router.add_api_route(
            "/credentials/storacha",
            self.add_storacha_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add Storacha/W3 credentials",
            description="Add new Storacha/W3 credentials or update existing ones",
        )

        router.add_api_route(
            "/credentials/filecoin",
            self.add_filecoin_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add Filecoin credentials",
            description="Add new Filecoin credentials or update existing ones",
        )

        router.add_api_route(
            "/credentials/ipfs",
            self.add_ipfs_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add IPFS credentials",
            description="Add new IPFS credentials or update existing ones",
        )

        # Delete credential route
        router.add_api_route(
            "/credentials/{service}/{name}",
            self.remove_credential,
            methods=["DELETE"],
            response_model=CredentialResponse,
            summary="Remove credentials",
            description="Remove credentials for a specific service and name",
        )

        logger.info("Credential Controller routes registered")

    async def add_generic_credential(self, credential_request: GenericCredentialRequest):
        """
        Add generic credentials for any service.

        Args:
            credential_request: Generic credential request with service, name, and values

        Returns:
            Dictionary with operation results
        """
        logger.debug(
            f"Adding generic credentials for service: {credential_request.service}, name: {credential_request.name}"
        )

        try:
            # Validate service
            valid_services = ["ipfs", "s3", "storacha", "filecoin", "ipfs_cluster"]
            if credential_request.service not in valid_services:
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Invalid service: {credential_request.service}",
        endpoint="/api/v0/credential",
        doc_category="api"
    )

            # Add credential using the generic method
            success = self.credential_manager.add_credential(
                credential_request.service,
                credential_request.name,
                credential_request.values,
            )

            if not success:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override="Failed to add credentials",
        endpoint="/api/v0/credential",
        doc_category="api"
    )

            return {
                "success": True,
                "operation": "add_credentials",
                "name": credential_request.name,
                "service": credential_request.service,
                "timestamp": time.time(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding generic credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to add credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="api"
    )}")

    async def list_credentials(self, service: Optional[str] = None):
        """
        List available credentials, optionally filtered by service.

        Args:
            service: Optional service filter

        Returns:
            Dictionary with credential information
        """
        logger.debug(f"Listing credentials for service: {service or 'all'}")

        try:
            credentials = self.credential_manager.list_credentials(service)

            return {
                "success": True,
                "credentials": credentials,
                "count": len(credentials),
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(f"Error listing credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to list credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="api"
    )}")

    async def add_s3_credentials(self, credential_request: S3CredentialRequest):
        """
        Add S3 credentials.

        Args:
            credential_request: S3 credential request

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Adding S3 credentials with name: {credential_request.name}")

        try:
            success = self.credential_manager.add_s3_credentials(
                name=credential_request.name,
                aws_access_key_id=credential_request.aws_access_key_id,
                aws_secret_access_key=credential_request.aws_secret_access_key,
                endpoint_url=credential_request.endpoint_url,
                region=credential_request.region,
            )

            if not success:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override="Failed to add S3 credentials",
        endpoint="/api/v0/credential",
        doc_category="storage"
    )

            return {
                "success": True,
                "operation": "add_credentials",
                "name": credential_request.name,
                "service": "s3",
                "timestamp": time.time(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding S3 credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to add S3 credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="storage"
    )}")

    async def add_storacha_credentials(self, credential_request: StorachaCredentialRequest):
        """
        Add Storacha/W3 credentials.

        Args:
            credential_request: Storacha credential request

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Adding Storacha credentials with name: {credential_request.name}")

        try:
            success = self.credential_manager.add_storacha_credentials(
                name=credential_request.name,
                api_token=credential_request.api_token,
                space_did=credential_request.space_did,
            )

            if not success:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override="Failed to add Storacha credentials",
        endpoint="/api/v0/credential",
        doc_category="storage"
    )

            return {
                "success": True,
                "operation": "add_credentials",
                "name": credential_request.name,
                "service": "storacha",
                "timestamp": time.time(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding Storacha credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to add Storacha credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="storage"
    )}"
            )

    async def add_filecoin_credentials(self, credential_request: FilecoinCredentialRequest):
        """
        Add Filecoin credentials.

        Args:
            credential_request: Filecoin credential request

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Adding Filecoin credentials with name: {credential_request.name}")

        try:
            success = self.credential_manager.add_filecoin_credentials(
                name=credential_request.name,
                api_key=credential_request.api_key,
                api_secret=credential_request.api_secret,
                wallet_address=credential_request.wallet_address,
                provider=credential_request.provider,
            )

            if not success:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override="Failed to add Filecoin credentials",
        endpoint="/api/v0/credential",
        doc_category="storage"
    )

            return {
                "success": True,
                "operation": "add_credentials",
                "name": credential_request.name,
                "service": "filecoin",
                "timestamp": time.time(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding Filecoin credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to add Filecoin credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="storage"
    )}"
            )

    async def add_ipfs_credentials(self, credential_request: IPFSCredentialRequest):
        """
        Add IPFS credentials.

        Args:
            credential_request: IPFS credential request

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Adding IPFS credentials with name: {credential_request.name}")

        try:
            # Create credential dictionary
            credentials = {"type": "ipfs"}

            if credential_request.identity:
                credentials["identity"] = credential_request.identity

            if credential_request.api_address:
                credentials["api_address"] = credential_request.api_address

            if credential_request.cluster_secret:
                # Add to IPFS Cluster credentials
                self.credential_manager.add_credential(
                    "ipfs_cluster",
                    credential_request.name,
                    {
                        "type": "cluster_secret",
                        "secret": credential_request.cluster_secret,
                    },
                )
                # Also include in IPFS credentials for reference
                credentials["cluster_secret_available"] = True

            # Skip if no credential data was provided
            if len(credentials) <= 1:  # Just has "type"
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override="No credential data provided",
        endpoint="/api/v0/credential",
        doc_category="api"
    )

            success = self.credential_manager.add_credential(
                "ipfs", credential_request.name, credentials
            )

            if not success:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override="Failed to add IPFS credentials",
        endpoint="/api/v0/credential",
        doc_category="api"
    )

            return {
                "success": True,
                "operation": "add_credentials",
                "name": credential_request.name,
                "service": "ipfs",
                "timestamp": time.time(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding IPFS credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to add IPFS credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="api"
    )}")

    async def remove_credential(self, service: str, name: str):
        """
        Remove credentials for a specific service and name.

        Args:
            service: Service identifier
            name: Name of the credential set

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Removing {service} credentials with name: {name}")

        try:
            # Validate service
            valid_services = ["ipfs", "s3", "storacha", "filecoin", "ipfs_cluster"]
            if service not in valid_services:
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Invalid service: {service}",
        endpoint="/api/v0/credential",
        doc_category="api"
    )

            success = self.credential_manager.remove_credential(service, name)

            if not success:
                mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=f"Credentials not found for {service}/{name}",
        endpoint="/api/v0/credential",
        doc_category="api"
    )

            return {
                "success": True,
                "operation": "remove_credentials",
                "name": name,
                "service": service,
                "timestamp": time.time(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error removing credentials: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to remove credentials: {str(e,
        endpoint="/api/v0/credential",
        doc_category="api"
    )}")
