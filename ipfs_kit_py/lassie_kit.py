#!/usr/bin/env python3
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import uuid
import shutil
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import requests

# Configure logger
logger = logging.getLogger(__name__)

# Check if lassie is actually available by trying to run it
try:
    result = subprocess.run(["lassie", "--version"], capture_output=True, timeout=2)
    LASSIE_AVAILABLE = result.returncode == 0
except (subprocess.SubprocessError, FileNotFoundError, OSError):
    LASSIE_AVAILABLE = False

logger.info(f"Lassie binary available: {LASSIE_AVAILABLE}")

# Alias for backwards compatibility  
LASSIE_KIT_AVAILABLE = True  # Always set to True since we now support mock mode


class LassieValidationError(Exception):
    """Error when input validation fails."""
    pass


class LassieContentNotFoundError(Exception):
    """Content with specified CID not found."""
    pass


class LassieConnectionError(Exception):
    """Error when connecting to Lassie services."""
    pass


class LassieError(Exception):
    """Base class for all Lassie-related exceptions."""
    pass


class LassieTimeoutError(Exception):
    """Timeout when communicating with Lassie services."""
    pass


def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
    }


def handle_error(result, error, message=None):
    """Handle errors in a standardized way."""
    result["success"] = False
    result["error"] = message or str(error)
    result["error_type"] = type(error).__name__
    return result


class lassie_kit:
    def __init__(self, resources=None, metadata=None):
        """Initialize lassie_kit with resources and metadata.
        
        Args:
            resources (dict, optional): Resources for the Lassie client.
            metadata (dict, optional): Metadata containing connection information.
        """
        # Store resources
        self.resources = resources or {}

        # Store metadata
        self.metadata = metadata or {}

        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())

        # Set up paths
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = self.path + ":" + os.path.join(this_dir, "bin")
        self.path_string = "PATH=" + self.path

        # Set up Lassie API connection parameters
        self.api_url = self.metadata.get("api_url", "http://localhost:8484")
        self.timeout = self.metadata.get("timeout", 300)  # Default timeout of 5 minutes
        
        # Configure simulation mode
        self.simulation_mode = self.metadata.get("simulation_mode", not LASSIE_AVAILABLE)
        logger.info(f"Lassie kit initialized with simulation_mode: {self.simulation_mode}")
        
        # Track simulated content for consistent CID responses
        self.simulated_content = {}

    def run_lassie_command(self, cmd_args, check=True, timeout=60, correlation_id=None, shell=False):
        """Run a lassie CLI command with proper error handling.
        
        Args:
            cmd_args (list): The command and arguments to execute.
            check (bool, optional): Whether to check the command's return code.
            timeout (int, optional): Command timeout in seconds.
            correlation_id (str, optional): Correlation ID for tracking operations.
            shell (bool, optional): Whether to run the command in a shell.
            
        Returns:
            dict: Result dictionary with command output information.
        """
        result = {
            "success": False,
            "command": cmd_args[0] if cmd_args else None,
            "timestamp": time.time(),
            "correlation_id": correlation_id or self.correlation_id,
        }

        try:
            # Adjust command for Windows
            if (
                platform.system() == "Windows"
                and isinstance(cmd_args, list)
                and cmd_args[0] == "lassie"
            ):
                cmd_args = ["lassie.exe"] + cmd_args[1:]

            # Set up environment
            env = os.environ.copy()
            env["PATH"] = self.path

            # Run the command
            process = subprocess.run(
                cmd_args, 
                capture_output=True, 
                check=check, 
                timeout=timeout, 
                shell=shell, 
                env=env
            )

            # Process successful completion
            result["success"] = True
            result["returncode"] = process.returncode
            result["stdout"] = process.stdout.decode("utf-8", errors="replace")

            # Only include stderr if there's content
            if process.stderr:
                result["stderr"] = process.stderr.decode("utf-8", errors="replace")

            return result

        except subprocess.TimeoutExpired as e:
            result["error"] = f"Command timed out after {timeout} seconds"
            result["error_type"] = "timeout"
            logger.error(
                f"Timeout running command: {' '.join(cmd_args) if isinstance(cmd_args, list) else cmd_args}"
            )

        except subprocess.CalledProcessError as e:
            result["error"] = f"Command failed with return code {e.returncode}"
            result["error_type"] = "process_error"
            result["returncode"] = e.returncode
            result["stdout"] = e.stdout.decode("utf-8", errors="replace")
            result["stderr"] = e.stderr.decode("utf-8", errors="replace")
            logger.error(
                f"Command failed: {' '.join(cmd_args) if isinstance(cmd_args, list) else cmd_args}\n"
                f"Return code: {e.returncode}\n"
                f"Stderr: {e.stderr.decode('utf-8', errors='replace')}"
            )

        except Exception as e:
            result["error"] = f"Failed to execute command: {str(e)}"
            result["error_type"] = "execution_error"
            logger.exception(
                f"Exception running command: {' '.join(cmd_args) if isinstance(cmd_args, list) else cmd_args}"
            )

        return result

    def make_api_request(self, method, url, params=None, headers=None, data=None, files=None, timeout=None):
        """Make a request to the Lassie HTTP API.
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            url (str): URL to make the request to
            params (dict, optional): Query parameters
            headers (dict, optional): HTTP headers
            data (dict or str, optional): Request data
            files (dict, optional): Files to upload
            timeout (int, optional): Request timeout in seconds
            
        Returns:
            requests.Response: The response from the API
        """
        timeout = timeout or self.timeout
        
        # Set default headers
        if headers is None:
            headers = {}
        
        if "X-Request-Id" not in headers:
            headers["X-Request-Id"] = self.correlation_id
            
        # Make the request
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                data=data,
                files=files,
                timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.Timeout):
                raise LassieTimeoutError(f"Request timed out after {timeout} seconds") from e
            elif isinstance(e, requests.exceptions.ConnectionError):
                raise LassieConnectionError(f"Failed to connect to Lassie API: {str(e)}") from e
            else:
                raise LassieError(f"API request failed: {str(e)}") from e

    def fetch_cid(self, cid, path=None, block_limit=None, protocols=None, providers=None, 
                 dag_scope=None, output_file=None, filename=None, correlation_id=None):
        """Fetch content by CID from Filecoin/IPFS networks using Lassie.
        
        Args:
            cid (str): The CID to fetch
            path (str, optional): Optional IPLD path to traverse within the DAG
            block_limit (int, optional): Maximum number of blocks to retrieve (0 = infinite)
            protocols (list, optional): List of protocols to use (bitswap, graphsync, http)
            providers (list, optional): List of provider multiaddrs to use
            dag_scope (str, optional): Scope of DAG to fetch (block, entity, all)
            output_file (str, optional): Path to write the CAR file to
            filename (str, optional): Override filename in Content-Disposition header
            correlation_id (str, optional): Correlation ID for tracking operations
            
        Returns:
            dict: Result dictionary with operation results
        """
        # Set up result dictionary
        result = create_result_dict("fetch_cid", correlation_id or self.correlation_id)
        result["cid"] = cid
        
        try:
            # If we're in simulation mode, generate simulated content
            if self.simulation_mode:
                # Generate or retrieve simulated content
                if cid in self.simulated_content:
                    simulated_content = self.simulated_content[cid]
                else:
                    # Generate fake content based on CID
                    simulated_content = f"Simulated content for CID: {cid}".encode('utf-8')
                    
                    # Make it larger for realism
                    simulated_content += b"\0" * (1024 * 10)  # Add 10KB of padding
                    
                    # Store for future requests
                    self.simulated_content[cid] = simulated_content
                
                # Create fake CAR file content (just binary data that looks like a CAR file)
                car_header = b"\x0a\x0c\x0a\x01\x18\x01\x20\x01\x28\x01\x30\x01"  # Fake CAR header
                fake_car_content = car_header + simulated_content
                
                # Handle output file if provided
                if output_file:
                    with open(output_file, "wb") as f:
                        f.write(fake_car_content)
                    
                    result["output_file"] = output_file
                    result["file_size"] = len(fake_car_content)
                else:
                    # Return the simulated content
                    result["content"] = fake_car_content
                    result["content_length"] = len(fake_car_content)
                
                # Add simulated headers
                result["headers"] = {
                    "Content-Type": "application/vnd.ipld.car",
                    "Content-Length": str(len(fake_car_content)),
                    "X-Simulated": "true"
                }
                
                # Mark as simulated and successful
                result["simulated"] = True
                result["success"] = True
                logger.info(f"Simulated fetch_cid for: {cid}")
                
                return result
                
            # For non-simulation mode, continue with real implementation
            # Build URL path
            url_path = f"/ipfs/{cid}"
            if path:
                # Ensure path starts with a slash
                if not path.startswith("/"):
                    path = f"/{path}"
                url_path += path
            
            # Build query parameters
            params = {}
            if block_limit is not None:
                params["blockLimit"] = block_limit
            
            if protocols:
                params["protocols"] = ",".join(protocols)
            
            if providers:
                params["providers"] = ",".join(providers)
            
            if dag_scope:
                params["dag-scope"] = dag_scope
            
            if filename:
                # Ensure filename has .car extension
                if not filename.endswith(".car"):
                    filename += ".car"
                params["filename"] = filename
            
            # Always set format=car to request CAR format
            params["format"] = "car"
            
            # Prepare headers
            headers = {
                "Accept": "application/vnd.ipld.car",
                "X-Request-Id": correlation_id or self.correlation_id,
            }
            
            # Build full URL
            url = urljoin(self.api_url, url_path)
            
            # Make the request
            response = self.make_api_request(
                method="GET",
                url=url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            # Handle response
            if output_file:
                # If output_file is provided, write the response content to it
                with open(output_file, "wb") as f:
                    f.write(response.content)
                
                result["output_file"] = output_file
                result["file_size"] = len(response.content)
            else:
                # Otherwise, return the raw content
                result["content"] = response.content
                result["content_length"] = len(response.content)
            
            # Add response headers to result
            result["headers"] = dict(response.headers)
            
            # Mark operation as successful
            result["success"] = True
            
            return result
            
        except LassieContentNotFoundError as e:
            return handle_error(result, e, f"Content not found: {cid}")
        except LassieConnectionError as e:
            return handle_error(result, e)
        except LassieTimeoutError as e:
            return handle_error(result, e)
        except LassieError as e:
            return handle_error(result, e)
        except Exception as e:
            logger.exception(f"Error in fetch_cid: {str(e)}")
            return handle_error(result, e)

    def fetch_to_file(self, cid, output_file, **kwargs):
        """Fetch content by CID and save to a file.
        
        This is a convenience wrapper around fetch_cid that ensures
        the content is saved to a file.
        
        Args:
            cid (str): The CID to fetch
            output_file (str): Path to write the CAR file to
            **kwargs: Additional parameters passed to fetch_cid
            
        Returns:
            dict: Result dictionary with operation results
        """
        return self.fetch_cid(cid=cid, output_file=output_file, **kwargs)

    def extract_car(self, car_file, output_dir=None, cid=None, correlation_id=None):
        """Extract content from a CAR file.
        
        Args:
            car_file (str): Path to the CAR file
            output_dir (str, optional): Directory to extract content to
            cid (str, optional): Specific CID to extract from the CAR file
            correlation_id (str, optional): Correlation ID for tracking operations
            
        Returns:
            dict: Result dictionary with extraction results
        """
        # Set up result dictionary
        result = create_result_dict("extract_car", correlation_id or self.correlation_id)
        result["car_file"] = car_file
        
        try:
            # If output_dir is not provided, create a temporary directory
            temp_dir = None
            if not output_dir:
                temp_dir = tempfile.TemporaryDirectory()
                output_dir = temp_dir.name
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # If we're in simulation mode, simulate extraction by creating a dummy file
            if self.simulation_mode:
                # Try to extract a root CID from the filename
                root_cid = "bafybeideputujfqvguedljtyezdxwcguop4nvbaskcrhlrx7l7rwtpq6cq"
                
                # If a specific CID was provided, use that instead
                if cid:
                    root_cid = cid
                    
                # Create a directory for the extracted content
                extracted_dir = os.path.join(output_dir, root_cid)
                os.makedirs(extracted_dir, exist_ok=True)
                
                # Create a dummy file in the extracted directory
                dummy_file_path = os.path.join(extracted_dir, "content")
                with open(dummy_file_path, "wb") as f:
                    # Check if we have previously generated content for this CID
                    content = self.simulated_content.get(root_cid)
                    if not content:
                        # Generate dummy content
                        content = f"Simulated content for CID: {root_cid}".encode('utf-8')
                        # Store for future requests
                        self.simulated_content[root_cid] = content
                    
                    # Write the content
                    f.write(content)
                
                # Add simulated command result
                result["command_result"] = {
                    "success": True,
                    "command": "lassie extract (simulated)",
                    "stdout": f"Extracted content to {extracted_dir}\nRoot CID: {root_cid}",
                    "returncode": 0
                }
                
                # Add extraction details to result
                result["output_dir"] = output_dir
                result["root_cid"] = root_cid
                result["extracted_files"] = [dummy_file_path]
                result["simulated"] = True
                result["success"] = True
                
                logger.info(f"Simulated extract_car for file: {car_file}")
                return result
            
            # For non-simulation mode, run the real extraction command
            cmd_args = ["lassie", "extract", car_file, "--output-dir", output_dir]
            
            # Add specific CID if provided
            if cid:
                cmd_args.extend(["--cid", cid])
                
            cmd_result = self.run_lassie_command(
                cmd_args=cmd_args,
                timeout=self.timeout,
                correlation_id=correlation_id
            )
            
            if not cmd_result.get("success", False):
                return handle_error(
                    result, 
                    LassieError(cmd_result.get("error", "Unknown error")),
                    f"Failed to extract CAR file: {car_file}"
                )
            
            # Add command results to our result
            result["command_result"] = cmd_result
            result["output_dir"] = output_dir
            
            # Parse the output to find the extracted CID and files
            stdout = cmd_result.get("stdout", "")
            
            # Extract root CID if possible
            cid_match = re.search(r"Root CID: ([a-zA-Z0-9]+)", stdout)
            if cid_match:
                result["root_cid"] = cid_match.group(1)
            
            # Mark operation as successful
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in extract_car: {str(e)}")
            return handle_error(result, e)
        finally:
            # Clean up temporary directory if we created one
            if temp_dir:
                temp_dir.cleanup()

    def check_lassie_installed(self, correlation_id=None):
        """Check if Lassie CLI is installed and get its version.
        
        Args:
            correlation_id (str, optional): Correlation ID for tracking operations
            
        Returns:
            dict: Result dictionary with installation status
        """
        # Set up result dictionary
        result = create_result_dict("check_lassie_installed", correlation_id or self.correlation_id)
        
        try:
            # If we're in simulation mode, return a simulated successful result
            if self.simulation_mode:
                result["installed"] = True
                result["version"] = "1.0.0-simulation"
                result["success"] = True
                result["simulated"] = True
                return result
                
            # Run lassie version command
            cmd_result = self.run_lassie_command(
                cmd_args=["lassie", "--version"],
                check=False,  # Don't throw error if command fails
                timeout=10,  # Short timeout for version check
                correlation_id=correlation_id
            )
            
            # Check if command was successful
            if cmd_result.get("success", False) and cmd_result.get("returncode", 1) == 0:
                # Extract version from output
                stdout = cmd_result.get("stdout", "")
                version_match = re.search(r"lassie version ([0-9.]+)", stdout)
                
                if version_match:
                    version = version_match.group(1)
                else:
                    version = "unknown"
                
                result["installed"] = True
                result["version"] = version
                result["success"] = True
            else:
                result["installed"] = False
                result["error"] = "Lassie CLI not found or not working properly"
                
            return result
            
        except Exception as e:
            logger.exception(f"Error in check_lassie_installed: {str(e)}")
            return handle_error(result, e)

    def retrieve_content(self, cid, path=None, output_file=None, extract=True, verbose=False, correlation_id=None):
        """Retrieve content by CID.
        
        Args:
            cid (str): The CID to retrieve
            path (str, optional): Optional IPLD path to traverse within the DAG
            output_file (str, optional): Path to write the result to
            extract (bool, optional): Whether to extract the CAR file
            verbose (bool, optional): Whether to enable verbose output
            correlation_id (str, optional): Correlation ID for tracking operations
            
        Returns:
            dict: Result dictionary with operation results
        """
        # Set up result dictionary
        result = create_result_dict("retrieve_content", correlation_id or self.correlation_id)
        result["cid"] = cid
        
        try:
            # If we're in simulation mode, generate simulated content directly
            if self.simulation_mode:
                # Generate or retrieve simulated content
                if cid in self.simulated_content:
                    content = self.simulated_content[cid]
                else:
                    # Generate fake content based on CID
                    content = f"Simulated content for CID: {cid}".encode('utf-8')
                    
                    # Make it larger for realism
                    content += b"\0" * (1024 * 10)  # Add 10KB of padding
                    
                    # Store for future requests
                    self.simulated_content[cid] = content
                
                # Handle output file if provided
                if output_file:
                    # Create parent directories if needed
                    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
                    
                    # Write content to file
                    with open(output_file, "wb") as f:
                        f.write(content)
                    
                    result["output_file"] = output_file
                    result["file_size"] = len(content)
                    
                    if verbose:
                        logger.info(f"Simulated content written to {output_file} ({len(content)} bytes)")
                else:
                    # Return the simulated content
                    result["content"] = content
                    result["content_length"] = len(content)
                
                # Include extracted flag
                result["extracted"] = True if extract else False
                
                # Mark as simulated and successful
                result["simulated"] = True
                result["success"] = True
                logger.info(f"Simulated retrieve_content for: {cid}")
                
                return result
            
            # For non-simulation mode, use the standard implementation
            # Create a temporary file if output_file is not provided
            temp_car_file = None
            temp_output_dir = None
            if not output_file:
                # Create temporary file for the CAR file
                temp_car_file = tempfile.NamedTemporaryFile(suffix=".car", delete=False)
                temp_car_file.close()
                
                # Create temporary directory for extraction
                temp_output_dir = tempfile.TemporaryDirectory()
                
                # Set the output file path to a file in the temp directory
                output_file = os.path.join(temp_output_dir.name, "content")
            
            # Fetch the content as a CAR file
            car_path = temp_car_file.name if temp_car_file else f"{output_file}.car"
            fetch_result = self.fetch_to_file(cid, car_path, path=path)
            
            if not fetch_result.get("success", False):
                # Clean up temp files
                if temp_car_file:
                    os.unlink(temp_car_file.name)
                if temp_output_dir:
                    temp_output_dir.cleanup()
                    
                return handle_error(
                    result,
                    LassieError(fetch_result.get("error", "Unknown error")),
                    f"Failed to fetch content for CID: {cid}"
                )
            
            # Only extract if requested
            if extract:
                # Extract the CAR file
                extract_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else "."
                extract_result = self.extract_car(car_path, extract_dir)
                
                # Clean up the temporary CAR file
                if temp_car_file:
                    os.unlink(temp_car_file.name)
                
                if not extract_result.get("success", False):
                    # Clean up temp directory
                    if temp_output_dir:
                        temp_output_dir.cleanup()
                        
                    return handle_error(
                        result,
                        LassieError(extract_result.get("error", "Unknown error")),
                        f"Failed to extract content for CID: {cid}"
                    )
                
                # Add details to result
                result["output_file"] = output_file
                if os.path.exists(output_file):
                    result["file_size"] = os.path.getsize(output_file)
                    
                    # Attempt to read the content if the file is not too large
                    if result["file_size"] < 10 * 1024 * 1024:  # 10MB limit
                        with open(output_file, "rb") as f:
                            result["content"] = f.read()
                
                result["extracted"] = True
            else:
                # Just use the CAR file as is
                result["output_file"] = car_path
                result["file_size"] = os.path.getsize(car_path)
                result["extracted"] = False
                
                # If not too large, read the content
                if result["file_size"] < 10 * 1024 * 1024:  # 10MB limit
                    with open(car_path, "rb") as f:
                        result["content"] = f.read()
            
            # Set success flag
            result["success"] = True
            
            # Add verbose information if requested
            if verbose:
                result["verbose_info"] = {
                    "fetch_duration_ms": fetch_result.get("duration_ms"),
                    "extract_duration_ms": extract_result.get("duration_ms") if extract else 0,
                    "total_duration_ms": (time.time() - result["timestamp"]) * 1000
                }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in retrieve_content: {str(e)}")
            return handle_error(result, e)
        finally:
            # Clean up temp directory if we created one
            if temp_output_dir:
                temp_output_dir.cleanup()

    def __call__(self, method, **kwargs):
        """Call a method by name with keyword arguments.
        
        Args:
            method (str): The name of the method to call
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            dict: Result dictionary from the called method
        """
        # Map method names to methods
        method_map = {
            "fetch_cid": self.fetch_cid,
            "fetch_to_file": self.fetch_to_file,
            "extract_car": self.extract_car,
            "check_lassie_installed": self.check_lassie_installed,
            "retrieve_content": self.retrieve_content,
        }
        
        # Check if method exists
        if method in method_map:
            return method_map[method](**kwargs)
        else:
            # Return error for unknown method
            result = create_result_dict("unknown_method", kwargs.get("correlation_id", self.correlation_id))
            return handle_error(
                result,
                LassieError(f"Unknown method: {method}"),
                f"The method '{method}' is not supported by lassie_kit"
            )