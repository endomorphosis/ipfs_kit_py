"""
Comprehensive logging management for IPFS Kit backends.
Collects, stores, and exposes logs from all backend systems.
"""

import logging
import logging.handlers
import asyncio
import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict
from datetime import datetime, timedelta
import threading
import subprocess

logger = logging.getLogger(__name__)


class BackendLogManager:
    """Manages logging for all backend systems."""
    
    def __init__(self, log_dir: str = "/tmp/ipfs_kit_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # In-memory log storage for quick access
        self.memory_logs = defaultdict(lambda: deque(maxlen=1000))
        self.log_levels = defaultdict(lambda: "INFO")
        
        # Backend-specific log files
        self.backend_log_files = {}
        
        # Log rotation settings
        self.max_log_size = 10 * 1024 * 1024  # 10MB
        self.max_log_files = 5
        
        # Initialize backend loggers
        self._setup_backend_loggers()
        
        # Start log collection thread
        self._start_log_collector()
        
    def _setup_backend_loggers(self):
        """Setup individual loggers for each backend."""
        backends = [
            "ipfs", "ipfs_cluster", "ipfs_cluster_follow", 
            "lotus", "storacha", "gdrive", "synapse", "s3", 
            "huggingface", "parquet"
        ]
        
        for backend_name in backends:
            log_file = self.log_dir / f"{backend_name}.log"
            self.backend_log_files[backend_name] = log_file
            
            # Create backend-specific logger
            backend_logger = logging.getLogger(f"ipfs_kit.backend.{backend_name}")
            backend_logger.setLevel(logging.INFO)
            
            # Create file handler with rotation
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.max_log_size,
                backupCount=self.max_log_files
            )
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            backend_logger.addHandler(handler)
            
            logger.info(f"✓ Setup logger for backend: {backend_name}")
    
    def _start_log_collector(self):
        """Start background thread to collect system logs."""
        def collect_logs():
            while True:
                try:
                    self._collect_system_logs()
                    time.sleep(5)  # Collect every 5 seconds
                except Exception as e:
                    logger.error(f"Error in log collector: {e}")
                    time.sleep(10)
        
        collector_thread = threading.Thread(target=collect_logs, daemon=True)
        collector_thread.start()
        logger.info("✓ Started background log collector")
    
    def _collect_system_logs(self):
        """Collect logs from system processes and services."""
        # Collect IPFS daemon logs
        self._collect_daemon_logs("ipfs", ["ipfs", "go-ipfs"])
        
        # Collect IPFS Cluster logs
        self._collect_daemon_logs("ipfs_cluster", ["ipfs-cluster-service"])
        
        # Collect Lotus logs
        self._collect_daemon_logs("lotus", ["lotus", "lotus-miner"])
        
        # Collect Docker container logs if applicable
        self._collect_docker_logs()
    
    def _collect_daemon_logs(self, backend_name: str, process_names: List[str]):
        """Collect logs from daemon processes."""
        try:
            for process_name in process_names:
                # Try to get logs from journalctl
                try:
                    result = subprocess.run(
                        ["journalctl", "-u", process_name, "--since", "5 minutes ago", "-n", "50"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        logs = result.stdout.strip().split('\n')
                        for log_line in logs[-10:]:  # Last 10 lines
                            self.add_log_entry(backend_name, "INFO", f"[{process_name}] {log_line}")
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    continue
                
                # Try to get logs from process output
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", process_name],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        pids = result.stdout.strip().split('\n')
                        for pid in pids[:1]:  # Check first PID only
                            if pid.strip():
                                self.add_log_entry(
                                    backend_name, 
                                    "INFO", 
                                    f"Process {process_name} (PID: {pid}) is running"
                                )
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    continue
                    
        except Exception as e:
            logger.error(f"Error collecting daemon logs for {backend_name}: {e}")
    
    def _collect_docker_logs(self):
        """Collect logs from Docker containers."""
        try:
            # Get running containers
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                containers = result.stdout.strip().split('\n')
                for container in containers:
                    if any(backend in container.lower() for backend in ['ipfs', 'lotus', 'cluster']):
                        # Get recent logs from container
                        log_result = subprocess.run(
                            ["docker", "logs", "--tail", "5", container],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if log_result.returncode == 0 and log_result.stdout.strip():
                            backend_name = self._map_container_to_backend(container)
                            logs = log_result.stdout.strip().split('\n')
                            for log_line in logs:
                                self.add_log_entry(backend_name, "INFO", f"[Docker:{container}] {log_line}")
                                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            # Docker not available or no containers
            pass
        except Exception as e:
            logger.error(f"Error collecting docker logs: {e}")
    
    def _map_container_to_backend(self, container_name: str) -> str:
        """Map container name to backend name."""
        name_lower = container_name.lower()
        if 'ipfs' in name_lower and 'cluster' in name_lower:
            return "ipfs_cluster"
        elif 'ipfs' in name_lower:
            return "ipfs"
        elif 'lotus' in name_lower:
            return "lotus"
        else:
            return "unknown"
    
    def add_log_entry(self, backend_name: str, level: str, message: str, extra_data: Optional[Dict] = None):
        """Add a log entry for a specific backend."""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            "id": f"{backend_name}_{int(time.time() * 1000000)}",  # Unique ID
            "timestamp": timestamp,
            "backend": backend_name,
            "level": level,
            "message": message,
            "extra": extra_data or {},
            "formatted_time": datetime.now().strftime("%H:%M:%S"),
            "formatted_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        # Add to memory storage
        self.memory_logs[backend_name].append(log_entry)
        
        # Write to backend-specific log file
        backend_logger = logging.getLogger(f"ipfs_kit.backend.{backend_name}")
        getattr(backend_logger, level.lower(), backend_logger.info)(f"[{backend_name}] {message}")
        
        # Also write to JSON log for structured access
        json_log_file = self.log_dir / f"{backend_name}_structured.jsonl"
        try:
            with open(json_log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write structured log for {backend_name}: {e}")
    
    def add_operation_log(self, backend_name: str, operation: str, status: str, details: Optional[Dict] = None):
        """Add an operation-specific log entry."""
        level = "INFO" if status == "success" else "WARNING" if status == "warning" else "ERROR"
        message = f"Operation '{operation}' {status}"
        if details:
            message += f" - {details.get('summary', '')}"
        
        extra_data = {
            "operation": operation,
            "status": status,
            "details": details or {}
        }
        
        self.add_log_entry(backend_name, level, message, extra_data)
    
    def get_backend_logs(self, backend_name: str, limit: Optional[int] = 100, level: Optional[str] = None) -> List[Dict]:
        """Get logs for a specific backend."""
        logs = list(self.memory_logs[backend_name])
        
        # Filter by level if specified
        if level:
            logs = [log for log in logs if log['level'].upper() == level.upper()]
        
        # Return most recent logs first
        if limit is None:
            return logs[::-1]
        return logs[-limit:][::-1]
    
    def get_all_backend_logs(self, limit: Optional[int] = 50) -> Dict[str, List[Dict]]:
        """Get logs for all backends."""
        all_logs = {}
        for backend_name in self.memory_logs.keys():
            all_logs[backend_name] = self.get_backend_logs(backend_name, limit)
        return all_logs
    
    def get_recent_logs(self, minutes: int = 30, limit: int = 200) -> List[Dict]:
        """Get recent logs from all backends."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        all_logs = []
        
        for backend_name, logs in self.memory_logs.items():
            for log_entry in logs:
                log_time = datetime.fromisoformat(log_entry['timestamp'])
                if log_time >= cutoff_time:
                    all_logs.append(log_entry)
        
        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_logs[:limit]
    
    def get_error_logs(self, limit: int = 50) -> List[Dict]:
        """Get error and warning logs from all backends."""
        error_logs = []
        
        for backend_name, logs in self.memory_logs.items():
            for log_entry in logs:
                if log_entry['level'] in ['ERROR', 'WARNING', 'CRITICAL']:
                    error_logs.append(log_entry)
        
        # Sort by timestamp (most recent first)
        error_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return error_logs[:limit]
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics for dashboard."""
        stats = {
            "total_backends": len(self.memory_logs),
            "total_log_entries": sum(len(logs) for logs in self.memory_logs.values()),
            "backends": {},
            "recent_activity": self._get_recent_activity(),
            "error_summary": self._get_error_summary()
        }
        
        for backend_name, logs in self.memory_logs.items():
            backend_stats = {
                "total_entries": len(logs),
                "levels": defaultdict(int),
                "last_entry": None
            }
            
            for log_entry in logs:
                backend_stats["levels"][log_entry['level']] += 1
                if not backend_stats["last_entry"] or log_entry['timestamp'] > backend_stats["last_entry"]:
                    backend_stats["last_entry"] = log_entry['timestamp']
            
            stats["backends"][backend_name] = {
                "total_entries": backend_stats["total_entries"],
                "levels": dict(backend_stats["levels"]),
                "last_entry": backend_stats["last_entry"]
            }
        
        return stats
    
    def _get_recent_activity(self) -> Dict[str, int]:
        """Get recent activity counts."""
        now = datetime.now()
        activity = {
            "last_hour": 0,
            "last_24h": 0,
            "last_week": 0
        }
        
        for logs in self.memory_logs.values():
            for log_entry in logs:
                log_time = datetime.fromisoformat(log_entry['timestamp'])
                time_diff = now - log_time
                
                if time_diff <= timedelta(hours=1):
                    activity["last_hour"] += 1
                if time_diff <= timedelta(days=1):
                    activity["last_24h"] += 1
                if time_diff <= timedelta(weeks=1):
                    activity["last_week"] += 1
        
        return activity
    
    def _get_error_summary(self) -> Dict[str, int]:
        """Get error summary statistics."""
        summary = defaultdict(int)
        
        for logs in self.memory_logs.values():
            for log_entry in logs:
                if log_entry['level'] in ['ERROR', 'WARNING', 'CRITICAL']:
                    summary[log_entry['level']] += 1
        
        return dict(summary)
    
    def clear_backend_logs(self, backend_name: str):
        """Clear logs for a specific backend."""
        self.memory_logs[backend_name].clear()
        logger.info(f"Cleared logs for backend: {backend_name}")
    
    def clear_all_logs(self):
        """Clear all logs."""
        self.memory_logs.clear()
        logger.info("Cleared all backend logs")
    
    def export_logs(self, backend_name: Optional[str] = None, format: str = "json") -> str:
        """Export logs to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if backend_name:
            filename = f"{backend_name}_logs_{timestamp}.{format}"
            logs = self.get_backend_logs(backend_name, limit=None)
        else:
            filename = f"all_logs_{timestamp}.{format}"
            logs = []
            for backend, backend_logs in self.get_all_backend_logs(limit=None).items():
                logs.extend(backend_logs)
        
        export_path = self.log_dir / filename
        
        try:
            if format == "json":
                with open(export_path, 'w') as f:
                    json.dump(logs, f, indent=2)
            elif format == "txt":
                with open(export_path, 'w') as f:
                    for log_entry in logs:
                        f.write(f"{log_entry['timestamp']} [{log_entry['backend']}] {log_entry['level']}: {log_entry['message']}\n")
            
            logger.info(f"Exported logs to: {export_path}")
            return str(export_path)
            
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            raise
