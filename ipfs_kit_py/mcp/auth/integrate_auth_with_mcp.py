#!/usr/bin/env python3
"""
MCP Authentication & Authorization Integration Script

This script helps integrate the Advanced Authentication & Authorization system
with the main MCP server. It creates a backup of the original server file and
applies the necessary changes to enable auth functionality.

Usage:
    python integrate_auth_with_mcp.py [--backup] [--server-path PATH]
"""

import os
import sys
import re
import shutil
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("auth_integration")

# Default MCP server path
DEFAULT_SERVER_PATH = "../direct_mcp_server.py"

# Import sections to add
AUTH_IMPORTS = """
# Advanced Authentication & Authorization
from ipfs_kit_py.mcp.auth.mcp_auth_integration import (
    setup_mcp_auth, get_mcp_auth,
    audit_login_attempt, audit_permission_check, audit_backend_access,
    audit_user_change, audit_system_event, audit_data_event
)
from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
"""

# Configuration block to add
AUTH_CONFIG = """
    # Initialize Advanced Authentication & Authorization System
    auth_config = {
        # JWT configuration
        "token_secret": os.environ.get("MCP_JWT_SECRET", "change-me-in-production"),
        "token_algorithm": "HS256",
        "token_expire_minutes": int(os.environ.get("JWT_EXPIRE_MINUTES", "1440")),
        
        # Admin account
        "admin_username": os.environ.get("MCP_ADMIN_USERNAME", "admin"),
        "admin_password": os.environ.get("MCP_ADMIN_PASSWORD", "change-me-in-production"),
        
        # OAuth providers (configure as needed)
        "oauth_providers": {
            "github": {
                "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
                "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
                "redirect_uri": os.environ.get("GITHUB_REDIRECT_URI", "")
            },
            "google": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uri": os.environ.get("GOOGLE_REDIRECT_URI", "")
            }
        },
        
        # Custom roles
        "custom_roles": [
            {
                "id": "data_scientist",
                "name": "Data Scientist",
                "parent_role": "user",
                "permissions": [
                    "read:ipfs", "write:ipfs", 
                    "read:huggingface", "write:huggingface",
                    "read:search", "write:search"
                ]
            },
            {
                "id": "operations",
                "name": "Operations",
                "parent_role": "user",
                "permissions": [
                    "read:ipfs", "write:ipfs", "pin:ipfs", "admin:ipfs",
                    "read:monitoring", "write:monitoring",
                    "read:migration", "write:migration"
                ]
            },
            {
                "id": "content_manager",
                "name": "Content Manager",
                "parent_role": "user",
                "permissions": [
                    "read:ipfs", "write:ipfs", 
                    "read:s3", "write:s3",
                    "read:storacha", "write:storacha",
                    "read:migration", "write:migration"
                ]
            }
        ]
    }
    
    auth_system = await setup_mcp_auth(
        app=app,
        backend_manager=backend_manager,
        config=auth_config
    )
    
    if auth_system and auth_system.initialized:
        logger.info("Advanced Authentication & Authorization system initialized")
        
        # Configure backend permissions
        await auth_system.configure_backend_permissions({
            "ipfs": ["read", "write", "pin", "admin"],
            "s3": ["read", "write", "delete"],
            "filecoin": ["read", "write", "verify"],
            "storacha": ["read", "write"],
            "huggingface": ["read", "write"],
            "lassie": ["read"]
        })
    else:
        logger.warning("Failed to initialize auth system")
"""

# Depends modifications for endpoints
ENDPOINT_MODIFICATIONS = [
    {
        "pattern": r"@app\.get\(\"\/api\/v0\/ipfs\/version\"\)\nasync def ipfs_version\(\):",
        "replacement": '@app.get("/api/v0/ipfs/version")\nasync def ipfs_version(current_user: User = Depends(get_current_user)):'
    },
    {
        "pattern": r"@app\.post\(\"\/api\/v0\/ipfs\/add\"\)\nasync def ipfs_add\(\s*file: UploadFile = File\(\.\.\.\),\s*pin: bool = Form\(True\)\s*\):",
        "replacement": '@app.post("/api/v0/ipfs/add")\nasync def ipfs_add(\n    file: UploadFile = File(...),\n    pin: bool = Form(True),\n    current_user: User = Depends(get_current_user)\n):'
    },
    {
        "pattern": r"@app\.get\(\"\/api\/v0\/ipfs\/cat\/\{cid\}\"\)\nasync def ipfs_cat\(cid: str\):",
        "replacement": '@app.get("/api/v0/ipfs/cat/{cid}")\nasync def ipfs_cat(cid: str, current_user: User = Depends(get_current_user)):'
    }
]

# Admin endpoint modifications
ADMIN_ENDPOINT_MODIFICATIONS = [
    {
        "pattern": r"@app\.get\(\"\/api\/v0\/admin\/system\/status\"\)\nasync def admin_system_status\(\):",
        "replacement": '@app.get("/api/v0/admin/system/status")\nasync def admin_system_status(current_user: User = Depends(get_admin_user)):'
    }
]

def create_backup(file_path: str) -> str:
    """
    Create a backup of the original server file.
    
    Args:
        file_path: Path to the server file
        
    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.bak_{timestamp}"
    
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at: {backup_path}")
    
    return backup_path

def modify_server_file(file_path: str) -> bool:
    """
    Modify the server file to integrate the auth system.
    
    Args:
        file_path: Path to the server file
        
    Returns:
        Success flag
    """
    try:
        # Read the original file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add auth imports
        if "# Advanced Authentication & Authorization" not in content:
            # Find import section
            import_pattern = r"# Import MCP components\s+try:"
            import_match = re.search(import_pattern, content)
            
            if import_match:
                # Add auth imports before the closing "try:"
                position = import_match.end()
                modified_content = (
                    content[:position] + 
                    AUTH_IMPORTS + 
                    content[position:]
                )
                content = modified_content
                logger.info("Added auth imports")
            else:
                logger.warning("Could not find import section")
        
        # Add auth initialization
        if "auth_system = await setup_mcp_auth" not in content:
            # Find initialization section in startup_event
            init_pattern = r"async def initialize_components\(\):.+?logger\.info\(\"All MCP components initialized"
            init_match = re.search(init_pattern, content, re.DOTALL)
            
            if init_match:
                # Find the position before "All MCP components initialized"
                init_text = init_match.group(0)
                position = init_match.start() + init_text.rfind("logger.info")
                
                # Add auth initialization before this line
                modified_content = (
                    content[:position] + 
                    AUTH_CONFIG + 
                    "    " + content[position:]
                )
                content = modified_content
                logger.info("Added auth initialization code")
            else:
                logger.warning("Could not find initialization section")
        
        # Modify endpoint dependencies
        for mod in ENDPOINT_MODIFICATIONS + ADMIN_ENDPOINT_MODIFICATIONS:
            pattern = mod["pattern"]
            replacement = mod["replacement"]
            
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                logger.info(f"Modified endpoint: {pattern}")
        
        # Write the modified content back to the file
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Successfully modified server file: {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error modifying server file: {e}")
        return False

def main():
    """Main function."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="MCP Auth Integration Script")
    parser.add_argument("--backup", action="store_true", help="Create backup before modifying")
    parser.add_argument("--server-path", default=DEFAULT_SERVER_PATH, help="Path to MCP server file")
    args = parser.parse_args()
    
    # Resolve server path
    server_path = os.path.abspath(args.server_path)
    if not os.path.exists(server_path):
        logger.error(f"Server file not found: {server_path}")
        return 1
    
    # Create backup if requested
    if args.backup:
        backup_path = create_backup(server_path)
        logger.info(f"Backup created at: {backup_path}")
    
    # Modify server file
    success = modify_server_file(server_path)
    
    if success:
        logger.info("Auth system integration completed successfully")
        return 0
    else:
        logger.error("Auth system integration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())