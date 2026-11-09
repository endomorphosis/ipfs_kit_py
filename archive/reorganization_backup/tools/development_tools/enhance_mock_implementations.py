#!/usr/bin/env python3
"""
IPFS Mock Implementation Enhancer

This script enhances the mock implementations in unified_ipfs_tools.py
to properly handle parameters, especially for ipfs_add.
"""

import os
import sys
import json
import logging
import importlib
import traceback
from typing import Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mock_enhancer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mock-enhancer")

class MockEnhancer:
    """Enhances mock implementations to handle parameters properly."""
    
    @staticmethod
    def enhance_mock_add_content(original_func):
        """
        Enhance the mock_add_content function to handle parameters properly.
        
        Args:
            original_func: The original mock_add_content function
            
        Returns:
            An enhanced function that handles parameters properly
        """
        async def enhanced_func(params):
            """Enhanced mock implementation of add_content."""
            try:
                logger.info(f"Enhanced mock_add_content received params: {params}")
                
                # Extract required parameters
                if not params or not isinstance(params, dict):
                    raise ValueError("Parameters must be a non-empty dictionary")
                
                content = params.get("content")
                if content is None:
                    raise ValueError("'content' parameter is required")
                
                # Handle optional parameters
                filename = params.get("filename")
                pin = params.get("pin", True)
                
                # Handle boolean string values
                if isinstance(pin, str):
                    if pin.lower() in ("true", "1", "yes"):
                        pin = True
                    elif pin.lower() in ("false", "0", "no"):
                        pin = False
                
                # Handle only_hash parameter (not used in the mock, but should be handled)
                only_hash = params.get("only_hash", False)
                if isinstance(only_hash, str):
                    if only_hash.lower() in ("true", "1", "yes"):
                        only_hash = True
                    elif only_hash.lower() in ("false", "0", "no"):
                        only_hash = False
                        
                # Special handling for filename and wrap_with_directory
                wrap_with_directory = params.get("wrap_with_directory", False)
                if isinstance(wrap_with_directory, str):
                    if wrap_with_directory.lower() in ("true", "1", "yes"):
                        wrap_with_directory = True
                    elif wrap_with_directory.lower() in ("false", "0", "no"):
                        wrap_with_directory = False
                
                # If filename is provided but wrap_with_directory is not true,
                # we should set it to ensure the filename is preserved
                if filename and not wrap_with_directory:
                    logger.info("Setting wrap_with_directory=True because filename is provided")
                    wrap_with_directory = True
                
                # Call the original function with extracted parameters
                logger.info(f"Calling original with content_length={len(content)}, filename={filename}, pin={pin}")
                result = await original_func(content, filename, pin)
                
                # Add additional fields to make the result match real implementation better
                if wrap_with_directory:
                    result["wrap_with_directory"] = True
                if only_hash:
                    result["only_hash"] = True
                
                return result
                
            except Exception as e:
                logger.error(f"Error in enhanced_mock_add_content: {e}")
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "error": str(e),
                    "note": "This error was caught by the enhanced mock implementation"
                }
        
        return enhanced_func

    @staticmethod
    def enhance_mock_cat(original_func):
        """
        Enhance the mock_cat function to handle parameters properly.
        
        Args:
            original_func: The original mock_cat function
            
        Returns:
            An enhanced function that handles parameters properly
        """
        async def enhanced_func(params):
            """Enhanced mock implementation of cat."""
            try:
                logger.info(f"Enhanced mock_cat received params: {params}")
                
                # Extract required parameters
                if not params or not isinstance(params, dict):
                    raise ValueError("Parameters must be a non-empty dictionary")
                
                cid = params.get("hash")
                if cid is None:
                    raise ValueError("'hash' parameter is required")
                
                # Handle optional parameters (not used in mock, but should be handled)
                offset = params.get("offset", 0)
                length = params.get("length", -1)
                
                # Convert to proper types
                if isinstance(offset, str):
                    try:
                        offset = int(offset)
                    except ValueError:
                        raise ValueError("'offset' must be an integer")
                        
                if isinstance(length, str):
                    try:
                        length = int(length)
                    except ValueError:
                        raise ValueError("'length' must be an integer")
                
                # Call the original function with extracted parameters
                logger.info(f"Calling original with cid={cid}")
                result = await original_func(cid)
                
                # Add additional fields to make the result match real implementation better
                result["offset"] = offset
                result["length"] = length
                
                # Simulate offset and length if content is available
                if "content" in result and offset > 0:
                    content = result["content"]
                    if offset < len(content):
                        if length > 0:
                            content = content[offset:offset+length]
                        else:
                            content = content[offset:]
                        result["content"] = content
                        result["size"] = len(content)
                    else:
                        result["content"] = ""
                        result["size"] = 0
                
                return result
                
            except Exception as e:
                logger.error(f"Error in enhanced_mock_cat: {e}")
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "error": str(e),
                    "note": "This error was caught by the enhanced mock implementation"
                }
        
        return enhanced_func

    @staticmethod
    def enhance_mock_files_ls(original_func):
        """
        Enhance the mock_files_ls function to handle parameters properly.
        
        Args:
            original_func: The original mock_files_ls function
            
        Returns:
            An enhanced function that handles parameters properly
        """
        async def enhanced_func(params):
            """Enhanced mock implementation of files_ls."""
            try:
                logger.info(f"Enhanced mock_files_ls received params: {params}")
                
                # Extract parameters
                if not params or not isinstance(params, dict):
                    path = "/"
                else:
                    path = params.get("path", "/")
                
                # Convert boolean string values
                long_format = params.get("long", False)
                if isinstance(long_format, str):
                    if long_format.lower() in ("true", "1", "yes"):
                        long_format = True
                    elif long_format.lower() in ("false", "0", "no"):
                        long_format = False
                
                # Call the original function with extracted parameters
                logger.info(f"Calling original with path={path}")
                result = await original_func(path)
                
                # Add additional fields to make the result match real implementation better
                result["long"] = long_format
                
                return result
                
            except Exception as e:
                logger.error(f"Error in enhanced_mock_files_ls: {e}")
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "error": str(e),
                    "note": "This error was caught by the enhanced mock implementation"
                }
        
        return enhanced_func

def apply_enhancements():
    """Apply enhancements to unified_ipfs_tools."""
    try:
        # Import the unified_ipfs_tools module
        import unified_ipfs_tools
        
        # Show original implementation info
        logger.info("Original implementation status:")
        for key, value in unified_ipfs_tools.TOOL_STATUS.items():
            logger.info(f"  {key}: {value}")
        
        # Track which functions we've enhanced
        enhanced_funcs = []
        
        # Enhance mock_add_content if available
        if hasattr(unified_ipfs_tools, "mock_add_content"):
            original_mock_add_content = unified_ipfs_tools.mock_add_content
            unified_ipfs_tools.mock_add_content = MockEnhancer.enhance_mock_add_content(original_mock_add_content)
            logger.info("✅ Enhanced mock_add_content with parameter validation")
            enhanced_funcs.append("mock_add_content")
        
        # Enhance mock_cat if available
        if hasattr(unified_ipfs_tools, "mock_cat"):
            original_mock_cat = unified_ipfs_tools.mock_cat
            unified_ipfs_tools.mock_cat = MockEnhancer.enhance_mock_cat(original_mock_cat)
            logger.info("✅ Enhanced mock_cat with parameter validation")
            enhanced_funcs.append("mock_cat")
        
        # Enhance mock_files_ls if available
        if hasattr(unified_ipfs_tools, "mock_files_ls"):
            original_mock_files_ls = unified_ipfs_tools.mock_files_ls
            unified_ipfs_tools.mock_files_ls = MockEnhancer.enhance_mock_files_ls(original_mock_files_ls)
            logger.info("✅ Enhanced mock_files_ls with parameter validation")
            enhanced_funcs.append("mock_files_ls")
        
        # Update the get_implementation function to use the enhanced mocks
        if hasattr(unified_ipfs_tools, "get_implementation"):
            original_get_implementation = unified_ipfs_tools.get_implementation
            
            def enhanced_get_implementation(tool_name):
                """Enhanced version of get_implementation that uses our enhanced mocks."""
                implementation = original_get_implementation(tool_name)
                logger.info(f"Original get_implementation returned: {implementation.__name__ if implementation else None}")
                return implementation
            
            unified_ipfs_tools.get_implementation = enhanced_get_implementation
            logger.info("✅ Enhanced get_implementation")
            enhanced_funcs.append("get_implementation")
        
        # Final success message
        if enhanced_funcs:
            logger.info(f"✅ Successfully enhanced {len(enhanced_funcs)} functions in unified_ipfs_tools:")
            for func in enhanced_funcs:
                logger.info(f"  - {func}")
            return True
        else:
            logger.warning("⚠️ No functions were enhanced in unified_ipfs_tools")
            return False
        
    except ImportError as e:
        logger.error(f"❌ Could not import unified_ipfs_tools: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error enhancing unified_ipfs_tools: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point."""
    logger.info("Starting IPFS Mock Implementation Enhancer")
    
    if apply_enhancements():
        logger.info("✅ Successfully applied enhancements to unified_ipfs_tools")
    else:
        logger.error("❌ Failed to apply enhancements to unified_ipfs_tools")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
