"""Filecoin Controller Module

This module provides the Filecoin controller functionality for the MCP server.
"""

import logging
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Request classes needed by tests
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
    wallet_type: str = Field("bls", description="Wallet type (bls or secp256k1)")


class TipsetKeyModel(BaseModel):
    """Tipset key model for Filecoin operations."""
    
    cid: str = Field(..., description="The CID of the tipset")
    height: Optional[int] = Field(None, description="The height of the tipset")
    parents: Optional[List[str]] = Field(None, description="Parent tipset CIDs")


class WalletRequest(BaseModel):
    """Request model for wallet operations."""
    
    wallet_type: str = Field("secp256k1", description="Type of wallet to create")


class DealRequest(BaseModel):
    """Request model for deal operations."""
    
    cid: str = Field(..., description="Content identifier")
    miner: str = Field(..., description="Miner address")
    price: str = Field("0", description="Price per epoch in attoFIL")
    duration: int = Field(518400, description="Duration in epochs")
    wallet: Optional[str] = Field(None, description="Wallet address")
    verified: bool = Field(False, description="Whether this is a verified deal")
    fast_retrieval: bool = Field(True, description="Enable fast retrieval")
    pin: bool = Field(True, description="Pin content after deal")


class RetrieveRequest(BaseModel):
    """Request model for content retrieval."""
    
    cid: str = Field(..., description="Content identifier to retrieve")
    output_path: Optional[str] = Field(None, description="Path to save retrieved content")


class IPFSToFilecoinRequest(BaseModel):
    """Request model for transferring content from IPFS to Filecoin."""
    
    cid: str = Field(..., description="IPFS content identifier")
    miner: str = Field(..., description="Target miner address")
    price: str = Field("0", description="Price per epoch in attoFIL")
    duration: int = Field(518400, description="Duration in epochs")
    wallet: Optional[str] = Field(None, description="Wallet address")
    verified: bool = Field(False, description="Whether this is a verified deal")
    fast_retrieval: bool = Field(True, description="Enable fast retrieval")
    pin: bool = Field(True, description="Pin content")


class FilecoinToIPFSRequest(BaseModel):
    """Request model for transferring content from Filecoin to IPFS."""
    
    data_cid: str = Field(..., description="Filecoin data CID")
    pin: bool = Field(True, description="Pin content in IPFS after transfer")


class ImportFileRequest(BaseModel):
    """Request model for importing a file."""
    
    file_path: str = Field(..., description="Path to file for import")


class MinerInfoRequest(BaseModel):
    """Request model for miner information."""
    
    miner_address: str = Field(..., description="Miner address to query")


class FilecoinDealRequest(BaseModel):
    """Request model for Filecoin storage deals."""
    
    cid: str = Field(..., description="The CID of the content to store")
    duration: int = Field(..., description="Duration of the deal in epochs")
    replication: int = Field(1, description="Number of storage providers to use")
    verified: bool = Field(False, description="Whether to use verified storage")
    price_max: Optional[float] = Field(None, description="Maximum price willing to pay")
    client_address: Optional[str] = Field(None, description="Filecoin client address")
    miner_addresses: Optional[List[str]] = Field(None, description="Preferred storage providers")


class FilecoinDealStatus(BaseModel):
    """Status model for Filecoin storage deals."""
    
    deal_id: str = Field(..., description="The ID of the storage deal")
    status: str = Field(..., description="Current status of the deal")
    provider: str = Field(..., description="Storage provider address")
    start_epoch: int = Field(..., description="Deal start epoch")
    end_epoch: int = Field(..., description="Deal end epoch")
    price_per_epoch: float = Field(..., description="Price per epoch")
    verified: bool = Field(..., description="Whether this is a verified deal")
    client_address: str = Field(..., description="Client address")
    created_at: str = Field(..., description="Creation timestamp")
    message_cid: Optional[str] = Field(None, description="Message CID")


class GetTipsetRequest(BaseModel):
    """Request model for retrieving a Filecoin tipset."""
    
    tipset_key: List[str] = Field(
        ..., description="List of block CIDs that form the tipset key"
    )
    height: Optional[int] = Field(None, description="The height of the tipset")


class FilecoinController:
    """Controller for Filecoin operations."""
    
    def __init__(self, filecoin_model):
        """Initialize with a Filecoin model."""
        self.filecoin_model = filecoin_model
        self.logger = logging.getLogger(__name__)
        
    def register_routes(self, router, prefix: str = ""):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
            prefix: Optional prefix for all routes
        """
        # Status endpoint
        router.add_api_route(
            "/filecoin/status",
            self.handle_status_request,
            methods=["GET"],
            summary="Get Filecoin node status",
            description="Check if the Filecoin node is available and get its version"
        )
        
        # Wallet endpoints
        router.add_api_route(
            "/filecoin/wallets",
            self.handle_list_wallets_request,
            methods=["GET"],
            summary="List Filecoin wallets",
            description="List all available Filecoin wallets"
        )
        
        router.add_api_route(
            "/filecoin/wallets/create",
            self.handle_create_wallet_request,
            methods=["POST"],
            summary="Create Filecoin wallet",
            description="Create a new Filecoin wallet"
        )
        
        router.add_api_route(
            "/filecoin/wallets/{address}/balance",
            self.handle_wallet_balance_request,
            methods=["GET"],
            summary="Get wallet balance",
            description="Get the balance of a specific Filecoin wallet"
        )
        
        # Storage deal endpoints
        router.add_api_route(
            "/filecoin/deals",
            self.handle_list_deals_request,
            methods=["GET"],
            summary="List storage deals",
            description="List all Filecoin storage deals"
        )
        
        router.add_api_route(
            "/filecoin/deals/{deal_id}",
            self.handle_deal_info_request,
            methods=["GET"],
            summary="Get deal info",
            description="Get information about a specific storage deal"
        )
        
        router.add_api_route(
            "/filecoin/deals/create",
            self.create_deal,
            methods=["POST"],
            summary="Create storage deal",
            description="Create a new Filecoin storage deal"
        )
        
        router.add_api_route(
            "/filecoin/deals/status",
            self.get_deal_status,
            methods=["POST"],
            summary="Get deal status",
            description="Get the status of a storage deal"
        )
        
        # Miner endpoints
        router.add_api_route(
            "/filecoin/miners",
            self.handle_list_miners_request,
            methods=["GET"],
            summary="List miners",
            description="List available Filecoin miners"
        )
        
        router.add_api_route(
            "/filecoin/miners/info",
            self.handle_miner_info_request,
            methods=["POST"],
            summary="Get miner info",
            description="Get information about a specific miner"
        )
        
        # File import endpoints
        router.add_api_route(
            "/filecoin/imports",
            self.handle_list_imports_request,
            methods=["GET"],
            summary="List imports",
            description="List all imports in Filecoin"
        )
        
        router.add_api_route(
            "/filecoin/imports/file",
            self.handle_import_file_request,
            methods=["POST"],
            summary="Import file",
            description="Import a file to Filecoin"
        )
        
        # Content transfer endpoints
        router.add_api_route(
            "/filecoin/from_ipfs",
            self.handle_ipfs_to_filecoin_request,
            methods=["POST"],
            summary="IPFS to Filecoin",
            description="Transfer content from IPFS to Filecoin"
        )
        
        router.add_api_route(
            "/filecoin/to_ipfs",
            self.handle_filecoin_to_ipfs_request,
            methods=["POST"],
            summary="Filecoin to IPFS",
            description="Transfer content from Filecoin to IPFS"
        )
        
        # Chain endpoints
        router.add_api_route(
            "/filecoin/chain/head",
            self.get_chain_head,
            methods=["GET"],
            summary="Get chain head",
            description="Get the current Filecoin chain head tipset"
        )
        
        router.add_api_route(
            "/filecoin/chain/tipset",
            self.get_tipset,
            methods=["POST"],
            summary="Get tipset",
            description="Get a specific tipset by key or height"
        )
        
        self.logger.info("Filecoin controller routes registered")
        
    async def handle_status_request(self) -> Dict[str, Any]:
        """Handle request to check Filecoin node status."""
        self.logger.info("Checking Filecoin node status")
        try:
            status = await self.filecoin_model.check_status_async()
            return {
                "is_available": status.get("is_available", False),
                "version": status.get("version", "unknown"),
                "success": True,
                "message": "Status check completed successfully"
            }
        except Exception as e:
            self.logger.error(f"Error checking Filecoin status: {str(e)}")
            return {
                "is_available": False,
                "version": "unknown",
                "success": False,
                "message": f"Error checking status: {str(e)}"
            }
    
    async def handle_list_wallets_request(self) -> Dict[str, Any]:
        """Handle request to list Filecoin wallets."""
        self.logger.info("Listing Filecoin wallets")
        try:
            wallets = await self.filecoin_model.list_wallets_async()
            return {
                "wallets": wallets,
                "count": len(wallets),
                "success": True,
                "message": "Wallets retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error listing wallets: {str(e)}")
            return {
                "wallets": [],
                "count": 0,
                "success": False,
                "message": f"Error listing wallets: {str(e)}"
            }
    
    async def handle_create_wallet_request(self, request: WalletRequest) -> Dict[str, Any]:
        """Handle request to create a new Filecoin wallet."""
        wallet_type = request.wallet_type
        self.logger.info(f"Creating new Filecoin wallet of type: {wallet_type}")
        try:
            address = await self.filecoin_model.create_wallet_async(wallet_type)
            return {
                "address": address,
                "wallet_type": wallet_type,
                "success": True,
                "message": f"Created new wallet with address {address}"
            }
        except Exception as e:
            self.logger.error(f"Error creating wallet: {str(e)}")
            return {
                "address": None,
                "wallet_type": wallet_type,
                "success": False,
                "message": f"Error creating wallet: {str(e)}"
            }
    
    async def handle_wallet_balance_request(self, address: str) -> Dict[str, Any]:
        """Handle request to get wallet balance."""
        self.logger.info(f"Getting balance for wallet: {address}")
        try:
            balance = await self.filecoin_model.get_wallet_balance_async(address)
            return {
                "address": address,
                "balance": balance,
                "success": True,
                "message": f"Balance retrieved for {address}"
            }
        except Exception as e:
            self.logger.error(f"Error getting wallet balance: {str(e)}")
            return {
                "address": address,
                "balance": None,
                "success": False,
                "message": f"Error getting wallet balance: {str(e)}"
            }
    
    async def handle_import_file_request(self, request: ImportFileRequest) -> Dict[str, Any]:
        """Handle request to import a file to Filecoin."""
        file_path = request.file_path
        self.logger.info(f"Importing file from path: {file_path}")
        try:
            result = await self.filecoin_model.import_file_async(file_path)
            return {
                "root": result.get("root", ""),
                "file_path": file_path,
                "size": result.get("size", 0),
                "success": True,
                "message": f"File imported with CID {result.get('root', '')}"
            }
        except Exception as e:
            self.logger.error(f"Error importing file: {str(e)}")
            return {
                "root": None,
                "file_path": file_path,
                "size": 0,
                "success": False,
                "message": f"Error importing file: {str(e)}"
            }
    
    async def handle_list_imports_request(self) -> Dict[str, Any]:
        """Handle request to list imports."""
        self.logger.info("Listing Filecoin imports")
        try:
            imports = await self.filecoin_model.list_imports_async()
            return {
                "imports": imports,
                "count": len(imports),
                "success": True,
                "message": "Imports retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error listing imports: {str(e)}")
            return {
                "imports": [],
                "count": 0,
                "success": False,
                "message": f"Error listing imports: {str(e)}"
            }
    
    async def handle_list_deals_request(self) -> Dict[str, Any]:
        """Handle request to list storage deals."""
        self.logger.info("Listing Filecoin storage deals")
        try:
            deals = await self.filecoin_model.list_deals_async()
            return {
                "deals": deals,
                "count": len(deals),
                "success": True,
                "message": "Deals retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error listing deals: {str(e)}")
            return {
                "deals": [],
                "count": 0,
                "success": False,
                "message": f"Error listing deals: {str(e)}"
            }
    
    async def handle_deal_info_request(self, deal_id: str) -> Dict[str, Any]:
        """Handle request to get information about a specific deal."""
        self.logger.info(f"Getting info for deal: {deal_id}")
        try:
            info = await self.filecoin_model.get_deal_info_async(deal_id)
            return {
                "deal_id": deal_id,
                "info": info,
                "success": True,
                "message": f"Deal info retrieved for {deal_id}"
            }
        except Exception as e:
            self.logger.error(f"Error getting deal info: {str(e)}")
            return {
                "deal_id": deal_id,
                "info": None,
                "success": False,
                "message": f"Error getting deal info: {str(e)}"
            }
    
    async def handle_list_miners_request(self) -> Dict[str, Any]:
        """Handle request to list miners."""
        self.logger.info("Listing Filecoin miners")
        try:
            miners = await self.filecoin_model.list_miners_async()
            return {
                "miners": miners,
                "count": len(miners),
                "success": True,
                "message": "Miners retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error listing miners: {str(e)}")
            return {
                "miners": [],
                "count": 0,
                "success": False,
                "message": f"Error listing miners: {str(e)}"
            }
    
    async def handle_miner_info_request(self, request: MinerInfoRequest) -> Dict[str, Any]:
        """Handle request to get miner information."""
        miner_address = request.miner_address
        self.logger.info(f"Getting info for miner: {miner_address}")
        try:
            info = await self.filecoin_model.get_miner_info_async(miner_address)
            return {
                "miner_address": miner_address,
                "info": info,
                "success": True,
                "message": f"Miner info retrieved for {miner_address}"
            }
        except Exception as e:
            self.logger.error(f"Error getting miner info: {str(e)}")
            return {
                "miner_address": miner_address,
                "info": None,
                "success": False,
                "message": f"Error getting miner info: {str(e)}"
            }
    
    async def handle_ipfs_to_filecoin_request(self, request: IPFSToFilecoinRequest) -> Dict[str, Any]:
        """Handle request to transfer content from IPFS to Filecoin."""
        self.logger.info(f"Transferring content from IPFS to Filecoin: {request.cid}")
        try:
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
            return {
                "cid": request.cid,
                "deal_id": result.get("deal_id", ""),
                "success": True,
                "message": "Content transferred from IPFS to Filecoin"
            }
        except Exception as e:
            self.logger.error(f"Error transferring from IPFS to Filecoin: {str(e)}")
            return {
                "cid": request.cid,
                "deal_id": None,
                "success": False,
                "message": f"Error transferring from IPFS to Filecoin: {str(e)}"
            }
    
    async def handle_filecoin_to_ipfs_request(self, request: FilecoinToIPFSRequest) -> Dict[str, Any]:
        """Handle request to transfer content from Filecoin to IPFS."""
        self.logger.info(f"Transferring content from Filecoin to IPFS: {request.data_cid}")
        try:
            result = await self.filecoin_model.filecoin_to_ipfs_async(
                data_cid=request.data_cid,
                pin=request.pin
            )
            return {
                "data_cid": request.data_cid,
                "ipfs_cid": result.get("ipfs_cid", ""),
                "success": True,
                "message": "Content transferred from Filecoin to IPFS"
            }
        except Exception as e:
            self.logger.error(f"Error transferring from Filecoin to IPFS: {str(e)}")
            return {
                "data_cid": request.data_cid,
                "ipfs_cid": None,
                "success": False,
                "message": f"Error transferring from Filecoin to IPFS: {str(e)}"
            }
    
    async def get_chain_head(self, request) -> Dict[str, Any]:
        """Get the current chain head tipset."""
        self.logger.info("Getting Filecoin chain head")
        try:
            head = await self.filecoin_model.get_chain_head_async()
            return {
                "tipset": head,
                "success": True,
                "message": "Chain head retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error getting chain head: {str(e)}")
            return {
                "tipset": None,
                "success": False,
                "message": f"Error getting chain head: {str(e)}"
            }
    
    async def create_deal(self, request: FilecoinDealRequest) -> Dict[str, Any]:
        """Create a new Filecoin storage deal."""
        self.logger.info(f"Creating Filecoin deal for CID: {request.cid}")
        try:
            deal = await self.filecoin_model.create_deal_async(
                cid=request.cid,
                duration=request.duration,
                replication=request.replication,
                verified=request.verified,
                price_max=request.price_max,
                client_address=request.client_address,
                miner_addresses=request.miner_addresses
            )
            return {
                "deal_id": deal.get("deal_id"),
                "success": True,
                "message": "Deal created successfully"
            }
        except Exception as e:
            self.logger.error(f"Error creating deal: {str(e)}")
            return {
                "deal_id": None,
                "success": False,
                "message": f"Error creating deal: {str(e)}"
            }
    
    async def get_deal_status(self, request) -> Dict[str, Any]:
        """Get the status of a Filecoin storage deal."""
        deal_id = request.deal_id
        self.logger.info(f"Getting status for deal: {deal_id}")
        try:
            status = await self.filecoin_model.get_deal_status_async(deal_id)
            return {
                "status": status,
                "success": True,
                "message": f"Deal status retrieved for {deal_id}"
            }
        except Exception as e:
            self.logger.error(f"Error getting deal status: {str(e)}")
            return {
                "status": None,
                "success": False,
                "message": f"Error getting deal status: {str(e)}"
            }
    
    async def list_deals(self, request) -> Dict[str, Any]:
        """List all Filecoin storage deals."""
        self.logger.info("Listing Filecoin deals")
        try:
            deals = await self.filecoin_model.list_deals_async(
                address=getattr(request, "address", None),
                status=getattr(request, "status", None),
                limit=getattr(request, "limit", None),
                offset=getattr(request, "offset", None)
            )
            return {
                "deals": deals,
                "count": len(deals),
                "success": True,
                "message": "Deals retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error listing deals: {str(e)}")
            return {
                "deals": [],
                "count": 0,
                "success": False,
                "message": f"Error listing deals: {str(e)}"
            }
    
    async def get_tipset(self, request: GetTipsetRequest) -> Dict[str, Any]:
        """Get a specific tipset by key or height."""
        self.logger.info(f"Getting tipset with key: {request.tipset_key}")
        try:
            tipset = await self.filecoin_model.get_tipset_async(
                key=request.tipset_key,
                height=request.height
            )
            return {
                "tipset": tipset,
                "success": True,
                "message": "Tipset retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error getting tipset: {str(e)}")
            return {
                "tipset": None,
                "success": False,
                "message": f"Error getting tipset: {str(e)}"
            }
    
    async def get_wallet_balance(self, request) -> Dict[str, Any]:
        """Get the balance of a Filecoin wallet address."""
        address = request.address
        self.logger.info(f"Getting wallet balance for address: {address}")
        try:
            balance = await self.filecoin_model.get_wallet_balance_async(address)
            return {
                "balance": balance,
                "success": True,
                "message": f"Balance retrieved for {address}"
            }
        except Exception as e:
            self.logger.error(f"Error getting wallet balance: {str(e)}")
            return {
                "balance": None,
                "success": False,
                "message": f"Error getting wallet balance: {str(e)}"
            }
