"""
Advanced Filecoin MCP Server Integration

This module integrates the advanced Filecoin features with the MCP server.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, Path, Depends

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import advanced Filecoin implementation
try:
    from advanced_filecoin import AdvancedFilecoinStorage
    ADVANCED_FILECOIN_AVAILABLE = True
except ImportError:
    ADVANCED_FILECOIN_AVAILABLE = False
    logger.warning("Advanced Filecoin features not available. Make sure advanced_filecoin.py is in the Python path.")

# Singleton instance of AdvancedFilecoinStorage
_filecoin_instance = None

def get_filecoin_client():
    """Get or create the AdvancedFilecoinStorage instance."""
    global _filecoin_instance
    
    if _filecoin_instance is None and ADVANCED_FILECOIN_AVAILABLE:
        try:
            _filecoin_instance = AdvancedFilecoinStorage()
        except Exception as e:
            logger.error(f"Error initializing AdvancedFilecoinStorage: {e}")
    
    return _filecoin_instance

def create_advanced_filecoin_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with advanced Filecoin endpoints.
    
    Args:
        api_prefix: The API prefix for the endpoints
        
    Returns:
        FastAPI router
    """
    if not ADVANCED_FILECOIN_AVAILABLE:
        logger.warning("Advanced Filecoin features not available. Returning minimal router.")
        router = APIRouter(prefix=f"{api_prefix}/filecoin/advanced")
        
        @router.get("/status")
        async def filecoin_advanced_status():
            return {
                "available": False,
                "error": "Advanced Filecoin features not available"
            }
        
        return router
    
    # Create the router with all endpoints
    router = APIRouter(prefix=f"{api_prefix}/filecoin/advanced")
    
    @router.get("/status")
    async def filecoin_advanced_status(filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)):
        """Get the status of the advanced Filecoin features."""
        if filecoin_client is None:
            return {
                "available": False,
                "error": "Advanced Filecoin client not initialized"
            }
        
        return {
            "available": True,
            "mock_mode": filecoin_client.mock_mode,
            "gateway_mode": filecoin_client.gateway_mode,
            "simulation_mode": filecoin_client.simulation_mode,
            "api_endpoint": filecoin_client.api_endpoint,
            "timestamp": time.time()
        }
    
    @router.get("/network/stats")
    async def filecoin_network_stats(filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)):
        """Get Filecoin network statistics."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.get_network_stats()
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.get("/network/gas")
    async def filecoin_gas_metrics(filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)):
        """Get current gas metrics for the Filecoin network."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.get_gas_metrics()
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.get("/miners/recommended")
    async def filecoin_recommended_miners(
        min_reputation: int = Query(85, description="Minimum miner reputation score"),
        region: Optional[str] = Query(None, description="Filter by region"),
        max_price: Optional[float] = Query(None, description="Maximum price per GiB per epoch"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Get recommended miners with optional filtering."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        filter_criteria = {
            "min_reputation": min_reputation,
            "region": region,
            "max_price": max_price
        }
        
        result = filecoin_client.get_recommended_miners(filter_criteria)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.get("/miners/{miner_address}")
    async def filecoin_analyze_miner(
        miner_address: str = Path(..., description="Filecoin address of the miner to analyze"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Analyze a specific miner."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.analyze_miner(miner_address)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.post("/storage/redundant")
    async def filecoin_create_redundant_storage(
        cid: str = Body(..., embed=True, description="Content ID to store"),
        miner_count: int = Body(3, embed=True, description="Number of different miners to use"),
        verified_deal: bool = Body(False, embed=True, description="Whether to make a verified storage deal"),
        deal_duration: int = Body(518400, embed=True, description="Deal duration in epochs"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Store IPFS content with multiple miners for redundancy."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.create_redundant_storage(cid, miner_count, verified_deal, deal_duration)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.post("/deals/{deal_id}/monitor")
    async def filecoin_monitor_deal(
        deal_id: str = Path(..., description="Deal ID to monitor"),
        callback_url: Optional[str] = Body(None, embed=True, description="Optional URL to call with status updates"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Start monitoring a storage deal's status."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.monitor_deal_status(deal_id, callback_url)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.post("/storage/estimate")
    async def filecoin_estimate_storage_cost(
        size_bytes: int = Body(..., embed=True, description="Size of data in bytes"),
        duration_days: int = Body(180, embed=True, description="Duration in days"),
        verified_deal: bool = Body(False, embed=True, description="Whether to use verified storage deals"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Estimate cost to store data on Filecoin."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.estimate_storage_cost(size_bytes, duration_days, verified_deal)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.get("/chain/block")
    async def filecoin_explore_chain_block(
        height: Optional[int] = Query(None, description="Optional block height, if None uses the latest block"),
        cid: Optional[str] = Query(None, description="Optional block CID, overrides height if provided"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Get information about a specific Filecoin blockchain block."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.explore_chain_block(height, cid)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    @router.get("/content/{cid}/health")
    async def filecoin_content_health(
        cid: str = Path(..., description="Content ID to check"),
        filecoin_client: AdvancedFilecoinStorage = Depends(get_filecoin_client)
    ):
        """Check the health of content stored on Filecoin."""
        if filecoin_client is None:
            raise HTTPException(status_code=503, detail="Advanced Filecoin client not available")
        
        result = filecoin_client.get_content_health(cid)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    return router