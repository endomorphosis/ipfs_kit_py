"""
MCP Feature Integration Module

This module integrates the implemented roadmap features with the MCP server:
- Advanced IPFS Operations
- Enhanced Metrics & Monitoring
- Optimized Data Routing
- Advanced Authentication & Authorization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, APIRouter

logger = logging.getLogger("mcp_integration")

class MCPFeatureIntegration:
    """
    Integrates roadmap features with the MCP server.
    
    This class handles the registration of all implemented feature
    components with the main MCP server application.
    """
    
    def __init__(self, app: FastAPI, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the integration module.
        
        Args:
            app: FastAPI application instance
            config: Optional configuration dictionary
        """
        self.app = app
        self.config = config or {}
        self.registered_features = set()
        
        logger.info("MCP Feature Integration initialized")
    
    def register_all_features(self) -> None:
        """Register all available roadmap features."""
        # Register features in a specific order to handle dependencies
        self.register_auth_feature()
        self.register_monitoring_feature()
        self.register_advanced_ipfs_feature()
        self.register_optimized_routing_feature()
        self.register_ai_ml_feature()
        
        logger.info(f"Registered features: {', '.join(self.registered_features)}")
    
    def register_auth_feature(self) -> None:
        """Register the Advanced Authentication & Authorization feature."""
        try:
            # Import the auth router
            from ipfs_kit_py.mcp.auth.router import router as auth_router
            from ipfs_kit_py.mcp.auth.router import register_auth_middleware
            
            # Register the router with the application
            self.app.include_router(auth_router)
            
            # Register the authentication middleware
            register_auth_middleware(self.app)
            
            # Initialize the auth service
            from ipfs_kit_py.mcp.auth.service import get_instance as get_auth_service
            auth_service = get_auth_service(self.config.get("auth", {}))
            
            self.registered_features.add("auth")
            logger.info("Registered Auth feature")
            
        except ImportError as e:
            logger.warning(f"Could not register Auth feature: {e}")
        except Exception as e:
            logger.error(f"Error registering Auth feature: {e}")
    
    def register_monitoring_feature(self) -> None:
        """Register the Enhanced Metrics & Monitoring feature."""
        try:
            # Import the metrics router
            from ipfs_kit_py.mcp.monitoring.metrics_router import router as metrics_router
            
            # Register the router with the application
            self.app.include_router(metrics_router)
            
            # Initialize the metrics service
            from ipfs_kit_py.mcp.monitoring.metrics import get_instance as get_metrics
            metrics = get_metrics(self.config.get("metrics", {}))
            
            # Start metrics collection
            metrics.start_collection()
            
            self.registered_features.add("monitoring")
            logger.info("Registered Monitoring feature")
            
            # Add middleware to track API requests
            from fastapi import Request
            from starlette.middleware.base import BaseHTTPMiddleware
            import time
            
            class MetricsMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):
                    start_time = time.time()
                    
                    # Process the request
                    response = await call_next(request)
                    
                    # Record metrics
                    duration = time.time() - start_time
                    metrics.track_api_request(
                        endpoint=request.url.path,
                        method=request.method,
                        status_code=response.status_code,
                        duration=duration,
                        content_type=response.headers.get("content-type")
                    )
                    
                    return response
            
            self.app.add_middleware(MetricsMiddleware)
            
        except ImportError as e:
            logger.warning(f"Could not register Monitoring feature: {e}")
        except Exception as e:
            logger.error(f"Error registering Monitoring feature: {e}")
    
    def register_advanced_ipfs_feature(self) -> None:
        """Register the Advanced IPFS Operations feature."""
        try:
            # Import the IPFS advanced router
            from ipfs_kit_py.mcp.extensions.ipfs_advanced_router import router as ipfs_advanced_router
            
            # Register the router with the application
            self.app.include_router(ipfs_advanced_router)
            
            # Initialize the IPFS advanced operations
            from ipfs_kit_py.mcp.extensions.ipfs_advanced import get_instance as get_ipfs_advanced
            ipfs_advanced = get_ipfs_advanced()
            
            self.registered_features.add("advanced_ipfs")
            logger.info("Registered Advanced IPFS feature")
            
        except ImportError as e:
            logger.warning(f"Could not register Advanced IPFS feature: {e}")
        except Exception as e:
            logger.error(f"Error registering Advanced IPFS feature: {e}")
    
    def register_optimized_routing_feature(self) -> None:
        """Register the Optimized Data Routing feature."""
        try:
            # Import the router (if we have one, otherwise just the core module)
            from ipfs_kit_py.mcp.routing.optimized_router import get_instance as get_router
            
            # Initialize the router
            router = get_router(self.config.get("routing", {}))
            
            # Register available backends
            if "storage_backends" in self.config:
                for backend_name in self.config["storage_backends"]:
                    router.register_backend(backend_name)
            
            # Start background updates
            router.start_updates()
            
            # Create a router endpoint
            router_api = APIRouter(prefix="/api/v0/routing", tags=["routing"])
            
            @router_api.get("/status", summary="Get routing status")
            async def get_routing_status():
                """Get the current status of the optimized router."""
                return {
                    "registered_backends": list(router.backends),
                    "default_strategy": router.default_strategy.value,
                    "current_region": router.current_region
                }
            
            @router_api.get("/backends", summary="Get backend stats")
            async def get_backend_stats(backend_name: Optional[str] = None):
                """Get statistics for storage backends."""
                return router.get_backend_stats(backend_name)
            
            @router_api.get("/mappings", summary="Get route mappings")
            async def get_route_mappings(content_category: Optional[str] = None):
                """Get content category to backend mappings."""
                return router.get_route_mappings(content_category)
            
            @router_api.get("/suggestions", summary="Get suggested routing weights")
            async def get_routing_suggestions():
                """Get suggested routing weights based on performance metrics."""
                return router.suggest_backend_weights()
            
            # Register the router with the application
            self.app.include_router(router_api)
            
            self.registered_features.add("optimized_routing")
            logger.info("Registered Optimized Routing feature")
            
        except ImportError as e:
            logger.warning(f"Could not register Optimized Routing feature: {e}")
        except Exception as e:
            logger.error(f"Error registering Optimized Routing feature: {e}")
    
    def register_ai_ml_feature(self) -> None:
        """Register the AI/ML Integration feature."""
        try:
            # Import the AI/ML integrator
            from ipfs_kit_py.mcp.ai.ai_ml_integrator import get_instance as get_ai_ml
            
            # Initialize the AI/ML components
            ai_ml = get_ai_ml(config=self.config.get("ai_ml", {}))
            
            # Initialize components
            if not ai_ml.initialized:
                ai_ml.initialize()
            
            # Register the AI/ML router with the application
            ai_ml.register_with_server(self.app, prefix="/api/v0/ai")
            
            # Store reference to AI/ML integrator on app for access in other parts
            self.app._ai_ml_integrator = ai_ml
            
            self.registered_features.add("ai_ml")
            logger.info("Registered AI/ML Integration feature")
            
        except ImportError as e:
            logger.warning(f"Could not register AI/ML Integration feature: {e}")
        except Exception as e:
            logger.error(f"Error registering AI/ML Integration feature: {e}")
    
    def shutdown(self) -> None:
        """Shutdown and cleanup all registered features."""
        # Shutdown monitoring
        if "monitoring" in self.registered_features:
            try:
                from ipfs_kit_py.mcp.monitoring.metrics import get_instance as get_metrics
                metrics = get_metrics()
                metrics.stop_collection()
                logger.info("Stopped metrics collection")
            except Exception as e:
                logger.error(f"Error stopping metrics collection: {e}")
        
        # Shutdown routing
        if "optimized_routing" in self.registered_features:
            try:
                from ipfs_kit_py.mcp.routing.optimized_router import get_instance as get_router
                router = get_router()
                router.stop_updates()
                logger.info("Stopped routing updates")
            except Exception as e:
                logger.error(f"Error stopping routing updates: {e}")
        
        # Shutdown AI/ML
        if "ai_ml" in self.registered_features:
            try:
                # Clean up any AI/ML resources if needed
                if hasattr(self.app, "_ai_ml_integrator"):
                    # Currently no specific cleanup needed, but adding the hook for future use
                    logger.info("Stopped AI/ML services")
            except Exception as e:
                logger.error(f"Error stopping AI/ML services: {e}")
        
        logger.info("MCP Feature Integration shutdown complete")


# Singleton instance for integration with MCP server
_instance = None

def get_integrator(app=None, config=None):
    """Get or create the MCP feature integrator."""
    global _instance
    if _instance is None and app is not None:
        _instance = MCPFeatureIntegration(app, config)
    return _instance