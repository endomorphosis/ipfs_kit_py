"""
MCP extensions integration module.

This module provides unified access to all MCP extensions and handles
updating storage backends status information.
"""

import logging
import importlib.util
import sys
import os
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dictionary to track extension availability
extensions = {
    "huggingface": False,
    "s3": False,
    "filecoin": False,
    "storacha": False,
    "lassie": False,
    "migration": False,
    "metrics": False,
    "auth": False,
    "routing": False,
    "search": False,
    "websocket": False,
    "udm": False,
    "webrtc": False
}

# Try to import each extension
def _import_extension(name: str) -> bool:
    """
    Import an extension module if available.
    
    Args:
        name: Name of the extension
        
    Returns:
        bool: True if imported successfully
    """
    try:
        # Check if the extension file exists
        file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            f"{name}_extension.py"
        )
        if not os.path.exists(file_path):
            logger.warning(f"Extension file not found: {file_path}")
            return False
            
        # Import the extension
        if f"mcp_extensions.{name}_extension" in sys.modules:
            logger.debug(f"Extension {name} already imported")
            return True
            
        spec = importlib.util.spec_from_file_location(
            f"mcp_extensions.{name}_extension", 
            file_path
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for extension: {name}")
            return False
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[f"mcp_extensions.{name}_extension"] = module
        logger.info(f"Successfully imported extension: {name}")
        return True
    except Exception as e:
        logger.error(f"Error importing extension {name}: {e}")
        return False

# Import all available extensions
for ext_name in extensions:
    extensions[ext_name] = _import_extension(ext_name)

def create_extension_routers(api_prefix: str) -> List:
    """
    Create FastAPI routers for all available extensions.
    
    Args:
        api_prefix: API prefix for the endpoints
        
    Returns:
        List of extension routers
    """
    routers = []
    
    # Create HuggingFace router if available
    if extensions["huggingface"]:
        try:
            from mcp_extensions.huggingface_extension import create_huggingface_router
            routers.append(create_huggingface_router(api_prefix))
            logger.info("Added HuggingFace router")
        except Exception as e:
            logger.error(f"Error creating HuggingFace router: {e}")
    
    # Create S3 router if available
    if extensions["s3"]:
        try:
            from mcp_extensions.s3_extension import create_s3_router
            routers.append(create_s3_router(api_prefix))
            logger.info("Added S3 router")
        except Exception as e:
            logger.error(f"Error creating S3 router: {e}")
    
    # Create Filecoin router if available
    if extensions["filecoin"]:
        try:
            from mcp_extensions.filecoin_extension import create_filecoin_router
            filecoin_routers = create_filecoin_router(api_prefix)
            
            # Handle case where the extension returns multiple routers
            if isinstance(filecoin_routers, list):
                for router in filecoin_routers:
                    routers.append(router)
                    logger.info(f"Added Filecoin router: {router.prefix}")
            else:
                routers.append(filecoin_routers)
                logger.info("Added Filecoin router")
        except Exception as e:
            logger.error(f"Error creating Filecoin router: {e}")
    
    # Create Storacha router if available
    if extensions["storacha"]:
        try:
            from mcp_extensions.storacha_extension import create_storacha_router
            routers.append(create_storacha_router(api_prefix))
            logger.info("Added Storacha router")
        except Exception as e:
            logger.error(f"Error creating Storacha router: {e}")
    
    # Create Lassie router if available
    if extensions["lassie"]:
        try:
            from mcp_extensions.lassie_extension import create_lassie_router
            routers.append(create_lassie_router(api_prefix))
            logger.info("Added Lassie router")
        except Exception as e:
            logger.error(f"Error creating Lassie router: {e}")
    
    # Create Migration router if available
    if extensions["migration"]:
        try:
            from mcp_extensions.migration_extension import create_migration_router
            routers.append(create_migration_router(api_prefix))
            logger.info("Added Migration router")
        except Exception as e:
            logger.error(f"Error creating Migration router: {e}")
    
    # Create Metrics router if available
    if extensions["metrics"]:
        try:
            from mcp_extensions.metrics_extension import create_metrics_router
            routers.append(create_metrics_router(api_prefix))
            logger.info("Added Metrics router")
        except Exception as e:
            logger.error(f"Error creating Metrics router: {e}")
    
    # Create Authentication router if available
    # if extensions["auth"]: # Commented out due to missing mcp_auth module
    #     try:
    #         from mcp_extensions.auth_extension import create_auth_router
    #         routers.append(create_auth_router(api_prefix))
    #         logger.info("Added Authentication router")
    #     except Exception as e:
    #         logger.error(f"Error creating Authentication router: {e}")
    
    # Create Routing router if available
    if extensions["routing"]:
        try:
            from mcp_extensions.routing_extension import create_routing_router
            routers.append(create_routing_router(api_prefix))
            logger.info("Added Routing router")
        except Exception as e:
            logger.error(f"Error creating Routing router: {e}")
    
    # Create Search router if available
    if extensions["search"]:
        try:
            from mcp_extensions.search_extension import create_search_router_wrapper
            routers.append(create_search_router_wrapper(api_prefix))
            logger.info("Added Search router")
        except Exception as e:
            logger.error(f"Error creating Search router: {e}")
    
    # Create WebSocket REST router if available
    # Note: WebSocket routes are registered directly with the app elsewhere
    if extensions["websocket"]:
        try:
            from mcp_extensions.websocket_extension import create_websocket_extension_router
            websocket_router, rest_router = create_websocket_extension_router(api_prefix)
            if rest_router:
                routers.append(rest_router)
                logger.info("Added WebSocket REST router")
        except Exception as e:
            logger.error(f"Error creating WebSocket router: {e}")
    
    # Create WebRTC router if available
    # Note: WebRTC WebSocket routes are registered directly with the app elsewhere
    if extensions["webrtc"]:
        try:
            from mcp_extensions.webrtc_extension import create_webrtc_extension_router
            webrtc_router = create_webrtc_extension_router(api_prefix)
            if webrtc_router:
                routers.append(webrtc_router)
                logger.info("Added WebRTC router")
        except Exception as e:
            logger.error(f"Error creating WebRTC router: {e}")
    
    # Create Unified Data Management router if available
    if extensions["udm"]:
        try:
            from mcp_extensions.udm_extension import create_udm_router
            routers.append(create_udm_router(api_prefix))
            logger.info("Added Unified Data Management router")
        except Exception as e:
            logger.error(f"Error creating Unified Data Management router: {e}")
    
    return routers

def update_storage_backends(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with status from all extensions.
    
    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Update HuggingFace status
    if extensions["huggingface"]:
        try:
            from mcp_extensions.huggingface_extension import update_huggingface_status
            update_huggingface_status(storage_backends)
            logger.debug("Updated HuggingFace storage backend status")
        except Exception as e:
            logger.error(f"Error updating HuggingFace status: {e}")
    
    # Update S3 status
    if extensions["s3"]:
        try:
            from mcp_extensions.s3_extension import update_s3_status
            update_s3_status(storage_backends)
            logger.debug("Updated S3 storage backend status")
        except Exception as e:
            logger.error(f"Error updating S3 status: {e}")
    
    # Update Filecoin status
    if extensions["filecoin"]:
        try:
            from mcp_extensions.filecoin_extension import update_filecoin_status
            update_filecoin_status(storage_backends)
            logger.debug("Updated Filecoin storage backend status")
        except Exception as e:
            logger.error(f"Error updating Filecoin status: {e}")
    
    # Update Storacha status
    if extensions["storacha"]:
        try:
            from mcp_extensions.storacha_extension import update_storacha_status
            update_storacha_status(storage_backends)
            logger.debug("Updated Storacha storage backend status")
        except Exception as e:
            logger.error(f"Error updating Storacha status: {e}")
    
    # Update Lassie status
    if extensions["lassie"]:
        try:
            from mcp_extensions.lassie_extension import update_lassie_status
            update_lassie_status(storage_backends)
            logger.debug("Updated Lassie storage backend status")
        except Exception as e:
            logger.error(f"Error updating Lassie status: {e}")
            
    # Update Migration status
    if extensions["migration"]:
        try:
            from mcp_extensions.migration_extension import update_migration_status
            update_migration_status(storage_backends)
            logger.debug("Updated Migration extension with backend status")
        except Exception as e:
            logger.error(f"Error updating Migration extension: {e}")
            
    # Update Metrics status
    if extensions["metrics"]:
        try:
            from mcp_extensions.metrics_extension import update_metrics_status
            update_metrics_status(storage_backends)
            logger.debug("Updated Metrics extension with backend status")
        except Exception as e:
            logger.error(f"Error updating Metrics extension: {e}")
            
    # Update Routing status
    if extensions["routing"]:
        try:
            from mcp_extensions.routing_extension import update_routing_status
            update_routing_status(storage_backends)
            logger.debug("Updated Routing extension with backend status")
        except Exception as e:
            logger.error(f"Error updating Routing extension: {e}")
            
    # Update Search status
    if extensions["search"]:
        try:
            from mcp_extensions.search_extension import update_search_status
            update_search_status(storage_backends)
            logger.debug("Updated Search extension with backend status")
        except Exception as e:
            logger.error(f"Error updating Search extension: {e}")
            
    # Update WebSocket status
    if extensions["websocket"]:
        try:
            from mcp_extensions.websocket_extension import update_websocket_status
            update_websocket_status(storage_backends)
            logger.debug("Updated WebSocket extension with backend status")
        except Exception as e:
            logger.error(f"Error updating WebSocket extension: {e}")
    
    # Update WebRTC status
    if extensions["webrtc"]:
        try:
            from mcp_extensions.webrtc_extension import update_webrtc_status
            update_webrtc_status(storage_backends)
            logger.debug("Updated WebRTC extension with backend status")
        except Exception as e:
            logger.error(f"Error updating WebRTC extension: {e}")
            
    # Update Unified Data Management status
    if extensions["udm"]:
        try:
            from mcp_extensions.udm_extension import update_udm_status
            update_udm_status(storage_backends)
            logger.debug("Updated Unified Data Management extension with backend status")
        except Exception as e:
            logger.error(f"Error updating Unified Data Management extension: {e}")
