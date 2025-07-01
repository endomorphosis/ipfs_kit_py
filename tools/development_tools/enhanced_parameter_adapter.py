#!/usr/bin/env python3
"""
Enhanced Tool Parameter Adapter

This module provides robust parameter mapping between different naming conventions
used in MCP tool implementations and client calls.
"""

import inspect
import logging
import functools
import asyncio
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger("enhanced-parameter-adapter")

# Common parameter mappings across all tools
COMMON_PARAM_MAPPINGS = {
    # IPFS content parameters
    'content': ['content', 'data', 'text', 'value'],
    
    # IPFS identifiers
    'cid': ['cid', 'hash', 'content_id', 'ipfs_hash'],
    
    # Paths
    'path': ['path', 'file_path', 'filepath', 'mfs_path', 'vfs_path', 'fs_path'],
    
    # Backend parameters
    'backend_id': ['backend_id', 'backend', 'id', 'name'],
    'backend_type': ['backend_type', 'type'],
    
    # MFS parameters
    'source': ['source', 'src', 'from_path', 'from'],
    'dest': ['dest', 'destination', 'to_path', 'to', 'target'],
    
    # Pin parameters
    'recursive': ['recursive', 'recurse'],
    
    # Other
    'filename': ['filename', 'name', 'file_name'],
    'offset': ['offset', 'start'],
    'count': ['count', 'length', 'size', 'limit'],
    'create': ['create', 'create_if_not_exists'],
    'format': ['format', 'output_format'],
    'timeout': ['timeout', 'timeout_seconds'],
    'pin': ['pin', 'should_pin', 'keep'],
}

class ToolContext:
    """Wrapper for tool context to provide consistent access to parameters."""
    
    def __init__(self, ctx):
        self.original_ctx = ctx
        self.arguments = self._extract_arguments()
    
    def _extract_arguments(self) -> Dict[str, Any]:
        """Extract arguments from context."""
        if hasattr(self.original_ctx, 'arguments') and self.original_ctx.arguments is not None:
            return dict(self.original_ctx.arguments)
        elif hasattr(self.original_ctx, 'params') and self.original_ctx.params is not None:
            return dict(self.original_ctx.params)
        else:
            # Try to extract attributes as a fallback
            args = {}
            for attr_name in dir(self.original_ctx):
                if not attr_name.startswith('_') and not callable(getattr(self.original_ctx, attr_name)):
                    args[attr_name] = getattr(self.original_ctx, attr_name)
            return args
    
    async def info(self, message: str):
        """Log informational message."""
        if hasattr(self.original_ctx, 'info'):
            await self.original_ctx.info(message)
        else:
            logger.info(message)
    
    async def warning(self, message: str):
        """Log warning message."""
        if hasattr(self.original_ctx, 'warning'):
            await self.original_ctx.warning(message)
        else:
            logger.warning(message)
    
    async def error(self, message: str):
        """Log error message."""
        if hasattr(self.original_ctx, 'error'):
            await self.original_ctx.error(message)
        else:
            logger.error(message)


def adapt_parameters(func=None, *, mappings: Optional[Dict[str, list]] = None):
    """
    Decorator to adapt parameters for a tool function.
    
    Args:
        func: The function to decorate
        mappings: Additional parameter mappings specific to this function
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(ctx):
            # Wrap context for consistent access
            wrapped_ctx = ToolContext(ctx)
            
            # Get arguments from context
            arguments = wrapped_ctx.arguments
            
            # Combine common mappings with any function-specific mappings
            param_map = COMMON_PARAM_MAPPINGS.copy()
            if mappings:
                param_map.update(mappings)
            
            # Get expected parameters from function signature
            sig = inspect.signature(fn)
            expected_params = {}
            
            # Gather parameter info including defaults
            for name, param in sig.parameters.items():
                if name != 'ctx':
                    expected_params[name] = param.default if param.default is not param.empty else None
            
            # Map parameters
            mapped_args = {}
            
            # First pass: direct matches
            for param_name in expected_params:
                if param_name in arguments:
                    mapped_args[param_name] = arguments[param_name]
            
            # Second pass: try mapped parameters
            for param_name in expected_params:
                if param_name not in mapped_args:
                    # Find all possible alternative names for this parameter
                    alternatives = []
                    for target, alts in param_map.items():
                        if param_name == target:
                            alternatives.extend(alts)
                        elif param_name in alts:
                            alternatives.append(target)
                            alternatives.extend([a for a in alts if a != param_name])
                    
                    # Try each alternative name
                    for alt in alternatives:
                        if alt in arguments:
                            mapped_args[param_name] = arguments[alt]
                            logger.debug(f"Mapped parameter '{alt}' to '{param_name}'")
                            break
            
            # Log conversion for troubleshooting
            logger.debug(f"Original parameters: {arguments}")
            logger.debug(f"Mapped parameters: {mapped_args}")
            
            # Third pass: fill in defaults for missing parameters
            for param_name, default_value in expected_params.items():
                if param_name not in mapped_args and default_value is not None:
                    mapped_args[param_name] = default_value
            
            # Call with mapped parameters
            try:
                return await fn(**mapped_args)
            except Exception as e:
                error_msg = f"Error in {fn.__name__}: {str(e)}"
                logger.error(error_msg)
                await wrapped_ctx.error(error_msg)
                return {
                    "success": False,
                    "error": str(e),
                    "function": fn.__name__
                }
        
        # Store the original signature for inspection
        wrapper.original_sig = inspect.signature(fn)
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)


def create_tool_wrapper(impl_func, tool_name):
    """
    Create a wrapper function for a tool implementation.
    
    Args:
        impl_func: The implementation function
        tool_name: The name of the tool
    
    Returns:
        A wrapped async function that handles parameter adaptation
    """
    async def wrapper(ctx):
        # Get the tool context
        wrapped_ctx = ToolContext(ctx)
        arguments = wrapped_ctx.arguments
        
        # Log the call
        await wrapped_ctx.info(f"Called {tool_name}")
        
        try:
            # Extract parameters using inspection to match function signature
            sig = inspect.signature(impl_func)
            expected_params = [p for p in sig.parameters.keys()]
            
            # Map incoming parameter keys to expected function parameters
            # Handle common parameter naming discrepancies
            param_mappings = COMMON_PARAM_MAPPINGS
            
            # Create a dictionary of parameters matching the function signature
            processed_args = {}
            
            # First try direct matches
            for param in expected_params:
                if param in arguments:
                    processed_args[param] = arguments[param]
            
            # Then try mapped parameters for any that weren't directly matched
            for param in expected_params:
                if param not in processed_args:
                    # Find all possible alternative names for this parameter
                    alternatives = []
                    for target, alts in param_mappings.items():
                        if param == target:
                            alternatives.extend(alts)
                        elif param in alts:
                            alternatives.append(target)
                            alternatives.extend([a for a in alts if a != param])
                    
                    # Try each alternative name
                    for alt in alternatives:
                        if alt in arguments:
                            processed_args[param] = arguments[alt]
                            logger.debug(f"Mapped parameter '{alt}' to '{param}'")
                            break
            
            # Log the parameter mapping for debugging
            logger.debug(f"Tool: {tool_name}")
            logger.debug(f"Original arguments: {arguments}")
            logger.debug(f"Mapped arguments: {processed_args}")
            
            # Call the implementation with matched parameters
            result = await impl_func(**processed_args)
            return result
        except Exception as e:
            error_msg = f"Error executing {tool_name}: {str(e)}"
            logger.error(error_msg)
            await wrapped_ctx.error(error_msg)
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    return wrapper


def create_generic_handler(tool_name):
    """
    Create a generic handler for a tool with no specific implementation.
    
    Args:
        tool_name: The name of the tool
    
    Returns:
        A generic async function that handles any parameters
    """
    async def handler(ctx):
        # Get the tool context
        wrapped_ctx = ToolContext(ctx)
        arguments = wrapped_ctx.arguments
        
        # Log the call
        logger.info(f"Generic handler for {tool_name} with arguments: {arguments}")
        
        # Process common parameter types
        processed_result = {}
        
        for key, value in arguments.items():
            processed_result[key] = value
        
        # Add generic success indicators
        from datetime import datetime
        return {
            "success": True,
            "warning": "Generic implementation",
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            **processed_result  # Include the processed arguments in the result
        }
    
    return handler