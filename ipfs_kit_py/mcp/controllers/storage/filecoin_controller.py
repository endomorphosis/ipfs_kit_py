"""
Filecoin Controller for the MCP server.

This controller handles HTTP requests related to Filecoin operations and
delegates the business logic to the Filecoin model.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile, Form, Response, Query

# Import Pydantic models for request/response validation
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Define Pydantic models for requests and responses
class WalletRequest(BaseModel):
    """Request model for wallet operations."""
    wallet_type: str = Field("bls", description="Wallet type (bls or secp256k1)")

class DealRequest(BaseModel):
    """Request model for deal operations."""
    data_cid: str = Field(..., description="The CID of the data to store")
    miner: str = Field(..., description="The miner ID to store with")
    price: str = Field(..., description="The price per epoch in attoFIL")
    duration: int = Field(..., description="The duration of the deal in epochs")
    wallet: Optional[str] = Field(None, description="Optional wallet address to use")
    verified: bool = Field(False, description="Whether this is a verified deal")
    fast_retrieval: bool = Field(True, description="Whether to enable fast retrieval")

class RetrieveRequest(BaseModel):
    """Request model for data retrieval."""
    data_cid: str = Field(..., description="The CID of the data to retrieve")
    out_file: str = Field(..., description="Path where the retrieved data should be saved")

class IPFSToFilecoinRequest(BaseModel):
    """Request model for IPFS to Filecoin operations."""
    cid: str = Field(..., description="Content identifier in IPFS")
    miner: str = Field(..., description="The miner ID to store with")
    price: str = Field(..., description="The price per epoch in attoFIL")
    duration: int = Field(..., description="The duration of the deal in epochs")
    wallet: Optional[str] = Field(None, description="Optional wallet address to use")
    verified: bool = Field(False, description="Whether this is a verified deal")
    fast_retrieval: bool = Field(True, description="Whether to enable fast retrieval")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")

class FilecoinToIPFSRequest(BaseModel):
    """Request model for Filecoin to IPFS operations."""
    data_cid: str = Field(..., description="The CID of the data to retrieve from Filecoin")
    pin: bool = Field(True, description="Whether to pin the content in IPFS")

class ImportFileRequest(BaseModel):
    """Request model for file import operations."""
    file_path: str = Field(..., description="Path to the file to import")

class MinerInfoRequest(BaseModel):
    """Request model for miner info operations."""
    miner_address: str = Field(..., description="The address of the miner")

class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation: Optional[str] = Field(None, description="Operation type")
    duration_ms: Optional[float] = Field(None, description="Duration of the operation in milliseconds")

class WalletResponse(OperationResponse):
    """Response model for wallet operations."""
    address: Optional[str] = Field(None, description="Wallet address")
    wallet_type: Optional[str] = Field(None, description="Wallet type")

class WalletListResponse(OperationResponse):
    """Response model for wallet list operations."""
    wallets: Optional[List[str]] = Field(None, description="List of wallet addresses")
    count: Optional[int] = Field(None, description="Number of wallets")

class WalletBalanceResponse(OperationResponse):
    """Response model for wallet balance operations."""
    address: Optional[str] = Field(None, description="Wallet address")
    balance: Optional[str] = Field(None, description="Wallet balance")

class DealResponse(OperationResponse):
    """Response model for deal operations."""
    deal_cid: Optional[str] = Field(None, description="Deal CID")
    data_cid: Optional[str] = Field(None, description="Data CID")
    miner: Optional[str] = Field(None, description="Miner ID")
    price: Optional[str] = Field(None, description="Price per epoch")
    duration: Optional[int] = Field(None, description="Deal duration in epochs")

class RetrieveResponse(OperationResponse):
    """Response model for data retrieval operations."""
    cid: Optional[str] = Field(None, description="Data CID")
    file_path: Optional[str] = Field(None, description="Path where the data was saved")
    size_bytes: Optional[int] = Field(None, description="Size of the retrieved data in bytes")

class MinerListResponse(OperationResponse):
    """Response model for miner list operations."""
    miners: Optional[List[str]] = Field(None, description="List of miner addresses")
    count: Optional[int] = Field(None, description="Number of miners")

class MinerInfoResponse(OperationResponse):
    """Response model for miner info operations."""
    miner_address: Optional[str] = Field(None, description="Miner address")
    miner_info: Optional[Dict[str, Any]] = Field(None, description="Miner information")

class ImportResponse(OperationResponse):
    """Response model for file import operations."""
    root: Optional[str] = Field(None, description="Root CID of the imported data")
    file_path: Optional[str] = Field(None, description="Path of the imported file")
    size_bytes: Optional[int] = Field(None, description="Size of the imported file in bytes")

class ImportListResponse(OperationResponse):
    """Response model for import list operations."""
    imports: Optional[List[Dict[str, Any]]] = Field(None, description="List of imports")
    count: Optional[int] = Field(None, description="Number of imports")

class DealListResponse(OperationResponse):
    """Response model for deal list operations."""
    deals: Optional[List[Dict[str, Any]]] = Field(None, description="List of deals")
    count: Optional[int] = Field(None, description="Number of deals")

class DealInfoResponse(OperationResponse):
    """Response model for deal info operations."""
    deal_id: Optional[int] = Field(None, description="Deal ID")
    deal_info: Optional[Dict[str, Any]] = Field(None, description="Deal information")

class IPFSToFilecoinResponse(OperationResponse):
    """Response model for IPFS to Filecoin operations."""
    ipfs_cid: Optional[str] = Field(None, description="Content identifier in IPFS")
    filecoin_cid: Optional[str] = Field(None, description="Content identifier in Filecoin")
    deal_cid: Optional[str] = Field(None, description="Deal CID")
    miner: Optional[str] = Field(None, description="Miner ID")
    price: Optional[str] = Field(None, description="Price per epoch")
    duration: Optional[int] = Field(None, description="Deal duration in epochs")
    size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")

class FilecoinToIPFSResponse(OperationResponse):
    """Response model for Filecoin to IPFS operations."""
    filecoin_cid: Optional[str] = Field(None, description="Content identifier in Filecoin")
    ipfs_cid: Optional[str] = Field(None, description="Content identifier in IPFS")
    size_bytes: Optional[int] = Field(None, description="Size of the content in bytes")


class FilecoinController:
    """
    Controller for Filecoin operations.
    
    Handles HTTP requests related to Filecoin operations and delegates
    the business logic to the Filecoin model.
    """
    
    def __init__(self, filecoin_model):
        """
        Initialize the Filecoin controller.
        
        Args:
            filecoin_model: Filecoin model to use for operations
        """
        self.filecoin_model = filecoin_model
        logger.info("Filecoin Controller initialized")
    
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
        
        logger.info("Filecoin routes registered")
    
    async def handle_status_request(self):
        """
        Handle status request for Filecoin backend.
        
        Returns:
            Status response
        """
        # Check connection to Lotus API
        result = self.filecoin_model.check_connection()
        
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
        result = self.filecoin_model.list_wallets()
        
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
        result = self.filecoin_model.get_wallet_balance(address)
        
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
        result = self.filecoin_model.create_wallet(wallet_type=request.wallet_type)
        
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
        result = self.filecoin_model.import_file(file_path=request.file_path)
        
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
        result = self.filecoin_model.list_imports()
        
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
        result = self.filecoin_model.list_deals()
        
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
        result = self.filecoin_model.get_deal_info(deal_id)
        
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
        result = self.filecoin_model.start_deal(
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
        result = self.filecoin_model.retrieve_data(
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
        result = self.filecoin_model.list_miners()
        
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
        result = self.filecoin_model.get_miner_info(miner_address=request.miner_address)
        
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
        result = self.filecoin_model.ipfs_to_filecoin(
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
        result = self.filecoin_model.filecoin_to_ipfs(
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