"""
Filecoin (Lotus) Model for MCP Server.

This module provides the business logic for Filecoin operations in the MCP server.
It relies on the lotus_kit module for underlying functionality and implements the
BaseStorageModel interface for consistent operation patterns.
"""

import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any
from ipfs_kit_py.mcp.models.storage.base_storage_model import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class FilecoinModel(BaseStorageModel):
    """Model for Filecoin (Lotus) operations.

    This class implements Filecoin/Lotus storage operations using the BaseStorageModel interface.
    It provides methods for working with Filecoin storage, including wallet management,
    deal creation, data import/export, and integration with IPFS for cross-backend operations.
    """
    def __init__(
        self, # Added missing comma
        lotus_kit_instance = None,
        ipfs_model = None,
        cache_manager = None,
        credential_manager = None
    ):
        """Initialize Filecoin model with dependencies.

        Args:
            lotus_kit_instance: lotus_kit instance for Filecoin operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(lotus_kit_instance, cache_manager, credential_manager)

        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model

        logger.info("Filecoin Model initialized")

    def check_connection(self) -> Dict[str, Any]:
        """Check connection to the Lotus API.

        Returns:
            Result dictionary with connection status
        """
        start_time = time.time()
        result = self._create_result_template("check_connection")

        try:
            # Use lotus_kit to check connection
            if self.kit:
                connection_result = self.kit.check_connection()

                if connection_result.get("success", False):
                    result["success"] = True
                    result["connected"] = True

                    # Include version information if available
                    if "result" in connection_result:
                        result["version"] = connection_result["result"]
                else:
                    result["error"] = connection_result.get("error", "Failed to connect to Lotus API")
                    result["error_type"] = connection_result.get("error_type", "ConnectionError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "configure", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "check_connection")

    def list_wallets(self) -> Dict[str, Any]:
        """List all wallet addresses.

        Returns:
            Result dictionary with wallet addresses
        """
        start_time = time.time()
        result = self._create_result_template("list_wallets")

        try:
            # Use lotus_kit to list wallets
            if self.kit:
                wallet_result = self.kit.list_wallets()

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
            return self._handle_exception(e, result, "list_wallets")

    def get_wallet_balance(self, address: str) -> Dict[str, Any]:
        """Get wallet balance.

        Args:
            address: The wallet address to check balance for

        Returns:
            Result dictionary with wallet balance
        """
        start_time = time.time()
        result = self._create_result_template("get_wallet_balance")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Wallet address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get wallet balance
            if self.kit:
                balance_result = self.kit.wallet_balance(address)

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
            return self._handle_exception(e, result, "get_wallet_balance")

    def create_wallet(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Create a new wallet.

        Args:
            wallet_type: The type of wallet to create (bls or secp256k1)

        Returns:
            Result dictionary with new wallet address
        """
        start_time = time.time()
        result = self._create_result_template("create_wallet")

        try:
            # Validate wallet_type
            valid_types = ["bls", "secp256k1"]
            if wallet_type not in valid_types:
                result["error"] = f"Invalid wallet type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to create wallet
            if self.kit:
                wallet_result = self.kit.create_wallet(wallet_type)

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
            return self._handle_exception(e, result, "create_wallet")

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """Import a file into the Lotus client.

        Args:
            file_path: Path to the file to import

        Returns:
            Result dictionary with import information
        """
        start_time = time.time()
        result = self._create_result_template("import_file")

        try:
            # Validate inputs
            if not os.path.exists(file_path):
                result["error"] = f"File not found: {file_path}"
                result["error_type"] = "FileNotFoundError"
                return result

            # Get file size for statistics
            file_size = self._get_file_size(file_path)

            # Use lotus_kit to import the file
            if self.kit:
                import_result = self.kit.client_import(file_path)

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
            )
        except Exception as e:
            return self._handle_exception(e, result, "import_file")

    def list_imports(self) -> Dict[str, Any]:
        """List all imported files.

        Returns:
            Result dictionary with list of imports
        """
        start_time = time.time()
        result = self._create_result_template("list_imports")

        try:
            # Use lotus_kit to list imports
            if self.kit:
                imports_result = self.kit.client_list_imports()

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
            return self._handle_exception(e, result, "list_imports")

    def find_data(self, data_cid: str) -> Dict[str, Any]:
        """Find where data is stored.

        Args:
            data_cid: The CID of the data to find

        Returns:
            Result dictionary with data location information
        """
        start_time = time.time()
        result = self._create_result_template("find_data")

        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to find data
            if self.kit:
                find_result = self.kit.client_find_data(data_cid)

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
            return self._handle_exception(e, result, "find_data")

    def list_deals(self) -> Dict[str, Any]:
        """List all deals made by the client.

        Returns:
            Result dictionary with list of deals
        """
        start_time = time.time()
        result = self._create_result_template("list_deals")

        try:
            # Use lotus_kit to list deals
            if self.kit:
                deals_result = self.kit.client_list_deals()

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
            return self._handle_exception(e, result, "list_deals")

    def get_deal_info(self, deal_id: int) -> Dict[str, Any]:
        """Get information about a specific deal.

        Args:
            deal_id: ID of the deal to get information about

        Returns:
            Result dictionary with deal information
        """
        start_time = time.time()
        result = self._create_result_template("get_deal_info")

        try:
            # Validate inputs
            if not isinstance(deal_id, int):
                result["error"] = "Deal ID must be an integer"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get deal info
            if self.kit:
                deal_result = self.kit.client_deal_info(deal_id)

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
            return self._handle_exception(e, result, "get_deal_info")

    def start_deal(
        self,
        data_cid: str,
        miner: str,
        price: str,
        duration: int,
        wallet: Optional[str] = None,
        verified: bool = False,
        fast_retrieval: bool = True,
    ) -> Dict[str, Any]:
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
        start_time = time.time()
        result = self._create_result_template("start_deal")

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
                wallet_result = self.kit.list_wallets()
                if wallet_result.get("success", False) and wallet_result.get("result"):
                    wallet = wallet_result["result"][0]

            # Use lotus_kit to start deal
            if self.kit:
                deal_result = self.kit.client_start_deal(
                    data_cid=data_cid,
                    miner=miner,
                    price=price,
                    duration=duration,
                    wallet=wallet,
                    verified=verified,
                    fast_retrieval=fast_retrieval
                )

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
            return self._handle_exception(e, result, "start_deal")

    def retrieve_data(self, data_cid: str, out_file: str) -> Dict[str, Any]:
        """Retrieve data from the Filecoin network.

        Args:
            data_cid: The CID of the data to retrieve
            out_file: Path where the retrieved data should be saved

        Returns:
            Result dictionary with retrieval information
        """
        start_time = time.time()
        result = self._create_result_template("retrieve_data")

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
            os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)

            # Use lotus_kit to retrieve data
            if self.kit:
                retrieve_result = self.kit.client_retrieve(data_cid, out_file)

                if retrieve_result.get("success", False):
                    # Get file size for statistics
                    file_size = self._get_file_size(out_file)

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
                result,
                "download",
                start_time,
                result.get("size_bytes") if result["success"] else None,
            )
        except Exception as e:
            return self._handle_exception(e, result, "retrieve_data")

    def list_miners(self) -> Dict[str, Any]:
        """List all miners in the network.

        Returns:
            Result dictionary with list of miners
        """
        start_time = time.time()
        result = self._create_result_template("list_miners")

        try:
            # Use lotus_kit to list miners
            if self.kit:
                miners_result = self.kit.list_miners()

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
            return self._handle_exception(e, result, "list_miners")

    def get_miner_info(self, miner_address: str) -> Dict[str, Any]:
        """Get information about a specific miner.

        Args:
            miner_address: The address of the miner

        Returns:
            Result dictionary with miner information
        """
        start_time = time.time()
        result = self._create_result_template("get_miner_info")

        try:
            # Validate inputs
            if not miner_address:
                result["error"] = "Miner address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get miner info
            if self.kit:
                miner_result = self.kit.miner_get_info(miner_address)

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
            return self._handle_exception(e, result, "get_miner_info")

    def ipfs_to_filecoin(
        self,
        cid: str,
        miner: str,
        price: str,
        duration: int,
        wallet: Optional[str] = None,
        verified: bool = False,
        fast_retrieval: bool = True,
        pin: bool = True,
    ) -> Dict[str, Any]:
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
        start_time = time.time()
        result = self._create_result_template("ipfs_to_filecoin")

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

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{cid}") as temp_file:
                temp_path = temp_file.name

                # Retrieve content from IPFS
                ipfs_result = self.ipfs_model.get_content(cid)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to retrieve content from IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSGetError")
                    result["ipfs_result"] = ipfs_result
                    os.unlink(temp_path)
                    return result

                # Write content to temporary file
                content = ipfs_result.get("data")
                if not content:
                    result["error"] = "No content retrieved from IPFS"
                    result["error_type"] = "ContentMissingError"
                    result["ipfs_result"] = ipfs_result
                    os.unlink(temp_path)
                    return result

                temp_file.write(content)
                temp_file.flush()

                # Pin the content if requested
                if pin:
                    pin_result = self.ipfs_model.pin_content(cid)
                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                # Import file to Lotus
                import_result = self.import_file(temp_path)

                # Clean up the temporary file
                os.unlink(temp_path)

                if not import_result.get("success", False):
                    result["error"] = import_result.get("error", "Failed to import content to Lotus")
                    result["error_type"] = import_result.get("error_type", "LotusImportError")
                    result["import_result"] = import_result
                    return result

                # Start the deal with the imported data
                data_cid = import_result.get("root")
                if not data_cid:
                    result["error"] = "No root CID returned from import"
                    result["error_type"] = "ImportError"
                    return result

                deal_result = self.start_deal(
                    data_cid=data_cid,
                    miner=miner,
                    price=price,
                    duration=duration,
                    wallet=wallet,
                    verified=verified,
                    fast_retrieval=fast_retrieval
                )

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

            return self._handle_operation_result(
                result,
                "transfer",
                start_time,
                result.get("size_bytes") if result["success"] else None,
            )
        except Exception as e:
            return self._handle_exception(e, result, "ipfs_to_filecoin")

    def filecoin_to_ipfs(self, data_cid: str, pin: bool = True) -> Dict[str, Any]:
        """Retrieve content from Filecoin and add to IPFS.

        Args:
            data_cid: The CID of the data to retrieve from Filecoin
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_template("filecoin_to_ipfs")

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

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

                # Retrieve data from Filecoin
                retrieve_result = self.retrieve_data(data_cid, temp_path)

                if not retrieve_result.get("success", False):
                    result["error"] = retrieve_result.get("error", "Failed to retrieve content from Filecoin")
                    result["error_type"] = retrieve_result.get("error_type", "FilecoinRetrieveError")
                    result["retrieve_result"] = retrieve_result
                    os.unlink(temp_path)
                    return result

                # Get file size for statistics
                file_size = self._get_file_size(temp_path)

                # Read the file content
                with open(temp_path, "rb") as f:
                    content = f.read()

                # Add to IPFS
                ipfs_result = self.ipfs_model.add_content(content)

                # Clean up the temporary file
                os.unlink(temp_path)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSAddError")
                    result["ipfs_result"] = ipfs_result
                    return result

                ipfs_cid = ipfs_result.get("cid")

                # Pin the content if requested
                if pin and ipfs_cid:
                    pin_result = self.ipfs_model.pin_content(ipfs_cid)
                    if not pin_result.get("success", False):
                        logger.warning(
                            f"Failed to pin content {ipfs_cid}: {pin_result.get('error')}"
                        )

                # Set success and copy relevant fields
                result["success"] = True
                result["filecoin_cid"] = data_cid
                result["ipfs_cid"] = ipfs_cid
                result["size_bytes"] = file_size

            return self._handle_operation_result(
                result,
                "transfer",
                start_time,
                result.get("size_bytes") if result["success"] else None,
            )
        except Exception as e:
            return self._handle_exception(e, result, "filecoin_to_ipfs")

    # Chain methods
    def get_tipset(self, tipset_key: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get a tipset by its key.

        Args:
            tipset_key: List of block CIDs forming the tipset key.

        Returns:
            Result dictionary with tipset details.
        """
        start_time = time.time()
        result = self._create_result_template("get_tipset")

        try:
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            tipset_result = self.kit.get_tipset(tipset_key)
            result.update(tipset_result)
            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_tipset")

    def get_chain_head(self) -> Dict[str, Any]:
        """Get the current head of the chain.

        Returns:
            Result dictionary with chain head information
        """
        start_time = time.time()
        result = self._create_result_template("get_chain_head")

        try:
            if self.kit:
                head_result = self.kit._call_api("Filecoin.ChainHead")

                if head_result.get("success", False):
                    result["success"] = True
                    result["chain_head"] = head_result.get("result")
                else:
                    result["error"] = head_result.get("error", "Failed to get chain head")
                    result["error_type"] = head_result.get("error_type", "ChainHeadError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_chain_head")

    def get_block(self, block_cid: str) -> Dict[str, Any]:
        """Get block information by CID.

        Args:
            block_cid: The CID of the block to retrieve

        Returns:
            Result dictionary with block information
        """
        start_time = time.time()
        result = self._create_result_template("get_block")

        try:
            # Validate inputs
            if not block_cid:
                result["error"] = "Block CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get block
            if self.kit:
                # Prepare CID parameter in the format expected by the API
                cid_param = {"/": block_cid} if not block_cid.startswith("{") else block_cid

                block_result = self.kit.chain_get_block(cid_param) # Pass cid_param

                if block_result.get("success", False):
                    result["success"] = True
                    result["block"] = block_result.get("result", {})
                    result["block_cid"] = block_cid
                else:
                    result["error"] = block_result.get("error", "Failed to get block")
                    result["error_type"] = block_result.get("error_type", "GetBlockError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_block")

    def get_message(self, message_cid: str) -> Dict[str, Any]:
        """Get message information by CID.

        Args:
            message_cid: The CID of the message to retrieve

        Returns:
            Result dictionary with message information
        """
        start_time = time.time()
        result = self._create_result_template("get_message")

        try:
            # Validate inputs
            if not message_cid:
                result["error"] = "Message CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get message
            if self.kit:
                # Prepare CID parameter in the format expected by the API
                cid_param = {"/": message_cid} if not message_cid.startswith("{") else message_cid

                message_result = self.kit._call_api("Filecoin.ChainGetMessage", [cid_param])

                if message_result.get("success", False):
                    result["success"] = True
                    result["message"] = message_result.get("result", {})
                    result["message_cid"] = message_cid
                else:
                    result["error"] = message_result.get("error", "Failed to get message")
                    result["error_type"] = message_result.get("error_type", "GetMessageError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_message")

    def get_tipset_by_height(self, height: int, tipset_key: List = None) -> Dict[str, Any]:
        """Get a tipset at the specified height.

        Args:
            height: Chain epoch to look for
            tipset_key: Optional parent tipset to start looking from

        Returns:
            Result dictionary with tipset information
        """
        start_time = time.time()
        result = self._create_result_template("get_tipset_by_height")

        try:
            # Validate inputs
            if not isinstance(height, int) or height < 0:
                result["error"] = "Height must be a non-negative integer"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get tipset
            if self.kit:
                tipset_result = self.kit.chain_get_tipset_by_height(height, tipset_key)

                if tipset_result.get("success", False):
                    result["success"] = True
                    result["tipset"] = tipset_result.get("result", {})
                    result["height"] = height
                else:
                    result["error"] = tipset_result.get("error", "Failed to get tipset")
                    result["error_type"] = tipset_result.get("error_type", "GetTipsetError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_tipset_by_height")

    def search_message(self, message_cid: str, limit: int = None) -> Dict[str, Any]:
        """Search for a message in the chain by its CID.

        Args:
            message_cid: The CID of the message to search for
            limit: Optional maximum number of epochs to look back

        Returns:
            Result dictionary with message lookup information
        """
        start_time = time.time()
        result = self._create_result_template("search_message")

        try:
            # Validate inputs
            if not message_cid:
                result["error"] = "Message CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to search for message
            if self.kit:
                # Prepare CID parameter in the format expected by the API
                cid_param = {"/": message_cid} if not message_cid.startswith("{") else message_cid

                # Call appropriate API method based on whether limit is provided
                if limit is not None:
                    if not isinstance(limit, int) or limit <= 0:
                        result["error"] = "Limit must be a positive integer"
                        result["error_type"] = "ValidationError"
                        return result

                    search_result = self.kit._call_api(
                        "Filecoin.StateSearchMsgLimited", [cid_param, limit]
                    )
                else:
                    search_result = self.kit._call_api("Filecoin.StateSearchMsg", [cid_param])

                if search_result.get("success", False):
                    result["success"] = True
                    result["message_lookup"] = search_result.get("result", {})
                    result["message_cid"] = message_cid
                else:
                    result["error"] = search_result.get("error", "Failed to search for message")
                    result["error_type"] = search_result.get("error_type", "SearchMessageError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "search_message")

    # State methods
    # Wallet API methods
    def wallet_new(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Create a new wallet address.

        Args:
            wallet_type: Type of wallet to create ("bls" or "secp256k1")

        Returns:
            Result dictionary with new wallet address
        """
        start_time = time.time()
        result = self._create_result_template("wallet_new")

        try:
            # Validate wallet type
            valid_types = ["bls", "secp256k1"]
            if wallet_type not in valid_types:
                result["error"] = f"Invalid wallet type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to create wallet
            if self.kit:
                wallet_result = self.kit.wallet_new(wallet_type=wallet_type)

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
            return self._handle_exception(e, result, "wallet_new")

    def wallet_has(self, address: str) -> Dict[str, Any]:
        """Check if wallet address exists.

        Args:
            address: Wallet address to check

        Returns:
            Result dictionary with existence check
        """
        start_time = time.time()
        result = self._create_result_template("wallet_has")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to check wallet
            if self.kit:
                wallet_result = self.kit.wallet_has(address=address)

                if wallet_result.get("success", False):
                    result["success"] = True
                    result["address"] = address
                    result["exists"] = wallet_result.get("result", False)
                else:
                    result["error"] = wallet_result.get("error", f"Failed to check if wallet {address} exists")
                    result["error_type"] = wallet_result.get("error_type", "WalletCheckError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "wallet_has")

    def wallet_default_address(self) -> Dict[str, Any]:
        """Get the default wallet address.

        Returns:
            Result dictionary with default wallet address
        """
        start_time = time.time()
        result = self._create_result_template("wallet_default_address")

        try:
            # Use lotus_kit to get default wallet
            if self.kit:
                default_result = self.kit.wallet_default_address()

                if default_result.get("success", False):
                    result["success"] = True
                    result["address"] = default_result.get("result")
                else:
                    result["error"] = default_result.get("error", "Failed to get default wallet address")
                    result["error_type"] = default_result.get("error_type", "WalletDefaultAddressError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "wallet_default_address")

    def wallet_set_default(self, address: str) -> Dict[str, Any]:
        """Set the default wallet address.

        Args:
            address: Address to set as default

        Returns:
            Result dictionary with operation status
        """
        start_time = time.time()
        result = self._create_result_template("wallet_set_default")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to set default wallet
            if self.kit:
                set_result = self.kit.wallet_set_default(address=address)

                if set_result.get("success", False):
                    result["success"] = True
                    result["address"] = address
                else:
                    result["error"] = set_result.get("error", f"Failed to set {address} as default wallet")
                    result["error_type"] = set_result.get("error_type", "WalletSetDefaultError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "update", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "wallet_set_default")

    def wallet_sign(self, address: str, data: str) -> Dict[str, Any]:
        """Sign data with a wallet.

        Args:
            address: Address to sign with
            data: Base64-encoded data to sign

        Returns:
            Result dictionary with signature
        """
        start_time = time.time()
        result = self._create_result_template("wallet_sign")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Address is required"
                result["error_type"] = "ValidationError"
                return result

            if not data:
                result["error"] = "Data to sign is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to sign with wallet
            if self.kit:
                sign_result = self.kit.wallet_sign(address=address, data=data)

                if sign_result.get("success", False):
                    result["success"] = True
                    result["address"] = address
                    result["signature"] = sign_result.get("result")
                else:
                    result["error"] = sign_result.get("error", "Failed to sign data with wallet")
                    result["error_type"] = sign_result.get("error_type", "WalletSignError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "compute", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "wallet_sign")

    def wallet_verify(self, address: str, data: str, signature: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a signature.

        Args:
            address: Address that signed the data
            data: Base64-encoded data that was signed
            signature: Signature to verify

        Returns:
            Result dictionary with verification result
        """
        start_time = time.time()
        result = self._create_result_template("wallet_verify")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Address is required"
                result["error_type"] = "ValidationError"
                return result

            if not data:
                result["error"] = "Data is required"
                result["error_type"] = "ValidationError"
                return result

            if not signature:
                result["error"] = "Signature is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to verify with wallet
            if self.kit:
                verify_result = self.kit.wallet_verify(
                    address=address, data=data, signature=signature
                )

                if verify_result.get("success", False):
                    result["success"] = True
                    result["address"] = address
                    result["valid"] = verify_result.get("result", False)
                else:
                    result["error"] = verify_result.get("error", "Failed to verify signature")
                    result["error_type"] = verify_result.get("error_type", "WalletVerifyError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "validate", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "wallet_verify")

    # State API methods
    def get_actor(
        self, address: str, tipset_key: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Get actor information.

        Args:
            address: The address of the actor.
            tipset_key: Optional tipset key to query state at (default: head).

        Returns:
            Result dictionary with actor details.
        """
        start_time = time.time()
        result = self._create_result_template("get_actor")

        try:
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            actor_result = self.kit.state_get_actor(address, tipset_key)
            result.update(actor_result)
            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_actor")

    def state_list_miners(
        self, tipset_key: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """List all miners in the network.

        Args:
            tipset_key: Optional tipset key to query state at (default: head)

        Returns:
            Result dictionary with list of miners
        """
        start_time = time.time()
        result = self._create_result_template("state_list_miners")

        try:
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            miners_result = self.kit.state_list_miners(tipset_key=tipset_key)
            result.update(miners_result)
            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "state_list_miners")

    def state_miner_power(
        self, miner_address: str, tipset_key: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Get miner power information.

        Args:
            miner_address: Miner address to query
            tipset_key: Optional tipset key to query state at (default: head)

        Returns:
            Result dictionary with miner power information
        """
        start_time = time.time()
        result = self._create_result_template("state_miner_power")

        try:
            # Validate inputs
            if not miner_address:
                result["error"] = "Miner address is required"
                result["error_type"] = "ValidationError"
                return result

            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            power_result = self.kit.state_miner_power(
                miner_address=miner_address, tipset_key=tipset_key
            )
            result.update(power_result)
            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "state_miner_power")

    def get_messages_in_tipset(self, tipset_key: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get all messages included in the given tipset.

        Args:
            tipset_key: List of block CIDs forming the tipset key.

        Returns:
            Result dictionary with the list of messages.
        """
        start_time = time.time()
        result = self._create_result_template("get_messages_in_tipset")

        try:
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            messages_result = self.kit.get_messages_in_tipset(tipset_key)
            result.update(messages_result)
            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_messages_in_tipset")

    def wait_message(self, message_cid: str, confidence: int = 1) -> Dict[str, Any]:
        """Wait for a message to appear on-chain.

        Args:
            message_cid: The CID of the message to wait for.
            confidence: Number of epochs of confidence needed.

        Returns:
            Result dictionary with message lookup details (receipt, tipset, height).
        """
        start_time = time.time()
        result = self._create_result_template("wait_message")

        try:
            if not self.kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result

            wait_result = self.kit.wait_message(message_cid, confidence)
            result.update(wait_result)
            # This is a potentially long-running operation, categorize as 'process'
            return self._handle_operation_result(result, "process", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "wait_message")

    # Multisig methods
    def create_multisig(
        self,
        required_signers: int,
        signer_addresses: List[str],
        unlock_duration: int,
        initial_balance: str,
        sender_address: str,
    ) -> Dict[str, Any]:
        """Create a multisig wallet.

        Args:
            required_signers: Number of required signers
            signer_addresses: List of signer addresses
            unlock_duration: Duration for unlocking funds in epochs
            initial_balance: Initial balance for the wallet
            sender_address: Address of the sender creating the wallet

        Returns:
            Result dictionary with multisig wallet details
        """
        start_time = time.time()
        result = self._create_result_template("create_multisig")

        try:
            # Validate inputs
            if not isinstance(required_signers, int) or required_signers <= 0:
                result["error"] = "Required signers must be a positive integer"
                result["error_type"] = "ValidationError"
                return result

            if not signer_addresses or not isinstance(signer_addresses, list):
                result["error"] = "Signer addresses must be a non-empty list"
                result["error_type"] = "ValidationError"
                return result

            if not isinstance(unlock_duration, int) or unlock_duration < 0:
                result["error"] = "Unlock duration must be a non-negative integer"
                result["error_type"] = "ValidationError"
                return result

            if not initial_balance:
                result["error"] = "Initial balance is required"
                result["error_type"] = "ValidationError"
                return result

            if not sender_address:
                result["error"] = "Sender address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to create multisig
            if self.kit:
                multisig_result = self.kit.multisig_create(
                    required_signers,
                    signer_addresses,
                    unlock_duration,
                    initial_balance,
                    sender_address
                )

                if multisig_result.get("success", False):
                    result["success"] = True
                    result["multisig_address"] = multisig_result.get("result", {})

                    # Add creation details
                    result["required_signers"] = required_signers
                    result["signer_addresses"] = signer_addresses
                    result["unlock_duration"] = unlock_duration
                    result["initial_balance"] = initial_balance
                    result["creator"] = sender_address
                else:
                    result["error"] = multisig_result.get("error", "Failed to create multisig wallet")
                    result["error_type"] = multisig_result.get("error_type", "MultisigCreationError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "create_multisig")

    def get_multisig_balance(self, multisig_address: str) -> Dict[str, Any]:
        """Get the available balance of a multisig wallet.

        Args:
            multisig_address: The address of the multisig wallet

        Returns:
            Result dictionary with balance information
        """
        start_time = time.time()
        result = self._create_result_template("get_multisig_balance")

        try:
            # Validate inputs
            if not multisig_address:
                result["error"] = "Multisig address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get multisig balance
            if self.kit:
                balance_result = self.kit._call_api(
                    "Filecoin.MsigGetAvailableBalance", [multisig_address, []]
                )

                if balance_result.get("success", False):
                    result["success"] = True
                    result["multisig_address"] = multisig_address
                    result["available_balance"] = balance_result.get("result")
                else:
                    result["error"] = balance_result.get("error", "Failed to get multisig balance")
                    result["error_type"] = balance_result.get("error_type", "MultisigBalanceError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_multisig_balance")

    def list_pending_multisig_transactions(self, multisig_address: str) -> Dict[str, Any]:
        """List pending transactions for a multisig wallet.

        Args:
            multisig_address: The address of the multisig wallet

        Returns:
            Result dictionary with pending transactions
        """
        start_time = time.time()
        result = self._create_result_template("list_pending_multisig_transactions")

        try:
            # Validate inputs
            if not multisig_address:
                result["error"] = "Multisig address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get pending transactions
            if self.kit:
                pending_result = self.kit._call_api(
                    "Filecoin.MsigGetPending", [multisig_address, []]
                )

                if pending_result.get("success", False):
                    result["success"] = True
                    result["multisig_address"] = multisig_address
                    result["pending_transactions"] = pending_result.get("result", [])
                    result["count"] = len(result["pending_transactions"])
                else:
                    result["error"] = pending_result.get("error", "Failed to get pending multisig transactions")
                    result["error_type"] = pending_result.get("error_type", "MultisigPendingError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_pending_multisig_transactions")

    def propose_multisig_transaction(
        self,
        multisig_address: str,
        recipient_address: str,
        value: str,
        proposer_address: str,
        method: int = 0,
        params: bytes = None,
    ) -> Dict[str, Any]:
        """Propose a multisig transaction.

        Args:
            multisig_address: The address of the multisig wallet
            recipient_address: The address to receive the funds
            value: The amount to transfer
            proposer_address: The address of the proposer
            method: Method to call in the proposed message
            params: Parameters to include in the proposed message

        Returns:
            Result dictionary with proposal information
        """
        start_time = time.time()
        result = self._create_result_template("propose_multisig_transaction")

        try:
            # Validate inputs
            if not multisig_address:
                result["error"] = "Multisig address is required"
                result["error_type"] = "ValidationError"
                return result

            if not recipient_address:
                result["error"] = "Recipient address is required"
                result["error_type"] = "ValidationError"
                return result

            if not value:
                result["error"] = "Value is required"
                result["error_type"] = "ValidationError"
                return result

            if not proposer_address:
                result["error"] = "Proposer address is required"
                result["error_type"] = "ValidationError"
                return result

            # Convert params to base64 if provided
            params_encoded = params if params else b""

            # Use lotus_kit to propose multisig transaction
            if self.kit:
                propose_result = self.kit._call_api(
                    "Filecoin.MsigPropose",
                    [
                        multisig_address,
                        recipient_address,
                        value,
                        proposer_address,
                        method,
                        params_encoded
                    ]
                )

                if propose_result.get("success", False):
                    result["success"] = True
                    result["multisig_address"] = multisig_address
                    result["proposal_cid"] = propose_result.get("result", {}).get("/")

                    # Add transaction details
                    result["recipient"] = recipient_address
                    result["value"] = value
                    result["proposer"] = proposer_address
                    result["method"] = method
                else:
                    result["error"] = propose_result.get("error", "Failed to propose multisig transaction")
                    result["error_type"] = propose_result.get("error_type", "MultisigProposeError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "propose_multisig_transaction")

    def approve_multisig_transaction(
        self, multisig_address: str, transaction_id: int, approver_address: str
    ) -> Dict[str, Any]:
        """Approve a previously proposed multisig transaction.

        Args:
            multisig_address: The address of the multisig wallet
            transaction_id: The proposed transaction ID
            approver_address: The address of the approver

        Returns:
            Result dictionary with approval information
        """
        start_time = time.time()
        result = self._create_result_template("approve_multisig_transaction")

        try:
            # Validate inputs
            if not multisig_address:
                result["error"] = "Multisig address is required"
                result["error_type"] = "ValidationError"
                return result

            if not isinstance(transaction_id, int) or transaction_id < 0:
                result["error"] = "Transaction ID must be a non-negative integer"
                result["error_type"] = "ValidationError"
                return result

            if not approver_address:
                result["error"] = "Approver address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to approve multisig transaction
            if self.kit:
                approve_result = self.kit._call_api(
                    "Filecoin.MsigApprove",
                    [multisig_address, transaction_id, approver_address],
                )

                if approve_result.get("success", False):
                    result["success"] = True
                    result["multisig_address"] = multisig_address
                    result["transaction_id"] = transaction_id
                    result["approval_cid"] = approve_result.get("result", {}).get("/")
                    result["approver"] = approver_address
                else:
                    result["error"] = approve_result.get("error", "Failed to approve multisig transaction")
                    result["error_type"] = approve_result.get("error_type", "MultisigApproveError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "update", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "approve_multisig_transaction")

    def cancel_multisig_transaction(
        self, multisig_address: str, transaction_id: int, canceller_address: str
    ) -> Dict[str, Any]:
        """Cancel a previously proposed multisig transaction.

        Args:
            multisig_address: The address of the multisig wallet
            transaction_id: The proposed transaction ID
            canceller_address: The address of the canceller

        Returns:
            Result dictionary with cancellation information
        """
        start_time = time.time()
        result = self._create_result_template("cancel_multisig_transaction")

        try:
            # Validate inputs
            if not multisig_address:
                result["error"] = "Multisig address is required"
                result["error_type"] = "ValidationError"
                return result

            if not isinstance(transaction_id, int) or transaction_id < 0:
                result["error"] = "Transaction ID must be a non-negative integer"
                result["error_type"] = "ValidationError"
                return result

            if not canceller_address:
                result["error"] = "Canceller address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get the pending transaction details first
            if self.kit:
                # Get the pending transaction to get the parameters needed for cancellation
                pending_result = self.kit._call_api(
                    "Filecoin.MsigGetPending", [multisig_address, []]
                )

                if not pending_result.get("success", False):
                    result["error"] = pending_result.get("error", "Failed to get pending transaction details")
                    result["error_type"] = pending_result.get("error_type", "MultisigPendingError")
                    return result

                # Find the transaction with the given ID
                transaction = None
                for tx in pending_result.get("result", []):
                    if tx.get("ID") == transaction_id:
                        transaction = tx
                        break

                if not transaction:
                    result["error"] = f"Transaction ID {transaction_id} not found"
                    result["error_type"] = "TransactionNotFoundError"
                    return result

                # Extract transaction details
                to_address = transaction.get("To")
                value = transaction.get("Value")
                method = transaction.get("Method")
                params = transaction.get("Params", b"")

                # Call cancel with the transaction details
                cancel_result = self.kit._call_api(
                    "Filecoin.MsigCancel",
                    [
                        multisig_address,
                        transaction_id,
                        to_address,
                        value,
                        canceller_address,
                        method,
                        params
                    ]
                )

                if cancel_result.get("success", False):
                    result["success"] = True
                    result["multisig_address"] = multisig_address
                    result["transaction_id"] = transaction_id
                    result["cancellation_cid"] = cancel_result.get("result", {}).get("/")
                    result["canceller"] = canceller_address
                else:
                    result["error"] = cancel_result.get("error", "Failed to cancel multisig transaction")
                    result["error_type"] = cancel_result.get("error_type", "MultisigCancelError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "update", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "cancel_multisig_transaction")

    # Payment Channel methods
    def list_payment_channels(self) -> Dict[str, Any]:
        """List all locally tracked payment channels.

        Returns:
            Result dictionary with list of channel addresses
        """
        start_time = time.time()
        result = self._create_result_template("list_payment_channels")

        try:
            # Use lotus_kit to list payment channels
            if self.kit:
                channels_result = self.kit._call_api("Filecoin.PaychList")

                if channels_result.get("success", False):
                    result["success"] = True
                    result["channels"] = channels_result.get("result", [])
                    result["count"] = len(result["channels"])
                else:
                    result["error"] = channels_result.get("error", "Failed to list payment channels")
                    result["error_type"] = channels_result.get("error_type", "PaychListError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_payment_channels")

    def create_payment_channel(
        self, from_address: str, to_address: str, amount: str
    ) -> Dict[str, Any]:
        """Create a new payment channel.

        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Amount to add to the channel in FIL

        Returns:
            Result dictionary with channel information
        """
        start_time = time.time()
        result = self._create_result_template("create_payment_channel")

        try:
            # Validate inputs
            if not from_address:
                result["error"] = "From address is required"
                result["error_type"] = "ValidationError"
                return result

            if not to_address:
                result["error"] = "To address is required"
                result["error_type"] = "ValidationError"
                return result

            if not amount:
                result["error"] = "Amount is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to create payment channel
            if self.kit:
                channel_result = self.kit._call_api(
                    "Filecoin.PaychGet", [from_address, to_address, amount]
                )

                if channel_result.get("success", False):
                    result["success"] = True
                    result["channel"] = channel_result.get("result", {})

                    # Add creation details
                    result["from_address"] = from_address
                    result["to_address"] = to_address
                    result["amount"] = amount
                else:
                    result["error"] = channel_result.get("error", "Failed to create payment channel")
                    result["error_type"] = channel_result.get("error_type", "PaychGetError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "create_payment_channel")

    def get_payment_channel_status(self, channel_address: str) -> Dict[str, Any]:
        """Get the status of a payment channel.

        Args:
            channel_address: Payment channel address

        Returns:
            Result dictionary with channel status
        """
        start_time = time.time()
        result = self._create_result_template("get_payment_channel_status")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get payment channel status
            if self.kit:
                status_result = self.kit._call_api("Filecoin.PaychStatus", [channel_address])

                if status_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["status"] = status_result.get("result", {})
                else:
                    result["error"] = status_result.get("error", "Failed to get payment channel status")
                    result["error_type"] = status_result.get("error_type", "PaychStatusError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_payment_channel_status")

    def get_payment_channel_available_funds(self, channel_address: str) -> Dict[str, Any]:
        """Get available funds in a payment channel.

        Args:
            channel_address: Payment channel address

        Returns:
            Result dictionary with available funds information
        """
        start_time = time.time()
        result = self._create_result_template("get_payment_channel_available_funds")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get payment channel available funds
            if self.kit:
                funds_result = self.kit._call_api("Filecoin.PaychAvailableFunds", [channel_address])

                if funds_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["available_funds"] = funds_result.get("result", {})
                else:
                    result["error"] = funds_result.get("error", "Failed to get payment channel available funds")
                    result["error_type"] = funds_result.get("error_type", "PaychAvailableFundsError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "get_payment_channel_available_funds")

    def create_payment_channel_voucher(
        self, channel_address: str, amount: str, lane: int = 0
    ) -> Dict[str, Any]:
        """Create a payment channel voucher.

        Args:
            channel_address: Payment channel address
            amount: Voucher amount in FIL
            lane: Payment lane number

        Returns:
            Result dictionary with voucher information
        """
        start_time = time.time()
        result = self._create_result_template("create_payment_channel_voucher")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            if not amount:
                result["error"] = "Amount is required"
                result["error_type"] = "ValidationError"
                return result

            if not isinstance(lane, int) or lane < 0:
                result["error"] = "Lane must be a non-negative integer"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to create payment channel voucher
            if self.kit:
                voucher_result = self.kit._call_api(
                    "Filecoin.PaychVoucherCreate", [channel_address, amount, lane]
                )

                if voucher_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["voucher"] = voucher_result.get("result", {}).get("Voucher")
                    result["shortfall"] = voucher_result.get("result", {}).get("Shortfall")

                    # Add voucher details
                    result["amount"] = amount
                    result["lane"] = lane
                else:
                    result["error"] = voucher_result.get("error", "Failed to create payment channel voucher")
                    result["error_type"] = voucher_result.get("error_type", "PaychVoucherCreateError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "create_payment_channel_voucher")

    def list_payment_channel_vouchers(self, channel_address: str) -> Dict[str, Any]:
        """List all vouchers for a payment channel.

        Args:
            channel_address: Payment channel address

        Returns:
            Result dictionary with voucher list
        """
        start_time = time.time()
        result = self._create_result_template("list_payment_channel_vouchers")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to list payment channel vouchers
            if self.kit:
                vouchers_result = self.kit._call_api("Filecoin.PaychVoucherList", [channel_address])

                if vouchers_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["vouchers"] = vouchers_result.get("result", [])
                    result["count"] = len(result["vouchers"])
                else:
                    result["error"] = vouchers_result.get("error", "Failed to list payment channel vouchers")
                    result["error_type"] = vouchers_result.get("error_type", "PaychVoucherListError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_payment_channel_vouchers")

    def check_payment_channel_voucher(
        self, channel_address: str, voucher: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check validity of payment channel voucher.

        Args:
            channel_address: Payment channel address
            voucher: Voucher to check

        Returns:
            Result dictionary with validation result
        """
        start_time = time.time()
        result = self._create_result_template("check_payment_channel_voucher")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            if not voucher:
                result["error"] = "Voucher is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to check payment channel voucher
            if self.kit:
                check_result = self.kit._call_api(
                    "Filecoin.PaychVoucherCheckValid", [channel_address, voucher]
                )

                if check_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["valid"] = True  # If no error returned, the voucher is valid
                else:
                    # Check if this is just an invalid voucher or a different error
                    if "invalid voucher" in check_result.get("error", "").lower():
                        result["success"] = True
                        result["valid"] = False
                        result["validation_error"] = check_result.get("error")
                    else:
                        result["error"] = check_result.get("error", "Failed to check payment channel voucher")
                        result["error_type"] = check_result.get("error_type", "PaychVoucherCheckError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "validate", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "check_payment_channel_voucher")

    def submit_payment_channel_voucher(
        self, channel_address: str, voucher: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit voucher to chain to update payment channel state.

        Args:
            channel_address: Payment channel address
            voucher: Voucher to submit

        Returns:
            Result dictionary with submission result
        """
        start_time = time.time()
        result = self._create_result_template("submit_payment_channel_voucher")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            if not voucher:
                result["error"] = "Voucher is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to submit payment channel voucher
            if self.kit:
                # These parameters are optional in the Lotus API: secret, proof
                submit_result = self.kit._call_api(
                    "Filecoin.PaychVoucherSubmit",
                    [channel_address, voucher, None, None],
                )

                if submit_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["message_cid"] = submit_result.get("result", {}).get("/")
                else:
                    result["error"] = submit_result.get("error", "Failed to submit payment channel voucher")
                    result["error_type"] = submit_result.get("error_type", "PaychVoucherSubmitError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "update", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "submit_payment_channel_voucher")

    def settle_payment_channel(self, channel_address: str) -> Dict[str, Any]:
        """Settle a payment channel.

        This starts the settlement period for the channel, after which funds can be collected.

        Args:
            channel_address: Payment channel address

        Returns:
            Result dictionary with settlement operation result
        """
        start_time = time.time()
        result = self._create_result_template("settle_payment_channel")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to settle payment channel
            if self.kit:
                settle_result = self.kit._call_api("Filecoin.PaychSettle", [channel_address])

                if settle_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["message_cid"] = settle_result.get("result", {}).get("/")
                else:
                    result["error"] = settle_result.get("error", "Failed to settle payment channel")
                    result["error_type"] = settle_result.get("error_type", "PaychSettleError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "update", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "settle_payment_channel")

    def collect_payment_channel(self, channel_address: str) -> Dict[str, Any]:
        """Collect funds from a payment channel.

        Channel must be settled and the settlement period expired to collect.

        Args:
            channel_address: Payment channel address

        Returns:
            Result dictionary with collection operation result
        """
        start_time = time.time()
        result = self._create_result_template("collect_payment_channel")

        try:
            # Validate inputs
            if not channel_address:
                result["error"] = "Channel address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to collect payment channel
            if self.kit:
                collect_result = self.kit._call_api("Filecoin.PaychCollect", [channel_address])

                if collect_result.get("success", False):
                    result["success"] = True
                    result["channel_address"] = channel_address
                    result["message_cid"] = collect_result.get("result", {}).get("/")
                else:
                    result["error"] = collect_result.get("error", "Failed to collect payment channel")
                    result["error_type"] = collect_result.get("error_type", "PaychCollectError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "update", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "collect_payment_channel")

    # Message Pool (mpool) methods
    def mpool_get_nonce(self, address: str) -> Dict[str, Any]:
        """Get next nonce for an account.

        Args:
            address: Account address to check

        Returns:
            Result dictionary with nonce information
        """
        start_time = time.time()
        result = self._create_result_template("mpool_get_nonce")

        try:
            # Validate inputs
            if not address:
                result["error"] = "Address is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to get nonce
            if self.kit:
                nonce_result = self.kit.mpool_get_nonce(address=address)

                if nonce_result.get("success", False):
                    result["success"] = True
                    result["address"] = address
                    result["nonce"] = nonce_result.get("result")
                else:
                    result["error"] = nonce_result.get("error", "Failed to get nonce")
                    result["error_type"] = nonce_result.get("error_type", "MpoolGetNonceError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "read", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "mpool_get_nonce")

    def mpool_pending(self, tipset_key: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Get pending messages in the message pool.

        Args:
            tipset_key: Optional tipset key to query state at (default: head)

        Returns:
            Result dictionary with pending messages
        """
        start_time = time.time()
        result = self._create_result_template("mpool_pending")

        try:
            # Use lotus_kit to get pending messages
            if self.kit:
                pending_result = self.kit.mpool_pending(tipset_key=tipset_key)

                if pending_result.get("success", False):
                    result["success"] = True
                    result["messages"] = pending_result.get("result", [])
                    result["count"] = len(result["messages"])
                else:
                    result["error"] = pending_result.get("error", "Failed to get pending messages")
                    result["error_type"] = pending_result.get("error_type", "MpoolPendingError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "mpool_pending")

    def mpool_push(self, signed_message: Dict[str, Any]) -> Dict[str, Any]:
        """Push a signed message to the message pool.

        Args:
            signed_message: Signed message to push

        Returns:
            Result dictionary with message push result
        """
        start_time = time.time()
        result = self._create_result_template("mpool_push")

        try:
            # Validate inputs
            if not signed_message:
                result["error"] = "Signed message is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lotus_kit to push message
            if self.kit:
                push_result = self.kit.mpool_push(signed_message=signed_message)

                if push_result.get("success", False):
                    result["success"] = True
                    result["message_cid"] = push_result.get("result", {}).get("/")
                else:
                    result["error"] = push_result.get("error", "Failed to push message")
                    result["error_type"] = push_result.get("error_type", "MpoolPushError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "mpool_push")

    # Gas estimation methods
    def gas_estimate_message_gas(
        self, message: Dict[str, Any], tipset_key: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Estimate gas parameters for a message.

        Args:
            message: Message to estimate gas for
            tipset_key: Optional tipset key to query state at (default: head)

        Returns:
            Result dictionary with gas estimation information
        """
        start_time = time.time()
        result = self._create_result_template("gas_estimate_message_gas")

        try:
            # Validate inputs
            if not message:
                result["error"] = "Message is required"
                result["error_type"] = "ValidationError"
                return result

            # Ensure message has required fields
            required_fields = ["From", "To"]
            for field in required_fields:
                if field not in message:
                    result["error"] = f"Message must have '{field}' field"
                    result["error_type"] = "ValidationError"
                    return result

            # Use lotus_kit to estimate gas
            if self.kit:
                gas_result = self.kit.gas_estimate_message_gas(
                    message=message, tipset_key=tipset_key
                )

                if gas_result.get("success", False):
                    result["success"] = True
                    result["estimate"] = gas_result.get("result", {})

                    # Add message info for reference
                    result["message"] = {
                        "from": message.get("From"),
                        "to": message.get("To"),
                        "value": message.get("Value"),
                        "method": message.get("Method"),
                    }
                else:
                    result["error"] = gas_result.get("error", "Failed to estimate gas")
                    result["error_type"] = gas_result.get("error_type", "GasEstimateError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "compute", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "gas_estimate_message_gas")    
        