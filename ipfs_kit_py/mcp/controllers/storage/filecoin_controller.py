"""
Filecoin Controller for the MCP server.

This controller handles HTTP requests related to Filecoin operations and
delegates the business logic to the Filecoin model.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import (
from pydantic import BaseModel, Field

APIRouter,
    HTTPException)

# Import Pydantic models for request/response validation


# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class WalletRequest(BaseModel):
    """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Request model for wallet operations."""
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
    duration_ms: Optional[float] = Field(
        None, description="Duration of the operation in milliseconds"
    )


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


# Models for new Chain/State methods
class TipsetKeyModel(BaseModel):
    """Model for a CID within a tipset key."""
    cid: str = Field(..., alias="/", description="CID string")


class GetTipsetRequest(BaseModel):
    """Request model for getting a tipset."""
    tipset_key: List[TipsetKeyModel] = Field(
        ..., description="List of block CIDs forming the tipset key"
    )


class GetTipsetResponse(OperationResponse):
    """Response model for getting a tipset."""
    tipset: Optional[Dict[str, Any]] = Field(None, description="Tipset details")


class GetActorRequest(BaseModel):
    """Request model for getting actor information."""
    address: str = Field(..., description="The address of the actor")
    tipset_key: Optional[List[TipsetKeyModel]] = Field(
        None, description="Optional tipset key to query state at (default: head)"
    )


class GetActorResponse(OperationResponse):
    """Response model for getting actor information."""
    actor: Optional[Dict[str, Any]] = Field(None, description="Actor details")


class GetMessagesInTipsetRequest(BaseModel):
    """Request model for getting messages in a tipset."""
    tipset_key: List[TipsetKeyModel] = Field(
        ..., description="List of block CIDs forming the tipset key"
    )


class GetMessagesInTipsetResponse(OperationResponse):
    """Response model for getting messages in a tipset."""
    messages: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of messages in the tipset"
    )
    count: Optional[int] = Field(None, description="Number of messages")


class WaitMessageRequest(BaseModel):
    """Request model for waiting for a message."""
    message_cid: str = Field(..., description="The CID of the message to wait for")
    confidence: int = Field(1, description="Number of epochs of confidence needed")


class WaitMessageResponse(OperationResponse):
    """Response model for waiting for a message."""
    message_lookup: Optional[Dict[str, Any]] = Field(
        None, description="Message lookup details (receipt, tipset, height)"
    )


class MpoolPendingRequest(BaseModel):
    """Request model for getting pending messages."""
    tipset_key: Optional[List[TipsetKeyModel]] = Field(
        None,
        description="Optional tipset key to filter pending messages for (default: current)",
    )


class MpoolPendingResponse(OperationResponse):
    """Response model for getting pending messages."""
    pending_messages: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of pending signed messages"
    )
    count: Optional[int] = Field(None, description="Number of pending messages")


class MpoolPushRequest(BaseModel):
    """Request model for pushing a message to the message pool."""
    message: Dict[str, Any] = Field(..., description="The signed message to push")


class MpoolPushResponse(OperationResponse):
    """Response model for pushing a message to the message pool."""
    message_cid: Optional[str] = Field(None, description="CID of the pushed message")


class MpoolGetNonceRequest(BaseModel):
    """Request model for getting the nonce for an address."""
    address: str = Field(..., description="Account address to get nonce for")


class MpoolGetNonceResponse(OperationResponse):
    """Response model for getting the nonce for an address."""
    address: Optional[str] = Field(None, description="Account address")
    nonce: Optional[int] = Field(None, description="Next nonce value for the address")


class GasEstimateMessageGasRequest(BaseModel):
    """Request model for estimating message gas."""
    message: Dict[str, Any] = Field(..., description="The message object to estimate gas for")
    max_fee: Optional[str] = Field(None, description="Maximum fee willing to pay (attoFIL)")
    tipset_key: Optional[List[TipsetKeyModel]] = Field(
        None, description="Optional tipset key to base the estimate on (default: head)"
    )


class GasEstimateMessageGasResponse(OperationResponse):
    """Response model for estimating message gas."""
    estimated_message: Optional[Dict[str, Any]] = Field(
        None, description="Message object with estimated gas values"
    )


class WalletNewRequest(BaseModel):
    """Request model for creating a new wallet."""
    wallet_type: str = Field("bls", description="Type of wallet to create (bls or secp256k1)")


class WalletNewResponse(OperationResponse):
    """Response model for creating a new wallet."""
    address: Optional[str] = Field(None, description="New wallet address")
    wallet_type: Optional[str] = Field(None, description="Type of wallet created")


class WalletHasRequest(BaseModel):
    """Request model for checking if a wallet address exists."""
    address: str = Field(..., description="Address to check")


class WalletHasResponse(OperationResponse):
    """Response model for checking if a wallet address exists."""
    address: Optional[str] = Field(None, description="Checked wallet address")
    exists: Optional[bool] = Field(None, description="Whether the wallet exists")


class WalletDefaultAddressRequest(BaseModel):
    """Request model for getting the default wallet address."""
    pass


class WalletDefaultAddressResponse(OperationResponse):
    """Response model for getting the default wallet address."""
    address: Optional[str] = Field(None, description="Default wallet address")


class WalletSetDefaultRequest(BaseModel):
    """Request model for setting the default wallet address."""
    address: str = Field(..., description="Address to set as default")


class WalletSetDefaultResponse(OperationResponse):
    """Response model for setting the default wallet address."""
    address: Optional[str] = Field(None, description="New default wallet address")
    success: bool = Field(..., description="Whether the operation was successful")


class WalletSignRequest(BaseModel):
    """Request model for signing data with a wallet."""
    address: str = Field(..., description="Address to sign with")
    data: str = Field(..., description="Base64-encoded data to sign")


class WalletSignResponse(OperationResponse):
    """Response model for signing data with a wallet."""
    address: Optional[str] = Field(None, description="Wallet address used for signing")
    signature: Optional[Dict[str, Any]] = Field(None, description="Signature data")


class WalletVerifyRequest(BaseModel):
    """Request model for verifying a signature."""
    address: str = Field(..., description="Address that signed the data")
    data: str = Field(..., description="Base64-encoded data that was signed")
    signature: Dict[str, Any] = Field(..., description="Signature to verify")


class WalletVerifyResponse(OperationResponse):
    """Response model for verifying a signature."""
    address: Optional[str] = Field(None, description="Wallet address for verification")
    valid: Optional[bool] = Field(None, description="Whether the signature is valid")


class StateListMinersRequest(BaseModel):
    """Request model for listing miners in the network."""
    tipset_key: Optional[List[TipsetKeyModel]] = Field(
        None, description="Optional tipset key to filter miners for (default: current)"
    )


class StateListMinersResponse(OperationResponse):
    """Response model for listing miners in the network."""
    miners: Optional[List[str]] = Field(None, description="List of miner addresses")
    count: Optional[int] = Field(None, description="Number of miners")


class StateMinerPowerRequest(BaseModel):
    """Request model for getting miner power information."""
    miner_address: str = Field(..., description="Miner address to query")
    tipset_key: Optional[List[TipsetKeyModel]] = Field(
        None, description="Optional tipset key (default: current)"
    )


class StateMinerPowerResponse(OperationResponse):
    """Response model for getting miner power information."""
    miner_address: Optional[str] = Field(None, description="Miner address")
    power: Optional[Dict[str, Any]] = Field(None, description="Miner power information")


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
            description="Get current status of the Filecoin backend",
        )

        # Wallet endpoints
        router.add_api_route(
            "/filecoin/wallets",
            self.handle_list_wallets_request,
            methods=["GET"],
            response_model=WalletListResponse,
            summary="List Wallets",
            description="List all wallet addresses",
        )

        router.add_api_route(
            "/filecoin/wallet/balance/{address}",
            self.handle_wallet_balance_request,
            methods=["GET"],
            response_model=WalletBalanceResponse,
            summary="Wallet Balance",
            description="Get wallet balance",
        )

        router.add_api_route(
            "/filecoin/wallet/create",
            self.handle_create_wallet_request,
            methods=["POST"],
            response_model=WalletResponse,
            summary="Create Wallet",
            description="Create a new wallet",
        )

        # Storage endpoints
        router.add_api_route(
            "/filecoin/import",
            self.handle_import_file_request,
            methods=["POST"],
            response_model=ImportResponse,
            summary="Import File",
            description="Import a file into the Lotus client",
        )

        router.add_api_route(
            "/filecoin/imports",
            self.handle_list_imports_request,
            methods=["GET"],
            response_model=ImportListResponse,
            summary="List Imports",
            description="List all imported files",
        )

        router.add_api_route(
            "/filecoin/deals",
            self.handle_list_deals_request,
            methods=["GET"],
            response_model=DealListResponse,
            summary="List Deals",
            description="List all deals made by the client",
        )

        router.add_api_route(
            "/filecoin/deal/{deal_id}",
            self.handle_deal_info_request,
            methods=["GET"],
            response_model=DealInfoResponse,
            summary="Deal Info",
            description="Get information about a specific deal",
        )

        router.add_api_route(
            "/filecoin/deal/start",
            self.handle_start_deal_request,
            methods=["POST"],
            response_model=DealResponse,
            summary="Start Deal",
            description="Start a storage deal with a miner",
        )

        router.add_api_route(
            "/filecoin/retrieve",
            self.handle_retrieve_data_request,
            methods=["POST"],
            response_model=RetrieveResponse,
            summary="Retrieve Data",
            description="Retrieve data from the Filecoin network",
        )

        # Miner endpoints
        router.add_api_route(
            "/filecoin/miners",
            self.handle_list_miners_request,
            methods=["GET"],
            response_model=MinerListResponse,
            summary="List Miners",
            description="List all miners in the network",
        )

        router.add_api_route(
            "/filecoin/miner/info",
            self.handle_miner_info_request,
            methods=["POST"],
            response_model=MinerInfoResponse,
            summary="Miner Info",
            description="Get information about a specific miner",
        )

        # Cross-service endpoints
        router.add_api_route(
            "/filecoin/from_ipfs",
            self.handle_ipfs_to_filecoin_request,
            methods=["POST"],
            response_model=IPFSToFilecoinResponse,
            summary="IPFS to Filecoin",
            description="Store IPFS content on Filecoin",
        )

        router.add_api_route(
            "/filecoin/to_ipfs",
            self.handle_filecoin_to_ipfs_request,
            methods=["POST"],
            response_model=FilecoinToIPFSResponse,
            summary="Filecoin to IPFS",
            description="Retrieve content from Filecoin and add to IPFS",
        )

        # Chain/State endpoints
        router.add_api_route(
            "/filecoin/chain/tipset",
            self.handle_get_tipset_request,
            methods=["POST"],
            response_model=GetTipsetResponse,
            summary="Get Tipset",
            description="Get tipset details by its key",
        )

        router.add_api_route(
            "/filecoin/state/actor",
            self.handle_get_actor_request,
            methods=["POST"],
            response_model=GetActorResponse,
            summary="Get Actor",
            description="Get actor information by address",
        )

        router.add_api_route(
            "/filecoin/chain/messages",
            self.handle_get_messages_in_tipset_request,
            methods=["POST"],
            response_model=GetMessagesInTipsetResponse,
            summary="Get Messages in Tipset",
            description="Get all messages included in a given tipset",
        )

        router.add_api_route(
            "/filecoin/state/wait_message",
            self.handle_wait_message_request,
            methods=["POST"],
            response_model=WaitMessageResponse,
            summary="Wait for Message",
            description="Wait for a message to appear on-chain and get its receipt",
        )

        # Mpool endpoints
        router.add_api_route(
            "/filecoin/mpool/pending",
            self.handle_mpool_pending_request,
            methods=["POST"],  # Using POST as it takes an optional body
            response_model=MpoolPendingResponse,
            summary="Get Pending Messages",
            description="Get pending messages from the message pool",
        )

        # Gas endpoints
        router.add_api_route(
            "/filecoin/gas/estimate_message_gas",
            self.handle_gas_estimate_message_gas_request,
            methods=["POST"],
            response_model=GasEstimateMessageGasResponse,
            summary="Estimate Message Gas",
            description="Estimate gas values for a message",
        )

        # Additional wallet endpoints
        router.add_api_route(
            "/filecoin/wallet/new",
            self.handle_wallet_new_request,
            methods=["POST"],
            response_model=WalletNewResponse,
            summary="Create New Wallet",
            description="Create a new wallet address of specified type",
        )

        router.add_api_route(
            "/filecoin/wallet/has/{address}",
            self.handle_wallet_has_request,
            methods=["GET"],
            response_model=WalletHasResponse,
            summary="Check Wallet",
            description="Check if wallet address exists",
        )

        router.add_api_route(
            "/filecoin/wallet/default",
            self.handle_wallet_default_address_request,
            methods=["GET"],
            response_model=WalletDefaultAddressResponse,
            summary="Get Default Wallet",
            description="Get default wallet address",
        )

        router.add_api_route(
            "/filecoin/wallet/set_default",
            self.handle_wallet_set_default_request,
            methods=["POST"],
            response_model=WalletSetDefaultResponse,
            summary="Set Default Wallet",
            description="Set default wallet address",
        )

        router.add_api_route(
            "/filecoin/wallet/sign",
            self.handle_wallet_sign_request,
            methods=["POST"],
            response_model=WalletSignResponse,
            summary="Sign Message",
            description="Sign data with a wallet",
        )

        router.add_api_route(
            "/filecoin/wallet/verify",
            self.handle_wallet_verify_request,
            methods=["POST"],
            response_model=WalletVerifyResponse,
            summary="Verify Signature",
            description="Verify signature with a wallet address",
        )

        # Additional state endpoints
        router.add_api_route(
            "/filecoin/state/list_miners",
            self.handle_state_list_miners_request,
            methods=["POST"],
            response_model=StateListMinersResponse,
            summary="List Miners",
            description="List all miners in the network at specified tipset",
        )

        router.add_api_route(
            "/filecoin/state/miner_power",
            self.handle_state_miner_power_request,
            methods=["POST"],
            response_model=StateMinerPowerResponse,
            summary="Miner Power",
            description="Get miner power information",
        )

        # Additional mpool endpoints
        router.add_api_route(
            "/filecoin/mpool/get_nonce",
            self.handle_mpool_get_nonce_request,
            methods=["POST"],
            response_model=MpoolGetNonceResponse,
            summary="Get Nonce",
            description="Get the next nonce for an address",
        )

        router.add_api_route(
            "/filecoin/mpool/push",
            self.handle_mpool_push_request,
            methods=["POST"],
            response_model=MpoolPushResponse,
            summary="Push Message",
            description="Push a signed message to the message pool",
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
                "error": result.get("error", "Failed to connect to Lotus API"),
            }

        # Return successful response with connection status
        return {
            "success": True,
            "operation": "check_connection",
            "duration_ms": result.get("duration_ms", 0),
            "is_available": True,
            "backend": "filecoin",
            "version": result.get("version"),
            "connected": True,
        }

    async def handle_list_wallets_request(self):
        """
        Handle list wallets request.

        Returns:
            List of wallet addresses
        """
        result = self.filecoin_model.list_wallets()

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletListError"),
                },
            )

        return result

    async def handle_get_tipset_request(self, request: GetTipsetRequest):
        """
        Handle get tipset request.

        Args:
            request: GetTipsetRequest containing the tipset key.

        Returns:
            Tipset details.
        """
        # Convert Pydantic models back to simple dicts for the model layer
        tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]
        result = self.filecoin_model.get_tipset(tipset_key=tipset_key_dicts)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "GetTipsetError"),
                },
            )
        # Rename 'result' field to 'tipset' for the response model
        if "result" in result:
            result["tipset"] = result.pop("result")
        return result

    async def handle_get_actor_request(self, request: GetActorRequest):
        """
        Handle get actor request.

        Args:
            request: GetActorRequest containing address and optional tipset key.

        Returns:
            Actor details.
        """
        tipset_key_dicts = None
        if request.tipset_key:
            tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]

        result = self.filecoin_model.get_actor(address=request.address, tipset_key=tipset_key_dicts)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "GetActorError"),
                },
            )
        # Rename 'result' field to 'actor' for the response model
        if "result" in result:
            result["actor"] = result.pop("result")
        return result

    async def handle_get_messages_in_tipset_request(self, request: GetMessagesInTipsetRequest):
        """
        Handle get messages in tipset request.

        Args:
            request: GetMessagesInTipsetRequest containing the tipset key.

        Returns:
            List of messages in the tipset.
        """
        tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]
        result = self.filecoin_model.get_messages_in_tipset(tipset_key=tipset_key_dicts)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "GetMessagesError"),
                },
            )
        # Rename 'result' field to 'messages' and add count
        if "result" in result:
            messages = result.pop("result")
            result["messages"] = messages
            result["count"] = len(messages) if messages else 0
        return result

    async def handle_wait_message_request(self, request: WaitMessageRequest):
        """
        Handle wait message request.

        Args:
            request: WaitMessageRequest containing message CID and confidence.

        Returns:
            Message lookup details.
        """
        result = self.filecoin_model.wait_message(
            message_cid=request.message_cid, confidence=request.confidence
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WaitMessageError"),
                },
            )
        # Rename 'result' field to 'message_lookup'
        if "result" in result:
            result["message_lookup"] = result.pop("result")
        return result

    async def handle_mpool_pending_request(self, request: MpoolPendingRequest):
        """
        Handle mpool pending request.

        Args:
            request: MpoolPendingRequest containing optional tipset key.

        Returns:
            List of pending messages.
        """
        tipset_key_dicts = None
        if request.tipset_key:
            tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]

        result = self.filecoin_model.mpool_pending(tipset_key=tipset_key_dicts)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "MpoolPendingError"),
                },
            )
        # The model returns 'messages' and 'count' fields, but we need to rename to 'pending_messages'
        if "messages" in result:
            result["pending_messages"] = result.pop("messages")
        return result

    async def handle_gas_estimate_message_gas_request(self, request: GasEstimateMessageGasRequest):
        """
        Handle gas estimate message gas request.

        Args:
            request: GasEstimateMessageGasRequest containing message and options.

        Returns:
            Message with estimated gas values.
        """
        tipset_key_dicts = None
        if request.tipset_key:
            tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]

        result = self.filecoin_model.gas_estimate_message_gas(
            message=request.message, tipset_key=tipset_key_dicts
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "GasEstimateError"),
                },
            )
        # Rename 'result' field to 'estimated_message'
        if "estimate" in result:
            result["estimated_message"] = result.pop("estimate")
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletBalanceError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletCreationError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "ImportError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "ListImportsError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "ListDealsError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "DealInfoError"),
                },
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
            fast_retrieval=request.fast_retrieval,
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "StartDealError"),
                },
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
            data_cid=request.data_cid, out_file=request.out_file
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "RetrieveError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "ListMinersError"),
                },
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
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "MinerInfoError"),
                },
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
            pin=request.pin,
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "IPFSToFilecoinError"),
                },
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
        result = self.filecoin_model.filecoin_to_ipfs(data_cid=request.data_cid, pin=request.pin)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get(,
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "FilecoinToIPFSError"),
                },
            )

        return result

    # Wallet endpoints handlers
    async def handle_wallet_new_request(self, request: WalletNewRequest):
        """
        Handle wallet new request.

        Args:
            request: Wallet new request parameters

        Returns:
            New wallet address
        """
        result = self.filecoin_model.wallet_new(wallet_type=request.wallet_type)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletNewError"),
                },
            )

        return result

    async def handle_wallet_has_request(self, address: str):
        """
        Handle wallet has request.

        Args:
            address: Wallet address to check

        Returns:
            Whether the wallet exists
        """
        result = self.filecoin_model.wallet_has(address)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletHasError"),
                },
            )

        return result

    async def handle_wallet_default_address_request(self):
        """
        Handle wallet default address request.

        Returns:
            Default wallet address
        """
        result = self.filecoin_model.wallet_default_address()

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletDefaultAddressError"),
                },
            )

        return result

    async def handle_wallet_set_default_request(self, request: WalletSetDefaultRequest):
        """
        Handle wallet set default request.

        Args:
            request: Wallet set default request parameters

        Returns:
            Result of setting default wallet
        """
        result = self.filecoin_model.wallet_set_default(address=request.address)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get(,
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletSetDefaultError"),
                },
            )

        return result

    async def handle_wallet_sign_request(self, request: WalletSignRequest):
        """
        Handle wallet sign request.

        Args:
            request: Wallet sign request parameters

        Returns:
            Signature data
        """
        result = self.filecoin_model.wallet_sign(address=request.address, data=request.data)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletSignError"),
                },
            )

        return result

    async def handle_wallet_verify_request(self, request: WalletVerifyRequest):
        """
        Handle wallet verify request.

        Args:
            request: Wallet verify request parameters

        Returns:
            Verification result
        """
        result = self.filecoin_model.wallet_verify(
            address=request.address, data=request.data, signature=request.signature
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "WalletVerifyError"),
                },
            )

        return result

    # State endpoints handlers
    async def handle_state_list_miners_request(self, request: StateListMinersRequest):
        """
        Handle state list miners request.

        Args:
            request: State list miners request parameters

        Returns:
            List of miners
        """
        tipset_key_dicts = None
        if request.tipset_key:
            tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]

        result = self.filecoin_model.state_list_miners(tipset_key=tipset_key_dicts)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "StateListMinersError"),
                },
            )

        # Rename 'result' field to 'miners' and add count
        if "result" in result:
            miners = result.pop("result")
            result["miners"] = miners
            result["count"] = len(miners) if miners else 0

        return result

    async def handle_state_miner_power_request(self, request: StateMinerPowerRequest):
        """
        Handle state miner power request.

        Args:
            request: State miner power request parameters

        Returns:
            Miner power information
        """
        tipset_key_dicts = None
        if request.tipset_key:
            tipset_key_dicts = [{"/": item.cid} for item in request.tipset_key]

        result = self.filecoin_model.state_miner_power(
            miner_address=request.miner_address, tipset_key=tipset_key_dicts
        )

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "StateMinerPowerError"),
                },
            )

        # Rename 'result' field to 'power'
        if "result" in result:
            result["power"] = result.pop("result")
            result["miner_address"] = request.miner_address

        return result

    # Mpool endpoints handlers
    async def handle_mpool_get_nonce_request(self, request: MpoolGetNonceRequest):
        """
        Handle mpool get nonce request.

        Args:
            request: Mpool get nonce request parameters

        Returns:
            Next nonce for address
        """
        result = self.filecoin_model.mpool_get_nonce(address=request.address)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "MpoolGetNonceError"),
                },
            )

        # Rename 'result' field to 'nonce'
        if "result" in result:
            result["nonce"] = result.pop("result")
            result["address"] = request.address

        return result

    async def handle_mpool_push_request(self, request: MpoolPushRequest):
        """
        Handle mpool push request.

        Args:
            request: Mpool push request parameters

        Returns:
            Message push result
        """
        result = self.filecoin_model.mpool_push(signed_message=request.message)

        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override={
                    "error": result.get("error",
        endpoint="/api/v0/filecoin",
        doc_category="storage"
    ),
                    "error_type": result.get("error_type", "MpoolPushError"),
                },
            )

        # The message_cid field should already be set by the model
        return result
