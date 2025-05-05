#!/usr/bin/env python3
"""
Fix MCP IPFS Integration
This script applies comprehensive fixes to ensure proper integration between
IPFS tools and filesystem features in the MCP server.
"""

import os
import sys
import logging
import re
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ipfs_integration_fix.log")
    ]
)
logger = logging.getLogger("ipfs-integration-fix")

def fix_direct_mcp_server():
    """Fix direct_mcp_server.py to properly integrate with IPFS and FS tools"""
    logger.info("Fixing direct_mcp_server.py for IPFS and FS integration...")
    
    # Path to the direct_mcp_server.py file
    server_path = "direct_mcp_server.py"
    
    if not os.path.exists(server_path):
        logger.error(f"File not found: {server_path}")
        return False
    
    # Read the original file
    with open(server_path, 'r') as f:
        content = f.read()
    
    # Add necessary imports if they don't exist
    import_block = """
import os
import sys
import logging
import json
import importlib
from pathlib import Path

# Import IPFS extensions
try:
    from ipfs_kit_py.mcp.ipfs_extensions import register_ipfs_tools
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    import ipfs_kit_py.mcp.models.ipfs_model as ipfs_model
    IPFS_AVAILABLE = True
except ImportError:
    logger.warning("IPFS extensions not available")
    IPFS_AVAILABLE = False

# Import FS Journal tools
try:
    from fs_journal_tools import register_fs_journal_tools
    FS_JOURNAL_AVAILABLE = True
except ImportError:
    logger.warning("FS Journal tools not available")
    FS_JOURNAL_AVAILABLE = False

# Import IPFS-FS Bridge
try:
    from ipfs_mcp_fs_integration import register_integration_tools
    IPFS_FS_BRIDGE_AVAILABLE = True
except ImportError:
    logger.warning("IPFS-FS Bridge not available")
    IPFS_FS_BRIDGE_AVAILABLE = False

# Import Multi-Backend FS
try:
    from multi_backend_fs_integration import register_multi_backend_tools
    MULTI_BACKEND_FS_AVAILABLE = True
except ImportError:
    logger.warning("Multi-Backend FS not available")
    MULTI_BACKEND_FS_AVAILABLE = False
"""
    
    # Check if imports exist and add if they don't
    if "from ipfs_kit_py.mcp.ipfs_extensions import register_ipfs_tools" not in content:
        # Find the import section
        import_match = re.search(r'import .*?(?=\n\n)', content, re.DOTALL)
        if import_match:
            # Add our imports after the existing imports
            new_content = content[:import_match.end()] + import_block + content[import_match.end():]
            content = new_content
        else:
            # Prepend our imports at the top (after any shebang or docstring)
            docstring_match = re.search(r'""".*?"""', content, re.DOTALL)
            if docstring_match:
                new_content = content[:docstring_match.end()] + "\n" + import_block + content[docstring_match.end():]
                content = new_content
            else:
                content = import_block + "\n" + content
    
    # Add tool registration function if it doesn't exist
    register_function = """
def register_all_tools(mcp_server):
    \"\"\"Register all available tools with the MCP server.\"\"\"
    logger.info("Registering all available tools with MCP server...")
    
    # Register IPFS tools if available
    if IPFS_AVAILABLE:
        try:
            # Initialize IPFS model
            ipfs = ipfs_model.IPFSModel()
            
            # Initialize IPFS controller
            controller = IPFSController(ipfs)
            
            # Register IPFS tools
            register_ipfs_tools(mcp_server, controller, ipfs)
            logger.info("✅ Successfully registered IPFS tools")
        except Exception as e:
            logger.error(f"Failed to register IPFS tools: {e}")
    
    # Register FS Journal tools if available
    if FS_JOURNAL_AVAILABLE:
        try:
            register_fs_journal_tools(mcp_server)
            logger.info("✅ Successfully registered FS Journal tools")
        except Exception as e:
            logger.error(f"Failed to register FS Journal tools: {e}")
    
    # Register IPFS-FS Bridge tools if available
    if IPFS_FS_BRIDGE_AVAILABLE:
        try:
            register_integration_tools(mcp_server)
            logger.info("✅ Successfully registered IPFS-FS Bridge tools")
        except Exception as e:
            logger.error(f"Failed to register IPFS-FS Bridge tools: {e}")
    
    # Register Multi-Backend FS tools if available
    if MULTI_BACKEND_FS_AVAILABLE:
        try:
            register_multi_backend_tools(mcp_server)
            logger.info("✅ Successfully registered Multi-Backend FS tools")
        except Exception as e:
            logger.error(f"Failed to register Multi-Backend FS tools: {e}")
    
    logger.info("Tool registration complete")
"""
    
    # Check if registration function exists and add if it doesn't
    if "def register_all_tools" not in content:
        # Find a good insertion point (before the main function or at the end)
        main_match = re.search(r'def main\(\):', content)
        if main_match:
            # Add our function before the main function
            new_content = content[:main_match.start()] + register_function + "\n" + content[main_match.start():]
            content = new_content
        else:
            # Add at the end
            content += "\n" + register_function
    
    # Update the main function to call our registration function
    if "register_all_tools(server)" not in content:
        # Find the server instantiation
        server_match = re.search(r'server\s*=\s*FastMCP\(\)', content)
        if server_match:
            # Add our function call after server instantiation
            insert_pos = server_match.end()
            # Find the end of the line
            line_end = content.find("\n", insert_pos)
            if line_end > 0:
                new_content = content[:line_end] + "\n    \n    # Register all tools\n    register_all_tools(server)" + content[line_end:]
                content = new_content
    
    # Write the updated file
    with open(server_path, 'w') as f:
        f.write(content)
    
    logger.info(f"✅ Successfully fixed {server_path} for IPFS and FS integration")
    return True

def create_fs_journal_tools():
    """Create simple FS Journal tools module if it doesn't exist"""
    if not os.path.exists("fs_journal_tools.py"):
        logger.info("Creating minimal fs_journal_tools.py...")
        fs_journal_content = """#!/usr/bin/env python3
\"\"\"
Filesystem Journal Tools for IPFS MCP Integration
Minimal implementation for integration testing
\"\"\"

import logging
import os
import json
import time

logger = logging.getLogger(__name__)

class FSJournal:
    \"\"\"Minimal File System Journal implementation\"\"\"
    
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.getcwd()
        self.journal_path = os.path.join(self.base_dir, '.fs_journal')
        os.makedirs(self.journal_path, exist_ok=True)
        logger.info(f"Initialized minimal FS Journal with base directory: {self.base_dir}")
    
    def get_history(self, path, limit=50):
        \"\"\"Get history for a specific path\"\"\"
        return {
            'path': path,
            'entries': [],
            'message': 'Minimal implementation - no history available'
        }
    
    def sync_path(self, path, recursive=True):
        \"\"\"Synchronize path to journal\"\"\"
        return {
            'path': path,
            'status': 'synced',
            'message': 'Minimal implementation - sync simulated'
        }

def register_fs_journal_tools(mcp_server):
    \"\"\"Register FS Journal tools with MCP server\"\"\"
    logger.info("Registering minimal FS Journal tools...")
    
    # Initialize the journal
    journal = FSJournal()
    
    # Register tools
    @mcp_server.tool("fs_journal_get_history")
    def fs_journal_get_history(path, limit=50):
        \"\"\"Get history of file changes\"\"\"
        logger.info(f"MCP Tool call: fs_journal_get_history({path}, {limit})")
        return journal.get_history(path, limit)
    
    @mcp_server.tool("fs_journal_sync")
    def fs_journal_sync(path, recursive=True):
        \"\"\"Synchronize changes to journal\"\"\"
        logger.info(f"MCP Tool call: fs_journal_sync({path}, {recursive})")
        return journal.sync_path(path, recursive)
    
    logger.info("✅ Successfully registered minimal FS Journal tools with MCP server")
"""
        with open("fs_journal_tools.py", 'w') as f:
            f.write(fs_journal_content)
        logger.info("✅ Created minimal fs_journal_tools.py")
        return True
    return False

def create_ipfs_fs_integration():
    """Create simple IPFS-FS Bridge module if it doesn't exist"""
    if not os.path.exists("ipfs_mcp_fs_integration.py"):
        logger.info("Creating minimal ipfs_mcp_fs_integration.py...")
        ipfs_fs_integration_content = """#!/usr/bin/env python3
'''
IPFS-FS Integration Bridge
Minimal implementation for integration testing
'''

import logging
import os

logger = logging.getLogger(__name__)

def register_integration_tools(mcp_server):
    \"\"\"Register IPFS-FS integration tools with MCP server\"\"\"
    logger.info("Registering minimal IPFS-FS integration tools...")
    
    @mcp_server.tool("ipfs_fs_bridge_status")
    def ipfs_fs_bridge_status(path=None):
        \"\"\"Get bridge status\"\"\"
        logger.info(f"MCP Tool call: ipfs_fs_bridge_status({path})")
        return {
            'status': 'active',
            'path': path,
            'message': 'Minimal implementation - bridge status simulated'
        }
    
    @mcp_server.tool("ipfs_fs_bridge_sync")
    def ipfs_fs_bridge_sync(path, direction="to_ipfs"):
        \"\"\"Sync between IPFS and filesystem\"\"\"
        logger.info(f"MCP Tool call: ipfs_fs_bridge_sync({path}, {direction})")
        return {
            'path': path,
            'direction': direction,
            'status': 'synced',
            'message': 'Minimal implementation - sync simulated'
        }
    
    logger.info("✅ Successfully registered minimal IPFS-FS integration tools")
"""
        with open("ipfs_mcp_fs_integration.py", 'w') as f:
            f.write(ipfs_fs_integration_content)
        logger.info("✅ Created minimal ipfs_mcp_fs_integration.py")
        return True
    return False

def fix_run_direct_mcp_server():
    """Fix run_direct_mcp_server.py imports if it exists"""
    if os.path.exists("run_direct_mcp_server.py"):
        logger.info("Fixing run_direct_mcp_server.py...")
        with open("run_direct_mcp_server.py", 'r') as f:
            content = f.read()
        
        # Fix the imports if needed
        if "register_ipfs_tools" in content and "from ipfs_kit_py.mcp.ipfs_extensions import register_ipfs_tools" not in content:
            content = content.replace(
                "from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController",
                "from ipfs_kit_py.mcp.ipfs_extensions import register_ipfs_tools\nfrom ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController"
            )
            with open("run_direct_mcp_server.py", 'w') as f:
                f.write(content)
            logger.info("✅ Fixed run_direct_mcp_server.py imports")
            return True
    return False

def fix_all_files():
    """Fix all necessary files for comprehensive IPFS tool coverage"""
    
    # Fix direct_mcp_server.py
    if not fix_direct_mcp_server():
        logger.error("Failed to fix direct_mcp_server.py")
        return False
    
    # Create simple FS Journal tools module if it doesn't exist
    create_fs_journal_tools()
    
    # Create simple IPFS-FS Bridge module if it doesn't exist
    create_ipfs_fs_integration()
    
    # Fix run_direct_mcp_server.py if it exists
    fix_run_direct_mcp_server()
    
    logger.info("All files fixed successfully for comprehensive IPFS tool coverage")
    return True

if __name__ == "__main__":
    logger.info("Starting comprehensive IPFS integration fix...")
    if fix_all_files():
        logger.info("✅ All fixes applied successfully!")
        print("\n✅ IPFS integration fixes applied successfully!")
        print("Run './start_ipfs_mcp_with_tools.sh' to start the MCP server with comprehensive IPFS tool coverage.")
    else:
        logger.error("❌ Failed to apply all fixes")
        print("\n❌ Failed to apply all IPFS integration fixes.")
        print("Check the logs for details and try to fix the issues manually.")
