"""
MCP Server Integrator Package

This package contains modules for integrating various components with the MCP server.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-integrator")

# Expose the AI/ML integrator function
try:
    from .ai_ml_integrator import integrate_ai_ml_with_mcp_server
    HAS_AI_ML_INTEGRATION = True
except ImportError:
    # Define a placeholder if the module is not available
    HAS_AI_ML_INTEGRATION = False
    def integrate_ai_ml_with_mcp_server(app: Any, get_current_user=None) -> bool:
        """Placeholder for AI/ML integration when the module is not available."""
        logger.warning("AI/ML integration module not available")
        return False

# Expose the High Availability integrator
try:
    from .ha_integrator import get_ha_integration, HAIntegration
    HAS_HA_INTEGRATION = True
except ImportError:
    # Define placeholders if the module is not available
    HAS_HA_INTEGRATION = False
    def get_ha_integration() -> Any:
        """Placeholder for HA integration when the module is not available."""
        logger.warning("High Availability integration module not available")
        return None

async def integrate_ha_with_mcp_server(app: Any, 
                                     config_path: Optional[str] = None,
                                     node_id: Optional[str] = None, 
                                     redis_url: Optional[str] = None) -> bool:
    """
    Integrate High Availability components with the MCP server.
    
    Args:
        app: The FastAPI or Starlette application instance
        config_path: Path to the HA configuration file
        node_id: ID of the local node
        redis_url: URL of the Redis server for distributed state
        
    Returns:
        True if integration was successful, False otherwise
    """
    if not HAS_HA_INTEGRATION:
        logger.warning("High Availability integration module not available")
        return False
    
    try:
        # Get HA integration instance
        ha_integration = get_ha_integration()
        
        # Set configuration if provided
        if config_path:
            ha_integration.config_path = config_path
        if node_id:
            ha_integration.node_id = node_id
        if redis_url:
            ha_integration.redis_url = redis_url
        
        # Initialize the integration
        success = await ha_integration.initialize()
        
        if success:
            # Add API router to app if available
            router = ha_integration.get_api_router()
            if router:
                # Check if the app has the include_router method (FastAPI)
                if hasattr(app, 'include_router'):
                    # FastAPI app
                    app.include_router(router)
                    logger.info("Added HA router to FastAPI app")
                elif hasattr(app, 'routes'):
                    # Starlette app
                    from starlette.routing import Mount
                    from starlette.applications import Starlette
                    
                    # Create a sub-application for the HA routes
                    ha_app = Starlette()
                    ha_app.routes = router.routes
                    
                    # Mount the sub-application
                    app.routes.append(Mount("/api/v0/ha", app=ha_app))
                    logger.info("Mounted HA router to Starlette app")
                else:
                    logger.error("Unsupported application type. Cannot add HA router.")
                    return False
            
            logger.info("High Availability integration completed successfully")
            return True
        else:
            logger.error("Failed to initialize High Availability integration")
            return False
    
    except Exception as e:
        logger.error(f"Error integrating High Availability components: {e}")
        return False

# Function to register all available integrators with an MCP server app
async def register_all_integrators(app: Any, options: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
    """
    Register all available integrators with the given MCP server app.
    
    Args:
        app: The FastAPI or Starlette application instance
        options: Optional configuration options for the integrators
        
    Returns:
        A dictionary mapping integrator names to their success status
    """
    options = options or {}
    results = {}
    
    # Register AI/ML integrator
    if options.get("enable_ai_ml", True):
        results["ai_ml"] = integrate_ai_ml_with_mcp_server(
            app, 
            get_current_user=options.get("get_current_user")
        )
    
    # Register High Availability integrator
    if options.get("enable_ha", True):
        results["ha"] = await integrate_ha_with_mcp_server(
            app,
            config_path=options.get("ha_config_path"),
            node_id=options.get("ha_node_id"),
            redis_url=options.get("ha_redis_url")
        )
    
    return results