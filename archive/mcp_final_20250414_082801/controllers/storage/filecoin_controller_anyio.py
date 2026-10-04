import logging
logger = logging.getLogger(__name__) # Added logger initialization
import sniffio
"""
Filecoin Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to Filecoin operations and
delegates the business logic to the Filecoin model, using the AnyIO library
to provide support for any async backend (async-io or trio).
"""

import warnings
import sniffio
from fastapi import (
from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import (

# import time # Removed F401


# from typing import Optional # Removed F401

# AnyIO import

# Import Pydantic models for request/response validation

    APIRouter,
    HTTPException)

# Import original controller for inheritance

    FilecoinController,
    WalletRequest,
    DealRequest,
    RetrieveRequest,
    IPFSToFilecoinRequest,
    FilecoinToIPFSRequest,
    ImportFileRequest,
    MinerInfoRequest,
    OperationResponse,
    WalletResponse,
    WalletListResponse,
    WalletBalanceResponse,
    DealResponse,
    RetrieveResponse,
    MinerListResponse,
    MinerInfoResponse,
    ImportResponse,
    ImportListResponse,
    DealListResponse,
    DealInfoResponse,
    IPFSToFilecoinResponse,
    FilecoinToIPFSResponse,
)




class FilecoinControllerAnyIO(FilecoinController):
    """
    Controller for Filecoin operations with AnyIO support.

    Handles HTTP requests related to Filecoin operations and delegates
    the business logic to the Filecoin model, using AnyIO for async operations.
    """
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3,
            )

    # Override synchronous methods to warn when called from async context

    def handle_status_request(self):
        """
        Handle status request for Filecoin backend.

        Returns:
            Status response
        """
        self._warn_if_async_context("handle_status_request")
        return super().handle_status_request()

    def handle_list_wallets_request(self):
        """
        Handle list wallets request.

        Returns:
            List of wallet addresses
        """
        self._warn_if_async_context("handle_list_wallets_request")
        return super().handle_list_wallets_request()

    def handle_wallet_balance_request(self, address: str):
        """
        Handle wallet balance request.

        Args:
            address: Wallet address

        Returns:
            Wallet balance
        """
        self._warn_if_async_context("handle_wallet_balance_request")
        return super().handle_wallet_balance_request(address)

    def handle_create_wallet_request(self, request: WalletRequest):
        """
        Handle create wallet request.

        Args:
            request: Wallet request parameters

        Returns:
            New wallet address
        """
        self._warn_if_async_context("handle_create_wallet_request")
        return super().handle_create_wallet_request(request)

    def handle_import_file_request(self, request: ImportFileRequest):
        """
        Handle import file request.

        Args:
            request: Import file request parameters

        Returns:
            Import result
        """
        self._warn_if_async_context("handle_import_file_request")
        return super().handle_import_file_request(request)

    def handle_list_imports_request(self):
        """
        Handle list imports request.

        Returns:
            List of imports
        """
        self._warn_if_async_context("handle_list_imports_request")
        return super().handle_list_imports_request()

    def handle_list_deals_request(self):
        """
        Handle list deals request.

        Returns:
            List of deals
        """
        self._warn_if_async_context("handle_list_deals_request")
        return super().handle_list_deals_request()

    def handle_deal_info_request(self, deal_id: int):
        """
        Handle deal info request.

        Args:
            deal_id: Deal ID

        Returns:
            Deal information
        """
        self._warn_if_async_context("handle_deal_info_request")
        return super().handle_deal_info_request(deal_id)

    def handle_start_deal_request(self, request: DealRequest):
        """
        Handle start deal request.

        Args:
            request: Deal request parameters

        Returns:
            Deal result
        """
        self._warn_if_async_context("handle_start_deal_request")
        return super().handle_start_deal_request(request)

    def handle_retrieve_data_request(self, request: RetrieveRequest):
        """
        Handle retrieve data request.

        Args:
            request: Retrieve data request parameters

        Returns:
            Retrieval result
        """
        self._warn_if_async_context("handle_retrieve_data_request")
        return super().handle_retrieve_data_request(request)

    def handle_list_miners_request(self):
        """
        Handle list miners request.

        Returns:
            List of miners
        """
        self._warn_if_async_context("handle_list_miners_request")
        return super().handle_list_miners_request()

    def handle_miner_info_request(self, request: MinerInfoRequest):
        """
        Handle miner info request.

        Args:
            request: Miner info request parameters

        Returns:
            Miner information
        """
        self._warn_if_async_context("handle_miner_info_request")
        return super().handle_miner_info_request(request)

    def handle_ipfs_to_filecoin_request(self, request: IPFSToFilecoinRequest):
        """
        Handle IPFS to Filecoin request.

        Args:
            request: IPFS to Filecoin request parameters

        Returns:
            Operation result
        """
        self._warn_if_async_context("handle_ipfs_to_filecoin_request")
        return super().handle_ipfs_to_filecoin_request(request)

    def handle_filecoin_to_ipfs_request(self, request: FilecoinToIPFSRequest):
        """
        Handle Filecoin to IPFS request.

        Args:
            request: Filecoin to IPFS request parameters

        Returns:
            Operation result
        """
        self._warn_if_async_context("handle_filecoin_to_ipfs_request")
        return super().handle_filecoin_to_ipfs_request(request)

    # Async versions of all methods

    async def handle_status_request_async(self):
        """
        Handle status request for Filecoin backend asynchronously.

        Returns:
            Status response
        """
        # Check connection to Lotus API using async method
        result = await self.filecoin_model.check_connection_async()

        if not result.get("success", False):
            # Return a successful response with connection status
            return {
                "success": True
                "operation": "check_connection",
                "duration_ms": result.get("duration_ms", 0),
                "is_available": False
                "backend": "filecoin",
                "error": result.get("error", "Failed to connect to Lotus API"),
            }

        # Return successful response with connection status
        return {
            "success": True
            "operation": "check_connection",
            "duration_ms": result.get("duration_ms", 0),
            "is_available": True
            "backend": "filecoin",
            "version": result.get("version"),
            "connected": True
        }

    async def handle_list_wallets_request_async(self):
        """
        Handle list wallets request asynchronously.

        Returns:
            List of wallet addresses
        """
        result = await self.filecoin_model.list_wallets_async()

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list wallets"),
                    "error_type": result.get("error_type", "WalletListError"),
                },
            )

        return result

    async def handle_wallet_balance_request_async(self, address: str):
        """
        Handle wallet balance request asynchronously.

        Args:
            address: Wallet address

        Returns:
            Wallet balance
        """
        result = await self.filecoin_model.get_wallet_balance_async(address)

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to get wallet balance"),
                    "error_type": result.get("error_type", "WalletBalanceError"),
                },
            )

        return result

    async def handle_create_wallet_request_async(self, request: WalletRequest):
        """
        Handle create wallet request asynchronously.

        Args:
            request: Wallet request parameters

        Returns:
            New wallet address
        """
        result = await self.filecoin_model.create_wallet_async(wallet_type=request.wallet_type)

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to create wallet"),
                    "error_type": result.get("error_type", "WalletCreationError"),
                },
            )

        return result

    async def handle_import_file_request_async(self, request: ImportFileRequest):
        """
        Handle import file request asynchronously.

        Args:
            request: Import file request parameters

        Returns:
            Import result
        """
        result = await self.filecoin_model.import_file_async(file_path=request.file_path)

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to import file"),
                    "error_type": result.get("error_type", "ImportError"),
                },
            )

        return result

    async def handle_list_imports_request_async(self):
        """
        Handle list imports request asynchronously.

        Returns:
            List of imports
        """
        result = await self.filecoin_model.list_imports_async()

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list imports"),
                    "error_type": result.get("error_type", "ListImportsError"),
                },
            )

        return result

    async def handle_list_deals_request_async(self):
        """
        Handle list deals request asynchronously.

        Returns:
            List of deals
        """
        result = await self.filecoin_model.list_deals_async()

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list deals"),
                    "error_type": result.get("error_type", "ListDealsError"),
                },
            )

        return result

    async def handle_deal_info_request_async(self, deal_id: int):
        """
        Handle deal info request asynchronously.

        Args:
            deal_id: Deal ID

        Returns:
            Deal information
        """
        result = await self.filecoin_model.get_deal_info_async(deal_id)

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to get deal info"),
                    "error_type": result.get("error_type", "DealInfoError"),
                },
            )

        return result

    async def handle_start_deal_request_async(self, request: DealRequest):
        """
        Handle start deal request asynchronously.

        Args:
            request: Deal request parameters

        Returns:
            Deal result
        """
        result = await self.filecoin_model.start_deal_async(
            data_cid=request.data_cid,
            miner=request.miner,
            price=request.price,
            duration=request.duration,
            wallet=request.wallet,
            verified=request.verified,
            fast_retrieval=request.fast_retrieval,
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to start deal"),
                    "error_type": result.get("error_type", "StartDealError"),
                },
            )

        return result

    async def handle_retrieve_data_request_async(self, request: RetrieveRequest):
        """
        Handle retrieve data request asynchronously.

        Args:
            request: Retrieve data request parameters

        Returns:
            Retrieval result
        """
        result = await self.filecoin_model.retrieve_data_async(
            data_cid=request.data_cid, out_file=request.out_file
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to retrieve data"),
                    "error_type": result.get("error_type", "RetrieveError"),
                },
            )

        return result

    async def handle_list_miners_request_async(self):
        """
        Handle list miners request asynchronously.

        Returns:
            List of miners
        """
        result = await self.filecoin_model.list_miners_async()

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list miners"),
                    "error_type": result.get("error_type", "ListMinersError"),
                },
            )

        return result

    async def handle_miner_info_request_async(self, request: MinerInfoRequest):
        """
        Handle miner info request asynchronously.

        Args:
            request: Miner info request parameters

        Returns:
            Miner information
        """
        result = await self.filecoin_model.get_miner_info_async(miner_address=request.miner_address)

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to get miner info"),
                    "error_type": result.get("error_type", "MinerInfoError"),
                },
            )

        return result

    async def handle_ipfs_to_filecoin_request_async(self, request: IPFSToFilecoinRequest):
        """
        Handle IPFS to Filecoin request asynchronously.

        Args:
            request: IPFS to Filecoin request parameters

        Returns:
            Operation result
        """
        result = await self.filecoin_model.ipfs_to_filecoin_async(
            cid=request.cid,
            miner=request.miner,
            price=request.price,
            duration=request.duration,
            wallet=request.wallet,
            verified=request.verified,
            fast_retrieval=request.fast_retrieval,
            pin=request.pin,
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to store IPFS content on Filecoin"),
                    "error_type": result.get("error_type", "IPFSToFilecoinError"),
                },
            )

        return result

    async def handle_filecoin_to_ipfs_request_async(self, request: FilecoinToIPFSRequest):
        """
        Handle Filecoin to IPFS request asynchronously.

        Args:
            request: Filecoin to IPFS request parameters

        Returns:
            Operation result
        """
        result = await self.filecoin_model.filecoin_to_ipfs_async(
            data_cid=request.data_cid, pin=request.pin
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get(
                        "error",
                        "Failed to retrieve content from Filecoin and add to IPFS",
                    ),
                    "error_type": result.get("error_type", "FilecoinToIPFSError"),
                },
            )

        return result

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        In AnyIO mode, registers the async versions of handlers.

        Args:
            router: FastAPI router to register routes with
        """
        # Connection check endpoint
        router.add_api_route(
            "/filecoin/status",
            self.handle_status_request_async,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Filecoin Status",
            description="Get current status of the Filecoin backend",
        )

        # Wallet endpoints
        router.add_api_route(
            "/filecoin/wallets",
            self.handle_list_wallets_request_async,
            methods=["GET"],
            response_model=WalletListResponse,
            summary="List Wallets",
            description="List all wallet addresses",
        )

        router.add_api_route(
            "/filecoin/wallet/balance/{address}",
            self.handle_wallet_balance_request_async,
            methods=["GET"],
            response_model=WalletBalanceResponse,
            summary="Wallet Balance",
            description="Get wallet balance",
        )

        router.add_api_route(
            "/filecoin/wallet/create",
            self.handle_create_wallet_request_async,
            methods=["POST"],
            response_model=WalletResponse,
            summary="Create Wallet",
            description="Create a new wallet",
        )

        # Storage endpoints
        router.add_api_route(
            "/filecoin/import",
            self.handle_import_file_request_async,
            methods=["POST"],
            response_model=ImportResponse,
            summary="Import File",
            description="Import a file into the Lotus client",
        )

        router.add_api_route(
            "/filecoin/imports",
            self.handle_list_imports_request_async,
            methods=["GET"],
            response_model=ImportListResponse,
            summary="List Imports",
            description="List all imported files",
        )

        router.add_api_route(
            "/filecoin/deals",
            self.handle_list_deals_request_async,
            methods=["GET"],
            response_model=DealListResponse,
            summary="List Deals",
            description="List all deals made by the client",
        )

        router.add_api_route(
            "/filecoin/deal/{deal_id}",
            self.handle_deal_info_request_async,
            methods=["GET"],
            response_model=DealInfoResponse,
            summary="Deal Info",
            description="Get information about a specific deal",
        )

        router.add_api_route(
            "/filecoin/deal/start",
            self.handle_start_deal_request_async,
            methods=["POST"],
            response_model=DealResponse,
            summary="Start Deal",
            description="Start a storage deal with a miner",
        )

        router.add_api_route(
            "/filecoin/retrieve",
            self.handle_retrieve_data_request_async,
            methods=["POST"],
            response_model=RetrieveResponse,
            summary="Retrieve Data",
            description="Retrieve data from the Filecoin network",
        )

        # Miner endpoints
        router.add_api_route(
            "/filecoin/miners",
            self.handle_list_miners_request_async,
            methods=["GET"],
            response_model=MinerListResponse,
            summary="List Miners",
            description="List all miners in the network",
        )

        router.add_api_route(
            "/filecoin/miner/info",
            self.handle_miner_info_request_async,
            methods=["POST"],
            response_model=MinerInfoResponse,
            summary="Miner Info",
            description="Get information about a specific miner",
        )

        # Cross-service endpoints
        router.add_api_route(
            "/filecoin/from_ipfs",
            self.handle_ipfs_to_filecoin_request_async,
            methods=["POST"],
            response_model=IPFSToFilecoinResponse,
            summary="IPFS to Filecoin",
            description="Store IPFS content on Filecoin",
        )

        router.add_api_route(
            "/filecoin/to_ipfs",
            self.handle_filecoin_to_ipfs_request_async,
            methods=["POST"],
            response_model=FilecoinToIPFSResponse,
            summary="Filecoin to IPFS",
            description="Retrieve content from Filecoin and add to IPFS",
        )

        logger.info("Filecoin AnyIO routes registered")
