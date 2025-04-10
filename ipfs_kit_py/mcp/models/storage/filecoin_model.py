"""
Filecoin (Lotus) Model for MCP Server.

This module provides the business logic for Filecoin operations in the MCP server.
It relies on the lotus_kit module for underlying functionality.
"""

import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any, Union

from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.mcp.models.storage import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class FilecoinModel(BaseStorageModel):
    """Model for Filecoin (Lotus) operations."""
    
    def __init__(self, lotus_kit_instance=None, ipfs_model=None, cache_manager=None, credential_manager=None):
        """Initialize Filecoin model with dependencies.
        
        Args:
            lotus_kit_instance: lotus_kit instance for Filecoin operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(lotus_kit_instance, cache_manager, credential_manager)
        
        # Store the lotus_kit instance
        self.lotus_kit = lotus_kit_instance
        
        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model
        
        logger.info("Filecoin Model initialized")
    
    def check_connection(self) -> Dict[str, Any]:
        """Check connection to the Lotus API.
        
        Returns:
            Result dictionary with connection status
        """
        start_time = time.time()
        result = self._create_result_dict("check_connection")
        
        try:
            # Use lotus_kit to check connection
            if self.lotus_kit:
                connection_result = self.lotus_kit.check_connection()
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_wallets(self) -> Dict[str, Any]:
        """List all wallet addresses.
        
        Returns:
            Result dictionary with wallet addresses
        """
        start_time = time.time()
        result = self._create_result_dict("list_wallets")
        
        try:
            # Use lotus_kit to list wallets
            if self.lotus_kit:
                wallet_result = self.lotus_kit.list_wallets()
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def get_wallet_balance(self, address: str) -> Dict[str, Any]:
        """Get wallet balance.
        
        Args:
            address: The wallet address to check balance for
            
        Returns:
            Result dictionary with wallet balance
        """
        start_time = time.time()
        result = self._create_result_dict("get_wallet_balance")
        
        try:
            # Validate inputs
            if not address:
                result["error"] = "Wallet address is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Use lotus_kit to get wallet balance
            if self.lotus_kit:
                balance_result = self.lotus_kit.wallet_balance(address)
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def create_wallet(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Create a new wallet.
        
        Args:
            wallet_type: The type of wallet to create (bls or secp256k1)
            
        Returns:
            Result dictionary with new wallet address
        """
        start_time = time.time()
        result = self._create_result_dict("create_wallet")
        
        try:
            # Validate wallet_type
            valid_types = ["bls", "secp256k1"]
            if wallet_type not in valid_types:
                result["error"] = f"Invalid wallet type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result
            
            # Use lotus_kit to create wallet
            if self.lotus_kit:
                wallet_result = self.lotus_kit.create_wallet(wallet_type)
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def import_file(self, file_path: str) -> Dict[str, Any]:
        """Import a file into the Lotus client.
        
        Args:
            file_path: Path to the file to import
            
        Returns:
            Result dictionary with import information
        """
        start_time = time.time()
        result = self._create_result_dict("import_file")
        
        try:
            # Validate inputs
            if not os.path.exists(file_path):
                result["error"] = f"File not found: {file_path}"
                result["error_type"] = "FileNotFoundError"
                return result
            
            # Get file size for statistics
            file_size = os.path.getsize(file_path)
            
            # Use lotus_kit to import the file
            if self.lotus_kit:
                import_result = self.lotus_kit.client_import(file_path)
                
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
            
            # Update statistics
            self._update_stats(result, file_size if result["success"] else None)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_imports(self) -> Dict[str, Any]:
        """List all imported files.
        
        Returns:
            Result dictionary with list of imports
        """
        start_time = time.time()
        result = self._create_result_dict("list_imports")
        
        try:
            # Use lotus_kit to list imports
            if self.lotus_kit:
                imports_result = self.lotus_kit.client_list_imports()
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def find_data(self, data_cid: str) -> Dict[str, Any]:
        """Find where data is stored.
        
        Args:
            data_cid: The CID of the data to find
            
        Returns:
            Result dictionary with data location information
        """
        start_time = time.time()
        result = self._create_result_dict("find_data")
        
        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Use lotus_kit to find data
            if self.lotus_kit:
                find_result = self.lotus_kit.client_find_data(data_cid)
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_deals(self) -> Dict[str, Any]:
        """List all deals made by the client.
        
        Returns:
            Result dictionary with list of deals
        """
        start_time = time.time()
        result = self._create_result_dict("list_deals")
        
        try:
            # Use lotus_kit to list deals
            if self.lotus_kit:
                deals_result = self.lotus_kit.client_list_deals()
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def get_deal_info(self, deal_id: int) -> Dict[str, Any]:
        """Get information about a specific deal.
        
        Args:
            deal_id: ID of the deal to get information about
            
        Returns:
            Result dictionary with deal information
        """
        start_time = time.time()
        result = self._create_result_dict("get_deal_info")
        
        try:
            # Validate inputs
            if not isinstance(deal_id, int):
                result["error"] = "Deal ID must be an integer"
                result["error_type"] = "ValidationError"
                return result
            
            # Use lotus_kit to get deal info
            if self.lotus_kit:
                deal_result = self.lotus_kit.client_deal_info(deal_id)
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def start_deal(self, data_cid: str, miner: str, price: str, duration: int, wallet: Optional[str] = None,
                 verified: bool = False, fast_retrieval: bool = True) -> Dict[str, Any]:
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
        result = self._create_result_dict("start_deal")
        
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
            if not wallet and self.lotus_kit:
                wallet_result = self.lotus_kit.list_wallets()
                if wallet_result.get("success", False) and wallet_result.get("result"):
                    wallet = wallet_result["result"][0]
            
            # Use lotus_kit to start deal
            if self.lotus_kit:
                deal_result = self.lotus_kit.client_start_deal(
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def retrieve_data(self, data_cid: str, out_file: str) -> Dict[str, Any]:
        """Retrieve data from the Filecoin network.
        
        Args:
            data_cid: The CID of the data to retrieve
            out_file: Path where the retrieved data should be saved
            
        Returns:
            Result dictionary with retrieval information
        """
        start_time = time.time()
        result = self._create_result_dict("retrieve_data")
        
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
            if self.lotus_kit:
                retrieve_result = self.lotus_kit.client_retrieve(data_cid, out_file)
                
                if retrieve_result.get("success", False):
                    # Get file size for statistics
                    file_size = os.path.getsize(out_file) if os.path.exists(out_file) else 0
                    
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
            
            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_miners(self) -> Dict[str, Any]:
        """List all miners in the network.
        
        Returns:
            Result dictionary with list of miners
        """
        start_time = time.time()
        result = self._create_result_dict("list_miners")
        
        try:
            # Use lotus_kit to list miners
            if self.lotus_kit:
                miners_result = self.lotus_kit.list_miners()
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def get_miner_info(self, miner_address: str) -> Dict[str, Any]:
        """Get information about a specific miner.
        
        Args:
            miner_address: The address of the miner
            
        Returns:
            Result dictionary with miner information
        """
        start_time = time.time()
        result = self._create_result_dict("get_miner_info")
        
        try:
            # Validate inputs
            if not miner_address:
                result["error"] = "Miner address is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Use lotus_kit to get miner info
            if self.lotus_kit:
                miner_result = self.lotus_kit.miner_get_info(miner_address)
                
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
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def ipfs_to_filecoin(self, cid: str, miner: str, price: str, duration: int, wallet: Optional[str] = None,
                        verified: bool = False, fast_retrieval: bool = True, pin: bool = True) -> Dict[str, Any]:
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
        result = self._create_result_dict("ipfs_to_filecoin")
        
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
            if not self.lotus_kit:
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
            
            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def filecoin_to_ipfs(self, data_cid: str, pin: bool = True) -> Dict[str, Any]:
        """Retrieve content from Filecoin and add to IPFS.
        
        Args:
            data_cid: The CID of the data to retrieve from Filecoin
            pin: Whether to pin the content in IPFS
            
        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("filecoin_to_ipfs")
        
        try:
            # Validate inputs
            if not data_cid:
                result["error"] = "Data CID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Only continue if all dependencies are available
            if not self.lotus_kit:
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
                file_size = os.path.getsize(temp_path)
                
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
                        logger.warning(f"Failed to pin content {ipfs_cid}: {pin_result.get('error')}")
                
                # Set success and copy relevant fields
                result["success"] = True
                result["filecoin_cid"] = data_cid
                result["ipfs_cid"] = ipfs_cid
                result["size_bytes"] = file_size
            
            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result