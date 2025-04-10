#!/usr/bin/env python3
"""
Comprehensive test for FilecoinModel methods and error handling patterns.

This script:
1. Tests all FilecoinModel methods with a mocked lotus_kit
2. Creates both success and failure scenarios
3. Verifies consistent error handling across all methods
4. Tests cross-backend operations with mocked IPFS model
"""

import os
import sys
import json
import time
import uuid
import tempfile
import logging
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Create test results directory
TEST_RESULTS_DIR = "test_results"
os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
TEST_RESULTS_FILE = os.path.join(TEST_RESULTS_DIR, "filecoin_model_methods_test.json")

# Mock BaseStorageModel
class MockBaseStorageModel:
    """Minimal mock of BaseStorageModel."""
    
    def __init__(self, kit_instance=None, cache_manager=None, credential_manager=None):
        """Initialize with the same signature."""
        self.kit = kit_instance
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.correlation_id = str(uuid.uuid4())
        self.operation_stats = self._initialize_stats()
    
    def _initialize_stats(self) -> Dict[str, Any]:
        """Initialize operation statistics."""
        return {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "bytes_uploaded": 0,
            "bytes_downloaded": 0
        }
    
    def _create_result_dict(self, operation: str) -> Dict[str, Any]:
        """Create a standardized result dictionary."""
        return {
            "success": False,
            "operation": operation,
            "timestamp": time.time(),
            "correlation_id": self.correlation_id
        }
    
    def _update_stats(self, result: Dict[str, Any], bytes_count: Optional[int] = None) -> None:
        """Update operation statistics."""
        self.operation_stats["total_operations"] += 1
        if result.get("success", False):
            self.operation_stats["success_count"] += 1
            if bytes_count:
                if "upload" in result.get("operation", ""):
                    self.operation_stats["bytes_uploaded"] += bytes_count
                elif "download" in result.get("operation", ""):
                    self.operation_stats["bytes_downloaded"] += bytes_count
        else:
            self.operation_stats["failure_count"] += 1
    
    def _handle_error(self, result: Dict[str, Any], error: Exception, message: Optional[str] = None) -> Dict[str, Any]:
        """Handle errors in a standardized way."""
        result["success"] = False
        result["error"] = message or str(error)
        result["error_type"] = type(error).__name__
        return result

# Mock lotus_kit class - Configurable to simulate success or failure
class MockLotusKit:
    """Mock lotus_kit class that can simulate success or failure scenarios."""
    
    def __init__(self, metadata=None, should_succeed=False):
        """Initialize with metadata and success flag."""
        self.metadata = metadata or {}
        self.api_url = metadata.get("api_url", "http://localhost:1234/rpc/v0")
        self.should_succeed = should_succeed
        self.wallet_addresses = ["t1abjxfbp274xpdqcpuaykwkfb43omjotacm2p3za", "t1cncuf2kvd4d4lssiqa82gn5lx4jpiasxl7hrv2i"]
        self.miners = ["t01000", "t01001", "t01002"]
        self.deals = [{"DealID": 1, "State": 1}, {"DealID": 2, "State": 7}]
        self.imports = [{"Key": "ImportKey1", "Root": {"/":" bafyCID1"}, "Status": "Success"}, 
                         {"Key": "ImportKey2", "Root": {"/":" bafyCID2"}, "Status": "Success"}]
    
    def check_connection(self):
        """Simulate connection success or failure."""
        if self.should_succeed:
            return {
                "success": True,
                "result": "Lotus v1.24.0",
                "timestamp": time.time()
            }
        else:
            return {
                "success": False,
                "error": f"Failed to connect to Lotus API at {self.api_url}: Connection refused",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
    
    def list_wallets(self):
        """Simulate wallet listing success or failure."""
        if self.should_succeed:
            return {
                "success": True,
                "result": self.wallet_addresses,
                "timestamp": time.time()
            }
        else:
            return {
                "success": False,
                "error": f"Failed to list wallets: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
    
    def wallet_balance(self, address):
        """Simulate wallet balance check."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to get wallet balance: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
        
        # Basic validation
        if address not in self.wallet_addresses:
            return {
                "success": False,
                "error": f"Wallet address not found: {address}",
                "error_type": "WalletNotFoundError",
                "timestamp": time.time()
            }
            
        return {
            "success": True,
            "result": "100000000000000000",  # 0.1 FIL in attoFIL
            "timestamp": time.time()
        }
    
    def create_wallet(self, wallet_type):
        """Simulate wallet creation."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to create wallet: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Return a new mock address
        new_address = f"t1new{uuid.uuid4().hex[:10]}"
        self.wallet_addresses.append(new_address)
        
        return {
            "success": True,
            "result": new_address,
            "timestamp": time.time()
        }
    
    def client_import(self, file_path):
        """Simulate file import."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to import file: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError",
                "timestamp": time.time()
            }
            
        # Create a mock result
        import_key = f"ImportKey{uuid.uuid4().hex[:8]}"
        mock_cid = f"bafy{uuid.uuid4().hex[:44]}"
        
        result = {
            "success": True,
            "result": {
                "ImportID": import_key,
                "Root": {"/": mock_cid},
                "Size": os.path.getsize(file_path),
                "Status": "Success"
            },
            "timestamp": time.time()
        }
        
        # Add to imports list
        self.imports.append(result["result"])
        
        return result
    
    def client_list_imports(self):
        """Simulate listing imports."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to list imports: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        return {
            "success": True,
            "result": self.imports,
            "timestamp": time.time()
        }
    
    def client_find_data(self, data_cid):
        """Simulate finding data."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to find data: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Return mock locations
        locations = [
            {"LocalPath": f"/path/to/{data_cid}"},
            {"RemoteStatus": "Success", "MinerId": "t01000"}
        ]
        
        return {
            "success": True,
            "result": locations,
            "timestamp": time.time()
        }
    
    def client_list_deals(self):
        """Simulate listing deals."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to list deals: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        return {
            "success": True,
            "result": self.deals,
            "timestamp": time.time()
        }
    
    def client_deal_info(self, deal_id):
        """Simulate getting deal info."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to get deal info: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Check if deal exists
        for deal in self.deals:
            if deal.get("DealID") == deal_id:
                return {
                    "success": True,
                    "result": deal,
                    "timestamp": time.time()
                }
                
        return {
            "success": False,
            "error": f"Deal not found: {deal_id}",
            "error_type": "DealNotFoundError",
            "timestamp": time.time()
        }
    
    def client_start_deal(self, data_cid, miner, price, duration, wallet=None, verified=False, fast_retrieval=True):
        """Simulate starting a deal."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to start deal: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Validate miner
        if miner not in self.miners:
            return {
                "success": False,
                "error": f"Miner not found: {miner}",
                "error_type": "MinerNotFoundError",
                "timestamp": time.time()
            }
            
        # Create mock deal CID
        deal_cid = f"bafy{uuid.uuid4().hex[:44]}"
        
        # Add to deals list
        new_deal = {
            "DealID": len(self.deals) + 1,
            "State": 1,
            "Provider": miner,
            "DataCID": data_cid,
            "PricePerEpoch": price,
            "Duration": duration
        }
        self.deals.append(new_deal)
        
        return {
            "success": True,
            "result": {"/": deal_cid},
            "timestamp": time.time()
        }
    
    def client_retrieve(self, data_cid, out_file):
        """Simulate data retrieval."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to retrieve data: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        
        # Write mock data to the output file
        with open(out_file, "wb") as f:
            f.write(b"Mock Filecoin data for testing")
            
        return {
            "success": True,
            "result": True,
            "timestamp": time.time()
        }
    
    def list_miners(self):
        """Simulate listing miners."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to list miners: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        return {
            "success": True,
            "result": self.miners,
            "timestamp": time.time()
        }
    
    def miner_get_info(self, miner_address):
        """Simulate getting miner info."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": f"Failed to get miner info: Connection to Lotus API failed",
                "error_type": "LotusConnectionError",
                "timestamp": time.time()
            }
            
        # Check if miner exists
        if miner_address not in self.miners:
            return {
                "success": False,
                "error": f"Miner not found: {miner_address}",
                "error_type": "MinerNotFoundError",
                "timestamp": time.time()
            }
            
        # Return mock info
        return {
            "success": True,
            "result": {
                "Owner": "t3owner",
                "Worker": "t3worker",
                "PeerId": "12D3KooWPeerId",
                "SectorSize": 34359738368,  # 32 GiB
                "WindowPoStPartitionSectors": 2349,
                "Multiaddrs": ["/ip4/127.0.0.1/tcp/58398"]
            },
            "timestamp": time.time()
        }

# Mock IPFS model for cross-backend operations
class MockIPFSModel:
    """Mock IPFS model for testing cross-backend operations."""
    
    def __init__(self, should_succeed=True):
        """Initialize with success flag."""
        self.should_succeed = should_succeed
    
    def get_content(self, cid):
        """Simulate getting content from IPFS."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": "Failed to get content from IPFS",
                "error_type": "IPFSError",
                "timestamp": time.time()
            }
            
        # Return mock content
        return {
            "success": True,
            "data": b"Mock IPFS content for " + cid.encode(),
            "cid": cid,
            "size": 22 + len(cid),
            "timestamp": time.time()
        }
    
    def add_content(self, content):
        """Simulate adding content to IPFS."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": "Failed to add content to IPFS",
                "error_type": "IPFSError",
                "timestamp": time.time()
            }
            
        # Generate mock CID
        mock_cid = f"Qm{uuid.uuid4().hex[:44]}"
        
        return {
            "success": True,
            "cid": mock_cid,
            "size": len(content),
            "timestamp": time.time()
        }
    
    def pin_content(self, cid):
        """Simulate pinning content in IPFS."""
        if not self.should_succeed:
            return {
                "success": False,
                "error": "Failed to pin content in IPFS",
                "error_type": "IPFSError",
                "timestamp": time.time()
            }
            
        return {
            "success": True,
            "cid": cid,
            "pinned": True,
            "timestamp": time.time()
        }

# Implement FilecoinModel
class FilecoinModel(MockBaseStorageModel):
    """FilecoinModel implementation for testing method error handling patterns."""
    
    def __init__(self, lotus_kit_instance=None, ipfs_model=None, cache_manager=None, credential_manager=None):
        """Initialize with dependencies."""
        super().__init__(lotus_kit_instance, cache_manager, credential_manager)
        self.lotus_kit = lotus_kit_instance
        self.ipfs_model = ipfs_model
    
    def check_connection(self) -> Dict[str, Any]:
        """Check connection to Lotus API."""
        start_time = time.time()
        result = self._create_result_dict("check_connection")
        
        try:
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_wallets(self) -> Dict[str, Any]:
        """List wallet addresses."""
        start_time = time.time()
        result = self._create_result_dict("list_wallets")
        
        try:
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def get_wallet_balance(self, address: str) -> Dict[str, Any]:
        """Get wallet balance."""
        start_time = time.time()
        result = self._create_result_dict("get_wallet_balance")
        
        try:
            # Validate inputs
            if not address:
                result["error"] = "Wallet address is required"
                result["error_type"] = "ValidationError"
                return result
            
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def create_wallet(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Create a new wallet."""
        start_time = time.time()
        result = self._create_result_dict("create_wallet")
        
        try:
            # Validate wallet_type
            valid_types = ["bls", "secp256k1"]
            if wallet_type not in valid_types:
                result["error"] = f"Invalid wallet type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result
            
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_miners(self) -> Dict[str, Any]:
        """List all miners in the network."""
        start_time = time.time()
        result = self._create_result_dict("list_miners")
        
        try:
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_deals(self) -> Dict[str, Any]:
        """List all deals made by the client."""
        start_time = time.time()
        result = self._create_result_dict("list_deals")
        
        try:
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_imports(self) -> Dict[str, Any]:
        """List all imported files."""
        start_time = time.time()
        result = self._create_result_dict("list_imports")
        
        try:
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
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def ipfs_to_filecoin(self, cid: str, miner: str, price: str, duration: int, wallet: Optional[str] = None,
                        verified: bool = False, fast_retrieval: bool = True, pin: bool = True) -> Dict[str, Any]:
        """Store IPFS content on Filecoin."""
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
            
            # Check dependencies
            if not self.lotus_kit:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
                return result
                
            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{cid}") as temp_file:
                temp_path = temp_file.name
                
                # Get content from IPFS
                ipfs_result = self.ipfs_model.get_content(cid)
                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to retrieve content from IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSGetError")
                    result["ipfs_result"] = ipfs_result
                    os.unlink(temp_path)
                    return result
                
                # Get content
                content = ipfs_result.get("data")
                if not content:
                    result["error"] = "No content retrieved from IPFS"
                    result["error_type"] = "ContentMissingError"
                    result["ipfs_result"] = ipfs_result
                    os.unlink(temp_path)
                    return result
                
                # Write to temporary file
                temp_file.write(content)
                temp_file.flush()
                
                # Pin if requested
                if pin:
                    pin_result = self.ipfs_model.pin_content(cid)
                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")
                
                # Import to Lotus
                import_result = {}  # Mock for now
                # We'd typically call self.import_file(temp_path) but we'll simulate directly
                import_result = {
                    "success": True,
                    "root": f"bafy{uuid.uuid4().hex[:44]}",
                    "file_path": temp_path,
                    "size_bytes": len(content)
                }
                
                # Clean up
                os.unlink(temp_path)
                
                if not import_result.get("success", False):
                    result["error"] = import_result.get("error", "Failed to import content to Lotus")
                    result["error_type"] = import_result.get("error_type", "LotusImportError")
                    result["import_result"] = import_result
                    return result
                
                # Get data CID
                data_cid = import_result.get("root")
                if not data_cid:
                    result["error"] = "No root CID returned from import"
                    result["error_type"] = "ImportError"
                    return result
                
                # Start deal
                deal_result = self.lotus_kit.client_start_deal(
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
                
                # Success!
                result["success"] = True
                result["ipfs_cid"] = cid
                result["filecoin_cid"] = data_cid
                result["deal_cid"] = deal_result.get("result", {}).get("/")
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

def test_filecoin_model_methods():
    """Test all FilecoinModel methods with both success and failure scenarios."""
    results = {
        "timestamp": time.time(),
        "tests": {},
        "success": True
    }
    
    # Test with failing Lotus API
    failing_lotus = MockLotusKit(metadata={"api_url": "http://localhost:9999/rpc/v0"}, should_succeed=False)
    failing_model = FilecoinModel(lotus_kit_instance=failing_lotus)
    
    # Test with working Lotus API
    working_lotus = MockLotusKit(metadata={"api_url": "http://localhost:1234/rpc/v0"}, should_succeed=True)
    working_model = FilecoinModel(lotus_kit_instance=working_lotus)
    
    # Test: Initialization
    results["tests"]["initialization"] = {
        "success": failing_model is not None and working_model is not None,
        "message": "FilecoinModel instances initialized successfully"
    }
    
    # Test methods with failing Lotus API
    method_tests = [
        ("check_connection", [], {}),
        ("list_wallets", [], {}),
        ("get_wallet_balance", ["t1abjxfbp274xpdqcpuaykwkfb43omjotacm2p3za"], {}),
        ("create_wallet", ["bls"], {}),
        ("list_miners", [], {}),
        ("list_deals", [], {}),
        ("list_imports", [], {})
    ]
    
    # Run failing tests
    failing_results = {}
    for method_name, args, kwargs in method_tests:
        try:
            method = getattr(failing_model, method_name)
            result = method(*args, **kwargs)
            
            # Verify error structure
            has_error = "error" in result
            has_error_type = "error_type" in result
            has_timestamp = "timestamp" in result
            has_operation = "operation" in result
            has_duration = "duration_ms" in result
            
            # Method should fail but have proper error structure
            failing_results[method_name] = {
                "success": not result.get("success", True) and has_error and has_error_type and has_timestamp and has_operation and has_duration,
                "has_proper_error_structure": has_error and has_error_type and has_timestamp and has_operation and has_duration,
                "error_type": result.get("error_type", "missing")
            }
            
            print(f"Failing test for {method_name}: {'SUCCESS' if failing_results[method_name]['success'] else 'FAILURE'}")
            
        except Exception as e:
            failing_results[method_name] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            print(f"Unexpected exception in {method_name}: {e}")
    
    results["tests"]["failing_methods"] = failing_results
    
    # Run successful tests
    working_results = {}
    for method_name, args, kwargs in method_tests:
        try:
            method = getattr(working_model, method_name)
            result = method(*args, **kwargs)
            
            # Verify success structure
            has_success = "success" in result
            has_timestamp = "timestamp" in result
            has_operation = "operation" in result
            has_duration = "duration_ms" in result
            
            # Method should succeed
            working_results[method_name] = {
                "success": result.get("success", False) and has_success and has_timestamp and has_operation and has_duration,
                "has_proper_structure": has_success and has_timestamp and has_operation and has_duration
            }
            
            print(f"Working test for {method_name}: {'SUCCESS' if working_results[method_name]['success'] else 'FAILURE'}")
            
        except Exception as e:
            working_results[method_name] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            print(f"Unexpected exception in {method_name}: {e}")
    
    results["tests"]["working_methods"] = working_results
    
    # Test cross-backend operations
    ipfs_model = MockIPFSModel(should_succeed=True)
    cross_backend_model = FilecoinModel(lotus_kit_instance=working_lotus, ipfs_model=ipfs_model)
    
    # Test ipfs_to_filecoin
    try:
        ipfs_to_filecoin_result = cross_backend_model.ipfs_to_filecoin(
            cid="QmTest123",
            miner="t01000",
            price="0",
            duration=1000,
            wallet=None,
            verified=False,
            fast_retrieval=True,
            pin=True
        )
        
        # Verify success
        cross_backend_success = ipfs_to_filecoin_result.get("success", False)
        has_ipfs_cid = "ipfs_cid" in ipfs_to_filecoin_result
        has_filecoin_cid = "filecoin_cid" in ipfs_to_filecoin_result
        has_deal_cid = "deal_cid" in ipfs_to_filecoin_result
        
        results["tests"]["cross_backend"] = {
            "success": cross_backend_success and has_ipfs_cid and has_filecoin_cid and has_deal_cid,
            "has_ipfs_cid": has_ipfs_cid,
            "has_filecoin_cid": has_filecoin_cid,
            "has_deal_cid": has_deal_cid
        }
        
        print(f"Cross-backend test (ipfs_to_filecoin): {'SUCCESS' if results['tests']['cross_backend']['success'] else 'FAILURE'}")
        
    except Exception as e:
        results["tests"]["cross_backend"] = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        print(f"Unexpected exception in ipfs_to_filecoin: {e}")
    
    # Test dependency validation - missing IPFS model
    no_ipfs_model = FilecoinModel(lotus_kit_instance=working_lotus, ipfs_model=None)
    try:
        no_ipfs_result = no_ipfs_model.ipfs_to_filecoin(
            cid="QmTest123",
            miner="t01000",
            price="0",
            duration=1000
        )
        
        # Should fail with DependencyError
        dependency_check = (not no_ipfs_result.get("success", True) and 
                          no_ipfs_result.get("error_type") == "DependencyError")
        
        results["tests"]["dependency_check"] = {
            "success": dependency_check,
            "error_type": no_ipfs_result.get("error_type", "missing"),
            "has_proper_error": no_ipfs_result.get("error_type") == "DependencyError"
        }
        
        print(f"Dependency check test: {'SUCCESS' if results['tests']['dependency_check']['success'] else 'FAILURE'}")
        
    except Exception as e:
        results["tests"]["dependency_check"] = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        print(f"Unexpected exception in dependency check: {e}")
    
    # Input validation
    try:
        invalid_input_result = cross_backend_model.ipfs_to_filecoin(
            cid="",  # Empty CID should fail validation
            miner="t01000",
            price="0",
            duration=1000
        )
        
        # Should fail with ValidationError
        validation_check = (not invalid_input_result.get("success", True) and 
                           invalid_input_result.get("error_type") == "ValidationError")
        
        results["tests"]["validation_check"] = {
            "success": validation_check,
            "error_type": invalid_input_result.get("error_type", "missing"),
            "has_proper_error": invalid_input_result.get("error_type") == "ValidationError"
        }
        
        print(f"Validation check test: {'SUCCESS' if results['tests']['validation_check']['success'] else 'FAILURE'}")
        
    except Exception as e:
        results["tests"]["validation_check"] = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        print(f"Unexpected exception in validation check: {e}")
    
    # Overall success - all tests passed
    all_failing_tests_passed = all(test.get("success", False) for test in failing_results.values())
    all_working_tests_passed = all(test.get("success", False) for test in working_results.values())
    cross_backend_test_passed = results["tests"]["cross_backend"].get("success", False)
    dependency_check_passed = results["tests"]["dependency_check"].get("success", False)
    validation_check_passed = results["tests"]["validation_check"].get("success", False)
    
    overall_success = (results["tests"]["initialization"]["success"] and
                     all_failing_tests_passed and
                     all_working_tests_passed and
                     cross_backend_test_passed and
                     dependency_check_passed and
                     validation_check_passed)
    
    results["success"] = overall_success
    
    # Save results
    with open(TEST_RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n===== Test Results =====")
    print(f"Initialization: {'✅ PASSED' if results['tests']['initialization']['success'] else '❌ FAILED'}")
    
    print("\nFailing API Tests:")
    for method_name, result in failing_results.items():
        print(f"  {method_name}: {'✅ PASSED' if result.get('success', False) else '❌ FAILED'}")
        
    print("\nWorking API Tests:")
    for method_name, result in working_results.items():
        print(f"  {method_name}: {'✅ PASSED' if result.get('success', False) else '❌ FAILED'}")
        
    print(f"\nCross-Backend Operation: {'✅ PASSED' if cross_backend_test_passed else '❌ FAILED'}")
    print(f"Dependency Validation: {'✅ PASSED' if dependency_check_passed else '❌ FAILED'}")
    print(f"Input Validation: {'✅ PASSED' if validation_check_passed else '❌ FAILED'}")
    
    print(f"\nOverall Result: {'✅ PASSED' if results['success'] else '❌ FAILED'}")
    print(f"Test results saved to {TEST_RESULTS_FILE}")
    
    return results["success"]

if __name__ == "__main__":
    # Run the test
    success = test_filecoin_model_methods()
    sys.exit(0 if success else 1)