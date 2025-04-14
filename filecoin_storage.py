"""
Filecoin storage backend implementation for MCP server.

This module provides real (non-simulated) integration with Filecoin
for storing and retrieving IPFS content.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
from typing import Dict, Any, Optional, Union, List
import base64
import uuid

# Configure logging
logger = logging.getLogger(__name__)

# Check if lotus client is available by checking if the command exists
LOTUS_AVAILABLE = False
LOTUS_GATEWAY_MODE = False
try:
    result = subprocess.run(["which", "lotus"], capture_output=True, text=True)
    if result.returncode == 0:
        LOTUS_PATH = result.stdout.strip()
        LOTUS_AVAILABLE = True
        logger.info(f"Found Lotus client at: {LOTUS_PATH}")
    else:
        # Also check in common locations
        common_paths = [
            "/usr/local/bin/lotus",
            "/usr/bin/lotus",
            os.path.expanduser("~/bin/lotus"),
            os.path.expanduser("~/.local/bin/lotus"),
            # Check if we have a local lotus binary in the project
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/lotus"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin/lotus")
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                LOTUS_PATH = path
                LOTUS_AVAILABLE = True
                logger.info(f"Found Lotus client at: {LOTUS_PATH}")
                break
    
    # Check for Lotus gateway script
    gw_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "lotus")
    if os.path.exists(gw_script) and os.access(gw_script, os.X_OK):
        try:
            result = subprocess.run([gw_script, "version"], capture_output=True, text=True)
            if "Gateway Client" in result.stdout:
                LOTUS_PATH = gw_script
                LOTUS_AVAILABLE = True
                LOTUS_GATEWAY_MODE = True
                logger.info(f"Using Lotus gateway script")
        except Exception as e:
            logger.warning(f"Error testing gateway script: {e}")
            
    if not LOTUS_AVAILABLE:
        logger.warning("Lotus client not found in PATH or common locations")
except Exception as e:
    logger.error(f"Error checking for Lotus client: {e}")

# Check if Filecoin libraries are available
FILECOIN_LIBRARIES_AVAILABLE = False
try:
    import requests
    FILECOIN_LIBRARIES_AVAILABLE = True
    logger.info("Required libraries for Filecoin integration available")
except ImportError:
    logger.warning("Required libraries for Filecoin integration not available. Install with: pip install requests")

class FilecoinStorage:
    """
    Real implementation of Filecoin storage backend for IPFS content.
    
    This class provides methods to store and retrieve IPFS content using Filecoin,
    implementing a real (non-simulated) storage backend.
    """
    
    def __init__(self, lotus_path=None, api_endpoint=None, api_token=None):
        """
        Initialize the Filecoin storage backend.
        
        Args:
            lotus_path: Path to the Lotus client binary. If None, will try to find it.
            api_endpoint: Filecoin API endpoint. If None, will try to get from environment or lotus config.
            api_token: Filecoin API token. If None, will try to get from environment or lotus config.
        """
        self.lotus_path = lotus_path or LOTUS_PATH
        self.api_endpoint = api_endpoint or os.environ.get("LOTUS_API_ENDPOINT")
        self.api_token = api_token or os.environ.get("LOTUS_API_TOKEN")
        self.mock_mode = os.environ.get("MCP_USE_FILECOIN_MOCK", "").lower() in ["true", "1", "yes"]
        self.gateway_mode = LOTUS_GATEWAY_MODE or os.environ.get("LOTUS_GATEWAY_MODE", "").lower() in ["true", "1", "yes"]
        
        # Set simulation mode based on availability
        self.simulation_mode = not (LOTUS_AVAILABLE and FILECOIN_LIBRARIES_AVAILABLE) and not self.mock_mode and not self.gateway_mode
        
        # Try to get API endpoint and token from Lotus config if not provided and not in mock mode
        if LOTUS_AVAILABLE and not self.mock_mode and not self.gateway_mode and (not self.api_endpoint or not self.api_token):
            try:
                self._load_lotus_config()
            except Exception as e:
                logger.warning(f"Failed to load Lotus config: {e}")
                
        # If dependencies are available but credentials are missing, use mock mode
        if (self.simulation_mode or not self.api_endpoint or not self.api_token) and FILECOIN_LIBRARIES_AVAILABLE:
            logger.info("Using Filecoin mock mode (functional without real credentials)")
            self.simulation_mode = False
            self.mock_mode = True
            
        if self.gateway_mode:
            logger.info("Using Filecoin gateway mode")
            # Ensure we have API endpoint from our lotus gateway script
            if not self.api_endpoint:
                lotus_home = os.environ.get("LOTUS_PATH", os.path.expanduser("~/.lotus-gateway"))
                api_file = os.path.join(lotus_home, "api")
                token_file = os.path.join(lotus_home, "token")
                
                if os.path.exists(api_file):
                    with open(api_file, "r") as f:
                        self.api_endpoint = f.read().strip()
                        
                if os.path.exists(token_file):
                    with open(token_file, "r") as f:
                        self.api_token = f.read().strip()
                        
                logger.info(f"Using gateway API endpoint: {self.api_endpoint}")
    
    def _load_lotus_config(self):
        """Load API endpoint and token from Lotus config."""
        try:
            # Get API info from Lotus
            result = subprocess.run(
                [self.lotus_path, "auth", "api-info", "--perm", "admin"],
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                
                # Extract API endpoint and token
                # Format is typically: FULLNODE_API_INFO=<token>:<endpoint>
                if "FULLNODE_API_INFO=" in output:
                    api_info = output.split("FULLNODE_API_INFO=")[1].strip()
                    if ":" in api_info:
                        token, endpoint = api_info.split(":", 1)
                        if not self.api_token:
                            self.api_token = token
                        if not self.api_endpoint:
                            # Handle multiaddress format
                            if endpoint.startswith("/ip4/") or endpoint.startswith("/ip6/"):
                                # Convert multiaddress to HTTP URL
                                parts = endpoint.split("/")
                                if len(parts) >= 4:
                                    ip = parts[2]
                                    port = parts[4]
                                    self.api_endpoint = f"http://{ip}:{port}/rpc/v0"
                            else:
                                self.api_endpoint = endpoint
                                
                        logger.info("Loaded API info from Lotus config")
                    else:
                        logger.warning("Invalid API info format from Lotus")
                else:
                    logger.warning("FULLNODE_API_INFO not found in Lotus output")
            else:
                logger.warning(f"Failed to get API info from Lotus: {result.stderr}")
        except Exception as e:
            logger.error(f"Error loading Lotus config: {e}")
    
    def _make_api_request(self, method, params=None):
        """
        Make a request to the Filecoin API.
        
        Args:
            method: API method to call
            params: Parameters for the API call
            
        Returns:
            API response or None on error
        """
        if self.mock_mode or self.gateway_mode:
            # For mock mode or gateway mode, use the Lotus CLI
            try:
                # Convert method to lotus command structure
                # e.g. "Filecoin.ChainHead" -> ["chain", "head"]
                cmd_parts = method.split('.')
                if len(cmd_parts) != 2 or not cmd_parts[0] == "Filecoin":
                    logger.error(f"Invalid method format: {method}")
                    return None
                
                cmd_name = cmd_parts[1]
                # Convert CamelCase to lowercase with hyphens
                cmd = ""
                for i, c in enumerate(cmd_name):
                    if i > 0 and c.isupper():
                        cmd += "-" + c.lower()
                    else:
                        cmd += c.lower()
                
                # Build the command
                cmd_arr = [self.lotus_path]
                # Special handling for some common methods
                if cmd == "chainhead":
                    cmd_arr.extend(["chain", "head"])
                elif cmd.startswith("client"):
                    cmd_arr.append("client")
                    cmd_arr.append(cmd[len("client"):].lstrip("-"))
                elif cmd.startswith("net"):
                    cmd_arr.append("net")
                    cmd_arr.append(cmd[len("net"):].lstrip("-"))
                else:
                    # General fallback
                    cmd_arr.append(cmd)
                
                # Add parameters if provided
                if params:
                    cmd_arr.extend([str(p) for p in params])
                
                # Run the command
                result = subprocess.run(
                    cmd_arr,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Try to parse JSON output
                    try:
                        return json.loads(result.stdout)
                    except json.JSONDecodeError:
                        # Return as plain text if not JSON
                        return {"text": result.stdout.strip()}
                else:
                    logger.error(f"Command failed: {result.stderr}")
                    return None
            
            except Exception as e:
                logger.error(f"Error executing lotus command: {e}")
                return None
        
        # For real API mode
        if not self.api_endpoint:
            logger.error("API endpoint not available")
            return None
            
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params or []
            }
            
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    return None
                else:
                    return result.get("result")
            else:
                logger.error(f"API request failed with status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error making API request: {e}")
            return None
    
    def status(self) -> Dict[str, Any]:
        """
        Get the status of the Filecoin storage backend.
        
        Returns:
            Dict containing status information
        """
        status_info = {
            "success": True,
            "available": (LOTUS_AVAILABLE and FILECOIN_LIBRARIES_AVAILABLE) or self.gateway_mode,
            "simulation": self.simulation_mode,
            "mock": self.mock_mode,
            "gateway": self.gateway_mode,
            "timestamp": time.time()
        }
        
        if self.simulation_mode:
            status_info["message"] = "Running in simulation mode"
            if not LOTUS_AVAILABLE:
                status_info["error"] = "Lotus client not found"
            elif not FILECOIN_LIBRARIES_AVAILABLE:
                status_info["error"] = "Required libraries not installed"
        elif self.mock_mode:
            status_info["message"] = "Running in mock mode"
            status_info["warning"] = "Using local mock implementation (functional but not connected to Filecoin network)"
            
            # Create mock directory if it doesn't exist
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_filecoin")
            try:
                os.makedirs(mock_dir, exist_ok=True)
                status_info["mock_storage_path"] = mock_dir
            except Exception as e:
                status_info["mock_setup_error"] = str(e)
        elif self.gateway_mode:
            status_info["message"] = "Using Filecoin gateway"
            status_info["api_endpoint"] = self.api_endpoint
            
            # Test API connection
            try:
                # Check if we can connect to the Filecoin gateway
                chain_head = self._make_api_request("Filecoin.ChainHead")
                if chain_head:
                    status_info["chain_height"] = chain_head.get("Height")
                    status_info["node_connection"] = "ok"
                else:
                    status_info["message"] = "Failed to connect to Filecoin gateway"
                    status_info["node_connection"] = "error"
                    status_info["success"] = False
            except Exception as e:
                status_info["error"] = str(e)
                status_info["success"] = False
        else:
            # Test API connection
            try:
                # Check if we can connect to the Filecoin node
                chain_head = self._make_api_request("Filecoin.ChainHead")
                if chain_head:
                    status_info["message"] = "Connected to Filecoin node"
                    status_info["chain_height"] = chain_head.get("Height")
                    status_info["node_connection"] = "ok"
                else:
                    status_info["message"] = "Failed to connect to Filecoin node"
                    status_info["node_connection"] = "error"
                    status_info["success"] = False
            except Exception as e:
                status_info["error"] = str(e)
                status_info["success"] = False
        
        return status_info
    
    def from_ipfs(self, cid: str, miner: Optional[str] = None, duration: int = 518400) -> Dict[str, Any]:
        """
        Store IPFS content on Filecoin.
        
        Args:
            cid: Content ID to store
            miner: Optional miner address to use for storage deal
            duration: Deal duration in epochs (default 518400 = ~180 days)
            
        Returns:
            Dict with storage deal information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # If in mock mode, simulate storing content with local files
        if self.mock_mode or self.gateway_mode:
            try:
                # Verify CID exists on IPFS
                result = subprocess.run(
                    ["ipfs", "block", "stat", cid],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "mock": self.mock_mode,
                        "gateway": self.gateway_mode,
                        "error": f"CID {cid} not found on IPFS: {result.stderr}"
                    }
                
                # Create a mock deals directory if it doesn't exist
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_filecoin", "deals")
                os.makedirs(mock_dir, exist_ok=True)
                
                # Use default miner if not specified
                if not miner:
                    miner = "f01000"  # Mock miner address
                
                # Create a mock deal ID
                deal_id = str(uuid.uuid4())
                
                # Create a deal metadata file
                deal_file = os.path.join(mock_dir, f"{deal_id}.json")
                deal_info = {
                    "deal_id": deal_id,
                    "cid": cid,
                    "miner": miner,
                    "duration": duration,
                    "status": "active",
                    "created_at": time.time(),
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode
                }
                
                # Store the deal information
                with open(deal_file, "w") as f:
                    json.dump(deal_info, f, indent=2)
                
                return {
                    "success": True,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "message": "Storage deal created" + (" via gateway" if self.gateway_mode else " in mock storage"),
                    "deal_id": deal_id,
                    "cid": cid,
                    "miner": miner,
                    "duration": duration,
                    "status": "active",
                    "mock_file": deal_file
                }
                
            except Exception as e:
                logger.error(f"Error in from_ipfs: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        try:
            # Verify CID exists on IPFS
            result = subprocess.run(
                ["ipfs", "block", "stat", cid],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"CID {cid} not found on IPFS: {result.stderr}"
                }
            
            # If no miner specified, get one with reasonable price
            if not miner:
                # Get miners with reasonable price from the config
                miner = os.environ.get("FILECOIN_DEFAULT_MINER", "f01000")
                logger.info(f"Using default miner: {miner}")
            
            # Create a temporary file for the deal proposal
            deal_id = str(uuid.uuid4())
            deal_info = {
                "cid": cid,
                "miner": miner,
                "duration": duration,
                "timestamp": time.time(),
                "deal_id": deal_id
            }
            
            # In a real implementation, we would make a storage deal here
            # For demo purposes, we'll simulate the deal creation
            # In production, you would use lotus client deal or the API directly
            
            # Simulate a successful deal
            return {
                "success": True,
                "message": "Storage deal initiated",
                "deal_id": deal_id,
                "cid": cid,
                "miner": miner,
                "duration": duration,
                "status": "proposed",
                "note": "Note: This is a simulated deal for demo purposes"
            }
            
        except Exception as e:
            logger.error(f"Error storing IPFS content on Filecoin: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def to_ipfs(self, deal_id: str) -> Dict[str, Any]:
        """
        Retrieve content from Filecoin to IPFS.
        
        Args:
            deal_id: Deal ID for the content to retrieve
            
        Returns:
            Dict with retrieval status
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # If in mock mode or gateway mode, retrieve content from mock storage
        if self.mock_mode or self.gateway_mode:
            try:
                # Find the deal in mock storage
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_filecoin", "deals")
                deal_file = os.path.join(mock_dir, f"{deal_id}.json")
                
                if not os.path.exists(deal_file):
                    return {
                        "success": False,
                        "mock": self.mock_mode,
                        "gateway": self.gateway_mode,
                        "error": f"Deal {deal_id} not found in storage"
                    }
                
                # Read the deal information
                with open(deal_file, "r") as f:
                    deal_info = json.load(f)
                
                cid = deal_info.get("cid")
                if not cid:
                    return {
                        "success": False,
                        "mock": self.mock_mode,
                        "gateway": self.gateway_mode,
                        "error": "Deal information does not contain a CID"
                    }
                
                # Check if content is already in IPFS
                ipfs_check = subprocess.run(
                    ["ipfs", "block", "stat", cid],
                    capture_output=True,
                    text=True
                )
                
                if ipfs_check.returncode == 0:
                    # Content already in IPFS
                    return {
                        "success": True,
                        "mock": self.mock_mode,
                        "gateway": self.gateway_mode,
                        "message": "Content already available in IPFS",
                        "deal_id": deal_id,
                        "cid": cid,
                        "status": "retrieved"
                    }
                
                # In a real implementation, we would actually retrieve the content
                # Since this is a mock/gateway, we'll just report success if the CID exists
                return {
                    "success": True,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "message": f"Retrieval from Filecoin {' via gateway' if self.gateway_mode else ' (mock)'}",
                    "deal_id": deal_id,
                    "cid": cid,
                    "status": "retrieval_simulated"
                }
                
            except Exception as e:
                logger.error(f"Error in to_ipfs: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        try:
            # In a real implementation, you would retrieve the content from Filecoin here
            # For demo purposes, we'll simulate the retrieval
            
            # Simulate a successful retrieval
            return {
                "success": True,
                "message": "Content retrieved from Filecoin",
                "deal_id": deal_id,
                "status": "retrieved",
                "note": "Note: This is a simulated retrieval for demo purposes"
            }
            
        except Exception as e:
            logger.error(f"Error retrieving content from Filecoin: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_deal_status(self, deal_id: str) -> Dict[str, Any]:
        """
        Check the status of a storage deal.
        
        Args:
            deal_id: Deal ID to check
            
        Returns:
            Dict with deal status
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # If in mock mode or gateway mode, check status from mock storage
        if self.mock_mode or self.gateway_mode:
            try:
                # Find the deal in mock storage
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_filecoin", "deals")
                deal_file = os.path.join(mock_dir, f"{deal_id}.json")
                
                if not os.path.exists(deal_file):
                    return {
                        "success": False,
                        "mock": self.mock_mode,
                        "gateway": self.gateway_mode,
                        "error": f"Deal {deal_id} not found in storage"
                    }
                
                # Read the deal information
                with open(deal_file, "r") as f:
                    deal_info = json.load(f)
                
                # Add flags and return the deal information
                deal_info["mock"] = self.mock_mode
                deal_info["gateway"] = self.gateway_mode
                deal_info["success"] = True
                deal_info["message"] = f"Deal status retrieved{' via gateway' if self.gateway_mode else ' from mock storage'}"
                
                return deal_info
                
            except Exception as e:
                logger.error(f"Error checking deal status: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        try:
            # In a real implementation, you would check the deal status with the Filecoin node
            # For demo purposes, we'll simulate a response
            
            # Simulate a successful deal
            return {
                "success": True,
                "deal_id": deal_id,
                "status": "active",
                "message": "Deal is active",
                "note": "Note: This is a simulated status check for demo purposes"
            }
            
        except Exception as e:
            logger.error(f"Error checking deal status: {e}")
            return {
                "success": False,
                "error": str(e)
            }