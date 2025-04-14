"""
Filecoin (Lotus) Model AnyIO implementation for MCP Server.

This module provides asynchronous versions of the Filecoin operations for the MCP server,
supporting both asyncio and trio via AnyIO. It wraps the synchronous FilecoinModel methods
with async equivalents for better performance in async contexts.
"""

import anyio
import logging
import os
import sniffio
import tempfile
import time
import warnings
from typing import Dict, Optional, Any
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel

# Configure logger
logger = logging.getLogger(__name__)


class FilecoinModelAnyIO(FilecoinModel):
    """AnyIO-compatible model for Filecoin (Lotus) operations.

    This class extends the synchronous FilecoinModel with asynchronous versions of
    all methods, ensuring efficient operation in async contexts. It supports both
    asyncio and trio via the AnyIO library.
    """
    def __init__(
        self
lotus_kit_instance = None
ipfs_model = None
cache_manager = None
credential_manager = None
        """Initialize FilecoinModelAnyIO with dependencies.

        Args:
            lotus_kit_instance: lotus_kit instance for Filecoin operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(lotus_kit_instance, ipfs_model, cache_manager, credential_manager)

        logger.info("FilecoinModelAnyIO initialized")

    @staticmethod
    def get_backend():
        """Get the current async backend being used.

        Returns:
            String name of the async backend or None if not in an async context
        """
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version.

        Args:
            method_name: The name of the method being called
        """
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
stacklevel=3

    # Override parent methods to add warning in async context
    def check_connection(self) -> Dict[str, Any]:
        """Check connection to the Lotus API.

        Returns:
            Result dictionary with connection status
        """
        self._warn_if_async_context("check_connection")
        return super().check_connection()

    async def check_connection_async(self) -> Dict[str, Any]:
        """Async version: Check connection to the Lotus API.

        Returns:
            Result dictionary with connection status
        """
        start_time = time.time()
        result = self._create_result_template("check_connection_async")

        try:
            # Use lotus_kit to check connection
            if self.kit:
                connection_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.check_connection()

                if connection_result.get("success", False):
                    result["success"] = True
                    result["connected"] = True

                    # Include version information if available
                    if "result" in connection_result:
                        result["version"] = connection_result["result"]
                else:
                    result["error"] = connection_result.get(
                        "error", "Failed to connect to Lotus API"
                    result["error_type"] = connection_result.get("error_type", "ConnectionError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "configure", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "check_connection_async")

    def list_wallets(self) -> Dict[str, Any]:
        """List all wallet addresses.

        Returns:
            Result dictionary with wallet addresses
        """
        self._warn_if_async_context("list_wallets")
        return super().list_wallets()

    async def list_wallets_async(self) -> Dict[str, Any]:
        """Async version: List all wallet addresses.

        Returns:
            Result dictionary with wallet addresses
        """
        start_time = time.time()
        result = self._create_result_template("list_wallets_async")

        try:
            # Use lotus_kit to list wallets
            if self.kit:
                wallet_result = await anyio.to_thread.run_sync(lambda: self.kit.list_wallets())

                if wallet_result.get("success", False):
                    result["success"] = True
                    result["wallets"] = wallet_result.get("result", [])
                    result["count"] = len(result["wallets"])
                else:
                    result["error"] = wallet_result.get("error", "Failed to list wallets")
                    result["error_type"] = wallet_result.get("error_type", "WalletListError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_wallets_async")

    def get_wallet_balance(self, address: str) -> Dict[str, Any]:
        """Get wallet balance.

        Args:
            address: The wallet address to check balance for

        Returns:
            Result dictionary with wallet balance
        """
        self._warn_if_async_context("get_wallet_balance")
        return super().get_wallet_balance(address)

    async def get_wallet_balance_async(self, address: str) -> Dict[str, Any]:
        """Async version: Get wallet balance.

        Args:
            address: The wallet address to check balance for

        Returns:
            Result dictionary with wallet balance
        """
        start_time = time.time()
        result = self._create_result_template("get_wallet_balance_async")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Wallet address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get wallet balance
            if self.kit:
                balance_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.wallet_balance(address)

                if balance_result.get("success", False):
                    result["success"] = True
                    result["address"] = address
                    result["balance"] = balance_result.get("result")
                else:
                    result["error"] = balance_result.get("error", "Failed to get wallet balance")
                    result["error_type"] = balance_result.get("error_type", "WalletBalanceError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_wallet_balance_async")

    def create_wallet(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Create a new wallet.

        Args:
            wallet_type: The type of wallet to create (bls or secp256k1)

        Returns:
            Result dictionary with new wallet address
        """
        self._warn_if_async_context("create_wallet")
        return super().create_wallet(wallet_type)

    async def create_wallet_async(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Async version: Create a new wallet.

        Args:
            wallet_type: The type of wallet to create (bls or secp256k1)

        Returns:
            Result dictionary with new wallet address
        """
        start_time = time.time()
        result = self._create_result_template("create_wallet_async")

        try:
            # Validate wallet_type
            valid_types = ["bls", "secp256k1"]
            if wallet_type not in valid_types:
                result["error"] = f"Invalid wallet type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to create wallet
            if self.kit:
                wallet_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.create_wallet(wallet_type)

                if wallet_result.get("success", False):
                    result["success"] = True
                    result["address"] = wallet_result.get("result")
                    result["wallet_type"] = wallet_type
                else:
                    result["error"] = wallet_result.get("error", "Failed to create wallet")
                    result["error_type"] = wallet_result.get("error_type", "WalletCreationError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "create_wallet_async")

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """Import a file into the Lotus client.

        Args:
            file_path: Path to the file to import

        Returns:
            Result dictionary with import information
        """
        self._warn_if_async_context("import_file")
        return super().import_file(file_path)

    async def import_file_async(self, file_path: str) -> Dict[str, Any]:
        """Async version: Import a file into the Lotus client.

        Args:
            file_path: Path to the file to import

        Returns:
            Result dictionary with import information
        """
        start_time = time.time()
        result = self._create_result_template("import_file_async")

        try:
            # Validate inputs
            file_exists = await anyio.to_thread.run_sync(lambda: os.path.exists(file_path))
            if not file_exists:
                result["error"] = f"File not found: {file_path}"
                result["error_type"] = "FileNotFoundError"
                return result

            # Get file size for statistics
            file_size = await anyio.to_thread.run_sync(lambda: self._get_file_size(file_path))

            # Use lotus_kit to import the file
            if self.kit:
                import_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.client_import(file_path)

                if import_result.get("success", False):
                    result["success"] = True
                    result["root"] = import_result.get("result", {}).get("Root", {}).get("/")
                    result["file_path"] = file_path
                    result["size_bytes"] = file_size

                    # Copy other import details if available
                    if "result" in import_result:
                        for field in ["ImportID", "Size", "Status"]:
                            if field in import_result["result"]:
                                result[field.lower()] = import_result["result"][field]
                else:
                    result["error"] = import_result.get("error", "Failed to import file")
                    result["error_type"] = import_result.get("error_type", "ImportError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(
                result, "upload", start_time, file_size if result["success"] else None

        except Exception as e:
            return self._handle_exception(e, result, "import_file_async")

    def list_imports(self) -> Dict[str, Any]:
        """List all imported files.

        Returns:
            Result dictionary with list of imports
        """
        self._warn_if_async_context("list_imports")
        return super().list_imports()

    async def list_imports_async(self) -> Dict[str, Any]:
        """Async version: List all imported files.

        Returns:
            Result dictionary with list of imports
        """
        start_time = time.time()
        result = self._create_result_template("list_imports_async")

        try:
            # Use lotus_kit to list imports
            if self.kit:
                imports_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.client_list_imports()

                if imports_result.get("success", False):
                    result["success"] = True
                    result["imports"] = imports_result.get("result", [])
                    result["count"] = len(result["imports"])
                else:
                    result["error"] = imports_result.get("error", "Failed to list imports")
                    result["error_type"] = imports_result.get("error_type", "ListImportsError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_imports_async")

    def find_data(self, data_cid: str) -> Dict[str, Any]:
        """Find where data is stored.

        Args:
            data_cid: The CID of the data to find

        Returns:
            Result dictionary with data location information
        """
        self._warn_if_async_context("find_data")
        return super().find_data(data_cid)

    async def find_data_async(self, data_cid: str) -> Dict[str, Any]:
        """Async version: Find where data is stored.

        Args:
            data_cid: The CID of the data to find

        Returns:
            Result dictionary with data location information
        """
        start_time = time.time()
        result = self._create_result_template("find_data_async")

        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to find data
            if self.kit:
                find_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.client_find_data(data_cid)

                if find_result.get("success", False):
                    result["success"] = True
                    result["cid"] = data_cid
                    result["locations"] = find_result.get("result", [])
                    result["count"] = len(result["locations"])
                else:
                    result["error"] = find_result.get("error", "Failed to find data")
                    result["error_type"] = find_result.get("error_type", "FindDataError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "find_data_async")

    def list_deals(self) -> Dict[str, Any]:
        """List all deals made by the client.

        Returns:
            Result dictionary with list of deals
        """
        self._warn_if_async_context("list_deals")
        return super().list_deals()

    async def list_deals_async(self) -> Dict[str, Any]:
        """Async version: List all deals made by the client.

        Returns:
            Result dictionary with list of deals
        """
        start_time = time.time()
        result = self._create_result_template("list_deals_async")

        try:
            # Use lotus_kit to list deals
            if self.kit:
                deals_result = await anyio.to_thread.run_sync(lambda: self.kit.client_list_deals())

                if deals_result.get("success", False):
                    result["success"] = True
                    result["deals"] = deals_result.get("result", [])
                    result["count"] = len(result["deals"])
                else:
                    result["error"] = deals_result.get("error", "Failed to list deals")
                    result["error_type"] = deals_result.get("error_type", "ListDealsError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_deals_async")

    def get_deal_info(self, deal_id: int) -> Dict[str, Any]:
        """Get information about a specific deal.

        Args:
            deal_id: ID of the deal to get information about

        Returns:
            Result dictionary with deal information
        """
        self._warn_if_async_context("get_deal_info")
        return super().get_deal_info(deal_id)

    async def get_deal_info_async(self, deal_id: int) -> Dict[str, Any]:
        """Async version: Get information about a specific deal.

        Args:
            deal_id: ID of the deal to get information about

        Returns:
            Result dictionary with deal information
        """
        start_time = time.time()
        result = self._create_result_template("get_deal_info_async")

        try:
            # Validate inputs
            if not isinstance(deal_id, int):
                result["error"] = "Deal ID must be an integer"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get deal info
            if self.kit:
                deal_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.client_deal_info(deal_id)

                if deal_result.get("success", False):
                    result["success"] = True
                    result["deal_id"] = deal_id
                    result["deal_info"] = deal_result.get("result", {})
                else:
                    result["error"] = deal_result.get("error", "Failed to get deal info")
                    result["error_type"] = deal_result.get("error_type", "DealInfoError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_deal_info_async")

    def start_deal(
        self
        data_cid: str
        miner: str
        price: str
        duration: int
        wallet: Optional[str] = None,
        verified: bool = False,
        fast_retrieval: bool = True,
        """Start a storage deal with a miner.

        Args:
            data_cid: The CID of the data to store
            miner: The miner ID to store with
            price: The price per epoch in attoFIL
            duration: The duration of the deal in epochs
            wallet: Optional wallet address to use
            verified: Whether this is a verified deal
            fast_retrieval: Whether to enable fast retrieval

        Returns:
            Result dictionary with deal information
        """
        self._warn_if_async_context("start_deal")
        return super().start_deal(
            data_cid, miner, price, duration, wallet, verified, fast_retrieval

    async def start_deal_async(
        self
        data_cid: str
        miner: str
        price: str
        duration: int
        wallet: Optional[str] = None,
        verified: bool = False,
        fast_retrieval: bool = True,
        """Async version: Start a storage deal with a miner.

        Args:
            data_cid: The CID of the data to store
            miner: The miner ID to store with
            price: The price per epoch in attoFIL
            duration: The duration of the deal in epochs
            wallet: Optional wallet address to use
            verified: Whether this is a verified deal
            fast_retrieval: Whether to enable fast retrieval

        Returns:
            Result dictionary with deal information
        """
        start_time = time.time()
        result = self._create_result_template("start_deal_async")

        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result

            if not miner:
                result["error"] = "Miner ID is required"
                result["error_type"] = "ValidationError"
                return result

            if not price:
                result["error"] = "Price is required"
                result["error_type"] = "ValidationError"
                return result

            if not duration:
                result["error"] = "Duration is required"
                result["error_type"] = "ValidationError"
                return result

            # If wallet not specified, get default wallet
            if not wallet and self.kit:
                wallet_result = await anyio.to_thread.run_sync(lambda: self.kit.list_wallets())
                if wallet_result.get("success", False) and wallet_result.get("result"):
                    wallet = wallet_result["result"][0]

            # Use lotus_kit to start deal
            if self.kit:
                # Use a lambda to ensure all params are properly captured
                deal_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.client_start_deal(
data_cid=data_cid
miner=miner
price=price
duration=duration
wallet=wallet
verified=verified
fast_retrieval=fast_retrieval

                if deal_result.get("success", False):
                    result["success"] = True
                    result["deal_cid"] = deal_result.get("result", {}).get("/")

                    # Add deal parameters
                    result["data_cid"] = data_cid
                    result["miner"] = miner
                    result["price"] = price
                    result["duration"] = duration
                    result["wallet"] = wallet
                    result["verified"] = verified
                    result["fast_retrieval"] = fast_retrieval
                else:
                    result["error"] = deal_result.get("error", "Failed to start deal")
                    result["error_type"] = deal_result.get("error_type", "StartDealError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "start_deal_async")

    def retrieve_data(self, data_cid: str, out_file: str) -> Dict[str, Any]:
        """Retrieve data from the Filecoin network.

        Args:
            data_cid: The CID of the data to retrieve
            out_file: Path where the retrieved data should be saved

        Returns:
            Result dictionary with retrieval information
        """
        self._warn_if_async_context("retrieve_data")
        return super().retrieve_data(data_cid, out_file)

    async def retrieve_data_async(self, data_cid: str, out_file: str) -> Dict[str, Any]:
        """Async version: Retrieve data from the Filecoin network.

        Args:
            data_cid: The CID of the data to retrieve
            out_file: Path where the retrieved data should be saved

        Returns:
            Result dictionary with retrieval information
        """
        start_time = time.time()
        result = self._create_result_template("retrieve_data_async")

        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result

            if not out_file:
                result["error"] = "Output file path is required"
                result["error_type"] = "ValidationError"
                return result

            # Create output directory if it doesn't exist
            out_dir = os.path.dirname(os.path.abspath(out_file))
            await anyio.to_thread.run_sync(lambda: os.makedirs(out_dir, exist_ok=True))

            # Use lotus_kit to retrieve data
            if self.kit:
                retrieve_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.client_retrieve(data_cid, out_file)

                if retrieve_result.get("success", False):
                    # Get file size for statistics
                    file_size = await anyio.to_thread.run_sync(
                        lambda: self._get_file_size(out_file)

                    result["success"] = True
                    result["cid"] = data_cid
                    result["file_path"] = out_file
                    result["size_bytes"] = file_size
                else:
                    result["error"] = retrieve_result.get("error", "Failed to retrieve data")
                    result["error_type"] = retrieve_result.get("error_type", "RetrieveError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(
result
"download"
start_time
                result.get("size_bytes") if result["success"] else None,

        except Exception as e:
            return self._handle_exception(e, result, "retrieve_data_async")

    def list_miners(self) -> Dict[str, Any]:
        """List all miners in the network.

        Returns:
            Result dictionary with list of miners
        """
        self._warn_if_async_context("list_miners")
        return super().list_miners()

    async def list_miners_async(self) -> Dict[str, Any]:
        """Async version: List all miners in the network.

        Returns:
            Result dictionary with list of miners
        """
        start_time = time.time()
        result = self._create_result_template("list_miners_async")

        try:
            # Use lotus_kit to list miners
            if self.kit:
                miners_result = await anyio.to_thread.run_sync(lambda: self.kit.list_miners())

                if miners_result.get("success", False):
                    result["success"] = True
                    result["miners"] = miners_result.get("result", [])
                    result["count"] = len(result["miners"])
                else:
                    result["error"] = miners_result.get("error", "Failed to list miners")
                    result["error_type"] = miners_result.get("error_type", "ListMinersError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_miners_async")

    def get_miner_info(self, miner_address: str) -> Dict[str, Any]:
        """Get information about a specific miner.

        Args:
            miner_address: The address of the miner

        Returns:
            Result dictionary with miner information
        """
        self._warn_if_async_context("get_miner_info")
        return super().get_miner_info(miner_address)

    async def get_miner_info_async(self, miner_address: str) -> Dict[str, Any]:
        """Async version: Get information about a specific miner.

        Args:
            miner_address: The address of the miner

        Returns:
            Result dictionary with miner information
        """
        start_time = time.time()
        result = self._create_result_template("get_miner_info_async")

        try:
            # Validate inputs
            if not miner_address:
                result["error"] = "Miner address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get miner info
            if self.kit:
                miner_result = await anyio.to_thread.run_sync(
                    lambda: self.kit.miner_get_info(miner_address)

                if miner_result.get("success", False):
                    result["success"] = True
                    result["miner_address"] = miner_address
                    result["miner_info"] = miner_result.get("result", {})
                else:
                    result["error"] = miner_result.get("error", "Failed to get miner info")
                    result["error_type"] = miner_result.get("error_type", "MinerInfoError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_miner_info_async")

    def ipfs_to_filecoin(
        self
        cid: str
        miner: str
        price: str
        duration: int
        wallet: Optional[str] = None,
        verified: bool = False,
        fast_retrieval: bool = True,
        pin: bool = True,
        """Store IPFS content on Filecoin.

        Args:
            cid: Content identifier in IPFS
            miner: The miner ID to store with
            price: The price per epoch in attoFIL
            duration: The duration of the deal in epochs
            wallet: Optional wallet address to use
            verified: Whether this is a verified deal
            fast_retrieval: Whether to enable fast retrieval
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        self._warn_if_async_context("ipfs_to_filecoin")
        return super().ipfs_to_filecoin(
            cid, miner, price, duration, wallet, verified, fast_retrieval, pin

    async def ipfs_to_filecoin_async(
        self
        cid: str
        miner: str
        price: str
        duration: int
        wallet: Optional[str] = None,
        verified: bool = False,
        fast_retrieval: bool = True,
        pin: bool = True,
        """Async version: Store IPFS content on Filecoin.

        Args:
            cid: Content identifier in IPFS
            miner: The miner ID to store with
            price: The price per epoch in attoFIL
            duration: The duration of the deal in epochs
            wallet: Optional wallet address to use
            verified: Whether this is a verified deal
            fast_retrieval: Whether to enable fast retrieval
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_template("ipfs_to_filecoin_async")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            if not miner:
                result["error"] = "Miner ID is required"
                result["error_type"] = "ValidationError"
                return result

            if not price:
                result["error"] = "Price is required"
                result["error_type"] = "ValidationError"
                return result

            if not duration:
                result["error"] = "Duration is required"
                result["error_type"] = "ValidationError"
                return result

            # Only continue if all dependencies are available
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file using anyio's event loop
            temp_fd, temp_path = await anyio.to_thread.run_sync(tempfile.mkstemp)

            try:
                # Close the file descriptor
                await anyio.to_thread.run_sync(lambda: os.close(temp_fd))

                # Retrieve content from IPFS - use async method if available
                if hasattr(self.ipfs_model, "get_content_async") and callable(
                    getattr(self.ipfs_model, "get_content_async")
                    ipfs_result = await self.ipfs_model.get_content_async(cid)
                else:
                    ipfs_result = await anyio.to_thread.run_sync(
                        lambda: self.ipfs_model.get_content(cid)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get(
                        "error", "Failed to retrieve content from IPFS"
                    result["error_type"] = ipfs_result.get("error_type", "IPFSGetError")
                    result["ipfs_result"] = ipfs_result
                    return result

                # Write content to temporary file
                content = ipfs_result.get("data")
                if not content:
                    result["error"] = "No content retrieved from IPFS"
                    result["error_type"] = "ContentMissingError"
                    result["ipfs_result"] = ipfs_result
                    return result

                # Write to file using anyio
                async with await anyio.open_file(temp_path, "wb") as f:
                    await f.write(content)

                # Pin the content if requested - use async method if available
                if pin:
                    if hasattr(self.ipfs_model, "pin_content_async") and callable(
                        getattr(self.ipfs_model, "pin_content_async")
                        pin_result = await self.ipfs_model.pin_content_async(cid)
                    else:
                        pin_result = await anyio.to_thread.run_sync(
                            lambda: self.ipfs_model.pin_content(cid)

                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                # Import file to Lotus
                import_result = await self.import_file_async(temp_path)

                if not import_result.get("success", False):
                    result["error"] = import_result.get(
                        "error", "Failed to import content to Lotus"
                    result["error_type"] = import_result.get("error_type", "LotusImportError")
                    result["import_result"] = import_result
                    return result

                # Start the deal with the imported data
                data_cid = import_result.get("root")
                if not data_cid:
                    result["error"] = "No root CID returned from import"
                    result["error_type"] = "ImportError"
                    return result

                deal_result = await self.start_deal_async(
data_cid=data_cid
miner=miner
price=price
duration=duration
wallet=wallet
verified=verified
fast_retrieval=fast_retrieval

                if not deal_result.get("success", False):
                    result["error"] = deal_result.get("error", "Failed to start deal with miner")
                    result["error_type"] = deal_result.get("error_type", "StartDealError")
                    result["deal_result"] = deal_result
                    return result

                # Set success and copy relevant fields
                result["success"] = True
                result["ipfs_cid"] = cid
                result["filecoin_cid"] = data_cid
                result["deal_cid"] = deal_result.get("deal_cid")
                result["miner"] = miner
                result["price"] = price
                result["duration"] = duration
                result["size_bytes"] = import_result.get("size_bytes")

            finally:
                # Clean up the temporary file
                try:
                    await anyio.to_thread.run_sync(lambda: os.unlink(temp_path))
                except Exception as e:
                    logger.warning(f"Error cleaning up temporary file {temp_path}: {str(e)}")

            return self._handle_operation_result(
result
"transfer"
start_time
                result.get("size_bytes") if result["success"] else None,

        except Exception as e:
            return self._handle_exception(e, result, "ipfs_to_filecoin_async")

    def filecoin_to_ipfs(self, data_cid: str, pin: bool = True) -> Dict[str, Any]:
        """Retrieve content from Filecoin and add to IPFS.

        Args:
            data_cid: The CID of the data to retrieve from Filecoin
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        self._warn_if_async_context("filecoin_to_ipfs")
        return super().filecoin_to_ipfs(data_cid, pin)

    async def filecoin_to_ipfs_async(self, data_cid: str, pin: bool = True) -> Dict[str, Any]:
        """Async version: Retrieve content from Filecoin and add to IPFS.

        Args:
            data_cid: The CID of the data to retrieve from Filecoin
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_template("filecoin_to_ipfs_async")

        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Only continue if all dependencies are available
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file using anyio's event loop
            temp_fd, temp_path = await anyio.to_thread.run_sync(tempfile.mkstemp)

            try:
                # Close the file descriptor
                await anyio.to_thread.run_sync(lambda: os.close(temp_fd))

                # Retrieve data from Filecoin
                retrieve_result = await self.retrieve_data_async(data_cid, temp_path)

                if not retrieve_result.get("success", False):
                    result["error"] = retrieve_result.get(
                        "error", "Failed to retrieve content from Filecoin"
                    result["error_type"] = retrieve_result.get(
                        "error_type", "FilecoinRetrieveError"
                    result["retrieve_result"] = retrieve_result
                    return result

                # Get file size for statistics
                file_size = await anyio.to_thread.run_sync(lambda: self._get_file_size(temp_path))

                # Read the file content
                async with await anyio.open_file(temp_path, "rb") as f:
                    content = await f.read()

                # Add to IPFS - use async method if available
                if hasattr(self.ipfs_model, "add_content_async") and callable(
                    getattr(self.ipfs_model, "add_content_async")
                    ipfs_result = await self.ipfs_model.add_content_async(content)
                else:
                    ipfs_result = await anyio.to_thread.run_sync(
                        lambda: self.ipfs_model.add_content(content)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSAddError")
                    result["ipfs_result"] = ipfs_result
                    return result

                ipfs_cid = ipfs_result.get("cid")

                # Pin the content if requested - use async method if available
                if pin and ipfs_cid:
                    if hasattr(self.ipfs_model, "pin_content_async") and callable(
                        getattr(self.ipfs_model, "pin_content_async")
                        pin_result = await self.ipfs_model.pin_content_async(ipfs_cid)
                    else:
                        pin_result = await anyio.to_thread.run_sync(
                            lambda: self.ipfs_model.pin_content(ipfs_cid)

                    if not pin_result.get("success", False):
                        logger.warning(
                            f"Failed to pin content {ipfs_cid}: {pin_result.get('error')}"

                # Set success and copy relevant fields
                result["success"] = True
                result["filecoin_cid"] = data_cid
                result["ipfs_cid"] = ipfs_cid
                result["size_bytes"] = file_size

            finally:
                # Clean up the temporary file
                try:
                    await anyio.to_thread.run_sync(lambda: os.unlink(temp_path))
                except Exception as e:
                    logger.warning(f"Error cleaning up temporary file {temp_path}: {str(e)}")

            return self._handle_operation_result(
result
"transfer"
start_time
                result.get("size_bytes") if result["success"] else None,

        except Exception as e:
            return self._handle_exception(e, result, "filecoin_to_ipfs_async")
