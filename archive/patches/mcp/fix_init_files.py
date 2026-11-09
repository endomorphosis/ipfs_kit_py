#!/usr/bin/env python3
"""
Fix for the MCP server initialization issues after refactoring.

This patch ensures that proper __init__.py files exist in all necessary directories
and that they contain the correct imports for seamless operation.
"""

import os
import sys
from pathlib import Path

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Define the directories that need proper __init__.py files
DIRS_TO_FIX = [
    Path("ipfs_kit_py/mcp_server"),
    Path("ipfs_kit_py/mcp_server/controllers"),
    Path("ipfs_kit_py/mcp_server/models"),
    Path("ipfs_kit_py/mcp_server/persistence"),
]

# Content for the main mcp_server/__init__.py
MCP_SERVER_INIT = '''"""
MCP Server Package - Refactored implementation of the MCP (Multi-Component Protocol) Server.

This package provides a modular and maintainable implementation of the MCP Server,
with proper separation of concerns between controllers, models, and persistence layers.
"""

from ipfs_kit_py.mcp_server.server import MCPServer, AsyncMCPServer

__all__ = [
    'MCPServer',
    'AsyncMCPServer',
]
'''

# Content for controllers/__init__.py
CONTROLLERS_INIT = '''"""
MCP Server controllers - Responsible for handling client requests and coordinating
between different components of the system.
"""

from ipfs_kit_py.mcp_server.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp_server.controllers.libp2p_controller import LibP2PController
from ipfs_kit_py.mcp_server.controllers.storage_manager_controller import StorageManagerController

__all__ = [
    'IPFSController',
    'LibP2PController',
    'StorageManagerController',
]
'''

# Content for models/__init__.py
MODELS_INIT = '''"""
MCP Server models - Data models and business logic for the MCP Server.
"""

# Import model classes as they are implemented
# from ipfs_kit_py.mcp_server.models.ipfs_model import IPFSModel
# from ipfs_kit_py.mcp_server.models.libp2p_model import LibP2PModel
# from ipfs_kit_py.mcp_server.models.storage_model import StorageModel

__all__ = [
    # 'IPFSModel',
    # 'LibP2PModel',
    # 'StorageModel',
]
'''

# Content for persistence/__init__.py
PERSISTENCE_INIT = '''"""
MCP Server persistence - Data storage and retrieval mechanisms for the MCP Server.
"""

# Import persistence classes as they are implemented
# from ipfs_kit_py.mcp_server.persistence.storage_backend import StorageBackend

__all__ = [
    # 'StorageBackend',
]
'''

# Map directories to their init content
INIT_CONTENT = {
    "ipfs_kit_py/mcp_server": MCP_SERVER_INIT,
    "ipfs_kit_py/mcp_server/controllers": CONTROLLERS_INIT,
    "ipfs_kit_py/mcp_server/models": MODELS_INIT,
    "ipfs_kit_py/mcp_server/persistence": PERSISTENCE_INIT,
}

def fix_init_files():
    """Create or update __init__.py files in the MCP server directories."""
    print("Fixing __init__.py files in MCP server directories...")
    
    for dir_path in DIRS_TO_FIX:
        full_path = PROJECT_ROOT / dir_path
        
        # Ensure the directory exists
        if not full_path.exists():
            print(f"Creating directory: {full_path}")
            os.makedirs(full_path, exist_ok=True)
        
        # Create or update the __init__.py file
        init_file = full_path / "__init__.py"
        
        # Get the appropriate content for this directory
        content = INIT_CONTENT.get(str(dir_path), "# Auto-generated __init__.py file\n")
        
        # Backup the original file if it exists
        if init_file.exists():
            backup_file = init_file.with_suffix(".py.bak")
            with open(init_file, 'r') as f:
                original_content = f.read()
                
            with open(backup_file, 'w') as f:
                f.write(original_content)
                print(f"Created backup at {backup_file}")
        
        # Write the updated content
        with open(init_file, 'w') as f:
            f.write(content)
            
        print(f"Updated {init_file}")
    
    print("All __init__.py files fixed successfully")

if __name__ == "__main__":
    try:
        fix_init_files()
        print("Initialization files patch applied successfully!")
    except Exception as e:
        print(f"Error applying patch: {e}")
        sys.exit(1)