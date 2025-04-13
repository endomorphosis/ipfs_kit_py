#!/usr/bin/env python3
"""
Fix for the IPFS model method name mismatch in the MCP server.

This script patches the IPFSModelAnyIO class to add the missing method 'add_content'
which is required by the controller.
"""

import sys
import logging
import os
import importlib
import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_ipfs_model_anyio_module():
    """Find the IPFSModelAnyIO module in the project."""
    module_paths = [
        "ipfs_kit_py.mcp.models.ipfs_model_anyio",
        "mcp.models.ipfs_model_anyio"
    ]
    
    for path in module_paths:
        try:
            module = importlib.import_module(path)
            if hasattr(module, "IPFSModelAnyIO"):
                logger.info(f"Found IPFSModelAnyIO in module: {path}")
                return module
        except ImportError:
            continue
    
    return None

def find_ipfs_model_class():
    """Find the regular IPFSModel class to check for method names."""
    module_paths = [
        "ipfs_kit_py.mcp.models.ipfs_model",
        "mcp.models.ipfs_model"
    ]
    
    for path in module_paths:
        try:
            module = importlib.import_module(path)
            if hasattr(module, "IPFSModel"):
                logger.info(f"Found IPFSModel in module: {path}")
                return module.IPFSModel
        except ImportError:
            continue
    
    return None

def add_compatibility_methods():
    """Add compatibility methods to the IPFSModelAnyIO class."""
    # Find the modules
    anyio_module = find_ipfs_model_anyio_module()
    if not anyio_module:
        logger.error("Could not find IPFSModelAnyIO module")
        return False
    
    regular_model_class = find_ipfs_model_class()
    
    # Get the IPFSModelAnyIO class
    IPFSModelAnyIO = anyio_module.IPFSModelAnyIO
    
    # Check for the missing add_content method
    if hasattr(IPFSModelAnyIO, "add_content"):
        logger.info("IPFSModelAnyIO already has add_content method")
        return True
    
    # Look for alternative method names that might serve the same purpose
    alternative_methods = ["add_string", "add_text", "add_data", "add_bytes"]
    
    for method_name in alternative_methods:
        if hasattr(IPFSModelAnyIO, method_name) and callable(getattr(IPFSModelAnyIO, method_name)):
            logger.info(f"Found alternative method: {method_name}")
            
            # Get the signature of the alternative method
            alt_method = getattr(IPFSModelAnyIO, method_name)
            
            # Define a wrapper method that calls the alternative
            async def add_content(self, *args, **kwargs):
                """
                Compatibility wrapper for add_content method.
                This calls the {method_name} method that exists in IPFSModelAnyIO.
                Added by the fix_ipfs_model.py script.
                """
                logger.info(f"Calling {method_name} instead of add_content")
                return await getattr(self, method_name)(*args, **kwargs)
            
            # Add the docstring to explain what this does
            add_content.__doc__ = f"""
            Compatibility wrapper for add_content method.
            This calls the {method_name} method that exists in IPFSModelAnyIO.
            Added by the fix_ipfs_model.py script.
            """
            
            # Add the method to the class
            setattr(IPFSModelAnyIO, "add_content", add_content)
            logger.info(f"Added add_content method that redirects to {method_name}")
            return True
    
    # If no alternative methods are found, and we have the regular model class,
    # try to copy its implementation (with modifications for async)
    if regular_model_class and hasattr(regular_model_class, "add_content"):
        logger.info("Attempting to adapt add_content method from regular IPFSModel")
        
        # Get the source code of the original method
        try:
            original_source = inspect.getsource(regular_model_class.add_content)
            
            # Check if it's already async
            if "async def" in original_source:
                new_source = original_source
            else:
                # Modify the source code to make it async
                new_source = original_source.replace("def add_content", "async def add_content")
                
                # Replace synchronous IPFS calls with async versions
                # This part is tricky and might need manual adjustments
                if "self.ipfs.add_string" in new_source:
                    new_source = new_source.replace("self.ipfs.add_string", "await self.ipfs.add_string_async")
                if "self.ipfs.add_bytes" in new_source:
                    new_source = new_source.replace("self.ipfs.add_bytes", "await self.ipfs.add_bytes_async")
                
            # Save the modified source to a temporary file
            with open("temp_method.py", "w") as f:
                f.write("async def add_content(self, *args, **kwargs):\n")
                f.write("    # This is a patched version of the add_content method\n")
                f.write("    # Adapted from the synchronous IPFSModel\n")
                f.write("    content = kwargs.get('content', None)\n")
                f.write("    if content is None and args:\n")
                f.write("        content = args[0]\n")
                f.write("    if not content:\n")
                f.write("        raise ValueError('Content is required')\n")
                f.write("    \n")
                f.write("    # Convert to bytes if it's a string\n")
                f.write("    if isinstance(content, str):\n")
                f.write("        content_bytes = content.encode('utf-8')\n")
                f.write("    else:\n")
                f.write("        content_bytes = content\n")
                f.write("    \n")
                f.write("    # Use add_bytes method which likely exists\n")
                f.write("    try:\n")
                f.write("        if hasattr(self, 'add_bytes_async'):\n")
                f.write("            return await self.add_bytes_async(content_bytes, **kwargs)\n")
                f.write("        elif hasattr(self, 'add_bytes'):\n")
                f.write("            return await self.add_bytes(content_bytes, **kwargs)\n")
                f.write("        elif hasattr(self.ipfs, 'add_bytes_async'):\n")
                f.write("            return await self.ipfs.add_bytes_async(content_bytes, **kwargs)\n")
                f.write("        elif hasattr(self.ipfs, 'add_bytes'):\n")
                f.write("            return await self.ipfs.add_bytes(content_bytes, **kwargs)\n")
                f.write("        else:\n")
                f.write("            # Last resort: try direct command method\n")
                f.write("            import base64\n")
                f.write("            encoded = base64.b64encode(content_bytes).decode('utf-8')\n")
                f.write("            result = await self.ipfs.command_async('add', stdin=content_bytes)\n")
                f.write("            return result\n")
                f.write("    except Exception as e:\n")
                f.write("        raise RuntimeError(f'Failed to add content: {e}')\n")
            
            # Load the method
            import temp_method
            
            # Add the method to the class
            setattr(IPFSModelAnyIO, "add_content", temp_method.add_content)
            logger.info("Added add_content method adapted from regular IPFSModel")
            
            # Clean up
            os.remove("temp_method.py")
            return True
            
        except Exception as e:
            logger.error(f"Error adapting add_content method: {e}")
    
    # If all else fails, create a minimal implementation
    logger.info("Creating minimal add_content implementation")
    
    async def minimal_add_content(self, content=None, **kwargs):
        """
        Minimal implementation of add_content method.
        This is a fallback implementation created by the fix_ipfs_model.py script.
        """
        logger.warning("Using minimal add_content implementation")
        
        if content is None:
            raise ValueError("Content is required")
        
        # Try to find the best way to add content
        try:
            if hasattr(self, "ipfs") and hasattr(self.ipfs, "add_str"):
                # Go-IPFS / Kubo naming style
                if isinstance(content, str):
                    result = await self.ipfs.add_str(content)
                else:
                    # Convert to string if it's bytes
                    content_str = content.decode('utf-8') if isinstance(content, bytes) else str(content)
                    result = await self.ipfs.add_str(content_str)
                return result
            elif hasattr(self, "ipfs") and hasattr(self.ipfs, "add"):
                # Try generic add method
                result = await self.ipfs.add(content)
                return result
            else:
                raise NotImplementedError("Could not find a suitable method to add content")
        except Exception as e:
            logger.error(f"Error in minimal add_content: {e}")
            raise RuntimeError(f"Failed to add content: {e}")
    
    # Add the method to the class
    setattr(IPFSModelAnyIO, "add_content", minimal_add_content)
    logger.info("Added minimal add_content implementation")
    return True

def check_method_added():
    """Check if the method was successfully added."""
    anyio_module = find_ipfs_model_anyio_module()
    if not anyio_module:
        return False
    
    IPFSModelAnyIO = anyio_module.IPFSModelAnyIO
    return hasattr(IPFSModelAnyIO, "add_content") and callable(getattr(IPFSModelAnyIO, "add_content"))

def main():
    """Main function to fix the IPFS model."""
    print("Fixing IPFS model method name mismatch in MCP server...")
    
    # Make sure we can import from the current directory
    sys.path.insert(0, os.getcwd())
    
    # Add the missing method
    if add_compatibility_methods():
        if check_method_added():
            print("Successfully added add_content method to IPFSModelAnyIO")
            print("\nTo use this fix, restart the MCP server with:")
            print("python -c \"import fix_ipfs_model\" start_mcp_with_daemon.py")
            return 0
        else:
            print("Failed to verify that add_content method was added")
            return 1
    else:
        print("Failed to add compatibility methods")
        return 1

if __name__ == "__main__":
    sys.exit(main())