"""
Credential Controller for the MCP server using AnyIO.

This controller handles HTTP requests related to credential management for
various storage services like IPFS, S3, Storacha, and Filecoin.

This implementation uses AnyIO for backend-agnostic async operations.
"""

import logging
import time
from typing import Optional

import anyio
import sniffio
from fastapi import APIRouter

from ipfs_kit_py.mcp.controllers.credential_controller import (
    CredentialInfoResponse,
    CredentialResponse,
    FilecoinCredentialRequest,
    # Import AnyIO for backend-agnostic async operations
    # Import Pydantic models for request/response validation
    # Import from original controller
    GenericCredentialRequest,
    IPFSCredentialRequest,
    S3CredentialRequest,
    StorachaCredentialRequest,
)

# Configure logger
logger = logging.getLogger(__name__)


class CredentialControllerAnyIO:
    """
    Controller for credential management operations using AnyIO.

    Handles HTTP requests related to credential management for various storage services.
    This implementation uses AnyIO for backend-agnostic async operations.
    """

    def __init__(self, credential_manager):
        """
        Initialize the credential controller.

        Args:
            credential_manager: Credential manager to use for operations
        """
        self.credential_manager = credential_manager
        logger.info("Credential Controller (AnyIO) initialized")

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
            description="List all available credentials without sensitive information",
        )

        # Generic credential operations (service-agnostic)
        router.add_api_route(
            "/credentials/add",
            self.add_generic_credential,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add generic credentials",
            description="Add credentials for any service using a generic format",
        )

        router.add_api_route(
            "/credentials/remove",
            self.remove_credential,
            methods=["DELETE"],
            response_model=CredentialResponse,
            summary="Remove credentials",
            description="Remove credentials for a specific service and name",
        )

        # S3 credential routes
        router.add_api_route(
            "/credentials/s3/add",
            self.add_s3_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add S3 credentials",
            description="Add AWS S3 or compatible service credentials",
        )

        # Storacha/W3 credential routes
        router.add_api_route(
            "/credentials/storacha/add",
            self.add_storacha_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add Storacha credentials",
            description="Add Storacha/W3 service credentials",
        )

        # Filecoin credential routes
        router.add_api_route(
            "/credentials/filecoin/add",
            self.add_filecoin_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add Filecoin credentials",
            description="Add Filecoin service credentials",
        )

        # IPFS credential routes
        router.add_api_route(
            "/credentials/ipfs/add",
            self.add_ipfs_credentials,
            methods=["POST"],
            response_model=CredentialResponse,
            summary="Add IPFS credentials",
            description="Add IPFS daemon credentials",
        )

        logger.info("Credential Controller (AnyIO) routes registered")

    @staticmethod
    def get_backend():
        """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    async def add_generic_credential(self, credential_request: GenericCredentialRequest):
        """
        Add generic credentials for any service.

        Args:
            credential_request: Generic credential request

        Returns:
            Credential operation response
        """
        logger.debug(
            f"Adding generic credentials for service: {credential_request.service}, name: {credential_request.name}"
        )

        # Check if service is supported
        supported_services = [
            "ipfs",
            "s3",
            "storacha",
            "filecoin",
            "huggingface",
            "lassie",
        ]

        if credential_request.service not in supported_services:
            mcp_error_handling.raise_http_exception(
                code="INVALID_REQUEST",
                message_override=f"Unsupported service: {credential_request.service}. Supported services: {' '.join(supported_services)}",
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

        try:
            # Check if the credential_manager's add_credential method is async
            if hasattr(self.credential_manager.add_credential, "__await__"):
                # Method is already async
                await self.credential_manager.add_credential(
                    service=credential_request.service,
                    name=credential_request.name,
                    values=credential_request.values
                )
            else:
                # Run synchronous method in a thread
                await anyio.to_thread.run_sync(
                    self.credential_manager.add_credential,
                    service=credential_request.service,
                    name=credential_request.name,
                    values=credential_request.values
                )

            return {
                "success": True,
                "operation": "add_credential",
                "service": credential_request.service,
                "name": credential_request.name,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error adding credential: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

    async def list_credentials(self, service: Optional[str] = None):
        """
        List available credentials without sensitive information.

        Args:
            service: Optional service filter

        Returns:
            List of credential information
        """
        logger.debug(f"Listing credentials{' for service: ' + service if service else ''}")

        try:
            # Check if the credential_manager's list_credentials method is async
            if hasattr(self.credential_manager.list_credentials, "__await__"):
                # Method is already async
                if service:
                    credentials = await self.credential_manager.list_credentials(service=service)
                else:
                    credentials = await self.credential_manager.list_credentials()
            else:
                # Run synchronous method in a thread
                if service:
                    credentials = await anyio.to_thread.run_sync(
                        self.credential_manager.list_credentials, service=service
                    )
                else:
                    credentials = await anyio.to_thread.run_sync(
                        self.credential_manager.list_credentials
                    )

            return {
                "success": True,
                "credentials": credentials,
                "count": len(credentials),
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error listing credentials: {e}")
            return {
                "success": False,
                "credentials": [],
                "count": 0,
                "timestamp": time.time(),
                "error": str(e)
            }

    async def add_s3_credentials(self, credential_request: S3CredentialRequest):
        """
        Add AWS S3 or compatible service credentials.

        Args:
            credential_request: S3 credential request

        Returns:
            Credential operation response
        """
        logger.debug(f"Adding S3 credentials name: {credential_request.name}")

        # Convert S3 credentials to generic format
        values = {
            "aws_access_key_id": credential_request.aws_access_key_id,
            "aws_secret_access_key": credential_request.aws_secret_access_key
        }

        # Add optional fields if present
        if credential_request.endpoint_url:
            values["endpoint_url"] = credential_request.endpoint_url
        if credential_request.region:
            values["region"] = credential_request.region

        try:
            # Check if the credential_manager's add_credential method is async
            if hasattr(self.credential_manager.add_credential, "__await__"):
                # Method is already async
                await self.credential_manager.add_credential(
                    service="s3", name=credential_request.name, values=values
                )
            else:
                # Run synchronous method in a thread
                await anyio.to_thread.run_sync(
                    self.credential_manager.add_credential,
                    service="s3",
                    name=credential_request.name,
                    values=values
                )

            return {
                "success": True,
                "operation": "add_s3_credential",
                "service": "s3",
                "name": credential_request.name,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error adding S3 credential: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

    async def add_storacha_credentials(self, credential_request: StorachaCredentialRequest):
        """
        Add Storacha/W3 service credentials.

        Args:
            credential_request: Storacha credential request

        Returns:
            Credential operation response
        """
        logger.debug(f"Adding Storacha credentials name: {credential_request.name}")

        # Convert Storacha credentials to generic format
        values = {"api_token": credential_request.api_token}

        # Add optional fields if present
        if credential_request.space_did:
            values["space_did"] = credential_request.space_did

        try:
            # Check if the credential_manager's add_credential method is async
            if hasattr(self.credential_manager.add_credential, "__await__"):
                # Method is already async
                await self.credential_manager.add_credential(
                    service="storacha", name=credential_request.name, values=values
                )
            else:
                # Run synchronous method in a thread
                await anyio.to_thread.run_sync(
                    self.credential_manager.add_credential,
                    service="storacha",
                    name=credential_request.name,
                    values=values
                )

            return {
                "success": True,
                "operation": "add_storacha_credential",
                "service": "storacha",
                "name": credential_request.name,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error adding Storacha credential: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

    async def add_filecoin_credentials(self, credential_request: FilecoinCredentialRequest):
        """
        Add Filecoin service credentials.

        Args:
            credential_request: Filecoin credential request

        Returns:
            Credential operation response
        """
        logger.debug(f"Adding Filecoin credentials name: {credential_request.name}")

        # Convert Filecoin credentials to generic format
        values = {"api_key": credential_request.api_key}

        # Add optional fields if present
        if credential_request.api_secret:
            values["api_secret"] = credential_request.api_secret
        if credential_request.wallet_address:
            values["wallet_address"] = credential_request.wallet_address
        if credential_request.provider:
            values["provider"] = credential_request.provider

        try:
            # Check if the credential_manager's add_credential method is async
            if hasattr(self.credential_manager.add_credential, "__await__"):
                # Method is already async
                await self.credential_manager.add_credential(
                    service="filecoin", name=credential_request.name, values=values
                )
            else:
                # Run synchronous method in a thread
                await anyio.to_thread.run_sync(
                    self.credential_manager.add_credential,
                    service="filecoin",
                    name=credential_request.name,
                    values=values
                )

            return {
                "success": True,
                "operation": "add_filecoin_credential",
                "service": "filecoin",
                "name": credential_request.name,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error adding Filecoin credential: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

    async def add_ipfs_credentials(self, credential_request: IPFSCredentialRequest):
        """
        Add IPFS daemon credentials.

        Args:
            credential_request: IPFS credential request

        Returns:
            Credential operation response
        """
        logger.debug(f"Adding IPFS credentials name: {credential_request.name}")

        # Convert IPFS credentials to generic format
        values = {}

        # Add optional fields if present
        if credential_request.identity:
            values["identity"] = credential_request.identity
        if credential_request.api_address:
            values["api_address"] = credential_request.api_address
        if credential_request.cluster_secret:
            values["cluster_secret"] = credential_request.cluster_secret

        # Ensure at least one credential field is provided
        if not values:
            mcp_error_handling.raise_http_exception(
                code="INVALID_REQUEST",
                message_override="At least one credential field (identity, api_address, or cluster_secret) must be provided",
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

        try:
            # Check if the credential_manager's add_credential method is async
            if hasattr(self.credential_manager.add_credential, "__await__"):
                # Method is already async
                await self.credential_manager.add_credential(
                    service="ipfs", name=credential_request.name, values=values
                )
            else:
                # Run synchronous method in a thread
                await anyio.to_thread.run_sync(
                    self.credential_manager.add_credential,
                    service="ipfs",
                    name=credential_request.name,
                    values=values
                )

            return {
                "success": True,
                "operation": "add_ipfs_credential",
                "service": "ipfs",
                "name": credential_request.name,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error adding IPFS credential: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )

    async def remove_credential(self, service: str, name: str):
        """
        Remove credentials for a specific service and name.

        Args:
            service: Service identifier
            name: Credential name

        Returns:
            Credential operation response
        """
        logger.debug(f"Removing credentials for service: {service}, name: {name}")

        try:
            # Check if the credential_manager's remove_credential method is async
            if hasattr(self.credential_manager.remove_credential, "__await__"):
                # Method is already async
                await self.credential_manager.remove_credential(service=service, name=name)
            else:
                # Run synchronous method in a thread
                await anyio.to_thread.run_sync(
                    self.credential_manager.remove_credential,
                    service=service,
                    name=name
                )

            return {
                "success": True,
                "operation": "remove_credential",
                "service": service,
                "name": name,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error removing credential: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/credential_anyio",
                doc_category="api"
            )
