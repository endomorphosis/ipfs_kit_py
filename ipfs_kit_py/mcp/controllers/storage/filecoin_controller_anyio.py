"""
Filecoin Controller for the MCP server with AnyIO support.

This controller handles HTTP requests related to Filecoin operations and
delegates the business logic to the Filecoin model, using the AnyIO library
to provide support for any async backend (asyncio or trio).
"""

import logging
import time
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile, Form, Response, Query

# Import Pydantic models for request/response validation
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Import models from synchronous controller to reuse
from .filecoin_controller import (
    WalletRequest, DealRequest, RetrieveRequest, IPFSToFilecoinRequest,
    FilecoinToIPFSRequest, ImportFileRequest, MinerInfoRequest, OperationResponse,
    WalletResponse, WalletListResponse, WalletBalanceResponse, DealResponse,
    RetrieveResponse, MinerListResponse, MinerInfoResponse, ImportResponse,
    ImportListResponse, DealListResponse, DealInfoResponse, IPFSToFilecoinResponse,
    FilecoinToIPFSResponse
)


class FilecoinControllerAnyIO:
    """
    Controller for Filecoin operations with AnyIO support.
    
    Handles HTTP requests related to Filecoin operations and delegates
    the business logic to the Filecoin model, using AnyIO for async operations.
    """
    
    def __init__(self, filecoin_model):
        """
        Initialize the Filecoin controller.
        
        Args:
            filecoin_model: Filecoin model to use for operations (should be FilecoinModelAnyIO)
        """
        self.filecoin_model = filecoin_model
        logger.info("Filecoin Controller (AnyIO) initialized")
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Connection check endpoint
        router.add_api_route(
            "/filecoin/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=OperationResponse,
            summary="Filecoin Status",
            description="Get current status of the Filecoin backend"
        )
        
        # Wallet endpoints
        router.add_api_route(
            "/filecoin/wallets",
            self.handle_list_wallets_request,
            methods=["GET"],
            response_model=WalletListResponse,
            summary="List Wallets",
            description="List all wallet addresses"
        )
        
        router.add_api_route(
            "/filecoin/wallet/balance/{address}",
            self.handle_wallet_balance_request,
            methods=["GET"],
            response_model=WalletBalanceResponse,
            summary="Wallet Balance",
            description="Get wallet balance"
        )
        
        router.add_api_route(
            "/filecoin/wallet/create",
            self.handle_create_wallet_request,
            methods=["POST"],
            response_model=WalletResponse,
            summary="Create Wallet",
            description="Create a new wallet"
        )
        
        # Storage endpoints
        router.add_api_route(
            "/filecoin/import",
            self.handle_import_file_request,
            methods=["POST"],
            response_model=ImportResponse,
            summary="Import File",
            description="Import a file into the Lotus client"
        )
        
        router.add_api_route(
            "/filecoin/imports",
            self.handle_list_imports_request,
            methods=["GET"],
            response_model=ImportListResponse,
            summary="List Imports",
            description="List all imported files"
        )
        
        router.add_api_route(
            "/filecoin/deals",
            self.handle_list_deals_request,
            methods=["GET"],
            response_model=DealListResponse,
            summary="List Deals",
            description="List all deals made by the client"
        )
        
        router.add_api_route(
            "/filecoin/deal/{deal_id}",
            self.handle_deal_info_request,
            methods=["GET"],
            response_model=DealInfoResponse,
            summary="Deal Info",
            description="Get information about a specific deal"
        )
        
        router.add_api_route(
            "/filecoin/deal/start",
            self.handle_start_deal_request,
            methods=["POST"],
            response_model=DealResponse,
            summary="Start Deal",
            description="Start a storage deal with a miner"
        )
        
        router.add_api_route(
            "/filecoin/retrieve",
            self.handle_retrieve_data_request,
            methods=["POST"],
            response_model=RetrieveResponse,
            summary="Retrieve Data",
            description="Retrieve data from the Filecoin network"
        )
        
        # Miner endpoints
        router.add_api_route(
            "/filecoin/miners",
            self.handle_list_miners_request,
            methods=["GET"],
            response_model=MinerListResponse,
            summary="List Miners",
            description="List all miners in the network"
        )
        
        router.add_api_route(
            "/filecoin/miner/info",
            self.handle_miner_info_request,
            methods=["POST"],
            response_model=MinerInfoResponse,
            summary="Miner Info",
            description="Get information about a specific miner"
        )
        
        # Cross-service endpoints
        router.add_api_route(
            "/filecoin/from_ipfs",
            self.handle_ipfs_to_filecoin_request,
            methods=["POST"],
            response_model=IPFSToFilecoinResponse,
            summary="IPFS to Filecoin",
            description="Store IPFS content on Filecoin"
        )
        
        router.add_api_route(
            "/filecoin/to_ipfs",
            self.handle_filecoin_to_ipfs_request,
            methods=["POST"],
            response_model=FilecoinToIPFSResponse,
            summary="Filecoin to IPFS",
            description="Retrieve content from Filecoin and add to IPFS"
        )
        
        logger.info("Filecoin AnyIO routes registered")
    
    async def handle_status_request(self):
        """
        Handle status request for Filecoin backend.
        
        Returns:
            Status response
        """
        # Check connection to Lotus API using async method
        result = await self.filecoin_model.check_connection_async()
        
        if not result.get("success", False):
            # Return a successful response with connection status
            return {
                "success": True,
                "operation": "check_connection",
                "duration_ms": result.get("duration_ms", 0),
                "is_available": False,
                "backend": "filecoin",
                "error": result.get("error", "Failed to connect to Lotus API")
            }
        
        # Return successful response with connection status
        return {
            "success": True,
            "operation": "check_connection",
            "duration_ms": result.get("duration_ms", 0),
            "is_available": True,
            "backend": "filecoin",
            "version": result.get("version"),
            "connected": True
        }
    
    async def handle_list_wallets_request(self):
        """
        Handle list wallets request.
        
        Returns:
            List of wallet addresses
        """
        result = await self.filecoin_model.list_wallets_async()
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list wallets"),
                    "error_type": result.get("error_type", "WalletListError")
                }
            )
        
        return result
    
    async def handle_wallet_balance_request(self, address: str):
        """
        Handle wallet balance request.
        
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
                    "error_type": result.get("error_type", "WalletBalanceError")
                }
            )
        
        return result
    
    async def handle_create_wallet_request(self, request: WalletRequest):
        """
        Handle create wallet request.
        
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
                    "error_type": result.get("error_type", "WalletCreationError")
                }
            )
        
        return result
    
    async def handle_import_file_request(self, request: ImportFileRequest):
        """
        Handle import file request.
        
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
                    "error_type": result.get("error_type", "ImportError")
                }
            )
        
        return result
    
    async def handle_list_imports_request(self):
        """
        Handle list imports request.
        
        Returns:
            List of imports
        """
        result = await self.filecoin_model.list_imports_async()
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list imports"),
                    "error_type": result.get("error_type", "ListImportsError")
                }
            )
        
        return result
    
    async def handle_list_deals_request(self):
        """
        Handle list deals request.
        
        Returns:
            List of deals
        """
        result = await self.filecoin_model.list_deals_async()
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list deals"),
                    "error_type": result.get("error_type", "ListDealsError")
                }
            )
        
        return result
    
    async def handle_deal_info_request(self, deal_id: int):
        """
        Handle deal info request.
        
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
                    "error_type": result.get("error_type", "DealInfoError")
                }
            )
        
        return result
    
    async def handle_start_deal_request(self, request: DealRequest):
        """
        Handle start deal request.
        
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
            fast_retrieval=request.fast_retrieval
        )
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to start deal"),
                    "error_type": result.get("error_type", "StartDealError")
                }
            )
        
        return result
    
    async def handle_retrieve_data_request(self, request: RetrieveRequest):
        """
        Handle retrieve data request.
        
        Args:
            request: Retrieve data request parameters
            
        Returns:
            Retrieval result
        """
        result = await self.filecoin_model.retrieve_data_async(
            data_cid=request.data_cid,
            out_file=request.out_file
        )
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to retrieve data"),
                    "error_type": result.get("error_type", "RetrieveError")
                }
            )
        
        return result
    
    async def handle_list_miners_request(self):
        """
        Handle list miners request.
        
        Returns:
            List of miners
        """
        result = await self.filecoin_model.list_miners_async()
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to list miners"),
                    "error_type": result.get("error_type", "ListMinersError")
                }
            )
        
        return result
    
    async def handle_miner_info_request(self, request: MinerInfoRequest):
        """
        Handle miner info request.
        
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
                    "error_type": result.get("error_type", "MinerInfoError")
                }
            )
        
        return result
    
    async def handle_ipfs_to_filecoin_request(self, request: IPFSToFilecoinRequest):
        """
        Handle IPFS to Filecoin request.
        
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
            pin=request.pin
        )
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to store IPFS content on Filecoin"),
                    "error_type": result.get("error_type", "IPFSToFilecoinError")
                }
            )
        
        return result
    
    async def handle_filecoin_to_ipfs_request(self, request: FilecoinToIPFSRequest):
        """
        Handle Filecoin to IPFS request.
        
        Args:
            request: Filecoin to IPFS request parameters
            
        Returns:
            Operation result
        """
        result = await self.filecoin_model.filecoin_to_ipfs_async(
            data_cid=request.data_cid,
            pin=request.pin
        )
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "Failed to retrieve content from Filecoin and add to IPFS"),
                    "error_type": result.get("error_type", "FilecoinToIPFSError")
                }
            )
        
        return result