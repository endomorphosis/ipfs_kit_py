"""
MCP Server Tools for Secrets Management

Exposes secrets management functionality including AES-256-GCM encryption
to the MCP server for consumption by CLI tools and JavaScript SDK.

Architecture:
  ipfs_kit_py.aes_encryption          (core module)
  ipfs_kit_py.enhanced_secrets_manager (core module)
       ↓
  ipfs_kit_py.mcp.servers.secrets_mcp_tools (MCP server layer)
       ↓
  mcp.secrets_mcp_tools                (compatibility shim)
       ↓
  MCP Server → JavaScript SDK → Dashboard
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from dataclasses import asdict

# Import core functionality from ipfs_kit_py package
try:
    from ipfs_kit_py.enhanced_secrets_manager import (
        EnhancedSecretManager,
        SecretType,
        AES_ENCRYPTION_AVAILABLE,
    )
    from ipfs_kit_py.aes_encryption import MultiVersionEncryption
    SECRETS_AVAILABLE = True
except ImportError:
    SECRETS_AVAILABLE = False

# MCP types
try:
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    # Fallback for when MCP is not available
    Tool = Dict[str, Any]  # type: ignore
    TextContent = Dict[str, Any]  # type: ignore
    MCP_AVAILABLE = False


# Global secrets manager instance
_secrets_manager: Optional[EnhancedSecretManager] = None


def get_secrets_manager(
    storage_path: str = "~/.ipfs_kit/secrets",
    encryption_method: str = "aes-gcm"
) -> EnhancedSecretManager:
    """
    Get or create the global secrets manager instance.
    
    Args:
        storage_path: Path to secrets storage
        encryption_method: Encryption method ("aes-gcm" or "xor")
        
    Returns:
        EnhancedSecretManager instance
    """
    global _secrets_manager
    
    if _secrets_manager is None:
        _secrets_manager = EnhancedSecretManager(
            storage_path=storage_path,
            encryption_method=encryption_method,
        )
    
    return _secrets_manager


def create_secrets_tools() -> List[Tool]:
    """
    Create MCP tools for secrets management.
    
    Returns:
        List of MCP Tool definitions
    """
    if not SECRETS_AVAILABLE:
        return []
    
    tools = [
        Tool(
            name="secrets_store",
            description=(
                "Store a secret with AES-256-GCM encryption. "
                "Secrets are encrypted with production-grade security including "
                "PBKDF2 key derivation, random salt, and authenticated encryption."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name for the secret"
                    },
                    "secret_value": {
                        "type": "string",
                        "description": "Secret value to store (will be encrypted)"
                    },
                    "secret_type": {
                        "type": "string",
                        "enum": ["api_key", "password", "token", "certificate", "private_key", "connection_string"],
                        "description": "Type of secret",
                        "default": "api_key"
                    },
                    "expires_in": {
                        "type": "number",
                        "description": "Expiration time in seconds (optional)"
                    },
                    "rotation_interval": {
                        "type": "number",
                        "description": "Rotation interval in seconds (optional)"
                    }
                },
                "required": ["service", "secret_value"]
            }
        ),
        Tool(
            name="secrets_retrieve",
            description="Retrieve a secret by ID. Automatically decrypts the secret value.",
            inputSchema={
                "type": "object",
                "properties": {
                    "secret_id": {
                        "type": "string",
                        "description": "ID of the secret to retrieve"
                    }
                },
                "required": ["secret_id"]
            }
        ),
        Tool(
            name="secrets_rotate",
            description="Rotate a secret to a new value while keeping the same ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "secret_id": {
                        "type": "string",
                        "description": "ID of the secret to rotate"
                    },
                    "new_value": {
                        "type": "string",
                        "description": "New secret value"
                    }
                },
                "required": ["secret_id", "new_value"]
            }
        ),
        Tool(
            name="secrets_delete",
            description="Delete a secret by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "secret_id": {
                        "type": "string",
                        "description": "ID of the secret to delete"
                    }
                },
                "required": ["secret_id"]
            }
        ),
        Tool(
            name="secrets_list",
            description="List all secrets with their metadata (excluding secret values).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="secrets_migrate",
            description=(
                "Migrate all secrets from legacy XOR encryption to AES-256-GCM. "
                "This upgrades security for all stored secrets."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="secrets_statistics",
            description="Get statistics about stored secrets including encryption versions.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="secrets_encryption_info",
            description="Get encryption information for a specific secret.",
            inputSchema={
                "type": "object",
                "properties": {
                    "secret_id": {
                        "type": "string",
                        "description": "ID of the secret"
                    }
                },
                "required": ["secret_id"]
            }
        ),
    ]
    
    return tools


def _text(payload: Dict[str, Any]) -> List[TextContent]:
    """Helper to format response as text content."""
    return [TextContent(type="text", text=json.dumps(payload, indent=2))]


async def handle_secrets_store(arguments: Dict[str, Any]):
    """Handle secrets_store tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        service = arguments.get("service")
        secret_value = arguments.get("secret_value")
        secret_type_str = arguments.get("secret_type", "api_key")
        expires_in = arguments.get("expires_in")
        rotation_interval = arguments.get("rotation_interval")
        
        if not service or not secret_value:
            return _text({"success": False, "error": "Missing required arguments"})
        
        # Convert string to SecretType enum
        secret_type = SecretType(secret_type_str)
        
        manager = get_secrets_manager()
        secret_id = manager.store_secret(
            service=service,
            secret_value=secret_value,
            secret_type=secret_type,
            expires_in=expires_in,
            rotation_interval=rotation_interval,
        )
        
        return _text({
            "success": True,
            "secret_id": secret_id,
            "service": service,
            "encryption": "AES-256-GCM" if AES_ENCRYPTION_AVAILABLE else "XOR (legacy)"
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_retrieve(arguments: Dict[str, Any]):
    """Handle secrets_retrieve tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        secret_id = arguments.get("secret_id")
        if not secret_id:
            return _text({"success": False, "error": "Missing secret_id"})
        
        manager = get_secrets_manager()
        secret_value = manager.retrieve_secret(secret_id)
        
        if secret_value is None:
            return _text({
                "success": False,
                "error": "Secret not found or expired"
            })
        
        return _text({
            "success": True,
            "secret_id": secret_id,
            "secret_value": secret_value
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_rotate(arguments: Dict[str, Any]):
    """Handle secrets_rotate tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        secret_id = arguments.get("secret_id")
        new_value = arguments.get("new_value")
        
        if not secret_id or not new_value:
            return _text({"success": False, "error": "Missing required arguments"})
        
        manager = get_secrets_manager()
        success = manager.rotate_secret(secret_id, new_value)
        
        return _text({
            "success": success,
            "secret_id": secret_id,
            "message": "Secret rotated successfully" if success else "Failed to rotate secret"
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_delete(arguments: Dict[str, Any]):
    """Handle secrets_delete tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        secret_id = arguments.get("secret_id")
        if not secret_id:
            return _text({"success": False, "error": "Missing secret_id"})
        
        manager = get_secrets_manager()
        success = manager.delete_secret(secret_id)
        
        return _text({
            "success": success,
            "secret_id": secret_id,
            "message": "Secret deleted successfully" if success else "Secret not found"
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_list(arguments: Dict[str, Any]):
    """Handle secrets_list tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        manager = get_secrets_manager()
        
        secrets_list = []
        for secret_id, metadata in manager.metadata.items():
            secrets_list.append({
                "secret_id": secret_id,
                "service": metadata.service,
                "secret_type": metadata.secret_type.value,
                "created_at": metadata.created_at,
                "last_rotated": metadata.last_rotated,
                "last_accessed": metadata.last_accessed,
                "access_count": metadata.access_count,
                "expires_at": metadata.expires_at,
            })
        
        return _text({
            "success": True,
            "count": len(secrets_list),
            "secrets": secrets_list
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_migrate(arguments: Dict[str, Any]):
    """Handle secrets_migrate tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    if not AES_ENCRYPTION_AVAILABLE:
        return _text({
            "success": False,
            "error": "AES encryption not available. Install cryptography library."
        })
    
    try:
        manager = get_secrets_manager()
        result = manager.migrate_all_secrets()
        
        return _text({
            "success": True,
            "migrated": result['migrated'],
            "already_current": result['already_current'],
            "errors": result['errors'],
            "total_secrets": result['total_secrets']
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_statistics(arguments: Dict[str, Any]):
    """Handle secrets_statistics tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        manager = get_secrets_manager()
        stats = manager.get_statistics()
        
        return _text({
            "success": True,
            "statistics": stats
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


async def handle_secrets_encryption_info(arguments: Dict[str, Any]):
    """Handle secrets_encryption_info tool invocation."""
    if not SECRETS_AVAILABLE:
        return _text({"success": False, "error": "Secrets management not available"})
    
    try:
        secret_id = arguments.get("secret_id")
        if not secret_id:
            return _text({"success": False, "error": "Missing secret_id"})
        
        manager = get_secrets_manager()
        info = manager.get_encryption_info(secret_id)
        
        if info is None:
            return _text({"success": False, "error": "Secret not found"})
        
        return _text({
            "success": True,
            "encryption_info": info
        })
        
    except Exception as e:
        return _text({"success": False, "error": str(e)})


# Export handler mapping for easy integration
SECRETS_HANDLERS = {
    "secrets_store": handle_secrets_store,
    "secrets_retrieve": handle_secrets_retrieve,
    "secrets_rotate": handle_secrets_rotate,
    "secrets_delete": handle_secrets_delete,
    "secrets_list": handle_secrets_list,
    "secrets_migrate": handle_secrets_migrate,
    "secrets_statistics": handle_secrets_statistics,
    "secrets_encryption_info": handle_secrets_encryption_info,
}
