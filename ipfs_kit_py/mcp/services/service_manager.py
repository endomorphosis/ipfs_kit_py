#!/usr/bin/env python3
"""
Service Manager for IPFS Kit Storage Backends.

This module provides a comprehensive interface for managing storage backends
and services used by IPFS Kit. It handles detection, configuration, and
control of all supported storage services including:

- IPFS (native IPFS daemon)
- IPFS Cluster (cluster service)
- IPFS Cluster Follow (follower service)
- S3 (Amazon S3 or compatible)
- FTP (File Transfer Protocol)
- SSHFS (SSH File System)
- GitHub (GitHub repository storage)
- HuggingFace (HuggingFace Hub)
- Lotus (Filecoin storage)
- Synapse (Matrix/Synapse storage)
- Storacha (Web3.Storage)
- Parquet (Apache Parquet files)
- Arrow (Apache Arrow files)
"""

import os
import json
import logging
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Enumeration of possible service statuses."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"
    NOT_CONFIGURED = "not_configured"
    CONFIGURING = "configuring"
    STARTING = "starting"
    STOPPING = "stopping"


class ServiceType(Enum):
    """Enumeration of supported service types."""
    IPFS = "ipfs"
    IPFS_CLUSTER = "ipfs_cluster"
    IPFS_CLUSTER_FOLLOW = "ipfs_cluster_follow"
    S3 = "s3"
    FTP = "ftp"
    SSHFS = "sshfs"
    GITHUB = "github"
    HUGGINGFACE = "huggingface"
    LOTUS = "lotus"
    SYNAPSE = "synapse"
    STORACHA = "storacha"
    PARQUET = "parquet"
    ARROW = "arrow"


@dataclass
class ServiceInfo:
    """Information about a storage service."""
    service_type: ServiceType
    name: str
    status: ServiceStatus
    description: str
    config: Optional[Dict[str, Any]] = None
    pid: Optional[int] = None
    port: Optional[int] = None
    endpoint: Optional[str] = None
    version: Optional[str] = None
    health_check_url: Optional[str] = None
    last_check: Optional[float] = None
    error_message: Optional[str] = None
    actions: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.actions is None:
            self.actions = []
        if self.last_check is None:
            self.last_check = time.time()


class ServiceManager:
    """
    Comprehensive service manager for IPFS Kit storage backends.
    
    This class provides:
    - Detection of installed services and their current status
    - Configuration management via ~/.ipfs_kit/ metadata files
    - Service control operations (start/stop/restart)
    - Health monitoring and status reporting
    - Integration with IPFS Kit components
    """
    
    def __init__(self, metadata_dir: Optional[str] = None):
        """
        Initialize the service manager.
        
        Args:
            metadata_dir: Directory for service metadata. Defaults to ~/.ipfs_kit/
        """
        self.metadata_dir = Path(metadata_dir or os.path.expanduser("~/.ipfs_kit"))
        self.metadata_dir.mkdir(exist_ok=True)
        
        # Service registry
        self.services: Dict[str, ServiceInfo] = {}
        
        # Configuration
        self.config_file = self.metadata_dir / "services.json"
        self.load_config()
        
        logger.info(f"ServiceManager initialized with metadata dir: {self.metadata_dir}")
    
    def load_config(self):
        """Load service configuration from metadata files."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    
                for service_id, service_data in config_data.items():
                    try:
                        # Convert status and type from strings back to enums
                        service_data['status'] = ServiceStatus(service_data['status'])
                        service_data['service_type'] = ServiceType(service_data['service_type'])
                        
                        service_info = ServiceInfo(**service_data)
                        self.services[service_id] = service_info
                        
                    except Exception as e:
                        logger.error(f"Failed to load service {service_id}: {e}")
                        
                logger.info(f"Loaded {len(self.services)} services from config")
            else:
                logger.info("No existing service config found, will create default services")
                self._create_default_services()
                
        except Exception as e:
            logger.error(f"Failed to load service config: {e}")
            self._create_default_services()
    
    def save_config(self):
        """Save current service configuration to metadata files."""
        try:
            # Convert services to serializable format
            config_data = {}
            for service_id, service_info in self.services.items():
                service_dict = asdict(service_info)
                # Convert enums to strings for JSON serialization
                service_dict['status'] = service_info.status.value
                service_dict['service_type'] = service_info.service_type.value
                config_data[service_id] = service_dict
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
            logger.info(f"Saved configuration for {len(self.services)} services")
            
        except Exception as e:
            logger.error(f"Failed to save service config: {e}")
    
    def _create_default_services(self):
        """Create default service definitions."""
        default_services = [
            ServiceInfo(
                service_type=ServiceType.IPFS,
                name="IPFS Daemon",
                status=ServiceStatus.UNKNOWN,
                description="InterPlanetary File System daemon for content-addressed storage",
                port=5001,
                endpoint="http://127.0.0.1:5001",
                health_check_url="http://127.0.0.1:5001/api/v0/id",
                actions=["start", "stop", "restart", "configure", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.IPFS_CLUSTER,
                name="IPFS Cluster",
                status=ServiceStatus.UNKNOWN,
                description="IPFS Cluster service for coordinated pinning and content management",
                port=9094,
                endpoint="http://127.0.0.1:9094",
                health_check_url="http://127.0.0.1:9094/id",
                actions=["start", "stop", "restart", "configure", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.S3,
                name="S3 Storage",
                status=ServiceStatus.UNKNOWN,
                description="Amazon S3 or S3-compatible object storage backend",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.HUGGINGFACE,
                name="HuggingFace Hub",
                status=ServiceStatus.UNKNOWN,
                description="HuggingFace Hub integration for model and dataset storage",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.GITHUB,
                name="GitHub Storage",
                status=ServiceStatus.UNKNOWN,
                description="GitHub repository-based storage backend",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.STORACHA,
                name="Storacha (Web3.Storage)",
                status=ServiceStatus.UNKNOWN,
                description="Web3.Storage (formerly NFT.Storage) for decentralized storage",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.LOTUS,
                name="Lotus (Filecoin)",
                status=ServiceStatus.UNKNOWN,
                description="Filecoin Lotus node for blockchain-based storage",
                port=1234,
                endpoint="http://127.0.0.1:1234/rpc/v0",
                actions=["start", "stop", "restart", "configure", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.FTP,
                name="FTP Server",
                status=ServiceStatus.UNKNOWN,
                description="FTP server for file transfer protocol access",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.SSHFS,
                name="SSHFS Mount",
                status=ServiceStatus.UNKNOWN,
                description="SSH File System for remote file system mounting",
                actions=["configure", "mount", "unmount", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.SYNAPSE,
                name="Matrix Synapse",
                status=ServiceStatus.UNKNOWN,
                description="Matrix Synapse server for distributed messaging and file storage",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.PARQUET,
                name="Parquet Handler",
                status=ServiceStatus.UNKNOWN,
                description="Apache Parquet file format handler for structured data",
                actions=["configure", "test", "status"]
            ),
            ServiceInfo(
                service_type=ServiceType.ARROW,
                name="Arrow Handler",
                status=ServiceStatus.UNKNOWN,
                description="Apache Arrow columnar data format handler",
                actions=["configure", "test", "status"]
            ),
        ]
        
        for service in default_services:
            service_id = service.service_type.value
            self.services[service_id] = service
            
        # Save the default configuration
        self.save_config()
        logger.info(f"Created default configuration with {len(default_services)} services")
    
    async def detect_services(self) -> Dict[str, ServiceInfo]:
        """
        Detect currently installed and running services.
        
        Returns:
            Dictionary of service ID to ServiceInfo for all detected services
        """
        logger.info("Starting service detection...")
        
        detection_tasks = []
        for service_id, service in self.services.items():
            task = asyncio.create_task(self._detect_service(service_id, service))
            detection_tasks.append(task)
        
        await asyncio.gather(*detection_tasks, return_exceptions=True)
        
        # Save updated status
        self.save_config()
        
        logger.info(f"Service detection completed. Found {len([s for s in self.services.values() if s.status == ServiceStatus.RUNNING])} running services")
        return self.services.copy()
    
    async def _detect_service(self, service_id: str, service: ServiceInfo):
        """Detect the status of a specific service."""
        try:
            if service.service_type == ServiceType.IPFS:
                await self._detect_ipfs_service(service)
            elif service.service_type == ServiceType.IPFS_CLUSTER:
                await self._detect_ipfs_cluster_service(service)
            elif service.service_type == ServiceType.S3:
                await self._detect_s3_service(service)
            elif service.service_type == ServiceType.HUGGINGFACE:
                await self._detect_huggingface_service(service)
            elif service.service_type == ServiceType.GITHUB:
                await self._detect_github_service(service)
            elif service.service_type == ServiceType.STORACHA:
                await self._detect_storacha_service(service)
            elif service.service_type == ServiceType.LOTUS:
                await self._detect_lotus_service(service)
            else:
                # For other services, do basic binary detection
                await self._detect_generic_service(service)
                
            service.last_check = time.time()
            service.error_message = None
            
        except Exception as e:
            logger.error(f"Failed to detect service {service_id}: {e}")
            service.status = ServiceStatus.ERROR
            service.error_message = str(e)
            service.last_check = time.time()
    
    async def _detect_ipfs_service(self, service: ServiceInfo):
        """Detect IPFS daemon status."""
        try:
            # Check if IPFS binary is available
            result = await asyncio.create_subprocess_exec(
                'which', 'ipfs',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "IPFS binary not found in PATH"
                return
            
            # Check if daemon is running
            try:
                result = await asyncio.create_subprocess_exec(
                    'ipfs', 'id',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    # Parse version info
                    result = await asyncio.create_subprocess_exec(
                        'ipfs', 'version',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    version_out, _ = await result.communicate()
                    if result.returncode == 0:
                        service.version = version_out.decode().strip()
                    
                    service.status = ServiceStatus.RUNNING
                    service.config = json.loads(stdout.decode()) if stdout else {}
                else:
                    service.status = ServiceStatus.STOPPED
                    service.error_message = stderr.decode() if stderr else "IPFS daemon not running"
                    
            except Exception as e:
                service.status = ServiceStatus.STOPPED
                service.error_message = str(e)
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check IPFS: {e}"
    
    async def _detect_ipfs_cluster_service(self, service: ServiceInfo):
        """Detect IPFS Cluster service status."""
        try:
            # Check if IPFS Cluster binary is available
            result = await asyncio.create_subprocess_exec(
                'which', 'ipfs-cluster-service',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "ipfs-cluster-service binary not found in PATH"
                return
            
            # Check if cluster service is running
            try:
                result = await asyncio.create_subprocess_exec(
                    'ipfs-cluster-ctl', 'id',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    service.status = ServiceStatus.RUNNING
                    service.config = json.loads(stdout.decode()) if stdout else {}
                else:
                    service.status = ServiceStatus.STOPPED
                    service.error_message = stderr.decode() if stderr else "IPFS Cluster service not running"
                    
            except Exception as e:
                service.status = ServiceStatus.STOPPED
                service.error_message = str(e)
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check IPFS Cluster: {e}"
    
    async def _detect_s3_service(self, service: ServiceInfo):
        """Detect S3 service configuration."""
        try:
            # Check for AWS credentials and configuration
            aws_config_file = Path.home() / ".aws" / "config"
            aws_credentials_file = Path.home() / ".aws" / "credentials"
            
            # Check environment variables
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            
            if (aws_config_file.exists() or aws_credentials_file.exists() or 
                (aws_access_key and aws_secret_key)):
                service.status = ServiceStatus.RUNNING
                service.config = {
                    "has_config_file": aws_config_file.exists(),
                    "has_credentials_file": aws_credentials_file.exists(),
                    "has_env_vars": bool(aws_access_key and aws_secret_key)
                }
            else:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "No AWS credentials found"
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check S3 config: {e}"
    
    async def _detect_huggingface_service(self, service: ServiceInfo):
        """Detect HuggingFace Hub configuration."""
        try:
            # Check for HuggingFace token
            hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
            hf_cache_dir = os.getenv("HF_HOME") or Path.home() / ".cache" / "huggingface"
            
            if hf_token or hf_cache_dir.exists():
                service.status = ServiceStatus.RUNNING
                service.config = {
                    "has_token": bool(hf_token),
                    "cache_dir": str(hf_cache_dir),
                    "cache_exists": hf_cache_dir.exists()
                }
            else:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "No HuggingFace token found"
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check HuggingFace config: {e}"
    
    async def _detect_github_service(self, service: ServiceInfo):
        """Detect GitHub service configuration."""
        try:
            # Check for GitHub token
            gh_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
            
            # Check for git configuration
            try:
                result = await asyncio.create_subprocess_exec(
                    'git', 'config', 'user.name',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                has_git_config = result.returncode == 0
            except:
                has_git_config = False
            
            if gh_token or has_git_config:
                service.status = ServiceStatus.RUNNING
                service.config = {
                    "has_token": bool(gh_token),
                    "has_git_config": has_git_config
                }
            else:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "No GitHub token or git configuration found"
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check GitHub config: {e}"
    
    async def _detect_storacha_service(self, service: ServiceInfo):
        """Detect Storacha service configuration."""
        try:
            # Check for Web3.Storage token
            w3s_token = os.getenv("WEB3_STORAGE_TOKEN") or os.getenv("W3S_TOKEN")
            
            if w3s_token:
                service.status = ServiceStatus.RUNNING
                service.config = {
                    "has_token": True
                }
            else:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "No Web3.Storage token found"
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check Storacha config: {e}"
    
    async def _detect_lotus_service(self, service: ServiceInfo):
        """Detect Lotus (Filecoin) service status."""
        try:
            # Check if Lotus binary is available
            result = await asyncio.create_subprocess_exec(
                'which', 'lotus',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                service.status = ServiceStatus.NOT_CONFIGURED
                service.error_message = "Lotus binary not found in PATH"
                return
            
            # Check if Lotus daemon is running
            try:
                result = await asyncio.create_subprocess_exec(
                    'lotus', 'sync', 'status',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    service.status = ServiceStatus.RUNNING
                    service.config = {"sync_output": stdout.decode().strip()}
                else:
                    service.status = ServiceStatus.STOPPED
                    service.error_message = stderr.decode() if stderr else "Lotus daemon not running"
                    
            except Exception as e:
                service.status = ServiceStatus.STOPPED
                service.error_message = str(e)
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to check Lotus: {e}"
    
    async def _detect_generic_service(self, service: ServiceInfo):
        """Generic service detection for services without specific logic."""
        try:
            # Default to not configured for now
            service.status = ServiceStatus.NOT_CONFIGURED
            service.error_message = "Service detection not implemented"
            
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = f"Failed to detect service: {e}"
    
    async def start_service(self, service_id: str) -> bool:
        """
        Start a specific service.
        
        Args:
            service_id: ID of the service to start
            
        Returns:
            True if service was started successfully, False otherwise
        """
        if service_id not in self.services:
            logger.error(f"Service {service_id} not found")
            return False
        
        service = self.services[service_id]
        service.status = ServiceStatus.STARTING
        
        try:
            success = False
            
            if service.service_type == ServiceType.IPFS:
                success = await self._start_ipfs_service(service)
            elif service.service_type == ServiceType.IPFS_CLUSTER:
                success = await self._start_ipfs_cluster_service(service)
            elif service.service_type == ServiceType.LOTUS:
                success = await self._start_lotus_service(service)
            else:
                logger.warning(f"Start operation not implemented for service type {service.service_type}")
                service.status = ServiceStatus.UNKNOWN
                return False
            
            if success:
                service.status = ServiceStatus.RUNNING
                service.error_message = None
            else:
                service.status = ServiceStatus.ERROR
            
            self.save_config()
            return success
            
        except Exception as e:
            logger.error(f"Failed to start service {service_id}: {e}")
            service.status = ServiceStatus.ERROR
            service.error_message = str(e)
            self.save_config()
            return False
    
    async def stop_service(self, service_id: str) -> bool:
        """
        Stop a specific service.
        
        Args:
            service_id: ID of the service to stop
            
        Returns:
            True if service was stopped successfully, False otherwise
        """
        if service_id not in self.services:
            logger.error(f"Service {service_id} not found")
            return False
        
        service = self.services[service_id]
        service.status = ServiceStatus.STOPPING
        
        try:
            success = False
            
            if service.service_type == ServiceType.IPFS:
                success = await self._stop_ipfs_service(service)
            elif service.service_type == ServiceType.IPFS_CLUSTER:
                success = await self._stop_ipfs_cluster_service(service)
            elif service.service_type == ServiceType.LOTUS:
                success = await self._stop_lotus_service(service)
            else:
                logger.warning(f"Stop operation not implemented for service type {service.service_type}")
                service.status = ServiceStatus.UNKNOWN
                return False
            
            if success:
                service.status = ServiceStatus.STOPPED
                service.error_message = None
            else:
                service.status = ServiceStatus.ERROR
            
            self.save_config()
            return success
            
        except Exception as e:
            logger.error(f"Failed to stop service {service_id}: {e}")
            service.status = ServiceStatus.ERROR
            service.error_message = str(e)
            self.save_config()
            return False
    
    async def _start_ipfs_service(self, service: ServiceInfo) -> bool:
        """Start IPFS daemon."""
        try:
            result = await asyncio.create_subprocess_exec(
                'ipfs', 'daemon', '--enable-pubsub-experiment',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Check if it started successfully
            await self._detect_ipfs_service(service)
            
            return service.status == ServiceStatus.RUNNING
            
        except Exception as e:
            logger.error(f"Failed to start IPFS service: {e}")
            return False
    
    async def _stop_ipfs_service(self, service: ServiceInfo) -> bool:
        """Stop IPFS daemon."""
        try:
            # Try graceful shutdown first
            result = await asyncio.create_subprocess_exec(
                'ipfs', 'shutdown',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            # Give it a moment to shutdown
            await asyncio.sleep(2)
            
            # Check if it stopped successfully
            await self._detect_ipfs_service(service)
            
            return service.status == ServiceStatus.STOPPED
            
        except Exception as e:
            logger.error(f"Failed to stop IPFS service: {e}")
            return False
    
    async def _start_ipfs_cluster_service(self, service: ServiceInfo) -> bool:
        """Start IPFS Cluster service."""
        try:
            result = await asyncio.create_subprocess_exec(
                'ipfs-cluster-service', 'daemon',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Give it a moment to start
            await asyncio.sleep(3)
            
            # Check if it started successfully
            await self._detect_ipfs_cluster_service(service)
            
            return service.status == ServiceStatus.RUNNING
            
        except Exception as e:
            logger.error(f"Failed to start IPFS Cluster service: {e}")
            return False
    
    async def _stop_ipfs_cluster_service(self, service: ServiceInfo) -> bool:
        """Stop IPFS Cluster service."""
        try:
            # IPFS Cluster doesn't have a graceful shutdown command
            # We would need to find and kill the process
            result = await asyncio.create_subprocess_exec(
                'pkill', '-f', 'ipfs-cluster-service',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            # Give it a moment to shutdown
            await asyncio.sleep(2)
            
            # Check if it stopped successfully
            await self._detect_ipfs_cluster_service(service)
            
            return service.status == ServiceStatus.STOPPED
            
        except Exception as e:
            logger.error(f"Failed to stop IPFS Cluster service: {e}")
            return False
    
    async def _start_lotus_service(self, service: ServiceInfo) -> bool:
        """Start Lotus daemon."""
        try:
            result = await asyncio.create_subprocess_exec(
                'lotus', 'daemon',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Give it a moment to start
            await asyncio.sleep(5)
            
            # Check if it started successfully
            await self._detect_lotus_service(service)
            
            return service.status == ServiceStatus.RUNNING
            
        except Exception as e:
            logger.error(f"Failed to start Lotus service: {e}")
            return False
    
    async def _stop_lotus_service(self, service: ServiceInfo) -> bool:
        """Stop Lotus daemon."""
        try:
            # Kill Lotus daemon
            result = await asyncio.create_subprocess_exec(
                'pkill', '-f', 'lotus daemon',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            # Give it a moment to shutdown
            await asyncio.sleep(2)
            
            # Check if it stopped successfully
            await self._detect_lotus_service(service)
            
            return service.status == ServiceStatus.STOPPED
            
        except Exception as e:
            logger.error(f"Failed to stop Lotus service: {e}")
            return False
    
    async def restart_service(self, service_id: str) -> bool:
        """
        Restart a specific service.
        
        Args:
            service_id: ID of the service to restart
            
        Returns:
            True if service was restarted successfully, False otherwise
        """
        logger.info(f"Restarting service {service_id}")
        
        # Stop first
        stop_success = await self.stop_service(service_id)
        if not stop_success:
            logger.warning(f"Failed to stop service {service_id}, attempting to start anyway")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Start
        start_success = await self.start_service(service_id)
        
        return start_success
    
    def get_service_info(self, service_id: str) -> Optional[ServiceInfo]:
        """
        Get information about a specific service.
        
        Args:
            service_id: ID of the service
            
        Returns:
            ServiceInfo object if found, None otherwise
        """
        return self.services.get(service_id)
    
    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """
        Get information about all services.
        
        Returns:
            Dictionary of service ID to ServiceInfo
        """
        return self.services.copy()
    
    def get_running_services(self) -> Dict[str, ServiceInfo]:
        """
        Get information about currently running services.
        
        Returns:
            Dictionary of service ID to ServiceInfo for running services only
        """
        return {
            service_id: service for service_id, service in self.services.items()
            if service.status == ServiceStatus.RUNNING
        }
    
    def get_service_stats(self) -> Dict[str, int]:
        """
        Get statistics about service states.
        
        Returns:
            Dictionary with counts for each service state
        """
        stats = {}
        for status in ServiceStatus:
            stats[status.value] = 0
        
        for service in self.services.values():
            stats[service.status.value] += 1
        
        return stats