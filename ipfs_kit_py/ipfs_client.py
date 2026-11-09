"""
IPFS client implementation for the MCP server.

This module provides the ipfs_py class that was missing from ipfs_kit_py.ipfs.ipfs_py
as mentioned in the MCP roadmap. This is a simplified implementation that includes
the essential functionality needed by the IPFS backend.
"""

import logging
import subprocess
import json
import os
import tempfile
import shutil
from typing import Dict, Any, Optional, Union, BinaryIO, List

# Configure logger
logger = logging.getLogger(__name__)

class ipfs_py:
    """
    IPFS client implementation that provides an interface to interact with an IPFS node.
    
    This is a simplified version of the ipfs_py class that was missing from the
    ipfs_kit_py.ipfs.ipfs_py dependency, as mentioned in the MCP roadmap.
    """
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """
        Initialize the IPFS client.
        
        Args:
            resources: Dictionary containing configuration details like API endpoint
            metadata: Additional metadata for the client
        """
        self.resources = resources
        self.metadata = metadata
        self.api_endpoint = resources.get("api_endpoint", "http://localhost:5001/api/v0")
        self.timeout = resources.get("timeout", 60)
        self.ipfs_bin = resources.get("ipfs_bin", "ipfs")
        
        # Cache directory for temporary files
        self.cache_dir = resources.get("cache_dir", tempfile.gettempdir())
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Test the connection to the IPFS node
        connection_test = self._run_ipfs_command(["id"])
        if not connection_test.get("success", False):
            logger.warning(f"Failed to connect to IPFS node: {connection_test.get('error')}")
            logger.warning("Some IPFS operations may not work correctly.")
    
    def _run_ipfs_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Run an IPFS command using the ipfs binary.
        
        Args:
            args: List of command arguments
            
        Returns:
            Dictionary with the result
        """
        try:
            # Construct the full command
            cmd = [self.ipfs_bin] + args
            
            # Execute the command
            logger.debug(f"Running IPFS command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Process the command output
            if result.returncode == 0:
                # Successful command
                try:
                    # Try to parse as JSON if possible
                    output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    # Not JSON, use as string
                    output = result.stdout.strip()
                
                return {
                    "success": True,
                    "output": output
                }
            else:
                # Command failed
                return {
                    "success": False,
                    "error": result.stderr.strip(),
                    "returncode": result.returncode
                }
        except subprocess.TimeoutExpired:
            logger.error(f"IPFS command timed out after {self.timeout} seconds")
            return {"success": False, "error": f"Command timed out after {self.timeout} seconds"}
        except Exception as e:
            logger.error(f"Error running IPFS command: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def ipfs_add_file(self, file_obj: BinaryIO) -> Dict[str, Any]:
        """
        Add a file to IPFS.
        
        Args:
            file_obj: File-like object to add
            
        Returns:
            Dictionary with operation result including CID
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, dir=self.cache_dir) as temp_file:
                temp_path = temp_file.name
                # Write the file content
                shutil.copyfileobj(file_obj, temp_file)
            
            # Add the file to IPFS
            result = self._run_ipfs_command(["add", "-Q", temp_path])
            
            # Clean up
            try:
                os.unlink(temp_path)
            except:
                pass
            
            if result.get("success", False):
                cid = result.get("output", "").strip()
                if cid:
                    return {
                        "success": True,
                        "Hash": cid,
                        "cid": cid
                    }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to add file to IPFS")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_add_bytes(self, data: bytes) -> Dict[str, Any]:
        """
        Add bytes data to IPFS.
        
        Args:
            data: Bytes data to add
            
        Returns:
            Dictionary with operation result including CID
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, dir=self.cache_dir) as temp_file:
                temp_path = temp_file.name
                # Write the bytes data
                temp_file.write(data)
            
            # Add the file to IPFS
            result = self._run_ipfs_command(["add", "-Q", temp_path])
            
            # Clean up
            try:
                os.unlink(temp_path)
            except:
                pass
            
            if result.get("success", False):
                cid = result.get("output", "").strip()
                if cid:
                    return {
                        "success": True,
                        "Hash": cid,
                        "cid": cid
                    }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to add bytes to IPFS")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_cat(self, cid: str) -> Dict[str, Any]:
        """
        Retrieve content from IPFS.
        
        Args:
            cid: Content identifier (CID) to retrieve
            
        Returns:
            Dictionary with operation result including data
        """
        try:
            result = self._run_ipfs_command(["cat", cid])
            
            if result.get("success", False):
                # Convert output to bytes if it's a string
                output = result.get("output", "")
                if isinstance(output, str):
                    data = output.encode("utf-8")
                else:
                    data = output
                    
                return {
                    "success": True,
                    "data": data
                }
            
            return {
                "success": False,
                "error": result.get("error", f"Failed to retrieve content for CID: {cid}")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_pin_ls(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """
        List pinned items in IPFS.
        
        Args:
            cid: Optional CID to filter by
            
        Returns:
            Dictionary with operation result including pins
        """
        try:
            args = ["pin", "ls", "--json"]
            if cid:
                # Filter by specific CID
                args.append(cid)
            
            result = self._run_ipfs_command(args)
            
            if result.get("success", False):
                output = result.get("output", {})
                if isinstance(output, dict) and "Keys" in output:
                    # Format as {cid: {"Type": "recursive"}, ...}
                    pins = {cid: {"Type": details["Type"]} for cid, details in output["Keys"].items()}
                    return {
                        "success": True,
                        "pins": pins
                    }
                else:
                    return {
                        "success": True,
                        "pins": {}
                    }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to list pins")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_pin_add(self, cid: str) -> Dict[str, Any]:
        """
        Pin content in IPFS.
        
        Args:
            cid: Content identifier (CID) to pin
            
        Returns:
            Dictionary with operation result
        """
        try:
            result = self._run_ipfs_command(["pin", "add", cid])
            
            if result.get("success", False):
                return {
                    "success": True,
                    "Pins": [cid]
                }
            
            return {
                "success": False,
                "error": result.get("error", f"Failed to pin CID: {cid}")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_pin_rm(self, cid: str) -> Dict[str, Any]:
        """
        Unpin content from IPFS.
        
        Args:
            cid: Content identifier (CID) to unpin
            
        Returns:
            Dictionary with operation result
        """
        try:
            result = self._run_ipfs_command(["pin", "rm", cid])
            
            if result.get("success", False):
                return {
                    "success": True,
                    "Pins": [cid]
                }
            
            return {
                "success": False,
                "error": result.get("error", f"Failed to unpin CID: {cid}")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_object_stat(self, cid: str) -> Dict[str, Any]:
        """
        Get object stats for a CID.
        
        Args:
            cid: Content identifier (CID) to get stats for
            
        Returns:
            Dictionary with operation result including object stats
        """
        try:
            result = self._run_ipfs_command(["object", "stat", cid])
            
            if result.get("success", False):
                output = result.get("output", "")
                # Parse the output to extract stats
                stats = {}
                if isinstance(output, str):
                    # Parse text output
                    lines = output.strip().split("\n")
                    for line in lines:
                        if ":" in line:
                            key, value = line.split(":", 1)
                            stats[key.strip()] = value.strip()
                elif isinstance(output, dict):
                    # Already parsed as JSON
                    stats = output
                
                # Convert numeric values
                for key in ["CumulativeSize", "DataSize", "NumLinks", "BlockSize", "LinksSize"]:
                    if key in stats and isinstance(stats[key], str):
                        try:
                            stats[key] = int(stats[key])
                        except ValueError:
                            pass
                
                return {
                    "success": True,
                    **stats
                }
            
            return {
                "success": False,
                "error": result.get("error", f"Failed to get object stats for CID: {cid}")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_add_metadata(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add metadata for a CID.
        
        Note: This is a custom implementation since IPFS doesn't natively support metadata.
        The metadata is stored in a separate JSON file that references the original CID.
        
        Args:
            cid: Content identifier (CID) to add metadata for
            metadata: Metadata dictionary
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Create a JSON structure with the metadata
            metadata_json = {
                "target_cid": cid,
                "metadata": metadata,
                "timestamp": int(os.path.getmtime(__file__))
            }
            
            # Convert to JSON string
            metadata_str = json.dumps(metadata_json)
            
            # Add the metadata to IPFS
            return self.ipfs_add_bytes(metadata_str.encode("utf-8"))
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_ipfs_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Run an arbitrary IPFS command.
        
        Args:
            args: List of command arguments
            
        Returns:
            Dictionary with operation result
        """
        return self._run_ipfs_command(args)