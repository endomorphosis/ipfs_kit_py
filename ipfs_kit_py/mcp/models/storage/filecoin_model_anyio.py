"""
Filecoin (Lotus) Model AnyIO implementation for MCP Server.

This module provides asynchronous versions of the Filecoin operations for the MCP server,
supporting both asyncio and trio via AnyIO. It wraps the synchronous FilecoinModel methods
with async equivalents for better performance in async contexts.
"""

import anyio
import logging
import os
import sniffio # Import sniffio here
import tempfile
import time
import warnings
from typing import Dict, Optional, Any, List # Added List
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
# Add the parent directory to sys.path to allow importing mcp_error_handling
# This assumes mcp_error_handling.py is at the root of the project
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling
import asyncio # Import asyncio for fallback

# Configure logger
logger = logging.getLogger(__name__)

# Helper function to run sync code in thread (using anyio or asyncio fallback)
async def run_in_thread(sync_func, *args, **kwargs):
    use_anyio = False
    try:
        # Check if anyio has the 'to_thread' attribute first
        if 'anyio' in sys.modules and hasattr(anyio, 'to_thread'):
            # Now check if 'run_sync' exists on 'to_thread'
             if hasattr(anyio.to_thread, 'run_sync'):
                 use_anyio = True
    except Exception:
        pass # Fallback to asyncio if checks fail

    if use_anyio:
        # Use anyio if available
        try:
            return await anyio.to_thread.run_sync(sync_func, *args, **kwargs)
        except Exception as anyio_err:
            logger.warning(f"anyio.to_thread.run_sync failed: {anyio_err}. Falling back to asyncio.")
            # Fall through to asyncio fallback if anyio fails unexpectedly
    # Fallback to asyncio (if use_anyio is False or if anyio call failed)
    logger.debug("Falling back to asyncio loop.run_in_executor for run_in_thread")
    loop = asyncio.get_running_loop()
    # functools.partial can help pass args/kwargs to loop.run_in_executor
    import functools
    func_call = functools.partial(sync_func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


class FilecoinModelAnyIO(FilecoinModel):
    """AnyIO-compatible model for Filecoin (Lotus) operations.

    This class extends the synchronous FilecoinModel with asynchronous versions of
    all methods, ensuring efficient operation in async contexts. It supports both
    asyncio and trio via the AnyIO library.
    """
    def __init__(
        self,
        lotus_kit_instance=None,
        ipfs_model=None,
        cache_manager=None,
        credential_manager=None
    ):
        """Initialize FilecoinModelAnyIO with dependencies.

        Args:
            lotus_kit_instance: lotus_kit instance for Filecoin operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        # Correctly call super().__init__ from the base FilecoinModel
        super().__init__(
            lotus_kit_instance=lotus_kit_instance,
            ipfs_model=ipfs_model, # Pass ipfs_model here
            cache_manager=cache_manager,
            credential_manager=credential_manager
        )
        # Explicitly store kit and ipfs_model instances for clarity,
        # even if base class also stores them.
        self.kit = lotus_kit_instance
        self.ipfs_model = ipfs_model
        logger.info("FilecoinModelAnyIO initialized")

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
                stacklevel=3
            )

    # --- Helper Methods (Basic stubs for now) ---
    def _create_result_template(self, operation_name: str) -> Dict[str, Any]:
        """Creates a standard result dictionary template."""
        return {"success": False, "operation": operation_name, "timestamp": time.time()}

    def _get_file_size(self, file_path: str) -> Optional[int]:
        """Safely get file size."""
        try:
            return os.path.getsize(file_path)
        except OSError:
            logger.warning(f"Could not get size for file: {file_path}")
            return None

    def _handle_operation_result(self, result, operation_type, start_time, size=None):
        """Basic handler for operation results."""
        result["duration_ms"] = (time.time() - start_time) * 1000
        # Add metrics/logging here if needed in the future
        return result

    def _handle_exception(self, e, result, operation_name):
        """Basic handler for exceptions."""
        logger.error(f"Exception in {operation_name}: {e}", exc_info=True)
        result["success"] = False # Ensure success is false
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        if "timestamp" in result:
             result["duration_ms"] = (time.time() - result["timestamp"]) * 1000
        return result

    # --- Overridden Sync Methods ---
    def check_connection(self) -> Dict[str, Any]:
        self._warn_if_async_context("check_connection")
        return super().check_connection()

    def list_wallets(self) -> Dict[str, Any]:
        self._warn_if_async_context("list_wallets")
        return super().list_wallets()

    def get_wallet_balance(self, address: str) -> Dict[str, Any]:
        self._warn_if_async_context("get_wallet_balance")
        return super().get_wallet_balance(address)

    def create_wallet(self, wallet_type: str = "bls") -> Dict[str, Any]:
        self._warn_if_async_context("create_wallet")
        return super().create_wallet(wallet_type)

    def import_file(self, file_path: str) -> Dict[str, Any]:
        self._warn_if_async_context("import_file")
        return super().import_file(file_path)

    def list_imports(self) -> Dict[str, Any]:
        self._warn_if_async_context("list_imports")
        return super().list_imports()

    def find_data(self, data_cid: str) -> Dict[str, Any]:
        self._warn_if_async_context("find_data")
        return super().find_data(data_cid)

    def list_deals(self) -> Dict[str, Any]:
        self._warn_if_async_context("list_deals")
        return super().list_deals()

    def get_deal_info(self, deal_id: int) -> Dict[str, Any]:
        self._warn_if_async_context("get_deal_info")
        return super().get_deal_info(deal_id)

    def start_deal(
        self, data_cid: str, miner: str, price: str, duration: int,
        wallet: Optional[str] = None, verified: bool = False, fast_retrieval: bool = True
    ) -> Dict[str, Any]:
        self._warn_if_async_context("start_deal")
        return super().start_deal(
            data_cid=data_cid, miner=miner, price=price, duration=duration,
            wallet=wallet, verified=verified, fast_retrieval=fast_retrieval
        )

    def retrieve_data(self, data_cid: str, out_file: str) -> Dict[str, Any]:
        self._warn_if_async_context("retrieve_data")
        return super().retrieve_data(data_cid, out_file)

    def list_miners(self) -> Dict[str, Any]:
        self._warn_if_async_context("list_miners")
        return super().list_miners()

    def get_miner_info(self, miner_address: str) -> Dict[str, Any]:
        self._warn_if_async_context("get_miner_info")
        return super().get_miner_info(miner_address)

    def ipfs_to_filecoin(
        self, cid: str, miner: str, price: str, duration: int,
        wallet: Optional[str] = None, verified: bool = False,
        fast_retrieval: bool = True, pin: bool = True
    ) -> Dict[str, Any]:
        self._warn_if_async_context("ipfs_to_filecoin")
        return super().ipfs_to_filecoin(
            cid=cid, miner=miner, price=price, duration=duration,
            wallet=wallet, verified=verified, fast_retrieval=fast_retrieval, pin=pin
        )

    def filecoin_to_ipfs(self, data_cid: str, pin: bool = True) -> Dict[str, Any]:
        self._warn_if_async_context("filecoin_to_ipfs")
        return super().filecoin_to_ipfs(data_cid, pin)

    # --- Async Methods ---
    async def check_connection_async(self) -> Dict[str, Any]:
        """Async version: Check connection to the Lotus API."""
        start_time = time.time()
        result = self._create_result_template("check_connection_async")
        try:
            if not self.kit: raise RuntimeError("Lotus kit not available")
            connection_result = await run_in_thread(self.kit.check_connection) # Use helper
            # Add check for connection_result being None or failure
            if connection_result and connection_result.get("success", False):
                result["success"] = True
                result["connected"] = True
                result["version"] = connection_result.get("result") # Safe get
            else:
                result["error"] = connection_result.get("error", "Failed to connect to Lotus API") if connection_result else "Connection check failed unexpectedly"
                result["error_type"] = connection_result.get("error_type", "ConnectionError") if connection_result else "UnknownError"
            return self._handle_operation_result(result, "configure", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "check_connection_async")

    async def list_wallets_async(self) -> Dict[str, Any]:
        """Async version: List all wallet addresses."""
        start_time = time.time()
        result = self._create_result_template("list_wallets_async")
        try:
            if not self.kit: raise RuntimeError("Lotus kit not available")
            wallet_result = await run_in_thread(self.kit.list_wallets) # Use helper
            # Add check for wallet_result being None or failure
            if wallet_result and wallet_result.get("success", False):
                result["success"] = True
                wallets = wallet_result.get("result", []) # Safe get
                result["wallets"] = wallets
                result["count"] = len(wallets) if isinstance(wallets, list) else 0
            else:
                result["error"] = wallet_result.get("error", "Failed to list wallets") if wallet_result else "List wallets failed unexpectedly"
                result["error_type"] = wallet_result.get("error_type", "WalletListError") if wallet_result else "UnknownError"
            return self._handle_operation_result(result, "list", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "list_wallets_async")

    async def get_wallet_balance_async(self, address: str) -> Dict[str, Any]:
        """Async version: Get wallet balance."""
        start_time = time.time()
        result = self._create_result_template("get_wallet_balance_async")
        try:
            if not address: raise ValueError("Wallet address is required")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            balance_result = await run_in_thread(self.kit.wallet_balance, address) # Use helper
            # Add check for balance_result being None or failure
            if balance_result and balance_result.get("success", False):
                result["success"] = True
                result["address"] = address
                result["balance"] = balance_result.get("result") # Safe get
            else:
                result["error"] = balance_result.get("error", "Failed to get wallet balance") if balance_result else "Get balance failed unexpectedly"
                result["error_type"] = balance_result.get("error_type", "WalletBalanceError") if balance_result else "UnknownError"
            return self._handle_operation_result(result, "read", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "get_wallet_balance_async")

    async def create_wallet_async(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Async version: Create a new wallet."""
        start_time = time.time()
        result = self._create_result_template("create_wallet_async")
        try:
            valid_types = ["bls", "secp256k1"]
            if wallet_type not in valid_types:
                raise ValueError(f"Invalid wallet type. Must be one of: {', '.join(valid_types)}")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            wallet_result = await run_in_thread(self.kit.create_wallet, wallet_type) # Use helper
            # Add check for wallet_result being None or failure
            if wallet_result and wallet_result.get("success", False):
                result["success"] = True
                result["address"] = wallet_result.get("result") # Safe get
                result["wallet_type"] = wallet_type
            else:
                result["error"] = wallet_result.get("error", "Failed to create wallet") if wallet_result else "Create wallet failed unexpectedly"
                result["error_type"] = wallet_result.get("error_type", "WalletCreationError") if wallet_result else "UnknownError"
            return self._handle_operation_result(result, "create", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "create_wallet_async")

    async def import_file_async(self, file_path: str) -> Dict[str, Any]:
        """Async version: Import a file into the Lotus client."""
        start_time = time.time()
        result = self._create_result_template("import_file_async")
        file_size = None
        try:
            file_exists = await run_in_thread(os.path.exists, file_path) # Use helper
            if not file_exists: raise FileNotFoundError(f"File not found: {file_path}")
            file_size = await run_in_thread(self._get_file_size, file_path) # Use helper
            if not self.kit: raise RuntimeError("Lotus kit not available")
            import_result = await run_in_thread(self.kit.client_import, file_path) # Use helper
            # Add check for import_result being None or failure
            if import_result and import_result.get("success", False):
                result["success"] = True
                # Safely access nested dictionary keys
                import_details = import_result.get("result", {})
                root_cid = import_details.get("Root", {}).get("/") if isinstance(import_details.get("Root"), dict) else None
                result["root"] = root_cid
                result["file_path"] = file_path
                result["size_bytes"] = file_size
                if isinstance(import_details, dict):
                    for field in ["ImportID", "Size", "Status"]:
                        if field in import_details:
                            result[field.lower()] = import_details[field]
            else:
                result["error"] = import_result.get("error", "Failed to import file") if import_result else "Import file failed unexpectedly"
                result["error_type"] = import_result.get("error_type", "ImportError") if import_result else "UnknownError"
            return self._handle_operation_result(result, "upload", start_time, file_size)
        except Exception as e:
            return self._handle_exception(e, result, "import_file_async")

    async def list_imports_async(self) -> Dict[str, Any]:
        """Async version: List all imported files."""
        start_time = time.time()
        result = self._create_result_template("list_imports_async")
        try:
            if not self.kit: raise RuntimeError("Lotus kit not available")
            imports_result = await run_in_thread(self.kit.client_list_imports) # Use helper
            if imports_result and imports_result.get("success", False):
                result["success"] = True
                result["imports"] = imports_result.get("result", [])
                result["count"] = len(result["imports"])
            else:
                result["error"] = imports_result.get("error", "Failed to list imports") if imports_result else "List imports failed unexpectedly"
                result["error_type"] = imports_result.get("error_type", "ListImportsError") if imports_result else "UnknownError"
            return self._handle_operation_result(result, "list", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "list_imports_async")

    async def find_data_async(self, data_cid: str) -> Dict[str, Any]:
        """Async version: Find where data is stored."""
        start_time = time.time()
        result = self._create_result_template("find_data_async")
        try:
            if not data_cid: raise ValueError("Data CID is required")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            find_result = await run_in_thread(self.kit.client_find_data, data_cid) # Use helper
            if find_result and find_result.get("success", False):
                result["success"] = True
                result["cid"] = data_cid
                result["locations"] = find_result.get("result", [])
                result["count"] = len(result["locations"])
            else:
                result["error"] = find_result.get("error", "Failed to find data") if find_result else "Find data failed unexpectedly"
                result["error_type"] = find_result.get("error_type", "FindDataError") if find_result else "UnknownError"
            return self._handle_operation_result(result, "read", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "find_data_async")

    async def list_deals_async(self) -> Dict[str, Any]:
        """Async version: List all deals made by the client."""
        start_time = time.time()
        result = self._create_result_template("list_deals_async")
        try:
            if not self.kit: raise RuntimeError("Lotus kit not available")
            deals_result = await run_in_thread(self.kit.client_list_deals) # Use helper
            if deals_result and deals_result.get("success", False):
                result["success"] = True
                result["deals"] = deals_result.get("result", [])
                result["count"] = len(result["deals"])
            else:
                result["error"] = deals_result.get("error", "Failed to list deals") if deals_result else "List deals failed unexpectedly"
                result["error_type"] = deals_result.get("error_type", "ListDealsError") if deals_result else "UnknownError"
            return self._handle_operation_result(result, "list", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "list_deals_async")

    async def get_deal_info_async(self, deal_id: int) -> Dict[str, Any]:
        """Async version: Get information about a specific deal."""
        start_time = time.time()
        result = self._create_result_template("get_deal_info_async")
        try:
            if not isinstance(deal_id, int): raise ValueError("Deal ID must be an integer")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            deal_result = await run_in_thread(self.kit.client_deal_info, deal_id) # Use helper
            if deal_result and deal_result.get("success", False):
                result["success"] = True
                result["deal_id"] = deal_id
                result["deal_info"] = deal_result.get("result", {})
            else:
                result["error"] = deal_result.get("error", "Failed to get deal info") if deal_result else "Get deal info failed unexpectedly"
                result["error_type"] = deal_result.get("error_type", "DealInfoError") if deal_result else "UnknownError"
            return self._handle_operation_result(result, "read", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "get_deal_info_async")

    async def start_deal_async(
        self, data_cid: str, miner: str, price: str, duration: int,
        wallet: Optional[str] = None, verified: bool = False, fast_retrieval: bool = True
    ) -> Dict[str, Any]:
        """Async version: Start a storage deal with a miner."""
        start_time = time.time()
        result = self._create_result_template("start_deal_async")
        try:
            if not all([data_cid, miner, price, duration]):
                 raise ValueError("Missing required parameters for starting deal")
            if not self.kit: raise RuntimeError("Lotus kit not available")

            if not wallet:
                wallet_result = await run_in_thread(self.kit.list_wallets) # Use helper
                if wallet_result and wallet_result.get("success", False) and wallet_result.get("result"):
                    wallet = wallet_result["result"][0]
                else:
                    logger.warning("Could not determine default wallet, proceeding without it.")

            deal_result = await run_in_thread( # Use helper
                self.kit.client_start_deal,
                data_cid=data_cid, miner=miner, price=price, duration=duration,
                wallet=wallet, verified=verified, fast_retrieval=fast_retrieval
            )
            if deal_result and deal_result.get("success", False):
                result["success"] = True
                result["deal_cid"] = deal_result.get("result", {}).get("/")
                result["data_cid"] = data_cid
                result["miner"] = miner
                result["price"] = price
                result["duration"] = duration
                result["wallet"] = wallet
                result["verified"] = verified
                result["fast_retrieval"] = fast_retrieval
            else:
                result["error"] = deal_result.get("error", "Failed to start deal") if deal_result else "Start deal failed unexpectedly"
                result["error_type"] = deal_result.get("error_type", "StartDealError") if deal_result else "UnknownError"
            return self._handle_operation_result(result, "create", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "start_deal_async")

    async def retrieve_data_async(self, data_cid: str, out_file: str) -> Dict[str, Any]:
        """Async version: Retrieve data from the Filecoin network."""
        start_time = time.time()
        result = self._create_result_template("retrieve_data_async")
        file_size = None
        try:
            if not data_cid: raise ValueError("Data CID is required")
            if not out_file: raise ValueError("Output file path is required")
            if not self.kit: raise RuntimeError("Lotus kit not available")

            out_dir = os.path.dirname(os.path.abspath(out_file))
            await run_in_thread(os.makedirs, out_dir, exist_ok=True) # Use helper

            retrieve_result = await run_in_thread(self.kit.client_retrieve, data_cid, out_file) # Use helper
            if retrieve_result and retrieve_result.get("success", False):
                file_size = await run_in_thread(self._get_file_size, out_file) # Use helper
                result["success"] = True
                result["cid"] = data_cid
                result["file_path"] = out_file
                result["size_bytes"] = file_size
            else:
                result["error"] = retrieve_result.get("error", "Failed to retrieve data") if retrieve_result else "Retrieve data failed unexpectedly"
                result["error_type"] = retrieve_result.get("error_type", "RetrieveError") if retrieve_result else "UnknownError"
            return self._handle_operation_result(result, "download", start_time, file_size)
        except Exception as e:
            return self._handle_exception(e, result, "retrieve_data_async")

    async def list_miners_async(self) -> Dict[str, Any]:
        """Async version: List all miners in the network."""
        start_time = time.time()
        result = self._create_result_template("list_miners_async")
        try:
            if not self.kit: raise RuntimeError("Lotus kit not available")
            miners_result = await run_in_thread(self.kit.list_miners) # Use helper
            if miners_result and miners_result.get("success", False):
                result["success"] = True
                result["miners"] = miners_result.get("result", [])
                result["count"] = len(result["miners"])
            else:
                result["error"] = miners_result.get("error", "Failed to list miners") if miners_result else "List miners failed unexpectedly"
                result["error_type"] = miners_result.get("error_type", "ListMinersError") if miners_result else "UnknownError"
            return self._handle_operation_result(result, "list", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "list_miners_async")

    async def get_miner_info_async(self, miner_address: str) -> Dict[str, Any]:
        """Async version: Get information about a specific miner."""
        start_time = time.time()
        result = self._create_result_template("get_miner_info_async")
        try:
            if not miner_address: raise ValueError("Miner address is required")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            miner_result = await run_in_thread(self.kit.miner_get_info, miner_address) # Use helper
            if miner_result and miner_result.get("success", False):
                result["success"] = True
                result["miner_address"] = miner_address
                result["miner_info"] = miner_result.get("result", {})
            else:
                result["error"] = miner_result.get("error", "Failed to get miner info") if miner_result else "Get miner info failed unexpectedly"
                result["error_type"] = miner_result.get("error_type", "MinerInfoError") if miner_result else "UnknownError"
            return self._handle_operation_result(result, "read", start_time)
        except Exception as e:
            return self._handle_exception(e, result, "get_miner_info_async")

    async def ipfs_to_filecoin_async(
        self, cid: str, miner: str, price: str, duration: int,
        wallet: Optional[str] = None, verified: bool = False,
        fast_retrieval: bool = True, pin: bool = True
    ) -> Dict[str, Any]:
        """Async version: Store IPFS content on Filecoin."""
        start_time = time.time()
        result = self._create_result_template("ipfs_to_filecoin_async")
        temp_path = ""
        temp_fd = -1 # Initialize fd
        try:
            if not all([cid, miner, price, duration]):
                 raise ValueError("Missing required parameters for IPFS to Filecoin transfer")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            if not self.ipfs_model: raise RuntimeError("IPFS model not available")

            temp_fd, temp_path = await run_in_thread(tempfile.mkstemp) # Use helper
            await run_in_thread(os.close, temp_fd) # Use helper
            temp_fd = -1 # Mark as closed

            if hasattr(self.ipfs_model, "get_content_async"):
                ipfs_result = await self.ipfs_model.get_content_async(cid)
            else:
                ipfs_result = await run_in_thread(self.ipfs_model.get_content, cid) # Use helper

            if not ipfs_result or not ipfs_result.get("success", False):
                raise RuntimeError(f"IPFS Get Error: {ipfs_result.get('error') if ipfs_result else 'Unknown'}")

            content = ipfs_result.get("data")
            if not content: raise RuntimeError("No content retrieved from IPFS")

            # Ensure content is bytes before writing
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            elif isinstance(content, bytes):
                content_bytes = content
            else:
                raise TypeError("IPFS content data must be bytes or str")

            async with await anyio.open_file(temp_path, "wb") as f:
                await f.write(content_bytes)

            if pin:
                if hasattr(self.ipfs_model, "pin_content_async"):
                    pin_result = await self.ipfs_model.pin_content_async(cid)
                else:
                    pin_result = await run_in_thread(self.ipfs_model.pin_content, cid) # Use helper
                if not pin_result or not pin_result.get("success", False):
                    logger.warning(f"Failed to pin content {cid}: {pin_result.get('error') if pin_result else 'Unknown'}")

            import_result = await self.import_file_async(temp_path)
            if not import_result or not import_result.get("success", False):
                raise RuntimeError(f"Lotus Import Error: {import_result.get('error') if import_result else 'Unknown'}")

            data_cid = import_result.get("root")
            if not data_cid: raise RuntimeError("No root CID returned from import")

            deal_result = await self.start_deal_async(
                data_cid=data_cid, miner=miner, price=price, duration=duration,
                wallet=wallet, verified=verified, fast_retrieval=fast_retrieval
            )
            if not deal_result or not deal_result.get("success", False):
                raise RuntimeError(f"Start Deal Error: {deal_result.get('error') if deal_result else 'Unknown'}")

            result["success"] = True
            result["ipfs_cid"] = cid
            result["filecoin_cid"] = data_cid
            result["deal_cid"] = deal_result.get("deal_cid")
            result["miner"] = miner
            result["price"] = price
            result["duration"] = duration
            result["size_bytes"] = import_result.get("size_bytes")

            return self._handle_operation_result(result, "transfer", start_time, result.get("size_bytes"))

        except Exception as e:
            return self._handle_exception(e, result, "ipfs_to_filecoin_async")
        finally:
            if temp_fd != -1: # Check if fd needs closing
                 try: await run_in_thread(os.close, temp_fd) # Use helper
                 except Exception: pass
            if temp_path and os.path.exists(temp_path):
                try: await run_in_thread(os.unlink, temp_path) # Use helper
                except Exception as e_unlink: logger.warning(f"Error cleaning up temp file {temp_path}: {e_unlink}")


    async def filecoin_to_ipfs_async(self, data_cid: str, pin: bool = True) -> Dict[str, Any]:
        """Async version: Retrieve content from Filecoin and add to IPFS."""
        start_time = time.time()
        result = self._create_result_template("filecoin_to_ipfs_async")
        temp_path = ""
        temp_fd = -1 # Initialize fd
        file_size = None
        try:
            if not data_cid: raise ValueError("Data CID is required")
            if not self.kit: raise RuntimeError("Lotus kit not available")
            if not self.ipfs_model: raise RuntimeError("IPFS model not available")

            temp_fd, temp_path = await run_in_thread(tempfile.mkstemp) # Use helper
            await run_in_thread(os.close, temp_fd) # Use helper
            temp_fd = -1 # Mark as closed

            retrieve_result = await self.retrieve_data_async(data_cid, temp_path)
            if not retrieve_result or not retrieve_result.get("success", False):
                raise RuntimeError(f"Filecoin Retrieve Error: {retrieve_result.get('error') if retrieve_result else 'Unknown'}")

            file_size = await run_in_thread(self._get_file_size, temp_path) # Use helper

            async with await anyio.open_file(temp_path, "rb") as f:
                content = await f.read()

            if hasattr(self.ipfs_model, "add_content_async"):
                ipfs_result = await self.ipfs_model.add_content_async(content)
            else:
                ipfs_result = await run_in_thread(self.ipfs_model.add_content, content) # Use helper

            if not ipfs_result or not ipfs_result.get("success", False):
                raise RuntimeError(f"IPFS Add Error: {ipfs_result.get('error') if ipfs_result else 'Unknown'}")

            ipfs_cid = ipfs_result.get("cid")

            if pin and ipfs_cid:
                if hasattr(self.ipfs_model, "pin_content_async"):
                    pin_result = await self.ipfs_model.pin_content_async(ipfs_cid)
                else:
                    pin_result = await run_in_thread(self.ipfs_model.pin_content, ipfs_cid) # Use helper
                if not pin_result or not pin_result.get("success", False):
                    logger.warning(f"Failed to pin content {ipfs_cid}: {pin_result.get('error') if pin_result else 'Unknown'}")

            result["success"] = True
            result["filecoin_cid"] = data_cid
            result["ipfs_cid"] = ipfs_cid
            result["size_bytes"] = file_size

            return self._handle_operation_result(result, "transfer", start_time, file_size)

        except Exception as e:
            return self._handle_exception(e, result, "filecoin_to_ipfs_async")
        finally:
            if temp_fd != -1: # Check if fd needs closing
                 try: await run_in_thread(os.close, temp_fd) # Use helper
                 except Exception: pass
            if temp_path and os.path.exists(temp_path):
                try: await run_in_thread(os.unlink, temp_path) # Use helper
                except Exception as e_unlink: logger.warning(f"Error cleaning up temp file {temp_path}: {e_unlink}")