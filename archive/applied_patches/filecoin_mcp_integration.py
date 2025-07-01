"""
Advanced Filecoin Integration for MCP Server

This module provides API endpoints that integrate the advanced Filecoin features
with the MCP server, exposing the following capabilities:
- Network Analytics & Metrics
- Intelligent Miner Selection & Management
- Enhanced Storage Operations
- Content Health & Reliability
- Blockchain Integration

All functionality is accessible through the /api/v0/filecoin/advanced/* API endpoints.
"""

import json
import logging
import os
import time
from typing import Dict, Any, List, Optional, Union

# Import the advanced Filecoin implementation
try:
    from advanced_filecoin import AdvancedFilecoinStorage
    ADVANCED_FILECOIN_AVAILABLE = True
except ImportError:
    ADVANCED_FILECOIN_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)


class FilecoinMCPIntegration:
    """
    Integration of Advanced Filecoin features with MCP Server.
    
    This class provides API handlers that expose advanced Filecoin functionality
    through the MCP server REST API.
    """
    
    def __init__(self, resources=None, config=None):
        """
        Initialize the Filecoin MCP integration.
        
        Args:
            resources: Shared resources for service initialization
            config: Configuration options
        """
        self.resources = resources or {}
        self.config = config or {}
        
        # Initialize advanced Filecoin client
        self.filecoin_client = None
        if ADVANCED_FILECOIN_AVAILABLE:
            try:
                logger.info("Initializing Advanced Filecoin integration")
                self.filecoin_client = AdvancedFilecoinStorage(resources=resources, **self.config)
                logger.info("Advanced Filecoin integration initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Advanced Filecoin integration: {e}")
        else:
            logger.warning("Advanced Filecoin integration not available (missing dependencies)")
        
        # Setup fallback mode if integration not available
        self.mock_mode = not ADVANCED_FILECOIN_AVAILABLE or self.config.get("mock_mode", False)
        if self.mock_mode:
            logger.info("Advanced Filecoin integration running in mock mode")
    
    def handle_request(self, path: str, method: str, params: dict) -> Dict[str, Any]:
        """
        Handle API requests for the Filecoin advanced endpoints.
        
        Args:
            path: API endpoint path (e.g., /network/stats)
            method: HTTP method (e.g., GET, POST)
            params: Request parameters
            
        Returns:
            API response object
        """
        # Check if advanced Filecoin is available
        if not ADVANCED_FILECOIN_AVAILABLE and not self.mock_mode:
            return {
                "success": False,
                "error": "Advanced Filecoin integration not available",
                "error_type": "integration_unavailable"
            }
        
        # Network Analytics & Metrics endpoints
        if path.startswith("/network/"):
            return self._handle_network_endpoints(path, method, params)
        
        # Miner Selection & Management endpoints
        elif path.startswith("/miners/"):
            return self._handle_miner_endpoints(path, method, params)
        
        # Storage Operations endpoints
        elif path.startswith("/storage/"):
            return self._handle_storage_endpoints(path, method, params)
        
        # Content Health & Reliability endpoints
        elif path.startswith("/health/"):
            return self._handle_health_endpoints(path, method, params)
        
        # Blockchain Integration endpoints
        elif path.startswith("/chain/"):
            return self._handle_chain_endpoints(path, method, params)
        
        # Unknown endpoint
        return {
            "success": False,
            "error": f"Unknown endpoint: {path}",
            "error_type": "invalid_endpoint"
        }
    
    def _handle_network_endpoints(self, path: str, method: str, params: dict) -> Dict[str, Any]:
        """Handle Network Analytics & Metrics endpoints."""
        if not self.filecoin_client and not self.mock_mode:
            return self._client_unavailable_response()
        
        # Network statistics
        if path == "/network/stats" and method == "GET":
            if self.mock_mode:
                return self._mock_network_stats()
            return self.filecoin_client.get_network_stats()
        
        # Gas metrics and price estimates
        elif path == "/network/gas" and method == "GET":
            if self.mock_mode:
                return self._mock_gas_metrics()
            return self.filecoin_client.get_gas_metrics()
        
        # Network deal statistics
        elif path == "/network/deals" and method == "GET":
            if self.mock_mode:
                return self._mock_deal_stats()
            
            # This would be implemented in the AdvancedFilecoinStorage class
            if hasattr(self.filecoin_client, "get_network_deal_stats"):
                return self.filecoin_client.get_network_deal_stats()
            else:
                return {"success": False, "error": "Method not implemented", "mock": self.mock_mode}
        
        # Unknown network endpoint
        return {"success": False, "error": f"Unknown network endpoint: {path}", "mock": self.mock_mode}
    
    def _handle_miner_endpoints(self, path: str, method: str, params: dict) -> Dict[str, Any]:
        """Handle Miner Selection & Management endpoints."""
        if not self.filecoin_client and not self.mock_mode:
            return self._client_unavailable_response()
        
        # Recommended miners
        if path == "/miners/recommended" and method == "GET":
            # Parse filter criteria from params
            filter_criteria = {}
            if "min_reputation" in params:
                filter_criteria["min_reputation"] = int(params["min_reputation"])
            if "region" in params:
                filter_criteria["region"] = params["region"]
            if "max_price" in params:
                filter_criteria["max_price"] = float(params["max_price"])
            
            if self.mock_mode:
                return self._mock_recommended_miners(filter_criteria)
            return self.filecoin_client.get_recommended_miners(filter_criteria)
        
        # Detailed miner analysis
        elif path == "/miners/analyze" and method == "GET":
            if "miner" not in params:
                return {"success": False, "error": "Missing required parameter: miner", "mock": self.mock_mode}
            
            miner_address = params["miner"]
            if self.mock_mode:
                return self._mock_miner_analysis(miner_address)
            return self.filecoin_client.analyze_miner(miner_address)
        
        # Compare miners
        elif path == "/miners/compare" and method == "POST":
            if "miners" not in params:
                return {"success": False, "error": "Missing required parameter: miners", "mock": self.mock_mode}
            
            miners = params["miners"]
            if not isinstance(miners, list):
                return {"success": False, "error": "Miners parameter must be a list", "mock": self.mock_mode}
            
            if self.mock_mode:
                return self._mock_miner_comparison(miners)
            
            # This would be implemented in the AdvancedFilecoinStorage class
            if hasattr(self.filecoin_client, "compare_miners"):
                return self.filecoin_client.compare_miners(miners)
            else:
                return {"success": False, "error": "Method not implemented", "mock": self.mock_mode}
        
        # Unknown miner endpoint
        return {"success": False, "error": f"Unknown miner endpoint: {path}", "mock": self.mock_mode}
    
    def _handle_storage_endpoints(self, path: str, method: str, params: dict) -> Dict[str, Any]:
        """Handle Storage Operations endpoints."""
        if not self.filecoin_client and not self.mock_mode:
            return self._client_unavailable_response()
        
        # Estimate storage cost
        if path == "/storage/estimate" and method == "GET":
            if "size_bytes" not in params:
                return {"success": False, "error": "Missing required parameter: size_bytes", "mock": self.mock_mode}
            
            size_bytes = int(params["size_bytes"])
            duration_days = int(params.get("duration_days", 180))
            verified_deal = params.get("verified_deal", "false").lower() == "true"
            
            if self.mock_mode:
                return self._mock_storage_estimate(size_bytes, duration_days, verified_deal)
            return self.filecoin_client.estimate_storage_cost(size_bytes, duration_days, verified_deal)
        
        # Create redundant storage
        elif path == "/storage/redundant" and method == "POST":
            if "cid" not in params:
                return {"success": False, "error": "Missing required parameter: cid", "mock": self.mock_mode}
            
            cid = params["cid"]
            miner_count = int(params.get("miner_count", 3))
            verified_deal = params.get("verified_deal", "false").lower() == "true"
            deal_duration = int(params.get("deal_duration", 518400))  # Default ~180 days
            
            if self.mock_mode:
                return self._mock_redundant_storage(cid, miner_count, verified_deal, deal_duration)
            return self.filecoin_client.create_redundant_storage(cid, miner_count, verified_deal, deal_duration)
        
        # Import from IPFS
        elif path == "/storage/from_ipfs" and method == "POST":
            if "cid" not in params:
                return {"success": False, "error": "Missing required parameter: cid", "mock": self.mock_mode}
            
            cid = params["cid"]
            miner = params.get("miner")
            deal_duration = int(params.get("deal_duration", 518400))
            verified_deal = params.get("verified_deal", "false").lower() == "true"
            
            if self.mock_mode:
                return self._mock_from_ipfs(cid, miner, deal_duration, verified_deal)
            return self.filecoin_client.from_ipfs(cid, miner, deal_duration)
        
        # Unknown storage endpoint
        return {"success": False, "error": f"Unknown storage endpoint: {path}", "mock": self.mock_mode}
    
    def _handle_health_endpoints(self, path: str, method: str, params: dict) -> Dict[str, Any]:
        """Handle Content Health & Reliability endpoints."""
        if not self.filecoin_client and not self.mock_mode:
            return self._client_unavailable_response()
        
        # Check content health
        if path == "/health/check" and method == "GET":
            if "cid" not in params:
                return {"success": False, "error": "Missing required parameter: cid", "mock": self.mock_mode}
            
            cid = params["cid"]
            if self.mock_mode:
                return self._mock_content_health(cid)
            return self.filecoin_client.get_content_health(cid)
        
        # Monitor deal status
        elif path == "/health/monitor_deal" and method == "POST":
            if "deal_id" not in params:
                return {"success": False, "error": "Missing required parameter: deal_id", "mock": self.mock_mode}
            
            deal_id = params["deal_id"]
            callback_url = params.get("callback_url")
            
            if self.mock_mode:
                return self._mock_monitor_deal(deal_id, callback_url)
            return self.filecoin_client.monitor_deal_status(deal_id, callback_url)
        
        # Check deal status
        elif path == "/health/deal_status" and method == "GET":
            if "deal_id" not in params:
                return {"success": False, "error": "Missing required parameter: deal_id", "mock": self.mock_mode}
            
            deal_id = params["deal_id"]
            if self.mock_mode:
                return self._mock_deal_status(deal_id)
            return self.filecoin_client.check_deal_status(deal_id)
        
        # Unknown health endpoint
        return {"success": False, "error": f"Unknown health endpoint: {path}", "mock": self.mock_mode}
    
    def _handle_chain_endpoints(self, path: str, method: str, params: dict) -> Dict[str, Any]:
        """Handle Blockchain Integration endpoints."""
        if not self.filecoin_client and not self.mock_mode:
            return self._client_unavailable_response()
        
        # Explore chain block
        if path == "/chain/block" and method == "GET":
            height = params.get("height")
            cid = params.get("cid")
            
            if height is not None:
                height = int(height)
            
            if self.mock_mode:
                return self._mock_chain_block(height, cid)
            return self.filecoin_client.explore_chain_block(height, cid)
        
        # Get chain head
        elif path == "/chain/head" and method == "GET":
            if self.mock_mode:
                return self._mock_chain_head()
            
            # This would be implemented in the AdvancedFilecoinStorage class
            if hasattr(self.filecoin_client, "get_chain_head"):
                return self.filecoin_client.get_chain_head()
            else:
                return {"success": False, "error": "Method not implemented", "mock": self.mock_mode}
        
        # Track transaction
        elif path == "/chain/transaction" and method == "GET":
            if "cid" not in params:
                return {"success": False, "error": "Missing required parameter: cid", "mock": self.mock_mode}
            
            cid = params["cid"]
            if self.mock_mode:
                return self._mock_transaction(cid)
            
            # This would be implemented in the AdvancedFilecoinStorage class
            if hasattr(self.filecoin_client, "track_transaction"):
                return self.filecoin_client.track_transaction(cid)
            else:
                return {"success": False, "error": "Method not implemented", "mock": self.mock_mode}
        
        # Unknown chain endpoint
        return {"success": False, "error": f"Unknown chain endpoint: {path}", "mock": self.mock_mode}
    
    def _client_unavailable_response(self) -> Dict[str, Any]:
        """Generate response for when the Filecoin client is unavailable."""
        return {
            "success": False,
            "error": "Advanced Filecoin client unavailable",
            "error_type": "client_unavailable"
        }
    
    # Mock implementations for when the real client is not available
    
    def _mock_network_stats(self) -> Dict[str, Any]:
        """Generate mock network statistics."""
        current_time = time.time()
        epoch_time = 30  # seconds per epoch
        
        return {
            "success": True,
            "mock": True,
            "data": {
                "chain_height": 2500000 + int(current_time / epoch_time) % 1000,
                "storage_power_TiB": 20145.32,
                "active_miners": 780,
                "average_price_per_GiB_per_epoch": 0.0000000002,
                "network_storage_capacity_GiB": 14500000,
                "fil_plus_storage_GiB": 12500000,
                "baseline_total": "8.25 EiB",
                "verified_deals_count": 42500,
                "last_updated": current_time,
                "network_storage_cost_per_year_per_GiB": 0.00000576,
                "base_fee": "100000000",
                "base_fee_change_log": 0.01
            }
        }
    
    def _mock_gas_metrics(self) -> Dict[str, Any]:
        """Generate mock gas metrics."""
        base_fee = 100000000
        
        return {
            "success": True,
            "mock": True,
            "data": {
                "base_fee": str(base_fee),
                "base_fee_change_log": 0.01,
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
    
    def _mock_deal_stats(self) -> Dict[str, Any]:
        """Generate mock deal statistics."""
        return {
            "success": True,
            "mock": True,
            "data": {
                "total_deals": 152385,
                "active_deals": 145932,
                "verified_deals": 127845,
                "regular_deals": 24540,
                "total_data_size_GiB": 15483284,
                "average_deal_size_GiB": 106.18,
                "daily_new_deals": 487,
                "daily_data_onboarding_GiB": 51712
            }
        }
    
    def _mock_recommended_miners(self, filter_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock recommended miners list."""
        min_reputation = filter_criteria.get("min_reputation", 85)
        region = filter_criteria.get("region")
        
        # Define base list
        all_miners = [
            {"address": "f01606", "name": "ServeTheFuture", "location": "France", "reputation": 95, "price_per_GiB_per_epoch": 0.0000000001},
            {"address": "f0135078", "name": "FilSwan", "location": "China", "reputation": 92, "price_per_GiB_per_epoch": 0.0000000002},
            {"address": "f022352", "name": "DekPool", "location": "Germany", "reputation": 90, "price_per_GiB_per_epoch": 0.00000000015},
            {"address": "f01247", "name": "ScaleSphere", "location": "Singapore", "reputation": 88, "price_per_GiB_per_epoch": 0.00000000018},
            {"address": "f02576", "name": "IPFSMain", "location": "USA", "reputation": 89, "price_per_GiB_per_epoch": 0.0000000002}
        ]
        
        # Apply filters
        filtered_miners = []
        for miner in all_miners:
            if miner["reputation"] < min_reputation:
                continue
            
            if region and region.lower() not in miner["location"].lower():
                continue
            
            filtered_miners.append(miner)
        
        return {
            "success": True,
            "mock": True,
            "miners": filtered_miners,
            "count": len(filtered_miners),
            "filters_applied": filter_criteria
        }
    
    def _mock_miner_analysis(self, miner_address: str) -> Dict[str, Any]:
        """Generate mock miner analysis."""
        import random
        import uuid
        
        sector_size = 32 * (1024**3)  # 32 GiB in bytes
        analysis = {
            "miner_info": {
                "address": miner_address,
                "name": f"Miner {miner_address}",
                "location": random.choice(["USA", "Europe", "Asia", "Unknown"]),
                "reputation": random.randint(70, 99),
                "price_per_GiB_per_epoch": random.uniform(0.0000000001, 0.0000000003)
            },
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
                "published_verified": 0.0000000001,
                "published_regular": 0.0000000002,
                "calculated_cost_per_year": 0.000006
            },
            "recent_deals": [],
            "active_deals_count": random.randint(100, 1000)
        }
        
        return {
            "success": True,
            "mock": True,
            "analysis": analysis
        }
    
    def _mock_miner_comparison(self, miners: List[str]) -> Dict[str, Any]:
        """Generate mock miner comparison."""
        comparison = []
        for miner in miners:
            analysis = self._mock_miner_analysis(miner)
            if analysis.get("success", False):
                comparison.append(analysis["analysis"])
        
        metrics = ["raw_power", "quality_power", "active_sectors", "faulty_sectors", 
                  "deal_success_rate", "performance_score"]
        
        # Get best miner for each metric
        best_miners = {}
        for metric in metrics:
            if metric in ["faulty_sectors"]:
                # Lower is better
                best = min(comparison, key=lambda x: x.get(metric, float("inf")))
            else:
                # Higher is better
                best = max(comparison, key=lambda x: x.get(metric, 0))
            
            best_miners[metric] = best["miner_info"]["address"]
        
        return {
            "success": True,
            "mock": True,
            "comparison": comparison,
            "best_miners": best_miners
        }
    
    def _mock_storage_estimate(self, size_bytes: int, duration_days: int, verified_deal: bool) -> Dict[str, Any]:
        """Generate mock storage cost estimate."""
        size_gib = size_bytes / (1024**3)
        duration_epochs = int((duration_days * 24 * 60 * 60) / 30)  # 30 second epochs
        
        avg_price = 0.0000000002
        if verified_deal:
            price_multiplier = 0.5  # 50% discount
        else:
            price_multiplier = 1.0
        
        storage_cost_fil = size_gib * avg_price * duration_epochs * price_multiplier
        total_cost_fil = storage_cost_fil + 0.05  # Add 0.05 FIL for gas
        
        return {
            "success": True,
            "mock": True,
            "estimate": {
                "size_bytes": size_bytes,
                "size_gib": round(size_gib, 4),
                "duration_days": duration_days,
                "duration_epochs": duration_epochs,
                "verified_deal": verified_deal,
                "avg_price_per_gib_per_epoch": avg_price,
                "storage_cost_fil": round(storage_cost_fil, 8),
                "gas_cost_fil": 0.05,
                "total_cost_fil": round(total_cost_fil, 8),
                "price_range_fil": {
                    "min": round(storage_cost_fil * 0.8, 8),
                    "max": round(storage_cost_fil * 1.2, 8),
                    "avg": round(storage_cost_fil, 8)
                },
                "usd_per_fil": 3.50,
                "total_cost_usd": round(total_cost_fil * 3.50, 2)
            }
        }
    
    def _mock_redundant_storage(self, cid: str, miner_count: int, verified_deal: bool, deal_duration: int) -> Dict[str, Any]:
        """Generate mock redundant storage response."""
        import random
        import uuid
        
        miners = [
            {"address": "f01606", "name": "ServeTheFuture", "location": "France", "reputation": 95},
            {"address": "f0135078", "name": "FilSwan", "location": "China", "reputation": 92},
            {"address": "f022352", "name": "DekPool", "location": "Germany", "reputation": 90},
            {"address": "f01247", "name": "ScaleSphere", "location": "Singapore", "reputation": 88},
            {"address": "f02576", "name": "IPFSMain", "location": "USA", "reputation": 89}
        ]
        
        if miner_count > len(miners):
            miner_count = len(miners)
        
        selected_miners = random.sample(miners, miner_count)
        
        deals = []
        for miner in selected_miners:
            deal_id = str(random.randint(100000, 999999))
            
            deals.append({
                "success": True,
                "deal_id": deal_id,
                "miner": miner["address"],
                "miner_info": miner,
                "cid": cid,
                "start_epoch": int(time.time() / 30),
                "duration": deal_duration
            })
        
        return {
            "success": True,
            "mock": True,
            "deals": deals,
            "failed_deals": [],
            "total_deals": len(deals),
            "failed_count": 0,
            "requested_count": miner_count,
            "redundancy_factor": len(deals),
            "cid": cid
        }
    
    def _mock_from_ipfs(self, cid: str, miner: Optional[str], deal_duration: int, verified_deal: bool) -> Dict[str, Any]:
        """Generate mock from_ipfs response."""
        import random
        
        if not miner:
            miners = ["f01606", "f0135078", "f022352", "f01247", "f02576"]
            miner = random.choice(miners)
        
        deal_id = str(random.randint(100000, 999999))
        
        return {
            "success": True,
            "mock": True,
            "deal_id": deal_id,
            "cid": cid,
            "miner": miner,
            "start_epoch": int(time.time() / 30),
            "duration": deal_duration,
            "verified_deal": verified_deal,
            "deal_state": "proposed",
            "message": f"Deal {deal_id} proposed to miner {miner}"
        }
    
    def _mock_content_health(self, cid: str) -> Dict[str, Any]:
        """Generate mock content health check."""
        import random
        
        miners = ["f01606", "f0135078", "f022352", "f01247", "f02576"]
        deal_states = ["active", "sealing", "proposed", "failed", "expired"]
        
        # Generate random active deals
        active_count = random.randint(1, 3)
        active_deals = []
        for i in range(active_count):
            active_deals.append({
                "deal_id": str(random.randint(100000, 999999)),
                "status": "active",
                "miner": random.choice(miners)
            })
        
        # Generate random expired deals
        expired_count = random.randint(0, 2)
        expired_deals = []
        for i in range(expired_count):
            expired_deals.append({
                "deal_id": str(random.randint(100000, 999999)),
                "status": "expired",
                "miner": random.choice(miners),
                "created_at": time.time() - random.randint(86400*180, 86400*365),
                "expired_at": time.time() - random.randint(0, 86400*30)
            })
        
        # Generate random failing deals
        failing_count = random.randint(0, 1)
        failing_deals = []
        for i in range(failing_count):
            failing_deals.append({
                "deal_id": str(random.randint(100000, 999999)),
                "error": "Failed to activate deal",
                "miner": random.choice(miners)
            })
        
        total_deals = active_count + expired_count + failing_count
        health_score = (active_count / total_deals) * 100 if total_deals > 0 else 0
        
        health_status = "Healthy"
        if health_score < 33:
            health_status = "Critical"
        elif health_score < 66:
            health_status = "Warning"
        
        return {
            "success": True,
            "mock": True,
            "health": {
                "cid": cid,
                "active_deals": active_deals,
                "expired_deals": expired_deals,
                "failing_deals": failing_deals,
                "total_deals": total_deals,
                "redundancy_level": active_count,
                "health_score": round(health_score, 2),
                "health_status": health_status,
                "last_checked": time.time()
            }
        }
    
    def _mock_monitor_deal(self, deal_id: str, callback_url: Optional[str]) -> Dict[str, Any]:
        """Generate mock deal monitoring response."""
        import random
        
        deal_states = ["proposed", "published", "active", "sealing"]
        deal_state = random.choice(deal_states)
        
        return {
            "success": True,
            "mock": True,
            "message": f"Started monitoring deal {deal_id}",
            "deal_id": deal_id,
            "callback_url": callback_url,
            "current_status": deal_state
        }
    
    def _mock_deal_status(self, deal_id: str) -> Dict[str, Any]:
        """Generate mock deal status check."""
        import random
        
        deal_states = ["proposed", "published", "active", "sealing", "terminated", "error"]
        deal_state = random.choice(deal_states)
        
        miners = ["f01606", "f0135078", "f022352", "f01247", "f02576"]
        miner = random.choice(miners)
        
        result = {
            "success": True,
            "mock": True,
            "deal_id": deal_id,
            "status": deal_state,
            "miner": miner,
            "message": f"Deal {deal_id} is currently in {deal_state} state with miner {miner}"
        }
        
        if deal_state == "error":
            result["error"] = "Failed to activate deal"
        
        if deal_state == "active":
            result["sector_start_epoch"] = int(time.time() / 30) - random.randint(10, 1000)
            result["sector_expiration_epoch"] = int(time.time() / 30) + random.randint(1000, 10000)
        
        return result
    
    def _mock_chain_block(self, height: Optional[int], cid: Optional[str]) -> Dict[str, Any]:
        """Generate mock chain block information."""
        import random
        import uuid
        
        current_time = time.time()
        epoch_time = 30  # seconds per epoch
        
        if height is None:
            height = 2500000 + int(current_time / epoch_time) % 1000
        
        block_timestamp = int(current_time - ((2500000 + int(current_time / epoch_time) % 1000 - height) * epoch_time))
        
        if cid:
            block_cid = cid
        else:
            block_cid = f"bafy2bzace{uuid.uuid4().hex[:16]}{uuid.uuid4().hex[:16]}"
        
        mock_block = {
            "Height": height,
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
            "mock": True,
            "block": mock_block
        }
    
    def _mock_chain_head(self) -> Dict[str, Any]:
        """Generate mock chain head information."""
        import random
        import uuid
        
        current_time = time.time()
        epoch_time = 30  # seconds per epoch
        
        height = 2500000 + int(current_time / epoch_time) % 1000
        
        blocks = []
        for i in range(random.randint(2, 5)):
            blocks.append({
                "Height": height,
                "Timestamp": int(current_time),
                "Cid": f"bafy2bzace{uuid.uuid4().hex[:16]}{uuid.uuid4().hex[:16]}",
                "Miner": f"f0{random.randint(1000, 100000)}",
                "ParentWeight": str(random.randint(1000000000000, 9000000000000)),
                "ParentBaseFee": str(random.randint(90000000, 110000000))
            })
        
        return {
            "success": True,
            "mock": True,
            "Height": height,
            "Blocks": blocks
        }
    
    def _mock_transaction(self, cid: str) -> Dict[str, Any]:
        """Generate mock transaction tracking."""
        import random
        
        states = ["pending", "confirmed", "error"]
        state = random.choice(states)
        
        receipt = {
            "ExitCode": 0 if state == "confirmed" else 1,
            "Return": "",
            "GasUsed": random.randint(1000000, 10000000),
        }
        
        if state == "error":
            receipt["Error"] = "execution failed"
        
        return {
            "success": True,
            "mock": True,
            "cid": cid,
            "state": state,
            "block_height": 2500000 + random.randint(1, 1000),
            "confirmed": state == "confirmed",
            "receipt": receipt
        }