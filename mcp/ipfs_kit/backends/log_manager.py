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
        self.log_lock = threading.Lock()
        
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
        # Prioritize structured JSONL logs
        for backend_name in self.backend_log_files.keys():
            json_log_file = self.log_dir / f"{backend_name}_structured.jsonl"
            if json_log_file.exists():
                try:
                    new_entries = []  # Initialize new_entries list
                    with open(json_log_file, 'r') as f:
                        for line in f:
                            try:
                                log_entry = json.loads(line)
                                
                                # Ensure log entry has an ID field
                                if 'id' not in log_entry:
                                    # Generate a unique identifier for duplicate checking
                                    timestamp = log_entry.get('timestamp', str(time.time()))
                                    message_part = log_entry.get('message', '')[:50]
                                    log_entry['id'] = f"{backend_name}_{timestamp}_{hash(message_part) % 1000000}"
                                
                                # Get existing ID for duplicate checking
                                log_entry_id = log_entry['id']
                                
                                # Add to new_entries if not already in memory_logs (avoid duplicates)
                                if not any(entry.get("id") == log_entry_id for entry in self.memory_logs[backend_name]):
                                    new_entries.append(log_entry)
                            except json.JSONDecodeError as je:
                                logger.warning(f"Malformed JSON log entry in {json_log_file}: {line.strip()}")
                                # Try to create a valid log entry from the malformed line
                                try:
                                    fallback_entry = {
                                        "id": f"{backend_name}_fallback_{int(time.time() * 1000000)}",
                                        "timestamp": datetime.now().isoformat(),
                                        "backend": backend_name,
                                        "level": "WARNING",
                                        "message": f"Malformed log entry: {line.strip()[:100]}",
                                        "extra": {"original_line": line.strip()},
                                        "formatted_time": datetime.now().strftime("%H:%M:%S"),
                                        "formatted_date": datetime.now().strftime("%Y-%m-%d")
                                    }
                                    new_entries.append(fallback_entry)
                                except Exception as fe:
                                    logger.error(f"Failed to create fallback log entry: {fe}")
                            except Exception as e:
                                logger.error(f"Error processing log entry in {json_log_file}: {e}")
                    with self.log_lock:
                        self.memory_logs[backend_name].extend(new_entries)
                except Exception as e:
                    logger.error(f"Error reading structured log file {json_log_file}: {e}")

        # Fallback to daemon-specific log collection if structured logs are not comprehensive
        self._collect_daemon_logs("ipfs", ["ipfs", "go-ipfs"])
        self._collect_daemon_logs("ipfs_cluster", ["ipfs-cluster-service"])
        self._collect_daemon_logs("lotus", ["lotus", "lotus-miner"])
        self._collect_docker_logs()

        # Generic system log collection (placeholder for more robust implementation)
        # try:
        #     # Example: Read from syslog or messages
        #     with open("/var/log/syslog", 'r') as f:
        #         for line in f.readlines()[-20:]:
        #             self.add_log_entry("system", "INFO", line.strip())
        # except FileNotFoundError:
        #     pass
        # except Exception as e:
        #     logger.error(f"Error collecting generic system logs: {e}")
    
    def _collect_daemon_logs(self, backend_name: str, process_names: List[str]):
        """Collect logs from daemon processes."""
        try:
            for process_name in process_names:
                new_entries = [] # Temporary list for new entries
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
                            log_entry = self._create_log_entry(backend_name, "INFO", f"[{process_name}] {log_line}")
                            new_entries.append(log_entry)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass
                
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
                                # Verify the PID still exists before logging
                                try:
                                    proc_check = subprocess.run(
                                        ["ps", "-p", pid.strip()],
                                        capture_output=True, text=True, timeout=1
                                    )
                                    if proc_check.returncode == 0:
                                        # For Lotus, verify it's not a Python script or other false positive
                                        if process_name == "lotus":
                                            try:
                                                cmd_result = subprocess.run(
                                                    ["ps", "-p", pid.strip(), "-o", "cmd="],
                                                    capture_output=True, text=True, timeout=1
                                                )
                                                if cmd_result.returncode == 0:
                                                    cmd_line = cmd_result.stdout.strip().lower()
                                                    # Skip Python scripts and other non-Lotus processes
                                                    if ("python" in cmd_line or 
                                                        "test" in cmd_line or
                                                        not ("/bin/lotus" in cmd_line or 
                                                             "lotus daemon" in cmd_line or 
                                                             cmd_line.strip().endswith("lotus"))):
                                                        continue
                                            except Exception:
                                                continue
                                        
                                        log_entry = self._create_log_entry(
                                            backend_name, 
                                            "INFO", 
                                            f"Process {process_name} (PID: {pid}) is running"
                                        )
                                        new_entries.append(log_entry)
                                    # If process doesn't exist, don't log anything
                                except Exception:
                                    # If we can't verify the process, don't log it
                                    pass
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass
                
                with self.log_lock:
                    self.memory_logs[backend_name].extend(new_entries)
        except Exception as e:
            logger.error(f"Error collecting daemon logs for {backend_name}: {e}")
    
    def _collect_docker_logs(self):
        """Collect logs from Docker containers."""
        new_entries = [] # Temporary list for new entries
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
                                log_entry = self._create_log_entry(backend_name, "INFO", f"[Docker:{container}] {log_line}")
                                new_entries.append(log_entry)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            # Docker not available or no containers
            pass
        except Exception as e:
            logger.error(f"Error collecting docker logs: {e}")
        
        # Add new entries to appropriate backends
        with self.log_lock:
            for backend_name in self.memory_logs.keys():
                backend_entries = [entry for entry in new_entries if entry.get('backend') == backend_name]
                if backend_entries:
                    self.memory_logs[backend_name].extend(backend_entries)
    
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
    
    def _create_log_entry(self, backend_name: str, level: str, message: str, extra_data: Optional[Dict] = None) -> Dict:
        """Helper to create a structured log entry."""
        timestamp = datetime.now().isoformat()
        return {
            "id": f"{backend_name}_{int(time.time() * 1000000)}_{hash(message) % 1000000}",
            "timestamp": timestamp,
            "backend": backend_name,
            "level": level,
            "message": message,
            "extra": extra_data or {},
            "formatted_time": datetime.now().strftime("%H:%M:%S"),
            "formatted_date": datetime.now().strftime("%Y-%m-%d")
        }

    def add_log_entry(self, backend_name: str, level: str, message: str, extra_data: Optional[Dict] = None):
        """Add a log entry for a specific backend."""
        log_entry = self._create_log_entry(backend_name, level, message, extra_data)
        
        # Add to memory storage
        with self.log_lock:
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
        with self.log_lock:
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
        with self.log_lock:
            for backend_name in self.memory_logs.keys():
                all_logs[backend_name] = self.get_backend_logs(backend_name, limit)
        return all_logs
    
    def get_recent_logs(self, minutes: int = 30, limit: int = 200) -> List[Dict]:
        """Get recent logs from all backends."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        all_logs = []
        
        with self.log_lock:
            for backend_name, logs in self.memory_logs.items():
                for log_entry in logs:
                    try:
                        log_time = datetime.fromisoformat(log_entry['timestamp'])
                        if log_time > cutoff_time:
                            all_logs.append(log_entry)
                    except (ValueError, KeyError):
                        continue
        
        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_logs[:limit]
    
    def get_error_logs(self, limit: int = 50) -> List[Dict]:
        """Get error and warning logs from all backends."""
        error_logs = []
        
        with self.log_lock:
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
            "total_log_entries": 0,
            "backends": {},
            "recent_activity": self._get_recent_activity(),
            "error_summary": self._get_error_summary()
        }
        
        with self.log_lock:
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
                stats["total_log_entries"] += len(logs)
        
        return stats
    
    def _get_recent_activity(self) -> Dict[str, int]:
        """Get recent activity counts."""
        now = datetime.now()
        activity = {
            "last_hour": 0,
            "last_24h": 0,
            "last_week": 0
        }
        
        with self.log_lock:
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
        
        with self.log_lock:
            for logs in self.memory_logs.values():
                for log_entry in logs:
                    if log_entry['level'] in ['ERROR', 'WARNING', 'CRITICAL']:
                        summary[log_entry['level']] += 1
        
        return dict(summary)
    
    def clear_backend_logs(self, backend_name: str):
        """Clear logs for a specific backend."""
        with self.log_lock:
            self.memory_logs[backend_name].clear()
        logger.info(f"Cleared logs for backend: {backend_name}")
    
    def clear_all_logs(self):
        """Clear all logs."""
        with self.log_lock:
            self.memory_logs.clear()
        logger.info("Cleared all backend logs")
    
    def export_logs(self, backend_name: Optional[str] = None, format: str = "json") -> str:
        """Export logs to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if backend_name:
            filename = f"{backend_name}_logs_{timestamp}.{format}"
            with self.log_lock:
                logs = self.get_backend_logs(backend_name, limit=None)
        else:
            filename = f"all_logs_{timestamp}.{format}"
            logs = []
            with self.log_lock:
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
