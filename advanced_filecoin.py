"""
Advanced Filecoin Features for MCP Server

This module extends the basic Filecoin integration with advanced features:
- Network metrics and statistics
- Advanced storage deal management
- Miner selection and analysis
- Content replication and redundancy
- Deal lifecycle management
- Chain exploration and analysis
"""

import os
import json
import logging
import time
import uuid
import math
import random
import subprocess
import tempfile
from typing import Dict, Any, List, Optional, Set, Tuple
import threading
from datetime import datetime, timedelta
from pathlib import Path
import traceback

# Try to import filecoin_storage to extend the base implementation
try:
    from filecoin_storage import FilecoinStorage, LOTUS_AVAILABLE, LOTUS_GATEWAY_MODE
except ImportError:
    # Handle case where filecoin_storage cannot be imported
    FilecoinStorage = object
    LOTUS_AVAILABLE = False
    LOTUS_GATEWAY_MODE = False

# Configure logging
logger = logging.getLogger(__name__)

# Try importing additional dependencies
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("Requests library not available. Install with: pip install requests")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("Pandas library not available. Advanced analytics features disabled.")

# Constants for Filecoin network
FIL_PRECISION = 1e18  # 1 FIL = 10^18 attoFIL
DEFAULT_GAS_FEE_CAP = "100000000"  # Default gas fee cap in attoFIL
DEFAULT_GAS_PREMIUM = "100000"  # Default gas premium in attoFIL
DEFAULT_DEAL_DURATION = 518400  # Default deal duration (~180 days in epochs)
EPOCH_DURATION_SECONDS = 30  # Filecoin epoch duration in seconds

# List of recommended public miners
# In a real implementation, this would be dynamically updated
RECOMMENDED_MINERS = [
    {"address": "f01606", "name": "ServeTheFuture", "location": "France", "reputation": 95},
    {"address": "f0135078", "name": "FilSwan", "location": "China", "reputation": 92},
    {"address": "f022352", "name": "DekPool", "location": "Germany", "reputation": 90},
    {"address": "f01247", "name": "ScaleSphere", "location": "Singapore", "reputation": 88},
    {"address": "f02576", "name": "IPFSMain", "location": "USA", "reputation": 89}
]

class AdvancedFilecoinStorage(FilecoinStorage):
    """
    Advanced Filecoin integration with enhanced features.
    
    This class extends the basic FilecoinStorage implementation with
    advanced features for comprehensive Filecoin network integration.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the advanced Filecoin storage backend."""
        super().__init__(*args, **kwargs)
        
        # Additional initialization
        self.deal_cache = {}  # Cache for deal information
        self.deal_cache_lock = threading.Lock()  # Lock for thread safety
        self.miner_stats_cache = {}  # Cache for miner statistics
        self.network_stats_cache = {}  # Cache for network statistics
        self.cache_expiry = {}  # Expiry time for cache items
        
        # Deal lifecycle management
        self.deal_watch_thread = None
        self.watch_active = False
        
        # Create advanced mock storage directories if needed
        if self.mock_mode or self.gateway_mode:
            self._setup_advanced_mock_storage()
    
    def _setup_advanced_mock_storage(self):
        """Set up advanced mock storage directories."""
        mock_base = os.path.expanduser("~/.ipfs_kit/mock_filecoin")
        
        # Create subdirectories for different data types
        dirs = ["deals", "miners", "network", "analytics", "chain"]
        for d in dirs:
            os.makedirs(os.path.join(mock_base, d), exist_ok=True)
        
        # Create initial data files if they don't exist
        miners_file = os.path.join(mock_base, "miners", "recommended.json")
        if not os.path.exists(miners_file):
            with open(miners_file, "w") as f:
                json.dump(RECOMMENDED_MINERS, f, indent=2)
        
        # Create network stats file
        network_file = os.path.join(mock_base, "network", "stats.json")
        if not os.path.exists(network_file):
            network_stats = {
                "chain_height": 2500000 + int(time.time() / EPOCH_DURATION_SECONDS),
                "storage_power_TiB": 20145.32,
                "active_miners": 780,
                "average_price_per_GiB_per_epoch": 0.0000000002,
                "network_storage_capacity_GiB": 14500000,
                "fil_plus_storage_GiB": 12500000,
                "baseline_total": "8.25 EiB",
                "verified_deals_count": 42500,
                "last_updated": time.time()
            }
            with open(network_file, "w") as f:
                json.dump(network_stats, f, indent=2)
    
    def get_network_stats(self) -> Dict[str, Any]:
        """
        Get Filecoin network statistics.
        
        Returns:
            Dict with network statistics
        """
        # Check cache first
        if "network_stats" in self.cache_expiry and time.time() < self.cache_expiry["network_stats"]:
            return self.network_stats_cache
        
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        if self.mock_mode or self.gateway_mode:
            try:
                # Get mock network stats
                mock_base = os.path.expanduser("~/.ipfs_kit/mock_filecoin")
                network_file = os.path.join(mock_base, "network", "stats.json")
                
                if os.path.exists(network_file):
                    with open(network_file, "r") as f:
                        stats = json.load(f)
                else:
                    # Create simulated stats
                    chain_height = self._get_chain_height() or 2500000
                    stats = {
                        "chain_height": chain_height,
                        "storage_power_TiB": 20145.32,
                        "active_miners": 780,
                        "average_price_per_GiB_per_epoch": 0.0000000002,
                        "network_storage_capacity_GiB": 14500000,
                        "fil_plus_storage_GiB": 12500000,
                        "baseline_total": "8.25 EiB",
                        "verified_deals_count": 42500,
                        "last_updated": time.time()
                    }
                
                # Update with current chain height
                current_height = self._get_chain_height()
                if current_height:
                    stats["chain_height"] = current_height
                else:
                    # Simulate chain progress if we can't get real height
                    elapsed_since_update = time.time() - stats.get("last_updated", time.time())
                    epochs_passed = int(elapsed_since_update / EPOCH_DURATION_SECONDS)
                    stats["chain_height"] += epochs_passed
                    stats["last_updated"] = time.time()
                
                # Calculate derived metrics
                stats["network_storage_cost_per_year_per_GiB"] = round(
                    stats["average_price_per_GiB_per_epoch"] * 30 * 24 * 365, 8
                )
                
                # Add gas price metrics
                gas_metrics = self.get_gas_metrics()
                if gas_metrics["success"]:
                    stats.update(gas_metrics)
                
                # Update mock file
                with open(network_file, "w") as f:
                    json.dump(stats, f, indent=2)
                
                # Add success flag
                result = {
                    "success": True,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "data": stats
                }
                
                # Cache the result
                self.network_stats_cache = result
                self.cache_expiry["network_stats"] = time.time() + 300  # Cache for 5 minutes
                
                return result
            
            except Exception as e:
                logger.error(f"Error getting mock network stats: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        # For real node implementation
        try:
            # Get chain head first - most reliable indicator
            chain_head = self._make_api_request("Filecoin.ChainHead")
            if not chain_head:
                return {
                    "success": False,
                    "error": "Failed to get chain head"
                }
            
            chain_height = chain_head.get("Height", 0)
            
            # Try to get network stats via StateNetworkStats
            network_stats = self._make_api_request("Filecoin.StateNetworkStats", [chain_height])
            
            # Try to get verified registry stats
            verifreg_stats = self._make_api_request("Filecoin.StateVerifiedRegistryRootKey", [None, None])
            
            # Get all miners info
            miners_info = self._make_api_request("Filecoin.StateListMiners", [None])
            miner_count = len(miners_info) if miners_info else 0
            
            # Get gas metrics
            gas_metrics = self.get_gas_metrics()
            
            # Combine data
            stats = {
                "chain_height": chain_height,
                "active_miners": miner_count,
                "last_updated": time.time()
            }
            
            if network_stats:
                stats.update(network_stats)
            
            if verifreg_stats:
                stats["verified_registry_root"] = verifreg_stats
            
            if gas_metrics["success"]:
                stats.update(gas_metrics["data"])
            
            # Create final result
            result = {
                "success": True,
                "data": stats
            }
            
            # Cache the result
            self.network_stats_cache = result
            self.cache_expiry["network_stats"] = time.time() + 300  # Cache for 5 minutes
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Filecoin network stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_gas_metrics(self) -> Dict[str, Any]:
        """
        Get current gas metrics for the Filecoin network.
        
        Returns:
            Dict with gas price information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        if self.mock_mode or self.gateway_mode:
            # Generate mock gas metrics
            base_fee = 100000000 + random.randint(-10000000, 10000000)
            return {
                "success": True,
                "mock": self.mock_mode,
                "gateway": self.gateway_mode,
                "data": {
                    "base_fee": str(base_fee),
                    "base_fee_change_log": random.uniform(-0.05, 0.05),
                    "gas_premium_estimate": {
                        "low": str(int(base_fee * 0.5)),
                        "medium": str(int(base_fee * 1.0)),
                        "high": str(int(base_fee * 1.5))
                    },
                    "gas_fee_cap_estimate": {
                        "low": str(int(base_fee * 2)),
                        "medium": str(int(base_fee * 3)),
                        "high": str(int(base_fee * 4))
                    }
                }
            }
        
        try:
            # Get current mpool configuration for gas estimates
            mpool_config = self._make_api_request("Filecoin.MpoolGetConfig", [])
            
            # Get chain head for current base fee
            chain_head = self._make_api_request("Filecoin.ChainHead")
            
            if not chain_head:
                return {
                    "success": False,
                    "error": "Failed to get chain head"
                }
            
            # Extract base fee from chain head
            if "Blocks" in chain_head and len(chain_head["Blocks"]) > 0:
                base_fee = chain_head["Blocks"][0].get("ParentBaseFee", "100000000")
            else:
                base_fee = "100000000"  # Default if can't get from chain
            
            # Calculate gas estimates
            premium_estimates = {}
            fee_cap_estimates = {}
            
            # Low, medium, high priority estimates
            priorities = ["low", "medium", "high"]
            premium_multipliers = [0.5, 1.0, 1.5]
            fee_cap_multipliers = [2, 3, 4]
            
            for i, priority in enumerate(priorities):
                premium_estimates[priority] = str(int(float(base_fee) * premium_multipliers[i]))
                fee_cap_estimates[priority] = str(int(float(base_fee) * fee_cap_multipliers[i]))
            
            # Get base fee change over last 60 minutes
            try:
                lookback = 60  # Look back 60 epochs (30 seconds each = 30 minutes)
                current_height = chain_head.get("Height", 0)
                
                if current_height > lookback:
                    past_height = current_height - lookback
                    past_tipset = self._make_api_request("Filecoin.ChainGetTipSetByHeight", [past_height, None])
                    
                    if past_tipset and "Blocks" in past_tipset and len(past_tipset["Blocks"]) > 0:
                        past_base_fee = past_tipset["Blocks"][0].get("ParentBaseFee", base_fee)
                        if float(past_base_fee) > 0:
                            fee_change_log = math.log(float(base_fee) / float(past_base_fee))
                        else:
                            fee_change_log = 0
                    else:
                        fee_change_log = 0
                else:
                    fee_change_log = 0
            except Exception as e:
                logger.warning(f"Error calculating fee change: {e}")
                fee_change_log = 0
            
            result = {
                "success": True,
                "data": {
                    "base_fee": base_fee,
                    "base_fee_change_log": fee_change_log,
                    "gas_premium_estimate": premium_estimates,
                    "gas_fee_cap_estimate": fee_cap_estimates,
                    "mpool_config": mpool_config
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting gas metrics: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_recommended_miners(self, filter_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get a list of recommended miners based on optional filter criteria.
        
        Args:
            filter_criteria: Optional criteria to filter miners (min_reputation, region, etc.)
            
        Returns:
            Dict with recommended miners list
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        filter_criteria = filter_criteria or {}
        min_reputation = filter_criteria.get("min_reputation", 85)
        region = filter_criteria.get("region", None)
        max_price = filter_criteria.get("max_price", None)
        
        if self.mock_mode or self.gateway_mode:
            try:
                # Get recommended miners from mock storage
                mock_base = os.path.expanduser("~/.ipfs_kit/mock_filecoin")
                miners_file = os.path.join(mock_base, "miners", "recommended.json")
                
                if os.path.exists(miners_file):
                    with open(miners_file, "r") as f:
                        miners = json.load(f)
                else:
                    # Use default list
                    miners = RECOMMENDED_MINERS
                
                # Apply filters
                filtered_miners = []
                for miner in miners:
                    if miner.get("reputation", 0) < min_reputation:
                        continue
                    
                    if region and region.lower() not in miner.get("location", "").lower():
                        continue
                    
                    if max_price and miner.get("price_per_GiB_per_epoch", float("inf")) > max_price:
                        continue
                    
                    # Add simulated price if not present
                    if "price_per_GiB_per_epoch" not in miner:
                        miner["price_per_GiB_per_epoch"] = random.uniform(0.0000000001, 0.0000000003)
                    
                    filtered_miners.append(miner)
                
                return {
                    "success": True,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "miners": filtered_miners,
                    "count": len(filtered_miners),
                    "filters_applied": {
                        "min_reputation": min_reputation,
                        "region": region,
                        "max_price": max_price
                    }
                }
            
            except Exception as e:
                logger.error(f"Error getting recommended miners: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        # For real node implementation
        try:
            # This is more complex with a real node and requires additional analysis
            # For now, return a filtered version of our recommended list
            filtered_miners = []
            for miner in RECOMMENDED_MINERS:
                if miner.get("reputation", 0) < min_reputation:
                    continue
                
                if region and region.lower() not in miner.get("location", "").lower():
                    continue
                
                # Try to get miner power from chain
                miner_address = miner.get("address")
                if miner_address:
                    miner_power = self._make_api_request("Filecoin.StateMinerPower", [miner_address, None])
                    if miner_power:
                        miner["power"] = miner_power
                
                filtered_miners.append(miner)
            
            return {
                "success": True,
                "miners": filtered_miners,
                "count": len(filtered_miners),
                "filters_applied": {
                    "min_reputation": min_reputation,
                    "region": region,
                    "max_price": max_price
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting recommended miners: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def analyze_miner(self, miner_address: str) -> Dict[str, Any]:
        """
        Perform detailed analysis of a specific miner.
        
        Args:
            miner_address: Filecoin address of the miner to analyze
            
        Returns:
            Dict with detailed miner analysis
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        if self.mock_mode or self.gateway_mode:
            try:
                # Check if we have this miner in our recommended list
                mock_base = os.path.expanduser("~/.ipfs_kit/mock_filecoin")
                miners_file = os.path.join(mock_base, "miners", "recommended.json")
                
                miner_info = None
                if os.path.exists(miners_file):
                    with open(miners_file, "r") as f:
                        miners = json.load(f)
                    
                    for miner in miners:
                        if miner.get("address") == miner_address:
                            miner_info = miner
                            break
                
                if not miner_info:
                    # Create mock info for this miner
                    miner_info = {
                        "address": miner_address,
                        "name": f"Miner {miner_address}",
                        "location": random.choice(["USA", "Europe", "Asia", "Unknown"]),
                        "reputation": random.randint(70, 99),
                        "price_per_GiB_per_epoch": random.uniform(0.0000000001, 0.0000000003)
                    }
                
                # Generate detailed mock analysis
                sector_size = 32 * (1024**3)  # 32 GiB in bytes
                analysis = {
                    "miner_info": miner_info,
                    "storage_power": f"{random.randint(1, 1000)} TiB",
                    "raw_power": random.randint(1, 10000) * sector_size,
                    "quality_power": random.randint(1, 10000) * sector_size,
                    "sector_size": sector_size,
                    "active_sectors": random.randint(100, 10000),
                    "faulty_sectors": random.randint(0, 10),
                    "recovering_sectors": random.randint(0, 5),
                    "deal_success_rate": random.uniform(0.95, 0.999),
                    "avg_deal_completion_time": f"{random.randint(1, 5)} days",
                    "peer_id": f"12D3KooW{uuid.uuid4().hex[:15]}",
                    "multiaddresses": [
                        f"/ip4/172.65.0.{random.randint(1, 255)}/tcp/1234",
                        f"/ip4/192.168.1.{random.randint(1, 255)}/tcp/1234"
                    ],
                    "performance_score": random.randint(85, 100),
                    "average_block_rewards_24h": random.uniform(0.1, 5.0),
                    "last_seen_active": int(time.time() - random.randint(0, 86400)),
                    "deal_pricing": {
                        "published_verified": round(miner_info.get("price_per_GiB_per_epoch", 0.0000000001), 16),
                        "published_regular": round(miner_info.get("price_per_GiB_per_epoch", 0.0000000002) * 2, 16),
                        "calculated_cost_per_year": round(
                            miner_info.get("price_per_GiB_per_epoch", 0.0000000002) * 2880 * 365, 8
                        )
                    }
                }
                
                # Add custom analysis data
                storage_deals_file = os.path.join(mock_base, "miners", f"{miner_address}_deals.json")
                if os.path.exists(storage_deals_file):
                    with open(storage_deals_file, "r") as f:
                        deals_data = json.load(f)
                    analysis["recent_deals"] = deals_data.get("recent_deals", [])
                    analysis["active_deals_count"] = deals_data.get("active_deals_count", random.randint(100, 1000))
                else:
                    analysis["recent_deals"] = []
                    analysis["active_deals_count"] = random.randint(100, 1000)
                
                return {
                    "success": True,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "analysis": analysis
                }
            
            except Exception as e:
                logger.error(f"Error analyzing miner: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        # For real node implementation
        try:
            # Get miner power
            miner_power = self._make_api_request("Filecoin.StateMinerPower", [miner_address, None])
            
            # Get miner info
            miner_info = self._make_api_request("Filecoin.StateMinerInfo", [miner_address, None])
            
            # Get sector stats
            miner_sectors = self._make_api_request("Filecoin.StateMinerSectors", [miner_address, None, None, False])
            
            # Get fault stats
            miner_faults = self._make_api_request("Filecoin.StateMinerFaults", [miner_address, None])
            
            # Get recoveries
            miner_recoveries = self._make_api_request("Filecoin.StateMinerRecoveries", [miner_address, None])
            
            # Combine all data
            analysis = {
                "address": miner_address,
                "power": miner_power,
                "info": miner_info,
                "sectors_count": len(miner_sectors) if miner_sectors else 0,
                "faults_count": len(miner_faults) if miner_faults else 0,
                "recoveries_count": len(miner_recoveries) if miner_recoveries else 0
            }
            
            # Try to get peer ID info if available
            if miner_info and "PeerId" in miner_info:
                peer_id = miner_info["PeerId"]
                if peer_id:
                    # Try to get node info
                    node_info = self._make_api_request("Filecoin.NetFindPeer", [peer_id])
                    if node_info:
                        analysis["node_info"] = node_info
            
            # Calculate derived metrics
            if miner_power:
                raw_power = int(miner_power.get("MinerPower", {}).get("RawBytePower", "0"))
                quality_power = int(miner_power.get("MinerPower", {}).get("QualityAdjPower", "0"))
                
                analysis["raw_power_bytes"] = raw_power
                analysis["quality_power_bytes"] = quality_power
                
                # Calculate in more human-readable formats
                raw_power_tib = raw_power / (1024**4)  # TiB
                analysis["raw_power_tib"] = round(raw_power_tib, 3)
                
                # Calculate percentage of network power
                if miner_power.get("TotalPower", {}).get("RawBytePower", "0") != "0":
                    network_power = int(miner_power.get("TotalPower", {}).get("RawBytePower", "0"))
                    power_percentage = (raw_power / network_power) * 100
                    analysis["network_power_percentage"] = round(power_percentage, 6)
            
            return {
                "success": True,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"Error analyzing miner: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_redundant_storage(self, cid: str, miner_count: int = 3, 
                               verified_deal: bool = False, deal_duration: int = DEFAULT_DEAL_DURATION) -> Dict[str, Any]:
        """
        Store IPFS content with multiple miners for redundancy.
        
        Args:
            cid: Content ID to store
            miner_count: Number of different miners to use
            verified_deal: Whether to make a verified storage deal
            deal_duration: Deal duration in epochs
            
        Returns:
            Dict with multiple storage deals information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # First get recommended miners
        miners_result = self.get_recommended_miners({"min_reputation": 90})
        
        if not miners_result.get("success", False):
            return {
                "success": False,
                "error": "Failed to get recommended miners"
            }
        
        recommended_miners = miners_result.get("miners", [])
        if len(recommended_miners) < miner_count:
            return {
                "success": False,
                "error": f"Not enough recommended miners: found {len(recommended_miners)}, needed {miner_count}"
            }
        
        # Choose a subset of recommended miners
        selected_miners = random.sample(recommended_miners, miner_count)
        
        # Create storage deals with each miner
        deals = []
        failed_deals = []
        
        for miner in selected_miners:
            miner_address = miner.get("address")
            if not miner_address:
                failed_deals.append({
                    "miner": miner,
                    "error": "Missing miner address"
                })
                continue
            
            # Make storage deal
            deal_result = self.from_ipfs(cid, miner_address, deal_duration)
            
            if deal_result.get("success", False):
                deal_result["miner_info"] = miner
                deals.append(deal_result)
            else:
                failed_deals.append({
                    "miner": miner,
                    "error": deal_result.get("error", "Unknown error")
                })
        
        # Return combined results
        return {
            "success": len(deals) > 0,
            "deals": deals,
            "failed_deals": failed_deals,
            "total_deals": len(deals),
            "failed_count": len(failed_deals),
            "requested_count": miner_count,
            "redundancy_factor": len(deals),
            "cid": cid
        }
    
    def monitor_deal_status(self, deal_id: str, callback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Start monitoring a storage deal's status.
        
        Args:
            deal_id: Deal ID to monitor
            callback_url: Optional URL to call with status updates
            
        Returns:
            Dict with monitoring status
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # Check if deal exists
        deal_status = self.check_deal_status(deal_id)
        
        if not deal_status.get("success", False):
            return {
                "success": False,
                "error": f"Deal {deal_id} not found or invalid"
            }
        
        # Register for monitoring
        with self.deal_cache_lock:
            # Store in deal cache
            self.deal_cache[deal_id] = {
                "status": deal_status,
                "callback_url": callback_url,
                "monitoring_start": time.time(),
                "update_interval": 3600,  # Update every hour by default
                "last_updated": time.time(),
                "update_count": 0
            }
        
        # Start the monitoring thread if not already running
        if not self.watch_active or not self.deal_watch_thread or not self.deal_watch_thread.is_alive():
            self.watch_active = True
            self.deal_watch_thread = threading.Thread(target=self._deal_monitoring_thread, daemon=True)
            self.deal_watch_thread.start()
        
        return {
            "success": True,
            "message": f"Started monitoring deal {deal_id}",
            "deal_id": deal_id,
            "callback_url": callback_url,
            "current_status": deal_status.get("status", "unknown")
        }
    
    def _deal_monitoring_thread(self):
        """Background thread to monitor deal status."""
        logger.info("Deal monitoring thread started")
        
        while self.watch_active:
            try:
                deals_to_update = []
                
                # Find deals that need updating
                current_time = time.time()
                with self.deal_cache_lock:
                    for deal_id, info in self.deal_cache.items():
                        if current_time - info.get("last_updated", 0) > info.get("update_interval", 3600):
                            deals_to_update.append(deal_id)
                
                # Update each deal
                for deal_id in deals_to_update:
                    try:
                        # Check current status
                        status = self.check_deal_status(deal_id)
                        
                        # Update cache
                        with self.deal_cache_lock:
                            if deal_id in self.deal_cache:
                                self.deal_cache[deal_id]["status"] = status
                                self.deal_cache[deal_id]["last_updated"] = current_time
                                self.deal_cache[deal_id]["update_count"] += 1
                                
                                # Call callback if provided
                                callback_url = self.deal_cache[deal_id].get("callback_url")
                                if callback_url and REQUESTS_AVAILABLE:
                                    try:
                                        requests.post(
                                            callback_url,
                                            json={
                                                "deal_id": deal_id,
                                                "status": status,
                                                "timestamp": current_time
                                            },
                                            timeout=10
                                        )
                                    except Exception as e:
                                        logger.warning(f"Error calling callback URL for deal {deal_id}: {e}")
                    
                    except Exception as e:
                        logger.warning(f"Error updating deal {deal_id}: {e}")
                
                # Sleep for a while
                time.sleep(60)  # Check every minute
            
            except Exception as e:
                logger.error(f"Error in deal monitoring thread: {e}")
                time.sleep(300)  # On error, wait 5 minutes before retrying
    
    def estimate_storage_cost(self, size_bytes: int, duration_days: int = 180, 
                            verified_deal: bool = False) -> Dict[str, Any]:
        """
        Estimate cost to store data on Filecoin.
        
        Args:
            size_bytes: Size of data in bytes
            duration_days: Duration in days
            verified_deal: Whether to use verified storage deals
            
        Returns:
            Dict with cost estimation
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # Get network stats for baseline pricing
        network_stats = self.get_network_stats()
        
        if not network_stats.get("success", False):
            return {
                "success": False,
                "error": "Failed to get network stats for pricing"
            }
        
        stats_data = network_stats.get("data", {})
        
        # Calculate storage parameters
        size_gib = size_bytes / (1024**3)
        duration_epochs = int((duration_days * 24 * 60 * 60) / EPOCH_DURATION_SECONDS)
        
        # Calculate baseline price
        avg_price_per_gib_per_epoch = stats_data.get(
            "average_price_per_GiB_per_epoch", 0.0000000002
        )
        
        # Apply discount for verified deals
        if verified_deal:
            price_multiplier = 0.5  # 50% discount for verified deals
        else:
            price_multiplier = 1.0
        
        # Calculate storage price
        storage_cost_attoFil = size_gib * avg_price_per_gib_per_epoch * duration_epochs * price_multiplier * FIL_PRECISION
        storage_cost_fil = storage_cost_attoFil / FIL_PRECISION
        
        # Estimate gas costs
        publish_deal_gas = 0.05  # FIL per deal publication
        
        # Calculate total cost
        total_cost_fil = storage_cost_fil + publish_deal_gas
        
        # Get recommended miners for this deal
        miners_result = self.get_recommended_miners()
        recommended_miners = miners_result.get("miners", []) if miners_result.get("success", False) else []
        
        # Calculate price range across miners
        pricing_range = {"min": float("inf"), "max": 0, "avg": 0}
        if recommended_miners:
            prices = []
            for miner in recommended_miners:
                price = miner.get("price_per_GiB_per_epoch", avg_price_per_gib_per_epoch)
                prices.append(price)
                
                miner_cost = size_gib * price * duration_epochs * price_multiplier * FIL_PRECISION / FIL_PRECISION
                
                pricing_range["min"] = min(pricing_range["min"], miner_cost)
                pricing_range["max"] = max(pricing_range["max"], miner_cost)
            
            if prices:
                avg_price = sum(prices) / len(prices)
                pricing_range["avg"] = size_gib * avg_price * duration_epochs * price_multiplier * FIL_PRECISION / FIL_PRECISION
        
        if pricing_range["min"] == float("inf"):
            pricing_range["min"] = storage_cost_fil
        
        # Return estimation result
        return {
            "success": True,
            "mock": self.mock_mode,
            "gateway": self.gateway_mode,
            "estimate": {
                "size_bytes": size_bytes,
                "size_gib": round(size_gib, 4),
                "duration_days": duration_days,
                "duration_epochs": duration_epochs,
                "verified_deal": verified_deal,
                "avg_price_per_gib_per_epoch": avg_price_per_gib_per_epoch,
                "storage_cost_fil": round(storage_cost_fil, 8),
                "gas_cost_fil": publish_deal_gas,
                "total_cost_fil": round(total_cost_fil, 8),
                "price_range_fil": {
                    "min": round(pricing_range["min"], 8),
                    "max": round(pricing_range["max"], 8),
                    "avg": round(pricing_range["avg"], 8)
                },
                "usd_per_fil": 3.50,  # Example value, would be dynamically fetched in production
                "total_cost_usd": round(total_cost_fil * 3.50, 2)
            }
        }
    
    def _get_chain_height(self) -> Optional[int]:
        """Helper method to get current chain height."""
        try:
            if self.mock_mode or self.gateway_mode:
                # Try to get from mock storage first
                mock_base = os.path.expanduser("~/.ipfs_kit/mock_filecoin")
                network_file = os.path.join(mock_base, "network", "stats.json")
                
                if os.path.exists(network_file):
                    with open(network_file, "r") as f:
                        stats = json.load(f)
                    
                    if "chain_height" in stats:
                        return stats["chain_height"]
            
            # Try to get real chain height
            chain_head = self._make_api_request("Filecoin.ChainHead")
            if chain_head and "Height" in chain_head:
                return chain_head["Height"]
            
            return None
        
        except Exception as e:
            logger.warning(f"Error getting chain height: {e}")
            return None

    def explore_chain_block(self, height: Optional[int] = None, cid: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a specific Filecoin blockchain block.
        
        Args:
            height: Optional block height, if None uses the latest block
            cid: Optional block CID, overrides height if provided
            
        Returns:
            Dict with block information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        if self.mock_mode or self.gateway_mode:
            try:
                # Get chain height from mock storage
                current_height = self._get_chain_height()
                if not current_height:
                    current_height = 2500000 + int(time.time() / EPOCH_DURATION_SECONDS)
                
                # If no height provided, use current height
                if height is None and cid is None:
                    height = current_height
                
                # Generate mock block data
                block_timestamp = int(time.time() - ((current_height - height) * EPOCH_DURATION_SECONDS)) if height else int(time.time())
                
                if cid:
                    block_cid = cid
                else:
                    block_cid = f"bafy2bzace{uuid.uuid4().hex[:16]}{uuid.uuid4().hex[:16]}"
                
                mock_block = {
                    "Height": height if height else current_height,
                    "Timestamp": block_timestamp,
                    "Cid": block_cid,
                    "Miner": f"f0{random.randint(1000, 100000)}",
                    "ParentCid": f"bafy2bzace{uuid.uuid4().hex[:32]}",
                    "Messages": [
                        f"bafy2bzace{uuid.uuid4().hex[:32]}" for _ in range(random.randint(5, 20))
                    ],
                    "ParentWeight": str(random.randint(1000000000000, 9000000000000)),
                    "BlockSize": random.randint(5000, 20000),
                    "ParentStateRoot": f"bafy2bzace{uuid.uuid4().hex[:32]}",
                    "ParentMessageReceipts": f"bafy2bzace{uuid.uuid4().hex[:32]}"
                }
                
                return {
                    "success": True,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "block": mock_block
                }
            
            except Exception as e:
                logger.error(f"Error exploring chain block: {e}")
                return {
                    "success": False,
                    "mock": self.mock_mode,
                    "gateway": self.gateway_mode,
                    "error": str(e)
                }
        
        # For real node implementation
        try:
            if cid:
                # Get block by CID
                block = self._make_api_request("Filecoin.ChainGetBlock", [{"/"  : cid}])
            elif height is not None:
                # Get tipset by height
                tipset = self._make_api_request("Filecoin.ChainGetTipSetByHeight", [height, None])
                
                if not tipset or "Blocks" not in tipset or not tipset["Blocks"]:
                    return {
                        "success": False,
                        "error": f"No blocks found at height {height}"
                    }
                
                # Get the first block in the tipset
                block = tipset["Blocks"][0]
            else:
                # Get current head
                chain_head = self._make_api_request("Filecoin.ChainHead")
                
                if not chain_head or "Blocks" not in chain_head or not chain_head["Blocks"]:
                    return {
                        "success": False,
                        "error": "Failed to get chain head"
                    }
                
                # Get the first block in the head tipset
                block = chain_head["Blocks"][0]
            
            if not block:
                return {
                    "success": False,
                    "error": "Failed to get block"
                }
            
            return {
                "success": True,
                "block": block
            }
            
        except Exception as e:
            logger.error(f"Error exploring chain block: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_content_health(self, cid: str) -> Dict[str, Any]:
        """
        Check the health of content stored on Filecoin.
        
        Args:
            cid: Content ID to check
            
        Returns:
            Dict with content health information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Filecoin backend is in simulation mode"
            }
        
        # Find all deals for this CID
        deals = self._find_deals_for_cid(cid)
        
        if not deals:
            return {
                "success": False,
                "error": f"No deals found for CID {cid}"
            }
        
        # Check status of each deal
        active_deals = []
        expired_deals = []
        failing_deals = []
        
        current_time = time.time()
        for deal in deals:
            deal_id = deal.get("deal_id")
            if not deal_id:
                continue
            
            status = self.check_deal_status(deal_id)
            
            if not status.get("success", False):
                failing_deals.append({
                    "deal_id": deal_id,
                    "error": status.get("error", "Unknown error")
                })
                continue
            
            deal_status = status.get("status", "unknown")
            
            # Check if deal is expired
            if "created_at" in deal and "duration" in deal:
                created_at = deal["created_at"]
                duration_seconds = deal["duration"] * EPOCH_DURATION_SECONDS
                expiry_time = created_at + duration_seconds
                
                if current_time > expiry_time:
                    expired_deals.append({
                        "deal_id": deal_id,
                        "status": deal_status,
                        "created_at": created_at,
                        "expired_at": expiry_time,
                        "miner": deal.get("miner")
                    })
                    continue
            
            # Deal is still active
            active_deals.append({
                "deal_id": deal_id,
                "status": deal_status,
                "miner": deal.get("miner")
            })
        
        # Calculate health metrics
        total_deals = len(active_deals) + len(expired_deals) + len(failing_deals)
        redundancy_level = len(active_deals)
        
        health_score = 0
        if total_deals > 0:
            health_score = (len(active_deals) / total_deals) * 100
        
        health_status = "Healthy"
        if health_score < 33:
            health_status = "Critical"
        elif health_score < 66:
            health_status = "Warning"
        
        return {
            "success": True,
            "mock": self.mock_mode,
            "gateway": self.gateway_mode,
            "health": {
                "cid": cid,
                "active_deals": active_deals,
                "expired_deals": expired_deals,
                "failing_deals": failing_deals,
                "total_deals": total_deals,
                "redundancy_level": redundancy_level,
                "health_score": round(health_score, 2),
                "health_status": health_status,
                "last_checked": current_time
            }
        }
    
    def _find_deals_for_cid(self, cid: str) -> List[Dict[str, Any]]:
        """Helper method to find all deals for a given CID."""
        if self.mock_mode or self.gateway_mode:
            # Check mock storage
            mock_base = os.path.expanduser("~/.ipfs_kit/mock_filecoin")
            deals_dir = os.path.join(mock_base, "deals")
            
            deals = []
            if os.path.exists(deals_dir):
                for filename in os.listdir(deals_dir):
                    if filename.endswith(".json"):
                        try:
                            deal_path = os.path.join(deals_dir, filename)
                            with open(deal_path, "r") as f:
                                deal = json.load(f)
                            
                            if deal.get("cid") == cid:
                                deals.append(deal)
                        except Exception:
                            pass
            
            return deals
        
        # For real node, we would query the lotus client deal list
        # This is a simplified implementation
        try:
            # Get list of all deals
            all_deals = self._make_api_request("Filecoin.ClientListDeals", [])
            
            # Filter deals for the CID
            matching_deals = []
            if all_deals:
                for deal in all_deals:
                    if cid in json.dumps(deal):  # Simple check, would be more precise in production
                        matching_deals.append(deal)
            
            return matching_deals
        
        except Exception as e:
            logger.warning(f"Error finding deals for CID {cid}: {e}")
            return []