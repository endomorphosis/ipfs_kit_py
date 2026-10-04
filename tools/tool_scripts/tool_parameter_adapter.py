#!/usr/bin/env python3
"""
Tool Parameter Adapter

This module provides adapter functions and parameter mapping to ensure that tools
correctly handle parameter names regardless of the context they're called in.
"""

import inspect
import logging
import functools

logger = logging.getLogger("tool-parameter-adapter")

def adapt_parameters(func):
    """Decorator to adapt parameters for a tool function."""
    
    @functools.wraps(func)
    async def wrapper(ctx):
        # Extract arguments from context
        arguments = {}
        if hasattr(ctx, 'arguments') and ctx.arguments is not None:
            arguments = ctx.arguments
        elif hasattr(ctx, 'params') and ctx.params is not None:
            arguments = ctx.params
        else:
            # Try to extract keyword arguments
            for attr_name in dir(ctx):
                if not attr_name.startswith('_') and not callable(getattr(ctx, attr_name)):
                    arguments[attr_name] = getattr(ctx, attr_name)
        
        # Common parameter mappings
        param_map = {
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
        }
        
        # Get expected parameters from function signature
        sig = inspect.signature(func)
        expected_params = [p for p in sig.parameters.keys() if p != 'ctx']
        
        # Map parameters
        mapped_args = {}
        
        for param in expected_params:
            # Direct match
            if param in arguments:
                mapped_args[param] = arguments[param]
                continue
            
            # Try mapped parameters
            for target, alternatives in param_map.items():
                if param == target:
                    # Try each alternative name
                    for alt in alternatives:
                        if alt in arguments:
                            mapped_args[param] = arguments[alt]
                            logger.debug(f"Mapped '{alt}' to '{param}'")
                            break
                    break
                elif param in alternatives and target in arguments:
                    # Parameter is an alternative name but target name is in arguments
                    mapped_args[param] = arguments[target]
                    logger.debug(f"Mapped '{target}' to '{param}'")
                    break
        
        logger.debug(f"Function: {func.__name__}, Expected params: {expected_params}, Mapped args: {mapped_args}")
        
        # Provide default values for missing parameters if they have defaults in the function signature
        for param_name, param in sig.parameters.items():
            if param_name not in mapped_args and param_name != 'ctx' and param.default is not param.empty:
                mapped_args[param_name] = param.default
                logger.debug(f"Using default value for '{param_name}'")
        
        # Call with mapped parameters
        try:
            return await func(**mapped_args)
        except TypeError as e:
            logger.error(f"Parameter mapping error for {func.__name__}: {e}")
            logger.error(f"Expected params: {expected_params}")
            logger.error(f"Mapped args: {mapped_args}")
            logger.error(f"Original arguments: {arguments}")
            return {
                "success": False,
                "error": f"Parameter mapping error: {e}",
                "function": func.__name__
            }
    
    return wrapper