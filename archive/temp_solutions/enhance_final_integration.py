#!/usr/bin/env python3
"""
Enhance Final MCP Server Integration with Virtual Filesystem

This script enhances the final_integration.py by adding comprehensive VFS integration
to the MCP server. It adds the necessary components to connect the IPFS kit with
the virtual filesystem and MCP server.
"""

import os
import sys
import logging
import importlib.util
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhance_final_integration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhance-final-integration")

def setup_python_paths():
    """Set up Python paths for proper module imports."""
    logger.info("Setting up Python paths for module imports...")
    
    # Current directory
    cwd = os.getcwd()
    
    # Add necessary paths
    paths_to_add = [
        # Main directory
        cwd,
        # IPFS Kit path
        os.path.join(cwd, "ipfs_kit_py"),
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")

def load_module(module_name, fail_silently=True):
    """
    Load a module dynamically
    
    Args:
        module_name: Name of the module to load
        fail_silently: If True, return None on error instead of raising an exception
        
    Returns:
        The loaded module or None if it couldn't be loaded and fail_silently is True
    """
    try:
        # Try to import the module
        if module_name in sys.modules:
            return sys.modules[module_name]
            
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            logger.warning(f"Module not found: {module_name}")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module not found: {module_name}")
        
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        else:
            logger.warning(f"Module {module_name} found but couldn't be loaded (no spec.loader)")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module {module_name} found but couldn't be loaded")
    except Exception as e:
        logger.error(f"Error loading module {module_name}: {e}")
        if fail_silently:
            return None
        else:
            raise

def check_vfs_components():
    """Check if the VFS components are available."""
    logger.info("Checking VFS components...")
    
    components = [
        "fs_journal_tools",
        "ipfs_mcp_fs_integration",
        "multi_backend_fs_integration",
        "integrate_vfs_to_final_mcp"
    ]
    
    available_components = []
    
    for component in components:
        module = load_module(component)
        if module:
            available_components.append(component)
            logger.info(f"✅ Component {component} is available")
        else:
            logger.warning(f"⚠️ Component {component} is not available")
    
    if available_components:
        return available_components
    else:
        return False

def create_vfs_integration_module():
    """Create the VFS integration module."""
    logger.info("Creating VFS integration module...")
    
    module_path = os.path.join(os.getcwd(), "enhance_vfs_mcp_integration.py")
    
    # Check if the module already exists
    if os.path.exists(module_path):
        logger.info(f"✅ VFS integration module already exists at {module_path}")
        return True
    
    module_content = """#!/usr/bin/env python3
\"\"\"
MCP and Virtual Filesystem Integration Enhancement

This module provides comprehensive VFS integration with MCP server.
It acts as a bridge between the various components of the IPFS kit
and the MCP server.
\"\"\"

import os
import sys
import logging
import importlib.util
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_module(module_name, fail_silently=True):
    \"\"\"
    Load a module dynamically
    
    Args:
        module_name: Name of the module to load
        fail_silently: If True, return None on error instead of raising an exception
        
    Returns:
        The loaded module or None if it couldn't be loaded and fail_silently is True
    \"\"\"
    try:
        # Try to import the module
        if module_name in sys.modules:
            return sys.modules[module_name]
            
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            logger.warning(f"Module not found: {module_name}")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module not found: {module_name}")
        
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        else:
            logger.warning(f"Module {module_name} found but couldn't be loaded (no spec.loader)")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module {module_name} found but couldn't be loaded")
    except Exception as e:
        logger.error(f"Error loading module {module_name}: {e}")
        if fail_silently:
            return None
        else:
            raise

def register_all_fs_tools(server):
    \"\"\"
    Register all filesystem tools with the MCP server
    
    Args:
        server: The MCP server instance
        
    Returns:
        bool: True if at least some tools were registered successfully
    \"\"\"
    try:
        # Try to import integrate_vfs_to_final_mcp first
        vfs_module = load_module("integrate_vfs_to_final_mcp")
        if vfs_module and hasattr(vfs_module, "register_all_fs_tools"):
            logger.info("Using integrate_vfs_to_final_mcp for tool registration")
            return vfs_module.register_all_fs_tools(server)
        else:
            logger.warning("integrate_vfs_to_final_mcp module not found or missing register_all_fs_tools function")
            
            # Try individual component registration as a fallback
            success = False
            
            # Try fs_journal_tools
            fs_journal = load_module("fs_journal_tools")
            if fs_journal and hasattr(fs_journal, "register_tools"):
                try:
                    fs_journal.register_tools(server)
                    logger.info("Registered tools from fs_journal_tools")
                    success = True
                except Exception as e:
                    logger.error(f"Error registering fs_journal tools: {e}")
            
            # Try ipfs_mcp_fs_integration
            fs_integration = load_module("ipfs_mcp_fs_integration")
            if fs_integration and hasattr(fs_integration, "register_integration_tools"):
                try:
                    fs_integration.register_integration_tools(server)
                    logger.info("Registered tools from ipfs_mcp_fs_integration")
                    success = True
                except Exception as e:
                    logger.error(f"Error registering ipfs_mcp_fs_integration tools: {e}")
            
            # Try multi_backend_fs_integration
            multi_backend = load_module("multi_backend_fs_integration")
            if multi_backend and hasattr(multi_backend, "register_tools"):
                try:
                    multi_backend.register_tools(server)
                    logger.info("Registered tools from multi_backend_fs_integration")
                    success = True
                except Exception as e:
                    logger.error(f"Error registering multi_backend_fs_integration tools: {e}")
            
            return success
    except Exception as e:
        logger.error(f"Error registering filesystem tools: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("This module should be imported by an MCP server, not run directly")
    sys.exit(0)
"""
    
    try:
        with open(module_path, "w") as f:
            f.write(module_content)
        
        # Make the module executable
        os.chmod(module_path, 0o755)
        
        logger.info(f"✅ Created VFS integration module at {module_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating VFS integration module: {e}")
        logger.error(traceback.format_exc())
        return False

def update_final_mcp_server_for_vfs():
    """Update final_mcp_server.py to use the enhanced VFS integration."""
    logger.info("Updating final_mcp_server.py to use enhanced VFS integration...")
    
    try:
        server_path = os.path.join(os.getcwd(), "final_mcp_server.py")
        
        if not os.path.exists(server_path):
            logger.error(f"❌ final_mcp_server.py not found at {server_path}")
            return False
        
        with open(server_path, "r") as f:
            content = f.read()
        
        # Check if the file already imports from integrate_vfs_to_final_mcp
        if "from integrate_vfs_to_final_mcp import register_all_fs_tools" in content:
            # Replace it with the dynamic import approach
            updated_content = content.replace(
                "from integrate_vfs_to_final_mcp import register_all_fs_tools",
                "# VFS integration will be imported dynamically after setting up paths"
            )
            
            # Update the import_required_modules function to use our dynamic VFS integration
            if "register_all_fs_tools(server)" in content:
                updated_content = updated_content.replace(
                    "register_all_fs_tools(server)",
                    """try:
            # Try to import our enhanced VFS integration module
            import enhance_vfs_mcp_integration
            enhance_vfs_mcp_integration.register_all_fs_tools(server)
            logger.info('Virtual filesystem tools registered via enhanced integration')
        except Exception as e:
            logger.error(f"Error registering virtual filesystem tools: {e}")
            logger.error(traceback.format_exc())"""
                )
            
            with open(server_path, "w") as f:
                f.write(updated_content)
            
            logger.info("✅ Updated final_mcp_server.py to use enhanced VFS integration")
            return True
        else:
            logger.info("⚠️ final_mcp_server.py does not import from integrate_vfs_to_final_mcp, no update needed")
            return True
    except Exception as e:
        logger.error(f"❌ Error updating final_mcp_server.py: {e}")
        logger.error(traceback.format_exc())
        return False

def update_final_integration():
    """Update final_integration.py to include VFS integration checks."""
    logger.info("Updating final_integration.py to include VFS integration checks...")
    
    try:
        integration_path = os.path.join(os.getcwd(), "final_integration.py")
        
        if not os.path.exists(integration_path):
            logger.error(f"❌ final_integration.py not found at {integration_path}")
            return False
        
        with open(integration_path, "r") as f:
            content = f.read()
        
        # Check if the check_vfs_components function is already there
        if "check_vfs_components" in content:
            logger.info("⚠️ final_integration.py already includes VFS checks, no update needed")
            return True
        
        # Find the location where we can add our VFS check
        if "def check_dependencies():" in content:
            # Add our check_vfs_components function before check_dependencies
            content_lines = content.split("\n")
            check_deps_index = -1
            for i, line in enumerate(content_lines):
                if "def check_dependencies():" in line:
                    check_deps_index = i
                    break
            
            if check_deps_index != -1:
                vfs_check_function = """def check_vfs_components():
    \"\"\"Check if the VFS components are available.\"\"\"
    logger.info("Checking VFS components...")
    
    components = [
        "fs_journal_tools",
        "ipfs_mcp_fs_integration",
        "multi_backend_fs_integration",
        "integrate_vfs_to_final_mcp",
        "enhance_vfs_mcp_integration"
    ]
    
    available_components = []
    
    for component in components:
        try:
            # Try to import the module
            spec = importlib.util.find_spec(component)
            if spec is None:
                logger.warning(f"⚠️ VFS component {component} is not available")
                continue
            
            importlib.import_module(component)
            available_components.append(component)
            logger.info(f"✅ VFS component {component} is available")
        except ImportError as e:
            logger.warning(f"⚠️ VFS component {component} could not be imported: {e}")
    
    return len(available_components) > 0
"""
                
                content_lines.insert(check_deps_index, vfs_check_function)
                
                # Update the main function to include our VFS check
                main_index = -1
                for i, line in enumerate(content_lines):
                    if "def main():" in line:
                        main_index = i
                        break
                
                if main_index != -1:
                    found_check_deps = False
                    for i in range(main_index, len(content_lines)):
                        if "check_dependencies()" in content_lines[i]:
                            # Add our VFS check after the dependencies check
                            vfs_check_code = """    # Check VFS components
    if check_vfs_components():
        logger.info("✅ VFS components are available")
    else:
        logger.warning("⚠️ VFS components are not available. Some functionality may be limited.")
"""
                            content_lines.insert(i + 1, vfs_check_code)
                            found_check_deps = True
                            break
                    
                    if not found_check_deps:
                        logger.warning("⚠️ Could not find check_dependencies call in main function")
                
                updated_content = "\n".join(content_lines)
                
                with open(integration_path, "w") as f:
                    f.write(updated_content)
                
                logger.info("✅ Updated final_integration.py to include VFS integration checks")
                return True
            else:
                logger.warning("⚠️ Could not find check_dependencies function in final_integration.py")
                return False
        else:
            logger.warning("⚠️ Could not find check_dependencies function in final_integration.py")
            return False
    except Exception as e:
        logger.error(f"❌ Error updating final_integration.py: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point."""
    logger.info("Starting enhanced final MCP server integration with VFS...")
    
    # Set up Python paths
    setup_python_paths()
    
    # Check VFS components
    vfs_components = check_vfs_components()
    if not vfs_components:
        logger.warning("⚠️ No VFS components found. Will create the necessary modules.")
    else:
        logger.info(f"✅ Found VFS components: {', '.join(vfs_components)}")
    
    # Create VFS integration module
    if create_vfs_integration_module():
        logger.info("✅ VFS integration module is ready")
    else:
        logger.error("❌ Failed to create VFS integration module")
        return 1
    
    # Update final_mcp_server.py
    if update_final_mcp_server_for_vfs():
        logger.info("✅ final_mcp_server.py updated for VFS integration")
    else:
        logger.error("❌ Failed to update final_mcp_server.py for VFS integration")
        return 1
    
    # Update final_integration.py
    if update_final_integration():
        logger.info("✅ final_integration.py updated to include VFS checks")
    else:
        logger.warning("⚠️ Failed to update final_integration.py for VFS checks")
    
    logger.info("✅ Enhanced final MCP server integration with VFS completed")
    logger.info("Now run the original final_integration.py to complete the setup")
    logger.info("Then use start_final_solution.sh to start the complete MCP server with all components")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
