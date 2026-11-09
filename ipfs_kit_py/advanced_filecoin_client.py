"""
Advanced Filecoin Client Library for MCP

This module implements the client library for interacting with the advanced Filecoin
features mentioned in the MCP roadmap:
1. Network Analytics & Metrics
2. Intelligent Miner Selection & Management
3. Enhanced Storage Operations
4. Content Health & Reliability
5. Blockchain Integration

This library can be used with either the mock server for development and testing,
or with actual Filecoin services in production.
"""

import os
import time
import json
import logging
import requests
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin

# Configure logger
logger = logging.getLogger(__name__)


class AdvancedFilecoinClient:
    """
    Client for interacting with advanced Filecoin features.
    
    This client implements the capabilities outlined in the MCP roadmap's
    "Advanced Filecoin Integration" section.
    """
    
    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        mock_mode: bool = False,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize the Advanced Filecoin Client.
        
        Args:
            base_url: Base URL for the Filecoin advanced API
            api_key: API key for authentication
            mock_mode: Whether to use mock responses for testing
            timeout: Request timeout in seconds
            max_retries: Maximum number of request retries
        """
        # Use environment variables as fallback
        self.base_url = base_url or os.environ.get("FILECOIN_ADVANCED_API_URL", "http://localhost:8175")
        self.api_key = api_key or os.environ.get("FILECOIN_API_KEY", "")
        self.mock_mode = mock_mode
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Normalize base URL
        if not self.base_url.endswith("/"):
            self.base_url = self.base_url + "/"
        
        # Setup session for connection pooling
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            "User-Agent": "MCP-Advanced-Filecoin-Client/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Add API key if provided
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        
        # Base API endpoint path
        self.api_path = "api/v0/filecoin/advanced/"
        
        logger.info(f"Initialized Advanced Filecoin Client with base URL: {self.base_url}")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        retries: int = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            retries: Number of retries (uses instance default if None)
            
        Returns:
            Response data as dictionary
        """
        if retries is None:
            retries = self.max_retries
        
        # Handle mock mode
        if self.mock_mode and endpoint != "status":
            return self._mock_response(method, endpoint, params, data)
        
        url = urljoin(self.base_url, self.api_path + endpoint)
        
        for attempt in range(retries + 1):
            try:
                if method.lower() == "get":
                    response = self.session.get(url, params=params, timeout=self.timeout)
                elif method.lower() == "post":
                    response = self.session.post(url, params=params, json=data, timeout=self.timeout)
                elif method.lower() == "put":
                    response = self.session.put(url, params=params, json=data, timeout=self.timeout)
                elif method.lower() == "delete":
                    response = self.session.delete(url, params=params, json=data, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check for successful response
                if response.status_code >= 200 and response.status_code < 300:
                    return response.json()
                
                # Handle error responses
                error_msg = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if "detail" in error_data:
                        error_msg = f"API error: {response.status_code} - {error_data['detail']}"
                except Exception:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                
                # Log error
                logger.error(error_msg)
                
                # For 5xx errors, retry
                if response.status_code >= 500 and attempt < retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying after {wait_time}s (attempt {attempt+1}/{retries})")
                    time.sleep(wait_time)
                    continue
                
                # For 4xx errors or final retry, return error
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
            except requests.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                
                # Retry on connection errors
                if attempt < retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying after {wait_time}s (attempt {attempt+1}/{retries})")
                    time.sleep(wait_time)
                    continue
                
                # Final retry, return error
                return {
                    "success": False,
                    "error": f"Request failed: {str(e)}",
                    "status_code": 0
                }
        
        # Should never get here, but just in case
        return {
            "success": False,
            "error": "Maximum retries exceeded",
            "status_code": 0
        }

    def _mock_response(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate mock responses for testing purposes.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            
        Returns:
            Mock response data
        """
        logger.info(f"Generating mock response for {method} {endpoint}")
        
        # Basic successful response
        response = {
            "success": True,
            "mock": True,
            "timestamp": time.time()
        }
        
        # Network statistics
        if endpoint == "network/stats":
            response.update({
                "stats": {
                    "chain_height": 1000000,
                    "network_storage_capacity": 10000000000000,
                    "active_miners": 5,
                    "average_price": "40000000000",
                    "avg_block_time": 30,
                    "current_base_fee": "100000000",
                    "total_committed_storage": 5000000000000,
                    "total_deals": 1000,
                }
            })
        
        # Gas prices
        elif endpoint == "network/gas":
            days = params.get("days", 7) if params else 7
            response.update({
                "current_base_fee": "100000000",
                "trends": [
                    {
                        "timestamp": time.time() - (i * 6 * 3600),
                        "base_fee": str(1000000 + i * 10000),
                        "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - (i * 6 * 3600)))
                    }
                    for i in range(days * 4)
                ],
                "period_days": days
            })
        
        # Storage stats
        elif endpoint == "network/storage":
            response.update({
                "total_capacity": 10000000000000,
                "committed_storage": 5000000000000,
                "utilization_percentage": 50.0,
                "price_trends": [
                    {
                        "timestamp": time.time() - (i * 24 * 3600),
                        "average_price": str(40000000000 + i * 1000000000),
                        "date": time.strftime("%Y-%m-%d", time.localtime(time.time() - (i * 24 * 3600)))
                    }
                    for i in range(30)
                ],
                "regional_stats": {
                    "North America": {"capacity": 3000000000000, "price": "50000000000"},
                    "Europe": {"capacity": 2500000000000, "price": "45000000000"},
                    "Asia": {"capacity": 2000000000000, "price": "40000000000"},
                    "South America": {"capacity": 1500000000000, "price": "35000000000"},
                    "Oceania": {"capacity": 1000000000000, "price": "30000000000"},
                }
            })
        
        # List miners
        elif endpoint == "miners":
            miner_count = 5
            response.update({
                "miners": [
                    {
                        "id": f"t0100{i}",
                        "region": ["North America", "Europe", "Asia", "South America", "Oceania"][i % 5],
                        "reputation": round(3.5 + i * 0.3, 1),
                        "success_rate": round(0.9 + i * 0.02, 2),
                        "ask_price": str(50000000000 - i * 5000000000),
                        "available_space": 1024000000000 + i * 1024000000000
                    }
                    for i in range(miner_count)
                ],
                "count": miner_count,
                "total_miners": miner_count
            })
        
        # Get miner info
        elif endpoint.startswith("miners/"):
            miner_id = endpoint.split("/")[-1]
            response.update({
                "miner": {
                    "id": miner_id,
                    "region": "North America",
                    "reputation": 4.8,
                    "success_rate": 0.99,
                    "ask_price": "50000000000",
                    "available_space": 1024000000000,
                    "deal_success_count": 950,
                    "deal_failure_count": 50,
                    "online_percentage": 99.5,
                    "time_to_seal": 6,
                    "regions_served": ["North America"],
                    "performance_history": [
                        {
                            "timestamp": time.time() - (i * 24 * 3600),
                            "date": time.strftime("%Y-%m-%d", time.localtime(time.time() - (i * 24 * 3600))),
                            "success_rate": round(0.99 - (i * 0.005), 2),
                            "online_percentage": round(99.5 - (i * 0.2), 1),
                            "time_to_seal": 6 + (i % 3)
                        }
                        for i in range(30)
                    ]
                }
            })
        
        # Recommend miners
        elif endpoint == "miners/recommend":
            size = params.get("size", 1024 * 1024) if params else 1024 * 1024
            replication = params.get("replication", 1) if params else 1
            gib = size / (1024 * 1024 * 1024)
            if gib < 0.001:
                gib = 0.001  # Minimum 1 MiB
            
            recommended = [f"t0100{i}" for i in range(replication)]
            costs = []
            
            for i in range(replication):
                price_per_gib_per_epoch = 50000000000 - i * 5000000000
                duration = 518400  # 180 days in epochs
                total_cost = price_per_gib_per_epoch * gib * duration
                costs.append({
                    "miner_id": f"t0100{i}",
                    "price_per_gib_per_epoch": price_per_gib_per_epoch,
                    "total_cost": str(int(total_cost)),
                    "total_cost_fil": str(int(total_cost) / 1e18),
                    "duration_days": 180,
                })
            
            response.update({
                "recommended_miners": recommended,
                "file_size_bytes": size,
                "file_size_gib": gib,
                "replication": replication,
                "costs": costs,
                "total_cost": str(sum(int(c["total_cost"]) for c in costs)),
                "total_cost_fil": str(sum(int(c["total_cost"]) for c in costs) / 1e18),
            })
        
        # Make deal
        elif endpoint == "storage/deal":
            cid = data.get("cid", "") if data else ""
            if not cid or cid == "auto":
                import uuid
                cid = f"bafy{uuid.uuid4().hex}"
            
            miner_id = data.get("miner_id", "") if data else ""
            miners = [miner_id] if miner_id else [f"t0100{i}" for i in range(data.get("replication", 1) if data else 1)]
            
            deals = []
            for i, miner in enumerate(miners):
                deal_id = f"deal-{uuid.uuid4().hex}"
                deals.append({
                    "deal_id": deal_id,
                    "cid": cid,
                    "miner": miner,
                    "client": "t3abc123def456",
                    "size": 1024 * 1024,
                    "price": "1000000000000",
                    "duration": 518400,
                    "start_time": time.time() + 3600,
                    "end_time": time.time() + (518400 * 30),
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "verified": data.get("verified", False) if data else False,
                    "state": "proposed",
                })
            
            response.update({
                "cid": cid,
                "deals": deals,
                "deal_count": len(deals),
            })
        
        # Get deal info
        elif endpoint.startswith("storage/deal/"):
            deal_id = endpoint.split("/")[-1]
            response.update({
                "deal": {
                    "deal_id": deal_id,
                    "cid": f"bafy{hash(deal_id)%100000:05d}",
                    "miner": "t01000",
                    "client": "t3abc123def456",
                    "size": 1024 * 1024,
                    "price": "1000000000000",
                    "duration": 518400,
                    "start_time": time.time() + 3600,
                    "end_time": time.time() + (518400 * 30),
                    "created_at": time.time() - 3600,
                    "updated_at": time.time() - 1800,
                    "verified": False,
                    "state": "active",
                    "sector": "s-t01-1234",
                    "history": [
                        {"time": time.time() - 3600, "state": "proposed", "message": "Deal proposed"},
                        {"time": time.time() - 3300, "state": "published", "message": "Deal published on-chain"},
                        {"time": time.time() - 1800, "state": "active", "message": "Deal activated by storage provider"},
                    ],
                }
            })
        
        # Get CID info
        elif endpoint.startswith("storage/cid/"):
            cid = endpoint.split("/")[-1]
            deal_count = 3
            deals = []
            
            for i in range(deal_count):
                deals.append({
                    "deal_id": f"deal-{cid}-{i}",
                    "cid": cid,
                    "miner": f"t0100{i}",
                    "client": "t3abc123def456",
                    "size": 1024 * 1024,
                    "price": "1000000000000",
                    "duration": 518400,
                    "start_time": time.time() + 3600,
                    "end_time": time.time() + (518400 * 30),
                    "created_at": time.time() - 3600,
                    "updated_at": time.time() - 1800,
                    "verified": False,
                    "state": ["proposed", "published", "active"][i % 3],
                })
            
            response.update({
                "cid": cid,
                "size": 1024 * 1024,
                "deals": deals,
                "deal_count": deal_count,
                "created_at": time.time() - 3600,
                "replication": deal_count,
            })
        
        # Get deal health
        elif endpoint.startswith("health/deal/"):
            deal_id = endpoint.split("/")[-1]
            response.update({
                "deal_id": deal_id,
                "cid": f"bafy{hash(deal_id)%100000:05d}",
                "health": {
                    "last_checked": time.time() - 1800,
                    "health": 95,
                    "message": "Deal is healthy",
                    "checks": [
                        {"time": time.time() - 3600, "result": "success", "message": "Initial health check: 95"},
                        {"time": time.time() - 1800, "result": "success", "message": "Regular health check: 95"},
                    ]
                },
                "state": "active",
                "history": [
                    {"time": time.time() - 3600, "state": "proposed", "message": "Deal proposed"},
                    {"time": time.time() - 3300, "state": "published", "message": "Deal published on-chain"},
                    {"time": time.time() - 1800, "state": "active", "message": "Deal activated by storage provider"},
                ],
            })
        
        # Get CID health
        elif endpoint.startswith("health/cid/"):
            cid = endpoint.split("/")[-1]
            deal_count = 3
            
            deal_healths = []
            for i in range(deal_count):
                health = 95 - (i * 5)  # Decrease health for each deal to simulate variation
                deal_healths.append({
                    "deal_id": f"deal-{cid}-{i}",
                    "miner": f"t0100{i}",
                    "state": ["proposed", "published", "active"][i % 3],
                    "health": health,
                    "last_checked": time.time() - 1800,
                })
            
            # Calculate overall health
            overall_health = sum(d["health"] for d in deal_healths) / len(deal_healths)
            
            # Determine if repairs are needed
            needs_repair = overall_health < 90
            repair_recommendations = []
            
            if needs_repair:
                # Find unhealthy deals
                unhealthy_deals = [d for d in deal_healths if d["health"] < 90]
                for deal in unhealthy_deals:
                    repair_recommendations.append({
                        "deal_id": deal["deal_id"],
                        "health": deal["health"],
                        "action": "replicate",
                        "reason": f"Deal health below threshold: {deal['health']}",
                    })
            
            response.update({
                "cid": cid,
                "overall_health": overall_health,
                "deal_count": deal_count,
                "healthy_deals": len([d for d in deal_healths if d["health"] >= 90]),
                "unhealthy_deals": len([d for d in deal_healths if d["health"] < 90]),
                "deals": deal_healths,
                "needs_repair": needs_repair,
                "repair_recommendations": repair_recommendations,
            })
        
        # Repair content
        elif endpoint == "health/repair":
            cid = params.get("cid", "") if params else ""
            strategy = params.get("strategy", "replicate") if params else "replicate"
            
            repair_results = []
            if strategy == "replicate":
                for i in range(2):
                    repair_results.append({
                        "action": "replicate",
                        "deal_id": f"deal-{cid}-new-{i}",
                        "miner": f"t0100{i+3}",
                        "status": "created",
                    })
            elif strategy == "recover":
                for i in range(2):
                    repair_results.append({
                        "action": "recover",
                        "deal_id": f"deal-{cid}-{i}",
                        "status": "repaired",
                        "new_health": 95,
                    })
            elif strategy == "migrate":
                for i in range(2):
                    repair_results.append({
                        "action": "migrate",
                        "old_deal_id": f"deal-{cid}-{i}",
                        "new_deal_id": f"deal-{cid}-new-{i}",
                        "old_miner": f"t0100{i}",
                        "new_miner": f"t0100{i+3}",
                        "status": "migrated",
                    })
            
            response.update({
                "cid": cid,
                "strategy": strategy,
                "unhealthy_deals": 2,
                "repair_actions": len(repair_results),
                "results": repair_results,
            })
        
        # Blockchain status
        elif endpoint == "blockchain/status":
            response.update({
                "chain_height": 1000000,
                "last_finalized": 999990,
                "avg_block_time": 30,
                "current_base_fee": "100000000",
                "latest_blocks": [
                    {
                        "height": 1000000 - i,
                        "cid": f"bafy{hash(1000000-i)%100000:05d}",
                        "timestamp": time.time() - (i * 30),
                        "parent_cid": f"bafy{hash(1000000-i-1)%100000:05d}" if i > 0 else None,
                        "miner": f"t0100{i%5}",
                        "messages": 50 + i * 2,
                        "reward": "10000000000000",
                    }
                    for i in range(5)
                ],
            })
        
        # Blockchain blocks
        elif endpoint == "blockchain/blocks":
            limit = params.get("limit", 10) if params else 10
            start = params.get("start", 1000000 - limit) if params else 1000000 - limit
            end = params.get("end", 1000000) if params else 1000000
            
            blocks = [
                {
                    "height": h,
                    "cid": f"bafy{hash(h)%100000:05d}",
                    "timestamp": time.time() - ((1000000 - h) * 30),
                    "parent_cid": f"bafy{hash(h-1)%100000:05d}" if h > start else None,
                    "miner": f"t0100{h%5}",
                    "messages": 50 + h % 20,
                    "reward": "10000000000000",
                }
                for h in range(start, end + 1)
            ]
            
            response.update({
                "blocks": blocks,
                "count": len(blocks),
                "chain_height": 1000000,
            })
        
        # Blockchain deals
        elif endpoint == "blockchain/deals":
            limit = params.get("limit", 100) if params else 100
            miner = params.get("miner", None) if params else None
            status = params.get("status", None) if params else None
            
            deals = []
            for i in range(limit):
                deal = {
                    "deal_id": f"deal-{i}",
                    "cid": f"bafy{hash(i)%100000:05d}",
                    "miner": f"t0100{i%5}",
                    "client": "t3abc123def456",
                    "size": 1024 * 1024,
                    "price": "1000000000000",
                    "duration": 518400,
                    "start_time": time.time() - 3600 + i * 60,
                    "end_time": time.time() + (518400 * 30) + i * 60,
                    "created_at": time.time() - 3600 - i * 60,
                    "updated_at": time.time() - 1800 - i * 30,
                    "verified": i % 3 == 0,
                    "state": ["proposed", "published", "active", "sealed"][i % 4],
                }
                
                # Apply filters
                if miner and deal["miner"] != miner:
                    continue
                
                if status and deal["state"] != status:
                    continue
                
                deals.append(deal)
            
            response.update({
                "deals": deals[:limit],
                "count": len(deals),
                "total_deals": 1000,
                "filters_applied": {
                    "miner": miner,
                    "status": status,
                },
            })
        
        # Transaction status
        elif endpoint.startswith("blockchain/transaction/"):
            tx_id = endpoint.split("/")[-1]
            response.update({
                "transaction": {
                    "id": tx_id,
                    "block_height": 1000000 - hash(tx_id) % 10,
                    "block_cid": f"bafy{hash(tx_id)%100000:05d}",
                    "timestamp": time.time() - hash(tx_id) % 3600,
                    "from": "t3sender123456789",
                    "to": "t3recipient987654321",
                    "value": "5000000000000",
                    "gas_fee": "100000000",
                    "method": "PublishStorageDeal",
                    "status": "success",
                    "confirmations": 5 + hash(tx_id) % 5,
                }
            })
        
        return response

    def check_api_status(self) -> Dict[str, Any]:
        """Check if the advanced Filecoin API is available."""
        try:
            # Try to connect to the API's status endpoint
            base_url = self.base_url.rstrip("/")
            url = f"{base_url}/status"
            
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return {
                        "success": True,
                        "status": "available",
                        "version": data.get("version", "unknown"),
                        "message": data.get("message", "API is available"),
                    }
                except ValueError:
                    return {
                        "success": True,
                        "status": "available",
                        "message": "API is available but returned non-JSON response",
                    }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "message": f"API returned status code {response.status_code}",
                }
        
        except requests.RequestException as e:
            return {
                "success": False,
                "status": "unavailable",
                "message": f"Failed to connect to API: {str(e)}",
            }

    def get_network_stats(self) -> Dict[str, Any]:
        """
        Get current Filecoin network statistics including capacity, miners, and pricing.
        
        Returns:
            Network statistics including chain height, storage capacity, active miners, etc.
        """
        return self._make_request("GET", "network/stats")

    def get_gas_prices(self, days: int = 7) -> Dict[str, Any]:
        """
        Get gas price trends for the Filecoin network.
        
        Args:
            days: Number of days of gas price history to retrieve
            
        Returns:
            Gas price trends including current base fee and historical data
        """
        return self._make_request("GET", "network/gas", params={"days": days})

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage capacity and utilization statistics including regional breakdowns.
        
        Returns:
            Storage statistics including total capacity, utilization, and price trends
        """
        return self._make_request("GET", "network/storage")

    def list_miners(
        self,
        region: Optional[str] = None,
        min_reputation: Optional[float] = None,
        max_price: Optional[str] = None,
        available_space: Optional[int] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List and filter storage miners based on various criteria.
        
        Args:
            region: Filter miners by geographic region
            min_reputation: Minimum reputation score (0-5 scale)
            max_price: Maximum price in attoFIL
            available_space: Minimum available space in bytes
            limit: Maximum number of miners to return
            
        Returns:
            List of miners matching the specified criteria
        """
        params = {"limit": limit}
        
        if region:
            params["region"] = region
        
        if min_reputation is not None:
            params["min_reputation"] = min_reputation
        
        if max_price:
            params["max_price"] = max_price
        
        if available_space is not None:
            params["available_space"] = available_space
        
        return self._make_request("GET", "miners", params=params)

    def get_miner_info(self, miner_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific miner including performance metrics.
        
        Args:
            miner_id: Miner ID to query (e.g., "t01000")
            
        Returns:
            Detailed information about the miner including performance history
        """
        return self._make_request("GET", f"miners/{miner_id}")

    def recommend_miners(
        self,
        size: int,
        replication: int = 1,
        max_price: Optional[str] = None,
        duration: int = 518400,
        region: Optional[str] = None,
        verified: bool = False
    ) -> Dict[str, Any]:
        """
        Get miner recommendations based on file requirements and optimization criteria.
        
        Args:
            size: File size in bytes
            replication: Number of replicas desired
            max_price: Maximum price per GiB per epoch in attoFIL
            duration: Deal duration in epochs (default 518400, ~180 days)
            region: Preferred geographic region
            verified: Whether to use verified datacap for deals
            
        Returns:
            Recommended miners with cost estimates and optimized selection
        """
        params = {
            "size": size,
            "replication": replication,
            "duration": duration,
            "verified": verified
        }
        
        if max_price:
            params["max_price"] = max_price
        
        if region:
            params["region"] = region
        
        return self._make_request("GET", "miners/recommend", params=params)

    def make_storage_deal(
        self,
        cid: str,
        miner_id: Optional[str] = None,
        duration: int = 518400,
        replication: int = 1,
        max_price: Optional[str] = None,
        verified: bool = False
    ) -> Dict[str, Any]:
        """
        Create storage deals with enhanced options like replication and miner selection.
        
        Args:
            cid: Content ID to store (use "auto" to generate a new CID for testing)
            miner_id: Specific miner to use (or None for automatic selection)
            duration: Deal duration in epochs (default 518400, ~180 days)
            replication: Number of replicas to create
            max_price: Maximum price per GiB per epoch in attoFIL
            verified: Whether to use verified datacap for the deal
            
        Returns:
            Created storage deal(s) information
        """
        data = {
            "cid": cid,
            "duration": duration,
            "replication": replication,
            "verified": verified
        }
        
        if miner_id:
            data["miner_id"] = miner_id
        
        if max_price:
            data["max_price"] = max_price
        
        return self._make_request("POST", "storage/deal", data=data)

    def get_deal_info(self, deal_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific storage deal.
        
        Args:
            deal_id: Deal ID to query
            
        Returns:
            Detailed information about the storage deal
        """
        return self._make_request("GET", f"storage/deal/{deal_id}")

    def get_content_deals(self, cid: str) -> Dict[str, Any]:
        """
        Get information about all storage deals for a specific content ID.
        
        Args:
            cid: Content ID to query
            
        Returns:
            Information about all deals storing the specified content
        """
        return self._make_request("GET", f"storage/cid/{cid}")

    def get_deal_health(self, deal_id: str) -> Dict[str, Any]:
        """
        Get health metrics and status for a specific storage deal.
        
        Args:
            deal_id: Deal ID to check
            
        Returns:
            Health metrics including latest checks and status history
        """
        return self._make_request("GET", f"health/deal/{deal_id}")

    def get_content_health(self, cid: str) -> Dict[str, Any]:
        """
        Get health metrics for all deals storing a specific content ID.
        
        Args:
            cid: Content ID to check
            
        Returns:
            Health metrics for all deals storing the content with repair recommendations
        """
        return self._make_request("GET", f"health/cid/{cid}")

    def repair_content(
        self,
        cid: str,
        strategy: str = "replicate"
    ) -> Dict[str, Any]:
        """
        Initiate repair operations for content with unhealthy deals.
        
        Args:
            cid: Content ID to repair
            strategy: Repair strategy (replicate, recover, migrate)
            
        Returns:
            Results of repair operations
        """
        params = {
            "cid": cid,
            "strategy": strategy
        }
        
        return self._make_request("POST", "health/repair", params=params)

    def get_blockchain_status(self) -> Dict[str, Any]:
        """
        Get current blockchain status including height and recent blocks.
        
        Returns:
            Current blockchain status information
        """
        return self._make_request("GET", "blockchain/status")

    def get_blockchain_blocks(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get blockchain blocks within a specified range.
        
        Args:
            start: Starting block height
            end: Ending block height
            limit: Maximum number of blocks to return
            
        Returns:
            List of blockchain blocks matching the criteria
        """
        params = {"limit": limit}
        
        if start is not None:
            params["start"] = start
        
        if end is not None:
            params["end"] = end
        
        return self._make_request("GET", "blockchain/blocks", params=params)

    def get_blockchain_deals(
        self,
        miner: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get on-chain deal information with filtering options.
        
        Args:
            miner: Filter by miner ID
            status: Filter by deal status
            limit: Maximum number of deals to return
            
        Returns:
            List of on-chain deals matching the criteria
        """
        params = {"limit": limit}
        
        if miner:
            params["miner"] = miner
        
        if status:
            params["status"] = status
        
        return self._make_request("GET", "blockchain/deals", params=params)

    def get_transaction_status(self, tx_id: str) -> Dict[str, Any]:
        """
        Get the status of a blockchain transaction.
        
        Args:
            tx_id: Transaction ID to query
            
        Returns:
            Transaction status and details
        """
        return self._make_request("GET", f"blockchain/transaction/{tx_id}")