#!/usr/bin/env python3
"""
MCP Tools for Backend Management.

Provides MCP server tools for managing storage backends (S3, IPFS, Storj, etc.),
following the architecture pattern:
  Core Module (backend_manager.py) → MCP Integration → MCP Server → JS SDK → Dashboard
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Define MCP tools for backend management
BACKEND_MCP_TOOLS = [
    {
        "name": "backend_create",
        "description": "Create a new storage backend configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name for the backend"
                },
                "backend_type": {
                    "type": "string",
                    "enum": ["s3", "ipfs", "storj", "storacha", "local", "custom"],
                    "description": "Type of storage backend"
                },
                "config": {
                    "type": "object",
                    "description": "Backend-specific configuration",
                    "properties": {
                        "endpoint": {"type": "string", "description": "Backend endpoint URL"},
                        "access_key": {"type": "string", "description": "Access key"},
                        "secret_key": {"type": "string", "description": "Secret key"},
                        "token": {"type": "string", "description": "Authentication token"},
                        "bucket": {"type": "string", "description": "Bucket name"},
                        "region": {"type": "string", "description": "Region"}
                    },
                    "additionalProperties": true
                }
            },
            "required": ["name", "backend_type"]
        }
    },
    {
        "name": "backend_list",
        "description": "List all configured storage backends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_disabled": {
                    "type": "boolean",
                    "description": "Include disabled backends",
                    "default": true
                }
            },
            "required": []
        }
    },
    {
        "name": "backend_get_info",
        "description": "Get detailed information about a specific backend",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Backend name"
                },
                "include_sensitive": {
                    "type": "boolean",
                    "description": "Include sensitive configuration values",
                    "default": false
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "backend_update",
        "description": "Update backend configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Backend name to update"
                },
                "config": {
                    "type": "object",
                    "description": "Configuration values to update",
                    "additionalProperties": true
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Enable or disable the backend"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "backend_delete",
        "description": "Delete a backend configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Backend name to delete"
                },
                "force": {
                    "type": "boolean",
                    "description": "Force delete even if backend has active pins",
                    "default": false
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "backend_test_connection",
        "description": "Test connection to a backend",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Backend name to test"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "backend_get_statistics",
        "description": "Get statistics for a backend",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Backend name"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "backend_list_pin_mappings",
        "description": "List pin mappings for a backend",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Backend name"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of mappings to return",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 10000
                }
            },
            "required": ["name"]
        }
    }
]


async def handle_backend_create(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_create MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        
        name = arguments.get("name")
        backend_type = arguments.get("backend_type")
        config = arguments.get("config", {})
        
        if not name or not backend_type:
            return {
                "success": False,
                "error": "name and backend_type are required"
            }
        
        result = await backend_manager.create_backend_config(
            backend_name=name,
            backend_type=backend_type,
            config=config
        )
        
        return result
    except Exception as e:
        logger.error(f"Error creating backend: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_list(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_list MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        include_disabled = arguments.get("include_disabled", True)
        
        result = await backend_manager.list_backend_configs()
        
        if result["success"]:
            backends = result["data"]["backends"]
            
            # Filter disabled if requested
            if not include_disabled:
                backends = [b for b in backends if b.get("enabled", True)]
            
            return {
                "success": True,
                "backends": backends,
                "count": len(backends)
            }
        
        return result
    except Exception as e:
        logger.error(f"Error listing backends: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_get_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_get_info MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        name = arguments.get("name")
        include_sensitive = arguments.get("include_sensitive", False)
        
        if not name:
            return {
                "success": False,
                "error": "name is required"
            }
        
        result = await backend_manager.get_backend_config(name)
        
        if result["success"] and not include_sensitive:
            # Hide sensitive configuration values
            config = result["data"]["backend_config"]
            backend_config = config.get("config", {})
            
            for key in list(backend_config.keys()):
                if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'token', 'password']):
                    backend_config[key] = "***HIDDEN***"
        
        return result
    except Exception as e:
        logger.error(f"Error getting backend info: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_update(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_update MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        name = arguments.get("name")
        config = arguments.get("config", {})
        enabled = arguments.get("enabled")
        
        if not name:
            return {
                "success": False,
                "error": "name is required"
            }
        
        result = await backend_manager.update_backend_config(
            backend_name=name,
            config=config,
            enabled=enabled
        )
        
        return result
    except Exception as e:
        logger.error(f"Error updating backend: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_delete(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_delete MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        name = arguments.get("name")
        force = arguments.get("force", False)
        
        if not name:
            return {
                "success": False,
                "error": "name is required"
            }
        
        result = await backend_manager.delete_backend_config(
            backend_name=name,
            force=force
        )
        
        return result
    except Exception as e:
        logger.error(f"Error deleting backend: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_test_connection(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_test_connection MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        name = arguments.get("name")
        
        if not name:
            return {
                "success": False,
                "error": "name is required"
            }
        
        result = await backend_manager.test_backend_connection(name)
        
        return result
    except Exception as e:
        logger.error(f"Error testing backend connection: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_get_statistics(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_get_statistics MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        name = arguments.get("name")
        
        if not name:
            return {
                "success": False,
                "error": "name is required"
            }
        
        result = await backend_manager.get_backend_statistics(name)
        
        return result
    except Exception as e:
        logger.error(f"Error getting backend statistics: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_backend_list_pin_mappings(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend_list_pin_mappings MCP tool call."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        name = arguments.get("name")
        limit = arguments.get("limit", 100)
        
        if not name:
            return {
                "success": False,
                "error": "name is required"
            }
        
        result = await backend_manager.list_pin_mappings(name, limit=limit)
        
        return result
    except Exception as e:
        logger.error(f"Error listing pin mappings: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# Handler mapping for MCP server
BACKEND_TOOL_HANDLERS = {
    "backend_create": handle_backend_create,
    "backend_list": handle_backend_list,
    "backend_get_info": handle_backend_get_info,
    "backend_update": handle_backend_update,
    "backend_delete": handle_backend_delete,
    "backend_test_connection": handle_backend_test_connection,
    "backend_get_statistics": handle_backend_get_statistics,
    "backend_list_pin_mappings": handle_backend_list_pin_mappings,
}
