#!/usr/bin/env python3
"""
Enhanced Daemon Manager for IPFS Kit

This module provides improved daemon management with:
- Repository version compatibility checking
- Automatic repository migration/reset
- Better error handling and recovery
- Dependency-aware daemon startup
- Health checks and monitoring
"""

import os
import sys
import time
import logging
import subprocess
import shutil
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Configure logger
logger = logging.getLogger(__name__)

class EnhancedDaemonManager:
    """Enhanced daemon manager with version compatibility and dependency management."""
    
    def __init__(self, ipfs_kit_instance=None):
        """Initialize the enhanced daemon manager.
        
        Args:
            ipfs_kit_instance: Reference to the main IPFS Kit instance
        """
        self.ipfs_kit = ipfs_kit_instance
        self.daemon_status = {}
        self.startup_order = [
            'ipfs',
            'lotus', 
            'ipfs_cluster_service',
            'lassie'
        ]
        
    def check_and_fix_ipfs_version_mismatch(self) -> Dict[str, Any]:
        """Check for IPFS version mismatch and attempt to fix it.
        
        Returns:
            Dict with operation results
        """
        result = {
            "success": False,
            "action_taken": None,
            "error": None,
            "details": {}
        }
        
        try:
            # Get IPFS path
            ipfs_path = getattr(self.ipfs_kit, 'ipfs_path', os.path.expanduser("~/.ipfs"))
            
            # Check if repository exists
            if not os.path.exists(ipfs_path):
                result["success"] = True
                result["action_taken"] = "no_repo_exists"
                result["details"]["message"] = "No IPFS repository exists, no version mismatch possible"
                return result
            
            # Check repository version
            version_file = os.path.join(ipfs_path, "version")
            if not os.path.exists(version_file):
                result["success"] = True
                result["action_taken"] = "no_version_file"
                result["details"]["message"] = "No version file found, assuming compatible"
                return result
            
            # Read repository version
            with open(version_file, 'r') as f:
                repo_version = f.read().strip()
            
            # Get installed IPFS version
            installed_version = self._get_installed_ipfs_version()
            if not installed_version:
                result["error"] = "Could not determine installed IPFS version"
                return result
            
            # Get expected repository version for installed IPFS
            expected_repo_version = self._get_expected_repo_version(installed_version)
            
            result["details"]["repo_version"] = repo_version
            result["details"]["installed_version"] = installed_version
            result["details"]["expected_repo_version"] = expected_repo_version
            
            if repo_version == expected_repo_version:
                result["success"] = True
                result["action_taken"] = "versions_compatible"
                result["details"]["message"] = "Repository and IPFS versions are compatible"
                return result
            
            # Version mismatch detected - attempt to fix
            logger.warning(f"IPFS version mismatch detected: repo={repo_version}, expected={expected_repo_version}")
            
            # Try to migrate or reset repository
            migration_result = self._migrate_or_reset_repository(ipfs_path)
            if migration_result["success"]:
                result["success"] = True
                result["action_taken"] = "repository_reset"
                result["details"]["migration_result"] = migration_result
                result["details"]["message"] = "Repository successfully reset due to version mismatch"
            else:
                result["error"] = f"Failed to reset repository: {migration_result.get('error', 'Unknown error')}"
                result["details"]["migration_result"] = migration_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking IPFS version compatibility: {e}")
            result["error"] = str(e)
            return result
    
    def _get_installed_ipfs_version(self) -> Optional[str]:
        """Get the currently installed IPFS version."""
        try:
            # Try to get version from IPFS Kit's install module
            if self.ipfs_kit and hasattr(self.ipfs_kit, 'install_ipfs_obj'):
                version = self.ipfs_kit.install_ipfs_obj.get_installed_kubo_version()
                if version:
                    return version
            
            # Fallback to direct command execution
            try:
                result = subprocess.run(['ipfs', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    # Parse version from output like "ipfs version 0.26.0"
                    parts = result.stdout.strip().split()
                    if len(parts) >= 3:
                        return f"v{parts[2]}"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting installed IPFS version: {e}")
            return None
    
    def _get_expected_repo_version(self, ipfs_version: str) -> str:
        """Get the expected repository version for a given IPFS version."""
        # Map IPFS versions to repository versions
        version_map = {
            "v0.35.0": "16", "v0.34.0": "16", "v0.33.0": "16", "v0.32.0": "16",
            "v0.31.0": "16", "v0.30.0": "16", "v0.29.0": "15", "v0.28.0": "15",
            "v0.27.0": "15", "v0.26.0": "15", "v0.25.0": "15", "v0.24.0": "15",
            "v0.23.0": "15", "v0.22.0": "15", "v0.21.0": "15", "v0.20.0": "15"
        }
        
        return version_map.get(ipfs_version, "16")  # Default to latest
    
    def _migrate_or_reset_repository(self, ipfs_path: str) -> Dict[str, Any]:
        """Migrate or reset the IPFS repository when there's a version mismatch."""
        result = {"success": False, "error": None, "backup_path": None}
        
        try:
            logger.info(f"Attempting to resolve IPFS repository version mismatch...")
            
            # Create backup of existing repository
            backup_path = f"{ipfs_path}.backup.{int(time.time())}"
            if os.path.exists(ipfs_path):
                logger.info(f"Backing up existing repository to {backup_path}")
                shutil.move(ipfs_path, backup_path)
                result["backup_path"] = backup_path
            
            # Create new repository directory
            os.makedirs(ipfs_path, exist_ok=True)
            
            logger.info(f"Repository reset completed. Old repository backed up to {backup_path}")
            result["success"] = True
            return result
            
        except Exception as e:
            logger.error(f"Error during repository migration/reset: {e}")
            result["error"] = str(e)
            return result
    
    def start_daemons_with_dependencies(self, role: str = "master") -> Dict[str, Any]:
        """Start daemons in the correct order with dependency checking.
        
        Args:
            role: The role for daemon startup (master, worker, etc.)
            
        Returns:
            Dict with startup results for each daemon
        """
        results = {
            "overall_success": False,
            "daemons": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # First, check and fix IPFS version mismatch
            version_check = self.check_and_fix_ipfs_version_mismatch()
            results["version_check"] = version_check
            
            if not version_check["success"] and version_check.get("error"):
                results["errors"].append(f"IPFS version check failed: {version_check['error']}")
                # Continue anyway, but note the issue
            
            # Start daemons in dependency order
            for daemon_name in self.startup_order:
                daemon_result = self._start_single_daemon(daemon_name, role)
                results["daemons"][daemon_name] = daemon_result
                
                if not daemon_result.get("success", False):
                    error_msg = f"Failed to start {daemon_name}: {daemon_result.get('error', 'Unknown error')}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
                    # For critical daemons, we might want to stop here
                    if daemon_name == "ipfs":
                        results["warnings"].append("IPFS daemon failed to start - other services may not work properly")
                else:
                    logger.info(f"Successfully started {daemon_name}")
            
            # Check overall success
            successful_daemons = sum(1 for result in results["daemons"].values() 
                                   if result.get("success", False))
            total_daemons = len(results["daemons"])
            
            results["overall_success"] = successful_daemons > 0  # At least one daemon started
            results["success_rate"] = f"{successful_daemons}/{total_daemons}"
            
            return results
            
        except Exception as e:
            logger.error(f"Error during daemon startup: {e}")
            results["errors"].append(str(e))
            return results
    
    def _start_single_daemon(self, daemon_name: str, role: str) -> Dict[str, Any]:
        """Start a single daemon with proper error handling.
        
        Args:
            daemon_name: Name of the daemon to start
            role: Role for daemon startup
            
        Returns:
            Dict with startup result
        """
        result = {"success": False, "error": None, "status": None}
        
        try:
            if daemon_name == "ipfs":
                result = self._start_ipfs_daemon()
            elif daemon_name == "lotus":
                result = self._start_lotus_daemon()
            elif daemon_name == "ipfs_cluster_service":
                result = self._start_ipfs_cluster_service()
            elif daemon_name == "lassie":
                result = self._start_lassie_daemon()
            else:
                result["error"] = f"Unknown daemon: {daemon_name}"
            
            return result
            
        except Exception as e:
            logger.error(f"Error starting {daemon_name}: {e}")
            result["error"] = str(e)
            return result
    
    def _start_ipfs_daemon(self) -> Dict[str, Any]:
        """Start the IPFS daemon with enhanced error handling."""
        result = {"success": False, "error": None, "status": None}
        
        try:
            # Check if IPFS is already running
            if self._is_daemon_running("ipfs"):
                result["success"] = True
                result["status"] = "already_running"
                return result
            
            # Ensure IPFS is configured
            if self.ipfs_kit and hasattr(self.ipfs_kit, 'install_ipfs_obj'):
                config_result = self.ipfs_kit.install_ipfs_obj.ensure_daemon_configured()
                if not config_result:
                    result["error"] = "Failed to ensure IPFS configuration"
                    return result
            
            # Try to start IPFS daemon
            try:
                # Use subprocess to start daemon in background
                process = subprocess.Popen(['ipfs', 'daemon'], 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE)
                
                # Wait a moment to see if it starts successfully
                time.sleep(3)
                
                if process.poll() is None:  # Still running
                    result["success"] = True
                    result["status"] = "started"
                    result["pid"] = process.pid
                else:
                    # Process exited, get error
                    stdout, stderr = process.communicate()
                    result["error"] = f"IPFS daemon exited: {stderr.decode()}"
                    
            except FileNotFoundError:
                result["error"] = "IPFS binary not found in PATH"
            except Exception as e:
                result["error"] = f"Failed to start IPFS daemon: {str(e)}"
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def _start_lotus_daemon(self) -> Dict[str, Any]:
        """Start the Lotus daemon with enhanced error handling."""
        result = {"success": False, "error": None, "status": None}
        
        try:
            # Check if we have lotus daemon manager
            if self.ipfs_kit and hasattr(self.ipfs_kit, 'lotus_daemon'):
                lotus_result = self.ipfs_kit.lotus_daemon.daemon_start()
                result["success"] = lotus_result.get("success", False)
                result["status"] = lotus_result.get("status", "unknown")
                if not result["success"]:
                    result["error"] = lotus_result.get("error", "Unknown lotus error")
            else:
                result["success"] = True
                result["status"] = "not_available"
                result["error"] = "Lotus daemon manager not available"
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def _start_ipfs_cluster_service(self) -> Dict[str, Any]:
        """Start the IPFS cluster service with enhanced error handling and lockfile management."""
        result = {"success": False, "error": None, "status": None}
        
        try:
            # Check if IPFS is running first (dependency)
            if not self._is_daemon_running("ipfs"):
                result["error"] = "IPFS daemon must be running before starting cluster service"
                return result
            
            # Handle lockfile cleanup and daemon lifecycle management
            lockfile_result = self._manage_cluster_lockfile_and_daemon()
            if not lockfile_result["success"]:
                logger.warning(f"Lockfile management issue: {lockfile_result['error']}")
            
            # Check if we have cluster service manager
            if self.ipfs_kit and hasattr(self.ipfs_kit, 'ipfs_cluster_service'):
                cluster_result = self.ipfs_kit.ipfs_cluster_service.daemon_start()
                result["success"] = cluster_result.get("success", False)
                result["status"] = cluster_result.get("status", "unknown")
                if not result["success"]:
                    result["error"] = cluster_result.get("error", "Unknown cluster error")
            else:
                result["success"] = True
                result["status"] = "not_available"
                result["error"] = "IPFS cluster service manager not available"
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def _start_lassie_daemon(self) -> Dict[str, Any]:
        """Start the Lassie daemon with enhanced error handling."""
        result = {"success": False, "error": None, "status": None}
        
        try:
            # Check if we have lassie manager
            if self.ipfs_kit and hasattr(self.ipfs_kit, 'lassie_kit'):
                # Lassie typically doesn't need a persistent daemon
                result["success"] = True
                result["status"] = "service_available"
            else:
                result["success"] = True
                result["status"] = "not_available"
                result["error"] = "Lassie kit not available"
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def _is_daemon_running(self, daemon_name: str) -> bool:
        """Check if a daemon is currently running."""
        try:
            if daemon_name == "ipfs":
                # Try to connect to IPFS API
                result = subprocess.run(['ipfs', 'id'], 
                                      capture_output=True, timeout=5)
                return result.returncode == 0
            elif daemon_name == "lotus":
                # Check if lotus daemon is running
                if self.ipfs_kit and hasattr(self.ipfs_kit, 'lotus_daemon'):
                    status = self.ipfs_kit.lotus_daemon.daemon_status()
                    return status.get("process_running", False)
            # Add other daemon checks as needed
            
            return False
            
        except Exception:
            return False
    
    def get_daemon_status_summary(self) -> Dict[str, Any]:
        """Get a summary of all daemon statuses."""
        summary = {
            "timestamp": time.time(),
            "daemons": {},
            "overall_health": "unknown"
        }
        
        running_count = 0
        total_count = 0
        
        for daemon_name in self.startup_order:
            total_count += 1
            is_running = self._is_daemon_running(daemon_name)
            summary["daemons"][daemon_name] = {
                "running": is_running,
                "status": "running" if is_running else "stopped"
            }
            if is_running:
                running_count += 1
        
        # Determine overall health
        if running_count == total_count:
            summary["overall_health"] = "healthy"
        elif running_count > 0:
            summary["overall_health"] = "partial"
        else:
            summary["overall_health"] = "unhealthy"
        
        summary["running_count"] = running_count
        summary["total_count"] = total_count
        
        return summary
    
    def stop_all_daemons(self) -> Dict[str, Any]:
        """Stop all managed daemons."""
        results = {
            "overall_success": True,
            "daemons": {},
            "errors": []
        }
        
        # Stop in reverse order
        for daemon_name in reversed(self.startup_order):
            try:
                stop_result = self._stop_single_daemon(daemon_name)
                results["daemons"][daemon_name] = stop_result
                
                if not stop_result.get("success", False):
                    results["overall_success"] = False
                    results["errors"].append(f"Failed to stop {daemon_name}")
                    
            except Exception as e:
                results["overall_success"] = False
                results["errors"].append(f"Error stopping {daemon_name}: {str(e)}")
        
        return results
    
    def _stop_single_daemon(self, daemon_name: str) -> Dict[str, Any]:
        """Stop a single daemon."""
        result = {"success": False, "error": None}
        
        try:
            if daemon_name == "ipfs":
                # Stop IPFS daemon
                try:
                    subprocess.run(['ipfs', 'shutdown'], timeout=10)
                    result["success"] = True
                except Exception as e:
                    result["error"] = str(e)
                    
            elif daemon_name == "lotus":
                if self.ipfs_kit and hasattr(self.ipfs_kit, 'lotus_daemon'):
                    lotus_result = self.ipfs_kit.lotus_daemon.daemon_stop()
                    result["success"] = lotus_result.get("success", False)
                    if not result["success"]:
                        result["error"] = lotus_result.get("error", "Unknown error")
                else:
                    result["success"] = True  # Not available, so "successfully" not running
                    
            elif daemon_name == "ipfs_cluster_service":
                if self.ipfs_kit and hasattr(self.ipfs_kit, 'ipfs_cluster_service'):
                    cluster_result = self.ipfs_kit.ipfs_cluster_service.daemon_stop()
                    result["success"] = cluster_result.get("success", False)
                    if not result["success"]:
                        result["error"] = cluster_result.get("error", "Unknown error")
                else:
                    result["success"] = True
                    
            else:
                result["success"] = True  # Unknown daemon, assume stopped
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    # Additional daemon management methods moved from MCP server
    
    def test_direct_ipfs(self) -> bool:
        """Test if IPFS commands work directly."""
        try:
            result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Direct IPFS test failed: {e}")
            return False
    
    def test_ipfs_connection(self) -> bool:
        """Test if IPFS daemon is accessible."""
        try:
            if self.ipfs_kit:
                result = self.ipfs_kit.ipfs_id()
                return result.get("success", False)
            else:
                # Test direct connection
                return self.test_direct_ipfs()
        except Exception as e:
            logger.debug(f"IPFS connection test failed: {e}")
            return False
    
    def test_ipfs_api_direct(self) -> bool:
        """Test if IPFS API is accessible directly via HTTP."""
        try:
            import requests
            response = requests.get('http://localhost:5001/api/v0/id', timeout=3)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Direct API test failed: {e}")
            return False
    
    def find_existing_ipfs_processes(self) -> List[int]:
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
    
    def kill_existing_ipfs_daemons(self) -> bool:
        """Kill existing IPFS daemon processes."""
        logger.info("Attempting to kill existing IPFS daemons...")
        
        pids = self.find_existing_ipfs_processes()
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
        remaining_pids = self.find_existing_ipfs_processes()
        
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
        final_pids = self.find_existing_ipfs_processes()
        
        if final_pids:
            logger.error(f"Failed to kill all IPFS processes: {final_pids}")
            return False
        else:
            logger.info("Successfully killed all existing IPFS daemon processes")
            return True
    
    def wait_for_daemon_stop(self, timeout: int = 10) -> bool:
        """Wait for IPFS daemon to stop."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.test_ipfs_connection():
                return True
            time.sleep(0.5)
        return False
    
    def kill_managed_daemon(self, daemon_process: Optional[subprocess.Popen] = None) -> bool:
        """Kill a specific managed IPFS daemon process."""
        if daemon_process and daemon_process.poll() is None:  # Still running
            logger.info(f"Attempting to terminate managed IPFS daemon (PID: {daemon_process.pid})...")
            try:
                # Send SIGTERM first
                daemon_process.terminate()
                daemon_process.wait(timeout=5)  # Wait for it to terminate
                if daemon_process.poll() is None:  # Still running after terminate
                    logger.warning(f"Managed daemon (PID: {daemon_process.pid}) did not terminate gracefully. Force killing.")
                    daemon_process.kill()
                    daemon_process.wait(timeout=5)  # Wait for kill
                logger.info("Managed IPFS daemon terminated.")
                return True
            except Exception as e:
                logger.error(f"Error terminating managed IPFS daemon: {e}")
                return False
        logger.info("No managed IPFS daemon is currently running.")
        return True
    
    def init_ipfs_if_needed(self):
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
    
    def ensure_daemon_running_comprehensive(self) -> Dict[str, Any]:
        """Comprehensive daemon management with connection testing and fallback logic.
        
        This method incorporates all the advanced daemon management logic from the MCP server.
        
        Returns:
            Dict with detailed results of daemon management operations
        """
        result = {
            "success": False,
            "daemon_started": False,
            "connection_methods": [],
            "errors": [],
            "warnings": [],
            "daemon_process": None
        }
        
        logger.info("Ensuring IPFS daemon is running with comprehensive checks...")

        # Test multiple connection methods to see if IPFS is working
        connection_tests = [
            ("IPFS Kit", self.test_ipfs_connection),
            ("Direct IPFS", self.test_direct_ipfs),
            ("HTTP API", self.test_ipfs_api_direct),
        ]
        
        working_methods = []
        for test_name, test_func in connection_tests:
            try:
                if test_func():
                    working_methods.append(test_name)
                    logger.debug(f"✓ {test_name} connection works")
                else:
                    logger.debug(f"✗ {test_name} connection failed")
            except Exception as e:
                logger.debug(f"✗ {test_name} connection test error: {e}")
        
        result["connection_methods"] = working_methods
        
        # If any connection method works, we're good
        if working_methods:
            logger.info(f"✓ IPFS is accessible via: {', '.join(working_methods)}")
            result["success"] = True
            return result

        # Check for existing IPFS daemon processes
        existing_pids = self.find_existing_ipfs_processes()
        if existing_pids:
            logger.warning(f"Found IPFS daemon processes ({existing_pids}) but none are responsive to any connection test.")
            result["warnings"].append(f"Found unresponsive IPFS daemons: {existing_pids}")

        # Try to start a new daemon
        logger.info("No accessible IPFS daemon found. Attempting to start a new one.")
        try:
            self.init_ipfs_if_needed()  # Ensure repo is initialized
            cmd = ['ipfs', 'daemon', '--enable-pubsub-experiment']
            logger.debug(f"Running command: {' '.join(cmd)}")

            daemon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
                env=os.environ.copy()
            )
            
            result["daemon_process"] = daemon_process

            for i in range(10):  # Wait up to 10 seconds
                time.sleep(1)
                if daemon_process.poll() is not None:
                    stdout, stderr = daemon_process.communicate()
                    stdout_str = stdout.decode()
                    stderr_str = stderr.decode()
                    
                    error_msg = f"IPFS daemon exited with code {daemon_process.returncode}"
                    logger.error(error_msg)
                    logger.error(f"STDOUT: {stdout_str}")
                    logger.error(f"STDERR: {stderr_str}")
                    
                    result["errors"].append(error_msg)
                    result["errors"].append(f"STDERR: {stderr_str}")
                    
                    # Check for specific repo version mismatch
                    if "version" in stderr_str and "lower than your repos" in stderr_str:
                        logger.warning("⚠️  IPFS repo version mismatch detected.")
                        logger.warning("The daemon cannot start due to version incompatibility.")
                        logger.info("Testing if direct IPFS commands work despite daemon failure...")
                        
                        # Test if direct commands work despite daemon failure
                        if self.test_direct_ipfs():
                            logger.info("✅ Direct IPFS commands work despite daemon failure. Proceeding without daemon.")
                            result["success"] = True
                            result["warnings"].append("Direct IPFS works despite daemon failure")
                            return result
                        else:
                            logger.error("❌ Direct IPFS commands also don't work.")
                            result["errors"].append("Direct IPFS commands also failed")
                    
                    return result
                    
                if self.test_ipfs_connection():
                    logger.info(f"✓ IPFS daemon started successfully (took {i+1} seconds).")
                    result["success"] = True
                    result["daemon_started"] = True
                    return result
                logger.debug(f"Waiting for daemon to be ready... ({i+1}/10)")

            logger.error("IPFS daemon started but not accessible after 10 seconds.")
            try:
                stdout, stderr = daemon_process.communicate(timeout=1)
                logger.error(f"Daemon STDOUT: {stdout.decode()}")
                logger.error(f"Daemon STDERR: {stderr.decode()}")
                result["errors"].append(f"Daemon unresponsive: {stderr.decode()}")
            except subprocess.TimeoutExpired:
                logger.error("Daemon still running but not responding.")
                result["errors"].append("Daemon started but unresponsive")
            
            return result

        except Exception as e:
            error_msg = f"Failed to start IPFS daemon: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["errors"].append(error_msg)
            return result

    def _manage_cluster_lockfile_and_daemon(self) -> Dict[str, Any]:
        """
        Manage IPFS cluster lockfile and daemon lifecycle.
        
        Logic:
        1. If lockfile exists and no daemon is running -> delete lockfile, start daemon
        2. If daemon is running -> test API, if API fails -> kill daemon, delete lockfile, restart daemon
        3. If no lockfile and no daemon -> normal startup
        """
        result = {"success": True, "action": "none", "error": None}
        
        try:
            # Define paths
            cluster_config_dir = Path.home() / ".ipfs-cluster"
            lockfile_path = cluster_config_dir / "cluster.lock"
            project_bin = Path(__file__).parent / "bin"
            
            # Add project bin to PATH for cluster commands
            os.environ["PATH"] = f"{project_bin}:{os.environ.get('PATH', '')}"
            
            # Check if lockfile exists
            lockfile_exists = lockfile_path.exists()
            
            # Check if daemon is running
            daemon_running = self._is_cluster_daemon_running()
            
            # Check API health if daemon is running
            api_healthy = False
            if daemon_running:
                api_healthy = self._test_cluster_api_health()
            
            logger.info(f"Cluster state: lockfile={lockfile_exists}, daemon={daemon_running}, api_healthy={api_healthy}")
            
            # Case 1: Lockfile exists but no daemon running
            if lockfile_exists and not daemon_running:
                logger.info("Stale lockfile detected - removing lockfile")
                try:
                    lockfile_path.unlink()
                    result["action"] = "removed_stale_lockfile"
                    logger.info("✓ Removed stale cluster lockfile")
                except Exception as e:
                    result["error"] = f"Failed to remove stale lockfile: {e}"
                    return result
            
            # Case 2: Daemon running but API unhealthy
            elif daemon_running and not api_healthy:
                logger.warning("Cluster daemon running but API unhealthy - restarting daemon")
                try:
                    # Kill the daemon
                    self._kill_cluster_daemon()
                    time.sleep(2)  # Give it time to shut down
                    
                    # Remove lockfile if it exists
                    if lockfile_path.exists():
                        lockfile_path.unlink()
                        logger.info("✓ Removed lockfile after killing unhealthy daemon")
                    
                    result["action"] = "restarted_unhealthy_daemon"
                    logger.info("✓ Killed unhealthy cluster daemon and cleaned up lockfile")
                    
                except Exception as e:
                    result["error"] = f"Failed to restart unhealthy daemon: {e}"
                    return result
            
            # Case 3: Everything looks good
            elif daemon_running and api_healthy:
                result["action"] = "daemon_healthy"
                logger.info("✓ Cluster daemon is running and healthy")
            
            # Case 4: Clean state - no lockfile, no daemon
            else:
                result["action"] = "clean_state"
                logger.info("✓ Clean state - ready for normal startup")
            
            return result
            
        except Exception as e:
            result["success"] = False
            result["error"] = f"Lockfile management failed: {e}"
            logger.error(f"Lockfile management error: {e}")
            logger.error(traceback.format_exc())
            return result
    
    def _is_cluster_daemon_running(self) -> bool:
        """Check if IPFS cluster daemon is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ipfs-cluster-service"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0 and result.stdout.strip()
        except Exception as e:
            logger.error(f"Error checking cluster daemon: {e}")
            return False
    
    def _test_cluster_api_health(self) -> bool:
        """Test if the cluster API is responding."""
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "3", "http://127.0.0.1:9094/api/v0/version"],
                capture_output=True, text=True, timeout=5
            )
            # API is healthy if curl succeeds and returns JSON-like content
            return result.returncode == 0 and ("{" in result.stdout or "version" in result.stdout.lower())
        except Exception as e:
            logger.error(f"Error testing cluster API: {e}")
            return False
    
    def _kill_cluster_daemon(self) -> bool:
        """Kill running cluster daemon processes."""
        try:
            # Try graceful shutdown first
            subprocess.run(
                ["pkill", "-TERM", "-f", "ipfs-cluster-service"],
                timeout=10
            )
            time.sleep(3)
            
            # Force kill if still running
            subprocess.run(
                ["pkill", "-KILL", "-f", "ipfs-cluster-service"],
                timeout=5
            )
            
            return True
        except Exception as e:
            logger.error(f"Error killing cluster daemon: {e}")
            return False
