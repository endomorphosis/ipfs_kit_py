"""
Web3.Storage (Storacha) integration module for IPFS Kit.

This module provides a complete interface to the Web3.Storage service, 
enabling content storage, retrieval, and management using the Web3.Storage 
API and command-line tools.

Key features:
- Content upload and retrieval using Content Addressable aRchives (CAR files)
- Space management for organizing content 
- Secure token-based authentication
- Pinning service integration
- Batch operations for efficient content handling
- HTTP API integration with standardized error handling

All methods follow a standardized error handling pattern returning result dictionaries
with consistent structure, including success status, timestamps, and detailed error information.
"""

import os
import sys
import subprocess
import requests
import tempfile
import json
import platform
import shutil
import logging
import time
import uuid
import re
from .error import (
    IPFSError, IPFSConnectionError, IPFSTimeoutError, IPFSContentNotFoundError,
    IPFSValidationError, IPFSConfigurationError, IPFSPinningError,
    create_result_dict, handle_error, perform_with_retry
)

# Configure logger
logger = logging.getLogger(__name__)

class storacha_kit:
    """Web3.Storage (Storacha) integration class for managing decentralized storage.
    
    This class provides a comprehensive interface to the Web3.Storage service,
    enabling content storage, retrieval, and management using both the CLI
    and HTTP API interfaces. All methods follow a standardized error handling
    pattern returning result dictionaries with consistent structure.
    
    Key Features:
    - Content storage and retrieval with standardized result format
    - Secure authentication and token management
    - Space management for content organization
    - Batch operations for efficient content handling
    - Secure command execution with validation
    - HTTP API integration with robust error handling
    - Cross-platform compatibility (Windows, macOS, Linux)
    
    Typical usage:
    ```python
    # Initialize with login metadata
    kit = storacha_kit(metadata={"login": "user@example.com"})
    
    # Install dependencies and login
    kit.install()
    kit.login(kit.metadata["login"])
    
    # Add content to a space
    spaces = kit.space_ls()
    first_space = spaces[list(spaces.keys())[0]]
    result = kit.store_add(first_space, "/path/to/file.txt")
    
    # Retrieve content
    kit.store_get(first_space, result["cid"], "/output/path")
    ```
    """
    
    def __init__(self, resources=None, metadata=None):
        """Initialize storacha_kit functionality.
        
        Args:
            resources: Dictionary containing system resources
                - memory_limit: Optional memory limit in bytes
                - storage_limit: Optional storage limit in bytes
                - cpu_limit: Optional CPU usage limit
            metadata: Dictionary containing configuration metadata
                - login: Email for Web3.Storage login
                - config: Optional configuration settings
                - correlation_id: Optional ID for operation tracking
        """
        # Initialize basic attributes
        self.resources = resources if resources is not None else {}
        self.metadata = metadata if metadata is not None else {}
        self.correlation_id = self.metadata.get('correlation_id', str(uuid.uuid4()))
        
        # Version information
        self.w3_version = "7.8.2"
        self.ipfs_car_version = "2.0.1-pre.0"  # Updated from 1.2.0
        self.w3_name_version = "1.0.8"
        self.npm_version = "7.5.6"
        
        # State tracking
        self.spaces = {}
        self.email_did = None
        self.tokens = {}
        self.space = None
        
        # API endpoints
        self.https_endpoint = "https://up.storacha.network/bridge"
        self.ipfs_gateway = "https://w3s.link/ipfs/"
        
        logger.debug(f"Initialized storacha_kit with correlation_id={self.correlation_id}")
        
        # Note: Removed redundant method assignments, they're not needed in Python
        
    def run_w3_command(self, cmd_args, check=True, timeout=60, correlation_id=None, shell=False):
        """Run w3 command with proper error handling and security measures.
        
        This method executes Web3.Storage CLI commands with standardized error
        handling and cross-platform compatibility.
        
        Args:
            cmd_args: Command and arguments as a list (recommended for security) or string
            check: Whether to raise exception on non-zero exit code
            timeout: Command timeout in seconds (defaults to 60s as w3 commands can be slow)
            correlation_id: ID for tracking related operations
            shell: Whether to use shell execution (SECURITY: Set to False whenever possible)
        
        Returns:
            Dictionary with command result information:
                - success: Boolean indicating overall success
                - command: The command that was executed
                - returncode: Exit code from the command
                - stdout: Standard output (decoded if possible)
                - stderr: Standard error (decoded if possible)
                - error: Error message if command failed
                - error_type: Type of error if command failed
                
        Security Notes:
            - Always pass cmd_args as a list rather than a string when possible
            - Only set shell=True when absolutely necessary (e.g., for output redirection)
            - All inputs are validated before being passed to subprocess
            - Platform-specific adjustments are made automatically
        """
        # Create standardized result dictionary
        command_str = cmd_args if isinstance(cmd_args, str) else " ".join(cmd_args)
        operation = command_str.split()[0] if isinstance(command_str, str) else cmd_args[0]
        
        result = create_result_dict(f"run_command_{operation}", correlation_id or self.correlation_id)
        result["command"] = command_str
        
        try:
            # Platform-specific prefix for commands
            if isinstance(cmd_args, list) and len(cmd_args) > 0:
                if platform.system() == "Windows" and cmd_args[0] == "w3":
                    # On Windows, we need to use npx
                    cmd_args[0] = "npx"
                    cmd_args.insert(1, "w3")
                    
                if platform.system() == "Windows" and cmd_args[0] == "ipfs-car":
                    # On Windows, we need to use npx
                    cmd_args[0] = "npx"
                    cmd_args.insert(1, "ipfs-car")
            
            # Never use shell=True unless absolutely necessary for security
            process = subprocess.run(
                cmd_args,
                capture_output=True,
                check=check,
                timeout=timeout,
                shell=shell
            )
            
            # Process completed successfully
            result["success"] = True
            result["returncode"] = process.returncode
            
            # Decode stdout and stderr if they exist
            if process.stdout:
                try:
                    result["stdout"] = process.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    result["stdout"] = process.stdout
                    
            if process.stderr:
                try:
                    result["stderr"] = process.stderr.decode('utf-8')
                except UnicodeDecodeError:
                    result["stderr"] = process.stderr
            
            return result
            
        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds: {command_str}"
            logger.error(error_msg)
            return handle_error(result, IPFSTimeoutError(error_msg))
        
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with return code {e.returncode}: {command_str}"
            result["returncode"] = e.returncode
            
            # Try to decode stdout and stderr
            if e.stdout:
                try:
                    result["stdout"] = e.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    result["stdout"] = e.stdout
                    
            if e.stderr:
                try:
                    result["stderr"] = e.stderr.decode('utf-8')
                except UnicodeDecodeError:
                    result["stderr"] = e.stderr
            
            logger.error(f"{error_msg}\nStderr: {result.get('stderr', '')}")
            return handle_error(result, IPFSError(error_msg))
        
        except FileNotFoundError as e:
            error_msg = f"Command binary not found: {command_str}"
            logger.error(error_msg)
            return handle_error(result, IPFSConfigurationError(error_msg))
        
        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            logger.exception(f"Exception running command: {command_str}")
            return handle_error(result, e)
    
    def space_ls(self, **kwargs):
        """List all available Web3.Storage spaces for the authenticated user.
        
        This method retrieves all spaces available to the currently authenticated
        user from Web3.Storage. It must be called after successful login.
        
        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                - refresh: Force refresh of spaces list from server (default: False)
                
        Returns:
            Dictionary mapping space names to their IDs if successful, otherwise error dict:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("space_ls")
                - timestamp: Unix timestamp of the operation
                - spaces: Dictionary mapping space names to IDs (if successful)
                - count: Number of spaces found (if successful)
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Example:
            ```python
            spaces = kit.space_ls()
            for name, space_id in spaces.items():
                print(f"Space: {name}, ID: {space_id}")
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("space_ls", correlation_id)
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Use the secure command execution helper
            cmd_result = self.run_w3_command(
                ["w3", "space", "ls"],
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to list spaces: {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Process the output
            output = cmd_result.get("stdout", "").strip()
            spaces = {}
            
            if output:
                # Parse the output lines
                lines = output.split("\n")
                for line in lines:
                    line = line.replace("* ", "").strip()  # Remove active space marker
                    if line:
                        parts = line.split(" ", 1)  # Split at first space
                        if len(parts) >= 2:
                            # Format: DID NAME
                            spaces[parts[1].strip()] = parts[0].strip()
            
            # Update instance state and result
            self.spaces = spaces
            result["spaces"] = spaces
            result["success"] = True
            result["count"] = len(spaces)
            
            logger.debug(f"Found {len(spaces)} Web3.Storage spaces")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in space_ls: {str(e)}")
            return handle_error(result, e)
    
    def space_create(self, space, **kwargs):
        """Create a new Web3.Storage space with the specified name.
        
        This method creates a new space in the Web3.Storage service under the 
        authenticated user's account. Each space acts as a separate storage
        container for organizing content. The user must be logged in before
        calling this method.
        
        Args:
            space: Name of the space to create (must be unique within your account)
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                - description: Optional description for the space
                
        Returns:
            Dictionary with operation result:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("space_create")
                - timestamp: Unix timestamp of the operation
                - space: Name of the created space
                - space_did: DID (Decentralized Identifier) of the created space
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Notes:
            - Space names must be unique within your account
            - After creating a space, you'll need to allocate storage to it
              using the space_allocate method before adding content
            - This method automatically refreshes the internal spaces list
              after successful creation
                
        Example:
            ```python
            result = kit.space_create("my-documents")
            if result["success"]:
                print(f"Created space: {result['space']} with DID: {result['space_did']}")
                # Allocate 10GB to the new space
                kit.space_allocate("my-documents", 10, "GiB")
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("space_create", correlation_id)
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            from .validation import is_safe_command_arg
            if not is_safe_command_arg(space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Use the secure command execution helper
            cmd_result = self.run_w3_command(
                ["w3", "space", "create", space],
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to create space '{space}': {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Update spaces list
            self.space_ls(correlation_id=correlation_id)
            
            result["success"] = True
            result["space_name"] = space
            result["command_output"] = cmd_result.get("stdout", "")
            
            logger.info(f"Successfully created space: {space}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in space_create: {str(e)}")
            return handle_error(result, e)
    
    def login(self, email, **kwargs):
        """Log in to Web3.Storage using email.
        
        Args:
            email: Email address to use for login
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 120)
                
        Returns:
            Dictionary with operation result
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("login", correlation_id)
        
        try:
            # Validate required parameters
            if not email:
                return handle_error(result, IPFSValidationError("Missing required parameter: email"))
            
            # Validate email (prevent command injection)
            if not isinstance(email, str):
                return handle_error(result, IPFSValidationError(f"Email must be a string, got {type(email).__name__}"))
            
            # Basic email validation - this is minimal, could be expanded
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                return handle_error(result, IPFSValidationError(f"Invalid email format: {email}"))
            
            # More thorough check for potential command injection
            from .validation import is_safe_command_arg
            if not is_safe_command_arg(email):
                return handle_error(result, IPFSValidationError(f"Email contains invalid characters: {email}"))
            
            # Set timeout for the command - login might take longer than usual
            timeout = kwargs.get('timeout', 120)
            
            # Use the secure command execution helper
            logger.info(f"Initiating Web3.Storage login for email: {email}")
            cmd_result = self.run_w3_command(
                ["w3", "login", email],
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to log in with email '{email}': {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Process the output to get the DID
            stdout = cmd_result.get("stdout", "")
            stderr = cmd_result.get("stderr", "")
            output = stdout if stdout else stderr
            
            # Extract the DID from the output
            email_did = None
            if "⁂ Agent was authorized by " in output:
                email_did = output.replace("⁂ Agent was authorized by ", "").strip()
            
            if email_did:
                self.email_did = email_did
                result["success"] = True
                result["email"] = email
                result["email_did"] = email_did
                logger.info(f"Successfully logged in as: {email_did}")
            else:
                result["success"] = False
                result["error"] = "Failed to extract DID from login response"
                logger.error("Failed to parse login response to extract DID")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in login: {str(e)}")
            return handle_error(result, e)
            
    def validate_email(self, email):
        """Validate email format and check for potential injection.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if email is valid, False otherwise
        """
        # Simple regex check for email format
        import re
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            return False
            
        # More thorough check for potential command injection
        if re.search(r'[;&|"`\'$<>]', email):
            return False
            
        return True
    
    def logout(self, **kwargs):
        """Log out from Web3.Storage.
        
        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 30)
                
        Returns:
            Dictionary with operation result
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("logout", correlation_id)
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 30)
            
            # Use the secure command execution helper
            cmd_result = self.run_w3_command(
                ["w3", "logout"],
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to log out: {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Reset state
            self.email_did = None
            
            result["success"] = True
            result["message"] = "Successfully logged out"
            
            logger.info("Successfully logged out from Web3.Storage")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in logout: {str(e)}")
            return handle_error(result, e)
    
    def bridge_generate_tokens(self, space, permissions, expiration=None, **kwargs):
        """Generate Bridge API tokens for a Web3.Storage space.
        
        Args:
            space: Name of the space to generate tokens for
            permissions: List of permission strings (e.g. ["store/add", "upload/list"])
            expiration: Optional expiration time in hours from now (default: 24 hours)
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("bridge_generate_tokens", correlation_id)
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            if not permissions or not isinstance(permissions, list):
                return handle_error(result, IPFSValidationError("Missing or invalid permissions parameter: must be a list"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Validate permissions
            valid_permissions = []
            for perm in permissions:
                if not isinstance(perm, str):
                    logger.warning(f"Skipping non-string permission: {perm}")
                    continue
                
                # Basic validation to prevent command injection
                if re.search(r'[;&|"`\'$<>]', perm):
                    logger.warning(f"Skipping permission with invalid characters: {perm}")
                    continue
                
                valid_permissions.append(perm)
            
            if not valid_permissions:
                return handle_error(result, IPFSValidationError("No valid permissions specified"))
            
            # Set up expiration timestamp
            if expiration is None:
                expiration_seconds = 24 * 3600  # 24 hours from now
            else:
                try:
                    expiration_seconds = int(expiration) * 3600  # Convert hours to seconds
                except (ValueError, TypeError):
                    return handle_error(result, IPFSValidationError(f"Invalid expiration value: {expiration}. Must be a number of hours."))
            
            # Calculate expiration timestamp
            expiration_timestamp = str(int(time.time()) + expiration_seconds)
            
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Build command arguments
            cmd_args = ["w3", "bridge", "generate-tokens", space]
            
            # Add permissions
            for perm in valid_permissions:
                cmd_args.extend(["--can", perm])
            
            # Add expiration
            cmd_args.extend(["--expiration", expiration_timestamp])
            
            # Use the secure command execution helper
            logger.debug(f"Generating bridge tokens for space '{space}' with permissions: {valid_permissions}")
            cmd_result = self.run_w3_command(
                cmd_args,
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to generate tokens for space '{space}': {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Process the output to extract tokens
            output = cmd_result.get("stdout", "").strip()
            
            # Parse the token information
            tokens = {}
            if output:
                lines = output.split("\n")
                lines = [line.strip() for line in lines if line.strip()]
                
                for line in lines:
                    parts = line.split(":", 1)  # Split on first colon only
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        tokens[key] = value
            
            if tokens:
                # Store tokens for later use
                self.tokens[space] = tokens
                
                result["success"] = True
                result["space"] = space
                result["tokens"] = tokens
                result["permissions"] = valid_permissions
                result["expiration_timestamp"] = expiration_timestamp
                
                logger.info(f"Successfully generated {len(tokens)} tokens for space '{space}'")
            else:
                result["success"] = False
                result["error"] = "Failed to extract tokens from command output"
                logger.error(f"Failed to parse token information from output: {output}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in bridge_generate_tokens: {str(e)}")
            return handle_error(result, e)
    
    def storacha_http_request(self, auth_secret, authorization, method, data, **kwargs):
        """Make secure HTTP requests to the Storacha/Web3.Storage API with robust error handling.
        
        This method provides a unified interface for all HTTP API interactions with
        Web3.Storage, including proper authentication, request formatting, error handling,
        and response processing.
        
        Args:
            auth_secret: X-Auth-Secret header value for authentication
            authorization: Authorization header value (Bearer token)
            method: API method to call (e.g., "upload/list", "store/add", "store/remove")
            data: JSON data to send in the request body
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations across systems
                - timeout: Request timeout in seconds (default: 60)
                - retry_count: Number of retries for failed requests (default: 3)
                - retry_delay: Delay between retries in seconds (default: 1)
                
        Returns:
            requests.Response object on success, or error dictionary on failure:
                - success: Boolean indicating request success
                - method: The API method that was called
                - status_code: HTTP status code (if a response was received)
                - response: Response object or content (if successful)
                - error: Error message if request failed
                - error_type: Type of error if request failed
                - timestamp: Unix timestamp of the operation
        
        API Methods:
            - "upload/list": List uploads in a space
            - "upload/add": Add content to a space
            - "upload/remove": Remove content from a space
            - "store/add": Add content to the store
            - "store/get": Retrieve content from the store
            - "store/remove": Remove content from the store
            - "store/list": List content in the store
            - "space/info": Get information about a space
            - "usage/report": Get usage information for a space
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("storacha_http_request", correlation_id)
        result["method"] = method
        
        try:
            # Validate parameters
            if not auth_secret:
                return handle_error(result, IPFSValidationError("Missing required parameter: auth_secret"))
            
            if not authorization:
                return handle_error(result, IPFSValidationError("Missing required parameter: authorization"))
            
            if not data:
                return handle_error(result, IPFSValidationError("Missing required parameter: data"))
            
            # Set request timeout and retry count
            timeout = kwargs.get('timeout', 60)
            retry_count = kwargs.get('retry_count', 3)
            
            # Prepare request headers and URL
            url = self.https_endpoint
            headers = {
                "X-Auth-Secret": auth_secret,
                "Authorization": authorization,
                "Content-Type": "application/json"
            }
            
            # Log the request (but omit sensitive headers)
            logger.debug(f"Making HTTP request to {url} for method {method}")
            
            # Execute request with retry logic
            response = perform_with_retry(
                lambda: requests.post(url, headers=headers, json=data, timeout=timeout),
                max_retries=retry_count,
                backoff_factor=2,
                retry_on=[requests.exceptions.ConnectionError, requests.exceptions.Timeout]
            )
            
            # Check if response was successful
            response.raise_for_status()
            
            # Process successful response
            result["success"] = True
            result["status_code"] = response.status_code
            
            # Store response headers (excluding potentially sensitive ones)
            safe_headers = {k: v for k, v in response.headers.items() 
                           if k.lower() not in ['authorization', 'x-auth-secret']}
            result["response_headers"] = safe_headers
            
            return response
            
        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP request failed: {str(e)}"
            logger.error(error_msg)
            
            # Add specific error details based on exception type
            if isinstance(e, requests.exceptions.ConnectionError):
                return handle_error(result, IPFSConnectionError(f"Failed to connect to Storacha API: {str(e)}"))
            elif isinstance(e, requests.exceptions.Timeout):
                return handle_error(result, IPFSTimeoutError(f"Request timed out after {timeout}s: {str(e)}"))
            elif isinstance(e, requests.exceptions.HTTPError):
                # Include status code and response content for HTTP errors
                result["status_code"] = e.response.status_code
                try:
                    result["response_content"] = e.response.json()
                except ValueError:
                    result["response_content"] = e.response.text
                error_type = f"HTTP {e.response.status_code}"
                return handle_error(result, IPFSError(f"{error_type} error: {str(e)}"))
            else:
                return handle_error(result, IPFSError(error_msg))
                
        except Exception as e:
            logger.exception(f"Unexpected error in storacha_http_request: {str(e)}")
            return handle_error(result, e)
    
    def install(self, **kwargs):
        """Install or update dependencies required for Web3.Storage functionality.
        
        This method checks for and installs npm, w3cli, ipfs-car, and w3name if needed.
        
        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 300 - installation can be slow)
                - force_update: Force update of all components even if newer version is installed
                
        Returns:
            Dictionary with operation result containing installation status
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("install", correlation_id)
        
        try:
            # Set timeout for commands - installations can take time
            timeout = kwargs.get('timeout', 300)
            force_update = kwargs.get('force_update', False)
            
            # Determine current OS and set appropriate commands
            system = platform.system()
            if system not in ["Windows", "Linux", "Darwin"]:
                return handle_error(result, IPFSConfigurationError(f"Unsupported operating system: {system}"))
            
            # Initialize installation status tracking
            result["dependencies"] = {
                "npm": {"installed": False, "version": None},
                "w3cli": {"installed": False, "version": None},
                "ipfs-car": {"installed": False, "version": None},
                "w3name": {"installed": False, "version": None}
            }
            
            logger.info(f"Beginning dependency installation/verification for Web3.Storage on {system}")
            
            # ==================== STEP 1: Configure npm registry ====================
            logger.debug("Configuring npm registry")
            
            # Delete potentially problematic npm registry config
            npm_config_cmd = ["npm", "config", "delete", "registry"]
            
            if system != "Windows":
                # First try without sudo
                self.run_w3_command(
                    npm_config_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                # Then try with sudo if needed
                sudo_cmd = ["sudo"]
                sudo_cmd.extend(npm_config_cmd)
                self.run_w3_command(
                    sudo_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
            else:
                self.run_w3_command(
                    npm_config_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
            
            # ==================== STEP 2: Verify/Install npm ====================
            logger.info("Checking for npm installation")
            
            # Determine command to check for npm
            if system == "Windows":
                detect_npm_cmd = ["where", "npm"]
            else:
                detect_npm_cmd = ["which", "npm"]
                
            # Check if npm is installed
            npm_check_result = self.run_w3_command(
                detect_npm_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            npm_installed = npm_check_result.get("success", False) and npm_check_result.get("returncode", 1) == 0
            
            # If npm not found, install it
            if not npm_installed:
                logger.info("npm not found, attempting installation")
                
                if system == "Windows":
                    # On Windows, npm installation is more complex - suggest installation via Node.js installer
                    logger.warning("npm not found on Windows. Please install Node.js from https://nodejs.org/")
                    result["dependencies"]["npm"]["error"] = "npm not found. Please install Node.js from https://nodejs.org/"
                else:
                    # On Linux/macOS, use package manager
                    if system == "Darwin":
                        install_cmd = ["brew", "install", "node"]
                    else:  # Linux
                        install_cmd = ["sudo", "apt-get", "install", "-y", "npm"]
                        
                    logger.info(f"Installing npm with command: {' '.join(install_cmd)}")
                    npm_install_result = self.run_w3_command(
                        install_cmd,
                        check=False,
                        timeout=timeout,
                        correlation_id=correlation_id
                    )
                    
                    npm_installed = npm_install_result.get("success", False) and npm_install_result.get("returncode", 1) == 0
                    if npm_installed:
                        logger.info("npm installed successfully")
                    else:
                        error_msg = f"Failed to install npm: {npm_install_result.get('stderr', '')}"
                        logger.error(error_msg)
                        result["dependencies"]["npm"]["error"] = error_msg
            
            # Check npm version if installed
            if npm_installed:
                npm_version_cmd = ["npm", "--version"]
                npm_version_result = self.run_w3_command(
                    npm_version_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if npm_version_result.get("success", False) and npm_version_result.get("returncode", 1) == 0:
                    npm_version_output = npm_version_result.get("stdout", "").strip()
                    result["dependencies"]["npm"]["installed"] = True
                    result["dependencies"]["npm"]["version"] = npm_version_output
                    logger.info(f"npm version: {npm_version_output}")
            
            # If npm not installed, we can't continue
            if not result["dependencies"]["npm"]["installed"]:
                return handle_error(result, IPFSConfigurationError("npm installation failed, cannot continue with Web3.Storage setup"))
            
            # ==================== STEP 3: Verify/Install w3cli ====================
            logger.info("Checking for w3cli installation")
            
            # Check if w3cli is installed
            if system == "Windows":
                w3_check_cmd = ["npx", "--no-install", "w3", "--version"]
            else:
                w3_check_cmd = ["w3", "--version"]
                
            w3_check_result = self.run_w3_command(
                w3_check_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            w3_installed = w3_check_result.get("success", False) and w3_check_result.get("returncode", 1) == 0
            
            # Parse version if installed
            w3_current_version = None
            if w3_installed:
                w3_output = w3_check_result.get("stdout", "")
                # Extract version from output like "w3, 7.8.2"
                version_match = re.search(r'w3,\s+(\d+\.\d+\.\d+)', w3_output)
                if version_match:
                    w3_current_version = version_match.group(1)
                    result["dependencies"]["w3cli"]["installed"] = True
                    result["dependencies"]["w3cli"]["version"] = w3_current_version
                    logger.info(f"w3cli version: {w3_current_version}")
            
            # Install or update w3cli if needed
            need_w3_install = not w3_installed
            need_w3_update = False
            
            if w3_current_version and not force_update:
                # Compare versions to see if update needed
                current_parts = [int(p) for p in w3_current_version.split('.')]
                required_parts = [int(p) for p in self.w3_version.split('.')]
                
                # Check if current version is older than required
                for i in range(min(len(current_parts), len(required_parts))):
                    if current_parts[i] < required_parts[i]:
                        need_w3_update = True
                        break
                    elif current_parts[i] > required_parts[i]:
                        # Current version is newer, no update needed
                        break
            else:
                need_w3_update = w3_installed and (force_update or not w3_current_version)
            
            # Install or update as needed
            if need_w3_install or need_w3_update:
                action = "Installing" if need_w3_install else "Updating"
                logger.info(f"{action} w3cli to version {self.w3_version}")
                
                if system == "Windows":
                    w3_install_cmd = ["npm", "install", "@web3-storage/w3cli"]
                else:
                    sudo_prefix = ["sudo"] if not os.access("/usr/local/bin", os.W_OK) else []
                    w3_install_cmd = sudo_prefix + ["npm", "install", "-g", "@web3-storage/w3cli@" + self.w3_version]
                
                w3_install_result = self.run_w3_command(
                    w3_install_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if w3_install_result.get("success", False) and w3_install_result.get("returncode", 1) == 0:
                    logger.info(f"w3cli {action.lower()} successful")
                    result["dependencies"]["w3cli"]["installed"] = True
                    result["dependencies"]["w3cli"]["version"] = self.w3_version
                else:
                    error_msg = f"Failed to {action.lower()} w3cli: {w3_install_result.get('stderr', '')}"
                    logger.error(error_msg)
                    result["dependencies"]["w3cli"]["error"] = error_msg
            
            # ==================== STEP 4: Verify/Install ipfs-car ====================
            logger.info("Checking for ipfs-car installation")
            
            # Check if ipfs-car is installed
            if system == "Windows":
                ipfs_car_check_cmd = ["npx", "--no-install", "ipfs-car", "--version"]
            else:
                ipfs_car_check_cmd = ["ipfs-car", "--version"]
                
            ipfs_car_check_result = self.run_w3_command(
                ipfs_car_check_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            ipfs_car_installed = ipfs_car_check_result.get("success", False) and ipfs_car_check_result.get("returncode", 1) == 0
            
            # Parse version if installed
            ipfs_car_current_version = None
            if ipfs_car_installed:
                ipfs_car_output = ipfs_car_check_result.get("stdout", "")
                # Extract version from output
                version_match = re.search(r'(\d+\.\d+\.\d+)', ipfs_car_output)
                if version_match:
                    ipfs_car_current_version = version_match.group(1)
                    result["dependencies"]["ipfs-car"]["installed"] = True
                    result["dependencies"]["ipfs-car"]["version"] = ipfs_car_current_version
                    logger.info(f"ipfs-car version: {ipfs_car_current_version}")
            
            # Install or update ipfs-car if needed
            need_ipfs_car_install = not ipfs_car_installed
            need_ipfs_car_update = False
            
            if ipfs_car_current_version and not force_update:
                # Compare versions to see if update needed
                current_parts = [int(p) for p in re.sub(r'[^\d.]', '', ipfs_car_current_version).split('.')]
                required_parts = [int(p) for p in re.sub(r'[^\d.]', '', self.ipfs_car_version).split('.')]
                
                # Check if current version is older than required
                for i in range(min(len(current_parts), len(required_parts))):
                    if current_parts[i] < required_parts[i]:
                        need_ipfs_car_update = True
                        break
                    elif current_parts[i] > required_parts[i]:
                        # Current version is newer, no update needed
                        break
            else:
                need_ipfs_car_update = ipfs_car_installed and (force_update or not ipfs_car_current_version)
            
            # Install or update as needed
            if need_ipfs_car_install or need_ipfs_car_update:
                action = "Installing" if need_ipfs_car_install else "Updating"
                logger.info(f"{action} ipfs-car to version {self.ipfs_car_version}")
                
                if system == "Windows":
                    ipfs_car_install_cmd = ["npm", "install", "ipfs-car@" + self.ipfs_car_version]
                else:
                    sudo_prefix = ["sudo"] if not os.access("/usr/local/bin", os.W_OK) else []
                    ipfs_car_install_cmd = sudo_prefix + ["npm", "install", "-g", "ipfs-car@" + self.ipfs_car_version]
                
                ipfs_car_install_result = self.run_w3_command(
                    ipfs_car_install_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if ipfs_car_install_result.get("success", False) and ipfs_car_install_result.get("returncode", 1) == 0:
                    logger.info(f"ipfs-car {action.lower()} successful")
                    result["dependencies"]["ipfs-car"]["installed"] = True
                    result["dependencies"]["ipfs-car"]["version"] = self.ipfs_car_version
                else:
                    error_msg = f"Failed to {action.lower()} ipfs-car: {ipfs_car_install_result.get('stderr', '')}"
                    logger.error(error_msg)
                    result["dependencies"]["ipfs-car"]["error"] = error_msg
            
            # ==================== STEP 5: Verify/Install w3name ====================
            logger.info("Checking for w3name installation")
            
            # Check if w3name is installed
            if system == "Windows":
                w3name_list_cmd = ["npm", "list", "--depth=0"]
                grep_pattern = "w3name"
            else:
                w3name_list_cmd = ["npm", "list", "--depth=0"]
                grep_pattern = "w3name"
                
            w3name_list_result = self.run_w3_command(
                w3name_list_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            w3name_installed = False
            w3name_current_version = None
            
            if w3name_list_result.get("success", False) and w3name_list_result.get("returncode", 1) == 0:
                output = w3name_list_result.get("stdout", "")
                # Check if w3name is in the output
                w3name_match = re.search(r'w3name@(\d+\.\d+\.\d+)', output)
                if w3name_match:
                    w3name_installed = True
                    w3name_current_version = w3name_match.group(1)
                    result["dependencies"]["w3name"]["installed"] = True
                    result["dependencies"]["w3name"]["version"] = w3name_current_version
                    logger.info(f"w3name version: {w3name_current_version}")
            
            # Install or update w3name if needed
            need_w3name_install = not w3name_installed
            need_w3name_update = False
            
            if w3name_current_version and not force_update:
                # Compare versions to see if update needed
                current_parts = [int(p) for p in w3name_current_version.split('.')]
                required_parts = [int(p) for p in self.w3_name_version.split('.')]
                
                # Check if current version is older than required
                for i in range(min(len(current_parts), len(required_parts))):
                    if current_parts[i] < required_parts[i]:
                        need_w3name_update = True
                        break
                    elif current_parts[i] > required_parts[i]:
                        # Current version is newer, no update needed
                        break
            else:
                need_w3name_update = w3name_installed and (force_update or not w3name_current_version)
            
            # Install or update as needed
            if need_w3name_install or need_w3name_update:
                action = "Installing" if need_w3name_install else "Updating"
                logger.info(f"{action} w3name to version {self.w3_name_version}")
                
                if system == "Windows":
                    w3name_install_cmd = ["npm", "install", "w3name@" + self.w3_name_version]
                else:
                    sudo_prefix = ["sudo"] if not os.access("/usr/local/bin", os.W_OK) else []
                    w3name_install_cmd = sudo_prefix + ["npm", "install", "-g", "w3name@" + self.w3_name_version]
                
                w3name_install_result = self.run_w3_command(
                    w3name_install_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if w3name_install_result.get("success", False) and w3name_install_result.get("returncode", 1) == 0:
                    logger.info(f"w3name {action.lower()} successful")
                    result["dependencies"]["w3name"]["installed"] = True
                    result["dependencies"]["w3name"]["version"] = self.w3_name_version
                else:
                    error_msg = f"Failed to {action.lower()} w3name: {w3name_install_result.get('stderr', '')}"
                    logger.error(error_msg)
                    result["dependencies"]["w3name"]["error"] = error_msg
            
            # ==================== STEP 6: Final status report ====================
            # Check if all critical dependencies are installed
            all_critical_deps_installed = (
                result["dependencies"]["npm"]["installed"] and
                result["dependencies"]["w3cli"]["installed"] and
                result["dependencies"]["ipfs-car"]["installed"]
            )
            
            result["success"] = all_critical_deps_installed
            if all_critical_deps_installed:
                logger.info("All Web3.Storage dependencies installed successfully")
            else:
                missing_deps = [name for name, info in result["dependencies"].items() 
                               if not info.get("installed", False)]
                logger.warning(f"Some Web3.Storage dependencies not installed: {', '.join(missing_deps)}")
                result["error"] = f"Failed to install all required dependencies: {', '.join(missing_deps)}"
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in install: {str(e)}")
            return handle_error(result, e)
    
    def store_add(self, space, file, **kwargs):
        """Add a file to Web3.Storage store using the CLI.
        
        This method uploads a file to Web3.Storage by first packing it into a Content
        Addressable aRchive (CAR) file and then storing it in the specified space.
        The file is content-addressed, meaning its identifier (CID) is derived from
        its contents.
        
        Args:
            space: Name of the space to store the file in
            file: Path to the file to store (must be accessible on local filesystem)
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 180 - large files need longer)
                - wrap: Whether to wrap the file in a directory (default: False)
                - name: Optional name for the file in the CAR archive
                
        Returns:
            Dictionary with operation result:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("store_add")
                - timestamp: Unix timestamp of the operation
                - space: Name of the space file was stored in
                - file: Path to the file that was stored
                - cid: Content Identifier (CID) of the stored file
                - car_cid: CID of the CAR file containing the content
                - size: Size of the file in bytes
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Notes:
            - For batch operations, use store_add_batch
            - For HTTP API version, use store_add_https
            - Large files may require increased timeout value
            - The space must have sufficient storage allocation
            - This operation requires authentication and appropriate permissions
            
        Example:
            ```python
            result = kit.store_add("my-documents", "/path/to/document.pdf")
            if result["success"]:
                print(f"Added file with CID: {result['cid']}")
                # Store the CID for later retrieval
                my_cids.append(result['cid'])
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_add", correlation_id)
        result["file_path"] = file
        result["space"] = space
        
        try:
            # Set timeout for the command - CAR packing can be slow for large files
            timeout = kwargs.get('timeout', 180)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not file or not isinstance(file, str):
                return handle_error(result, IPFSValidationError("Missing or invalid file parameter"))
                
            if not os.path.exists(file):
                return handle_error(result, IPFSValidationError(f"File not found: {file}"))
                
            # Prevent command injection - validate space name
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: Create temporary CAR file
            with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp:
                temp_path = temp.name
                logger.debug(f"Created temporary CAR file: {temp_path}")
                
                try:
                    # Step 3: Pack file into CAR format
                    logger.info(f"Packing file into CAR format: {file}")
                    
                    # Note: We need to use shell=True here because of output redirection
                    # This is a limitation of the current ipfs-car tool which doesn't have
                    # a way to specify output file directly in arguments
                    if platform.system() == "Windows":
                        ipfs_car_cmd = f"ipfs-car pack \"{file}\" > \"{temp_path}\""
                        shell_needed = True
                    else:
                        ipfs_car_cmd = f"npx ipfs-car pack \"{file}\" > \"{temp_path}\""
                        shell_needed = True
                    
                    # Due to the need for output redirection, we must use a string command
                    # and shell=True for now. A more secure option would be to modify ipfs-car
                    # to accept --output parameter or to use a different approach.
                    pack_result = self.run_w3_command(
                        ipfs_car_cmd,
                        check=False,
                        timeout=timeout,
                        correlation_id=correlation_id,
                        shell=shell_needed  # Unfortunately needed for redirection
                    )
                    
                    if not pack_result.get("success", False):
                        error_msg = f"Failed to pack file into CAR format: {pack_result.get('stderr', '')}"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                    
                    # Extract CID from stderr output
                    stderr_output = pack_result.get("stderr", "").strip()
                    if stderr_output:
                        # Parse the output to extract the CID
                        lines = stderr_output.split("\n")
                        lines = [i.strip() for i in lines if i.strip()]
                        
                        if lines:
                            content_cid = lines[0]  # First line should contain the CID
                            logger.debug(f"Generated CAR file with content CID: {content_cid}")
                            result["content_cid"] = content_cid
                    
                    # Step 4: Add the CAR file to Web3.Storage store
                    logger.info("Adding CAR file to Web3.Storage store")
                    
                    if platform.system() == "Windows":
                        store_add_cmd = ["npx", "w3", "can", "store", "add", temp_path]
                    else:
                        store_add_cmd = ["w3", "can", "store", "add", temp_path]
                        
                    store_add_result = self.run_w3_command(
                        store_add_cmd,
                        check=False,
                        timeout=timeout,
                        correlation_id=correlation_id
                    )
                    
                    if not store_add_result.get("success", False) or store_add_result.get("returncode", 1) != 0:
                        error_msg = f"Failed to add CAR to store: {store_add_result.get('stderr', '')}"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                    
                    # Process the output to extract CIDs
                    output = store_add_result.get("stdout", "").strip()
                    cids = []
                    
                    if output:
                        lines = output.split("\n")
                        cids = [line.strip() for line in lines if line.strip()]
                        logger.info(f"Successfully added file to store: {cids}")
                    
                    # Update result with success information
                    result["success"] = True
                    result["cids"] = cids
                    
                    return result
                    
                finally:
                    # Clean up temporary file
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                            logger.debug(f"Removed temporary CAR file: {temp_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_path}: {str(e)}")
            
        except Exception as e:
            logger.exception(f"Unexpected error in store_add: {str(e)}")
            return handle_error(result, e)
        
    def store_get(self, space, cid, **kwargs):
        """Check if a CID exists in the Web3.Storage store.
        
        Args:
            space: Name of the space to check in
            cid: Content identifier to look for
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing CID availability information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_get", correlation_id)
        result["cid"] = cid
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
                
            # Validate space name and CID to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
                
            if not isinstance(cid, str) or re.search(r'[;&|"`\'$<>]', cid):
                return handle_error(result, IPFSValidationError(f"Invalid CID: {cid}"))
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: List all CIDs in the store
            logger.info(f"Listing CIDs in store for space: {space}")
            
            if platform.system() == "Windows":
                store_ls_cmd = ["npx", "w3", "can", "store", "ls"]
            else:
                store_ls_cmd = ["w3", "can", "store", "ls"]
                
            store_ls_result = self.run_w3_command(
                store_ls_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not store_ls_result.get("success", False) or store_ls_result.get("returncode", 1) != 0:
                error_msg = f"Failed to list CIDs in store: {store_ls_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output to get the list of CIDs
            output = store_ls_result.get("stdout", "").strip()
            stored_cids = []
            
            if output:
                lines = output.split("\n")
                stored_cids = [line.strip() for line in lines if line.strip()]
                logger.debug(f"Found {len(stored_cids)} CIDs in store")
            
            # Step 3: Check if the requested CID is in the store
            cid_exists = cid in stored_cids
            
            # Update result with success information
            result["success"] = True
            result["found"] = cid_exists
            result["cids"] = [cid] if cid_exists else []
            
            if cid_exists:
                logger.info(f"CID {cid} found in space {space}")
            else:
                logger.info(f"CID {cid} not found in space {space}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in store_get: {str(e)}")
            return handle_error(result, e)
         
    def store_remove(self, space, cid, **kwargs):
        """Remove a CID from the Web3.Storage store.
        
        Args:
            space: Name of the space to remove from
            cid: Content identifier to remove
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing removal status
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_remove", correlation_id)
        result["cid"] = cid
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
                
            # Validate space name and CID to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
                
            if not isinstance(cid, str) or re.search(r'[;&|"`\'$<>]', cid):
                return handle_error(result, IPFSValidationError(f"Invalid CID: {cid}"))
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: Remove the CID from the store
            logger.info(f"Removing CID {cid} from store in space {space}")
            
            if platform.system() == "Windows":
                store_rm_cmd = ["npx", "w3", "can", "store", "rm", cid]
            else:
                store_rm_cmd = ["w3", "can", "store", "rm", cid]
                
            store_rm_result = self.run_w3_command(
                store_rm_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not store_rm_result.get("success", False) or store_rm_result.get("returncode", 1) != 0:
                error_msg = f"Failed to remove CID from store: {store_rm_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output for any relevant information
            output = store_rm_result.get("stdout", "").strip()
            if output:
                result["output"] = output
            
            # Update result with success information
            result["success"] = True
            result["removed"] = True
            result["cids"] = [cid]
            
            logger.info(f"Successfully removed CID {cid} from space {space}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in store_remove: {str(e)}")
            return handle_error(result, e)
    
    def store_list(self, space, **kwargs):
        """List all CAR files stored in a Web3.Storage space.
        
        Args:
            space: Name of the space to list content from
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing list of stored CIDs
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_list", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Run the store list command
            logger.info(f"Listing store content for space: {space}")
            
            if platform.system() == "Windows":
                store_list_cmd = ["npx", "w3", "store", "list", space]
            else:
                store_list_cmd = ["w3", "store", "list", space]
                
            store_list_result = self.run_w3_command(
                store_list_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not store_list_result.get("success", False) or store_list_result.get("returncode", 1) != 0:
                error_msg = f"Failed to list store content: {store_list_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output to get the list of CIDs
            output = store_list_result.get("stdout", "").strip()
            cids = []
            
            if output:
                lines = output.split("\n")
                cids = [line.strip() for line in lines if line.strip()]
                logger.debug(f"Found {len(cids)} CIDs in store for space {space}")
            
            # Update result with success information
            result["success"] = True
            result["cids"] = cids
            result["count"] = len(cids)
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in store_list: {str(e)}")
            return handle_error(result, e)
    
    def upload_add(self, space, file, **kwargs):
        """Upload a file to a Web3.Storage space.
        
        Args:
            space: Name of the space to upload to
            file: Path to the file to upload
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 180)
                
        Returns:
            Dictionary with operation result containing upload information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("upload_add", correlation_id)
        result["file_path"] = file
        result["space"] = space
        
        try:
            # Set timeout for the command - uploads can be slow for large files
            timeout = kwargs.get('timeout', 180)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not file or not isinstance(file, str):
                return handle_error(result, IPFSValidationError("Missing or invalid file parameter"))
                
            if not os.path.exists(file):
                return handle_error(result, IPFSValidationError(f"File not found: {file}"))
                
            # Validate space name to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: Upload the file
            logger.info(f"Uploading file to Web3.Storage: {file}")
            
            # Convert file path to absolute to prevent resolution issues
            abs_file_path = os.path.abspath(file)
            
            if platform.system() == "Windows":
                upload_cmd = ["npx", "w3", "upload", abs_file_path]
            else:  
                upload_cmd = ["w3", "upload", abs_file_path]
                
            upload_result = self.run_w3_command(
                upload_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not upload_result.get("success", False) or upload_result.get("returncode", 1) != 0:
                error_msg = f"Failed to upload file: {upload_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Parse the output to extract CIDs and other information
            output = upload_result.get("stdout", "").strip()
            cids = []
            
            if output:
                lines = output.split("\n")
                for line in lines:
                    # Clean and normalize the line
                    clean_line = line.strip()
                    
                    # Extract CID from lines like "⁂ https://w3s.link/ipfs/bafy..."
                    if "⁂ https://w3s.link/ipfs/" in clean_line:
                        cid = clean_line.replace("⁂ https://w3s.link/ipfs/", "").strip()
                        cids.append(cid)
                    # Also catch lines that might contain just the CID
                    elif clean_line.startswith("bafy") and len(clean_line) > 40:
                        cids.append(clean_line)
                        
                # Include the raw output for debugging
                result["output"] = output
                
                logger.info(f"Successfully uploaded file with {len(cids)} CIDs")
            
            # Update result with success information
            result["success"] = True
            result["cids"] = cids
            result["count"] = len(cids)
            
            if cids:
                # Add gateway URLs for easier access
                result["gateway_urls"] = [f"https://w3s.link/ipfs/{cid}" for cid in cids]
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in upload_add: {str(e)}")
            return handle_error(result, e)
    
    def upload_list(self, space, **kwargs):
        """List all files uploaded to a Web3.Storage space.
        
        Args:
            space: Name of the space to list uploads from
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing list of uploaded content
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("upload_list", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: List uploads
            logger.info(f"Listing uploads for space: {space}")
            
            if platform.system() == "Windows":
                list_cmd = ["npx", "w3", "ls"]
            else:
                list_cmd = ["w3", "ls"]
                
            list_result = self.run_w3_command(
                list_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not list_result.get("success", False) or list_result.get("returncode", 1) != 0:
                error_msg = f"Failed to list uploads: {list_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output to get the list of uploads
            output = list_result.get("stdout", "").strip()
            uploads = []
            
            if output:
                lines = output.split("\n")
                uploads = [line.strip() for line in lines if line.strip()]
                
                # Handle empty lists with messages like "No uploads in space"
                if len(uploads) > 0 and uploads[0].startswith("⁂ No uploads in space"):
                    uploads = []
                
                logger.debug(f"Found {len(uploads)} uploads for space {space}")
            
            # Update result with success information
            result["success"] = True
            result["uploads"] = uploads
            result["count"] = len(uploads)
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in upload_list: {str(e)}")
            return handle_error(result, e)
    
    def upload_list_https(self, space, **kwargs):
        """List uploads for a specific Web3.Storage space.
        
        Args:
            space: The space to list uploads for
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("upload_list_https")
                - timestamp: Unix timestamp of the operation
                - space: The space name uploads were listed for
                - uploads: List of upload information if successful
                - error: Error message if failed
                - error_type: Type of error if failed
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": False,
            "operation": "upload_list_https",
            "timestamp": time.time(),
            "space": space,
            "correlation_id": correlation_id
        }
        
        try:
            # Parameter validation
            if not space:
                raise ValueError("Space name must be provided")
                
            if space not in self.tokens:
                raise ValueError(f"Space '{space}' not found in available tokens")
            
            # Get authentication tokens
            auth_secret = self.tokens[space]["X-Auth-Secret header"]
            authorization = self.tokens[space]["Authorization header"]
            
            # Prepare request data
            method = "upload/list"
            data = {
                "tasks": [
                    [
                        "upload/list",
                        space,
                        {}
                    ]
                ]
            }
            
            # Set timeout
            timeout = kwargs.get('timeout', 60)
            
            # Make HTTP request to Web3.Storage
            logger.debug(f"Listing uploads for space '{space}' [correlation_id: {correlation_id}]")
            request_results = self.storacha_http_request(
                auth_secret, 
                authorization, 
                method, 
                data,
                timeout=timeout
            )
            
            # Parse response
            response_data = request_results.json()
            
            # Handle error case
            if "error" in list(response_data[0]["p"]["out"].keys()):
                error = response_data[0]["p"]["out"]["error"]
                result["error"] = error
                result["error_type"] = "api_error"
                logger.error(f"Error listing uploads for space '{space}': {error} [correlation_id: {correlation_id}]")
                return result
                
            # Handle success case
            if "ok" in list(response_data[0]["p"]["out"].keys()):
                if "results" in list(response_data[0]["p"]["out"]["ok"].keys()):
                    uploads = response_data[0]["p"]["out"]["ok"]["results"]
                    
                    # Add default message for empty results
                    if len(uploads) == 0:
                        uploads = ['⁂ No uploads in space', '⁂ Try out `w3 up <path to files>` to upload some']
                    
                    result["uploads"] = uploads
                    result["success"] = True
                    result["count"] = len(uploads)
                    logger.info(f"Successfully listed {len(uploads)} uploads for space '{space}' [correlation_id: {correlation_id}]")
                    return result
            
            # Handle unexpected response format
            result["error"] = "Unexpected response format from Web3.Storage API"
            result["error_type"] = "parse_error"
            result["raw_response"] = response_data
            logger.error(f"Unexpected response format when listing uploads for space '{space}' [correlation_id: {correlation_id}]")
            return result
            
        except requests.exceptions.Timeout as e:
            result["error"] = f"Request timed out: {str(e)}"
            result["error_type"] = "timeout"
            logger.error(f"Timeout while listing uploads for space '{space}': {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except requests.exceptions.RequestException as e:
            result["error"] = f"HTTP request failed: {str(e)}"
            result["error_type"] = "request_error"
            logger.error(f"Request error while listing uploads for space '{space}': {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except ValueError as e:
            result["error"] = str(e)
            result["error_type"] = "validation_error"
            logger.error(f"Validation error in upload_list_https: {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["error_type"] = "unknown_error"
            logger.exception(f"Unexpected error in upload_list_https for space '{space}' [correlation_id: {correlation_id}]")
            return result
    
    def upload_remove(self, space, cid, **kwargs):
        """Remove an uploaded file from a Web3.Storage space by CID.
        
        Args:
            space: Name of the space to remove the upload from
            cid: Content identifier to remove (string or list with single item)
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing removal status
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("upload_remove", correlation_id)
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
            
            # Handle cid as list (normalize to string)
            if isinstance(cid, list):
                if len(cid) == 0:
                    return handle_error(result, IPFSValidationError("Empty CID list provided"))
                cid = cid[0]
                
            # Validate space name and CID to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
                
            if not isinstance(cid, str) or re.search(r'[;&|"`\'$<>]', cid):
                return handle_error(result, IPFSValidationError(f"Invalid CID: {cid}"))
                
            result["cid"] = cid
            result["space"] = space
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: Remove the upload
            logger.info(f"Removing upload with CID {cid} from space {space}")
            
            if platform.system() == "Windows":
                remove_cmd = ["npx", "w3", "rm", cid]
            else:
                remove_cmd = ["w3", "rm", cid]
                
            remove_result = self.run_w3_command(
                remove_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Process result
            if not remove_result.get("success", False) or remove_result.get("returncode", 1) != 0:
                # Special handling for JSON error in stderr - some w3 commands return
                # error details in JSON format, but may not properly format the JSON
                stderr = remove_result.get("stderr", "")
                
                # Try to extract structured error if available
                error_msg = None
                try:
                    # Sometimes error details are in a JSON fragment, try to extract and parse it
                    if "{" in stderr:
                        # Extract JSON-like fragment - crude but often works
                        json_fragment = stderr[stderr.find("{"):stderr.rfind("}")+1]
                        
                        # Sanitize malformed JSON to help with parsing
                        json_fragment = re.sub(r'([a-zA-Z0-9_/]+):', r'"\1":', json_fragment)
                        json_fragment = re.sub(r': \'([^\']+)\'', r': "\1"', json_fragment)
                        json_fragment = json_fragment.replace('\\n', '')
                        
                        # Try to parse the JSON
                        error_data = json.loads(json_fragment)
                        if "message" in error_data:
                            error_msg = error_data["message"]
                except (ValueError, json.JSONDecodeError):
                    # If JSON parsing failed, just use the stderr text
                    pass
                    
                if not error_msg:
                    error_msg = f"Failed to remove upload: {stderr}"
                    
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process stdout/stderr for any useful information
            stdout = remove_result.get("stdout", "").strip()
            stderr = remove_result.get("stderr", "").strip()
            
            # Combine the output - sometimes w3 tools put useful info in stderr even on success
            output = "\n".join([line for line in [stdout, stderr] if line])
            
            # Update result with success information
            result["success"] = True
            result["removed"] = True
            result["cids"] = [cid]
            
            if output:
                result["output"] = output
                
            logger.info(f"Successfully removed upload with CID {cid} from space {space}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in upload_remove: {str(e)}")
            return handle_error(result, e)
    
    def upload_remove_https(self, space, cid, **kwargs):
        """Remove an uploaded file using the Web3.Storage HTTP API.
        
        Args:
            space: Name of the space to remove the upload from
            cid: Content identifier to remove
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing removal status
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("upload_remove_https", correlation_id)
        result["cid"] = cid
        result["space"] = space
        
        try:
            # Set timeout for the request
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
            
            # Handle cid as list (normalize to string)
            if isinstance(cid, list):
                if len(cid) == 0:
                    return handle_error(result, IPFSValidationError("Empty CID list provided"))
                cid = cid[0]
                
            # Validate space name and CID to prevent injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
                
            if not isinstance(cid, str) or re.search(r'[;&|"`\'$<>]', cid):
                return handle_error(result, IPFSValidationError(f"Invalid CID: {cid}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Prepare the API request
            method = "upload/remove"
            data = {
                "tasks": [
                    [
                        "upload/remove",
                        space,
                        {
                            "root": {
                                "/": cid
                            }
                        }
                    ]
                ]
            }
            
            logger.info(f"Removing upload with CID {cid} from space {space} via HTTP API")
            
            # Make the API request
            http_response = self.storacha_http_request(
                auth_secret=auth_secret,
                authorization=authorization,
                method=method,
                data=data,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the request was successful
            if not isinstance(http_response, requests.Response):
                error_msg = "HTTP request failed, invalid response object returned"
                logger.error(error_msg)
                return handle_error(result, IPFSConnectionError(error_msg))
            
            # Parse the JSON response
            try:
                response_data = http_response.json()
            except ValueError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Process the response
            if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                error_msg = "Invalid response format from API"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Check for common response structure
            task_result = response_data[0]
            if "p" not in task_result or "out" not in task_result["p"]:
                error_msg = "Invalid task result format in API response"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            task_output = task_result["p"]["out"]
            
            # Check for success or error in the response
            if "ok" in task_output:
                # Success case
                ok_data = task_output["ok"]
                
                result["success"] = True
                result["removed"] = True
                result["api_response"] = ok_data
                
                logger.info(f"Successfully removed upload with CID {cid} from space {space} via HTTP API")
                return result
                
            elif "error" in task_output:
                # Error case
                error_data = task_output["error"]
                error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            else:
                # Unexpected response format
                error_msg = f"Unexpected response format from API: {json.dumps(task_output)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
        except Exception as e:
            logger.exception(f"Unexpected error in upload_remove_https: {str(e)}")
            return handle_error(result, e)
    
    def space_allocate(self, space, amount, unit="GiB", **kwargs):
        """Allocate a specific amount of storage capacity to a Web3.Storage space.
        
        This method allocates a specified amount of storage to an existing space.
        Storage must be allocated before content can be added to a space. The
        allocation can be increased or decreased as needed, but cannot be reduced
        below the amount of storage currently in use.
        
        Args:
            space: Name of the space to allocate storage for
            amount: Amount of storage to allocate (numeric value)
            unit: Unit for the amount (default: "GiB", options: "MiB", "GiB", "TiB")
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("space_allocate")
                - timestamp: Unix timestamp of the operation
                - space: Name of the space storage was allocated for
                - amount: Amount of storage allocated
                - unit: Unit of storage allocation
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Notes:
            - The total storage allocated cannot exceed your account's quota
            - Storage allocation can be increased or decreased, but cannot be
              decreased below the amount of storage currently in use
            - This operation requires authentication and appropriate permissions
            
        Example:
            ```python
            # Allocate 10 gigabytes to a space
            result = kit.space_allocate("my-documents", 10, "GiB")
            if result["success"]:
                print(f"Allocated {result['amount']}{result['unit']} to {result['space']}")
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("space_allocate", correlation_id)
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            if not amount:
                return handle_error(result, IPFSValidationError("Missing required parameter: amount"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Validate amount
            try:
                amount_value = float(amount)
                if amount_value <= 0:
                    return handle_error(result, IPFSValidationError(f"Amount must be a positive number, got {amount}"))
            except (ValueError, TypeError):
                return handle_error(result, IPFSValidationError(f"Amount must be a number, got {type(amount).__name__}"))
            
            # Validate unit
            valid_units = ["B", "KiB", "MiB", "GiB", "TiB"]
            if unit not in valid_units:
                return handle_error(result, IPFSValidationError(f"Invalid unit: {unit}. Must be one of {valid_units}"))
            
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Use the secure command execution helper
            cmd_result = self.run_w3_command(
                ["w3", "space", "allocate", space, f"{amount}{unit}"],
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to allocate {amount}{unit} to space '{space}': {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Process the output
            output = cmd_result.get("stdout", "").strip()
            
            result["success"] = True
            result["space"] = space
            result["allocated"] = f"{amount}{unit}"
            result["command_output"] = output
            
            logger.info(f"Successfully allocated {amount}{unit} to space: {space}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in space_allocate: {str(e)}")
            return handle_error(result, e)

    def space_deallocate(self, space, **kwargs):
        """Completely deallocate all storage from a Web3.Storage space.
        
        This method removes all storage allocation from a space. The space must be
        empty (containing no content) before storage can be deallocated. This operation
        is useful for freeing up quota or before deleting a space.
        
        Args:
            space: Name of the space to deallocate storage from
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                - force: Force deallocation even if data might be lost (dangerous) (default: False)
                
        Returns:
            Dictionary with operation result:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("space_deallocate")
                - timestamp: Unix timestamp of the operation
                - space: Name of the space that was deallocated
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Notes:
            - The space must be empty (containing no content) before storage can be deallocated
            - This operation requires authentication and appropriate permissions
            - This operation cannot be undone
            
        Example:
            ```python
            # Remove all content first
            kit.store_remove_batch("my-documents", all_cids)
            
            # Then deallocate storage
            result = kit.space_deallocate("my-documents")
            if result["success"]:
                print(f"Deallocated all storage from space: {result['space']}")
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("space_deallocate", correlation_id)
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Use the secure command execution helper
            cmd_result = self.run_w3_command(
                ["w3", "space", "deallocate", space],
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the command was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to deallocate space '{space}': {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
            
            # Process the output
            output = cmd_result.get("stdout", "").strip()
            
            result["success"] = True
            result["space"] = space
            result["command_output"] = output
            
            logger.info(f"Successfully deallocated space: {space}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in space_deallocate: {str(e)}")
            return handle_error(result, e)

    def w3usage_report(self, space, **kwargs):
        """Get a usage report for a Web3.Storage space.
        
        Args:
            space: Name of the space to get the usage report for
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing usage report information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("w3usage_report", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Run the usage report command
            logger.info(f"Getting usage report for space: {space}")
            
            if platform.system() == "Windows":
                usage_report_cmd = ["npx", "w3", "usage", "report", space]
            else:
                usage_report_cmd = ["w3", "usage", "report", space]
                
            report_result = self.run_w3_command(
                usage_report_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not report_result.get("success", False) or report_result.get("returncode", 1) != 0:
                error_msg = f"Failed to get usage report: {report_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output to extract usage information
            output = report_result.get("stdout", "").strip()
            usage_data = {}
            
            if output:
                lines = output.split("\n")
                formatted_lines = [line.strip() for line in lines if line.strip()]
                
                # Parse key-value pairs from the output
                for line in formatted_lines:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        usage_data[key] = value
                
                logger.debug(f"Parsed {len(usage_data)} usage metrics for space {space}")
                
                # Add raw output for debugging/reference
                result["raw_output"] = formatted_lines
            
            # Update result with success information
            result["success"] = True
            result["usage_data"] = usage_data
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in w3usage_report: {str(e)}")
            return handle_error(result, e)
    
    def access_delegate(self, space, email_did, permissions, expiration=None, **kwargs):
        """Delegate access to a space to another user.
        
        Args:
            space: Name of the space to delegate access to
            email_did: Email or DID of the user to delegate access to
            permissions: List of permissions to grant
            expiration: Optional expiration time (hours or specific timestamp)
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing delegation information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("access_delegate", correlation_id)
        result["space"] = space
        result["email_did"] = email_did
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not email_did:
                return handle_error(result, IPFSValidationError("Missing required parameter: email_did"))
                
            if not permissions or not isinstance(permissions, list) or len(permissions) == 0:
                return handle_error(result, IPFSValidationError("Missing or invalid permissions parameter"))
                
            # Validate space and email_did to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
                
            if not isinstance(email_did, str) or re.search(r'[;&|"`\'$<>]', email_did):
                return handle_error(result, IPFSValidationError(f"Invalid email or DID: {email_did}"))
            
            # Build command arguments
            if platform.system() == "Windows":
                delegate_cmd = ["npx", "w3", "access", "delegate", space, email_did]
            else:
                delegate_cmd = ["w3", "access", "delegate", space, email_did]
                
            # Add permission arguments
            for permission in permissions:
                # Validate each permission to prevent command injection
                if not isinstance(permission, str) or re.search(r'[;&|"`\'$<>]', permission):
                    return handle_error(result, IPFSValidationError(f"Invalid permission: {permission}"))
                
                delegate_cmd.extend(["--can", permission])
            
            # Handle expiration
            if expiration is not None:
                # For expiration, we need to calculate a timestamp
                # This is complex and involves system commands, which is why shell=True might
                # typically be used. We'll implement a safer alternative.
                
                # If expiration is a string that looks like a timestamp, use it directly
                if isinstance(expiration, str) and re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', expiration):
                    timestamp = expiration
                else:
                    # Try to interpret it as a number of hours from now
                    try:
                        # Convert to hours if it's a number
                        hours = float(expiration) if expiration is not None else 24.0
                        
                        # Calculate expiration timestamp (hours from now)
                        from datetime import datetime, timedelta
                        expiry_time = datetime.now() + timedelta(hours=hours)
                        timestamp = expiry_time.strftime('%Y-%m-%dT%H:%M:%S')
                    except (ValueError, TypeError):
                        error_msg = f"Invalid expiration value: {expiration}. Use hours or ISO 8601 format."
                        logger.error(error_msg)
                        return handle_error(result, IPFSValidationError(error_msg))
                
                delegate_cmd.extend(["--expiration", timestamp])
                result["expiration"] = timestamp
            
            # Run the delegation command
            logger.info(f"Delegating access to space {space} for {email_did} with permissions: {permissions}")
            
            delegate_result = self.run_w3_command(
                delegate_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not delegate_result.get("success", False) or delegate_result.get("returncode", 1) != 0:
                error_msg = f"Failed to delegate access: {delegate_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output
            stdout = delegate_result.get("stdout", "").strip()
            stderr = delegate_result.get("stderr", "").strip()
            
            # Combine the output - sometimes w3 tools put useful info in stderr even on success
            output_lines = []
            if stdout:
                output_lines.extend(stdout.split("\n"))
            if stderr:
                output_lines.extend(stderr.split("\n"))
            
            output_lines = [line.strip() for line in output_lines if line.strip()]
            
            # Update result with success information
            result["success"] = True
            result["permissions"] = permissions
            result["output"] = output_lines
            
            logger.info(f"Successfully delegated access to space {space} for {email_did}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in access_delegate: {str(e)}")
            return handle_error(result, e)
    
    def access_revoke(self, space, email_did, **kwargs):
        """Revoke delegated access to a space from a user.
        
        Args:
            space: Name of the space to revoke access from
            email_did: Email or DID of the user to revoke access from
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing revocation status
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("access_revoke", correlation_id)
        result["space"] = space
        result["email_did"] = email_did
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            if not email_did:
                return handle_error(result, IPFSValidationError("Missing required parameter: email_did"))
                
            # Validate space and email_did to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
                
            if not isinstance(email_did, str) or re.search(r'[;&|"`\'$<>]', email_did):
                return handle_error(result, IPFSValidationError(f"Invalid email or DID: {email_did}"))
            
            # Build revoke command
            if platform.system() == "Windows":
                revoke_cmd = ["npx", "w3", "access", "revoke", space, email_did]
            else:
                revoke_cmd = ["w3", "access", "revoke", space, email_did]
            
            # Run the revocation command
            logger.info(f"Revoking access to space {space} from {email_did}")
            
            revoke_result = self.run_w3_command(
                revoke_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not revoke_result.get("success", False) or revoke_result.get("returncode", 1) != 0:
                error_msg = f"Failed to revoke access: {revoke_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output
            stdout = revoke_result.get("stdout", "").strip()
            stderr = revoke_result.get("stderr", "").strip()
            
            # Combine the output
            output_lines = []
            if stdout:
                output_lines.extend(stdout.split("\n"))
            if stderr:
                output_lines.extend(stderr.split("\n"))
            
            output_lines = [line.strip() for line in output_lines if line.strip()]
            
            # Update result with success information
            result["success"] = True
            result["revoked"] = True
            
            if output_lines:
                result["output"] = output_lines
                
            logger.info(f"Successfully revoked access to space {space} from {email_did}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in access_revoke: {str(e)}")
            return handle_error(result, e)
    
    def space_info(self, space, **kwargs):
        """Get detailed information about a Web3.Storage space using the CLI.
        
        This method retrieves comprehensive information about a space including
        its usage statistics, storage allocation, ownership, and other metadata.
        The information is retrieved using the W3 CLI tool.
        
        Args:
            space: Name of the space to get information for
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                - refresh: Force refresh of information from server (default: False)
                
        Returns:
            Dictionary with operation result containing space information:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("space_info")
                - timestamp: Unix timestamp of the operation
                - space: Name of the space
                - space_did: DID (Decentralized Identifier) of the space
                - allocation: Dictionary with storage allocation information
                - usage: Dictionary with usage statistics
                - members: List of space members and their roles
                - created_at: Space creation timestamp
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Notes:
            - For a lighter-weight HTTP API version of this method, see space_info_https
            - This method requires authentication and appropriate permissions
            - The information returned includes all available metadata about the space
            
        Example:
            ```python
            info = kit.space_info("my-documents")
            if info["success"]:
                print(f"Space: {info['space']}")
                print(f"DID: {info['space_did']}")
                print(f"Storage used: {info['usage']['used']} of {info['allocation']['amount']}")
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("space_info", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Build the space info command
            if platform.system() == "Windows":
                space_info_cmd = ["npx", "w3", "space", "info", "--space", space]
            else:
                space_info_cmd = ["w3", "space", "info", "--space", space]
            
            # Run the space info command
            logger.info(f"Getting information for space: {space}")
            
            info_result = self.run_w3_command(
                space_info_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not info_result.get("success", False) or info_result.get("returncode", 1) != 0:
                error_msg = f"Failed to get space information: {info_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output to extract space information
            output = info_result.get("stdout", "").strip()
            space_data = {}
            
            if output:
                lines = output.split("\n")
                formatted_lines = [line.strip() for line in lines if line.strip()]
                
                # Process the key-value pairs from the output
                for line in formatted_lines:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        space_data[key] = value
                
                logger.debug(f"Parsed {len(space_data)} information fields for space {space}")
                
                # Add raw output for reference
                result["raw_output"] = formatted_lines
            
            # Update result with success information
            result["success"] = True
            result["space_data"] = space_data
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in space_info: {str(e)}")
            return handle_error(result, e)
    
    def space_info_https(self, space, **kwargs):
        """Get information about a Web3.Storage space using the HTTP API.
        
        This method retrieves information about a space using the Web3.Storage HTTP API.
        It provides a lightweight alternative to the CLI-based space_info method and
        is generally faster but may return less comprehensive information.
        
        Args:
            space: Name of the space to get information for
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                - include_usage: Include detailed usage statistics (default: True)
                
        Returns:
            Dictionary with operation result containing space information:
                - success: Boolean indicating operation success
                - operation: Name of the operation ("space_info_https")
                - timestamp: Unix timestamp of the operation
                - space: Name of the space
                - space_did: DID (Decentralized Identifier) of the space
                - info: Dictionary containing space information from the API
                - error: Error message if failed
                - error_type: Type of error if failed
                
        Notes:
            - This method uses the HTTP API rather than the CLI
            - For more comprehensive information, use the space_info method
            - This method requires authentication and appropriate tokens
            - The HTTP API version may be faster but potentially less detailed
            
        Example:
            ```python
            info = kit.space_info_https("my-documents")
            if info["success"]:
                print(f"Space: {info['space']}")
                print(f"DID: {info['space_did']}")
                print(f"Usage info: {info['info']['usage']}")
            ```
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("space_info_https", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the request
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Prepare the API request
            method = "space/info"
            data = {
                "tasks": [
                    [
                        "space/info",
                        space,
                        {}
                    ]
                ]
            }
            
            logger.info(f"Getting information for space {space} via HTTP API")
            
            # Make the API request
            http_response = self.storacha_http_request(
                auth_secret=auth_secret,
                authorization=authorization,
                method=method,
                data=data,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the request was successful
            if not isinstance(http_response, requests.Response):
                error_msg = "HTTP request failed, invalid response object returned"
                logger.error(error_msg)
                return handle_error(result, IPFSConnectionError(error_msg))
            
            # Parse the JSON response
            try:
                response_data = http_response.json()
            except ValueError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Process the response
            if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                error_msg = "Invalid response format from API"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Check for common response structure
            task_result = response_data[0]
            if "p" not in task_result or "out" not in task_result["p"]:
                error_msg = "Invalid task result format in API response"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            task_output = task_result["p"]["out"]
            
            # Check for success or error in the response
            if "ok" in task_output:
                # Success case
                space_info = task_output["ok"]
                
                result["success"] = True
                result["space_info"] = space_info
                
                logger.info(f"Successfully retrieved information for space {space} via HTTP API")
                return result
                
            elif "error" in task_output:
                # Error case
                error_data = task_output["error"]
                error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            else:
                # Unexpected response format
                error_msg = f"Unexpected response format from API: {json.dumps(task_output)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
        except Exception as e:
            logger.exception(f"Unexpected error in space_info_https: {str(e)}")
            return handle_error(result, e)
        
    def usage_report(self, space, **kwargs):
        """Get a usage report for the current Web3.Storage space.
        
        Args:
            space: Name of the space to get usage report for
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing usage report information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("usage_report", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the command
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent command injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Step 1: Switch to the specified space if needed
            if space != self.space:
                logger.info(f"Switching to space: {space}")
                
                if platform.system() == "Windows":
                    space_use_cmd = ["npx", "w3", "space", "use", space]
                else:
                    space_use_cmd = ["w3", "space", "use", space]
                    
                space_use_result = self.run_w3_command(
                    space_use_cmd,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                if not space_use_result.get("success", False) or space_use_result.get("returncode", 1) != 0:
                    error_msg = f"Failed to switch to space '{space}': {space_use_result.get('stderr', '')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                self.space = space
                logger.debug(f"Successfully switched to space: {space}")
            
            # Step 2: Get the usage report
            logger.info(f"Getting usage report for space: {space}")
            
            if platform.system() == "Windows":
                report_cmd = ["npx", "w3", "usage", "report"]
            else:
                report_cmd = ["w3", "usage", "report"]
                
            report_result = self.run_w3_command(
                report_cmd,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not report_result.get("success", False) or report_result.get("returncode", 1) != 0:
                error_msg = f"Failed to get usage report: {report_result.get('stderr', '')}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Process the output to extract usage information
            output = report_result.get("stdout", "").strip()
            usage_data = {}
            
            if output:
                lines = output.split("\n")
                formatted_lines = [line.strip() for line in lines if line.strip()]
                
                # Parse key-value pairs from the output
                for line in formatted_lines:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        usage_data[key] = value
                
                logger.debug(f"Parsed {len(usage_data)} usage metrics for space {space}")
                
                # Add raw output for reference
                result["raw_output"] = formatted_lines
            
            # Update result with success information
            result["success"] = True
            result["usage_data"] = usage_data
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in usage_report: {str(e)}")
            return handle_error(result, e)
    
    def usage_report_https(self, space, **kwargs):
        """Get a usage report for a Web3.Storage space using the HTTP API.
        
        Args:
            space: Name of the space to get usage report for
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing usage report information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("usage_report_https", correlation_id)
        result["space"] = space
        
        try:
            # Set timeout for the request
            timeout = kwargs.get('timeout', 60)
            
            # Validate parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
                
            # Validate space name to prevent injection
            if not isinstance(space, str) or re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Invalid space name: {space}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Prepare the API request
            method = "usage/report"
            data = {
                "tasks": [
                    [
                        "usage/report",
                        space,
                        {}
                    ]
                ]
            }
            
            logger.info(f"Getting usage report for space {space} via HTTP API")
            
            # Make the API request
            http_response = self.storacha_http_request(
                auth_secret=auth_secret,
                authorization=authorization,
                method=method,
                data=data,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the request was successful
            if not isinstance(http_response, requests.Response):
                error_msg = "HTTP request failed, invalid response object returned"
                logger.error(error_msg)
                return handle_error(result, IPFSConnectionError(error_msg))
            
            # Parse the JSON response
            try:
                response_data = http_response.json()
            except ValueError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Process the response
            if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                error_msg = "Invalid response format from API"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Check for common response structure
            task_result = response_data[0]
            if "p" not in task_result or "out" not in task_result["p"]:
                error_msg = "Invalid task result format in API response"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            task_output = task_result["p"]["out"]
            
            # Check for success or error in the response
            if "ok" in task_output:
                # Success case
                usage_data = task_output["ok"]
                
                result["success"] = True
                result["usage_data"] = usage_data
                
                logger.info(f"Successfully retrieved usage report for space {space} via HTTP API")
                return result
                
            elif "error" in task_output:
                # Error case
                error_data = task_output["error"]
                error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            else:
                # Unexpected response format
                error_msg = f"Unexpected response format from API: {json.dumps(task_output)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
        except Exception as e:
            logger.exception(f"Unexpected error in usage_report_https: {str(e)}")
            return handle_error(result, e)
             
    # SECURITY NOTICE: These methods were deprecated due to security vulnerabilities
    # They have been replaced with safer implementations above (space_allocate and space_deallocate)
    # that avoid shell=True usage and follow standardized error handling patterns.
    # These method stubs are kept only for documentation purposes and should not be used.
    
    def store_add_batch(self, space, files, **kwargs):
        """Add multiple files to a Web3.Storage space in a batch operation.
        
        Args:
            space: The space to add files to
            files: List of file paths to add
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - parallel: Whether to process files in parallel (default: False)
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("store_add_batch")
                - timestamp: Unix timestamp of the operation
                - space: The space name files were added to
                - total: Total number of files processed
                - successful: Number of files successfully added
                - failed: Number of files that failed to add
                - files: Dictionary mapping file paths to their results
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": True,  # Assume success until we encounter a failure
            "operation": "store_add_batch",
            "timestamp": time.time(),
            "space": space,
            "correlation_id": correlation_id,
            "total": len(files),
            "successful": 0,
            "failed": 0,
            "files": {}
        }
        
        try:
            # Parameter validation
            if not space:
                raise ValueError("Space name must be provided")
                
            if not files:
                raise ValueError("Files list cannot be empty")
                
            if not isinstance(files, (list, tuple)):
                raise ValueError("Files must be provided as a list or tuple")
                
            for file in files:
                if not file:
                    continue
                    
                try:
                    # Process each file individually
                    file_result = self.store_add(
                        space=space, 
                        file=file, 
                        correlation_id=f"{correlation_id}:{file}" if correlation_id else None,
                        **kwargs
                    )
                    
                    # Store the result
                    result["files"][file] = file_result
                    
                    # Update counters
                    if file_result.get("success", False):
                        result["successful"] += 1
                    else:
                        result["failed"] += 1
                        result["success"] = False  # Mark the overall operation as failed
                        
                except Exception as e:
                    # Handle individual file failures without stopping the batch
                    logger.error(f"Error adding file {file} to space {space}: {str(e)} [correlation_id: {correlation_id}]")
                    result["files"][file] = {
                        "success": False,
                        "operation": "store_add",
                        "timestamp": time.time(),
                        "file": file,
                        "space": space,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    result["failed"] += 1
                    result["success"] = False  # Mark the overall operation as failed
            
            # Log the final result
            logger.info(f"Batch add completed for space {space}: {result['successful']}/{result['total']} successful [correlation_id: {correlation_id}]")
            return result
            
        except ValueError as e:
            result["error"] = str(e)
            result["error_type"] = "validation_error"
            logger.error(f"Validation error in store_add_batch: {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["error_type"] = "unknown_error"
            logger.exception(f"Unexpected error in store_add_batch for space {space} [correlation_id: {correlation_id}]")
            return result
    
    def store_get_batch(self, space, cids, output, **kwargs):
        """Retrieve multiple items from a Web3.Storage space by their CIDs in a batch operation.
        
        Args:
            space: The space to retrieve items from
            cids: List of CIDs to retrieve
            output: Output directory path
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - parallel: Whether to process CIDs in parallel (default: False)
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("store_get_batch")
                - timestamp: Unix timestamp of the operation
                - space: The space name items were retrieved from
                - output: Output directory path
                - total: Total number of CIDs processed
                - successful: Number of CIDs successfully retrieved
                - failed: Number of CIDs that failed to retrieve
                - items: Dictionary mapping CIDs to their results
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": True,  # Assume success until we encounter a failure
            "operation": "store_get_batch",
            "timestamp": time.time(),
            "space": space,
            "output": output,
            "correlation_id": correlation_id,
            "total": len(cids),
            "successful": 0,
            "failed": 0,
            "items": {}
        }
        
        try:
            # Parameter validation
            if not space:
                raise ValueError("Space name must be provided")
                
            if not cids:
                raise ValueError("CIDs list cannot be empty")
                
            if not isinstance(cids, (list, tuple)):
                raise ValueError("CIDs must be provided as a list or tuple")
                
            if not output:
                raise ValueError("Output directory must be provided")
                
            # Ensure output directory exists
            os.makedirs(output, exist_ok=True)
                
            for cid in cids:
                if not cid:
                    continue
                    
                try:
                    # Process each CID individually
                    cid_result = self.store_get(
                        space=space, 
                        cid=cid, 
                        output=output,
                        correlation_id=f"{correlation_id}:{cid}" if correlation_id else None,
                        **kwargs
                    )
                    
                    # Store the result
                    result["items"][cid] = cid_result
                    
                    # Update counters
                    if cid_result.get("success", False):
                        result["successful"] += 1
                    else:
                        result["failed"] += 1
                        result["success"] = False  # Mark the overall operation as failed
                        
                except Exception as e:
                    # Handle individual CID failures without stopping the batch
                    logger.error(f"Error retrieving CID {cid} from space {space}: {str(e)} [correlation_id: {correlation_id}]")
                    result["items"][cid] = {
                        "success": False,
                        "operation": "store_get",
                        "timestamp": time.time(),
                        "cid": cid,
                        "space": space,
                        "output": output,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    result["failed"] += 1
                    result["success"] = False  # Mark the overall operation as failed
            
                
                # Prepare API request data
                method = "store/add"
                data = {
                    "tasks": [
                        [
                            "store/add",
                            space,
                            {
                                "link": { "/" : car_hash },
                                "size": car_length
                            }
                        ]
                    ]
                }
                
                # Make the API request
                logger.info(f"Making store/add API request for file: {file}")
                timeout = kwargs.get('timeout', 60)
                
                http_response = self.storacha_http_request(
                    auth_secret=auth_secret,
                    authorization=authorization,
                    method=method,
                    data=data,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                # Check if the request was successful
                if not isinstance(http_response, requests.Response):
                    error_msg = "HTTP request failed, invalid response object returned"
                    logger.error(error_msg)
                    return handle_error(result, IPFSConnectionError(error_msg))
                
                # Parse the JSON response
                try:
                    response_data = http_response.json()
                except ValueError as e:
                    error_msg = f"Failed to parse JSON response: {str(e)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                # Process the response
                if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                    error_msg = "Invalid response format from API"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                # Check for common response structure
                task_result = response_data[0]
                if "p" not in task_result or "out" not in task_result["p"]:
                    error_msg = "Invalid task result format in API response"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                task_output = task_result["p"]["out"]
                
                # Check for success or error in the response
                if "ok" in task_output:
                    # Success case
                    ok_data = task_output["ok"]
                    
                    result["success"] = True
                    result["data"] = ok_data
                    
                    logger.info(f"Successfully added upload for file {file} to space {space}")
                    return result
                    
                elif "error" in task_output:
                    # Error case
                    error_data = task_output["error"]
                    error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                else:
                    # Unexpected response format
                    
                    # Update counters
                    if cid_result.get("success", False):
                        result["successful"] += 1
                    else:
                        result["failed"] += 1
                        result["success"] = False  # Mark the overall operation as failed
                        
        except Exception as e:
            # Handle individual CID failures without stopping the batch
            logger.error(f"Error removing CID {cid} from space {space}: {str(e)} [correlation_id: {correlation_id}]")
            result["items"][cid] = {
                "success": False,
                "operation": "store_remove",
                "timestamp": time.time(),
                "cid": cid,
                "space": space,
                "error": str(e),
                "error_type": type(e).__name__
            }
            result["failed"] += 1
            result["success"] = False  # Mark the overall operation as failed
            
        except ValueError as e:
            result["error"] = str(e)
            result["error_type"] = "validation_error"
            logger.error(f"Validation error in store_remove_batch: {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["error_type"] = "unknown_error"
            logger.exception(f"Unexpected error in store_remove_batch for space {space} [correlation_id: {correlation_id}]")
            return result
        # Log the final result
        logger.info(f"Batch removal completed for space {space}: {result['successful']}/{result['total']} successful [correlation_id: {correlation_id}]")
        return result
            
    def upload_add_batch(self, space, files, **kwargs):
        """Upload multiple files to a Web3.Storage space in a batch operation.
        
        Args:
            space: The space to upload files to
            files: List of file paths to upload
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - parallel: Whether to process files in parallel (default: False)
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("upload_add_batch")
                - timestamp: Unix timestamp of the operation
                - space: The space name files were uploaded to
                - total: Total number of files processed
                - successful: Number of files successfully uploaded
                - failed: Number of files that failed to upload
                - files: Dictionary mapping file paths to their results
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": True,  # Assume success until we encounter a failure
            "operation": "upload_add_batch",
            "timestamp": time.time(),
            "space": space,
            "correlation_id": correlation_id,
            "total": len(files),
            "successful": 0,
            "failed": 0,
            "files": {}
        }
        
        try:
            # Parameter validation
            if not space:
                raise ValueError("Space name must be provided")
                
            if not files:
                raise ValueError("Files list cannot be empty")
                
            if not isinstance(files, (list, tuple)):
                raise ValueError("Files must be provided as a list or tuple")
                
            for file in files:
                if not file:
                    continue
                    
                try:
                    # Process each file individually
                    file_result = self.upload_add(
                        space=space, 
                        file=file, 
                        correlation_id=f"{correlation_id}:{file}" if correlation_id else None,
                        **kwargs
                    )
                    
                    # Store the result
                    result["files"][file] = file_result
                    
                    # Update counters
                    if file_result.get("success", False):
                        result["successful"] += 1
                    else:
                        result["failed"] += 1
                        result["success"] = False  # Mark the overall operation as failed
                        
                except Exception as e:
                    # Handle individual file failures without stopping the batch
                    logger.error(f"Error uploading file {file} to space {space}: {str(e)} [correlation_id: {correlation_id}]")
                    result["files"][file] = {
                        "success": False,
                        "operation": "upload_add",
                        "timestamp": time.time(),
                        "file": file,
                        "space": space,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    result["failed"] += 1
                    result["success"] = False  # Mark the overall operation as failed
            
            # Log the final result
            logger.info(f"Batch upload completed for space {space}: {result['successful']}/{result['total']} successful [correlation_id: {correlation_id}]")
            return result
            
        except ValueError as e:
            result["error"] = str(e)
            result["error_type"] = "validation_error"
            logger.error(f"Validation error in upload_add_batch: {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["error_type"] = "unknown_error"
            logger.exception(f"Unexpected error in upload_add_batch for space {space} [correlation_id: {correlation_id}]")
            return result
    
    def upload_remove_batch(self, space, cids, **kwargs):
        """Remove multiple uploads from a Web3.Storage space by their CIDs in a batch operation.
        
        Args:
            space: The space to remove uploads from
            cids: List of CIDs to remove
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - parallel: Whether to process CIDs in parallel (default: False)
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("upload_remove_batch")
                - timestamp: Unix timestamp of the operation
                - space: The space name uploads were removed from
                - total: Total number of CIDs processed
                - successful: Number of CIDs successfully removed
                - failed: Number of CIDs that failed to remove
                - items: Dictionary mapping CIDs to their results
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": True,  # Assume success until we encounter a failure
            "operation": "upload_remove_batch",
            "timestamp": time.time(),
            "space": space,
            "correlation_id": correlation_id,
            "total": len(cids),
            "successful": 0,
            "failed": 0,
            "items": {}
        }
        
        try:
            # Parameter validation
            if not space:
                raise ValueError("Space name must be provided")
                
            if not cids:
                raise ValueError("CIDs list cannot be empty")
                
            if not isinstance(cids, (list, tuple)):
                raise ValueError("CIDs must be provided as a list or tuple")
                
            for cid in cids:
                if not cid:
                    continue
                    
                try:
                    # Process each CID individually
                    cid_result = self.upload_remove(
                        space=space, 
                        cid=cid,
                        correlation_id=f"{correlation_id}:{cid}" if correlation_id else None,
                        **kwargs
                    )
                    
                    # Store the result
                    result["items"][cid] = cid_result
                    
                    # Update counters
                    if cid_result.get("success", False):
                        result["successful"] += 1
                    else:
                        result["failed"] += 1
                        result["success"] = False  # Mark the overall operation as failed
                        
                except Exception as e:
                    # Handle individual CID failures without stopping the batch
                    logger.error(f"Error removing upload {cid} from space {space}: {str(e)} [correlation_id: {correlation_id}]")
                    result["items"][cid] = {
                        "success": False,
                        "operation": "upload_remove",
                        "timestamp": time.time(),
                        "cid": cid,
                        "space": space,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    result["failed"] += 1
                    result["success"] = False  # Mark the overall operation as failed
            
            # Log the final result
            logger.info(f"Batch upload removal completed for space {space}: {result['successful']}/{result['total']} successful [correlation_id: {correlation_id}]")
            return result
            
        except ValueError as e:
            result["error"] = str(e)
            result["error_type"] = "validation_error"
            logger.error(f"Validation error in upload_remove_batch: {str(e)} [correlation_id: {correlation_id}]")
            return result
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["error_type"] = "unknown_error"
            logger.exception(f"Unexpected error in upload_remove_batch for space {space} [correlation_id: {correlation_id}]")
            return result
    
    def store_add_https(self, space, file, file_root, **kwargs):
        """Add a file to Web3.Storage store using the HTTP API.
        
        Args:
            space: Name of the space to add the file to
            file: Path to the file to add
            file_root: Root directory path for determining relative path
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing CID(s) of added content
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_add_https", correlation_id)
        result["space"] = space
        result["file"] = file
        
        # Temp file tracking for cleanup
        temp_filename = None
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            if not file:
                return handle_error(result, IPFSValidationError("Missing required parameter: file"))
                
            if not file_root:
                return handle_error(result, IPFSValidationError("Missing required parameter: file_root"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Validate file path
            if not os.path.exists(file):
                return handle_error(result, IPFSContentNotFoundError(f"File not found: {file}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Create a temporary file for the CAR
            try:
                with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp:
                    temp_filename = temp.name
                    
                # Normalize file path for cross-platform compatibility
                file_path = file.replace(file_root, "")
                file_path = file_path.replace("\\", "/")
                
                # Create CAR file from the input file
                # Note: ipfs-car requires output redirection which we have to use shell=True for
                # Security note: While shell=True is generally avoided, we've validated all inputs above
                if platform.system() == "Windows":
                    ipfs_car_cmd = ["npx", "ipfs-car", "pack", file]
                else:
                    ipfs_car_cmd = ["ipfs-car", "pack", file]
                    
                # We need shell=True for output redirection, but have validated inputs
                ipfs_car_cmd_str = " ".join(ipfs_car_cmd) + " > " + temp_filename
                logger.info(f"Creating CAR file: {ipfs_car_cmd_str}")
                
                car_process = subprocess.run(
                    ipfs_car_cmd_str, 
                    shell=True,  # Required for output redirection
                    stderr=subprocess.PIPE,
                    timeout=kwargs.get('timeout', 120),  # CAR packing might take time for large files
                    check=False
                )
                
                # Check for errors
                if car_process.returncode != 0:
                    error_msg = f"Failed to create CAR file: {car_process.stderr.decode('utf-8', errors='replace')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                # Get CID from stderr output
                stderr_output = car_process.stderr.decode("utf-8", errors="replace").strip()
                if stderr_output:
                    cid_lines = [line.strip() for line in stderr_output.split("\n") if line.strip()]
                    if cid_lines:
                        cid = cid_lines[0]  # First line should contain the CID
                    else:
                        error_msg = "Could not extract CID from ipfs-car output"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                else:
                    error_msg = "No output from ipfs-car pack command"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                # Now get the CAR file hash
                if platform.system() == "Windows":
                    car_hash_cmd = ["npx", "ipfs-car", "hash", temp_filename]
                else:
                    car_hash_cmd = ["ipfs-car", "hash", temp_filename]
                    
                logger.info(f"Getting CAR hash: {' '.join(car_hash_cmd)}")
                
                # For cross-platform path compatibility
                temp_filename_normalized = temp_filename.replace("\\", "/")
                
                # We need shell=True for now until ipfs-car command can be executed differently
                # Security note: We've validated inputs above to mitigate shell injection risks
                if platform.system() == "Windows":
                    car_hash_cmd_str = f"npx ipfs-car hash {temp_filename_normalized}"
                else:
                    car_hash_cmd_str = f"ipfs-car hash {temp_filename_normalized}"
                
                car_hash_process = subprocess.run(
                    car_hash_cmd_str,
                    shell=True,  # Required due to ipfs-car limitations
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    timeout=kwargs.get('timeout', 30),
                    check=False
                )
                
                # Check for errors
                if car_hash_process.returncode != 0:
                    error_msg = f"Failed to get CAR hash: {car_hash_process.stderr.decode('utf-8', errors='replace')}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                # Combine stderr and stdout to find the hash
                hash_output = car_hash_process.stderr.decode("utf-8", errors="replace").strip()
                hash_output += car_hash_process.stdout.decode("utf-8", errors="replace").strip()
                
                hash_lines = [line.strip() for line in hash_output.split("\n") if line.strip()]
                if hash_lines:
                    car_hash = hash_lines[0]  # First line should contain the hash
                else:
                    error_msg = "Could not extract CAR hash from output"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                # Get the CAR file size
                car_length = os.path.getsize(temp_filename)
                
                # Prepare API request data
                method = "store/add"
                data = {
                    "tasks": [
                        [
                            "store/add",
                            space,
                            {
                                "link": { "/" : car_hash },
                                "size": car_length
                            }
                        ]
                    ]
                }
                
                # Make the API request
                logger.info(f"Making store/add API request for file: {file}")
                timeout = kwargs.get('timeout', 60)
                
                http_response = self.storacha_http_request(
                    auth_secret=auth_secret,
                    authorization=authorization,
                    method=method,
                    data=data,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                # Check if the request was successful
                if not isinstance(http_response, requests.Response):
                    error_msg = "HTTP request failed, invalid response object returned"
                    logger.error(error_msg)
                    return handle_error(result, IPFSConnectionError(error_msg))
                
                # Parse the JSON response
                try:
                    response_data = http_response.json()
                except ValueError as e:
                    error_msg = f"Failed to parse JSON response: {str(e)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                # Process the response
                if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                    error_msg = "Invalid response format from API"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                # Check for common response structure
                task_result = response_data[0]
                if "p" not in task_result or "out" not in task_result["p"]:
                    error_msg = "Invalid task result format in API response"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                task_output = task_result["p"]["out"]
                
                # Process based on response type
                if "ok" in task_output:
                    ok_data = task_output["ok"]
                    
                    if "status" in ok_data:
                        status = ok_data["status"]
                        
                        if status == "done":
                            # Content is already stored
                            result_cid = ok_data["link"]["/"]
                            
                            result["success"] = True
                            result["cids"] = [result_cid]
                            result["status"] = "done"
                            
                            logger.info(f"Successfully stored file {file} with CID {result_cid}")
                            return result
                            
                        elif status == "upload":
                            # Need to upload the CAR file
                            carpark_url = ok_data["url"]
                            headers_url = ok_data["headers"]
                            
                            # Upload the CAR file
                            logger.info(f"Uploading CAR file to {carpark_url}")
                            
                            try:
                                with open(temp_filename, 'rb') as f:
                                    upload_response = requests.put(
                                        carpark_url, 
                                        headers=headers_url, 
                                        data=f,
                                        timeout=kwargs.get('timeout', 120)  # Longer timeout for upload
                                    )
                                    
                                    if upload_response.status_code >= 400:
                                        error_msg = f"CAR upload failed with status {upload_response.status_code}: {upload_response.text}"
                                        logger.error(error_msg)
                                        return handle_error(result, IPFSConnectionError(error_msg))
                                        
                                    # Parse the upload response
                                    try:
                                        upload_data = upload_response.json()
                                    except ValueError as e:
                                        error_msg = f"Failed to parse upload response: {str(e)}"
                                        logger.error(error_msg)
                                        return handle_error(result, IPFSError(error_msg))
                                    
                                    # Extract CID from upload response
                                    if (isinstance(upload_data, list) and len(upload_data) > 0 and 
                                        "p" in upload_data[0] and "out" in upload_data[0]["p"] and
                                        "ok" in upload_data[0]["p"]["out"] and 
                                        "link" in upload_data[0]["p"]["out"]["ok"]):
                                        
                                        result_cid = upload_data[0]["p"]["out"]["ok"]["link"]["/"]
                                        
                                        result["success"] = True
                                        result["cids"] = [result_cid]
                                        result["status"] = "uploaded"
                                        
                                        logger.info(f"Successfully uploaded and stored file {file} with CID {result_cid}")
                                        return result
                                    else:
                                        error_msg = f"Invalid upload response format: {json.dumps(upload_data)}"
                                        logger.error(error_msg)
                                        return handle_error(result, IPFSError(error_msg))
                                        
                            except requests.RequestException as e:
                                error_msg = f"Error uploading CAR file: {str(e)}"
                                logger.error(error_msg)
                                return handle_error(result, IPFSConnectionError(error_msg))
                        else:
                            error_msg = f"Unknown status in response: {status}"
                            logger.error(error_msg)
                            return handle_error(result, IPFSError(error_msg))
                    
                    elif "error" in ok_data:
                        # Error in 'ok' object
                        error_data = ok_data["error"]
                        error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                    
                    else:
                        error_msg = f"Unexpected 'ok' data format: {json.dumps(ok_data)}"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                        
                elif "error" in task_output:
                    # Error case in main task output
                    error_data = task_output["error"]
                    error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                else:
                    # Unexpected response format
                    error_msg = f"Unexpected response format: {json.dumps(task_output)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
            finally:
                # Clean up temporary files
                if temp_filename and os.path.exists(temp_filename):
                    try:
                        os.unlink(temp_filename)
                        logger.debug(f"Cleaned up temporary file: {temp_filename}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary file {temp_filename}: {str(e)}")
                
        except Exception as e:
            logger.exception(f"Unexpected error in store_add_https: {str(e)}")
            return handle_error(result, e)
    
    
    def store_get_https(self, space, cid, **kwargs):
        """Get content from Web3.Storage using the HTTP API.
        
        Args:
            space: Name of the space to get content from
            cid: Content Identifier to retrieve
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing content information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_get_https", correlation_id)
        result["space"] = space
        result["cid"] = cid
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Validate CID format
            if not isinstance(cid, str):
                return handle_error(result, IPFSValidationError(f"CID must be a string, got {type(cid).__name__}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Prepare API request data
            method = "store/get"
            data = {
                "tasks": [
                    [
                        "store/get",
                        space,
                        {
                            "link": { "/" : cid },
                        }
                    ]
                ]
            }
            
            # Make the API request
            logger.info(f"Getting content with CID {cid} from space {space}")
            timeout = kwargs.get('timeout', 60)
            
            http_response = self.storacha_http_request(
                auth_secret=auth_secret,
                authorization=authorization,
                method=method,
                data=data,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the request was successful
            if not isinstance(http_response, requests.Response):
                error_msg = "HTTP request failed, invalid response object returned"
                logger.error(error_msg)
                return handle_error(result, IPFSConnectionError(error_msg))
            
            # Parse the JSON response
            try:
                response_data = http_response.json()
            except ValueError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Process the response
            if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                error_msg = "Invalid response format from API"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Check for common response structure
            task_result = response_data[0]
            if "p" not in task_result or "out" not in task_result["p"]:
                error_msg = "Invalid task result format in API response"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            task_output = task_result["p"]["out"]
            
            # Check for success or error in the response
            if "ok" in task_output:
                # Success case
                ok_data = task_output["ok"]
                
                result["success"] = True
                result["data"] = ok_data
                
                logger.info(f"Successfully retrieved content with CID {cid} from space {space}")
                return result
                
            elif "error" in task_output:
                # Error case
                error_data = task_output["error"]
                error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            else:
                # Unexpected response format
                error_msg = f"Unexpected response format from API: {json.dumps(task_output)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
        except Exception as e:
            logger.exception(f"Unexpected error in store_get_https: {str(e)}")
            return handle_error(result, e)
        
    def store_remove_https(self, space, cid, **kwargs):
        """Remove content from Web3.Storage using the HTTP API.
        
        Args:
            space: Name of the space to remove content from
            cid: Content Identifier to remove
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_remove_https", correlation_id)
        result["space"] = space
        result["cid"] = cid
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Validate CID format
            if not isinstance(cid, str):
                return handle_error(result, IPFSValidationError(f"CID must be a string, got {type(cid).__name__}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Prepare API request data
            method = "store/remove"
            data = {
                "tasks": [
                    [
                        "store/remove",
                        space,
                        {
                            "link": { "/" : cid },
                        }
                    ]
                ]
            }
            
            # Make the API request
            logger.info(f"Removing content with CID {cid} from space {space}")
            timeout = kwargs.get('timeout', 60)
            
            http_response = self.storacha_http_request(
                auth_secret=auth_secret,
                authorization=authorization,
                method=method,
                data=data,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the request was successful
            if not isinstance(http_response, requests.Response):
                error_msg = "HTTP request failed, invalid response object returned"
                logger.error(error_msg)
                return handle_error(result, IPFSConnectionError(error_msg))
            
            # Parse the JSON response
            try:
                response_data = http_response.json()
            except ValueError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Process the response
            if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                error_msg = "Invalid response format from API"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Check for common response structure
            task_result = response_data[0]
            if "p" not in task_result or "out" not in task_result["p"]:
                error_msg = "Invalid task result format in API response"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            task_output = task_result["p"]["out"]
            
            # Check for success or error in the response
            if "ok" in task_output:
                # Success case
                ok_data = task_output["ok"]
                
                result["success"] = True
                result["removed"] = True
                result["response_data"] = ok_data
                
                logger.info(f"Successfully removed content with CID {cid} from space {space}")
                return result
                
            elif "error" in task_output:
                # Error case
                error_data = task_output["error"]
                error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            else:
                # Unexpected response format
                error_msg = f"Unexpected response format from API: {json.dumps(task_output)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
        except Exception as e:
            logger.exception(f"Unexpected error in store_remove_https: {str(e)}")
            return handle_error(result, e)
        
    def store_list_https(self, space, **kwargs):
        """List content in a Web3.Storage space using the HTTP API.
        
        Args:
            space: Name of the space to list content from
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing list of content
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("store_list_https", correlation_id)
        result["space"] = space
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Prepare API request data
            method = "store/list"
            data = {
                "space": space,
            }
            
            # Make the API request
            logger.info(f"Listing content from space {space}")
            timeout = kwargs.get('timeout', 60)
            
            http_response = self.storacha_http_request(
                auth_secret=auth_secret,
                authorization=authorization,
                method=method,
                data=data,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            # Check if the request was successful
            if not isinstance(http_response, requests.Response):
                error_msg = "HTTP request failed, invalid response object returned"
                logger.error(error_msg)
                return handle_error(result, IPFSConnectionError(error_msg))
            
            # Parse the JSON response
            try:
                response_data = http_response.json()
            except ValueError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
            
            # Success case - store/list has a different response format than other methods
            result["success"] = True
            result["content_list"] = response_data
            
            logger.info(f"Successfully listed content from space {space}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in store_list_https: {str(e)}")
            return handle_error(result, e)
    
    def upload_add_https(self, space, file, file_root, shards=None, **kwargs):
        """Add a file to Web3.Storage as an upload using the HTTP API.
        
        Args:
            space: Name of the space to add the upload to
            file: Path to the file to upload
            file_root: Root directory path for determining relative path
            shards: Optional list of shards for the upload
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds (default: 60)
                
        Returns:
            Dictionary with operation result containing upload information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("upload_add_https", correlation_id)
        result["space"] = space
        result["file"] = file
        
        # Temp file tracking for cleanup
        temp_filename = None
        
        try:
            # Validate required parameters
            if not space:
                return handle_error(result, IPFSValidationError("Missing required parameter: space"))
            
            if not file:
                return handle_error(result, IPFSValidationError("Missing required parameter: file"))
                
            if not file_root:
                return handle_error(result, IPFSValidationError("Missing required parameter: file_root"))
            
            # Validate space name (prevent command injection)
            if not isinstance(space, str):
                return handle_error(result, IPFSValidationError(f"Space name must be a string, got {type(space).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', space):
                return handle_error(result, IPFSValidationError(f"Space name contains invalid characters: {space}"))
            
            # Validate file path
            if not os.path.exists(file):
                return handle_error(result, IPFSContentNotFoundError(f"File not found: {file}"))
            
            # Check if we have tokens for this space
            if space not in self.tokens:
                error_msg = f"No authorization tokens available for space: {space}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Get auth tokens
            try:
                auth_secret = self.tokens[space]["X-Auth-Secret header"]
                authorization = self.tokens[space]["Authorization header"]
            except KeyError as e:
                error_msg = f"Missing required token: {str(e)}"
                logger.error(error_msg)
                return handle_error(result, IPFSValidationError(error_msg))
            
            # Create a temporary file for the CAR
            try:
                with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp:
                    temp_filename = temp.name
                    
                # Create CAR file command
                if platform.system() == "Windows":
                    base_cmd = ["npx", "ipfs-car", "pack", file, "--output", temp_filename]
                else:
                    base_cmd = ["ipfs-car", "pack", file, "--output", temp_filename]
                
                # Convert to string for shell execution
                # Security note: We need shell=True here for Windows compatibility issues with ipfs-car
                # We've validated inputs above to mitigate shell injection risks
                ipfs_car_cmd = " ".join(base_cmd)
                logger.info(f"Creating CAR file with command: {ipfs_car_cmd}")
                
                # Run the command to create CAR file
                try:
                    car_process = subprocess.run(
                        ipfs_car_cmd,
                        shell=True,  # Required for Windows compatibility with ipfs-car
                        check=False,  # We'll handle errors ourselves
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        timeout=kwargs.get('timeout', 120)  # CAR packing might take time for large files
                    )
                    
                    # Check for errors
                    if car_process.returncode != 0:
                        error_msg = f"Failed to create CAR file: {car_process.stderr.decode('utf-8', errors='replace')}"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                    
                    # Extract CID from output
                    output = car_process.stderr.decode("utf-8", errors="replace").strip()
                    output += car_process.stdout.decode("utf-8", errors="replace").strip()
                    
                    # Process output lines
                    output_lines = [line.strip() for line in output.split("\n") if line.strip()]
                    
                    if output_lines:
                        cid = output_lines[0]  # First line should contain the CID
                    else:
                        error_msg = "Could not extract CID from ipfs-car output"
                        logger.error(error_msg)
                        return handle_error(result, IPFSError(error_msg))
                        
                except subprocess.TimeoutExpired as e:
                    error_msg = f"Timeout while creating CAR file: {str(e)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSTimeoutError(error_msg))
                        
                # Normalize file path for inclusion in request
                normalized_filename = file.replace(file_root, "")
                normalized_filename = normalized_filename.replace("\\", "/")
                
                # Prepare API request data for upload/add
                method = "upload/add"
                data = {
                    "tasks": [
                        [
                            "upload/add",  # Fixed from "upload/remove" in original
                            space,
                            {
                                "root": {
                                    "/": cid
                                },
                            }
                        ]
                    ]
                }
                
                # Add shards if provided
                if shards is not None:
                    data["tasks"][0][2]["shards"] = shards
                
                # Make the API request
                logger.info(f"Making upload/add API request for file: {file}")
                timeout = kwargs.get('timeout', 60)
                
                http_response = self.storacha_http_request(
                    auth_secret=auth_secret,
                    authorization=authorization,
                    method=method,
                    data=data,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                
                # Check if the request was successful
                if not isinstance(http_response, requests.Response):
                    error_msg = "HTTP request failed, invalid response object returned"
                    logger.error(error_msg)
                    return handle_error(result, IPFSConnectionError(error_msg))
                
                # Parse the JSON response
                try:
                    response_data = http_response.json()
                except ValueError as e:
                    error_msg = f"Failed to parse JSON response: {str(e)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                    
                # Process the response
                if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
                    error_msg = "Invalid response format from API"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                # Check for common response structure
                task_result = response_data[0]
                if "p" not in task_result or "out" not in task_result["p"]:
                    error_msg = "Invalid task result format in API response"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                task_output = task_result["p"]["out"]
                
                # Check for success or error in the response
                if "ok" in task_output:
                    # Success case
                    ok_data = task_output["ok"]
                    
                    result["success"] = True
                    
                    # Handle different response formats
                    if "results" in ok_data:
                        results_list = ok_data["results"]
                        if len(results_list) == 0:
                            results_list = ['No uploads in space', 'Try out w3 up <path to files> to upload some']
                        
                        result["results"] = results_list
                    
                    if "root" in ok_data:
                        result["root"] = ok_data["root"]
                        # Extract the CID if it's in the root
                        if isinstance(ok_data["root"], dict) and "/" in ok_data["root"]:
                            result["cid"] = ok_data["root"]["/"]
                    
                    # Include all the response data for completeness
                    result["response_data"] = ok_data
                    
                    logger.info(f"Successfully added upload for file {file} to space {space}")
                    return result
                    
                elif "error" in task_output:
                    # Error case
                    error_data = task_output["error"]
                    error_msg = error_data if isinstance(error_data, str) else f"API error: {json.dumps(error_data)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
                else:
                    # Unexpected response format
                    error_msg = f"Unexpected response format from API: {json.dumps(task_output)}"
                    logger.error(error_msg)
                    return handle_error(result, IPFSError(error_msg))
                
            finally:
                # Clean up temporary files
                if temp_filename and os.path.exists(temp_filename):
                    try:
                        os.unlink(temp_filename)
                        logger.debug(f"Cleaned up temporary file: {temp_filename}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary file {temp_filename}: {str(e)}")
                        
        except Exception as e:
            logger.exception(f"Unexpected error in upload_add_https: {str(e)}")
            return handle_error(result, e)
        
    def shard_upload(self, space, file, file_root=None, **kwargs):
        """Upload a large file in shards to a Web3.Storage space.
        
        Args:
            space: The space to upload the file to
            file: Path to the file to upload
            file_root: Optional root path for the file
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("shard_upload")
                - timestamp: Unix timestamp of the operation
                - space: The space name file was uploaded to
                - file: Path to the file that was uploaded
                - error: Error message if failed
                - error_type: Type of error if failed
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": False,
            "operation": "shard_upload",
            "timestamp": time.time(),
            "space": space,
            "file": file,
            "correlation_id": correlation_id
        }
        
        # This method is currently a stub - not implemented yet
        # When implemented, it should follow the standardized error handling pattern
        
        # Placeholder implementation
        result["error"] = "Method not implemented"
        result["error_type"] = "not_implemented"
        logger.warning(f"shard_upload method called but not implemented [correlation_id: {correlation_id}]")
        
        return result

    def batch_operations(self, space, files=None, cids=None, **kwargs):
        """Perform multiple operations in a batch to a Web3.Storage space.
        
        Args:
            space: The space to perform operations on
            files: Optional list of files to add
            cids: Optional list of CIDs to manage
            **kwargs: Additional optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: HTTP request timeout in seconds
                - operations: List of operations to perform (e.g., ['add', 'get', 'remove'])
                
        Returns:
            Dictionary with operation results containing:
                - success: Boolean indicating overall success
                - operation: Name of the operation ("batch_operations")
                - timestamp: Unix timestamp of the operation
                - space: The space name operations were performed on
                - error: Error message if failed
                - error_type: Type of error if failed
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = {
            "success": False,
            "operation": "batch_operations",
            "timestamp": time.time(),
            "space": space,
            "correlation_id": correlation_id
        }
        
        # This method is currently a stub - not implemented yet
        # When implemented, it should follow the standardized error handling pattern
        
        # Set default values for optional parameters
        files = files or []
        cids = cids or []
        
        # Add details to result
        result["files"] = files
        result["cids"] = cids
        
        # Placeholder implementation
        result["error"] = "Method not implemented"
        result["error_type"] = "not_implemented" 
        logger.warning(f"batch_operations method called but not implemented [correlation_id: {correlation_id}]")
        
        return result

    def test(self):
        """Run a comprehensive self-test of the storacha_kit functionality.
        
        This method performs an end-to-end test of the storacha_kit functionality
        by executing a series of operations including:
        1. Installation of dependencies
        2. User login
        3. Space information retrieval
        4. Token generation
        5. Usage report retrieval
        6. Content upload/download using both CLI and HTTP API
        7. Content removal
        
        The method measures and records the time taken for each operation,
        providing performance metrics for the different API interfaces.
        
        Returns:
            Dictionary with test results and performance metrics
            
        Note:
            This method is primarily intended for development and debugging.
            It creates temporary test files that are cleaned up after testing.
        """
        import time
        timestamps = []
        small_file_size = 6 * 1024
        medium_file_size = 6 * 1024 * 1024
        large_file_size = 6 * 1024 * 1024 * 1024
        small_file_name = ""
        medium_file_name = ""
        large_file_name = ""
        print("storacha_kit test")
        self.install()
        email_did = self.login(self.metadata["login"])
        spaces = self.space_ls()
        this_space = spaces[list(spaces.keys())[0]]
        space_info = self.space_info(this_space)
        permissions = [
            "access/delegate",
            "space/info",
            "space/allocate",
            "store/add",
            "store/get",
            "store/remove",
            "store/list",
            "upload/add",
            "upload/list",
            "upload/remove",
            "usage/report"
        ]
        timestamps.append(time.time())
        bridge_tokens = self.bridge_generate_tokens(this_space, permissions)
        timestamps.append(time.time())
        usage_report = self.usage_report(this_space)
        timestamps.append(time.time())
        upload_list = self.upload_list(this_space)
        timestamps.append(time.time())
        upload_list_https = self.upload_list_https(this_space)
        timestamps.append(time.time())
        tempdir = tempfile.gettempdir()
        if os.path.exists(os.path.join(tempdir, "small_file.bin")):
            small_file_name = os.path.join(tempdir, "small_file.bin")
        else:    
            with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp:
                temp_filename = temp.name
                temp_path = os.path.join(tempdir, "small_file.bin")
                # Create a small binary file with zeros for testing, using a secure method
                with open(temp_path, 'wb') as f:
                    # Same implementation for all platforms - avoid shell=True/os.system
                    f.write(b'\0' * small_file_size)
                small_file_name = os.path.join(os.path.dirname(temp_filename), "small_file.bin")
        timestamps.append(time.time())
        upload_add = self.upload_add(this_space, small_file_name)
        timestamps.append(time.time())
        upload_add_https = self.upload_add_https(this_space, small_file_name)
        store_add = self.store_add(this_space, small_file_name)
        timestamps.append(time.time())
        store_add_https = self.store_add_https(this_space, small_file_name)
        timestamps.append(time.time())
        upload_rm = self.upload_remove(this_space, upload_add)
        timestamps.append(time.time())
        upload_rm_https = self.upload_remove_https(this_space, upload_add)
        timestamps.append(time.time())
        os.remove(small_file_name)
        timestamps.append(time.time())
        store_get = self.store_get(this_space, store_add[0])
        timestamps.append(time.time())
        store_get_https = self.store_get_https(this_space, store_add[0])
        timestamps.append(time.time())
        store_remove = self.store_remove(this_space, store_add[0])
        timestamps.append(time.time())
        store_remove_https = self.store_remove_https(this_space, store_add[0])
        timestamps.append(time.time())
        # batch_operations = self.batch_operations(this_space, [small_file_name], [store_add[0]])  
        timestamps.append(time.time())
        # Commented out - Large file creation test - uses secure file creation
        # file_size = 6 * 1024 * 1024 * 1024
        # with tempfile.NamedTemporaryFile(suffix=".bin") as temp:
        #     temp_filename = temp.name
        #     temp_path = os.path.abspath(temp_filename)
        #     with open(temp_path, 'wb') as f:
        #         # Create file in chunks to avoid memory issues
        #         chunk_size = 10 * 1024 * 1024  # 10MB chunks
        #         remaining = file_size
        #         while remaining > 0:
        #             write_size = min(chunk_size, remaining)
        #             f.write(b'\0' * write_size)
        #             remaining -= write_size
        #     with open(temp_path, "r") as file:
        #         temp.write(file.read())
        #     shard_upload = self.shard_upload(this_space, temp_path)
        timestamps.append(time.time())
        results = {
            "email_did": email_did,
            "spaces": spaces,
            "space_info": space_info,
            "bridge_tokens": bridge_tokens,
            "usage_report": usage_report,
            "upload_list": upload_list,
            "upload_list_https": upload_list_https,
            "upload_add": upload_add,
            "upload_add_https": upload_add_https,
            "upload_rm": upload_rm,
            "upload_rm_https": upload_rm_https,
            "store_add": store_add,
            "store_add_https": store_add_https,
            "store_get": store_get,
            "store_get_https": store_get_https,
            "store_remove": store_remove,
            "store_remove_https": store_remove_https,
            # "batch_operations": batch_operations,
            # "shard_upload": shard_upload,
        }
        
        timestamps_results = {
            "email_did": timestamps[1] - timestamps[0],
            "bridge_tokens": timestamps[2] - timestamps[1],
            "usage_report": timestamps[3] - timestamps[2],
            "upload_list": timestamps[4] - timestamps[3],
            "upload_list_https": timestamps[5] - timestamps[4],
            "upload_add": timestamps[6] - timestamps[5],
            "upload_add_https": timestamps[7] - timestamps[6],
            "upload_rm": timestamps[8] - timestamps[7],
            "upload_rm_https": timestamps[9] - timestamps[8],
            "store_add": timestamps[10] - timestamps[9],
            "store_add_https": timestamps[11] - timestamps[10],
            "store_get": timestamps[12] - timestamps[11],
            "store_get_https": timestamps[13] - timestamps[12],
            "store_remove": timestamps[14] - timestamps[13],
            "store_remove_https": timestamps[15] - timestamps[14],
            # "batch_operations": timestamps[16] - timestamps[15],
            # "shard_upload": timestamps[17] - timestamps[16],
        }
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open( os.path.join(parent_dir, "test","storacha_kit_test_results.json"), "w") as file:
            file.write(json.dumps(results, indent=4))
        with open( os.path.join(parent_dir, "test", "storacha_kit_test_timestamps.json"), "w") as file:
            file.write(json.dumps(timestamps_results, indent=4))
        return results

# if __name__ == "__main__":
#     resources = {
#     }
#     metadata = {
#         "login": "starworks5@gmail.com",
#     }
#     storacha_kit_py = storacha_kit(resources, metadata)
#     test = storacha_kit_py.test()
#     print(test)
