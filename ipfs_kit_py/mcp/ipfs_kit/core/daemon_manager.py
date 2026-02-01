"""
Enhanced IPFS Daemon Manager for MCP Server.

This module provides comprehensive daemon management with:
1. API responsiveness checking
2. Port conflict resolution
3. Process cleanup and restart capabilities
4. Integration with content optimization system
"""

import anyio
import json
import logging
import os
import signal
import subprocess
import time
import psutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from enum import Enum

logger = logging.getLogger(__name__)


class DaemonTypes(Enum):
    """Supported daemon types.

    This enum exists primarily for backwards-compatibility with higher-level
    cluster management code that imports `DaemonTypes`.
    """

    IPFS = "ipfs"


# Backwards-compatible alias expected by cluster code.
# The refactor introduced `IPFSDaemonManager` but some modules still import
# `DaemonManager`.
DaemonManager = None  # set after class definition


class IPFSDaemonManager:
    """
    Enhanced IPFS daemon manager with intelligent startup, monitoring, and cleanup.
    """
    
    def __init__(self, ipfs_path: str = None, ipfs_kit_instance=None):
        self.ipfs_path = ipfs_path or os.path.expanduser("~/.ipfs")
        self.ipfs_kit = ipfs_kit_instance
        self.daemon_process = None
        self.is_monitoring = False
        self.last_health_check = None
        self.health_check_interval = 30  # seconds
        
        # IPFS standard ports
        self.ipfs_ports = {
            'api': 5001,
            'gateway': 8080,
            'swarm': 4001
        }
        
        logger.info("✓ Enhanced IPFS Daemon Manager initialized")
    
    async def start_daemon(self, force_restart: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Start IPFS daemon with comprehensive checks and cleanup.
        
        Args:
            force_restart: If True, force restart even if daemon appears running
            **kwargs: Additional daemon startup options
        """
        result = {
            "operation": "start_daemon",
            "success": False,
            "method": None,
            "daemon_responsive": False,
            "cleanup_performed": False,
            "port_conflicts_resolved": False,
            "process_info": {},
            "timestamp": time.time()
        }
        
        try:
            logger.info("🚀 Starting IPFS daemon with enhanced management")
            
            # Step 1: Check if daemon is already running and responsive
            if not force_restart:
                existing_check = await self._check_existing_daemon()
                result["existing_daemon_check"] = existing_check
                
                if existing_check.get("running") and existing_check.get("responsive"):
                    result["success"] = True
                    result["method"] = "already_running"
                    result["daemon_responsive"] = True
                    result["process_info"] = existing_check.get("process_info", {})
                    logger.info("✓ IPFS daemon already running and responsive")
                    return result
                elif existing_check.get("running") and not existing_check.get("responsive"):
                    logger.warning("⚠️ IPFS daemon running but not responsive, performing cleanup")
                    cleanup_result = await self._cleanup_unresponsive_daemon()
                    result["cleanup_result"] = cleanup_result
                    result["cleanup_performed"] = True
            
            # Step 2: Cleanup port conflicts
            port_cleanup = await self._cleanup_port_conflicts()
            result["port_cleanup"] = port_cleanup
            result["port_conflicts_resolved"] = port_cleanup.get("conflicts_resolved", False)
            
            # Step 3: Remove stale lock files
            lock_cleanup = await self._cleanup_lock_files()
            result["lock_cleanup"] = lock_cleanup
            
            # Step 4: Kill any remaining IPFS processes
            process_cleanup = await self._cleanup_ipfs_processes()
            result["process_cleanup"] = process_cleanup
            
            # Step 5: Try to start daemon
            start_result = await self._attempt_daemon_start(**kwargs)
            result.update(start_result)
            
            if start_result.get("success"):
                # Step 6: Wait for API to be responsive
                api_ready = await self._wait_for_api_ready(timeout=30)
                result["api_ready"] = api_ready
                result["daemon_responsive"] = api_ready.get("responsive", False)
                
                if api_ready.get("responsive"):
                    result["success"] = True
                    logger.info("✓ IPFS daemon started and API is responsive")
                    
                    # Start health monitoring
                    if not self.is_monitoring:
                        anyio.lowlevel.spawn_system_task(self._health_monitor_loop)
                else:
                    logger.error("❌ IPFS daemon started but API not responsive")
                    result["success"] = False
            
        except Exception as e:
            logger.error(f"❌ Error starting IPFS daemon: {e}")
            result["error"] = str(e)
        
        return result
    
    async def stop_daemon(self, graceful: bool = True, timeout: int = 10) -> Dict[str, Any]:
        """
        Stop IPFS daemon gracefully or forcefully.
        """
        result = {
            "operation": "stop_daemon",
            "success": False,
            "method": None,
            "graceful": graceful,
            "processes_terminated": [],
            "timestamp": time.time()
        }
        
        try:
            logger.info("🛑 Stopping IPFS daemon")
            
            # Find all IPFS daemon processes
            ipfs_processes = await self._find_ipfs_processes()
            result["found_processes"] = len(ipfs_processes)
            
            if not ipfs_processes:
                result["success"] = True
                result["method"] = "no_processes_found"
                logger.info("✓ No IPFS daemon processes found")
                return result
            
            # Stop processes
            for proc_info in ipfs_processes:
                try:
                    pid = proc_info["pid"]
                    proc = psutil.Process(pid)
                    
                    if graceful:
                        # Try graceful shutdown first
                        proc.terminate()
                        logger.info(f"📨 Sent SIGTERM to IPFS process {pid}")
                        
                        # Wait for graceful shutdown
                        try:
                            proc.wait(timeout=timeout)
                            result["processes_terminated"].append({
                                "pid": pid,
                                "method": "graceful",
                                "success": True
                            })
                        except psutil.TimeoutExpired:
                            # Force kill if graceful shutdown fails
                            logger.warning(f"⚠️ Graceful shutdown timeout for PID {pid}, force killing")
                            proc.kill()
                            proc.wait(timeout=5)
                            result["processes_terminated"].append({
                                "pid": pid,
                                "method": "force",
                                "success": True
                            })
                    else:
                        # Force kill immediately
                        proc.kill()
                        proc.wait(timeout=5)
                        result["processes_terminated"].append({
                            "pid": pid,
                            "method": "force",
                            "success": True
                        })
                        
                except psutil.NoSuchProcess:
                    result["processes_terminated"].append({
                        "pid": pid,
                        "method": "already_dead",
                        "success": True
                    })
                except Exception as e:
                    logger.error(f"❌ Error stopping process {pid}: {e}")
                    result["processes_terminated"].append({
                        "pid": pid,
                        "method": "error",
                        "success": False,
                        "error": str(e)
                    })
            
            # Cleanup lock files after stopping
            await self._cleanup_lock_files()
            
            result["success"] = all(p.get("success", False) for p in result["processes_terminated"])
            if result["success"]:
                logger.info("✓ IPFS daemon stopped successfully")
                self.is_monitoring = False
            
        except Exception as e:
            logger.error(f"❌ Error stopping IPFS daemon: {e}")
            result["error"] = str(e)
        
        return result
    
    async def restart_daemon(self, **kwargs) -> Dict[str, Any]:
        """Restart IPFS daemon with full cleanup."""
        logger.info("🔄 Restarting IPFS daemon")
        
        # Stop existing daemon
        stop_result = await self.stop_daemon(graceful=True, timeout=10)
        
        # Wait a moment for cleanup
        await anyio.sleep(2)
        
        # Start daemon with force restart
        start_result = await self.start_daemon(force_restart=True, **kwargs)
        
        return {
            "operation": "restart_daemon",
            "stop_result": stop_result,
            "start_result": start_result,
            "success": start_result.get("success", False),
            "timestamp": time.time()
        }
    
    async def check_daemon_health(self) -> Dict[str, Any]:
        """
        Comprehensive daemon health check.
        """
        health = {
            "timestamp": time.time(),
            "process_running": False,
            "api_responsive": False,
            "ports_available": {},
            "lock_files_status": {},
            "performance_metrics": {},
            "overall_health": "unhealthy"
        }
        
        try:
            # Check if process is running
            existing_check = await self._check_existing_daemon()
            health["process_running"] = existing_check.get("running", False)
            health["api_responsive"] = existing_check.get("responsive", False)
            health["process_info"] = existing_check.get("process_info", {})
            
            # Check port availability
            for port_name, port_num in self.ipfs_ports.items():
                port_status = await self._check_port_status(port_num)
                health["ports_available"][port_name] = port_status
            
            # Check lock files
            health["lock_files_status"] = await self._check_lock_files()
            
            # Performance metrics
            if health["api_responsive"]:
                health["performance_metrics"] = await self._get_performance_metrics()
            
            # Overall health assessment
            if health["process_running"] and health["api_responsive"]:
                health["overall_health"] = "healthy"
            elif health["process_running"]:
                health["overall_health"] = "degraded"
            else:
                health["overall_health"] = "unhealthy"
            
            self.last_health_check = health
            
        except Exception as e:
            logger.error(f"❌ Error checking daemon health: {e}")
            health["error"] = str(e)
        
        return health
    
    async def _check_existing_daemon(self) -> Dict[str, Any]:
        """Check if IPFS daemon is running and responsive."""
        result = {
            "running": False,
            "responsive": False,
            "process_info": {},
            "api_check": {}
        }
        
        try:
            # Find IPFS processes
            ipfs_processes = await self._find_ipfs_processes()
            
            if ipfs_processes:
                result["running"] = True
                result["process_info"] = ipfs_processes[0]  # Use first found process
                
                # Check API responsiveness
                api_check = await self._check_api_responsiveness()
                result["api_check"] = api_check
                result["responsive"] = api_check.get("responsive", False)
        
        except Exception as e:
            logger.debug(f"Error checking existing daemon: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _check_api_responsiveness(self, timeout: int = 5) -> Dict[str, Any]:
        """Check if IPFS API is responsive."""
        result = {
            "responsive": False,
            "response_time": None,
            "method": None
        }
        
        try:
            import httpx
            
            start_time = time.time()
            
            # Try HTTP API first
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"http://127.0.0.1:{self.ipfs_ports['api']}/api/v0/version")
                    
                if response.status_code == 200:
                    result["responsive"] = True
                    result["response_time"] = time.time() - start_time
                    result["method"] = "http_api"
                    result["api_response"] = response.json()
                    return result
                    
            except Exception as e:
                logger.debug(f"HTTP API check failed: {e}")
            
            # Try CLI as fallback
            try:
                with anyio.fail_after(timeout):
                    process = await anyio.run_process(
                        ["ipfs", "version"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env={**os.environ, "IPFS_PATH": self.ipfs_path},
                    )

                if process.returncode == 0:
                    result["responsive"] = True
                    result["response_time"] = time.time() - start_time
                    result["method"] = "cli"
                    result["cli_output"] = process.stdout.decode().strip()
                    
            except Exception as e:
                logger.debug(f"CLI check failed: {e}")
                result["cli_error"] = str(e)
        
        except Exception as e:
            logger.debug(f"API responsiveness check failed: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _cleanup_port_conflicts(self) -> Dict[str, Any]:
        """Clean up processes using IPFS ports."""
        result = {
            "conflicts_resolved": False,
            "ports_checked": [],
            "processes_killed": [],
            "errors": []
        }
        
        try:
            for port_name, port_num in self.ipfs_ports.items():
                result["ports_checked"].append(port_num)
                
                # Find processes using the port
                processes_on_port = []
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        for conn in proc.info['connections'] or []:
                            if conn.laddr.port == port_num:
                                processes_on_port.append(proc.info['pid'])
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Kill processes using the port
                for pid in processes_on_port:
                    try:
                        proc = psutil.Process(pid)
                        proc.terminate()
                        proc.wait(timeout=5)
                        result["processes_killed"].append({
                            "pid": pid,
                            "port": port_num,
                            "success": True
                        })
                        logger.info(f"✓ Killed process {pid} using port {port_num}")
                    except Exception as e:
                        result["errors"].append(f"Failed to kill process {pid}: {e}")
                        logger.warning(f"⚠️ Failed to kill process {pid}: {e}")
            
            result["conflicts_resolved"] = len(result["processes_killed"]) > 0
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up port conflicts: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _cleanup_lock_files(self) -> Dict[str, Any]:
        """Clean up IPFS lock and API files."""
        result = {
            "files_removed": [],
            "errors": []
        }
        
        lock_files = [
            Path(self.ipfs_path) / "repo.lock",
            Path(self.ipfs_path) / "api",
            Path(self.ipfs_path) / "datastore" / "LOCK"
        ]
        
        for lock_file in lock_files:
            try:
                if lock_file.exists():
                    lock_file.unlink()
                    result["files_removed"].append(str(lock_file))
                    logger.info(f"✓ Removed lock file: {lock_file}")
            except Exception as e:
                error_msg = f"Failed to remove {lock_file}: {e}"
                result["errors"].append(error_msg)
                logger.warning(f"⚠️ {error_msg}")
        
        return result
    
    async def _cleanup_ipfs_processes(self) -> Dict[str, Any]:
        """Kill all IPFS daemon processes."""
        result = {
            "processes_found": 0,
            "processes_killed": [],
            "errors": []
        }
        
        try:
            ipfs_processes = await self._find_ipfs_processes()
            result["processes_found"] = len(ipfs_processes)
            
            for proc_info in ipfs_processes:
                try:
                    pid = proc_info["pid"]
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=5)
                    result["processes_killed"].append({
                        "pid": pid,
                        "success": True
                    })
                    logger.info(f"✓ Killed IPFS process {pid}")
                except Exception as e:
                    error_msg = f"Failed to kill process {pid}: {e}"
                    result["errors"].append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
        
        except Exception as e:
            logger.error(f"❌ Error cleaning up IPFS processes: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _find_ipfs_processes(self) -> List[Dict[str, Any]]:
        """Find all IPFS daemon processes."""
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    if proc.info['name'] == 'ipfs' and 'daemon' in (proc.info['cmdline'] or []):
                        processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "cmdline": proc.info['cmdline'],
                            "create_time": proc.info['create_time']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"Error finding IPFS processes: {e}")
        
        return processes
    
    async def _attempt_daemon_start(self, **kwargs) -> Dict[str, Any]:
        """Attempt to start IPFS daemon."""
        result = {
            "success": False,
            "method": None,
            "process_info": {},
            "attempts": {}
        }
        
        # Try systemctl first if running as root
        if os.geteuid() == 0:
            systemctl_result = await self._try_systemctl_start()
            result["attempts"]["systemctl"] = systemctl_result
            
            if systemctl_result.get("success"):
                result["success"] = True
                result["method"] = "systemctl"
                return result
        
        # Try direct daemon start
        direct_result = await self._try_direct_start(**kwargs)
        result["attempts"]["direct"] = direct_result
        
        if direct_result.get("success"):
            result["success"] = True
            result["method"] = "direct"
            result["process_info"] = direct_result.get("process_info", {})
        
        return result
    
    async def _try_systemctl_start(self) -> Dict[str, Any]:
        """Try to start IPFS via systemctl."""
        result = {"success": False, "method": "systemctl"}
        
        try:
            process = await anyio.run_process(
                ["systemctl", "start", "ipfs"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if process.returncode == 0:
                result["success"] = True
                logger.info("✓ Started IPFS daemon via systemctl")
            else:
                result["error"] = process.stderr.decode().strip()
                logger.debug(f"Systemctl start failed: {result['error']}")
        
        except Exception as e:
            result["error"] = str(e)
            logger.debug(f"Systemctl start error: {e}")
        
        return result
    
    async def _try_direct_start(self, **kwargs) -> Dict[str, Any]:
        """Try to start IPFS daemon directly."""
        result = {"success": False, "method": "direct"}
        
        try:
            # Build command
            cmd = ["ipfs", "daemon", "--enable-gc", "--enable-pubsub-experiment"]
            
            if kwargs.get("offline"):
                cmd.append("--offline")
            if kwargs.get("routing") in ["dht", "none"]:
                cmd.append(f"--routing={kwargs['routing']}")
            if kwargs.get("mount"):
                cmd.append("--mount")
            
            # Set environment
            env = os.environ.copy()
            env["IPFS_PATH"] = self.ipfs_path
            
            # Start process
            process = await anyio.open_process(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            # Give it a moment to start
            await anyio.sleep(2)
            
            if process.returncode is None:  # Still running
                result["success"] = True
                result["process_info"] = {
                    "pid": process.pid,
                    "cmd": cmd
                }
                self.daemon_process = process
                logger.info(f"✓ Started IPFS daemon directly (PID: {process.pid})")
            else:
                stderr = await process.stderr.receive()
                result["error"] = stderr.decode().strip()
                logger.error(f"❌ IPFS daemon failed to start: {result['error']}")
        
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"❌ Direct daemon start error: {e}")
        
        return result
    
    async def _wait_for_api_ready(self, timeout: int = 30) -> Dict[str, Any]:
        """Wait for IPFS API to become ready."""
        result = {"responsive": False, "attempts": 0, "total_wait_time": 0}
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result["attempts"] += 1
            
            api_check = await self._check_api_responsiveness(timeout=2)
            
            if api_check.get("responsive"):
                result["responsive"] = True
                result["total_wait_time"] = time.time() - start_time
                result["api_check"] = api_check
                logger.info(f"✓ IPFS API ready after {result['total_wait_time']:.1f}s")
                break
            
            await anyio.sleep(1)
        
        if not result["responsive"]:
            result["total_wait_time"] = timeout
            logger.warning(f"⚠️ IPFS API not ready after {timeout}s")
        
        return result
    
    async def _health_monitor_loop(self):
        """Background health monitoring loop."""
        self.is_monitoring = True
        logger.info("🔍 Started IPFS daemon health monitoring")
        
        while self.is_monitoring:
            try:
                health = await self.check_daemon_health()
                
                if health["overall_health"] == "unhealthy":
                    logger.warning("⚠️ IPFS daemon unhealthy, attempting restart")
                    restart_result = await self.restart_daemon()
                    if restart_result.get("success"):
                        logger.info("✓ IPFS daemon restart successful")
                    else:
                        logger.error("❌ IPFS daemon restart failed")
                
                await anyio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in health monitoring: {e}")
                await anyio.sleep(self.health_check_interval)
    
    async def _check_port_status(self, port: int) -> Dict[str, Any]:
        """Check if a port is available or in use."""
        import socket
        
        result = {"port": port, "available": False, "in_use_by": None}
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            connection_result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if connection_result == 0:
                result["available"] = False
                # Try to find what's using the port
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        for conn in proc.info['connections'] or []:
                            if conn.laddr.port == port:
                                result["in_use_by"] = {
                                    "pid": proc.info['pid'],
                                    "name": proc.info['name']
                                }
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            else:
                result["available"] = True
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _check_lock_files(self) -> Dict[str, Any]:
        """Check status of IPFS lock files."""
        lock_files = {
            "repo_lock": Path(self.ipfs_path) / "repo.lock",
            "api_file": Path(self.ipfs_path) / "api",
            "datastore_lock": Path(self.ipfs_path) / "datastore" / "LOCK"
        }
        
        status = {}
        
        for name, path in lock_files.items():
            status[name] = {
                "exists": path.exists(),
                "path": str(path),
                "size": path.stat().st_size if path.exists() else 0,
                "modified": path.stat().st_mtime if path.exists() else None
            }
        
        return status
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get IPFS daemon performance metrics."""
        metrics = {
            "api_response_time": None,
            "version_info": None,
            "repo_stats": None,
            "bandwidth_stats": None
        }
        
        try:
            # API response time
            api_check = await self._check_api_responsiveness()
            metrics["api_response_time"] = api_check.get("response_time")
            
            # Get version info and repo stats via HTTP API if responsive
            if api_check.get("responsive") and api_check.get("method") == "http_api":
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    # Version
                    version_response = await client.post(f"http://127.0.0.1:{self.ipfs_ports['api']}/api/v0/version")
                    if version_response.status_code == 200:
                        metrics["version_info"] = version_response.json()
                    
                    # Repo stats
                    repo_stat_response = await client.post(f"http://127.0.0.1:{self.ipfs_ports['api']}/api/v0/repo/stat")
                    if repo_stat_response.status_code == 200:
                        metrics["repo_stats"] = repo_stat_response.json()

                    # Bandwidth stats
                    bw_stat_response = await client.post(f"http://127.0.0.1:{self.ipfs_ports['api']}/api/v0/stats/bw")
                    if bw_stat_response.status_code == 200:
                        metrics["bandwidth_stats"] = bw_stat_response.json()
            else:
                # Fallback to CLI for repo and bandwidth stats if API is not responsive or not used
                try:
                    # Repo stats via CLI
                    with anyio.fail_after(5):
                        repo_stat_cli = await anyio.run_process(
                            ["ipfs", "repo", "stat", "--json"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env={**os.environ, "IPFS_PATH": self.ipfs_path},
                        )
                    if repo_stat_cli.returncode == 0:
                        metrics["repo_stats"] = json.loads(repo_stat_cli.stdout.decode().strip())
                    else:
                        logger.debug(f"CLI repo stat failed: {repo_stat_cli.stderr.decode().strip()}")

                    # Bandwidth stats via CLI
                    with anyio.fail_after(5):
                        bw_stat_cli = await anyio.run_process(
                            ["ipfs", "stats", "bw", "--json"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env={**os.environ, "IPFS_PATH": self.ipfs_path},
                        )
                    if bw_stat_cli.returncode == 0:
                        metrics["bandwidth_stats"] = json.loads(bw_stat_cli.stdout.decode().strip())
                    else:
                        logger.debug(f"CLI bandwidth stat failed: {bw_stat_cli.stderr.decode().strip()}")

                except Exception as cli_e:
                    logger.debug(f"Error getting CLI performance metrics: {cli_e}")
        
        except Exception as e:
            logger.debug(f"Error getting performance metrics: {e}")
            metrics["error"] = str(e)
        
        return metrics


# Global daemon manager instance
_daemon_manager = None

# Finalize backwards-compatible alias
DaemonManager = IPFSDaemonManager

def get_daemon_manager() -> IPFSDaemonManager:
    """Get or create the global daemon manager instance."""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = IPFSDaemonManager()
    return _daemon_manager
