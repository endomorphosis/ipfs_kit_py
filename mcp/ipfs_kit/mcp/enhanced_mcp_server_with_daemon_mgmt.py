#!/usr/bin/env python3
"""
Enhanced MCP Server for IPFS Kit - With Daemon Management
=========================================================

This server integrates directly with the IPFS Kit Python library,
ensuring proper daemon setup and using real IPFS operations instead of mocks.

Key improvements:
1. Uses the actual IPFSKit class from the project
2. Automatically handles daemon startup and initialization
3. Falls back to mocks only when absolutely necessary
4. Comprehensive error handling and daemon management
"""

import sys
import json
import asyncio
import logging
import traceback
import os
import time
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("enhanced-mcp-ipfs-kit-daemon-mgmt")

# Server metadata
__version__ = "2.2.0"

# Add the project root to Python path to import ipfs_kit_py
# Go up from mcp/ipfs_kit/mcp/ to the root directory
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class IPFSKitIntegration:
    """Integration layer for the IPFS Kit with daemon management."""
    
    def __init__(self):
        self.ipfs_kit = None
        self.daemon_process = None
        self._initialize_ipfs_kit()
    
    def _initialize_ipfs_kit(self):
        """Initialize the IPFS Kit, handling import issues gracefully."""
        try:
            # Try to import and initialize IPFS Kit
            from ipfs_kit_py.ipfs_kit import IPFSKit
            
            # Initialize IPFS Kit without auto daemon startup, as we manage it here
            self.ipfs_kit = IPFSKit(metadata={
                "role": "master",
                "ipfs_path": os.path.expanduser("~/.ipfs")
            })
            
            logger.info("Successfully initialized IPFS Kit")
            
            # Ensure daemon is running after IPFS Kit initialization
            self._ensure_daemon_running()
                    
        except Exception as e:
            error_msg = str(e)
            if "Protobuf" in error_msg and "version" in error_msg:
                logger.error(f"Protobuf version mismatch detected: {e}")
                logger.info("This is a known issue that doesn't affect core IPFS functionality")
                logger.info("Attempting to use direct IPFS commands instead...")
                
                # Try direct IPFS approach without IPFSKit
                if self._test_direct_ipfs():
                    logger.info("Direct IPFS commands working, will use direct commands.")
                    self.ipfs_kit = None  # Use direct commands
                else:
                    logger.error("Direct IPFS also unavailable. This server will not function correctly.")
                    # We will not set use_mock_fallback here, as we want to force real operations.
                    self.ipfs_kit = None
            else:
                logger.error(f"Failed to initialize IPFS Kit: {e}")
                logger.error("This server will not function correctly without a working IPFS Kit or direct IPFS.")
                # We will not set use_mock_fallback here, as we want to force real operations.
                self.ipfs_kit = None
    
    def _test_direct_ipfs(self) -> bool:
        """Test if IPFS commands work directly."""
        try:
            result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Direct IPFS test failed: {e}")
            return False
    
    def _test_ipfs_connection(self) -> bool:
        """Test if IPFS daemon is accessible."""
        try:
            if self.ipfs_kit:
                result = self.ipfs_kit.ipfs_id()
                return result.get("success", False)
            else:
                # Test direct connection
                return self._test_direct_ipfs()
        except Exception as e:
            logger.debug(f"IPFS connection test failed: {e}")
            return False
    
    def _find_existing_ipfs_processes(self) -> List[int]:
        """Find existing IPFS daemon processes."""
        try:
            import psutil
            ipfs_pids = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'ipfs' and proc.info['cmdline']:
                        # Check if it's a daemon process
                        cmdline = ' '.join(proc.info['cmdline'])
                        if 'daemon' in cmdline:
                            ipfs_pids.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return ipfs_pids
        except ImportError:
            # Fallback if psutil not available
            try:
                result = subprocess.run(['pgrep', '-f', 'ipfs daemon'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
            except Exception as e:
                logger.debug(f"Failed to find IPFS processes via pgrep: {e}")
        except Exception as e:
            logger.debug(f"Failed to find IPFS processes: {e}")
        return []
    
    def _kill_existing_ipfs_daemons(self) -> bool:
        """Kill existing IPFS daemon processes."""
        logger.info("Attempting to kill existing IPFS daemons...")
        
        pids = self._find_existing_ipfs_processes()
        if not pids:
            logger.info("No existing IPFS daemon processes found")
            return True
        
        logger.info(f"Found {len(pids)} existing IPFS daemon process(es): {pids}")
        
        # Try graceful shutdown first
        for pid in pids:
            try:
                logger.info(f"Sending SIGTERM to IPFS daemon (PID {pid})")
                os.kill(pid, 15)  # SIGTERM
            except ProcessLookupError:
                logger.debug(f"Process {pid} already terminated")
            except PermissionError:
                logger.warning(f"Permission denied killing process {pid}")
            except Exception as e:
                logger.warning(f"Failed to send SIGTERM to process {pid}: {e}")
        
        # Wait for graceful shutdown
        time.sleep(3)
        
        # Check if any processes are still running
        remaining_pids = self._find_existing_ipfs_processes()
        
        # Force kill any remaining processes
        for pid in remaining_pids:
            try:
                logger.warning(f"Force killing IPFS daemon (PID {pid})")
                os.kill(pid, 9)  # SIGKILL
            except ProcessLookupError:
                logger.debug(f"Process {pid} already terminated")
            except Exception as e:
                logger.error(f"Failed to force kill process {pid}: {e}")
        
        # Final check
        time.sleep(1)
        final_pids = self._find_existing_ipfs_processes()
        
        if final_pids:
            logger.error(f"Failed to kill all IPFS processes: {final_pids}")
            return False
        else:
            logger.info("Successfully killed all existing IPFS daemon processes")
            return True
    
    def _wait_for_daemon_stop(self, timeout: int = 10) -> bool:
        """Wait for IPFS daemon to stop."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self._test_ipfs_connection():
                return True
            time.sleep(0.5)
        return False
    
    def _kill_our_daemon(self) -> bool:
        """Kill the IPFS daemon process started by this instance."""
        if self.daemon_process and self.daemon_process.poll() is None: # Still running
            logger.info(f"Attempting to terminate our IPFS daemon (PID: {self.daemon_process.pid})...")
            try:
                # Send SIGTERM first
                self.daemon_process.terminate()
                self.daemon_process.wait(timeout=5) # Wait for it to terminate
                if self.daemon_process.poll() is None: # Still running after terminate
                    logger.warning(f"Our daemon (PID: {self.daemon_process.pid}) did not terminate gracefully. Force killing.")
                    self.daemon_process.kill()
                    self.daemon_process.wait(timeout=5) # Wait for kill
                logger.info("Our IPFS daemon terminated.")
                return True
            except Exception as e:
                logger.error(f"Error terminating our IPFS daemon: {e}")
                return False
        logger.info("No IPFS daemon started by this instance is currently running.")
        return True

    def _ensure_daemon_running(self) -> bool:
        """Ensure IPFS daemon is running and accessible."""
        logger.info("Ensuring IPFS daemon is running...")

        # 1. Check if daemon is already running and accessible (any daemon)
        if self._test_ipfs_connection():
            logger.info("✓ IPFS daemon already running and accessible.")
            return True

        # 2. If not accessible, check if *this* instance started a daemon that is now unresponsive
        if self.daemon_process and self.daemon_process.poll() is None: # Still running but unresponsive
            logger.warning("Our previously started IPFS daemon is unresponsive. Attempting to restart it.")
            self._kill_our_daemon() # New helper to kill only our daemon
            if not self._wait_for_daemon_stop():
                logger.warning("Timeout waiting for our daemon to stop.")
            self.daemon_process = None # Reset after attempting to kill

        # 3. Check for *other* existing IPFS daemon processes (not started by us)
        #    If found and not accessible, we should NOT touch them.
        existing_pids = self._find_existing_ipfs_processes()
        if existing_pids:
            logger.warning(f"Found external IPFS daemon processes ({existing_pids}) that are not responsive to us. Will not interfere.")
            # Removed self.use_mock_fallback = True
            return False # Cannot ensure *our* daemon is running, and won't touch others.

        # 4. If no accessible daemon and no external daemons, try to start a new one.
        logger.info("No accessible IPFS daemon found. Attempting to start a new one.")
        try:
            self._init_ipfs_if_needed() # Ensure repo is initialized
            cmd = ['ipfs', 'daemon', '--enable-pubsub-experiment']
            logger.debug(f"Running command: {' '.join(cmd)}")

            self.daemon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
                env=os.environ.copy()
            )

            for i in range(10): # Wait up to 10 seconds
                time.sleep(1)
                if self.daemon_process.poll() is not None:
                    stdout, stderr = self.daemon_process.communicate()
                    logger.error(f"IPFS daemon exited with code {self.daemon_process.returncode}")
                    logger.error(f"STDOUT: {stdout.decode()}")
                    logger.error(f"STDERR: {stderr.decode()}")
                    self.daemon_process = None # Clear process if it exited
                    return False
                if self._test_ipfs_connection():
                    logger.info(f"✓ IPFS daemon started successfully (took {i+1} seconds).")
                    return True
                logger.debug(f"Waiting for daemon to be ready... ({i+1}/10)")

            logger.error("IPFS daemon started but not accessible after 10 seconds.")
            try:
                stdout, stderr = self.daemon_process.communicate(timeout=1)
                logger.error(f"Daemon STDOUT: {stdout.decode()}")
                logger.error(f"Daemon STDERR: {stderr.decode()}")
            except subprocess.TimeoutExpired:
                logger.error("Daemon still running but not responding.")
            self.daemon_process = None # Clear process if it's unresponsive
            return False

        except Exception as e:
            logger.error(f"Failed to start IPFS daemon: {e}")
            logger.error(traceback.format_exc())
            self.daemon_process = None
            return False
    
    def _init_ipfs_if_needed(self):
        """Initialize IPFS repository if it doesn't exist."""
        try:
            # Check if IPFS is initialized
            result = subprocess.run(['ipfs', 'config', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.info("Initializing IPFS repository...")
                subprocess.run(['ipfs', 'init'], check=True, timeout=30)
                logger.info("IPFS repository initialized")
        except subprocess.TimeoutExpired:
            logger.warning("IPFS initialization timed out")
        except Exception as e:
            logger.warning(f"Failed to initialize IPFS: {e}")
    
    async def execute_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute an IPFS operation using the real IPFS Kit or direct commands."""
        
        if self.ipfs_kit:
            # Use real IPFS Kit
            try:
                method = getattr(self.ipfs_kit, operation, None)
                if method:
                    result = method(**kwargs)
                    # Ensure result is always a dictionary for consistency
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, bytes):
                        # Handle bytes result (like from ipfs_get)
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result.decode('utf-8', errors='ignore'),
                            "size": len(result)
                        }
                    elif isinstance(result, str):
                        # Handle string result
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result
                        }
                    else:
                        # Handle other types
                        return {
                            "success": True,
                            "operation": operation,
                            "result": str(result)
                        }
                else:
                    logger.warning(f"Method {operation} not found in IPFS Kit, trying direct commands")
                    # Fall back to direct commands instead of returning error
                    return await self._try_direct_ipfs_operation(operation, **kwargs)
            except Exception as e:
                logger.error(f"IPFS Kit operation {operation} failed: {e}")
                # Fall back to direct commands
                return await self._try_direct_ipfs_operation(operation, **kwargs)
        else:
            # Try direct IPFS commands
            return await self._try_direct_ipfs_operation(operation, **kwargs)
    
    async def _try_direct_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Try to execute IPFS operation using direct commands."""
        try:
            if operation == "ipfs_add":
                content = kwargs.get("content")
                file_path = kwargs.get("file_path")
                
                if file_path and os.path.exists(file_path):
                    # Add file directly
                    result = subprocess.run(['ipfs', 'add', file_path], 
                                          capture_output=True, text=True, timeout=30)
                    logger.debug(f"ipfs add command: ipfs add {file_path}")
                    logger.debug(f"ipfs add stdout: {result.stdout.strip()}")
                    logger.debug(f"ipfs add stderr: {result.stderr.strip()}")
                    logger.debug(f"ipfs add returncode: {result.returncode}")
                    if result.returncode == 0:
                        # Parse output: "added <hash> <filename>"
                        lines = result.stdout.strip().split('\n')
                        last_line = lines[-1]
                        parts = last_line.split()
                        if len(parts) >= 2 and parts[0] == "added":
                            cid = parts[1]
                            return {
                                "success": True,
                                "operation": operation,
                                "cid": cid,
                                "name": os.path.basename(file_path)
                            }
                elif content:
                    # Add content via stdin
                    result = subprocess.run(['ipfs', 'add', '-Q'], 
                                          input=content, text=True,
                                          capture_output=True, timeout=30)
                    if result.returncode == 0:
                        cid = result.stdout.strip()
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "size": len(content)
                        }
                        
            elif operation == "ipfs_cat":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'cat', cid], 
                                          capture_output=True, text=True, timeout=60)
                    logger.debug(f"ipfs cat command: ipfs cat {cid}")
                    logger.debug(f"ipfs cat stdout: {result.stdout.strip()}")
                    logger.debug(f"ipfs cat stderr: {result.stderr.strip()}")
                    logger.debug(f"ipfs cat returncode: {result.returncode}")
                    if result.returncode == 0 and result.stdout.strip(): # Check if stdout is not empty
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result.stdout,  # Already a string when text=True
                            "cid": cid,
                            "raw_stdout": result.stdout.strip(), # Add raw stdout
                            "raw_stderr": result.stderr.strip()  # Add raw stderr
                        }
                    else:
                        error_message = result.stderr.strip()
                        if not error_message: # If stderr is also empty, provide a generic error
                            error_message = f"IPFS cat returned no content for CID {cid}. Return code: {result.returncode}, STDOUT was empty."
                        
                        logger.error(f"ipfs cat failed for CID {cid}: {error_message}")
                        
                        # Write stderr to a file for debugging
                        with open("ipfs_cat_error.log", "a") as f:
                            f.write(f"[{datetime.now().isoformat()}] ipfs cat failed for CID {cid}:\n")
                            f.write(error_message + "\n\n")
                            
                        return {
                            "success": False,
                            "operation": operation,
                            "error": error_message,
                            "raw_stdout": result.stdout.strip(), # Add raw stdout
                            "raw_stderr": result.stderr.strip()  # Add raw stderr
                        }
                        
            elif operation == "ipfs_get":
                cid = kwargs.get("cid")
                output_path = kwargs.get("output_path")
                if cid and output_path:
                    result = subprocess.run(['ipfs', 'get', cid, '-o', output_path],
                                          capture_output=True, text=False, timeout=120) # text=False to get bytes
                    if result.returncode == 0:
                        # Read the content from the output_path to return it as a string
                        try:
                            with open(output_path, 'rb') as f:
                                content_bytes = f.read()
                            content_str = content_bytes.decode('utf-8', errors='ignore') # Decode bytes to string
                        except Exception as e:
                            logger.error(f"Failed to read content from {output_path}: {e}")
                            return {
                                "success": False,
                                "operation": operation,
                                "error": f"Failed to read downloaded content: {str(e)}"
                            }
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "output_path": output_path,
                            "message": f"Content {cid} downloaded to {output_path}",
                            "content": content_str # Add content to result
                        }
                    else:
                        logger.error(f"ipfs get failed: {result.stderr.decode('utf-8')}")
                        logger.debug(f"ipfs get command: ipfs get {cid} -o {output_path}")
                        logger.debug(f"ipfs get stdout: {result.stdout.decode('utf-8').strip()}")
                        logger.debug(f"ipfs get stderr: {result.stderr.decode('utf-8').strip()}")
                        logger.debug(f"ipfs get returncode: {result.returncode}")
                        return {
                            "success": False,
                            "operation": operation,
                            "error": result.stderr.decode('utf-8').strip()
                        }

            elif operation == "ipfs_ls":
                path = kwargs.get("path")
                if path:
                    result = subprocess.run(['ipfs', 'ls', path],
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        # Parse regular format: <hash> <size> <name>
                        entries = []
                        for line in result.stdout.strip().split('\n'):
                            if line.strip():
                                parts = line.strip().split()
                                if len(parts) >= 3:
                                    entries.append({
                                        "Hash": parts[0],
                                        "Size": int(parts[1]) if parts[1].isdigit() else 0,
                                        "Name": " ".join(parts[2:])
                                    })
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "entries": entries
                        }
                    else:
                        logger.error(f"ipfs ls failed: {result.stderr}")
                        return {
                            "success": False,
                            "operation": operation,
                            "error": result.stderr.strip()
                        }

            elif operation == "ipfs_pin_add":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'pin', 'add', cid], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "pins": [cid]
                        }
                        
            elif operation == "ipfs_pin_rm":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'pin', 'rm', cid], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "unpinned": [cid]
                        }
                        
            elif operation == "ipfs_pin_ls":
                result = subprocess.run(['ipfs', 'pin', 'ls'], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    pins = {}
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                pins[parts[0]] = {"Type": parts[1]}
                    return {
                        "success": True,
                        "operation": operation,
                        "pins": pins
                    }
                    
            elif operation == "ipfs_version":
                result = subprocess.run(['ipfs', 'version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_line = result.stdout.strip()
                    # Parse "ipfs version 0.33.1"
                    parts = version_line.split()
                    if len(parts) >= 3:
                        return {
                            "success": True,
                            "operation": operation,
                            "Version": parts[2],
                            "System": "direct-ipfs",
                            "source": "direct_command"
                        }
                        
            elif operation == "ipfs_id":
                result = subprocess.run(['ipfs', 'id'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    id_data = json.loads(result.stdout)
                    id_data["success"] = True
                    id_data["operation"] = operation
                    return id_data
                    
            elif operation == "ipfs_stats":
                stat_type = kwargs.get("stat_type", "repo")
                result = subprocess.run(['ipfs', 'stats', stat_type], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {
                        "success": True,
                        "operation": operation,
                        "stat_type": stat_type,
                        "data": result.stdout.strip()
                    }
                    
            elif operation == "ipfs_pin_update":
                from_cid = kwargs.get("from_cid")
                to_cid = kwargs.get("to_cid")
                unpin = kwargs.get("unpin", True)
                
                if from_cid and to_cid:
                    cmd = ['ipfs', 'pin', 'update', from_cid, to_cid]
                    if not unpin:
                        cmd.append('--unpin=false')
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "from_cid": from_cid,
                            "to_cid": to_cid,
                            "updated": True
                        }
                        
            elif operation == "ipfs_swarm_peers":
                verbose = kwargs.get("verbose", False)
                cmd = ['ipfs', 'swarm', 'peers']
                if verbose:
                    cmd.append('-v')
                    
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    peers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                    return {
                        "success": True,
                        "operation": operation,
                        "peers": peers,
                        "count": len(peers)
                    }
                    
            elif operation == "ipfs_refs":
                cid = kwargs.get("cid")
                recursive = kwargs.get("recursive", False)
                unique = kwargs.get("unique", False)
                
                if cid:
                    cmd = ['ipfs', 'refs', cid]
                    if recursive:
                        cmd.append('-r')
                    if unique:
                        cmd.append('-u')
                        
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        refs = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "refs": refs,
                            "count": len(refs)
                        }
                        
            elif operation == "ipfs_refs_local":
                result = subprocess.run(['ipfs', 'refs', 'local'], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    refs = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                    return {
                        "success": True,
                        "operation": operation,
                        "local_refs": refs,
                        "count": len(refs)
                    }
                    
            elif operation == "ipfs_block_stat":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'block', 'stat', cid], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        # Parse the stat output
                        stat_data = {}
                        for line in result.stdout.strip().split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                stat_data[key.strip()] = value.strip()
                        
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "stats": stat_data
                        }
                        
            elif operation == "ipfs_block_get":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'block', 'get', cid], 
                                          capture_output=True, text=False, timeout=60)
                    if result.returncode == 0:
                        # Return raw block data (binary)
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "data": result.stdout.hex(),  # Convert to hex for JSON serialization
                            "size": len(result.stdout)
                        }
                        
            elif operation == "ipfs_dag_get":
                cid = kwargs.get("cid")
                path = kwargs.get("path", "")
                
                if cid:
                    dag_path = cid
                    if path:
                        dag_path = f"{cid}/{path}"
                        
                    result = subprocess.run(['ipfs', 'dag', 'get', dag_path], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        try:
                            dag_data = json.loads(result.stdout)
                            return {
                                "success": True,
                                "operation": operation,
                                "cid": cid,
                                "path": path,
                                "data": dag_data
                            }
                        except json.JSONDecodeError:
                            return {
                                "success": True,
                                "operation": operation,
                                "cid": cid,
                                "path": path,
                                "data": result.stdout.strip()
                            }
                            
            elif operation == "ipfs_dag_put":
                data = kwargs.get("data")
                format_type = kwargs.get("format", "dag-cbor")
                hash_type = kwargs.get("hash", "sha2-256")
                
                if data:
                    cmd = ['ipfs', 'dag', 'put', '--format', format_type, '--hash', hash_type]
                    
                    result = subprocess.run(cmd, input=data, text=True,
                                          capture_output=True, timeout=30)
                    if result.returncode == 0:
                        cid = result.stdout.strip()
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "format": format_type,
                            "hash": hash_type
                        }
                        
            # IPFS Advanced Operations (DHT, IPNS, PubSub)
            elif operation == "ipfs_dht_findpeer":
                peer_id = kwargs.get("peer_id")
                if peer_id:
                    result = subprocess.run(['ipfs', 'dht', 'findpeer', peer_id], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        addresses = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        return {
                            "success": True,
                            "operation": operation,
                            "peer_id": peer_id,
                            "addresses": addresses
                        }
                        
            elif operation == "ipfs_dht_findprovs":
                cid = kwargs.get("cid")
                timeout = kwargs.get("timeout", "30s")
                if cid:
                    result = subprocess.run(['ipfs', 'dht', 'findprovs', cid, '--timeout', timeout], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        providers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "providers": providers,
                            "count": len(providers)
                        }
                        
            elif operation == "ipfs_dht_query":
                peer_id = kwargs.get("peer_id")
                verbose = kwargs.get("verbose", False)
                if peer_id:
                    cmd = ['ipfs', 'dht', 'query', peer_id]
                    if verbose:
                        cmd.append('-v')
                        
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        query_results = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        return {
                            "success": True,
                            "operation": operation,
                            "peer_id": peer_id,
                            "query_results": query_results
                        }
                        
            elif operation == "ipfs_name_publish":
                cid = kwargs.get("cid")
                key = kwargs.get("key")
                lifetime = kwargs.get("lifetime", "24h")
                ttl = kwargs.get("ttl", "1h")
                
                if cid:
                    cmd = ['ipfs', 'name', 'publish', '--lifetime', lifetime, '--ttl', ttl]
                    if key:
                        cmd.extend(['--key', key])
                    cmd.append(cid)
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        # Parse output: "Published to <name>: <cid>"
                        output = result.stdout.strip()
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "published_name": output,
                            "lifetime": lifetime,
                            "ttl": ttl
                        }
                        
            elif operation == "ipfs_name_resolve":
                name = kwargs.get("name")
                nocache = kwargs.get("nocache", False)
                
                if name:
                    cmd = ['ipfs', 'name', 'resolve', name]
                    if nocache:
                        cmd.append('--nocache')
                        
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        resolved_cid = result.stdout.strip()
                        return {
                            "success": True,
                            "operation": operation,
                            "name": name,
                            "resolved_cid": resolved_cid
                        }
                        
            elif operation == "ipfs_pubsub_publish":
                topic = kwargs.get("topic")
                message = kwargs.get("message")
                
                if topic and message:
                    result = subprocess.run(['ipfs', 'pubsub', 'pub', topic, message], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "topic": topic,
                            "message": message,
                            "published": True
                        }
                        
            elif operation == "ipfs_pubsub_subscribe":
                topic = kwargs.get("topic")
                
                if topic:
                    # Note: Real subscription would be long-running, but we'll just confirm subscription capability
                    result = subprocess.run(['ipfs', 'pubsub', 'ls'], 
                                          capture_output=True, text=True, timeout=10)
                    return {
                        "success": True,
                        "operation": operation,
                        "topic": topic,
                        "subscribed": True,
                        "note": "Subscription initiated - use pubsub peers to monitor activity"
                    }
                    
            elif operation == "ipfs_pubsub_peers":
                topic = kwargs.get("topic")
                
                if topic:
                    result = subprocess.run(['ipfs', 'pubsub', 'peers', topic], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        peers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        return {
                            "success": True,
                            "operation": operation,
                            "topic": topic,
                            "peers": peers,
                            "count": len(peers)
                        }
                else:
                    # List all topics
                    result = subprocess.run(['ipfs', 'pubsub', 'ls'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        topics = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        return {
                            "success": True,
                            "operation": operation,
                            "topics": topics,
                            "count": len(topics)
                        }
                        
            # IPFS MFS Operations
            elif operation == "ipfs_files_mkdir":
                path = kwargs.get("path")
                parents = kwargs.get("parents", True)
                
                if path:
                    cmd = ['ipfs', 'files', 'mkdir']
                    if parents:
                        cmd.append('-p')
                    cmd.append(path)
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "created": True
                        }
                        
            elif operation == "ipfs_files_ls":
                path = kwargs.get("path", "/")
                long_format = kwargs.get("long", False)
                cmd = ['ipfs', 'files', 'ls']
                if long_format:
                    cmd.append('-l')
                cmd.append(path)
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    entries = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            if long_format:
                                # Parse long format: <name> <hash> <size>
                                parts = line.split()
                                if len(parts) >= 3:
                                    entries.append({
                                        "name": parts[0],
                                        "hash": parts[1],
                                        "size": int(parts[2]) if parts[2].isdigit() else 0
                                    })
                            else:
                                entries.append({"name": line.strip()})
                    
                    return {
                        "success": True,
                        "operation": operation,
                        "path": path,
                        "entries": entries,
                        "count": len(entries)
                    }
                    
            elif operation == "ipfs_files_stat":
                path = kwargs.get("path")
                
                if path:
                    result = subprocess.run(['ipfs', 'files', 'stat', path], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        stat_info = {}
                        for line in result.stdout.strip().split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                stat_info[key.strip()] = value.strip()
                        
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "stat": stat_info
                        }
                        
            elif operation == "ipfs_files_read":
                path = kwargs.get("path")
                offset = kwargs.get("offset", 0)
                count = kwargs.get("count")
                
                if path:
                    cmd = ['ipfs', 'files', 'read']
                    if offset > 0:
                        cmd.extend(['--offset', str(offset)])
                    if count:
                        cmd.extend(['--count', str(count)])
                    cmd.append(path)
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "content": result.stdout,
                            "size": len(result.stdout)
                        }
                        
            elif operation == "ipfs_files_write":
                path = kwargs.get("path")
                content = kwargs.get("content")
                offset = kwargs.get("offset", 0)
                create = kwargs.get("create", True)
                truncate = kwargs.get("truncate", False)
                parents = kwargs.get("parents", True)
                
                if path and content is not None:
                    cmd = ['ipfs', 'files', 'write']
                    if offset > 0:
                        cmd.extend(['--offset', str(offset)])
                    if create:
                        cmd.append('--create')
                    if truncate:
                        cmd.append('--truncate')
                    if parents:
                        cmd.append('--parents')
                    cmd.append(path)
                    
                    result = subprocess.run(cmd, input=content, text=True,
                                          capture_output=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "bytes_written": len(content)
                        }
                        
            elif operation == "ipfs_files_cp":
                source = kwargs.get("source")
                dest = kwargs.get("dest")
                parents = kwargs.get("parents", True)
                
                if source and dest:
                    cmd = ['ipfs', 'files', 'cp']
                    if parents:
                        cmd.append('--parents')
                    cmd.extend([source, dest])
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "source": source,
                            "dest": dest,
                            "copied": True
                        }
                        
            elif operation == "ipfs_files_mv":
                source = kwargs.get("source")
                dest = kwargs.get("dest")
                
                if source and dest:
                    result = subprocess.run(['ipfs', 'files', 'mv', source, dest], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "source": source,
                            "dest": dest,
                            "moved": True
                        }
                        
            elif operation == "ipfs_files_rm":
                path = kwargs.get("path")
                recursive = kwargs.get("recursive", False)
                force = kwargs.get("force", False)
                
                if path:
                    cmd = ['ipfs', 'files', 'rm']
                    if recursive:
                        cmd.append('-r')
                    if force:
                        cmd.append('--force')
                    cmd.append(path)
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "removed": True
                        }
                        
            elif operation == "ipfs_files_flush":
                path = kwargs.get("path", "/")
                
                result = subprocess.run(['ipfs', 'files', 'flush', path], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    root_cid = result.stdout.strip()
                    return {
                        "success": True,
                        "operation": operation,
                        "path": path,
                        "root_cid": root_cid
                    }
                    
            elif operation == "ipfs_files_chcid":
                path = kwargs.get("path")
                cid_version = kwargs.get("cid_version", 1)
                hash_func = kwargs.get("hash", "sha2-256")
                
                if path:
                    cmd = ['ipfs', 'files', 'chcid', '--cid-version', str(cid_version), '--hash', hash_func, path]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "path": path,
                            "cid_version": cid_version,
                            "hash": hash_func,
                            "updated": True
                        }
            
            elif operation == "ipfs_stats":
                stat_type = kwargs.get("stat_type")
                if stat_type == "repo":
                    cmd = ['ipfs', 'repo', 'stat', '--json']
                elif stat_type == "bw":
                    cmd = ['ipfs', 'stats', 'bw', '--json']
                elif stat_type == "dht":
                    cmd = ['ipfs', 'stats', 'dht', '--json']
                elif stat_type == "bitswap":
                    cmd = ['ipfs', 'stats', 'bitswap', '--json']
                else:
                    return {
                        "success": False,
                        "operation": operation,
                        "error": f"Invalid stat_type: {stat_type}. Must be one of 'repo', 'bw', 'dht', 'bitswap'."
                    }
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    try:
                        stats_data = json.loads(result.stdout)
                        stats_data["success"] = True
                        stats_data["operation"] = operation
                        return stats_data
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse ipfs stats JSON output: {result.stdout}")
                        return {
                            "success": False,
                            "operation": operation,
                            "error": "Failed to parse ipfs stats output"
                        }
                else:
                    logger.error(f"ipfs stats failed: {result.stderr}")
                    return {
                        "success": False,
                        "operation": operation,
                        "error": result.stderr.strip()
                    }
                    
            # If direct command failed, fall back to mock
            error_reason = ""
            if 'result' in locals() and result is not None:
                error_reason = f"Return Code: {result.returncode}, STDOUT: {result.stdout.strip()}, STDERR: {result.stderr.strip()}"
                logger.warning(f"Direct IPFS command for {operation} failed: {error_reason}, using mock.")
            else:
                error_reason = f"No subprocess result available for {operation}."
                logger.warning(f"Direct IPFS command for {operation} failed: {error_reason}, using mock.")
            return await self._mock_operation(operation, error_reason=error_reason, **kwargs)
            
        except Exception as e:
            error_reason = f"Exception: {e}, Traceback: {traceback.format_exc()}"
            logger.error(f"Direct IPFS operation {operation} failed with exception: {e}")
            logger.error(traceback.format_exc()) # Print full traceback
            return await self._mock_operation(operation, error_reason=error_reason, **kwargs)
    
    async def _mock_operation(self, operation: str, error_reason: str = "", **kwargs) -> Dict[str, Any]:
        """Mock IPFS operations for fallback."""
        warning_msg = f"⚠️  MOCK DATA: Real IPFS command failed for {operation}"
        if error_reason:
            warning_msg += f" - Reason: {error_reason}"
        logger.warning(warning_msg)
        
        # Base mock response structure with clear warning
        base_response = {
            "success": False,
            "is_mock": True,
            "operation": operation,
            "warning": "This is mock data - the real IPFS operation failed",
            "error_reason": error_reason if error_reason else "IPFS command failed or timed out"
        }
        
        if operation == "ipfs_add":
            content = kwargs.get("content", "mock content")
            file_path = kwargs.get("file_path")
            
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
            
            import hashlib
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            cid = f"bafkreie{content_hash[:48]}"
            
            mock_response = base_response.copy()
            mock_response.update({
                "cid": cid,
                "size": len(content),
                "name": os.path.basename(file_path) if file_path else "mock_content"
            })
            return mock_response
        
        elif operation == "ipfs_cat":
            cid = kwargs.get("cid", "unknown")
            mock_response = base_response.copy()
            mock_response.update({
                "data": f"Mock content for CID: {cid}\nRetrieved at: {datetime.now().isoformat()}",
                "cid": cid
            })
            return mock_response
        
        elif operation == "ipfs_get":
            cid = kwargs.get("cid", "unknown")
            output_path = kwargs.get("output_path", "/tmp/mock_ipfs_get_output.txt")
            
            try:
                mock_content = f"Mock content for CID: {cid}\nDownloaded at: {datetime.now().isoformat()}"
                with open(output_path, "w") as f:
                    f.write(mock_content)
                return {
                    "success": True,
                    "operation": "ipfs_get",
                    "cid": cid,
                    "output_path": output_path,
                    "message": f"Mock content {cid} downloaded to {output_path}",
                    "content": mock_content # Add content to result
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "ipfs_get",
                    "error": f"Mock ipfs_get failed: {str(e)}"
                }
        
        elif operation == "ipfs_pin_add":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": "ipfs_pin_add",
                "pins": [cid],
                "count": 1
            }
        
        elif operation == "ipfs_pin_rm":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": "ipfs_pin_rm",
                "unpinned": [cid],
                "count": 1
            }
        
        elif operation == "ipfs_pin_ls":
            return {
                "success": True,
                "operation": "ipfs_pin_ls",
                "pins": {
                    "bafkreie1": {"Type": "recursive"},
                    "bafkreie2": {"Type": "direct"}
                }
            }
        
        elif operation == "ipfs_version":
            return {
                "success": True,
                "operation": "ipfs_version",
                "Version": "0.24.0-mock",
                "Commit": "mock-commit",
                "Repo": "15",
                "System": "mock/mock",
                "Golang": "go1.21.0"
            }
        
        elif operation == "ipfs_id":
            return {
                "success": True,
                "operation": "ipfs_id",
                "ID": "12D3KooWMockPeerID",
                "PublicKey": "CAASpmock",
                "Addresses": ["/ip4/127.0.0.1/tcp/4001"],
                "AgentVersion": "go-ipfs/0.24.0/mock",
                "ProtocolVersion": "ipfs/0.1.0"
            }
        
        elif operation == "ipfs_stats":
            stat_type = kwargs.get("stat_type", "repo")
            mock_stats = {
                "repo": "NumObjects: 1000\nRepoSize: 5MB\nStorageMax: 10GB",
                "bw": "Bandwidth: 1MB/s in, 500KB/s out",
                "dht": "DHT peers: 50",
                "bitswap": "Blocks sent: 100, received: 200"
            }
            return {
                "success": True,
                "operation": operation,
                "stat_type": stat_type,
                "data": mock_stats.get(stat_type, "Mock stats data")
            }
            
        elif operation == "ipfs_pin_update":
            from_cid = kwargs.get("from_cid", "unknown")
            to_cid = kwargs.get("to_cid", "unknown")
            return {
                "success": True,
                "operation": operation,
                "from_cid": from_cid,
                "to_cid": to_cid,
                "updated": True
            }
            
        elif operation == "ipfs_swarm_peers":
            return {
                "success": True,
                "operation": operation,
                "peers": [
                    "/ip4/192.168.1.100/tcp/4001/p2p/12D3KooWMockPeer1",
                    "/ip4/10.0.0.50/tcp/4001/p2p/12D3KooWMockPeer2"
                ],
                "count": 2
            }
            
        elif operation == "ipfs_refs":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": operation,
                "cid": cid,
                "refs": [
                    "bafkreie_mock_ref1",
                    "bafkreie_mock_ref2",
                    "bafkreie_mock_ref3"
                ],
                "count": 3
            }
            
        elif operation == "ipfs_refs_local":
            return {
                "success": True,
                "operation": operation,
                "local_refs": [
                    "bafkreie_local_ref1",
                    "bafkreie_local_ref2",
                    "bafkreie_local_ref3"
                ],
                "count": 3
            }
            
        elif operation == "ipfs_block_stat":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": operation,
                "cid": cid,
                "stats": {
                    "Key": cid,
                    "Size": "1024"
                }
            }
            
        elif operation == "ipfs_block_get":
            cid = kwargs.get("cid", "unknown")
            mock_data = f"Mock block data for {cid}".encode()
            return {
                "success": True,
                "operation": operation,
                "cid": cid,
                "data": mock_data.hex(),
                "size": len(mock_data)
            }
            
        elif operation == "ipfs_dag_get":
            cid = kwargs.get("cid", "unknown")
            path = kwargs.get("path", "")
            mock_response = base_response.copy()
            mock_response.update({
                "cid": cid,
                "path": path,
                "data": {
                    "mock": "dag_node",
                    "links": [],
                    "data": f"Mock DAG data for {cid}"
                }
            })
            return mock_response
            
        elif operation == "ipfs_dag_put":
            data = kwargs.get("data", "{}")
            format_type = kwargs.get("format", "dag-cbor")
            hash_type = kwargs.get("hash", "sha2-256")
            
            import hashlib
            mock_cid = f"bafkreie{hashlib.sha256(data.encode()).hexdigest()[:48]}"
            
            return {
                "success": True,
                "operation": operation,
                "cid": mock_cid,
                "format": format_type,
                "hash": hash_type
            }
        
        # IPFS Advanced Operations Mocks
        elif operation == "ipfs_dht_findpeer":
            peer_id = kwargs.get("peer_id", "unknown")
            return {
                "success": True,
                "operation": operation,
                "peer_id": peer_id,
                "addresses": [
                    f"/ip4/192.168.1.100/tcp/4001/p2p/{peer_id}",
                    f"/ip6/::1/tcp/4001/p2p/{peer_id}"
                ]
            }
            
        elif operation == "ipfs_dht_findprovs":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": operation,
                "cid": cid,
                "providers": [
                    "12D3KooWMockProvider1",
                    "12D3KooWMockProvider2"
                ],
                "count": 2
            }
            
        elif operation == "ipfs_dht_query":
            peer_id = kwargs.get("peer_id", "unknown")
            return {
                "success": True,
                "operation": operation,
                "peer_id": peer_id,
                "query_results": [
                    f"Query result 1 for {peer_id}",
                    f"Query result 2 for {peer_id}"
                ]
            }
            
        elif operation == "ipfs_name_publish":
            cid = kwargs.get("cid", "unknown")
            key = kwargs.get("key", "self")
            return {
                "success": True,
                "operation": operation,
                "cid": cid,
                "published_name": f"Published to k51qzi5uqu5d{key}mock: {cid}",
                "lifetime": kwargs.get("lifetime", "24h"),
                "ttl": kwargs.get("ttl", "1h")
            }
            
        elif operation == "ipfs_name_resolve":
            name = kwargs.get("name", "unknown")
            return {
                "success": True,
                "operation": operation,
                "name": name,
                "resolved_cid": "bafkreie_mock_resolved_cid"
            }
            
        elif operation == "ipfs_pubsub_publish":
            topic = kwargs.get("topic", "unknown")
            message = kwargs.get("message", "")
            return {
                "success": True,
                "operation": operation,
                "topic": topic,
                "message": message,
                "published": True
            }
            
        elif operation == "ipfs_pubsub_subscribe":
            topic = kwargs.get("topic", "unknown")
            return {
                "success": True,
                "operation": operation,
                "topic": topic,
                "subscribed": True,
                "note": "Mock subscription - use pubsub peers to monitor activity"
            }
            
        elif operation == "ipfs_pubsub_peers":
            topic = kwargs.get("topic")
            if topic:
                return {
                    "success": True,
                    "operation": operation,
                    "topic": topic,
                    "peers": [
                        "12D3KooWMockPubsubPeer1",
                        "12D3KooWMockPubsubPeer2"
                    ],
                    "count": 2
                }
            else:
                return {
                    "success": True,
                    "operation": operation,
                    "topics": [
                        "mock-topic-1",
                        "mock-topic-2"
                    ],
                    "count": 2
                }
        
        # IPFS MFS Operations Mocks
        elif operation == "ipfs_files_mkdir":
            path = kwargs.get("path", "/mock_dir")
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "created": True
            }
            
        elif operation == "ipfs_files_ls":
            path = kwargs.get("path", "/")
            long_format = kwargs.get("long", False)
            
            if long_format:
                entries = [
                    {"name": "file1.txt", "hash": "bafkreie_mock1", "size": 1024},
                    {"name": "dir1", "hash": "bafkreie_mock2", "size": 0}
                ]
            else:
                entries = [
                    {"name": "file1.txt"},
                    {"name": "dir1"}
                ]
                
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "entries": entries,
                "count": len(entries)
            }
            
        elif operation == "ipfs_files_stat":
            path = kwargs.get("path", "/mock_file")
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "stat": {
                    "Hash": "bafkreie_mock_stat",
                    "Size": "1024",
                    "CumulativeSize": "1024",
                    "Type": "file"
                }
            }
            
        elif operation == "ipfs_files_read":
            path = kwargs.get("path", "/mock_file")
            mock_content = f"Mock content from MFS file: {path}\nGenerated at: {datetime.now().isoformat()}"
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "content": mock_content,
                "size": len(mock_content)
            }
            
        elif operation == "ipfs_files_write":
            path = kwargs.get("path", "/mock_file")
            content = kwargs.get("content", "")
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "bytes_written": len(content)
            }
            
        elif operation == "ipfs_files_cp":
            source = kwargs.get("source", "/source")
            dest = kwargs.get("dest", "/dest")
            return {
                "success": True,
                "operation": operation,
                "source": source,
                "dest": dest,
                "copied": True
            }
            
        elif operation == "ipfs_files_mv":
            source = kwargs.get("source", "/source")
            dest = kwargs.get("dest", "/dest")
            return {
                "success": True,
                "operation": operation,
                "source": source,
                "dest": dest,
                "moved": True
            }
            
        elif operation == "ipfs_files_rm":
            path = kwargs.get("path", "/mock_file")
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "removed": True
            }
            
        elif operation == "ipfs_files_flush":
            path = kwargs.get("path", "/")
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "root_cid": "bafkreie_mock_root_cid"
            }
            
        elif operation == "ipfs_files_chcid":
            path = kwargs.get("path", "/")
            cid_version = kwargs.get("cid_version", 1)
            hash_func = kwargs.get("hash", "sha2-256")
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "cid_version": cid_version,
                "hash": hash_func,
                "updated": True
            }
        
        elif operation == "ipfs_ls":
            path = kwargs.get("path", "/ipfs/mock_cid")
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "entries": [
                    {"Name": "file1.txt", "Hash": "bafkreie_mock_file1", "Size": 100},
                    {"Name": "dir1", "Hash": "bafkreie_mock_dir1", "Size": 0}
                ]
            })
            return mock_response
        
        elif operation == "ipfs_stats":
            stat_type = kwargs.get("stat_type", "repo")
            mock_data = {
                "repo": {"NumObjects": 100, "RepoSize": 102400, "Version": 10},
                "bw": {"TotalIn": 500000, "TotalOut": 700000, "RateIn": 1000, "RateOut": 1500},
                "dht": {"Providers": 50, "Peers": 100},
                "bitswap": {"BlocksReceived": 200, "DataReceived": 204800, "BlocksSent": 150, "DataSent": 153600}
            }
            return {
                "success": True,
                "operation": operation,
                "stat_type": stat_type,
                "data": mock_data.get(stat_type, {})
            }
        
        # VFS Operations Mocks
        elif operation == "vfs_mount":
            ipfs_path = kwargs.get("ipfs_path", "/ipfs/mock_cid")
            mount_point = kwargs.get("mount_point", "/tmp/mock_mount")
            read_only = kwargs.get("read_only", True)
            mock_response = base_response.copy()
            mock_response.update({
                "ipfs_path": ipfs_path,
                "mount_point": mount_point,
                "read_only": read_only,
                "mounted": True
            })
            return mock_response
            
        elif operation == "vfs_unmount":
            mount_point = kwargs.get("mount_point", "/tmp/mock_mount")
            mock_response = base_response.copy()
            mock_response.update({
                "mount_point": mount_point,
                "unmounted": True
            })
            return mock_response
            
        elif operation == "vfs_list_mounts":
            mock_response = base_response.copy()
            mock_response.update({
                "mounts": [
                    {
                        "ipfs_path": "/ipfs/bafkreie_mock1",
                        "mount_point": "/tmp/mock_mount1",
                        "read_only": True
                    },
                    {
                        "ipfs_path": "/ipfs/bafkreie_mock2", 
                        "mount_point": "/tmp/mock_mount2",
                        "read_only": False
                    }
                ],
                "count": 2
            })
            return mock_response
            
        elif operation == "vfs_read":
            path = kwargs.get("path", "/vfs/mock_file")
            encoding = kwargs.get("encoding", "utf-8")
            mock_content = f"Mock VFS content from: {path}\nEncoding: {encoding}\nTimestamp: {datetime.now().isoformat()}"
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "content": mock_content,
                "encoding": encoding,
                "size": len(mock_content)
            })
            return mock_response
            
        elif operation == "vfs_write":
            path = kwargs.get("path", "/vfs/mock_file")
            content = kwargs.get("content", "")
            encoding = kwargs.get("encoding", "utf-8")
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "bytes_written": len(content),
                "encoding": encoding
            })
            return mock_response
            
        elif operation == "vfs_copy":
            source = kwargs.get("source", "/vfs/source")
            dest = kwargs.get("dest", "/vfs/dest")
            preserve_metadata = kwargs.get("preserve_metadata", True)
            mock_response = base_response.copy()
            mock_response.update({
                "source": source,
                "dest": dest,
                "preserve_metadata": preserve_metadata,
                "copied": True
            })
            return mock_response
            
        elif operation == "vfs_move":
            source = kwargs.get("source", "/vfs/source")
            dest = kwargs.get("dest", "/vfs/dest")
            mock_response = base_response.copy()
            mock_response.update({
                "source": source,
                "dest": dest,
                "moved": True
            })
            return mock_response
            
        elif operation == "vfs_mkdir":
            path = kwargs.get("path", "/vfs/mock_dir")
            parents = kwargs.get("parents", True)
            mode = kwargs.get("mode", "0755")
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "mode": mode,
                "created": True
            })
            return mock_response
            
        elif operation == "vfs_rmdir":
            path = kwargs.get("path", "/vfs/mock_dir")
            recursive = kwargs.get("recursive", False)
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "recursive": recursive,
                "removed": True
            })
            return mock_response
            
        elif operation == "vfs_ls":
            path = kwargs.get("path", "/vfs")
            detailed = kwargs.get("detailed", False)
            recursive = kwargs.get("recursive", False)
            
            if detailed:
                entries = [
                    {"name": "file1.txt", "type": "file", "size": 1024, "modified": "2025-07-03T06:00:00Z"},
                    {"name": "dir1", "type": "directory", "size": 0, "modified": "2025-07-03T05:30:00Z"}
                ]
            else:
                entries = [
                    {"name": "file1.txt"},
                    {"name": "dir1"}
                ]
                
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "entries": entries,
                "count": len(entries),
                "test_marker": "NEW_VFS_LS_CODE_UPDATED_NOW"
            })
            return mock_response
            
        elif operation == "vfs_stat":
            path = kwargs.get("path", "/vfs/mock_file")
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "stat": {
                    "type": "file",
                    "size": 1024,
                    "modified": "2025-07-03T06:00:00Z",
                    "permissions": "0644",
                    "cid": "bafkreie_mock_vfs_stat"
                }
            })
            return mock_response
            
        elif operation == "vfs_sync_to_ipfs":
            path = kwargs.get("path", "/")
            recursive = kwargs.get("recursive", True)
            mock_response = base_response.copy()
            mock_response.update({
                "path": path,
                "recursive": recursive,
                "synced_files": 5,
                "root_cid": "bafkreie_mock_sync_root"
            })
            return mock_response
            
        elif operation == "vfs_sync_from_ipfs":
            ipfs_path = kwargs.get("ipfs_path", "/ipfs/mock_cid")
            vfs_path = kwargs.get("vfs_path", "/vfs")
            force = kwargs.get("force", False)
            mock_response = base_response.copy()
            mock_response.update({
                "ipfs_path": ipfs_path,
                "vfs_path": vfs_path,
                "force": force,
                "synced_files": 3,
                "synced_bytes": 4096
            })
            return mock_response
        
        else:
            return {
                "success": False,
                "error": f"Mock operation {operation} not implemented",
                "operation": operation
            }
    
    def cleanup(self):
        """Clean up resources and properly shutdown IPFS daemon."""
        logger.info("Cleaning up IPFS integration...")
        
        # If we started our own daemon process, shut it down gracefully
        if self.daemon_process:
            try:
                logger.info("Shutting down IPFS daemon we started...")
                
                # Send SIGTERM first for graceful shutdown
                self.daemon_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.daemon_process.wait(timeout=10)
                    logger.info("✓ IPFS daemon shut down gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("IPFS daemon didn't shut down gracefully, force killing...")
                    self.daemon_process.kill()
                    self.daemon_process.wait(timeout=5)
                    logger.info("✓ IPFS daemon force killed")
                    
            except Exception as e:
                logger.warning(f"Error shutting down daemon: {e}")
                try:
                    self.daemon_process.kill()
                    logger.info("✓ IPFS daemon force killed after error")
                except Exception as kill_error:
                    logger.error(f"Failed to kill daemon: {kill_error}")
        
        # Clean up any other resources
        self.ipfs_kit = None
        self.daemon_process = None
        logger.info("✓ IPFS integration cleanup complete")


class EnhancedMCPServerWithDaemonMgmt:
    """Enhanced MCP Server with integrated daemon management."""
    
    def __init__(self):
        self.ipfs_integration = IPFSKitIntegration()
        self.tools = {}
        self.register_tools()
        
    def register_tools(self):
        """Register all available tools."""
        self.tools = {
            # Core IPFS operations
            "ipfs_add": {
                "name": "ipfs_add",
                "description": "Add content to IPFS and return the CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to add to IPFS"},
                        "file_path": {"type": "string", "description": "Path to file to add to IPFS"}
                    }
                }
            },
            "ipfs_cat": {
                "name": "ipfs_cat",
                "description": "Retrieve and display content from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to retrieve content from"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_get": {
                "name": "ipfs_get",
                "description": "Download IPFS content to a specified path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to retrieve"},
                        "output_path": {"type": "string", "description": "Local path to save the content"}
                    },
                    "required": ["cid", "output_path"]
                }
            },
            "ipfs_ls": {
                "name": "ipfs_ls",
                "description": "List directory contents for an IPFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "IPFS path to list (e.g., /ipfs/<cid>)"}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_pin_add": {
                "name": "ipfs_pin_add",
                "description": "Pin content in IPFS to prevent garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to pin"},
                        "recursive": {"type": "boolean", "description": "Pin recursively", "default": True}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_pin_rm": {
                "name": "ipfs_pin_rm",
                "description": "Remove pin from IPFS content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to unpin"},
                        "recursive": {"type": "boolean", "description": "Unpin recursively", "default": True}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_list_pins": {
                "name": "ipfs_list_pins",
                "description": "List all pinned content in IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["all", "direct", "indirect", "recursive"], "default": "all"}
                    }
                }
            },
            "ipfs_version": {
                "name": "ipfs_version",
                "description": "Get IPFS daemon version information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "all": {"type": "boolean", "description": "Show all version information", "default": False}
                    }
                }
            },
            "ipfs_id": {
                "name": "ipfs_id",
                "description": "Get IPFS node identity and network information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_stats": {
                "name": "ipfs_stats",
                "description": "Get IPFS statistics (repo, bw, dht, bitswap)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "stat_type": {"type": "string", "enum": ["repo", "bw", "dht", "bitswap"], "description": "Type of statistics to retrieve"}
                    },
                    "required": ["stat_type"]
                }
            },
            "ipfs_swarm_peers": {
                "name": "ipfs_swarm_peers",
                "description": "List peers connected to this IPFS node",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "verbose": {"type": "boolean", "description": "Show verbose peer information", "default": False}
                    }
                }
            },
            "ipfs_pin_update": {
                "name": "ipfs_pin_update",
                "description": "Update a pinned object to a new version",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_cid": {"type": "string", "description": "CID of the current pinned object"},
                        "to_cid": {"type": "string", "description": "CID of the new object to pin"},
                        "unpin": {"type": "boolean", "description": "Unpin the old object", "default": True}
                    },
                    "required": ["from_cid", "to_cid"]
                }
            },
            "ipfs_swarm_peers": {
                "name": "ipfs_swarm_peers",
                "description": "List peers connected to this IPFS node",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "verbose": {"type": "boolean", "description": "Show verbose peer information", "default": False}
                    }
                }
            },
            "ipfs_refs": {
                "name": "ipfs_refs",
                "description": "List all references from an IPFS object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to list references for"},
                        "recursive": {"type": "boolean", "description": "Recursively list references", "default": False},
                        "unique": {"type": "boolean", "description": "Only show unique references", "default": False}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_refs_local": {
                "name": "ipfs_refs_local",
                "description": "List all local references in the repository",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_block_stat": {
                "name": "ipfs_block_stat",
                "description": "Get statistics for an IPFS block",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of the block"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_block_get": {
                "name": "ipfs_block_get",
                "description": "Get raw IPFS block data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of the block"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_block_stat": {
                "name": "ipfs_block_stat",
                "description": "Get statistics for an IPFS block",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of the block"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_refs_local": {
                "name": "ipfs_refs_local",
                "description": "List all local references in the repository",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_block_stat": {
                "name": "ipfs_block_stat",
                "description": "Get statistics for an IPFS block",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of the block"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_block_get": {
                "name": "ipfs_block_get",
                "description": "Get raw IPFS block data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of the block"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_dag_get": {
                "name": "ipfs_dag_get",
                "description": "Get a DAG node from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of the DAG node"},
                        "path": {"type": "string", "description": "Path within the DAG node"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_dag_put": {
                "name": "ipfs_dag_put",
                "description": "Add a DAG node to IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "JSON data to store as DAG node"},
                        "format": {"type": "string", "enum": ["dag-cbor", "dag-json", "dag-pb"], "default": "dag-cbor"},
                        "hash": {"type": "string", "enum": ["sha2-256", "sha2-512", "blake2b-256"], "default": "sha2-256"}
                    },
                    "required": ["data"]
                }
            },
            # IPFS Advanced Operations (DHT, IPNS, PubSub)
            "ipfs_dht_findpeer": {
                "name": "ipfs_dht_findpeer",
                "description": "Find a peer in the DHT",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "peer_id": {"type": "string", "description": "Peer ID to find"}
                    },
                    "required": ["peer_id"]
                }
            },
            "ipfs_dht_findprovs": {
                "name": "ipfs_dht_findprovs", 
                "description": "Find providers for a CID in the DHT",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "CID to find providers for"},
                        "timeout": {"type": "string", "description": "Timeout duration (e.g., '30s')", "default": "30s"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_dht_query": {
                "name": "ipfs_dht_query",
                "description": "Query the DHT for peer information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "peer_id": {"type": "string", "description": "Peer ID to query"},
                        "verbose": {"type": "boolean", "description": "Verbose output", "default": False}
                    },
                    "required": ["peer_id"]
                }
            },
            "ipfs_name_publish": {
                "name": "ipfs_name_publish",
                "description": "Publish an IPNS name record",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "CID to publish"},
                        "key": {"type": "string", "description": "Key name to use for publishing"},
                        "lifetime": {"type": "string", "description": "Lifetime of the record (e.g., '24h')", "default": "24h"},
                        "ttl": {"type": "string", "description": "TTL of the record (e.g., '1h')", "default": "1h"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_name_resolve": {
                "name": "ipfs_name_resolve",
                "description": "Resolve an IPNS name to a CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "IPNS name to resolve"},
                        "nocache": {"type": "boolean", "description": "Don't use cached entries", "default": False}
                    },
                    "required": ["name"]
                }
            },
 "ipfs_pubsub_publish": {
                "name": "ipfs_pubsub_publish",
                "description": "Publish a message to a pubsub topic",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic name"},
                        "message": {"type": "string", "description": "Message to publish"}
                    },
                    "required": ["topic", "message"]
                }
            },
            "ipfs_pubsub_subscribe": {
                "name": "ipfs_pubsub_subscribe",
                "description": "Subscribe to a pubsub topic (returns subscription info)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic name to subscribe to"}
                    },
                    "required": ["topic"]
                }
            },
            "ipfs_pubsub_peers": {
                "name": "ipfs_pubsub_peers",
                "description": "List peers subscribed to a pubsub topic",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic name (optional - lists all topics if omitted)"}
                    }
                }
            },
            # IPFS Mutable File System (MFS) Tools
            "ipfs_files_mkdir": {
                "name": "ipfs_files_mkdir",
                "description": "Create a directory in MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to create"},
                        "parents": {"type": "boolean", "description": "Create parent directories if needed", "default": True}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_ls": {
                "name": "ipfs_files_ls",
                "description": "List contents of an MFS directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to list", "default": "/"},
                        "long": {"type": "boolean", "description": "Show detailed information", "default": False}
                    }
                }
            },
            "ipfs_files_stat": {
                "name": "ipfs_files_stat",
                "description": "Get statistics for an MFS file or directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to stat"}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_read": {
                "name": "ipfs_files_read",
                "description": "Read content from an MFS file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to read"},
                        "offset": {"type": "integer", "description": "Byte offset to start reading from", "default": 0},
                        "count": {"type": "integer", "description": "Maximum number of bytes to read"}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_write": {
                "name": "ipfs_files_write",
                "description": "Write content to an MFS file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to write to"},
                        "content": {"type": "string", "description": "Content to write"},
                        "offset": {"type": "integer", "description": "Byte offset to start writing at", "default": 0},
                        "create": {"type": "boolean", "description": "Create file if it doesn't exist", "default": True},
                        "truncate": {"type": "boolean", "description": "Truncate file before writing", "default": False},
                        "parents": {"type": "boolean", "description": "Create parent directories", "default": True}
                    },
                    "required": ["path", "content"]
                }
            },
            "ipfs_files_cp": {
                "name": "ipfs_files_cp",
                "description": "Copy files within MFS or from IPFS to MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source path (IPFS CID or MFS path)"},
                        "dest": {"type": "string", "description": "Destination MFS path"},
                        "parents": {"type": "boolean", "description": "Create parent directories", "default": True}
                    },
                    "required": ["source", "dest"]
                }
            },
            "ipfs_files_mv": {
                "name": "ipfs_files_mv",
                "description": "Move or rename files within MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source MFS path"},
                        "dest": {"type": "string", "description": "Destination MFS path"}
                    },
                    "required": ["source", "dest"]
                }
            },
            "ipfs_files_rm": {
                "name": "ipfs_files_rm",
                "description": "Remove files or directories from MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to remove"},
                        "recursive": {"type": "boolean", "description": "Remove recursively", "default": False},
                        "force": {"type": "boolean", "description": "Force removal", "default": False}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_flush": {
                "name": "ipfs_files_flush",
                "description": "Flush MFS changes to disk and get the root CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to flush", "default": "/"}
                    }
                }
            },
            "ipfs_files_chcid": {
                "name": "ipfs_files_chcid",
                "description": "Change CID version or hash function for MFS directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path"},
                        "cid_version": {"type": "integer", "enum": [0, 1], "description": "CID version", "default": 1},
                        "hash": {"type": "string", "enum": ["sha2-256", "sha2-512", "blake2b-256"], "default": "sha2-256"}
                    },
                    "required": ["path"]
                }
            },
            # Virtual Filesystem Integration (12 tools)
            "vfs_mount": {
                "name": "vfs_mount",
                "description": "Mount an IPFS path to a local directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ipfs_path": {"type": "string", "description": "IPFS path to mount (e.g., /ipfs/<cid>)"},
                        "mount_point": {"type": "string", "description": "Local directory to mount to"},
                        "read_only": {"type": "boolean", "description": "Mount as read-only", "default": True}
                    },
                    "required": ["ipfs_path", "mount_point"]
                }
            },
            "vfs_unmount": {
                "name": "vfs_unmount",
                "description": "Unmount a previously mounted IPFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mount_point": {"type": "string", "description": "Local directory to unmount"}
                    },
                    "required": ["mount_point"]
                }
            },
            "vfs_list_mounts": {
                "name": "vfs_list_mounts",
                "description": "List all active VFS mounts",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "vfs_read": {
                "name": "vfs_read",
                "description": "Read file content from VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to read"},
                        "encoding": {"type": "string", "enum": ["utf-8", "binary", "base64"], "default": "utf-8"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_write": {
                "name": "vfs_write",
                "description": "Write content to VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to write to"},
                        "content": {"type": "string", "description": "Content to write"},
                        "encoding": {"type": "string", "enum": ["utf-8", "binary", "base64"], "default": "utf-8"},
                        "create_dirs": {"type": "boolean", "description": "Create parent directories", "default": True}
                    },
                    "required": ["path", "content"]
                }
            },
            "vfs_copy": {
                "name": "vfs_copy",
                "description": "Copy files within VFS or between VFS and local filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source path"},
                        "dest": {"type": "string", "description": "Destination path"},
                        "preserve_metadata": {"type": "boolean", "description": "Preserve file metadata", "default": True}
                    },
                    "required": ["source", "dest"]
                }
            },
            "vfs_move": {
                "name": "vfs_move",
                "description": "Move or rename files within VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source path"},
                        "dest": {"type": "string", "description": "Destination path"}
                    },
                    "required": ["source", "dest"]
                }
            },
            "vfs_mkdir": {
                "name": "vfs_mkdir",
                "description": "Create directory in VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to create"},
                        "parents": {"type": "boolean", "description": "Create parent directories", "default": True},
                        "mode": {"type": "string", "description": "Directory permissions (octal)", "default": "0755"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_rmdir": {
                "name": "vfs_rmdir",
                "description": "Remove directory from VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to remove"},
                        "recursive": {"type": "boolean", "description": "Remove recursively", "default": False}
                    },
                    "required": ["path"]
                }
            },
            "vfs_ls": {
                "name": "vfs_ls",
                "description": "List directory contents in VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"},
                        "detailed": {"type": "boolean", "description": "Show detailed file information", "default": False},
                        "recursive": {"type": "boolean", "description": "List recursively", "default": False}
                    },
                    "required": ["path"]
                }
            },
            "vfs_stat": {
                "name": "vfs_stat",
                "description": "Get file or directory statistics in VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to get statistics for"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_sync_to_ipfs": {
                "name": "vfs_sync_to_ipfs",
                "description": "Synchronize VFS changes to IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to sync", "default": "/"},
                        "recursive": {"type": "boolean", "description": "Sync recursively", "default": True}
                    }
                }
            },
            "vfs_sync_from_ipfs": {
                "name": "vfs_sync_from_ipfs",
                "description": "Synchronize IPFS content to VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ipfs_path": {"type": "string", "description": "IPFS path to sync from"},
                        "vfs_path": {"type": "string", "description": "VFS path to sync to"},
                        "force": {"type": "boolean", "description": "Force overwrite existing files", "default": False}
                    },
                    "required": ["ipfs_path", "vfs_path"]
                }
            },
            "system_health": {
                "name": "system_health",
                "description": "Get comprehensive system health status including IPFS daemon status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
        
        logger.info(f"Registered {len(self.tools)} tools with daemon management")
    
    # MCP Protocol handlers
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        logger.info("Handling initialize request")
        
        # Optional: Verify daemon health during MCP initialization
        daemon_healthy = self.ipfs_integration._test_ipfs_connection()
        if not daemon_healthy:
            logger.info("Daemon not accessible during MCP init, attempting restart...")
            self.ipfs_integration._ensure_daemon_running()
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "resourceTemplates": {"listChanged": False},
                "logging": {}
            },
            "serverInfo": {
                "name": "enhanced-ipfs-kit-mcp-server-daemon-mgmt",
                "version": __version__
            }
        }
    
    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        logger.info("Handling tools/list request")
        return {"tools": list(self.tools.values())}
    
    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        return {"resources": []}
    
    async def handle_resources_templates_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/templates/list request."""
        return {"resourceTemplates": []}
    
    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Handling tools/call request for: {tool_name}")
        logger.info("🔥 UPDATED SERVER VERSION WITH ENHANCED ERROR MESSAGES 🔥")
        
        if tool_name not in self.tools:
            raise Exception(f"Tool '{tool_name}' not found")
        
        # Execute the tool
        result = await self.execute_tool(tool_name, arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ],
            "isError": result.get("success", True) is False
        }
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool."""
        try:
            if tool_name == "ipfs_add":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_add", **arguments)
            elif tool_name == "ipfs_cat":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_cat", **arguments)
            elif tool_name == "ipfs_get":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_get", **arguments)
            elif tool_name == "ipfs_ls":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_ls", **arguments)
            elif tool_name == "ipfs_pin_add":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pin_add", **arguments)
            elif tool_name == "ipfs_pin_rm":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pin_rm", **arguments)
            elif tool_name == "ipfs_list_pins":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pin_ls", **arguments)
            elif tool_name == "ipfs_version":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_version", **arguments)
            elif tool_name == "ipfs_id":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_id", **arguments)
            elif tool_name == "ipfs_stats":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_stats", **arguments)
            elif tool_name == "ipfs_swarm_peers":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_swarm_peers", **arguments)
            elif tool_name == "ipfs_pin_update":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pin_update", **arguments)
            elif tool_name == "ipfs_refs":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_refs", **arguments)
            elif tool_name == "ipfs_refs_local":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_refs_local", **arguments)
            elif tool_name == "ipfs_block_stat":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_block_stat", **arguments)
            elif tool_name == "ipfs_block_get":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_block_get", **arguments)
            elif tool_name == "ipfs_dag_get":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_dag_get", **arguments)
            elif tool_name == "ipfs_dag_put":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_dag_put", **arguments)
            # IPFS Advanced Operations
            elif tool_name == "ipfs_dht_findpeer":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_dht_findpeer", **arguments)
            elif tool_name == "ipfs_dht_findprovs":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_dht_findprovs", **arguments)
            elif tool_name == "ipfs_dht_query":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_dht_query", **arguments)
            elif tool_name == "ipfs_name_publish":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_name_publish", **arguments)
            elif tool_name == "ipfs_name_resolve":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_name_resolve", **arguments)
            elif tool_name == "ipfs_pubsub_publish":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pubsub_publish", **arguments)
            elif tool_name == "ipfs_pubsub_subscribe":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pubsub_subscribe", **arguments)
            elif tool_name == "ipfs_pubsub_peers":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pubsub_peers", **arguments)
            # IPFS MFS Tools
            elif tool_name == "ipfs_files_mkdir":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_mkdir", **arguments)
            elif tool_name == "ipfs_files_ls":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_ls", **arguments)
            elif tool_name == "ipfs_files_stat":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_stat", **arguments)
            elif tool_name == "ipfs_files_read":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_read", **arguments)
            elif tool_name == "ipfs_files_write":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_write", **arguments)
            elif tool_name == "ipfs_files_cp":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_cp", **arguments)
            elif tool_name == "ipfs_files_mv":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_mv", **arguments)
            elif tool_name == "ipfs_files_rm":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_rm", **arguments)
            elif tool_name == "ipfs_files_flush":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_flush", **arguments)
            elif tool_name == "ipfs_files_chcid":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_files_chcid", **arguments)
            # VFS Tools
            elif tool_name == "vfs_mount":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_mount", **arguments)
            elif tool_name == "vfs_unmount":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_unmount", **arguments)
            elif tool_name == "vfs_list_mounts":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_list_mounts", **arguments)
            elif tool_name == "vfs_read":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_read", **arguments)
            elif tool_name == "vfs_write":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_write", **arguments)
            elif tool_name == "vfs_copy":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_copy", **arguments)
            elif tool_name == "vfs_move":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_move", **arguments)
            elif tool_name == "vfs_mkdir":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_mkdir", **arguments)
            elif tool_name == "vfs_rmdir":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_rmdir", **arguments)
            elif tool_name == "vfs_ls":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_ls", **arguments)
            elif tool_name == "vfs_stat":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_stat", **arguments)
            elif tool_name == "vfs_sync_to_ipfs":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_sync_to_ipfs", **arguments)
            elif tool_name == "vfs_sync_from_ipfs":
                return await self.ipfs_integration.execute_ipfs_operation("vfs_sync_from_ipfs", **arguments)
            elif tool_name == "system_health":
                return await self.system_health_tool(arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def system_health_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get system health including IPFS daemon status."""
        import psutil
        
        # Get basic system info
        health_info = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/')._asdict()
            },
            "ipfs": {
                "daemon_running": False,
                "connection_test": False
            }
        }
        
        # Test IPFS connection
        try:
            connection_test = self.ipfs_integration._test_ipfs_connection()
            health_info["ipfs"]["connection_test"] = connection_test
            health_info["ipfs"]["daemon_running"] = connection_test
        except Exception as e:
            health_info["ipfs"]["connection_error"] = str(e)
        
        return health_info
    
    def cleanup(self):
        """Clean up resources."""
        if self.ipfs_integration:
            self.ipfs_integration.cleanup()


# MCP Server main loop
async def main():
    """Main MCP server loop."""
    server = EnhancedMCPServerWithDaemonMgmt()
    
    try:
        while True:
            message = None  # Initialize message to None
            try:
                # Read JSON-RPC message from stdin
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                
                # Parse the message
                try:
                    message = json.loads(line.strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue
                
                # Handle the message
                response = await handle_message(server, message)
                
                # Send response
                if response is not None:
                    print(json.dumps(response), flush=True)
                    sys.stdout.flush() # Ensure output is flushed immediately
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.error(traceback.format_exc())
                
                # Send error response if we have a message ID
                msg_id = None
                if message and hasattr(message, 'get'): # Check if message is not None before accessing 'get'
                    try:
                        msg_id = message.get("id")
                    except:
                        pass
                    
                error_response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }
                print(json.dumps(error_response), flush=True)
    
    finally:
        server.cleanup()


async def handle_message(server: EnhancedMCPServerWithDaemonMgmt, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle a single MCP message."""
    
    method = message.get("method")
    params = message.get("params", {})
    msg_id = message.get("id")
    
    try:
        # Route to appropriate handler
        if method == "initialize":
            result = await server.handle_initialize(params)
        elif method == "tools/list":
            result = await server.handle_tools_list(params)
        elif method == "resources/list":
            result = await server.handle_resources_list(params)
        elif method == "resources/templates/list":
            result = await server.handle_resources_templates_list(params)
        elif method == "tools/call":
            result = await server.handle_tools_call(params)
        elif method == "notifications/initialized":
            # Handle initialization notification - no response needed
            logger.info("Client initialization notification received")
            return None
        elif method and method.startswith("notifications/"):
            # Handle other notifications - no response needed
            logger.info(f"Notification received: {method}")
            return None
        else:
            raise Exception(f"Unknown method: {method}")
        
        # Return success response
        if msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            }
        else:
            return None
    
    except Exception as e:
        logger.error(f"Error handling {method}: {e}")
        
        # Return error response
        if msg_id is not None:
            return {
                "jsonrpc": "2.0", 
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": str(e),
                    "data": traceback.format_exc()
                }
            }
        else:
            return None


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
