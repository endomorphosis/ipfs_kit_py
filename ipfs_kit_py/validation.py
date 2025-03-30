"""
Parameter validation module for IPFS Kit.

This module provides utilities for validating parameters in IPFS Kit functions.
"""

import os
import shlex
from typing import Dict, Any, List, Optional, Union, Tuple


# Define security patterns
COMMAND_INJECTION_PATTERNS = [
    ';', '&', '|', '>', '<', '`', '$', '(', ')', '{', '}', '[', ']',
    '&&', '||', '\\', '\n', '\r', '\t', '\v', '\f', '\0'
]

# Define dangerous commands
DANGEROUS_COMMANDS = [
    'rm', 'chown', 'chmod', 'exec', 'eval', 'source', 
    'curl', 'wget', 'bash', 'sh', 'sudo', 'su'
]


class IPFSValidationError(Exception):
    """
    Exception raised for parameter validation errors.
    """
    pass


def validate_parameters(params: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate parameters against specification.
    
    Args:
        params: Dictionary of parameter values to validate
        spec: Dictionary describing parameter specification
              {
                  'param_name': {
                      'type': type,  # Required parameter type
                      'choices': [],  # Optional list of valid choices
                      'default': value,  # Optional default value
                      'min': value,  # Optional minimum value (for numbers)
                      'max': value  # Optional maximum value (for numbers)
                  }
              }
    
    Returns:
        Dictionary of validated parameters with defaults applied
        
    Raises:
        IPFSValidationError: If validation fails
    """
    result = {}
    
    # Apply defaults and validate provided values
    for param_name, param_spec in spec.items():
        # Get parameter type from spec
        expected_type = param_spec.get('type')
        
        # Check if parameter is provided
        if param_name in params:
            value = params[param_name]
            
            # Validate type if specified
            if expected_type is not None and not isinstance(value, expected_type):
                raise IPFSValidationError(
                    f"Parameter '{param_name}' has invalid type. "
                    f"Expected {expected_type.__name__}, got {type(value).__name__}"
                )
            
            # Validate choices if specified
            choices = param_spec.get('choices')
            if choices is not None and value not in choices:
                raise IPFSValidationError(
                    f"Parameter '{param_name}' has invalid value. "
                    f"Must be one of: {choices}"
                )
            
            # Validate min/max for numbers
            if isinstance(value, (int, float)):
                min_value = param_spec.get('min')
                if min_value is not None and value < min_value:
                    raise IPFSValidationError(
                        f"Parameter '{param_name}' is too small. "
                        f"Minimum value is {min_value}"
                    )
                
                max_value = param_spec.get('max')
                if max_value is not None and value > max_value:
                    raise IPFSValidationError(
                        f"Parameter '{param_name}' is too large. "
                        f"Maximum value is {max_value}"
                    )
            
            # Add validated value to result
            result[param_name] = value
            
        else:
            # Check if parameter is required
            if 'default' not in param_spec:
                raise IPFSValidationError(f"Required parameter '{param_name}' is missing")
            
            # Apply default value
            result[param_name] = param_spec['default']
    
    return result


def validate_cid(cid: str) -> bool:
    """
    Validate CID format.
    
    Args:
        cid: Content identifier to validate
        
    Returns:
        True if CID is valid, False otherwise
    """
    # Simple validation for now - just check basic format
    if not cid or not isinstance(cid, str):
        return False
    
    # CIDv0 is 46 characters, base58-encoded
    if len(cid) == 46 and cid.startswith('Qm'):
        return True
    
    # CIDv1 often starts with 'b' (base32), 'z' (base58), 'f' (base16), etc.
    if cid.startswith(('b', 'z', 'f')) and len(cid) > 8:
        return True
    
    return False


# Alias for backward compatibility
is_valid_cid = validate_cid


def validate_multiaddr(multiaddr: str) -> bool:
    """
    Validate multiaddress format.
    
    Args:
        multiaddr: Multiaddress to validate
        
    Returns:
        True if multiaddress is valid, False otherwise
    """
    # Simple validation for now - just check basic format
    if not multiaddr or not isinstance(multiaddr, str):
        return False
    
    # Check for protocol prefixes
    if multiaddr.startswith(('/ip4/', '/ip6/', '/dns4/', '/dns6/', '/dnsaddr/', '/unix/')):
        # Check for port or peer ID
        if '/tcp/' in multiaddr or '/udp/' in multiaddr:
            # Check for peer ID
            if '/p2p/' in multiaddr or '/ipfs/' in multiaddr:
                return True
            # Check for port
            parts = multiaddr.split('/')
            for i, part in enumerate(parts):
                if part in ('tcp', 'udp') and i + 1 < len(parts):
                    try:
                        port = int(parts[i + 1])
                        return 0 < port <= 65535
                    except ValueError:
                        return False
        
        # Unix socket paths don't need ports
        if multiaddr.startswith('/unix/'):
            return len(multiaddr) > 6
    
    return False


def validate_timeout(timeout: int) -> bool:
    """
    Validate timeout value.
    
    Args:
        timeout: Timeout value in seconds
        
    Returns:
        True if timeout is valid, False otherwise
    """
    if not isinstance(timeout, (int, float)):
        return False
    
    # Timeout must be positive
    if timeout <= 0:
        return False
    
    # Timeout should be reasonable (less than a day)
    if timeout > 86400:
        return False
    
    return True


def validate_path(path: str) -> bool:
    """
    Validate file or directory path.
    
    Args:
        path: Path to validate
        
    Returns:
        True if path is valid, False otherwise
    """
    if not path or not isinstance(path, str):
        return False
    
    # Check for absolute paths
    if not path.startswith('/'):
        return False
    
    # Basic sanity checks
    if '..' in path:
        return False
    
    # Check for non-printable characters
    for char in path:
        if ord(char) < 32:
            return False
    
    return True


def is_safe_path(path: str) -> bool:
    """
    Check if a path is safe to access.
    
    Args:
        path: Path to check
        
    Returns:
        True if path is safe, False otherwise
    """
    if not path or not isinstance(path, str):
        return False
    
    # Expand user home directory if present
    path = os.path.abspath(os.path.expanduser(path))
    
    # Check for path traversal attacks
    if '..' in path:
        return False
    
    # Check for symlink attacks
    try:
        if os.path.islink(path):
            return False
    except (OSError, ValueError):
        return False
    
    # Check for non-printable characters
    for char in path:
        if ord(char) < 32:
            return False
    
    return True


def validate_required_parameter(params: Dict[str, Any], param_name: str) -> bool:
    """
    Validate that a required parameter is present and not None.
    
    Args:
        params: Parameter dictionary
        param_name: Name of the parameter to check
        
    Returns:
        True if parameter is valid, False otherwise
        
    Raises:
        IPFSValidationError: If parameter is missing or None
    """
    if param_name not in params:
        raise IPFSValidationError(f"Required parameter '{param_name}' is missing")
    
    if params[param_name] is None:
        raise IPFSValidationError(f"Required parameter '{param_name}' cannot be None")
    
    return True


def validate_parameter_type(params: Dict[str, Any], param_name: str, expected_type: type) -> bool:
    """
    Validate that a parameter has the expected type.
    
    Args:
        params: Parameter dictionary
        param_name: Name of the parameter to check
        expected_type: Expected type of the parameter
        
    Returns:
        True if parameter is valid, False otherwise
        
    Raises:
        IPFSValidationError: If parameter has incorrect type
    """
    if param_name not in params:
        return True  # Skip validation for missing parameters
    
    if params[param_name] is None:
        return True  # Skip validation for None values
    
    if not isinstance(params[param_name], expected_type):
        raise IPFSValidationError(
            f"Parameter '{param_name}' has incorrect type. "
            f"Expected {expected_type.__name__}, got {type(params[param_name]).__name__}"
        )
    
    return True


def validate_command_args(args: Union[str, List[str]]) -> List[str]:
    """
    Validate and normalize command arguments.
    
    Args:
        args: Command arguments as a string or list
        
    Returns:
        Normalized command arguments as a list
        
    Raises:
        IPFSValidationError: If arguments are invalid
    """
    if args is None:
        return []
        
    if isinstance(args, str):
        # Split string into arguments using shell-like syntax
        try:
            args_list = shlex.split(args)
        except ValueError as e:
            raise IPFSValidationError(f"Invalid command arguments: {e}")
    elif isinstance(args, list):
        args_list = args
    else:
        raise IPFSValidationError(
            f"Command arguments must be a string or list, got {type(args).__name__}"
        )
    
    # Validate each argument
    for arg in args_list:
        if not isinstance(arg, str):
            raise IPFSValidationError(
                f"Command arguments must be strings, got {type(arg).__name__}"
            )
    
    return args_list


def is_safe_command_arg(arg: str) -> bool:
    """
    Check if a command argument is safe to use.
    
    Args:
        arg: Command argument to check
        
    Returns:
        True if argument is safe, False otherwise
    """
    if not arg or not isinstance(arg, str):
        return False
    
    # Check for shell injection patterns
    for pattern in COMMAND_INJECTION_PATTERNS:
        if pattern in arg:
            return False
    
    # Check for commands that could be dangerous
    for cmd in DANGEROUS_COMMANDS:
        if arg == cmd or arg.startswith(cmd + ' '):
            return False
    
    return True


def validate_binary_path(binary_path: str) -> str:
    """
    Validate and normalize binary path.
    
    Args:
        binary_path: Path to binary
        
    Returns:
        Normalized binary path
        
    Raises:
        IPFSValidationError: If binary path is invalid
    """
    if not binary_path or not isinstance(binary_path, str):
        raise IPFSValidationError("Binary path must be a non-empty string")
    
    # Expand user home directory if present
    expanded_path = os.path.expanduser(binary_path)
    
    # Check if path is executable for direct paths
    if os.path.isfile(expanded_path):
        if not os.access(expanded_path, os.X_OK):
            raise IPFSValidationError(f"Binary at '{expanded_path}' is not executable")
    
    return expanded_path


def validate_ipfs_path(ipfs_path: Optional[str]) -> str:
    """
    Validate and normalize IPFS path.
    
    Args:
        ipfs_path: Path to IPFS directory
        
    Returns:
        Normalized IPFS path
        
    Raises:
        IPFSValidationError: If IPFS path is invalid
    """
    # Use default path if None
    if ipfs_path is None:
        return os.path.expanduser("~/.ipfs")
    
    if not isinstance(ipfs_path, str):
        raise IPFSValidationError(f"IPFS path must be a string, got {type(ipfs_path).__name__}")
    
    # Expand user home directory if present
    expanded_path = os.path.expanduser(ipfs_path)
    
    return expanded_path


def validate_role(role: str) -> str:
    """
    Validate node role.
    
    Args:
        role: Node role (master, worker, or leecher)
        
    Returns:
        Normalized role string
        
    Raises:
        IPFSValidationError: If role is invalid
    """
    if not role or not isinstance(role, str):
        raise IPFSValidationError("Role must be a non-empty string")
    
    role = role.lower()
    if role not in ("master", "worker", "leecher"):
        raise IPFSValidationError(
            f"Invalid role: {role}. Must be one of: master, worker, leecher"
        )
    
    return role


def validate_role_permission(role: str, required_role: str) -> bool:
    """
    Validate if a role has permission for an operation.
    
    Args:
        role: Current node role
        required_role: Minimum required role
        
    Returns:
        True if role has permission, False otherwise
    """
    # Role hierarchy: master > worker > leecher
    role_hierarchy = {
        "master": 3,
        "worker": 2,
        "leecher": 1
    }
    
    # Validate roles
    if role not in role_hierarchy:
        raise IPFSValidationError(f"Invalid role: {role}")
    if required_role not in role_hierarchy:
        raise IPFSValidationError(f"Invalid required role: {required_role}")
    
    # Compare role levels
    return role_hierarchy[role] >= role_hierarchy[required_role]


def validate_resources(resources: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate and normalize resource constraints.
    
    Args:
        resources: Resource constraints
        
    Returns:
        Normalized resource constraints
        
    Raises:
        IPFSValidationError: If resources are invalid
    """
    if resources is None:
        return {}
    
    if not isinstance(resources, dict):
        raise IPFSValidationError(f"Resources must be a dictionary, got {type(resources).__name__}")
    
    normalized = {}
    
    # Process memory constraints
    if "max_memory" in resources:
        max_memory = resources["max_memory"]
        if isinstance(max_memory, str):
            # Parse human-readable size
            try:
                if max_memory.endswith("GB"):
                    normalized["max_memory"] = int(float(max_memory[:-2]) * 1024 * 1024 * 1024)
                elif max_memory.endswith("MB"):
                    normalized["max_memory"] = int(float(max_memory[:-2]) * 1024 * 1024)
                elif max_memory.endswith("KB"):
                    normalized["max_memory"] = int(float(max_memory[:-2]) * 1024)
                elif max_memory.endswith("B"):
                    normalized["max_memory"] = int(max_memory[:-1])
                else:
                    # Assume bytes
                    normalized["max_memory"] = int(max_memory)
            except ValueError:
                raise IPFSValidationError(f"Invalid max_memory value: {max_memory}")
        elif isinstance(max_memory, (int, float)):
            normalized["max_memory"] = int(max_memory)
        else:
            raise IPFSValidationError(
                f"max_memory must be a string or number, got {type(max_memory).__name__}"
            )
    
    # Process other resource constraints
    for key in resources:
        if key == "max_memory":
            continue  # Already processed
        
        normalized[key] = resources[key]
    
    return normalized