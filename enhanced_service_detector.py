#!/usr/bin/env python3
"""
Enhanced Service Detector for MCP Dashboard

This module provides enhanced service detection capabilities for the MCP dashboard,
identifying all available daemon and virtual filesystem services.
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil


logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    """Information about a detected service."""
    name: str
    type: str
    status: str
    description: str
    pid: Optional[int] = None
    process_name: Optional[str] = None
    command_line: Optional[List[str]] = None
    port: Optional[int] = None
    config_file: Optional[str] = None
    manager_class: Optional[str] = None


class EnhancedServiceDetector:
    """Enhanced service detector for all IPFS Kit services."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir or Path.home() / ".ipfs_kit").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def detect_all_services(self) -> List[ServiceInfo]:
        """Detect all available services including daemons, VFS, and kit services."""
        services = []
        
        # Detect daemon services
        services.extend(self._detect_daemon_services())
        
        # Detect VFS services
        services.extend(self._detect_vfs_services())
        
        # Detect kit services (virtual filesystem backends)
        services.extend(self._detect_kit_services())
        
        # Detect backend services
        services.extend(self._detect_backend_services())
        
        # Detect storage services
        services.extend(self._detect_storage_services())
        
        return services
    
    def _detect_daemon_services(self) -> List[ServiceInfo]:
        """Detect daemon processes and services."""
        services = []
        
        # IPFS daemon
        ipfs_status = self._check_ipfs_daemon()
        services.append(ServiceInfo(
            name="IPFS Daemon",
            type="daemon",
            status=ipfs_status["status"],
            description="IPFS node daemon process",
            pid=ipfs_status.get("pid"),
            process_name=ipfs_status.get("process_name"),
            command_line=ipfs_status.get("command_line"),
            port=5001,
            manager_class="ipfs_daemon_manager.IPFSDaemonManager"
        ))
        
        # IPFS Cluster Service daemon
        cluster_service_status = self._check_ipfs_cluster_service()
        services.append(ServiceInfo(
            name="IPFS Cluster Service",
            type="daemon",
            status=cluster_service_status["status"],
            description="IPFS cluster service daemon",
            pid=cluster_service_status.get("pid"),
            process_name=cluster_service_status.get("process_name"),
            command_line=cluster_service_status.get("command_line"),
            port=9094,
            manager_class="ipfs_cluster_daemon_manager.IPFSClusterDaemonManager"
        ))
        
        # IPFS Cluster Follow daemon
        cluster_follow_status = self._check_ipfs_cluster_follow()
        services.append(ServiceInfo(
            name="IPFS Cluster Follow",
            type="daemon",
            status=cluster_follow_status["status"],
            description="IPFS cluster follow daemon",
            pid=cluster_follow_status.get("pid"),
            process_name=cluster_follow_status.get("process_name"),
            command_line=cluster_follow_status.get("command_line"),
            port=9095,
            manager_class="ipfs_cluster_follow_daemon_manager.IPFSClusterFollowDaemonManager"
        ))
        
        # Lotus daemon
        lotus_status = self._check_lotus_daemon()
        services.append(ServiceInfo(
            name="Lotus Daemon",
            type="daemon",
            status=lotus_status["status"],
            description="Filecoin Lotus node daemon",
            pid=lotus_status.get("pid"),
            process_name=lotus_status.get("process_name"),
            command_line=lotus_status.get("command_line"),
            port=1234,
            manager_class="lotus_daemon.LotusDaemon"
        ))
        
        return services
    
    def _detect_vfs_services(self) -> List[ServiceInfo]:
        """Detect VFS (Virtual File System) services."""
        services = []
        
        # Check if VFS services are available
        vfs_services = [
            ("Bucket VFS Manager", "bucket_vfs_manager.BucketVFSManager", "Manages bucket-based virtual file systems"),
            ("VFS Manager", "vfs_manager.VFSManager", "Core virtual file system manager"),
            ("VFS Version Tracker", "vfs_version_tracker.VFSVersionTracker", "Tracks VFS version changes"),
            ("Enhanced VFS Extractor", "enhanced_vfs_extractor.EnhancedVFSExtractor", "Enhanced VFS content extraction"),
            ("Git VFS Translator", "git_vfs_translator.GitVFSTranslator", "Git repository VFS interface"),
        ]
        
        for name, manager_class, description in vfs_services:
            status = self._check_module_availability(manager_class)
            services.append(ServiceInfo(
                name=name,
                type="vfs",
                status=status,
                description=description,
                manager_class=manager_class
            ))
            
        return services
    
    def _detect_kit_services(self) -> List[ServiceInfo]:
        """Detect kit services (virtual filesystem backends)."""
        services = []
        
        # Define all kit services with their details
        kit_services = [
            ("IPFS Kit", "ipfs_kit.IPFSKit", "Core IPFS integration service", 5001),
            ("S3 Kit", "s3_kit.S3Kit", "Amazon S3 storage backend", None),
            ("SSHFS Kit", "sshfs_kit.SSHFSKit", "SSH filesystem backend", 22),
            ("FTP Kit", "ftp_kit.FTPKit", "FTP server backend", 21),
            ("GDrive Kit", "gdrive_kit.GDriveKit", "Google Drive backend", None),
            ("GitHub Kit", "github_kit.GitHubKit", "GitHub repository backend", None),
            ("Lotus Kit", "lotus_kit.LotusKit", "Filecoin Lotus integration", 1234),
            ("Storacha Kit", "storacha_kit.StorachaKit", "Storacha storage backend", None),
            ("Enhanced Storacha Kit", "enhanced_storacha_kit.EnhancedStorachaKit", "Enhanced Storacha integration", None),
            ("Lassie Kit", "lassie_kit.LassieKit", "Lassie retrieval service", None),
            ("Synapse Kit", "synapse_kit.SynapseKit", "Synapse integration service", None),
            ("HuggingFace Kit", "huggingface_kit.HuggingFaceKit", "HuggingFace model backend", None),
            ("Aria2 Kit", "aria2_kit.Aria2Kit", "Aria2 download backend", 6800),
        ]
        
        for name, manager_class, description, port in kit_services:
            status = self._check_module_availability(manager_class)
            services.append(ServiceInfo(
                name=name,
                type="kit",
                status=status,
                description=description,
                port=port,
                manager_class=manager_class
            ))
            
        return services
    
    def _detect_backend_services(self) -> List[ServiceInfo]:
        """Detect backend services."""
        services = []
        
        backend_services = [
            ("S3 Backend", "backends.s3_backend.S3Backend", "Amazon S3 storage backend adapter"),
            ("IPFS Backend", "backends.ipfs_backend.IPFSBackend", "IPFS storage backend adapter"),
            ("Filesystem Backend", "backends.filesystem_backend.FilesystemBackend", "Local filesystem backend adapter"),
        ]
        
        for name, manager_class, description in backend_services:
            status = self._check_module_availability(manager_class)
            services.append(ServiceInfo(
                name=name,
                type="backend",
                status=status,
                description=description,
                manager_class=manager_class
            ))
            
        return services
    
    def _detect_storage_services(self) -> List[ServiceInfo]:
        """Detect additional storage and management services."""
        services = []
        
        storage_services = [
            ("Enhanced Daemon Manager", "enhanced_daemon_manager.EnhancedDaemonManager", "Enhanced daemon process management"),
            ("Intelligent Daemon Manager", "intelligent_daemon_manager.IntelligentDaemonManager", "AI-powered daemon management"),
            ("Service Manager", "service_manager.ServiceManager", "Core service management interface"),
            ("Backend Manager", "backend_manager.BackendManager", "Storage backend management"),
            ("Unified Bucket Interface", "unified_bucket_interface.UnifiedBucketInterface", "Unified bucket API interface"),
        ]
        
        for name, manager_class, description in storage_services:
            status = self._check_module_availability(manager_class)
            services.append(ServiceInfo(
                name=name,
                type="storage",
                status=status,
                description=description,
                manager_class=manager_class
            ))
            
        return services
    
    def _check_ipfs_daemon(self) -> Dict[str, Any]:
        """Check IPFS daemon status."""
        # Look for IPFS daemon process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'ipfs' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline'] or []
                    if 'daemon' in ' '.join(cmdline).lower():
                        return {
                            "status": "running",
                            "pid": proc.info['pid'],
                            "process_name": proc.info['name'],
                            "command_line": cmdline
                        }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        # Check if IPFS API is responding
        try:
            result = subprocess.run(
                ["ipfs", "version"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                return {"status": "available"}
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
            
        return {"status": "stopped"}
    
    def _check_ipfs_cluster_service(self) -> Dict[str, Any]:
        """Check IPFS Cluster Service daemon status."""
        # Look for cluster service process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                cmdline_str = ' '.join(cmdline).lower()
                if 'ipfs-cluster-service' in cmdline_str or 'cluster-service' in cmdline_str:
                    return {
                        "status": "running",
                        "pid": proc.info['pid'],
                        "process_name": proc.info['name'],
                        "command_line": cmdline
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return {"status": "stopped"}
    
    def _check_ipfs_cluster_follow(self) -> Dict[str, Any]:
        """Check IPFS Cluster Follow daemon status."""
        # Look for cluster follow process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                cmdline_str = ' '.join(cmdline).lower()
                if 'ipfs-cluster-follow' in cmdline_str or 'cluster-follow' in cmdline_str:
                    return {
                        "status": "running",
                        "pid": proc.info['pid'],
                        "process_name": proc.info['name'],
                        "command_line": cmdline
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return {"status": "stopped"}
    
    def _check_lotus_daemon(self) -> Dict[str, Any]:
        """Check Lotus daemon status."""
        # Look for lotus daemon process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                cmdline_str = ' '.join(cmdline).lower()
                if 'lotus' in cmdline_str and 'daemon' in cmdline_str:
                    return {
                        "status": "running",
                        "pid": proc.info['pid'],
                        "process_name": proc.info['name'],
                        "command_line": cmdline
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return {"status": "stopped"}
    
    def _check_module_availability(self, module_path: str) -> str:
        """Check if a Python module/class is available for import."""
        try:
            # Split module path like "ipfs_kit.IPFSKit" 
            if '.' in module_path:
                module_name, class_name = module_path.rsplit('.', 1)
            else:
                module_name = module_path
                class_name = None
                
            # Try to import the module from ipfs_kit_py
            full_module_path = f"ipfs_kit_py.{module_name}"
            
            # Check if module file exists first
            module_file_path = module_name.replace('.', '/') + '.py'
            expected_path = Path(__file__).parent / "ipfs_kit_py" / module_file_path
            
            if not expected_path.exists():
                # Try alternative paths
                alt_path = Path(__file__).parent / module_file_path
                if not alt_path.exists():
                    return "unavailable"
            
            # Try dynamic import
            try:
                module = __import__(full_module_path, fromlist=[class_name] if class_name else [])
                if class_name and hasattr(module, class_name):
                    return "available"
                elif not class_name:
                    return "available"
                else:
                    return "misconfigured"
            except ImportError:
                return "import_error"
                
        except Exception as e:
            logger.debug(f"Error checking module {module_path}: {e}")
            return "error"
    
    def get_service_control_actions(self, service: ServiceInfo) -> List[str]:
        """Get available control actions for a service."""
        actions = []
        
        if service.type == "daemon":
            if service.status == "running":
                actions.extend(["stop", "restart", "status"])
            else:
                actions.extend(["start", "status"])
            actions.append("configure")
            
        elif service.type in ["kit", "backend", "vfs", "storage"]:
            if service.status == "available":
                actions.extend(["enable", "disable", "configure", "status"])
            else:
                actions.extend(["install", "configure", "status"])
                
        return actions


def test_service_detection():
    """Test the service detection functionality."""
    detector = EnhancedServiceDetector()
    services = detector.detect_all_services()
    
    print(f"Detected {len(services)} services:")
    
    for service_type in ["daemon", "vfs", "kit", "backend", "storage"]:
        type_services = [s for s in services if s.type == service_type]
        print(f"\n{service_type.upper()} Services ({len(type_services)}):")
        for service in type_services:
            status_emoji = "🟢" if service.status == "running" else "🟡" if service.status == "available" else "🔴"
            print(f"  {status_emoji} {service.name} - {service.status}")
            if service.pid:
                print(f"      PID: {service.pid}")
            if service.manager_class:
                print(f"      Manager: {service.manager_class}")


if __name__ == "__main__":
    test_service_detection()