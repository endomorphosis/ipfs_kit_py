"""
Filecoin Storage API integration for direct interaction with Filecoin storage providers.

This module provides a simplified interface for storing and retrieving data using
Filecoin storage providers, with support for automated miner selection and deal management.
"""

import logging
import os
import time
import json
import tempfile
import hashlib
import subprocess
import uuid
import requests
from typing import Dict, Any, List, Optional, Union, Tuple

# Configure logger
logger = logging.getLogger(__name__)

# Check for specialized Filecoin tools
try:
    # First check for Boost (the newer deal making tool)
    result = subprocess.run(["boost", "--version"], capture_output=True, text=True, timeout=2)
    BOOST_AVAILABLE = result.returncode == 0
except (subprocess.SubprocessError, FileNotFoundError, OSError):
    BOOST_AVAILABLE = False

try:
    # Check for Estuary client
    result = subprocess.run(["estuary-client", "--version"], capture_output=True, text=True, timeout=2)
    ESTUARY_AVAILABLE = result.returncode == 0
except (subprocess.SubprocessError, FileNotFoundError, OSError):
    ESTUARY_AVAILABLE = False

logger.info(f"Boost available: {BOOST_AVAILABLE}")
logger.info(f"Estuary client available: {ESTUARY_AVAILABLE}")

# Default API endpoints
DEFAULT_ESTUARY_API = "https://api.estuary.tech"
DEFAULT_FILECOIN_MINER_API = "https://api.filscan.io"


class FilecoinValidationError(Exception):
    """Error when input validation fails."""
    pass


class FilecoinContentNotFoundError(Exception):
    """Content with specified CID not found."""
    pass


class FilecoinConnectionError(Exception):
    """Error when connecting to Filecoin services."""
    pass


class FilecoinError(Exception):
    """Base class for all Filecoin-related exceptions."""
    pass


class FilecoinTimeoutError(Exception):
    """Timeout when communicating with Filecoin services."""
    pass


def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }


def handle_error(result, error, context=None):
    """Handle error and update result dict."""
    result["success"] = False
    result["error"] = str(error)
    result["error_type"] = type(error).__name__
    
    if context:
        for key, value in context.items():
            result[key] = value
            
    return result


class filecoin_storage:
    """
    Class for interacting with Filecoin storage providers.
    
    Provides functionality for storing content on Filecoin, retrieving content,
    and managing storage deals with miners.
    """
    
    def __init__(self, resources: Dict[str, Any] = None, metadata: Dict[str, Any] = None):
        """
        Initialize the Filecoin storage interface.
        
        Args:
            resources: Dictionary of resources like API keys
            metadata: Configuration metadata like endpoints
        """
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Set up API endpoints
        self.estuary_api = self.metadata.get("estuary_api") or DEFAULT_ESTUARY_API
        self.filscan_api = self.metadata.get("filecoin_miner_api") or DEFAULT_FILECOIN_MINER_API
        
        # API keys
        self.estuary_api_key = self.resources.get("estuary_api_key") or os.environ.get("ESTUARY_API_KEY")
        
        # Storage mode selection (boost, estuary, or api)
        if BOOST_AVAILABLE:
            self.primary_mode = "boost"
        elif ESTUARY_AVAILABLE:
            self.primary_mode = "estuary"
        elif self.estuary_api_key:
            self.primary_mode = "estuary_api"
        else:
            self.primary_mode = "api"
            
        logger.info(f"Using Filecoin storage primary mode: {self.primary_mode}")
        
        # Create session for API calls
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        
        # Add API key if available
        if self.estuary_api_key and (self.primary_mode == "estuary_api"):
            self.session.headers.update({"Authorization": f"Bearer {self.estuary_api_key}"})
            
        # Initialize miner cache
        self.miner_cache = {}
        self.miner_cache_updated = 0
        self.miner_cache_ttl = 3600  # 1 hour
        
        # Load optional local miner preferences
        self.miner_preferences = self.metadata.get("miner_preferences", {})
        
    def _load_miner_metrics(self, force_refresh=False):
        """
        Load miner metrics from Filscan or similar API.
        
        Args:
            force_refresh: Whether to force refresh the cache
            
        Returns:
            Dictionary with miner metrics
        """
        # Check if cache is still valid
        if (not force_refresh and 
            self.miner_cache and 
            time.time() - self.miner_cache_updated < self.miner_cache_ttl):
            return self.miner_cache
        
        try:
            # Fetch active storage miners from Filscan API
            url = f"{self.filscan_api}/v1/storageprovider/list"
            params = {
                "page": 1,
                "page_size": 50,
                "order_by": "total_power",
                "order": "desc"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("status") == "success" and "data" in data:
                    miners = data["data"].get("storage_providers", [])
                    
                    # Process and cache miner data
                    self.miner_cache = {
                        "miners": miners,
                        "top_miners": [m["address"] for m in miners[:20]],
                        "metrics": {
                            m["address"]: {
                                "power": m.get("total_power", 0),
                                "sector_size": m.get("sector_size", 0),
                                "raw_power": m.get("raw_power", 0),
                                "rank": idx + 1
                            } for idx, m in enumerate(miners)
                        }
                    }
                    
                    self.miner_cache_updated = time.time()
                    logger.info(f"Updated miner cache with {len(miners)} miners")
                    
                    return self.miner_cache
            
            # Fallback to default miners if API fails
            if not self.miner_cache:
                # Default to some known reliable miners
                default_miners = ["f01019199", "f01240", "f01192075", "f01699618"]
                self.miner_cache = {
                    "miners": [{"address": m} for m in default_miners],
                    "top_miners": default_miners,
                    "metrics": {m: {"rank": idx + 1} for idx, m in enumerate(default_miners)},
                    "is_fallback": True
                }
                self.miner_cache_updated = time.time()
                logger.warning("Using fallback miner list")
            
            return self.miner_cache
            
        except Exception as e:
            logger.error(f"Error loading miner metrics: {e}")
            
            # Use cached data if available, otherwise default
            if not self.miner_cache:
                default_miners = ["f01019199", "f01240", "f01192075", "f01699618"]
                self.miner_cache = {
                    "miners": [{"address": m} for m in default_miners],
                    "top_miners": default_miners,
                    "metrics": {m: {"rank": idx + 1} for idx, m in enumerate(default_miners)},
                    "is_fallback": True,
                    "error": str(e)
                }
                self.miner_cache_updated = time.time()
                
            return self.miner_cache
    
    def _select_miners(self, replication: int = 1, exclude_miners: List[str] = None) -> List[str]:
        """
        Select miners for storage based on performance and availability.
        
        Args:
            replication: Number of miners to select
            exclude_miners: List of miners to exclude
            
        Returns:
            List of selected miner addresses
        """
        exclude_miners = exclude_miners or []
        
        # Load miner metrics
        metrics = self._load_miner_metrics()
        
        # Start with preferred miners if specified
        preferred = self.miner_preferences.get("preferred_miners", [])
        
        # Filter out excluded miners
        available_miners = [
            m for m in metrics.get("top_miners", [])
            if m not in exclude_miners
        ]
        
        # Add preferred miners at the top if not excluded
        selected_miners = [
            m for m in preferred
            if m not in exclude_miners and m in available_miners
        ]
        
        # Add more miners until we reach the desired replication count
        remaining = replication - len(selected_miners)
        if remaining > 0:
            # Use miners from the top list that aren't already selected
            additional_miners = [
                m for m in available_miners
                if m not in selected_miners
            ][:remaining]
            
            selected_miners.extend(additional_miners)
        
        # Return the selected miners
        return selected_miners[:replication]
    
    def _run_command(self, cmd, timeout=120):
        """
        Run a command-line tool with proper error handling.
        
        Args:
            cmd: List of command arguments
            timeout: Command timeout in seconds
            
        Returns:
            Dictionary with command results
        """
        operation = cmd[0] if cmd else "unknown"
        result = create_result_dict(f"command_{operation}")
        result["command"] = " ".join(cmd)
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result["success"] = process.returncode == 0
            result["exit_code"] = process.returncode
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            
            # Try to parse JSON output if possible
            if result["success"] and process.stdout.strip().startswith("{"):
                try:
                    result["parsed_output"] = json.loads(process.stdout)
                except json.JSONDecodeError:
                    pass
            
            return result
            
        except subprocess.TimeoutExpired as e:
            return handle_error(
                result, 
                FilecoinTimeoutError(f"Command timed out after {timeout} seconds"),
                {"timeout": timeout}
            )
            
        except Exception as e:
            return handle_error(result, e)
    
    def filecoin_store_file(
        self,
        file_path: str,
        miner: Optional[str] = None,
        replication: int = 1,
        duration: int = 518400,  # 180 days (in epochs)
        max_price: Optional[str] = None,
        verified_deal: bool = False,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """
        Store a file on Filecoin.
        
        Args:
            file_path: Path to file to store
            miner: Specific miner to use (optional)
            replication: Number of copies to store (if miner not specified)
            duration: Deal duration in epochs
            max_price: Maximum price per epoch per GiB
            verified_deal: Whether to use verified deals
            timeout: Operation timeout in seconds
            
        Returns:
            Dictionary with storage result
        """
        result = create_result_dict("filecoin_store_file")
        result["file_path"] = file_path
        
        try:
            # Validate inputs
            if not os.path.isfile(file_path):
                raise FilecoinValidationError(f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise FilecoinValidationError("File is empty")
            
            result["file_size"] = file_size
            
            # Calculate file CID for tracking
            # Compute a CID in a similar format as IPFS CIDs
            file_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    file_hash.update(chunk)
            
            cid = f"bafy2bzace{file_hash.hexdigest()[:32]}"
            result["cid"] = cid
            
            # Determine storage approach based on mode
            if self.primary_mode == "boost" and BOOST_AVAILABLE:
                return self._store_with_boost(
                    file_path=file_path,
                    cid=cid,
                    miner=miner,
                    replication=replication,
                    duration=duration,
                    max_price=max_price,
                    verified_deal=verified_deal,
                    timeout=timeout
                )
                
            elif (self.primary_mode == "estuary" and ESTUARY_AVAILABLE) or self.primary_mode == "estuary_api":
                return self._store_with_estuary(
                    file_path=file_path,
                    cid=cid,
                    miner=miner,
                    replication=replication,
                    duration=duration,
                    max_price=max_price,
                    verified_deal=verified_deal,
                    timeout=timeout
                )
                
            else:
                # Fall back to API-based storage
                return self._store_with_api(
                    file_path=file_path,
                    cid=cid,
                    miner=miner,
                    replication=replication,
                    duration=duration,
                    max_price=max_price,
                    verified_deal=verified_deal,
                    timeout=timeout
                )
                
        except Exception as e:
            logger.error(f"Error storing file on Filecoin: {e}")
            return handle_error(result, e)
    
    def _store_with_boost(
        self,
        file_path: str,
        cid: str,
        miner: Optional[str] = None,
        replication: int = 1,
        duration: int = 518400,
        max_price: Optional[str] = None,
        verified_deal: bool = False,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """Store file using Boost client."""
        result = create_result_dict("store_with_boost")
        result["file_path"] = file_path
        result["cid"] = cid
        
        try:
            # Select miners if not specified
            miners_to_use = [miner] if miner else self._select_miners(replication)
            result["miners"] = miners_to_use
            
            # Make deals with each selected miner
            deals = []
            
            for miner_addr in miners_to_use:
                # Prepare boost command
                cmd = [
                    "boost", "deal", "--verified-deal", str(verified_deal).lower(),
                    "--duration", str(duration),
                    "--provider", miner_addr,
                    file_path
                ]
                
                if max_price:
                    cmd.extend(["--price", max_price])
                
                # Run boost command
                deal_result = self._run_command(cmd, timeout=timeout)
                
                if deal_result.get("success", False):
                    # Parse output to get deal details
                    deal_info = {
                        "miner": miner_addr,
                        "duration": duration,
                        "verified": verified_deal,
                        "output": deal_result.get("stdout", "")
                    }
                    
                    # Try to extract deal ID from output
                    import re
                    deal_id_match = re.search(r"deal_id:\s*(\d+)", deal_result.get("stdout", ""))
                    if deal_id_match:
                        deal_info["deal_id"] = deal_id_match.group(1)
                    
                    deals.append(deal_info)
                else:
                    # Log error but continue with other miners
                    logger.error(f"Failed to make deal with miner {miner_addr}: {deal_result.get('stderr', '')}")
            
            # Return success if at least one deal was made
            if deals:
                result["success"] = True
                result["deals"] = deals
                result["deal_count"] = len(deals)
                
                return result
            else:
                # No deals were successful
                return handle_error(
                    result,
                    FilecoinError("Failed to make any deals"),
                    {"attempted_miners": miners_to_use}
                )
                
        except Exception as e:
            logger.error(f"Error in boost storage: {e}")
            return handle_error(result, e)
    
    def _store_with_estuary(
        self,
        file_path: str,
        cid: str,
        miner: Optional[str] = None,
        replication: int = 1,
        duration: int = 518400,
        max_price: Optional[str] = None,
        verified_deal: bool = False,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """Store file using Estuary."""
        result = create_result_dict("store_with_estuary")
        result["file_path"] = file_path
        result["cid"] = cid
        
        try:
            # Determine whether to use CLI or API
            if self.primary_mode == "estuary" and ESTUARY_AVAILABLE:
                # Use Estuary CLI
                cmd = ["estuary-client", "up", file_path]
                
                # Add options
                if miner:
                    cmd.extend(["--miner", miner])
                    
                # Run command
                upload_result = self._run_command(cmd, timeout=timeout)
                
                if upload_result.get("success", False):
                    # Parse output to get content details
                    import re
                    cid_match = re.search(r"CID:\s*(\w+)", upload_result.get("stdout", ""))
                    content_id_match = re.search(r"ID:\s*(\d+)", upload_result.get("stdout", ""))
                    
                    estuary_cid = cid_match.group(1) if cid_match else None
                    content_id = content_id_match.group(1) if content_id_match else None
                    
                    result["success"] = True
                    result["estuary_cid"] = estuary_cid
                    result["content_id"] = content_id
                    result["deals"] = [{
                        "type": "estuary",
                        "content_id": content_id,
                        "replication": replication
                    }]
                    
                    return result
                else:
                    # CLI upload failed
                    return handle_error(
                        result,
                        FilecoinError(f"Estuary upload failed: {upload_result.get('stderr', '')}"),
                        {"command_result": upload_result}
                    )
                    
            else:
                # Use Estuary API
                if not self.estuary_api_key:
                    return handle_error(
                        result,
                        FilecoinValidationError("Estuary API key is required for API uploads"),
                        {"mode": "estuary_api"}
                    )
                
                # Prepare request
                upload_url = f"{self.estuary_api}/content/add"
                
                files = {
                    "data": (os.path.basename(file_path), open(file_path, "rb"))
                }
                
                params = {
                    "replication": replication
                }
                
                if miner:
                    params["miner"] = miner
                
                headers = {
                    "Authorization": f"Bearer {self.estuary_api_key}",
                    "Accept": "application/json"
                }
                
                # Make API request
                response = requests.post(
                    upload_url,
                    files=files,
                    params=params,
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code in (200, 201):
                    # Parse response
                    api_result = response.json()
                    
                    # Extract content details
                    estuary_cid = api_result.get("cid")
                    content_id = api_result.get("estuaryId")
                    
                    result["success"] = True
                    result["estuary_cid"] = estuary_cid
                    result["content_id"] = content_id
                    result["deals"] = [{
                        "type": "estuary",
                        "content_id": content_id,
                        "replication": replication
                    }]
                    result["api_response"] = api_result
                    
                    return result
                else:
                    # API upload failed
                    error_msg = f"Estuary API upload failed: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = f"{error_msg} - {error_data.get('error', '')}"
                    except Exception:
                        error_msg = f"{error_msg} - {response.text}"
                    
                    return handle_error(
                        result,
                        FilecoinError(error_msg),
                        {"status_code": response.status_code}
                    )
                    
        except Exception as e:
            logger.error(f"Error in Estuary storage: {e}")
            return handle_error(result, e)
    
    def _store_with_api(
        self,
        file_path: str,
        cid: str,
        miner: Optional[str] = None,
        replication: int = 1,
        duration: int = 518400,
        max_price: Optional[str] = None,
        verified_deal: bool = False,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """Store file using available APIs when no local clients are available."""
        result = create_result_dict("store_with_api")
        result["file_path"] = file_path
        result["cid"] = cid
        
        # For now, this is a simplified version that falls back to Estuary API
        # In a full implementation, this would have more options
        if self.estuary_api_key:
            return self._store_with_estuary(
                file_path=file_path,
                cid=cid,
                miner=miner,
                replication=replication,
                duration=duration,
                max_price=max_price,
                verified_deal=verified_deal,
                timeout=timeout
            )
        else:
            return handle_error(
                result,
                FilecoinError("No Filecoin storage implementation available")
            )
    
    def filecoin_retrieve_file(
        self,
        cid: str,
        output_path: str,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Retrieve a file from Filecoin.
        
        Args:
            cid: CID of content to retrieve
            output_path: Path to save retrieved file
            timeout: Operation timeout in seconds
            
        Returns:
            Dictionary with retrieval result
        """
        result = create_result_dict("filecoin_retrieve_file")
        result["cid"] = cid
        result["output_path"] = output_path
        
        try:
            # Try to retrieve the file
            # First check if we can retrieve via Estuary
            estuary_result = self._retrieve_with_estuary(
                cid=cid,
                output_path=output_path,
                timeout=timeout
            )
            
            if estuary_result.get("success", False):
                return estuary_result
            
            # If Estuary failed, try with IPFS gateway as fallback
            logger.info(f"Estuary retrieval failed, trying IPFS gateway: {estuary_result.get('error')}")
            
            # Try IPFS gateways for retrieval
            gateway_urls = [
                f"https://dweb.link/ipfs/{cid}",
                f"https://ipfs.io/ipfs/{cid}",
                f"https://cloudflare-ipfs.com/ipfs/{cid}"
            ]
            
            for gateway_url in gateway_urls:
                try:
                    logger.info(f"Trying to retrieve {cid} from {gateway_url}")
                    
                    # Download the file
                    response = requests.get(gateway_url, timeout=timeout/len(gateway_urls))
                    
                    if response.status_code == 200:
                        # Save the content to the output path
                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        
                        with open(output_path, "wb") as f:
                            f.write(response.content)
                        
                        result["success"] = True
                        result["gateway"] = gateway_url
                        result["size"] = len(response.content)
                        
                        return result
                        
                except Exception as gateway_error:
                    logger.warning(f"Gateway retrieval error ({gateway_url}): {gateway_error}")
                    continue
            
            # All retrieval methods failed
            return handle_error(
                result,
                FilecoinContentNotFoundError(f"Failed to retrieve content: {cid}"),
                {"estuary_result": estuary_result}
            )
            
        except Exception as e:
            logger.error(f"Error retrieving file from Filecoin: {e}")
            return handle_error(result, e)
    
    def _retrieve_with_estuary(
        self,
        cid: str,
        output_path: str,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Retrieve file using Estuary."""
        result = create_result_dict("retrieve_with_estuary")
        result["cid"] = cid
        result["output_path"] = output_path
        
        try:
            # Try to use Estuary CLI if available
            if ESTUARY_AVAILABLE:
                cmd = ["estuary-client", "get", cid, output_path]
                
                # Run command
                retrieval_result = self._run_command(cmd, timeout=timeout)
                
                if retrieval_result.get("success", False):
                    result["success"] = True
                    
                    # Get file size
                    if os.path.exists(output_path):
                        result["size"] = os.path.getsize(output_path)
                    
                    return result
                else:
                    # CLI retrieval failed
                    logger.warning(f"Estuary CLI retrieval failed: {retrieval_result.get('stderr', '')}")
            
            # Try Estuary API
            if self.estuary_api_key:
                # Try to get content info first to find the ID
                content_url = f"{self.estuary_api}/content/by-cid/{cid}"
                
                headers = {
                    "Authorization": f"Bearer {self.estuary_api_key}",
                    "Accept": "application/json"
                }
                
                response = requests.get(
                    content_url,
                    headers=headers,
                    timeout=timeout/3
                )
                
                if response.status_code == 200:
                    content_info = response.json()
                    
                    if isinstance(content_info, list) and content_info:
                        # Get the first matching content
                        content_id = content_info[0].get("id")
                        
                        # Now get the content data
                        download_url = f"{self.estuary_api}/content/{content_id}"
                        
                        download_response = requests.get(
                            download_url,
                            headers={"Authorization": f"Bearer {self.estuary_api_key}"},
                            timeout=timeout
                        )
                        
                        if download_response.status_code == 200:
                            # Save the content to the output path
                            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                            
                            with open(output_path, "wb") as f:
                                f.write(download_response.content)
                            
                            result["success"] = True
                            result["content_id"] = content_id
                            result["size"] = len(download_response.content)
                            
                            return result
                    
                # Direct download from Estuary
                direct_url = f"{self.estuary_api}/gw/ipfs/{cid}"
                direct_response = requests.get(direct_url, timeout=timeout/3)
                
                if direct_response.status_code == 200:
                    # Save the content to the output path
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                    
                    with open(output_path, "wb") as f:
                        f.write(direct_response.content)
                    
                    result["success"] = True
                    result["direct_download"] = True
                    result["size"] = len(direct_response.content)
                    
                    return result
            
            # Estuary retrieval failed
            return handle_error(
                result,
                FilecoinContentNotFoundError(f"Content not found in Estuary: {cid}")
            )
            
        except Exception as e:
            logger.error(f"Error in Estuary retrieval: {e}")
            return handle_error(result, e)
    
    def filecoin_list_deals(
        self,
        miner: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        List active Filecoin deals.
        
        Args:
            miner: Filter by miner address
            status: Filter by deal status
            limit: Maximum number of deals to return
            
        Returns:
            Dictionary with deals list
        """
        result = create_result_dict("filecoin_list_deals")
        
        try:
            deals = []
            
            # Try listing deals with Estuary if available
            if ESTUARY_AVAILABLE:
                cmd = ["estuary-client", "deals", "list"]
                
                if miner:
                    cmd.extend(["--miner", miner])
                
                if status:
                    cmd.extend(["--status", status])
                
                # Run command
                deals_result = self._run_command(cmd)
                
                if deals_result.get("success", False):
                    # Parse output to get deals
                    import re
                    from io import StringIO
                    import csv
                    
                    # Try to parse tabular output
                    lines = deals_result.get("stdout", "").strip().split('\n')
                    
                    if len(lines) > 1:
                        # Skip header row
                        for line in lines[1:]:
                            # Parse fields
                            fields = re.split(r'\s+', line.strip(), maxsplit=6)
                            
                            if len(fields) >= 5:
                                deal = {
                                    "deal_id": fields[0],
                                    "miner": fields[1] if len(fields) > 1 else "",
                                    "size": fields[2] if len(fields) > 2 else "",
                                    "status": fields[3] if len(fields) > 3 else "",
                                    "cid": fields[5] if len(fields) > 5 else "",
                                }
                                
                                deals.append(deal)
                    
                    result["success"] = True
                    result["deals"] = deals[:limit]
                    result["deal_count"] = len(deals[:limit])
                    
                    return result
            
            # Try Estuary API
            if self.estuary_api_key:
                # Get deals from API
                deals_url = f"{self.estuary_api}/content/deals"
                
                headers = {
                    "Authorization": f"Bearer {self.estuary_api_key}",
                    "Accept": "application/json"
                }
                
                response = requests.get(
                    deals_url,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    api_deals = response.json()
                    
                    # Format the deals
                    for deal in api_deals:
                        deals.append({
                            "deal_id": str(deal.get("dealId", "")),
                            "miner": deal.get("miner", ""),
                            "status": deal.get("status", ""),
                            "cid": deal.get("cid", ""),
                            "size": deal.get("size", ""),
                            "verified": deal.get("verified", False),
                            "on_chain_status": deal.get("onChainStatus", ""),
                            "start_epoch": deal.get("startEpoch"),
                            "end_epoch": deal.get("endEpoch")
                        })
                    
                    # Apply filters
                    if miner:
                        deals = [d for d in deals if d.get("miner") == miner]
                    
                    if status:
                        deals = [d for d in deals if status.lower() in d.get("status", "").lower()]
                    
                    result["success"] = True
                    result["deals"] = deals[:limit]
                    result["deal_count"] = len(deals[:limit])
                    
                    return result
            
            # No methods available
            return handle_error(
                result,
                FilecoinError("No method available to list deals")
            )
            
        except Exception as e:
            logger.error(f"Error listing Filecoin deals: {e}")
            return handle_error(result, e)
    
    def filecoin_check_deal(
        self,
        cid: str,
        miner: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check status of a Filecoin deal for a specific CID.
        
        Args:
            cid: CID of content to check
            miner: Filter by miner address
            
        Returns:
            Dictionary with deal status
        """
        result = create_result_dict("filecoin_check_deal")
        result["cid"] = cid
        
        try:
            # List all deals
            deals_result = self.filecoin_list_deals(miner=miner, limit=100)
            
            if deals_result.get("success", False):
                # Filter deals for this CID
                deals = deals_result.get("deals", [])
                matching_deals = [d for d in deals if d.get("cid") == cid]
                
                # Count active deals
                active_deals = [d for d in matching_deals if d.get("status", "").lower() in ("active", "sealed")]
                
                result["success"] = True
                result["deals"] = matching_deals
                result["deal_count"] = len(matching_deals)
                result["active_deals"] = len(active_deals)
                
                return result
            else:
                # Deal listing failed
                return handle_error(
                    result,
                    FilecoinError(f"Failed to check deals: {deals_result.get('error', 'Unknown error')}"),
                    {"deals_result": deals_result}
                )
                
        except Exception as e:
            logger.error(f"Error checking Filecoin deal: {e}")
            return handle_error(result, e)
    
    def filecoin_cancel_deals(
        self,
        cid: str,
        miner: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancel Filecoin deals for a specific CID.
        
        Args:
            cid: CID of content to cancel deals for
            miner: Filter by miner address
            
        Returns:
            Dictionary with cancellation status
        """
        result = create_result_dict("filecoin_cancel_deals")
        result["cid"] = cid
        
        try:
            # Check for existing deals
            deals_result = self.filecoin_check_deal(cid=cid, miner=miner)
            
            if not deals_result.get("success", False):
                return handle_error(
                    result,
                    FilecoinError(f"Failed to check deals: {deals_result.get('error', 'Unknown error')}"),
                    {"deals_result": deals_result}
                )
            
            deals = deals_result.get("deals", [])
            
            if not deals:
                # No deals found
                result["success"] = True
                result["message"] = "No deals found for the given CID"
                return result
            
            # Try to cancel each deal
            cancelled_deals = []
            failed_cancellations = []
            
            for deal in deals:
                deal_id = deal.get("deal_id")
                
                # Skip if no deal ID
                if not deal_id:
                    continue
                
                # Check if deal is sealed (can't be cancelled)
                if deal.get("status", "").lower() in ("sealed", "active"):
                    # Deal is sealed and cannot be cancelled
                    failed_cancellations.append({
                        "deal_id": deal_id,
                        "reason": "sealed deals cannot be cancelled",
                        "deal": deal
                    })
                    continue
                
                # Try to cancel the deal
                if ESTUARY_AVAILABLE:
                    # Try Estuary CLI
                    cmd = ["estuary-client", "deals", "cancel", deal_id]
                    cancel_result = self._run_command(cmd)
                    
                    if cancel_result.get("success", False):
                        cancelled_deals.append({
                            "deal_id": deal_id,
                            "result": "cancelled"
                        })
                    else:
                        failed_cancellations.append({
                            "deal_id": deal_id,
                            "reason": cancel_result.get("stderr", "unknown error"),
                            "result": cancel_result
                        })
                        
                elif self.estuary_api_key:
                    # Try Estuary API
                    cancel_url = f"{self.estuary_api}/deals/{deal_id}"
                    
                    headers = {
                        "Authorization": f"Bearer {self.estuary_api_key}",
                        "Accept": "application/json"
                    }
                    
                    response = requests.delete(
                        cancel_url,
                        headers=headers,
                        timeout=10
                    )
                    
                    if response.status_code in (200, 202, 204):
                        cancelled_deals.append({
                            "deal_id": deal_id,
                            "result": "cancelled"
                        })
                    else:
                        error_msg = f"HTTP {response.status_code}"
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("error", error_msg)
                        except Exception:
                            pass
                        
                        failed_cancellations.append({
                            "deal_id": deal_id,
                            "reason": error_msg
                        })
                        
                else:
                    # No method available
                    failed_cancellations.append({
                        "deal_id": deal_id,
                        "reason": "no cancellation method available"
                    })
            
            # Return results
            if cancelled_deals:
                result["success"] = True
                result["cancelled_deals"] = cancelled_deals
                result["failed_cancellations"] = failed_cancellations
                result["remaining_deals"] = failed_cancellations
            elif failed_cancellations:
                # Handle case where all deals failed due to being sealed
                sealed_deals = [f for f in failed_cancellations if "sealed" in f.get("reason", "").lower()]
                
                if len(sealed_deals) == len(failed_cancellations):
                    return handle_error(
                        result,
                        FilecoinError("All deals are sealed and cannot be cancelled"),
                        {
                            "cancelled_deals": [],
                            "failed_cancellations": failed_cancellations,
                            "remaining_deals": failed_cancellations
                        }
                    )
                else:
                    return handle_error(
                        result,
                        FilecoinError("Failed to cancel any deals"),
                        {
                            "cancelled_deals": [],
                            "failed_cancellations": failed_cancellations,
                            "remaining_deals": failed_cancellations
                        }
                    )
            else:
                # No deals were actually tried
                result["success"] = True
                result["message"] = "No deals found to cancel"
            
            return result
            
        except Exception as e:
            logger.error(f"Error cancelling Filecoin deals: {e}")
            return handle_error(result, e)
    
    def filecoin_add_metadata(
        self,
        cid: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add or update metadata for Filecoin content.
        
        Args:
            cid: CID of content to add metadata for
            metadata: Metadata key-value pairs to add
            
        Returns:
            Dictionary with metadata status
        """
        result = create_result_dict("filecoin_add_metadata")
        result["cid"] = cid
        
        try:
            # For now, store metadata locally since there's no standard way
            # to store metadata on Filecoin
            
            # Create directory if it doesn't exist
            metadata_dir = os.path.expanduser("~/.filecoin_metadata")
            os.makedirs(metadata_dir, exist_ok=True)
            
            # Create a file path based on CID
            metadata_path = os.path.join(metadata_dir, f"{cid}.json")
            
            # Load existing metadata if available
            existing_metadata = {}
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        existing_metadata = json.load(f)
                except json.JSONDecodeError:
                    # Ignore if file is corrupt
                    pass
            
            # Update metadata
            updated_metadata = {**existing_metadata, **metadata}
            
            # Save metadata
            with open(metadata_path, "w") as f:
                json.dump(updated_metadata, f, indent=2)
            
            result["success"] = True
            result["metadata"] = updated_metadata
            result["message"] = "Metadata stored locally"
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding Filecoin metadata: {e}")
            return handle_error(result, e)
    
    def filecoin_get_metadata(
        self,
        cid: str,
    ) -> Dict[str, Any]:
        """
        Get metadata for Filecoin content.
        
        Args:
            cid: CID of content to get metadata for
            
        Returns:
            Dictionary with metadata
        """
        result = create_result_dict("filecoin_get_metadata")
        result["cid"] = cid
        
        try:
            # Look for local metadata
            metadata_dir = os.path.expanduser("~/.filecoin_metadata")
            metadata_path = os.path.join(metadata_dir, f"{cid}.json")
            
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                    
                    result["success"] = True
                    result["metadata"] = metadata
                    result["source"] = "local"
                    
                    return result
                except json.JSONDecodeError:
                    # Ignore if file is corrupt
                    pass
            
            # Try Estuary API for additional metadata
            if self.estuary_api_key:
                # Try to get content info
                content_url = f"{self.estuary_api}/content/by-cid/{cid}"
                
                headers = {
                    "Authorization": f"Bearer {self.estuary_api_key}",
                    "Accept": "application/json"
                }
                
                response = requests.get(
                    content_url,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    content_info = response.json()
                    
                    if isinstance(content_info, list) and content_info:
                        # Get the first matching content
                        content_data = content_info[0]
                        
                        # Extract metadata
                        api_metadata = {
                            "name": content_data.get("name"),
                            "size": content_data.get("size"),
                            "created": content_data.get("created"),
                            "type": content_data.get("type"),
                            "estuary_id": content_data.get("id"),
                            "pin_status": content_data.get("pinStatus"),
                            "pins": content_data.get("pins"),
                            "deals": content_data.get("deals")
                        }
                        
                        result["success"] = True
                        result["metadata"] = api_metadata
                        result["source"] = "estuary_api"
                        
                        return result
            
            # No metadata found
            return handle_error(
                result,
                FilecoinContentNotFoundError("No metadata found for the given CID")
            )
            
        except Exception as e:
            logger.error(f"Error getting Filecoin metadata: {e}")
            return handle_error(result, e)
    
    def get_filecoin_stats(self) -> Dict[str, Any]:
        """
        Get Filecoin network statistics.
        
        Returns:
            Dictionary with Filecoin network statistics
        """
        result = create_result_dict("get_filecoin_stats")
        
        try:
            # Try to get stats from Filscan API
            url = f"{self.filscan_api}/v1/overview"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("status") == "success" and "data" in data:
                    stats = data["data"]
                    
                    # Format stats
                    result["success"] = True
                    result["stats"] = {
                        "current_height": stats.get("height"),
                        "total_power": stats.get("total_power"),
                        "active_miners": stats.get("active_miners"),
                        "circulating_supply": stats.get("circulating_supply"),
                        "average_block_time": stats.get("average_block_time"),
                        "network_version": stats.get("network_version")
                    }
                    
                    return result
            
            # Try to get stats from Filecoin API directly
            url = "https://api.filecoin.io/network/stats/latest"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                stats = response.json()
                
                # Format stats
                result["success"] = True
                result["stats"] = {
                    "current_height": stats.get("height"),
                    "total_power": stats.get("totalRawPowerStr"),
                    "active_miners": stats.get("minerCount"),
                    "average_block_time": stats.get("blockTime"),
                    "timestamp": stats.get("timestamp")
                }
                
                return result
            
            # No stats available
            return handle_error(
                result,
                FilecoinError("Failed to retrieve Filecoin network statistics")
            )
            
        except Exception as e:
            logger.error(f"Error getting Filecoin stats: {e}")
            return handle_error(result, e)
    
    def get_miner_info(
        self,
        miner: str,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a Filecoin miner.
        
        Args:
            miner: Miner address
            
        Returns:
            Dictionary with miner information
        """
        result = create_result_dict("get_miner_info")
        result["miner"] = miner
        
        try:
            # Try to get miner info from Filscan API
            url = f"{self.filscan_api}/v1/storageprovider/detail"
            params = {"address": miner}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("status") == "success" and "data" in data:
                    miner_data = data["data"]
                    
                    # Format miner info
                    result["success"] = True
                    result["info"] = {
                        "address": miner_data.get("address"),
                        "raw_power": miner_data.get("raw_power"),
                        "quality_power": miner_data.get("quality_power"),
                        "sector_size": miner_data.get("sector_size"),
                        "sector_count": miner_data.get("sector_count"),
                        "active_deals": miner_data.get("active_deals"),
                        "rank": miner_data.get("rank"),
                        "peer_id": miner_data.get("peer_id"),
                        "location": miner_data.get("location"),
                    }
                    
                    return result
            
            # Try alternative API
            url = f"https://api.filrep.io/api/v1/miners?search={miner}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("totalMiners") > 0 and "miners" in data:
                    miners = data["miners"]
                    for m in miners:
                        if m.get("address") == miner:
                            result["success"] = True
                            result["info"] = {
                                "address": m.get("address"),
                                "raw_power": m.get("rawPower"),
                                "quality_power": m.get("qualityPower"),
                                "rank": m.get("rank"),
                                "score": m.get("score"),
                                "min_piece_size": m.get("minPieceSize"),
                                "max_piece_size": m.get("maxPieceSize"),
                                "price": m.get("price"),
                                "verified_price": m.get("verifiedPrice"),
                                "region": m.get("region"),
                                "isoCode": m.get("isoCode"),
                            }
                            
                            return result
            
            # No miner info available
            return handle_error(
                result,
                FilecoinError(f"Failed to retrieve information for miner {miner}")
            )
            
        except Exception as e:
            logger.error(f"Error getting miner info: {e}")
            return handle_error(result, e)
    
    def recommend_miners(
        self,
        count: int = 5,
        region: Optional[str] = None,
        min_score: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Recommend miners based on performance, reputation, and availability.
        
        Args:
            count: Number of miners to recommend
            region: Filter by region
            min_score: Minimum score threshold
            
        Returns:
            Dictionary with recommended miners
        """
        result = create_result_dict("recommend_miners")
        
        try:
            # Try to get miner recommendations from FilRep API
            url = "https://api.filrep.io/api/v1/miners"
            params = {
                "size": count * 2,  # Get more to filter
                "sortBy": "score",
                "order": "desc"
            }
            
            # Add region filter if specified
            if region:
                params["region"] = region
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if "miners" in data:
                    miners = data["miners"]
                    
                    # Filter by score and sort by score
                    filtered_miners = [
                        m for m in miners
                        if m.get("score", 0) >= min_score
                    ]
                    
                    # Return top miners
                    result["success"] = True
                    result["miners"] = filtered_miners[:count]
                    result["count"] = len(result["miners"])
                    
                    return result
            
            # Try alternative approach with miner cache
            metrics = self._load_miner_metrics(force_refresh=True)
            miners = metrics.get("miners", [])
            
            # Filter and sort miners
            filtered_miners = []
            for miner in miners:
                # Apply region filter if specified
                if region and miner.get("region") != region:
                    continue
                
                # Add to filtered list
                filtered_miners.append(miner)
            
            # Return top miners
            result["success"] = True
            result["miners"] = filtered_miners[:count]
            result["count"] = len(result["miners"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error recommending miners: {e}")
            return handle_error(result, e)