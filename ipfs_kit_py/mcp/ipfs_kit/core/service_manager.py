#!/usr/bin/env python3
"""
Robust Service Management for IPFS Kit MCP Integration

This module provides comprehensive service management including:
- IPFS daemon health monitoring
- Automatic restart capabilities
- Port conflict resolution
- Resource usage monitoring
"""

import subprocess
import psutil
import time
import socket
import logging
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import json
import requests
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """Service status enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"

@dataclass
class ServiceConfig:
    """Service configuration"""
    name: str
    command: List[str]
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    health_check_url: Optional[str] = None
    health_check_interval: int = 30
    restart_on_failure: bool = True
    max_restart_attempts: int = 3
    port: Optional[int] = None
    required_ports: List[int] = None
    dependencies: List[str] = None

@dataclass
class ServiceMetrics:
    """Service resource metrics"""
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    open_files: int
    connections: int
    uptime_seconds: float

class ServiceManager:
    """Comprehensive service management with health monitoring"""
    
    pids: List[int] = []
    logs: List[str] = []

    def __init__(self, start_monitoring: bool = True):
        self.services: Dict[str, ServiceConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.monitoring_threads: Dict[str, threading.Thread] = {}
        self.service_status: Dict[str, ServiceStatus] = {}
        self.restart_attempts: Dict[str, int] = {}
        self.monitoring_active = start_monitoring
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Start monitoring thread if enabled
        if start_monitoring:
            self.monitor_thread = threading.Thread(target=self._monitor_services, daemon=True)
            self.monitor_thread.start()
    
    def register_service(self, config: ServiceConfig) -> bool:
        """Register a service for management"""
        try:
            # Validate configuration
            if not self._validate_config(config):
                return False
            
            self.services[config.name] = config
            self.service_status[config.name] = ServiceStatus.STOPPED
            self.restart_attempts[config.name] = 0
            
            logger.info(f"Registered service: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register service {config.name}: {e}")
            return False
    
    def start_service(self, service_name: str) -> bool:
        """Start a service"""
        if service_name not in self.services:
            logger.error(f"Service {service_name} not registered")
            return False
        
        try:
            config = self.services[service_name]
            
            # Check if already running
            if self.is_service_running(service_name):
                logger.info(f"Service {service_name} is already running")
                return True
            
            # Check dependencies
            if not self._check_dependencies(service_name):
                logger.error(f"Dependencies not met for {service_name}")
                return False
            
            # Check port availability
            if not self._check_ports(config):
                logger.error(f"Required ports not available for {service_name}")
                return False
            
            # Set status to starting
            self.service_status[service_name] = ServiceStatus.STARTING
            
            # Prepare environment
            env = dict(os.environ)
            if config.env_vars:
                env.update(config.env_vars)
            
            # Start process
            process = subprocess.Popen(
                config.command,
                cwd=config.working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            self.processes[service_name] = process
            
            # Wait for startup
            if self._wait_for_startup(service_name):
                self.service_status[service_name] = ServiceStatus.RUNNING
                self.restart_attempts[service_name] = 0
                logger.info(f"Service {service_name} started successfully")
                return True
            else:
                self.service_status[service_name] = ServiceStatus.ERROR
                logger.error(f"Service {service_name} failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            self.service_status[service_name] = ServiceStatus.ERROR
            return False
    
    def stop_service(self, service_name: str, force: bool = False) -> bool:
        """Stop a service"""
        if service_name not in self.services:
            logger.error(f"Service {service_name} not registered")
            return False
        
        try:
            if service_name not in self.processes:
                self.service_status[service_name] = ServiceStatus.STOPPED
                return True
            
            self.service_status[service_name] = ServiceStatus.STOPPING
            process = self.processes[service_name]
            
            if force:
                process.kill()
            else:
                process.terminate()
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Service {service_name} did not stop gracefully, killing")
                    process.kill()
                    process.wait()
            
            del self.processes[service_name]
            self.service_status[service_name] = ServiceStatus.STOPPED
            logger.info(f"Service {service_name} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service {service_name}: {e}")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        logger.info(f"Restarting service {service_name}")
        if self.stop_service(service_name):
            time.sleep(2)  # Brief pause
            return self.start_service(service_name)
        return False
    
    def is_service_running(self, service_name: str) -> bool:
        """Check if a service is running"""
        if service_name not in self.processes:
            return False
        
        process = self.processes[service_name]
        return process.poll() is None
    
    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get current service status"""
        return self.service_status.get(service_name, ServiceStatus.UNKNOWN)
    
    def get_service_metrics(self, service_name: str) -> Optional[ServiceMetrics]:
        """Get service resource metrics"""
        if service_name not in self.processes:
            return None
        
        try:
            process = self.processes[service_name]
            psutil_proc = psutil.Process(process.pid)
            
            with psutil_proc.oneshot():
                cpu = psutil_proc.cpu_percent()
                memory_info = psutil_proc.memory_info()
                memory_percent = psutil_proc.memory_percent()
                num_files = psutil_proc.num_fds() if hasattr(psutil_proc, 'num_fds') else 0
                connections = len(psutil_proc.connections())
                create_time = psutil_proc.create_time()
                uptime = time.time() - create_time
            
            return ServiceMetrics(
                cpu_percent=cpu,
                memory_mb=memory_info.rss / 1024 / 1024,
                memory_percent=memory_percent,
                open_files=num_files,
                connections=connections,
                uptime_seconds=uptime
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def health_check(self, service_name: str) -> bool:
        """Perform health check on a service"""
        config = self.services.get(service_name)
        if not config or not config.health_check_url:
            # If no health check URL, just check if process is running
            return self.is_service_running(service_name)
        
        try:
            response = requests.get(config.health_check_url, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def _validate_config(self, config: ServiceConfig) -> bool:
        """Validate service configuration"""
        if not config.name:
            logger.error("Service name is required")
            return False
        
        if not config.command:
            logger.error(f"Command is required for service {config.name}")
            return False
        
        return True
    
    def _check_dependencies(self, service_name: str) -> bool:
        """Check if service dependencies are running"""
        config = self.services[service_name]
        if not config.dependencies:
            return True
        
        for dep in config.dependencies:
            if not self.is_service_running(dep):
                logger.error(f"Dependency {dep} not running for {service_name}")
                return False
        
        return True
    
    def _check_ports(self, config: ServiceConfig) -> bool:
        """Check if required ports are available"""
        ports_to_check = []
        if config.port:
            ports_to_check.append(config.port)
        if config.required_ports:
            ports_to_check.extend(config.required_ports)
        
        for port in ports_to_check:
            if not self._is_port_available(port):
                logger.error(f"Port {port} is not available")
                return False
        
        return True
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def _wait_for_startup(self, service_name: str, timeout: int = 30) -> bool:
        """Wait for service to start up"""
        config = self.services[service_name]
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.is_service_running(service_name):
                return False
            
            if self.health_check(service_name):
                return True
            
            time.sleep(1)
        
        return False
    
    def _monitor_services(self):
        """Background service monitoring"""
        while self.monitoring_active:
            try:
                for service_name in list(self.services.keys()):
                    self._monitor_service(service_name)
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Error in service monitoring: {e}")
    
    def _monitor_service(self, service_name: str):
        """Monitor a specific service"""
        config = self.services[service_name]
        
        # Check if process is still running
        if service_name in self.processes:
            if not self.is_service_running(service_name):
                logger.warning(f"Service {service_name} has stopped unexpectedly")
                self.service_status[service_name] = ServiceStatus.STOPPED
                del self.processes[service_name]
                
                # Attempt restart if configured
                if config.restart_on_failure:
                    self._attempt_restart(service_name)
        
        # Perform health check
        elif self.service_status.get(service_name) == ServiceStatus.RUNNING:
            if not self.health_check(service_name):
                logger.warning(f"Health check failed for {service_name}")
                if config.restart_on_failure:
                    self._attempt_restart(service_name)
    
    def _attempt_restart(self, service_name: str):
        """Attempt to restart a failed service"""
        config = self.services[service_name]
        current_attempts = self.restart_attempts.get(service_name, 0)
        
        if current_attempts < config.max_restart_attempts:
            self.restart_attempts[service_name] = current_attempts + 1
            logger.info(f"Attempting restart {current_attempts + 1}/{config.max_restart_attempts} for {service_name}")
            
            if self.start_service(service_name):
                logger.info(f"Successfully restarted {service_name}")
            else:
                logger.error(f"Failed to restart {service_name}")
        else:
            logger.error(f"Max restart attempts reached for {service_name}")
            self.service_status[service_name] = ServiceStatus.ERROR
    
    def find_available_port(self, start_port: int = 3000, max_attempts: int = 100) -> Optional[int]:
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            if self._is_port_available(port):
                return port
        return None
    
    def get_all_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all services"""
        status = {}
        for service_name in self.services:
            metrics = self.get_service_metrics(service_name)
            status[service_name] = {
                'status': self.get_service_status(service_name).value,
                'running': self.is_service_running(service_name),
                'restart_attempts': self.restart_attempts.get(service_name, 0),
                'metrics': metrics.__dict__ if metrics else None
            }
        return status
    
    def shutdown(self):
        """Shutdown service manager"""
        self.monitoring_active = False
        
        # Stop all services
        for service_name in list(self.services.keys()):
            self.stop_service(service_name)
        
        # Wait for monitor thread
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

# IPFS-specific service management
class IPFSServiceManager(ServiceManager):
    """Specialized service manager for IPFS"""
    
    def __init__(self, start_monitoring: bool = True):
        super().__init__(start_monitoring=start_monitoring)
        self._register_ipfs_service()
    
    def _register_ipfs_service(self):
        """Register IPFS daemon service"""
        config = ServiceConfig(
            name="ipfs",
            command=["ipfs", "daemon", "--routing=dhtclient"],
            health_check_url="http://127.0.0.1:5001/api/v0/version",
            health_check_interval=10,
            restart_on_failure=True,
            max_restart_attempts=3,
            port=5001,
            required_ports=[5001, 4001]
        )
        self.register_service(config)
    
    def ensure_ipfs_running(self) -> bool:
        """Ensure IPFS daemon is running"""
        if not self.is_service_running("ipfs"):
            logger.info("Starting IPFS daemon")
            return self.start_service("ipfs")
        return True
    
    def get_ipfs_info(self) -> Optional[Dict[str, Any]]:
        """Get IPFS daemon information"""
        if not self.health_check("ipfs"):
            return None
        
        try:
            response = requests.get("http://127.0.0.1:5001/api/v0/id", timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        
        return None

# Global service manager instances
import os
import sys

def _should_disable_monitoring() -> bool:
    if os.environ.get("IPFS_KIT_FAST_INIT") == "1":
        return True
    if os.environ.get("IPFS_KIT_DISABLE_SERVICE_MANAGER") == "1":
        return True
    pytest_env_markers = (
        "PYTEST_CURRENT_TEST",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_VERSION",
        "PYTEST_XDIST_WORKER",
    )
    if any(os.environ.get(key) for key in pytest_env_markers):
        return True
    argv = sys.argv or []
    if any(flag in argv for flag in ("-h", "--help")):
        return True
    return False

_disable_monitoring = _should_disable_monitoring()
service_manager = ServiceManager(start_monitoring=not _disable_monitoring)
ipfs_manager = IPFSServiceManager(start_monitoring=not _disable_monitoring)
