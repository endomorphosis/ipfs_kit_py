#!/usr/bin/env python3
"""
MCP Daemon Service - Lightweight Interface

This service provides a lightweight interface to interact with the daemon
WITHOUT starting or managing it. It performs atomic operations and reads
daemon status from ~/.ipfs_kit/ files.

The daemon itself is managed separately via 'ipfs-kit daemon' commands.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class DaemonStatus:
    """Daemon status information read from files."""
    is_running: bool = False
    pid: Optional[int] = None
    role: str = "unknown"
    start_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    port: Optional[int] = None
    services: Dict[str, bool] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.services is None:
            self.services = {}


class MCPDaemonService:
    """
    Lightweight daemon interface for MCP server.
    
    This service reads daemon status from ~/.ipfs_kit/ files and provides
    atomic operations WITHOUT managing the daemon lifecycle.
    """
    
    def __init__(self, data_dir: Path):
        """Initialize MCP daemon service.
        
        Args:
            data_dir: Path to ~/.ipfs_kit/ directory
        """
        self.data_dir = Path(data_dir).expanduser()
        self.daemon_status_file = self.data_dir / "daemon_status.json"
        self.daemon_pid_file = self.data_dir / "daemon.pid"
        
        logger.info(f"MCP Daemon Service initialized with data_dir: {self.data_dir}")
    
    async def start(self):
        """Start the MCP daemon service (read-only interface)."""
        logger.info("Starting MCP daemon service")
        # No daemon management - just initialize interface
        pass
    
    async def stop(self):
        """Stop the MCP daemon service."""
        logger.info("Stopping MCP daemon service")
        # No daemon management needed
        pass
    
    async def get_daemon_status(self, detailed: bool = False) -> DaemonStatus:
        """Get current daemon status by reading from files.
        
        Args:
            detailed: Whether to include detailed information
            
        Returns:
            DaemonStatus object
        """
        try:
            status = DaemonStatus()
            
            # Read daemon status file
            if self.daemon_status_file.exists():
                with open(self.daemon_status_file, 'r') as f:
                    data = json.load(f)
                
                status.is_running = data.get('is_running', False)
                status.role = data.get('role', 'unknown')
                status.port = data.get('port')
                status.services = data.get('services', {})
                
                # Parse timestamps
                if data.get('start_time'):
                    status.start_time = datetime.fromisoformat(data['start_time'])
                if data.get('last_heartbeat'):
                    status.last_heartbeat = datetime.fromisoformat(data['last_heartbeat'])
            
            # Read PID file
            if self.daemon_pid_file.exists():
                try:
                    with open(self.daemon_pid_file, 'r') as f:
                        status.pid = int(f.read().strip())
                    
                    # Check if process is actually running
                    if status.pid:
                        try:
                            import psutil
                            process = psutil.Process(status.pid)
                            if process.is_running():
                                status.is_running = True
                            else:
                                status.is_running = False
                        except (psutil.NoSuchProcess, ImportError):
                            status.is_running = False
                except ValueError:
                    pass
            
            # Check heartbeat freshness
            if status.last_heartbeat:
                heartbeat_age = datetime.now() - status.last_heartbeat
                if heartbeat_age > timedelta(minutes=5):
                    status.error_message = f"Daemon heartbeat is {heartbeat_age.total_seconds():.0f}s old"
                    status.is_running = False
            
            return status
            
        except Exception as e:
            logger.error(f"Error reading daemon status: {e}")
            return DaemonStatus(error_message=str(e))
    
    async def read_daemon_logs(self, lines: int = 100) -> List[str]:
        """Read daemon log entries.
        
        Args:
            lines: Number of log lines to return
            
        Returns:
            List of log lines
        """
        try:
            log_file = self.data_dir / "daemon.log"
            if not log_file.exists():
                return ["No daemon log file found"]
            
            # Read last N lines
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                return [line.rstrip() for line in all_lines[-lines:]]
                
        except Exception as e:
            logger.error(f"Error reading daemon logs: {e}")
            return [f"Error reading logs: {e}"]
    
    async def get_daemon_config(self) -> Dict[str, Any]:
        """Read daemon configuration from files.
        
        Returns:
            Daemon configuration dictionary
        """
        try:
            config_file = self.data_dir / "config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('daemon', {})
            
            return {}
            
        except Exception as e:
            logger.error(f"Error reading daemon config: {e}")
            return {}
    
    async def write_daemon_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Write a command for the daemon to process.
        
        This is an atomic operation that writes a command file for the daemon
        to pick up and process.
        
        Args:
            command: Command name (e.g., 'sync_pins', 'backup_metadata')
            args: Command arguments
            
        Returns:
            True if command was written successfully
        """
        try:
            commands_dir = self.data_dir / "commands"
            commands_dir.mkdir(exist_ok=True)
            
            command_data = {
                "command": command,
                "args": args or {},
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            }
            
            # Write command with timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            command_file = commands_dir / f"{command}_{timestamp}.json"
            
            with open(command_file, 'w') as f:
                json.dump(command_data, f, indent=2)
            
            logger.info(f"Written daemon command: {command}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing daemon command {command}: {e}")
            return False
    
    async def force_sync_pins(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Request daemon to force sync pins.
        
        Args:
            backend_name: Specific backend to sync (optional)
            
        Returns:
            Operation result dictionary
        """
        command_args = {}
        if backend_name:
            command_args["backend_name"] = backend_name
        
        success = await self.write_daemon_command("sync_pins", command_args)
        return {
            "success": success,
            "command": "sync_pins",
            "backend_name": backend_name,
            "message": "Pin sync command queued for daemon" if success else "Failed to queue pin sync command"
        }
    
    async def force_backup_metadata(self) -> Dict[str, Any]:
        """Request daemon to backup metadata.
        
        Returns:
            Operation result dictionary
        """
        success = await self.write_daemon_command("backup_metadata")
        return {
            "success": success,
            "command": "backup_metadata",
            "message": "Metadata backup command queued for daemon" if success else "Failed to queue backup command"
        }
    
    async def migrate_pins(self, source_backend: str, target_backend: str, 
                          pin_cids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Request daemon to migrate pins between backends.
        
        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            pin_cids: Specific CIDs to migrate (optional)
            
        Returns:
            Operation result dictionary
        """
        command_args = {
            "source_backend": source_backend,
            "target_backend": target_backend
        }
        if pin_cids:
            command_args["pin_cids"] = pin_cids
        
        success = await self.write_daemon_command("migrate_pins", command_args)
        return {
            "success": success,
            "command": "migrate_pins",
            "source_backend": source_backend,
            "target_backend": target_backend,
            "pin_count": len(pin_cids) if pin_cids else "all",
            "message": "Pin migration command queued for daemon" if success else "Failed to queue migration command"
        }
    
    async def check_backend_health(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Request daemon to check backend health.
        
        Args:
            backend_name: Specific backend to check (optional)
            
        Returns:
            Operation result dictionary
        """
        command_args = {}
        if backend_name:
            command_args["backend_name"] = backend_name
        
        success = await self.write_daemon_command("check_health", command_args)
        return {
            "success": success,
            "command": "check_health", 
            "backend_name": backend_name,
            "message": "Health check command queued for daemon" if success else "Failed to queue health check command"
        }

    async def get_peer_stats(self) -> Dict[str, Any]:
        """Get peer statistics from the IPFS daemon."""
        try:
            # Get connected peers
            peers_result = await asyncio.create_subprocess_exec(
                'ipfs', 'swarm', 'peers',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            peers_stdout, peers_stderr = await peers_result.communicate()
            peers_list = peers_stdout.decode().strip().split('\n') if peers_stdout else []
            connected_peers = len(peers_list) if peers_list and peers_list[0] != '' else 0

            # Get bandwidth stats
            bw_result = await asyncio.create_subprocess_exec(
                'ipfs', 'stats', 'bw',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            bw_stdout, bw_stderr = await bw_result.communicate()
            bandwidth = {}
            if bw_stdout:
                bw_output = bw_stdout.decode()
                for line in bw_output.split('\n'):
                    if 'TotalIn:' in line:
                        bandwidth['total_in'] = line.split()[-1]
                    elif 'TotalOut:' in line:
                        bandwidth['total_out'] = line.split()[-1]

            return {
                "success": True,
                "peer_count": connected_peers,
                "bandwidth": bandwidth,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting peer stats from daemon: {e}")
            return {"success": False, "error": str(e)}
