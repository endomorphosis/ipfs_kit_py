"""
Advanced Authentication & Authorization Configuration

This module provides configuration helpers for the advanced authentication
and authorization system implemented as part of the MCP roadmap Phase 1.
"""

import os
import secrets
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default configuration paths
DEFAULT_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "auth")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, "auth_config.json")


def generate_default_config() -> Dict[str, Any]:
    """
    Generate default configuration for the authentication system.
    
    Returns:
        Dictionary with default configuration values
    """
    # Generate a random secret key if not set
    jwt_secret = os.environ.get("MCP_JWT_SECRET", secrets.token_hex(32))
    
    config = {
        "jwt": {
            "secret_key": jwt_secret,
            "access_token_expire_minutes": int(os.environ.get("MCP_ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
            "refresh_token_expire_days": int(os.environ.get("MCP_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
        },
        "oauth": {
            "providers": {
                "github": {
                    "enabled": bool(os.environ.get("GITHUB_CLIENT_ID", "")),
                    "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
                    "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
                    "scope": "user:email",
                    "default_roles": ["user"]
                },
                "google": {
                    "enabled": bool(os.environ.get("GOOGLE_CLIENT_ID", "")),
                    "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                    "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                    "scope": "openid email profile",
                    "default_roles": ["user"]
                },
                "microsoft": {
                    "enabled": bool(os.environ.get("MICROSOFT_CLIENT_ID", "")),
                    "client_id": os.environ.get("MICROSOFT_CLIENT_ID", ""),
                    "client_secret": os.environ.get("MICROSOFT_CLIENT_SECRET", ""),
                    "scope": "User.Read",
                    "default_roles": ["user"]
                }
            }
        },
        "api_keys": {
            "prefix": os.environ.get("MCP_API_KEY_PREFIX", "ipfk_"),
            "default_expiration_days": int(os.environ.get("MCP_API_KEY_EXPIRE_DAYS", "365"))
        },
        "persistence": {
            "data_dir": os.environ.get("MCP_AUTH_DATA_DIR", DEFAULT_CONFIG_DIR),
            "use_redis": os.environ.get("MCP_USE_REDIS", "0") == "1",
            "redis_url": os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        },
        "audit": {
            "log_file": os.environ.get("MCP_AUDIT_LOG_FILE", os.path.join(DEFAULT_CONFIG_DIR, "audit.log")),
            "console_logging": os.environ.get("MCP_AUDIT_CONSOLE", "1") == "1",
            "json_logging": True,
            "retention_days": int(os.environ.get("MCP_AUDIT_RETENTION_DAYS", "365"))
        },
        "rbac": {
            "custom_roles_file": os.environ.get("MCP_CUSTOM_ROLES_FILE", os.path.join(DEFAULT_CONFIG_DIR, "custom_roles.json")),
            "permission_defaults_file": os.environ.get("MCP_PERMISSION_DEFAULTS_FILE", os.path.join(DEFAULT_CONFIG_DIR, "permission_defaults.json"))
        }
    }
    
    return config


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file or generate default.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    config_file = config_path or DEFAULT_CONFIG_FILE
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded auth configuration from {config_file}")
                return config
        else:
            config = generate_default_config()
            logger.info(f"Generated default auth configuration")
            
            # Try to save the config
            try:
                os.makedirs(os.path.dirname(config_file), exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                logger.info(f"Saved default auth configuration to {config_file}")
            except Exception as e:
                logger.warning(f"Failed to save default auth configuration: {e}")
            
            return config
    except Exception as e:
        logger.error(f"Error loading auth configuration: {e}")
        return generate_default_config()


def save_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """
    Save configuration to file.
    
    Args:
        config: Configuration dictionary
        config_path: Path to configuration file
        
    Returns:
        True if saved successfully
    """
    config_file = config_path or DEFAULT_CONFIG_FILE
    
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Saved auth configuration to {config_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving auth configuration: {e}")
        return False


def get_config_value(key: str, default: Any = None, config: Optional[Dict[str, Any]] = None) -> Any:
    """
    Get a configuration value by dot-separated key path.
    
    Args:
        key: Dot-separated key path (e.g., "jwt.secret_key")
        default: Default value if key not found
        config: Optional config dict, will load from file if not provided
        
    Returns:
        Configuration value or default
    """
    if config is None:
        config = load_config()
    
    parts = key.split('.')
    value = config
    
    try:
        for part in parts:
            value = value[part]
        return value
    except (KeyError, TypeError):
        return default


def setup_auth_dirs() -> None:
    """Create necessary directories for authentication system."""
    # Create main config directory
    os.makedirs(DEFAULT_CONFIG_DIR, exist_ok=True)
    
    # Create subdirectories
    os.makedirs(os.path.join(DEFAULT_CONFIG_DIR, "users"), exist_ok=True)
    os.makedirs(os.path.join(DEFAULT_CONFIG_DIR, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(DEFAULT_CONFIG_DIR, "api_keys"), exist_ok=True)
    os.makedirs(os.path.join(DEFAULT_CONFIG_DIR, "oauth"), exist_ok=True)
    os.makedirs(os.path.join(DEFAULT_CONFIG_DIR, "logs"), exist_ok=True)
    
    logger.info(f"Created authentication system directories in {DEFAULT_CONFIG_DIR}")


# Environment variable setup function
def print_env_setup_instructions() -> None:
    """Print instructions for setting up environment variables."""
    instructions = """
# Advanced Authentication & Authorization Configuration
# ====================================================
#
# Set the following environment variables to configure the system:

# JWT Configuration
export MCP_JWT_SECRET="your-secret-key-here"  # Set a secure secret key
export MCP_ACCESS_TOKEN_EXPIRE_MINUTES=60     # Access token expiration in minutes
export MCP_REFRESH_TOKEN_EXPIRE_DAYS=7        # Refresh token expiration in days

# OAuth Configuration
# GitHub
export GITHUB_CLIENT_ID="your-github-client-id"
export GITHUB_CLIENT_SECRET="your-github-client-secret"

# Google
export GOOGLE_CLIENT_ID="your-google-client-id"
export GOOGLE_CLIENT_SECRET="your-google-client-secret"

# Microsoft
export MICROSOFT_CLIENT_ID="your-microsoft-client-id"
export MICROSOFT_CLIENT_SECRET="your-microsoft-client-secret"

# API Key Configuration
export MCP_API_KEY_PREFIX="ipfk_"            # Prefix for API keys
export MCP_API_KEY_EXPIRE_DAYS=365           # Default expiration for API keys

# Persistence Configuration
export MCP_AUTH_DATA_DIR="~/.ipfs_kit/auth"  # Directory for auth data
export MCP_USE_REDIS=0                       # Use Redis for persistence (0=no, 1=yes)
export REDIS_URL="redis://localhost:6379/0"  # Redis URL (if enabled)

# Audit Logging Configuration
export MCP_AUDIT_LOG_FILE="~/.ipfs_kit/auth/audit.log"  # Audit log file
export MCP_AUDIT_CONSOLE=1                   # Log to console (0=no, 1=yes)
export MCP_AUDIT_RETENTION_DAYS=365          # Audit log retention in days

# RBAC Configuration
export MCP_CUSTOM_ROLES_FILE="~/.ipfs_kit/auth/custom_roles.json"
export MCP_PERMISSION_DEFAULTS_FILE="~/.ipfs_kit/auth/permission_defaults.json"
"""
    print(instructions)