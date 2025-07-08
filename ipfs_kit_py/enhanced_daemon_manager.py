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
            if hasattr(self.ipfs_kit, 'install_ipfs_obj'):
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
            if hasattr(self.ipfs_kit, 'install_ipfs_obj'):
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
            if hasattr(self.ipfs_kit, 'lotus_daemon'):
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
        """Start the IPFS cluster service with enhanced error handling."""
        result = {"success": False, "error": None, "status": None}
        
        try:
            # Check if IPFS is running first (dependency)
            if not self._is_daemon_running("ipfs"):
                result["error"] = "IPFS daemon must be running before starting cluster service"
                return result
            
            # Check if we have cluster service manager
            if hasattr(self.ipfs_kit, 'ipfs_cluster_service'):
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
            if hasattr(self.ipfs_kit, 'lassie_kit'):
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
                if hasattr(self.ipfs_kit, 'lotus_daemon'):
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
                if hasattr(self.ipfs_kit, 'lotus_daemon'):
                    lotus_result = self.ipfs_kit.lotus_daemon.daemon_stop()
                    result["success"] = lotus_result.get("success", False)
                    if not result["success"]:
                        result["error"] = lotus_result.get("error", "Unknown error")
                else:
                    result["success"] = True  # Not available, so "successfully" not running
                    
            elif daemon_name == "ipfs_cluster_service":
                if hasattr(self.ipfs_kit, 'ipfs_cluster_service'):
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
