"""Aria2 integration for ipfs_kit_py.

This module provides integration with Aria2, a high-speed download utility with
multi-connection/multi-source capabilities, extending the ipfs_kit_py ecosystem
with advanced download functionality.
"""

import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Union
import xml.etree.ElementTree as ET

try:
    import requests
    from urllib3.exceptions import InsecureRequestWarning

    # Suppress only the InsecureRequestWarning (for self-signed Aria2 RPC certificates)
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Create placeholder for imports
    requests = None

# Configure logger
logger = logging.getLogger(__name__)


def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }


def handle_error(result, error, message=None):
    """Handle errors in a standardized way."""
    result["success"] = False
    result["error"] = message or str(error)
    result["error_type"] = type(error).__name__
    return result


class aria2_kit:
    """Interface to Aria2 for high-speed, multi-source downloads.

    This class provides integration with Aria2, enabling high-performance downloads
    with advanced features like segmented downloading, BitTorrent support, and 
    metalink processing. It follows the storage backend pattern used in other 
    ipfs_kit_py components.
    """
    
    def _check_and_install_dependencies(self):
        """Check if required dependencies are available.
        
        This method ensures that the requests library and aria2c binary
        are available.
        
        Returns:
            bool: True if dependencies are available, False otherwise
        """
        global REQUESTS_AVAILABLE
        
        # Check for requests library
        if not REQUESTS_AVAILABLE:
            logger.warning("requests package not available. Some functionality will be limited.")
            logger.info("You can install it with: pip install requests")
            return False
            
        # Check for aria2c binary
        try:
            result = subprocess.run(
                ["aria2c", "--version"], 
                capture_output=True, 
                text=True,
                check=False
            )
            if result.returncode == 0:
                self.aria2_version = result.stdout.split("\n")[0]
                logger.info(f"Found aria2 version: {self.aria2_version}")
                return True
            else:
                logger.warning("aria2c binary not found in PATH or not executable.")
                return False
        except FileNotFoundError:
            logger.warning("aria2c binary not found in PATH.")
            logger.info("Please install aria2 with your package manager or from https://aria2.github.io/")
            return False
        
    def __init__(self, resources=None, metadata=None):
        """Initialize the Aria2 interface.

        Args:
            resources: Dictionary with resources and configuration
            metadata: Additional metadata
        """
        # Store resources
        self.resources = resources or {}
        
        # Store metadata
        self.metadata = metadata or {}
        
        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())
        
        # Initialize configuration
        self.rpc_url = self.resources.get("rpc_url", "http://localhost:6800/jsonrpc")
        self.rpc_secret = self.resources.get("rpc_secret", "")
        self.download_dir = self.resources.get("download_dir", os.path.expanduser("~/Downloads"))
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Auto-check dependencies on first run if they're not already checked
        if not self.metadata.get("skip_dependency_check", False):
            self.dependencies_available = self._check_and_install_dependencies()
        else:
            self.dependencies_available = True
        
        # Initialize RPC session
        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        
        # Initialize daemon status
        self.daemon_running = False
        self.daemon_process = None
        
        # Auto-start daemon if configured
        if self.resources.get("auto_start_daemon", False):
            self.start_daemon()

    def __call__(self, method, **kwargs):
        """Call a method on the Aria2 kit.

        Args:
            method: Method name to call
            **kwargs: Arguments to pass to the method

        Returns:
            Result of the method call
        """
        # Forward the call to the appropriate method
        if method == "add_uri":
            return self.add_uri(**kwargs)
        elif method == "add_torrent":
            return self.add_torrent(**kwargs)
        elif method == "add_metalink":
            return self.add_metalink(**kwargs)
        elif method == "remove_download":
            return self.remove_download(**kwargs)
        elif method == "pause_download":
            return self.pause_download(**kwargs)
        elif method == "resume_download":
            return self.resume_download(**kwargs)
        elif method == "get_status":
            return self.get_status(**kwargs)
        elif method == "list_downloads":
            return self.list_downloads(**kwargs)
        elif method == "purge_downloads":
            return self.purge_downloads(**kwargs)
        elif method == "start_daemon":
            return self.start_daemon(**kwargs)
        elif method == "stop_daemon":
            return self.stop_daemon(**kwargs)
        elif method == "get_global_status":
            return self.get_global_status(**kwargs)
        elif method == "get_version":
            return self.get_version(**kwargs)
        else:
            result = create_result_dict(method, self.correlation_id)
            result["error"] = f"Unknown method: {method}"
            return result
    
    def _rpc_call(self, method, params=None):
        """Make an RPC call to the Aria2 daemon.
        
        Args:
            method: RPC method name
            params: Parameters for the method
            
        Returns:
            Response from the RPC server or error
        """
        if not REQUESTS_AVAILABLE:
            return {"error": "requests library not available"}
        
        if not self.session:
            self.session = requests.Session()
        
        # Prepare RPC payload
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or []
        }
        
        # Add secret token if provided
        if self.rpc_secret:
            if not params:
                payload["params"] = [f"token:{self.rpc_secret}"]
            else:
                payload["params"].insert(0, f"token:{self.rpc_secret}")
        
        try:
            # Make RPC call
            response = self.session.post(
                self.rpc_url, 
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=30,
                verify=False  # Allow self-signed certificates for local RPC
            )
            
            # Check response status
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP error: {response.status_code}", "details": response.text}
                
        except Exception as e:
            logger.exception(f"RPC call failed: {str(e)}")
            return {"error": f"RPC call failed: {str(e)}"}
    
    def start_daemon(self, **kwargs):
        """Start the Aria2 daemon.
        
        Args:
            **kwargs: Additional arguments for daemon configuration
            
        Returns:
            Result dictionary with daemon status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("start_daemon", correlation_id)
        
        # Check if daemon is already running
        if self.daemon_running and self.daemon_process:
            if self.daemon_process.poll() is None:
                result["success"] = True
                result["message"] = "Daemon already running"
                result["pid"] = self.daemon_process.pid
                return result
        
        try:
            # Prepare daemon arguments
            listen_port = kwargs.get("listen_port", 6800)
            rpc_listen_all = kwargs.get("rpc_listen_all", True)
            
            # Prepare command line arguments
            cmd = [
                "aria2c",
                "--enable-rpc=true",
                f"--rpc-listen-port={listen_port}",
                f"--rpc-listen-all={'true' if rpc_listen_all else 'false'}",
                f"--dir={self.download_dir}",
                "--daemon=false",  # We'll manage the process ourselves
                "--file-allocation=none",  # Faster startup
            ]
            
            # Add secret token if provided
            if self.rpc_secret:
                cmd.append(f"--rpc-secret={self.rpc_secret}")
            
            # Add user-provided arguments
            for key, value in kwargs.items():
                if key.startswith("aria2_"):
                    option_name = key[6:]  # Remove 'aria2_' prefix
                    if isinstance(value, bool):
                        cmd.append(f"--{option_name}={'true' if value else 'false'}")
                    else:
                        cmd.append(f"--{option_name}={value}")
            
            # Start daemon process
            self.daemon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for daemon to start
            time.sleep(2)
            
            # Check if daemon started successfully
            if self.daemon_process.poll() is None:
                self.daemon_running = True
                result["success"] = True
                result["message"] = "Daemon started successfully"
                result["pid"] = self.daemon_process.pid
                
                # Update RPC URL if port was changed
                if listen_port != 6800:
                    self.rpc_url = f"http://localhost:{listen_port}/jsonrpc"
                    result["rpc_url"] = self.rpc_url
            else:
                stdout, stderr = self.daemon_process.communicate()
                result["error"] = "Failed to start daemon"
                result["stdout"] = stdout
                result["stderr"] = stderr
                self.daemon_running = False
                self.daemon_process = None
            
            return result
            
        except Exception as e:
            logger.exception(f"Error starting daemon: {str(e)}")
            return handle_error(result, e)
    
    def stop_daemon(self, **kwargs):
        """Stop the Aria2 daemon.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with daemon status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("stop_daemon", correlation_id)
        
        # Check if daemon is running
        if not self.daemon_running or not self.daemon_process:
            result["success"] = True
            result["message"] = "Daemon not running"
            return result
        
        try:
            # Try to stop daemon gracefully via RPC
            rpc_result = self._rpc_call("aria2.shutdown")
            
            # If RPC call succeeded, wait for process to exit
            if "error" not in rpc_result:
                # Wait up to 5 seconds for process to exit
                for _ in range(5):
                    if self.daemon_process.poll() is not None:
                        break
                    time.sleep(1)
            
            # If process is still running, terminate it
            if self.daemon_process.poll() is None:
                self.daemon_process.terminate()
                # Wait for termination
                try:
                    self.daemon_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    self.daemon_process.kill()
                    self.daemon_process.wait()
            
            # Update status
            self.daemon_running = False
            self.daemon_process = None
            
            # Set result
            result["success"] = True
            result["message"] = "Daemon stopped successfully"
            
            return result
            
        except Exception as e:
            logger.exception(f"Error stopping daemon: {str(e)}")
            return handle_error(result, e)
    
    def add_uri(self, uris, filename=None, options=None, **kwargs):
        """Add a new download by URI.
        
        Args:
            uris: URI or list of URIs to download
            filename: Optional filename for the download
            options: Optional advanced options for the download
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with download status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("add_uri", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Convert single URI to list
            if isinstance(uris, str):
                uris = [uris]
            
            # Prepare options
            aria2_options = options or {}
            
            # Add filename if provided
            if filename:
                aria2_options["out"] = filename
            
            # Add download directory if not specified in options
            if "dir" not in aria2_options:
                aria2_options["dir"] = self.download_dir
            
            # Make RPC call
            rpc_result = self._rpc_call("aria2.addUri", [uris, aria2_options])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success and add download information
            result["success"] = True
            result["gid"] = rpc_result["result"]
            result["uris"] = uris
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in add_uri: {str(e)}")
            return handle_error(result, e)
    
    def add_torrent(self, torrent, options=None, **kwargs):
        """Add a new download by torrent file.
        
        Args:
            torrent: Path to torrent file or torrent file content
            options: Optional advanced options for the download
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with download status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("add_torrent", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Check if torrent is a file path or content
            torrent_content = None
            if isinstance(torrent, str) and os.path.isfile(torrent):
                with open(torrent, "rb") as f:
                    torrent_content = f.read()
            elif isinstance(torrent, bytes):
                torrent_content = torrent
            else:
                result["error"] = "Invalid torrent parameter. Must be a file path or torrent content."
                return result
            
            # Encode torrent content in base64
            import base64
            torrent_base64 = base64.b64encode(torrent_content).decode("utf-8")
            
            # Prepare options
            aria2_options = options or {}
            
            # Add download directory if not specified in options
            if "dir" not in aria2_options:
                aria2_options["dir"] = self.download_dir
            
            # Make RPC call
            rpc_result = self._rpc_call("aria2.addTorrent", [torrent_base64, [], aria2_options])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success and add download information
            result["success"] = True
            result["gid"] = rpc_result["result"]
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in add_torrent: {str(e)}")
            return handle_error(result, e)
    
    def add_metalink(self, metalink, options=None, **kwargs):
        """Add a new download by metalink file.
        
        Args:
            metalink: Path to metalink file or metalink content
            options: Optional advanced options for the download
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with download status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("add_metalink", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Check if metalink is a file path or content
            metalink_content = None
            if isinstance(metalink, str) and os.path.isfile(metalink):
                with open(metalink, "rb") as f:
                    metalink_content = f.read()
            elif isinstance(metalink, bytes):
                metalink_content = metalink
            else:
                result["error"] = "Invalid metalink parameter. Must be a file path or metalink content."
                return result
            
            # Encode metalink content in base64
            import base64
            metalink_base64 = base64.b64encode(metalink_content).decode("utf-8")
            
            # Prepare options
            aria2_options = options or {}
            
            # Add download directory if not specified in options
            if "dir" not in aria2_options:
                aria2_options["dir"] = self.download_dir
            
            # Make RPC call
            rpc_result = self._rpc_call("aria2.addMetalink", [metalink_base64, aria2_options])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success and add download information
            result["success"] = True
            result["gid"] = rpc_result["result"]
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in add_metalink: {str(e)}")
            return handle_error(result, e)
    
    def remove_download(self, gid, force=False, **kwargs):
        """Remove a download.
        
        Args:
            gid: Download ID
            force: Whether to force removal
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with removal status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("remove_download", correlation_id)
        result["gid"] = gid
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Choose removal method based on force parameter
            method = "aria2.forceRemove" if force else "aria2.remove"
            
            # Make RPC call
            rpc_result = self._rpc_call(method, [gid])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in remove_download: {str(e)}")
            return handle_error(result, e)
    
    def pause_download(self, gid, force=False, **kwargs):
        """Pause a download.
        
        Args:
            gid: Download ID
            force: Whether to force pause
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with pause status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("pause_download", correlation_id)
        result["gid"] = gid
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Choose pause method based on force parameter
            method = "aria2.forcePause" if force else "aria2.pause"
            
            # Make RPC call
            rpc_result = self._rpc_call(method, [gid])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in pause_download: {str(e)}")
            return handle_error(result, e)
    
    def resume_download(self, gid, **kwargs):
        """Resume a paused download.
        
        Args:
            gid: Download ID
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with resume status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("resume_download", correlation_id)
        result["gid"] = gid
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Make RPC call
            rpc_result = self._rpc_call("aria2.unpause", [gid])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in resume_download: {str(e)}")
            return handle_error(result, e)
    
    def get_status(self, gid, **kwargs):
        """Get download status.
        
        Args:
            gid: Download ID
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with download status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("get_status", correlation_id)
        result["gid"] = gid
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Make RPC call
            rpc_result = self._rpc_call("aria2.tellStatus", [gid])
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success and add status information
            result["success"] = True
            result["status"] = rpc_result["result"]
            
            # Extract key information for easier access
            status_info = rpc_result["result"]
            
            # Calculate progress if download size is known
            if "totalLength" in status_info and status_info["totalLength"] != "0":
                total_length = int(status_info["totalLength"])
                completed_length = int(status_info["completedLength"])
                progress = (completed_length / total_length) * 100 if total_length > 0 else 0
                result["progress"] = progress
            else:
                result["progress"] = 0
            
            # Extract additional information
            result["download_speed"] = int(status_info.get("downloadSpeed", 0))
            result["upload_speed"] = int(status_info.get("uploadSpeed", 0))
            result["completed_length"] = int(status_info.get("completedLength", 0))
            result["total_length"] = int(status_info.get("totalLength", 0))
            result["state"] = status_info.get("status", "unknown")
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in get_status: {str(e)}")
            return handle_error(result, e)
    
    def list_downloads(self, **kwargs):
        """List all downloads.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with download list
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("list_downloads", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Get active downloads
            active_result = self._rpc_call("aria2.tellActive")
            
            if "error" in active_result:
                result["error"] = active_result["error"]
                return result
            
            # Get waiting downloads (up to 1000)
            waiting_result = self._rpc_call("aria2.tellWaiting", [0, 1000])
            
            if "error" in waiting_result:
                result["error"] = waiting_result["error"]
                return result
            
            # Get stopped downloads (up to 1000)
            stopped_result = self._rpc_call("aria2.tellStopped", [0, 1000])
            
            if "error" in stopped_result:
                result["error"] = stopped_result["error"]
                return result
            
            # Combine all downloads
            active_downloads = active_result["result"]
            waiting_downloads = waiting_result["result"]
            stopped_downloads = stopped_result["result"]
            
            all_downloads = []
            
            # Process active downloads
            for download in active_downloads:
                all_downloads.append({
                    "gid": download["gid"],
                    "status": download["status"],
                    "name": download.get("bittorrent", {}).get("info", {}).get("name") or download.get("files", [{}])[0].get("path", "").split("/")[-1],
                    "total_length": int(download.get("totalLength", 0)),
                    "completed_length": int(download.get("completedLength", 0)),
                    "download_speed": int(download.get("downloadSpeed", 0)),
                    "upload_speed": int(download.get("uploadSpeed", 0)),
                    "progress": (int(download.get("completedLength", 0)) / int(download.get("totalLength", 1))) * 100 if int(download.get("totalLength", 0)) > 0 else 0,
                    "state": "active"
                })
            
            # Process waiting downloads
            for download in waiting_downloads:
                all_downloads.append({
                    "gid": download["gid"],
                    "status": download["status"],
                    "name": download.get("bittorrent", {}).get("info", {}).get("name") or download.get("files", [{}])[0].get("path", "").split("/")[-1],
                    "total_length": int(download.get("totalLength", 0)),
                    "completed_length": int(download.get("completedLength", 0)),
                    "download_speed": 0,
                    "upload_speed": 0,
                    "progress": (int(download.get("completedLength", 0)) / int(download.get("totalLength", 1))) * 100 if int(download.get("totalLength", 0)) > 0 else 0,
                    "state": "waiting"
                })
            
            # Process stopped downloads
            for download in stopped_downloads:
                all_downloads.append({
                    "gid": download["gid"],
                    "status": download["status"],
                    "name": download.get("bittorrent", {}).get("info", {}).get("name") or download.get("files", [{}])[0].get("path", "").split("/")[-1],
                    "total_length": int(download.get("totalLength", 0)),
                    "completed_length": int(download.get("completedLength", 0)),
                    "download_speed": 0,
                    "upload_speed": 0,
                    "progress": (int(download.get("completedLength", 0)) / int(download.get("totalLength", 1))) * 100 if int(download.get("totalLength", 0)) > 0 else 0,
                    "state": "stopped"
                })
            
            # Set result success and add download list
            result["success"] = True
            result["downloads"] = all_downloads
            result["count"] = {
                "active": len(active_downloads),
                "waiting": len(waiting_downloads),
                "stopped": len(stopped_downloads),
                "total": len(all_downloads)
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in list_downloads: {str(e)}")
            return handle_error(result, e)
    
    def purge_downloads(self, **kwargs):
        """Purge completed/error/removed downloads.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with purge status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("purge_downloads", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Make RPC call
            rpc_result = self._rpc_call("aria2.purgeDownloadResult")
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in purge_downloads: {str(e)}")
            return handle_error(result, e)
    
    def get_global_status(self, **kwargs):
        """Get global download statistics.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with global statistics
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("get_global_status", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Make RPC call
            rpc_result = self._rpc_call("aria2.getGlobalStat")
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success and add global statistics
            result["success"] = True
            stats = rpc_result["result"]
            
            # Convert string values to integers
            result["stats"] = {
                "download_speed": int(stats.get("downloadSpeed", 0)),
                "upload_speed": int(stats.get("uploadSpeed", 0)),
                "num_active": int(stats.get("numActive", 0)),
                "num_waiting": int(stats.get("numWaiting", 0)),
                "num_stopped": int(stats.get("numStopped", 0)),
                "num_stopped_total": int(stats.get("numStoppedTotal", 0))
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in get_global_status: {str(e)}")
            return handle_error(result, e)
    
    def get_version(self, **kwargs):
        """Get Aria2 version information.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with version information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("get_version", correlation_id)
        
        if not REQUESTS_AVAILABLE:
            result["error"] = "requests library not available"
            return result
        
        try:
            # Make RPC call
            rpc_result = self._rpc_call("aria2.getVersion")
            
            if "error" in rpc_result:
                result["error"] = rpc_result["error"]
                return result
            
            # Set result success and add version information
            result["success"] = True
            result["version"] = rpc_result["result"]
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in get_version: {str(e)}")
            return handle_error(result, e)
    
    def create_metalink(self, file_data, **kwargs):
        """Create a metalink file for multiple sources.
        
        Args:
            file_data: List of dictionaries with file data
                Each dictionary should have:
                - name: File name
                - size: File size in bytes
                - urls: List of URLs to download from
                - hashes: Dict with hash types and values
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with metalink content
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("create_metalink", correlation_id)
        
        try:
            # Create metalink XML
            metalink = ET.Element("metalink", xmlns="urn:ietf:params:xml:ns:metalink")
            
            # Process each file
            for file_info in file_data:
                # Create file element
                file_elem = ET.SubElement(metalink, "file", name=file_info["name"])
                
                # Add file size
                size_elem = ET.SubElement(file_elem, "size")
                size_elem.text = str(file_info["size"])
                
                # Add URLs
                for url in file_info["urls"]:
                    url_elem = ET.SubElement(file_elem, "url")
                    url_elem.text = url
                
                # Add hashes
                for hash_type, hash_value in file_info.get("hashes", {}).items():
                    hash_elem = ET.SubElement(file_elem, "hash", type=hash_type)
                    hash_elem.text = hash_value
            
            # Convert to string
            from xml.dom import minidom
            xml_str = minidom.parseString(ET.tostring(metalink)).toprettyxml(indent="  ")
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".metalink", delete=False) as temp_file:
                temp_file.write(xml_str.encode())
                temp_file_path = temp_file.name
            
            # Set result success and add metalink path
            result["success"] = True
            result["metalink_path"] = temp_file_path
            result["metalink_content"] = xml_str
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in create_metalink: {str(e)}")
            return handle_error(result, e)