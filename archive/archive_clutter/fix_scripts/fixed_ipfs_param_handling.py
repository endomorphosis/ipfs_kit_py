#!/usr/bin/env python3
"""
Fixed IPFS Parameter Handling

This module provides improved parameter handling for IPFS tools, addressing 
the issues identified with ipfs_add and other IPFS tools in the MCP server.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional, Union, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fixed-ipfs-params")

class IPFSParamHandler:
    """Handler for IPFS tool parameters with improved validation and processing."""
    
    @staticmethod
    def validate_ipfs_add_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters for ipfs_add.
        
        Args:
            params: Dictionary of parameters for ipfs_add
        
        Returns:
            Normalized parameters dictionary
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not params:
            raise ValueError("Parameters for ipfs_add cannot be empty")
        
        # Ensure content is provided
        if "content" not in params:
            raise ValueError("'content' parameter is required for ipfs_add")
        
        # Create a copy to avoid modifying the original
        normalized_params = params.copy()
        
        # Convert boolean string values to actual booleans
        bool_params = ["only_hash", "wrap_with_directory", "chunker", "pin"]
        for param in bool_params:
            if param in normalized_params and isinstance(normalized_params[param], str):
                if normalized_params[param].lower() in ("true", "1", "yes"):
                    normalized_params[param] = True
                elif normalized_params[param].lower() in ("false", "0", "no"):
                    normalized_params[param] = False
        
        # Handle filename separately as it requires special processing
        if "filename" in normalized_params and not normalized_params.get("wrap_with_directory"):
            # If filename is provided but wrap_with_directory is not true,
            # we should set it to ensure the filename is preserved
            logger.info("Setting wrap_with_directory=True because filename is provided")
            normalized_params["wrap_with_directory"] = True
        
        return normalized_params
    
    @staticmethod
    def validate_ipfs_files_ls_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters for ipfs_files_ls.
        
        Args:
            params: Dictionary of parameters for ipfs_files_ls
        
        Returns:
            Normalized parameters dictionary
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Create a copy to avoid modifying the original
        normalized_params = params.copy()
        
        # Set default path if not provided
        if "path" not in normalized_params:
            normalized_params["path"] = "/"
        
        # Convert boolean string values to actual booleans
        bool_params = ["long"]
        for param in bool_params:
            if param in normalized_params and isinstance(normalized_params[param], str):
                if normalized_params[param].lower() in ("true", "1", "yes"):
                    normalized_params[param] = True
                elif normalized_params[param].lower() in ("false", "0", "no"):
                    normalized_params[param] = False
        
        return normalized_params
    
    @staticmethod
    def validate_ipfs_cat_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters for ipfs_cat.
        
        Args:
            params: Dictionary of parameters for ipfs_cat
        
        Returns:
            Normalized parameters dictionary
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not params:
            raise ValueError("Parameters for ipfs_cat cannot be empty")
        
        if "hash" not in params:
            raise ValueError("'hash' parameter is required for ipfs_cat")
        
        # Create a copy to avoid modifying the original
        normalized_params = params.copy()
        
        # Handle offset and length
        if "offset" in normalized_params and isinstance(normalized_params["offset"], str):
            try:
                normalized_params["offset"] = int(normalized_params["offset"])
            except ValueError:
                raise ValueError("'offset' must be an integer")
                
        if "length" in normalized_params and isinstance(normalized_params["length"], str):
            try:
                normalized_params["length"] = int(normalized_params["length"])
            except ValueError:
                raise ValueError("'length' must be an integer")
        
        return normalized_params

    @staticmethod
    def validate_params(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters for a specific IPFS tool.
        
        Args:
            tool_name: Name of the IPFS tool
            params: Dictionary of parameters for the tool
        
        Returns:
            Normalized parameters dictionary
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        params = params or {}
        
        # Choose the appropriate validation method based on the tool name
        if tool_name == "ipfs_add":
            return IPFSParamHandler.validate_ipfs_add_params(params)
        elif tool_name == "ipfs_cat":
            return IPFSParamHandler.validate_ipfs_cat_params(params)
        elif tool_name == "ipfs_files_ls":
            return IPFSParamHandler.validate_ipfs_files_ls_params(params)
        else:
            # For other tools, just return the parameters as is
            return params


def apply_param_fixes_to_unified_tools(unified_tools_module):
    """
    Apply the parameter handling fixes to the unified_ipfs_tools module.
    
    Args:
        unified_tools_module: The unified_ipfs_tools module to fix
    """
    if not hasattr(unified_tools_module, "register_tools"):
        logger.error("unified_ipfs_tools module doesn't have register_tools function")
        return False
    
    # Store original mock implementations that might need parameter fixes
    if hasattr(unified_tools_module, "mock_add_content"):
        original_mock_add_content = unified_tools_module.mock_add_content
        
        # Create enhanced version that handles parameter validation
        async def enhanced_mock_add_content(params):
            """Enhanced mock implementation with parameter validation"""
            try:
                # Validate and normalize parameters
                fixed_params = IPFSParamHandler.validate_params("ipfs_add", params)
                logger.debug(f"Fixed params for ipfs_add: {fixed_params}")
                
                # Extract the parameters needed by the original function
                content = fixed_params.get("content", "")
                filename = fixed_params.get("filename", None)
                pin = fixed_params.get("pin", True)
                
                # Call the original implementation with extracted parameters
                return await original_mock_add_content(content, filename, pin)
            except Exception as e:
                logger.error(f"Error in enhanced_mock_add_content: {e}")
                raise
        
        # Replace the original implementation
        unified_tools_module.mock_add_content = enhanced_mock_add_content
        logger.info("✅ Enhanced mock_add_content with parameter validation")
    
    # Store the original register_tools function
    original_register_tools = unified_tools_module.register_tools
    
    # Define a wrapper to intercept tool invocations and apply parameter fixes
    def fixed_tool_wrapper(tool_name, original_func):
        """Wrap a tool function to apply parameter fixes."""
        async def wrapper(params):
            try:
                # Apply parameter fixes
                fixed_params = IPFSParamHandler.validate_params(tool_name, params)
                logger.debug(f"Fixed params for {tool_name}: {fixed_params}")
                
                # Call the original function with fixed parameters
                return await original_func(fixed_params)
            except Exception as e:
                logger.error(f"Error in {tool_name}: {e}")
                raise
        
        return wrapper
    
    # Define a wrapper for the register_tools function
    def fixed_register_tools(dispatcher):
        """Wrap register_tools to apply parameter fixes to all tools."""
        # Get the original tools definition
        result = original_register_tools(dispatcher)
        
        # Fix the tools that are already registered
        for tool_name in dispatcher.methods:
            if tool_name.startswith("ipfs_"):
                original_method = dispatcher.methods[tool_name]
                dispatcher.methods[tool_name] = fixed_tool_wrapper(tool_name, original_method)
                logger.info(f"Applied parameter fixes to {tool_name}")
        
        return result
    
    # Replace the original register_tools with our fixed version
    unified_tools_module.register_tools = fixed_register_tools
    logger.info("✅ Parameter handling fixes applied to unified_ipfs_tools")
    
    return True


def main():
    """Test the parameter handling fixes."""
    logger.info("Testing parameter handling fixes...")
    
    # Test cases for ipfs_add
    test_cases = [
        {"tool": "ipfs_add", "params": {"content": "Hello IPFS!"}},
        {"tool": "ipfs_add", "params": {"content": "Test with filename", "filename": "test.txt"}},
        {"tool": "ipfs_add", "params": {"content": "Test with only_hash", "only_hash": "true"}},
        {"tool": "ipfs_add", "params": {"content": "Test with wrap_dir", "wrap_with_directory": True}},
        {"tool": "ipfs_files_ls", "params": {"path": "/"}},
        {"tool": "ipfs_cat", "params": {"hash": "QmTest", "offset": "10", "length": "100"}}
    ]
    
    for test in test_cases:
        tool = test["tool"]
        params = test["params"]
        try:
            logger.info(f"Testing {tool} with params: {params}")
            fixed_params = IPFSParamHandler.validate_params(tool, params)
            logger.info(f"Fixed params: {fixed_params}")
            logger.info("✅ Test passed")
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
    
    # Try to apply fixes to unified_ipfs_tools
    try:
        logger.info("\nTrying to apply fixes to unified_ipfs_tools...")
        
        # Import the unified_ipfs_tools module
        import unified_ipfs_tools
        
        # Show original implementation info
        logger.info("Original implementation status:")
        for key, value in unified_ipfs_tools.TOOL_STATUS.items():
            logger.info(f"  {key}: {value}")
        
        # Apply fixes
        success = apply_param_fixes_to_unified_tools(unified_ipfs_tools)
        if success:
            logger.info("✅ Successfully applied fixes to unified_ipfs_tools")
        else:
            logger.error("❌ Failed to apply fixes to unified_ipfs_tools")
        
    except ImportError as e:
        logger.error(f"❌ Could not import unified_ipfs_tools: {e}")
    except Exception as e:
        logger.error(f"❌ Error applying fixes to unified_ipfs_tools: {e}")
        logger.error(traceback.format_exc())
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
