"""
Parameter validation module for IPFS Kit.

This module provides utilities for validating parameters in IPFS Kit functions.
"""

import os
import shlex
import re
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
    def __init__(self, message):
        self.message = message
        self.error_type = "validation_error"  # Make it an instance attribute
        super().__init__(message)


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


def validate_cid(cid: str, param_name: str = "cid") -> bool:
    """
    Validate CID format.
    
    Args:
        cid: Content identifier to validate
        param_name: Name of the parameter (for error messages)
        
    Returns:
        True if CID is valid
        
    Raises:
        IPFSValidationError: If CID format is invalid
    """
    # Check basic requirements
    if not cid:
        raise IPFSValidationError(f"Invalid {param_name}: empty value not allowed")
    
    if not isinstance(cid, str):
        raise IPFSValidationError(f"Invalid {param_name} type: Expected string, got {type(cid).__name__}")
    
    # CIDv0 is 46 characters, base58-encoded
    if len(cid) == 46 and cid.startswith('Qm'):
        return True
    
    # CIDv1 often starts with 'b' (base32), 'z' (base58), 'f' (base16), etc.
    if cid.startswith(('b', 'z', 'f')) and len(cid) > 8:
        return True
    
    raise IPFSValidationError(f"Invalid cid format: {cid}")


# Function to check if a CID is valid without raising exceptions
def is_valid_cid(cid: str) -> bool:
    """
    Check if a CID is valid without raising exceptions.
    
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


def validate_multiaddr(multiaddr: str, param_name: str = "multiaddr") -> bool:
    """
    Validate multiaddress format.
    
    Args:
        multiaddr: Multiaddress to validate
        param_name: Name of the parameter (for error messages)
        
    Returns:
        True if multiaddress is valid, False otherwise
        
    Raises:
        IPFSValidationError: If multiaddress format is invalid
    """
    # Check basic requirements
    if not multiaddr:
        raise IPFSValidationError(f"Invalid {param_name}: Cannot be empty")
    
    if not isinstance(multiaddr, str):
        raise IPFSValidationError(f"Invalid {param_name} type: Expected string, got {type(multiaddr).__name__}")
    
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
                        if 0 < port <= 65535:
                            return True
                    except ValueError:
                        pass
        
        # Unix socket paths don't need ports
        if multiaddr.startswith('/unix/'):
            if len(multiaddr) > 6:
                return True
    
    raise IPFSValidationError(f"Invalid {param_name} format: {multiaddr}")


def validate_timeout(timeout: int, param_name: str = "timeout") -> bool:
    """
    Validate timeout value.
    
    Args:
        timeout: Timeout value in seconds
        param_name: Name of the parameter (for error messages)
        
    Returns:
        True if timeout is valid, False otherwise
    """
    if not isinstance(timeout, (int, float)):
        raise IPFSValidationError(f"Invalid {param_name} type: Expected number, got {type(timeout).__name__}")
    
    # Timeout must be positive
    if timeout <= 0:
        raise IPFSValidationError(f"Invalid {param_name}: Must be positive")
    
    # Timeout should be reasonable (less than a day)
    if timeout > 86400:
        raise IPFSValidationError(f"Invalid {param_name}: Value too large (max 86400 seconds)")
    
    return True


def validate_path(path: str, param_name: str = "path") -> bool:
    """
    Validate file or directory path.
    
    Args:
        path: Path to validate
        param_name: Name of the parameter (for error messages)
        
    Returns:
        True if path is valid, False otherwise
    """
    if not path:
        raise IPFSValidationError(f"Invalid {param_name}: Cannot be empty")
    
    if not isinstance(path, str):
        raise IPFSValidationError(f"Invalid {param_name} type: Expected string, got {type(path).__name__}")
    
    # Check for path traversal patterns
    if '..' in path:
        raise IPFSValidationError(f"Invalid {param_name}: Contains directory traversal pattern")
    
    # Check for non-printable characters
    for char in path:
        if ord(char) < 32:
            raise IPFSValidationError(f"Invalid {param_name}: Contains non-printable characters")
    
    # Check for command injection patterns
    for pattern in COMMAND_INJECTION_PATTERNS:
        if pattern in path:
            raise IPFSValidationError(f"Invalid {param_name}: Contains potentially dangerous pattern")
    
    return True


def is_safe_path(path: str) -> bool:
    """
    Check if a path is safe to access without raising exceptions.
    
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


def validate_required_parameter(value: Any, param_name: str) -> bool:
    """
    Validate that a required parameter is present and not None.
    
    Args:
        value: Parameter value to check
        param_name: Name of the parameter
        
    Returns:
        True if parameter is valid, False otherwise
        
    Raises:
        IPFSValidationError: If parameter is missing or None
    """
    if value is None:
        raise IPFSValidationError(f"Missing required parameter: {param_name}")
    
    return True


def validate_parameter_type(value: Any, expected_type: type, param_name: str) -> bool:
    """
    Validate that a parameter has the expected type.
    
    Args:
        value: Parameter value to check
        expected_type: Expected type of the parameter
        param_name: Name of the parameter
        
    Returns:
        True if parameter is valid, False otherwise
        
    Raises:
        IPFSValidationError: If parameter has incorrect type
    """
    if value is None:
        return True  # Skip validation for None values
    
    if not isinstance(value, expected_type):
        raise IPFSValidationError(
            f"Parameter '{param_name}' has incorrect type. "
            f"Expected {expected_type.__name__}, got {type(value).__name__}"
        )
    
    return True


def validate_command_args(args: Dict[str, Any]) -> bool:
    """
    Validate command arguments for security issues.
    
    Args:
        args: Command arguments as a dictionary (kwargs)
        
    Returns:
        True if arguments are valid, False otherwise
        
    Raises:
        IPFSValidationError: If arguments are invalid
    """
    if args is None:
        return True
        
    if not isinstance(args, dict):
        raise IPFSValidationError(
            f"Command arguments must be a dictionary, got {type(args).__name__}"
        )
    
    # Validate each string argument
    for key, value in args.items():
        if isinstance(value, str):
            # Check for shell injection patterns
            for pattern in COMMAND_INJECTION_PATTERNS:
                if pattern in value:
                    # Exception for common parameters that might contain these characters
                    # like base64 encodings or URLs
                    if key in ['content', 'encoded', 'url', 'base64'] and pattern in ['+', '=', '/']:
                        continue
                    raise IPFSValidationError(
                        f"Parameter '{key}' contains potentially dangerous pattern: {pattern}"
                    )
    
    return True


def is_safe_command_arg(arg: str) -> bool:
    """
    Check if a command argument is safe to use without raising exceptions.
    
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
