#!/usr/bin/env python3
"""
IPFS Daemon Manager

A comprehensive daemon manager for IPFS that handles:
- Starting and stopping daemons
- API responsiveness checking  
- Port cleanup and process management
- Lock file management
- Intelligent restart logic

Usage:
    from ipfs_kit_py.ipfs_daemon_manager import IPFSDaemonManager
    
    manager = IPFSDaemonManager()
    
    # Start daemon (will clean ports, remove stale locks, etc.)
    result = manager.start_daemon()
    
    # Stop daemon
    result = manager.stop_daemon()
    
    # Check if daemon is healthy and responsive
    is_healthy = manager.is_daemon_healthy()
    
    # Force restart if unresponsive
    result = manager.restart_daemon(force=True)
"""

import json
import logging
import os
import signal
import subprocess
import time
import httpx
import psutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IPFSConfig:
    """IPFS configuration settings"""
    ipfs_path: str = "~/.ipfs"
    api_port: int = 5001
    gateway_port: int = 8080
    swarm_port: int = 4001
    api_timeout: int = 10
    daemon_timeout: int = 30


class IPFSDaemonManager:
    """
    Comprehensive IPFS daemon manager with intelligent lifecycle management.
    
    Features:
    - API responsiveness checking
    - Port cleanup and process management
    - Lock file management
    - Intelligent restart logic
    - Process monitoring
    """
    
    def __init__(self, config: Optional[IPFSConfig] = None):
        # Respect project-local IPFS repos when an environment override is present.
        # This is critical for "zero-touch" installs and for tests, where we should
        # not mutate the user's ~/.ipfs unless explicitly requested.
        if config is None:
            config = IPFSConfig(ipfs_path=os.environ.get("IPFS_PATH", "~/.ipfs"))

        self.config = config
        self.ipfs_path = os.path.expanduser(self.config.ipfs_path)
        self.repo_lock_path = os.path.join(self.ipfs_path, "repo.lock")
        self.api_url = f"http://127.0.0.1:{self.config.api_port}"
        
        # Ensure IPFS path exists
        os.makedirs(self.ipfs_path, exist_ok=True)
    
    def start_daemon(self, force_restart: bool = False) -> Dict[str, Any]:
        """
        Start IPFS daemon with comprehensive checks and cleanup.
        
        Args:
            force_restart: If True, will kill existing daemon even if responsive
            
        Returns:
            Dict with success status, details, and any actions taken
        """
        operation = "daemon_start"
        result = {
            "success": False,
            "operation": operation,
            "status": None,
            "message": None,
            "actions_taken": [],
            "errors": [],
            "daemon_pid": None
        }
        
        try:
            logger.info("Starting IPFS daemon with comprehensive management...")
            
            # Step 1: Check current daemon status
            if not force_restart:
                daemon_status = self._check_daemon_status()
                if daemon_status["running"] and daemon_status["api_responsive"]:
                    result["success"] = True
                    result["status"] = "already_running"
                    result["message"] = "IPFS daemon is already running and responsive"
                    result["daemon_pid"] = daemon_status["pid"]
                    return result
                elif daemon_status["running"] and not daemon_status["api_responsive"]:
                    logger.warning("Daemon running but API unresponsive - will restart")
                    result["actions_taken"].append("detected_unresponsive_daemon")
                    self._kill_daemon_processes()
                    result["actions_taken"].append("killed_unresponsive_daemon")
            else:
                logger.info("Force restart requested - stopping any existing daemon")
                self._kill_daemon_processes()
                result["actions_taken"].append("force_killed_existing_daemon")
            
            # Step 2: Clean up ports
            port_cleanup_result = self._cleanup_ports()
            if port_cleanup_result["processes_killed"] > 0:
                result["actions_taken"].append(f"cleaned_ports_{port_cleanup_result['processes_killed']}_killed")
                # Wait for ports to be released
                time.sleep(2)
            
            # Step 3: Remove stale lock file
            lock_cleanup_result = self._cleanup_lock_file()
            if lock_cleanup_result["removed"]:
                result["actions_taken"].append("removed_stale_lock")
            
            # Step 4: Start the daemon
            start_result = self._start_daemon_process()
            if not start_result["success"]:
                result["errors"].append(start_result["error"])
                return result
            
            result["daemon_pid"] = start_result["pid"]
            result["actions_taken"].append("started_daemon_process")
            
            # Step 5: Wait for API to become responsive
            api_ready = self._wait_for_api_ready()
            if api_ready:
                result["success"] = True
                result["status"] = "started"
                result["message"] = "IPFS daemon started successfully and API is responsive"
                result["actions_taken"].append("verified_api_responsive")
            else:
                result["errors"].append("Daemon started but API is not responding")
                result["status"] = "started_but_unresponsive"
                
        except Exception as e:
            error_msg = f"Failed to start IPFS daemon: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            
        return result
    
    def stop_daemon(self) -> Dict[str, Any]:
        """
        Stop IPFS daemon gracefully.
        
        Returns:
            Dict with success status and details
        """
        result = {
            "success": False,
            "operation": "daemon_stop",
            "actions_taken": [],
            "errors": []
        }
        
        try:
            daemon_status = self._check_daemon_status()
            if not daemon_status["running"]:
                result["success"] = True
                result["message"] = "IPFS daemon is not running"
                return result
            
            # Try graceful shutdown first
            if self._graceful_shutdown():
                result["actions_taken"].append("graceful_shutdown")
                time.sleep(3)
                
                # Check if it stopped
                if not self._check_daemon_status()["running"]:
                    result["success"] = True
                    result["message"] = "IPFS daemon stopped gracefully"
                    return result
            
            # If graceful shutdown failed, force kill
            logger.warning("Graceful shutdown failed, force killing daemon processes")
            killed_count = self._kill_daemon_processes()
            result["actions_taken"].append(f"force_killed_{killed_count}_processes")
            
            # Clean up lock file
            lock_cleanup = self._cleanup_lock_file()
            if lock_cleanup["removed"]:
                result["actions_taken"].append("removed_lock_file")
            
            result["success"] = True
            result["message"] = "IPFS daemon stopped (force killed)"
            
        except Exception as e:
            error_msg = f"Failed to stop IPFS daemon: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            
        return result
    
    def restart_daemon(self, force: bool = True) -> Dict[str, Any]:
        """
        Restart IPFS daemon.
        
        Args:
            force: If True, will force kill existing daemon
            
        Returns:
            Dict with success status and details
        """
        logger.info("Restarting IPFS daemon...")
        
        # Stop the daemon
        stop_result = self.stop_daemon()
        
        # Wait a moment for cleanup
        time.sleep(2)
        
        # Start the daemon
        start_result = self.start_daemon(force_restart=force)
        
        # Combine results
        result = {
            "success": start_result["success"],
            "operation": "daemon_restart",
            "stop_result": stop_result,
            "start_result": start_result,
            "message": f"Restart {'successful' if start_result['success'] else 'failed'}"
        }
        
        return result
    
    def is_daemon_healthy(self) -> bool:
        """
        Check if IPFS daemon is running and responsive.
        
        Returns:
            True if daemon is healthy (running and API responsive)
        """
        status = self._check_daemon_status()
        return status["running"] and status["api_responsive"]
    
    def get_daemon_status(self) -> Dict[str, Any]:
        """
        Get comprehensive daemon status information.
        
        Returns:
            Dict with detailed status information
        """
        status = self._check_daemon_status()
        
        # Add additional info
        status.update({
            "config": {
                "ipfs_path": self.ipfs_path,
                "api_port": self.config.api_port,
                "gateway_port": self.config.gateway_port,
                "swarm_port": self.config.swarm_port
            },
            "lock_file_exists": os.path.exists(self.repo_lock_path),
            "lock_file_path": self.repo_lock_path
        })
        
        # Check port usage
        status["port_usage"] = self._check_port_usage()
        
        return status
    
    def _check_daemon_status(self) -> Dict[str, Any]:
        """Check current daemon status including process and API responsiveness."""
        status = {
            "running": False,
            "api_responsive": False,
            "pid": None,
            "processes": []
        }
        
        try:
            # Find IPFS daemon processes
            ipfs_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'ipfs' and proc.info['cmdline']:
                        cmdline_str = ' '.join(proc.info['cmdline'])
                        if 'daemon' in cmdline_str:
                            ipfs_processes.append({
                                'pid': proc.info['pid'],
                                'cmdline': cmdline_str
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            status["processes"] = ipfs_processes
            
            if ipfs_processes:
                status["running"] = True
                status["pid"] = ipfs_processes[0]["pid"]  # Primary daemon PID
                
                # Check API responsiveness
                status["api_responsive"] = self._test_api_responsiveness()
            
        except Exception as e:
            logger.debug(f"Error checking daemon status: {e}")
            
        return status
    
    def _test_api_responsiveness(self) -> bool:
        """Test if IPFS API is responsive."""
        try:
            with httpx.Client(timeout=self.config.api_timeout) as client:
                response = client.post(f"{self.api_url}/api/v0/version")
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"API responsiveness test failed: {e}")
            return False
    
    def _cleanup_ports(self) -> Dict[str, Any]:
        """Clean up processes using IPFS ports."""
        result = {
            "success": True,
            "processes_killed": 0,
            "ports_cleaned": [],
            "errors": []
        }
        
        ports_to_clean = [
            self.config.api_port,
            self.config.gateway_port,
            self.config.swarm_port
        ]
        
        for port in ports_to_clean:
            try:
                # Find processes using this port
                processes = self._find_processes_using_port(port)
                
                for proc_info in processes:
                    try:
                        pid = proc_info["pid"]
                        
                        # Skip if it's an IPFS process that we want to keep
                        if self._is_ipfs_process(pid) and not self._should_kill_ipfs_process(pid):
                            continue
                        
                        logger.info(f"Killing process {pid} using port {port}")
                        
                        # Try graceful termination first
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(1)
                        
                        # Check if still running, then force kill
                        try:
                            os.kill(pid, 0)  # Check if process exists
                            os.kill(pid, signal.SIGKILL)
                            logger.info(f"Force killed process {pid}")
                        except OSError:
                            # Process already terminated
                            pass
                        
                        result["processes_killed"] += 1
                        
                    except OSError as e:
                        logger.debug(f"Could not kill process {proc_info['pid']}: {e}")
                        
                result["ports_cleaned"].append(port)
                
            except Exception as e:
                error_msg = f"Error cleaning port {port}: {e}"
                logger.warning(error_msg)
                result["errors"].append(error_msg)
        
        return result
    
    def _find_processes_using_port(self, port: int) -> List[Dict[str, Any]]:
        """Find processes using a specific port."""
        processes = []
        
        try:
            # Use lsof to find processes
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid_str in pids:
                    if pid_str:
                        try:
                            pid = int(pid_str)
                            proc = psutil.Process(pid)
                            processes.append({
                                "pid": pid,
                                "name": proc.name(),
                                "cmdline": ' '.join(proc.cmdline())
                            })
                        except (ValueError, psutil.NoSuchProcess):
                            continue
                            
        except Exception as e:
            logger.debug(f"Error finding processes using port {port}: {e}")
            
        return processes
    
    def _is_ipfs_process(self, pid: int) -> bool:
        """Check if a process is an IPFS process."""
        try:
            proc = psutil.Process(pid)
            return proc.name() == 'ipfs'
        except psutil.NoSuchProcess:
            return False
    
    def _should_kill_ipfs_process(self, pid: int) -> bool:
        """Determine if an IPFS process should be killed."""
        try:
            proc = psutil.Process(pid)
            cmdline = ' '.join(proc.cmdline())
            
            # Don't kill if it's a responsive daemon and we're not forcing restart
            if 'daemon' in cmdline and self._test_api_responsiveness():
                return False
                
            return True
        except psutil.NoSuchProcess:
            return False
    
    def _cleanup_lock_file(self) -> Dict[str, Any]:
        """Clean up stale lock file."""
        result = {
            "removed": False,
            "was_stale": False,
            "error": None
        }
        
        if not os.path.exists(self.repo_lock_path):
            return result
        
        try:
            # Check if lock file is stale
            is_stale = True
            
            with open(self.repo_lock_path, 'r') as f:
                content = f.read().strip()
                if content and content.isdigit():
                    pid = int(content)
                    try:
                        # Check if process is still running
                        os.kill(pid, 0)
                        
                        # Process exists, check if it's actually IPFS
                        if self._is_ipfs_process(pid):
                            proc = psutil.Process(pid)
                            cmdline = ' '.join(proc.cmdline())
                            if 'daemon' in cmdline:
                                is_stale = False
                    except OSError:
                        # Process doesn't exist
                        is_stale = True
            
            result["was_stale"] = is_stale
            
            if is_stale:
                os.remove(self.repo_lock_path)
                result["removed"] = True
                logger.info(f"Removed stale lock file: {self.repo_lock_path}")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error cleaning up lock file: {e}")
        
        return result
    
    def _start_daemon_process(self) -> Dict[str, Any]:
        """Start the IPFS daemon process."""
        result = {
            "success": False,
            "pid": None,
            "error": None
        }
        
        try:
            # Build daemon command
            cmd = ["ipfs", "daemon", "--enable-pubsub-experiment"]
            
            # Start daemon process
            logger.info(f"Starting IPFS daemon with command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new session
            )
            
            result["pid"] = process.pid
            result["success"] = True
            
            logger.info(f"IPFS daemon started with PID {process.pid}")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to start daemon process: {e}")
        
        return result
    
    def _wait_for_api_ready(self, max_wait: int = None) -> bool:
        """Wait for IPFS API to become ready."""
        max_wait = max_wait or self.config.daemon_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for IPFS API to become ready (max {max_wait}s)...")
        
        while time.time() - start_time < max_wait:
            if self._test_api_responsiveness():
                elapsed = time.time() - start_time
                logger.info(f"IPFS API ready after {elapsed:.1f}s")
                return True
            
            time.sleep(1)
        
        logger.warning(f"IPFS API not ready after {max_wait}s")
        return False
    
    def _graceful_shutdown(self) -> bool:
        """Attempt graceful shutdown via API."""
        try:
            with httpx.Client(timeout=self.config.api_timeout) as client:
                response = client.post(f"{self.api_url}/api/v0/shutdown")
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Graceful shutdown failed: {e}")
            return False
    
    def _kill_daemon_processes(self) -> int:
        """Force kill all IPFS daemon processes."""
        killed_count = 0
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if (proc.info['name'] == 'ipfs' and 
                        proc.info['cmdline'] and 
                        'daemon' in ' '.join(proc.info['cmdline'])):
                        
                        pid = proc.info['pid']
                        logger.info(f"Killing IPFS daemon process {pid}")
                        
                        # Send SIGTERM first
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(1)
                        
                        # Check if still running, then SIGKILL
                        try:
                            os.kill(pid, 0)
                            os.kill(pid, signal.SIGKILL)
                            logger.info(f"Force killed IPFS daemon {pid}")
                        except OSError:
                            pass
                        
                        killed_count += 1
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    continue
                    
        except Exception as e:
            logger.error(f"Error killing daemon processes: {e}")
            
        return killed_count
    
    def _check_port_usage(self) -> Dict[str, Any]:
        """Check which ports are in use."""
        port_usage = {}
        
        ports_to_check = {
            "api": self.config.api_port,
            "gateway": self.config.gateway_port,
            "swarm": self.config.swarm_port
        }
        
        for port_name, port in ports_to_check.items():
            port_usage[port_name] = {
                "port": port,
                "in_use": False,
                "processes": []
            }
            
            processes = self._find_processes_using_port(port)
            if processes:
                port_usage[port_name]["in_use"] = True
                port_usage[port_name]["processes"] = processes
        
        return port_usage

    async def _get_ipfs_metrics(self) -> Dict[str, Any]:
        """
        Fetch various metrics from the IPFS daemon API.
        
        Returns:
            A dictionary containing IPFS metrics.
        """
        metrics = {
            "repo_size": 0,
            "repo_objects": 0,
            "pins_count": 0,
            "peer_count": 0,
            "bandwidth_in": 0,
            "bandwidth_out": 0,
            "datastore_type": "unknown"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.config.api_timeout) as client:
                # Get repo stats
                try:
                    repo_stat_response = await client.post(f"{self.api_url}/api/v0/repo/stat")
                    repo_stat_response.raise_for_status()
                    repo_stat = repo_stat_response.json()
                    metrics["repo_size"] = int(repo_stat.get("RepoSize", 0))
                    metrics["repo_objects"] = int(repo_stat.get("NumObjects", 0))
                    metrics["datastore_type"] = repo_stat.get("StorageMax", "unknown") # This is actually StorageMax, not datastore_type
                except Exception as e:
                    logger.warning(f"Could not get IPFS repo stats: {e}")

                # Get pin count
                try:
                    # Using 'pin/ls' with stream=true might be too verbose for just a count
                    # A simpler approach is to use 'pin/ls' without streaming and count
                    pin_ls_response = await client.post(f"{self.api_url}/api/v0/pin/ls")
                    pin_ls_response.raise_for_status()
                    pins = pin_ls_response.json().get("Keys", {})
                    metrics["pins_count"] = len(pins)
                except Exception as e:
                    logger.warning(f"Could not get IPFS pin count: {e}")

                # Get peer count
                try:
                    swarm_peers_response = await client.post(f"{self.api_url}/api/v0/swarm/peers")
                    swarm_peers_response.raise_for_status()
                    peers = swarm_peers_response.json().get("Peers", [])
                    metrics["peer_count"] = len(peers)
                except Exception as e:
                    logger.warning(f"Could not get IPFS peer count: {e}")

                # Get bandwidth stats
                try:
                    stats_bw_response = await client.post(f"{self.api_url}/api/v0/stats/bw")
                    stats_bw_response.raise_for_status()
                    bw_stats = stats_bw_response.json()
                    metrics["bandwidth_in"] = int(bw_stats.get("RateIn", 0))
                    metrics["bandwidth_out"] = int(bw_stats.get("RateOut", 0))
                except Exception as e:
                    logger.warning(f"Could not get IPFS bandwidth stats: {e}")

        except Exception as e:
            logger.error(f"Error fetching IPFS metrics: {e}")
            
        return metrics


def main():
    """CLI interface for IPFS daemon management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS Daemon Manager")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "health"],
                       help="Action to perform")
    parser.add_argument("--force", action="store_true",
                       help="Force restart even if daemon is responsive")
    parser.add_argument("--api-port", type=int, default=5001,
                       help="IPFS API port")
    parser.add_argument("--gateway-port", type=int, default=8080,
                       help="IPFS gateway port")
    parser.add_argument("--swarm-port", type=int, default=4001,
                       help="IPFS swarm port")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create manager
    config = IPFSConfig(
        api_port=args.api_port,
        gateway_port=args.gateway_port,
        swarm_port=args.swarm_port
    )
    manager = IPFSDaemonManager(config)
    
    # Execute action
    if args.action == "start":
        result = manager.start_daemon(force_restart=args.force)
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    
    elif args.action == "stop":
        result = manager.stop_daemon()
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    
    elif args.action == "restart":
        result = manager.restart_daemon(force=args.force)
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    
    elif args.action == "status":
        status = manager.get_daemon_status()
        print(json.dumps(status, indent=2))
        return 0
    
    elif args.action == "health":
        is_healthy = manager.is_daemon_healthy()
        print(f"Daemon healthy: {is_healthy}")
        return 0 if is_healthy else 1


if __name__ == "__main__":
    exit(main())
