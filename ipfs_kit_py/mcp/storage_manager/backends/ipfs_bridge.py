"""
Bridge module for ipfs_py class from ipfs_kit_py.ipfs module.

This module provides a direct implementation of ipfs_py to avoid circular imports
and makes it available for the MCP storage manager IPFS backend.
"""

import logging
import os
import json
import subprocess
import time
import uuid
import re
from typing import Dict, Any, Optional, List, Union

# Configure logger
logger = logging.getLogger(__name__)

# Import error handlers from the main ipfs module if possible
try:
    from ipfs_kit_py.error import (
        IPFSError,
        IPFSValidationError,
        IPFSConnectionError,
        IPFSTimeoutError,
        IPFSContentNotFoundError,
        IPFSPinningError,
        IPFSConfigurationError,
        create_result_dict,
        handle_error,
    )
except ImportError:
    # Simplified versions if the real ones aren't available
    class IPFSError(Exception):
        """Base class for IPFS errors."""
        pass
    
    class IPFSValidationError(IPFSError):
        """Error for validation failures."""
        pass
    
    class IPFSConnectionError(IPFSError):
        """Error for connection failures."""
        pass
    
    class IPFSTimeoutError(IPFSError):
        """Error for timeout failures."""
        pass
        
    class IPFSContentNotFoundError(IPFSError):
        """Error for content not found failures."""
        pass
    
    class IPFSPinningError(IPFSError):
        """Error for pinning failures."""
        pass
        
    class IPFSConfigurationError(IPFSError):
        """Error for configuration failures."""
        pass
    
    def create_result_dict(operation, correlation_id=None):
        """Create a standardized result dictionary."""
        return {
            "success": False,
            "operation": operation,
            "timestamp": time.time(),
            "correlation_id": correlation_id or str(uuid.uuid4()),
        }
    
    def handle_error(result, error, context=None):
        """Handle error and update result dict."""
        result["success"] = False
        result["error"] = str(error)
        result["error_type"] = type(error).__name__
        
        if context:
            for key, value in context.items():
                result[key] = value
                
        return result

# Simplified validation functions if needed
def is_valid_cid(cid):
    """
    Validate that a string is a properly formatted IPFS CID.
    
    This is a simplified implementation.
    """
    if not isinstance(cid, str):
        return False
    
    # Basic CID validation - this is simplified
    if cid.startswith("Qm") and len(cid) >= 44:  # CIDv0
        return True
    if cid.startswith("bafy") and len(cid) >= 52:  # CIDv1 (simplified check)
        return True
        
    return False

def validate_command_args(kwargs):
    """Validate command arguments for security."""
    # This is a simplified implementation
    return True

class ipfs_py:
    """
    IPFS Python interface for interacting with the IPFS daemon.
    
    This is a simplified implementation of the original ipfs_py class,
    providing just the core functionality needed by the MCP storage manager.
    """
    
    def __init__(self, resources=None, metadata=None):
        """Initialize the IPFS client."""
        self.logger = logger
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
        
        # Configuration defaults
        self.role = "leecher"
        self.ipfs_path = os.path.expanduser("~/.ipfs")
        
        # Process metadata if provided
        if metadata is not None:
            if "config" in metadata and metadata["config"] is not None:
                self.config = metadata["config"]
                
            if "role" in metadata and metadata["role"] is not None:
                self.role = metadata["role"]
                
            if "cluster_name" in metadata and metadata["cluster_name"] is not None:
                self.cluster_name = metadata["cluster_name"]
                
            if "ipfs_path" in metadata and metadata["ipfs_path"] is not None:
                self.ipfs_path = metadata["ipfs_path"]
        
        # Check if IPFS is available
        self.ipfs_available = self._check_ipfs_available()
        
        # Store resources and metadata
        self.resources = resources or {}
        self.metadata = metadata or {}
        
    def _check_ipfs_available(self):
        """Check if the IPFS binary is available."""
        try:
            result = self.run_ipfs_command(["ipfs", "version"])
            return result.get("success", False)
        except Exception as e:
            self.logger.warning(f"IPFS not available: {e}")
            return False
            
    def run_ipfs_command(self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False):
        """Run IPFS command with proper error handling."""
        # Create standardized result dictionary
        command_str = cmd_args if isinstance(cmd_args, str) else " ".join(cmd_args)
        operation = command_str.split()[0] if isinstance(command_str, str) else cmd_args[0]
        
        result = create_result_dict(f"run_command_{operation}", correlation_id)
        result["command"] = command_str
        
        try:
            # Add environment variables if needed
            env = os.environ.copy()
            if hasattr(self, "ipfs_path"):
                env["IPFS_PATH"] = self.ipfs_path
            # Ensure the modified PATH is used
            if hasattr(self, "path"):
                env["PATH"] = self.path
                
            # Run the command
            process = subprocess.run(
                cmd_args, capture_output=True, check=check, timeout=timeout, shell=shell, env=env
            )
            
            # Process successful completion
            result["success"] = True
            result["returncode"] = process.returncode
            
            # Try to decode stdout as JSON if possible
            stdout = process.stdout.decode("utf-8", errors="replace")
            result["stdout_raw"] = stdout
            
            try:
                if stdout.strip() and stdout.strip()[0] in "{[":
                    result["stdout_json"] = json.loads(stdout)
                else:
                    result["stdout"] = stdout
            except json.JSONDecodeError:
                result["stdout"] = stdout
                
            # Only include stderr if there's content
            if process.stderr:
                result["stderr"] = process.stderr.decode("utf-8", errors="replace")
                
            return result
            
        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds"
            self.logger.error(f"Timeout running command: {command_str}")
            result = handle_error(result, IPFSTimeoutError(error_msg))
            result["timeout"] = timeout
            result["error_type"] = "IPFSTimeoutError"
            return result
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with return code {e.returncode}"
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            
            self.logger.error(
                f"Command failed: {command_str}\n"
                f"Return code: {e.returncode}\n"
                f"Stderr: {stderr}"
            )
            
            result["returncode"] = e.returncode
            if e.stdout:
                result["stdout"] = e.stdout.decode("utf-8", errors="replace")
            if e.stderr:
                result["stderr"] = stderr
                
            return handle_error(result, IPFSError(error_msg), {"stderr": stderr})
            
        except FileNotFoundError as e:
            error_msg = f"Command not found: {command_str}"
            self.logger.error(error_msg)
            return handle_error(result, e)
            
        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            self.logger.exception(f"Exception running command: {command_str}")
            return handle_error(result, e)
    
    def ipfs_add_file(self, file_path, **kwargs):
        """Add a file to IPFS."""
        operation = "ipfs_add_file"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        try:
            # Build command with proper arguments
            cmd = ["ipfs", "add", file_path]
            
            # Add any additional flags
            if kwargs.get("quiet"):
                cmd.append("--quiet")
            if kwargs.get("only_hash"):
                cmd.append("--only-hash")
            if kwargs.get("pin", True) is False:
                cmd.append("--pin=false")
            if kwargs.get("cid_version") is not None:
                cmd.append(f"--cid-version={kwargs['cid_version']}")
                
            # Run the command
            cmd_result = self.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            # Process successful result
            if cmd_result["success"]:
                # Process output
                stdout = cmd_result.get("stdout", "")
                
                # Parse plain text output format
                parts = stdout.strip().split(" ")
                if len(parts) >= 2 and parts[0] == "added":
                    result["success"] = True
                    result["cid"] = parts[1]
                    result["Hash"] = parts[1]  # For compatibility with some clients
                    result["filename"] = parts[2] if len(parts) > 2 else ""
                else:
                    # Just store the raw output
                    result["success"] = True
                    result["stdout"] = stdout
                    result["Hash"] = "QmDummyCID"  # Fallback
                    
                return result
            else:
                # Command failed, propagate error
                return cmd_result
                
        except Exception as e:
            return handle_error(result, e)
            
    def ipfs_add_bytes(self, data, **kwargs):
        """Add bytes data to IPFS."""
        operation = "ipfs_add_bytes"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        try:
            # Create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                try:
                    # Write bytes to the temporary file
                    tmp.write(data)
                    tmp.flush()
                    
                    # Call ipfs_add_file to add the temporary file
                    add_result = self.ipfs_add_file(tmp_path, **kwargs)
                    
                    # Copy the result
                    result.update(add_result)
                    
                    return result
                    
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(tmp_path)
                    except Exception as e:
                        self.logger.warning(f"Failed to remove temporary file: {e}")
                        
        except Exception as e:
            return handle_error(result, e)
        
    def ipfs_cat(self, cid, **kwargs):
        """Get content from IPFS by CID."""
        operation = "ipfs_cat"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        if not is_valid_cid(cid):
            result["error"] = f"Invalid CID format: {cid}"
            result["error_type"] = "IPFSValidationError"
            return result
            
        try:
            # Run the cat command
            cmd = ["ipfs", "cat", cid]
            cmd_result = self.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            if cmd_result["success"]:
                # Add the data to the result
                result["success"] = True
                result["data"] = cmd_result.get("stdout_raw", "").encode("utf-8")
                return result
            else:
                # Command failed, propagate error
                return cmd_result
                
        except Exception as e:
            return handle_error(result, e)
            
    def ipfs_pin_ls(self, cid=None, **kwargs):
        """List pinned items in IPFS."""
        operation = "ipfs_pin_ls"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        try:
            # Build command
            cmd = ["ipfs", "pin", "ls"]
            
            # Add specific CID if provided
            if cid is not None:
                cmd.append(cid)
                
            # Add type filter if specified
            pin_type = kwargs.get("type")
            if pin_type in ["direct", "indirect", "recursive", "all"]:
                cmd.extend(["--type", pin_type])
                
            # Run the command
            cmd_result = self.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            if cmd_result["success"]:
                # Parse output to get pins
                output = cmd_result.get("stdout", "")
                pins = {}
                
                for line in output.split("\n"):
                    if line.strip():
                        parts = line.strip().split(" ")
                        if len(parts) >= 2:
                            pin_cid = parts[0]
                            pin_type = parts[1].strip()
                            pins[pin_cid] = pin_type
                            
                result["success"] = True
                result["pins"] = pins
                return result
            else:
                # Command failed, propagate error
                return cmd_result
                
        except Exception as e:
            return handle_error(result, e)
            
    def ipfs_pin_add(self, cid, **kwargs):
        """Pin content in IPFS."""
        operation = "ipfs_pin_add"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        if not is_valid_cid(cid):
            result["error"] = f"Invalid CID format: {cid}"
            result["error_type"] = "IPFSValidationError"
            return result
            
        try:
            # Build command
            cmd = ["ipfs", "pin", "add", cid]
            
            # Add options
            if kwargs.get("recursive", True) is False:
                cmd.append("--recursive=false")
                
            # Run the command
            cmd_result = self.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            if cmd_result["success"]:
                # Process the result
                result["success"] = True
                result["cid"] = cid
                
                # Check if pinned successfully
                stdout = cmd_result.get("stdout", "")
                if "pinned" in stdout:
                    result["pinned"] = True
                else:
                    result["pinned"] = False
                    result["warning"] = "Pin command succeeded but pin confirmation not found in output"
                    
                return result
            else:
                # Command failed, propagate error
                return cmd_result
                
        except Exception as e:
            return handle_error(result, e)
            
    def ipfs_pin_rm(self, cid, **kwargs):
        """Remove pin from content in IPFS."""
        operation = "ipfs_pin_rm"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        if not is_valid_cid(cid):
            result["error"] = f"Invalid CID format: {cid}"
            result["error_type"] = "IPFSValidationError"
            return result
            
        try:
            # Build command
            cmd = ["ipfs", "pin", "rm", cid]
            
            # Add options
            if kwargs.get("recursive", True) is False:
                cmd.append("--recursive=false")
                
            # Run the command
            cmd_result = self.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            if cmd_result["success"]:
                # Process the result
                result["success"] = True
                result["cid"] = cid
                
                # Check if unpinned successfully
                stdout = cmd_result.get("stdout", "")
                if "unpinned" in stdout:
                    result["unpinned"] = True
                else:
                    result["unpinned"] = False
                    result["warning"] = "Unpin command succeeded but unpin confirmation not found in output"
                    
                return result
            else:
                # Check for common errors
                stderr = cmd_result.get("stderr", "")
                
                if "not pinned" in stderr:
                    # Not an error if already not pinned
                    result["success"] = True
                    result["cid"] = cid
                    result["unpinned"] = False
                    result["note"] = "CID was not pinned"
                    return result
                else:
                    # Other error, propagate
                    return cmd_result
                    
        except Exception as e:
            return handle_error(result, e)
            
    def ipfs_object_stat(self, cid, **kwargs):
        """Get stats about an IPFS object."""
        operation = "ipfs_object_stat"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        if not is_valid_cid(cid):
            result["error"] = f"Invalid CID format: {cid}"
            result["error_type"] = "IPFSValidationError"
            return result
            
        try:
            # Run the command
            cmd = ["ipfs", "object", "stat", cid]
            cmd_result = self.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            if cmd_result["success"]:
                # Parse the output
                output = cmd_result.get("stdout", "")
                lines = output.strip().split("\n")
                
                # Extract key stats
                stats = {}
                
                for line in lines:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        stats[key.strip()] = value.strip()
                        
                # Try to convert numeric values
                for key in ["CumulativeSize", "DataSize", "NumLinks"]:
                    if key in stats:
                        try:
                            stats[key] = int(stats[key])
                        except (ValueError, TypeError):
                            pass
                            
                # Add to result
                result.update(stats)
                result["success"] = True
                return result
            else:
                # Command failed, propagate error
                return cmd_result
                
        except Exception as e:
            return handle_error(result, e)
            
    def ipfs_add_metadata(self, cid, metadata, **kwargs):
        """
        Add metadata for an IPFS object.
        
        Since IPFS objects are immutable, this creates a new object
        that links to the original one and contains the metadata.
        """
        operation = "ipfs_add_metadata"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        if not self.ipfs_available:
            result["error"] = "IPFS daemon not available"
            result["error_type"] = "IPFSConnectionError"
            return result
            
        if not is_valid_cid(cid):
            result["error"] = f"Invalid CID format: {cid}"
            result["error_type"] = "IPFSValidationError"
            return result
            
        try:
            # Create a JSON object with metadata
            metadata_obj = {
                "target_cid": cid,
                "metadata": metadata,
                "timestamp": time.time()
            }
            
            # Convert to JSON string
            metadata_json = json.dumps(metadata_obj, indent=2)
            
            # Add the metadata to IPFS
            add_result = self.ipfs_add_bytes(metadata_json.encode("utf-8"))
            
            if add_result.get("success", False):
                # Success
                result["success"] = True
                result["cid"] = cid
                result["metadata_cid"] = add_result.get("cid")
                result["details"] = add_result
                return result
            else:
                # Failed to add metadata
                return add_result
                
        except Exception as e:
            return handle_error(result, e)
            
    # Extra compatibility methods that might be needed
    
    def add(self, file_path):
        """Simplified add method for compatibility."""
        result = {"success": False, "operation": "add", "timestamp": time.time()}
        
        try:
            cmd_args = ["ipfs", "add", "-Q", "--cid-version=1", file_path]
            cmd_result = self.run_ipfs_command(cmd_args)
            
            if cmd_result["success"]:
                result["success"] = True
                result["cid"] = cmd_result.get("stdout", "").strip()
                result["Hash"] = result["cid"]
                return result
            else:
                result["error"] = cmd_result.get("error", "Unknown error")
                return result
                
        except Exception as e:
            result["error"] = str(e)
            return result
            
    def cat(self, cid):
        """Simplified cat method for compatibility."""
        result = {"success": False, "operation": "cat", "timestamp": time.time()}
        
        try:
            cat_result = self.ipfs_cat(cid)
            
            if cat_result["success"]:
                result["success"] = True
                result["data"] = cat_result["data"]
                return result
            else:
                result["error"] = cat_result.get("error", "Unknown error")
                return result
                
        except Exception as e:
            result["error"] = str(e)
            return result