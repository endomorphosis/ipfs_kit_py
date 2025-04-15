"""
Optimized Data Routing Integration Module

This module integrates the Optimized Data Routing feature with the MCP server.
It provides functions to initialize the router and add its API endpoints to the FastAPI application.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends

from .optimized_router import OptimizedDataRouter, RoutingStrategy, ContentCategory
from .bandwidth_aware_router import enhance_router
from .router_api import create_router_api
from ..storage_manager.backend_manager import BackendManager
from ..auth.router import get_admin_user

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_router_integration")

# Global router instance
_router_instance = None
_enhanced_router_instance = None

def get_router_instance() -> OptimizedDataRouter:
    """Get the singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = OptimizedDataRouter()
    return _router_instance

def get_enhanced_router_instance() -> Any:
    """Get the singleton enhanced router instance."""
    global _enhanced_router_instance
    if _enhanced_router_instance is None:
        _enhanced_router_instance = enhance_router(get_router_instance())
    return _enhanced_router_instance

async def setup_optimized_routing(app: FastAPI, backend_manager: BackendManager) -> Dict[str, Any]:
    """
    Set up optimized data routing for the MCP server.
    
    Args:
        app: FastAPI application instance
        backend_manager: Backend manager instance
        
    Returns:
        Dictionary with setup results
    """
    try:
        # Initialize router with configuration from environment
        config = {
            "default_strategy": os.environ.get("ROUTER_DEFAULT_STRATEGY", RoutingStrategy.HYBRID.value),
            "update_interval": int(os.environ.get("ROUTER_UPDATE_INTERVAL", "300")),
            "current_region": os.environ.get("ROUTER_CURRENT_REGION", "default"),
            "auto_start_updates": os.environ.get("ROUTER_AUTO_UPDATES", "1") == "1"
        }
        
        # Add backend costs if specified
        backend_costs_path = os.environ.get("ROUTER_BACKEND_COSTS_PATH")
        if backend_costs_path and os.path.exists(backend_costs_path):
            import json
            try:
                with open(backend_costs_path, 'r') as f:
                    backend_costs = json.load(f)
                    config["backend_costs"] = backend_costs
            except Exception as e:
                logger.error(f"Error loading backend costs: {e}")
        
        # Add geo regions if specified
        geo_regions_path = os.environ.get("ROUTER_GEO_REGIONS_PATH")
        if geo_regions_path and os.path.exists(geo_regions_path):
            import json
            try:
                with open(geo_regions_path, 'r') as f:
                    geo_regions = json.load(f)
                    config["geo_regions"] = geo_regions
            except Exception as e:
                logger.error(f"Error loading geo regions: {e}")
        
        # Initialize router
        router = get_router_instance()
        if not router:
            router = OptimizedDataRouter(config)
            global _router_instance
            _router_instance = router
        
        # Register active backends
        backend_names = backend_manager.list_backends()
        for backend_name in backend_names:
            router.register_backend(backend_name)
        
        # Create enhanced router
        enhanced_router = get_enhanced_router_instance()
        if not enhanced_router:
            enhanced_router = enhance_router(router)
            global _enhanced_router_instance
            _enhanced_router_instance = enhanced_router
        
        # Create and include router API
        router_api = create_router_api(
            base_router=router,
            get_current_admin_user=get_admin_user
        )
        
        # Add router API to FastAPI app
        app.include_router(
            router_api,
            prefix="/api/v0/routing",
            tags=["Optimized Routing"]
        )
        
        # Set up initial route mappings
        # Default mappings are set up automatically by the router
        
        # Start automatic updates if configured
        if config.get("auto_start_updates", True):
            router.start_updates()
        
        logger.info("Optimized Data Routing system initialized successfully")
        
        return {
            "success": True,
            "message": "Optimized Data Routing system initialized successfully",
            "default_strategy": router.default_strategy.value,
            "backends": list(router.backends),
            "auto_updates": router._update_thread is not None
        }
        
    except Exception as e:
        logger.error(f"Error setting up optimized data routing: {e}")
        return {
            "success": False,
            "message": f"Error setting up optimized data routing: {e}"
        }

async def verify_optimized_routing(backend_manager: BackendManager) -> Dict[str, Any]:
    """
    Verify that optimized data routing is working correctly.
    
    Args:
        backend_manager: Backend manager instance
        
    Returns:
        Dictionary with verification results
    """
    try:
        # Get router instance
        router = get_router_instance()
        if not router:
            return {
                "success": False,
                "message": "Router instance not initialized"
            }
        
        # Check if we have registered backends
        if not router.backends:
            # Register backends from backend manager
            backend_names = backend_manager.list_backends()
            for backend_name in backend_names:
                router.register_backend(backend_name)
        
        # Verify that we have backends
        if not router.backends:
            return {
                "success": False,
                "message": "No backends registered with router"
            }
        
        # Test routing with different strategies
        test_results = {}
        
        # Create test content info
        test_content = [
            {
                "name": "small_image",
                "content_info": {
                    "content_type": "image/jpeg",
                    "filename": "test.jpg",
                    "size_bytes": 100000
                }
            },
            {
                "name": "large_video",
                "content_info": {
                    "content_type": "video/mp4",
                    "filename": "test.mp4",
                    "size_bytes": 500000000
                }
            },
            {
                "name": "document",
                "content_info": {
                    "content_type": "application/pdf",
                    "filename": "test.pdf",
                    "size_bytes": 2000000
                }
            }
        ]
        
        # Test with each routing strategy
        for strategy in RoutingStrategy:
            strategy_results = {}
            
            for test in test_content:
                try:
                    selected_backend = router.get_backend_for_content(
                        test["content_info"],
                        strategy
                    )
                    
                    strategy_results[test["name"]] = {
                        "selected_backend": selected_backend,
                        "success": True
                    }
                except Exception as e:
                    strategy_results[test["name"]] = {
                        "success": False,
                        "error": str(e)
                    }
            
            test_results[strategy.value] = strategy_results
        
        # Get enhanced router and test network-aware routing
        enhanced_router = get_enhanced_router_instance()
        if enhanced_router:
            # Test network-aware routing
            try:
                # Update fake network metrics
                for backend in router.backends:
                    enhanced_router.update_network_metrics(
                        backend_name=backend,
                        latency_ms=50.0,
                        bandwidth_mbps=100.0
                    )
                
                # Test routing
                selected_backend = enhanced_router.get_backend_for_content(
                    test_content[0]["content_info"],
                    RoutingStrategy.HYBRID
                )
                
                test_results["network_aware"] = {
                    "selected_backend": selected_backend,
                    "success": True
                }
            except Exception as e:
                test_results["network_aware"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Verify successful test results
        all_successful = all(
            all(test["success"] for test in strategy_results.values())
            for strategy_results in test_results.values()
        )
        
        return {
            "success": all_successful,
            "message": "Optimized routing verification completed",
            "test_results": test_results,
            "registered_backends": list(router.backends),
            "default_strategy": router.default_strategy.value
        }
        
    except Exception as e:
        logger.error(f"Error verifying optimized data routing: {e}")
        return {
            "success": False,
            "message": f"Error verifying optimized data routing: {e}"
        }