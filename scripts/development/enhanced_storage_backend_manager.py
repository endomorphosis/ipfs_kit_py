#!/usr/bin/env python3
"""
Enhanced Storage Backend Manager

This module provides comprehensive management for storage backends in the MCP server,
ensuring proper identification, configuration, and control of all virtual filesystem
backends including IPFS, S3, Filecoin, Storacha, HuggingFace, Lassie, and others.

Key Features:
- Automatic discovery and registration of available backends
- Health monitoring and status checking
- Backend lifecycle management (start/stop/restart/configure)
- Configuration management for each backend
- Integration with the MCP dashboard
- Support for simulation and real implementations
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable

import psutil

# Configure logging
logger = logging.getLogger(__name__)


class BackendStatus:
    """Backend status tracking."""
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    DEGRADED = "degraded"


class StorageBackend:
    """Base class for storage backends."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        """Initialize storage backend."""
        self.name = name
        self.config = config or {}
        self.status = BackendStatus.UNKNOWN
        self.last_check = datetime.now()
        self.error_message = None
        self.details = {}
        
    async def check_health(self) -> Dict[str, Any]:
        """Check backend health status."""
        raise NotImplementedError
    
    async def start(self) -> Dict[str, Any]:
        """Start the backend."""
        raise NotImplementedError
    
    async def stop(self) -> Dict[str, Any]:
        """Stop the backend."""
        raise NotImplementedError
    
    async def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure the backend."""
        self.config.update(config)
        return {"success": True, "message": "Configuration updated"}
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get current status information."""
        return {
            "name": self.name,
            "status": self.status,
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message,
            "details": self.details,
            "config": self.config
        }


class IPFSBackend(StorageBackend):
    """IPFS storage backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("ipfs", config)
        self.api_port = self.config.get("api_port", 5001)
        self.gateway_port = self.config.get("gateway_port", 8080)
        self.swarm_port = self.config.get("swarm_port", 4001)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check IPFS daemon health."""
        try:
            # Check if IPFS daemon process is running
            ipfs_process = self._find_ipfs_process()
            if not ipfs_process:
                self.status = BackendStatus.STOPPED
                return {"success": False, "error": "IPFS daemon not running"}
            
            # Check API connectivity
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            api_result = sock.connect_ex(('localhost', self.api_port))
            sock.close()
            
            if api_result != 0:
                self.status = BackendStatus.ERROR
                self.error_message = f"IPFS API not accessible on port {self.api_port}"
                return {"success": False, "error": self.error_message}
            
            # Try to get IPFS version and ID
            try:
                result = subprocess.run(['ipfs', 'version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.details['version'] = result.stdout.strip()
                
                result = subprocess.run(['ipfs', 'id', '--format=<id>'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.details['peer_id'] = result.stdout.strip()
                
                # Get repo stats
                result = subprocess.run(['ipfs', 'repo', 'stat'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if 'RepoSize' in line:
                            self.details['repo_size'] = line.split(':')[1].strip()
                        elif 'NumObjects' in line:
                            self.details['num_objects'] = line.split(':')[1].strip()
                
            except Exception as e:
                logger.warning(f"Could not get IPFS details: {e}")
            
            self.status = BackendStatus.RUNNING
            self.last_check = datetime.now()
            self.error_message = None
            
            return {"success": True, "status": "running", "details": self.details}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            logger.error(f"IPFS health check failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start IPFS daemon."""
        try:
            # Check if already running
            if self._find_ipfs_process():
                return {"success": True, "message": "IPFS daemon already running"}
            
            # Initialize IPFS if needed
            ipfs_path = os.environ.get('IPFS_PATH', os.path.expanduser('~/.ipfs'))
            if not os.path.exists(ipfs_path):
                logger.info("Initializing IPFS repository")
                result = subprocess.run(['ipfs', 'init'], capture_output=True, text=True)
                if result.returncode != 0:
                    return {"success": False, "error": f"IPFS init failed: {result.stderr}"}
            
            # Start daemon
            logger.info("Starting IPFS daemon")
            process = subprocess.Popen(['ipfs', 'daemon'],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            
            # Wait a moment for startup
            await asyncio.sleep(3)
            
            # Verify it started
            health = await self.check_health()
            if health["success"]:
                return {"success": True, "message": "IPFS daemon started successfully"}
            else:
                return {"success": False, "error": "IPFS daemon failed to start properly"}
                
        except FileNotFoundError:
            return {"success": False, "error": "IPFS executable not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop IPFS daemon."""
        try:
            ipfs_process = self._find_ipfs_process()
            if not ipfs_process:
                return {"success": True, "message": "IPFS daemon was not running"}
            
            # Graceful shutdown
            ipfs_process.terminate()
            
            try:
                ipfs_process.wait(timeout=10)
            except psutil.TimeoutExpired:
                ipfs_process.kill()
            
            self.status = BackendStatus.STOPPED
            return {"success": True, "message": "IPFS daemon stopped"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _find_ipfs_process(self):
        """Find IPFS daemon process."""
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if process.name() == 'ipfs' or 'ipfs daemon' in ' '.join(process.cmdline()):
                    return process
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None


class S3Backend(StorageBackend):
    """S3 storage backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("s3", config)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check S3 backend health."""
        try:
            # Check if boto3 is available
            try:
                import boto3
                from botocore.exceptions import NoCredentialsError, ClientError
            except ImportError:
                self.status = BackendStatus.ERROR
                self.error_message = "boto3 not installed"
                return {"success": False, "error": "boto3 library not available"}
            
            # Check credentials
            try:
                session = boto3.Session()
                credentials = session.get_credentials()
                if not credentials:
                    self.status = BackendStatus.STOPPED
                    self.error_message = "No AWS credentials configured"
                    return {"success": False, "error": "No AWS credentials found"}
                
                # Try to create S3 client and list buckets
                s3_client = boto3.client('s3')
                response = s3_client.list_buckets()
                
                self.details['num_buckets'] = len(response['Buckets'])
                self.details['region'] = s3_client.meta.region_name
                
                self.status = BackendStatus.RUNNING
                self.last_check = datetime.now()
                self.error_message = None
                
                return {"success": True, "status": "running", "details": self.details}
                
            except NoCredentialsError:
                self.status = BackendStatus.STOPPED
                self.error_message = "AWS credentials not configured"
                return {"success": False, "error": "AWS credentials not configured"}
                
            except ClientError as e:
                self.status = BackendStatus.ERROR
                self.error_message = f"AWS API error: {e}"
                return {"success": False, "error": str(e)}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start S3 backend (configure credentials)."""
        # S3 doesn't need to be "started" but we can check configuration
        health = await self.check_health()
        if health["success"]:
            return {"success": True, "message": "S3 backend is properly configured"}
        else:
            return {"success": False, "error": "S3 backend needs configuration"}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop S3 backend (clear credentials)."""
        # We can't really "stop" S3, but we can indicate it's not configured
        self.status = BackendStatus.STOPPED
        return {"success": True, "message": "S3 backend marked as stopped"}


class HuggingFaceBackend(StorageBackend):
    """HuggingFace storage backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("huggingface", config)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check HuggingFace backend health."""
        try:
            try:
                import huggingface_hub
                from huggingface_hub import HfApi
            except ImportError:
                self.status = BackendStatus.ERROR
                self.error_message = "huggingface_hub not installed"
                return {"success": False, "error": "huggingface_hub library not available"}
            
            # Check if logged in
            token = huggingface_hub.get_token()
            if not token:
                self.status = BackendStatus.STOPPED
                self.error_message = "Not logged in to HuggingFace"
                return {"success": False, "error": "Not logged in to HuggingFace"}
            
            # Try to get user info
            try:
                api = HfApi()
                user_info = api.whoami()
                self.details['username'] = user_info['name']
                self.details['email'] = user_info.get('email', 'N/A')
                
                self.status = BackendStatus.RUNNING
                self.last_check = datetime.now()
                self.error_message = None
                
                return {"success": True, "status": "running", "details": self.details}
                
            except Exception as e:
                self.status = BackendStatus.ERROR
                self.error_message = f"HuggingFace API error: {e}"
                return {"success": False, "error": str(e)}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start HuggingFace backend."""
        health = await self.check_health()
        if health["success"]:
            return {"success": True, "message": "HuggingFace backend is ready"}
        else:
            return {"success": False, "error": "HuggingFace backend needs authentication"}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop HuggingFace backend."""
        self.status = BackendStatus.STOPPED
        return {"success": True, "message": "HuggingFace backend marked as stopped"}


class FilecoinBackend(StorageBackend):
    """Filecoin storage backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("filecoin", config)
        self.lotus_port = self.config.get("lotus_port", 1234)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check Filecoin/Lotus backend health."""
        try:
            # Check if Lotus daemon is running
            lotus_process = self._find_lotus_process()
            if not lotus_process:
                self.status = BackendStatus.STOPPED
                return {"success": False, "error": "Lotus daemon not running"}
            
            # Try to get Lotus version and status
            try:
                result = subprocess.run(['lotus', 'version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.details['version'] = result.stdout.strip()
                
                result = subprocess.run(['lotus', 'net', 'id'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.details['peer_id'] = result.stdout.strip()
                
            except Exception as e:
                logger.warning(f"Could not get Lotus details: {e}")
            
            self.status = BackendStatus.RUNNING
            self.last_check = datetime.now()
            self.error_message = None
            
            return {"success": True, "status": "running", "details": self.details}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start Lotus daemon."""
        try:
            if self._find_lotus_process():
                return {"success": True, "message": "Lotus daemon already running"}
            
            logger.info("Starting Lotus daemon")
            process = subprocess.Popen(['lotus', 'daemon'],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            
            await asyncio.sleep(5)  # Lotus takes longer to start
            
            health = await self.check_health()
            if health["success"]:
                return {"success": True, "message": "Lotus daemon started successfully"}
            else:
                return {"success": False, "error": "Lotus daemon failed to start properly"}
                
        except FileNotFoundError:
            return {"success": False, "error": "Lotus executable not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop Lotus daemon."""
        try:
            lotus_process = self._find_lotus_process()
            if not lotus_process:
                return {"success": True, "message": "Lotus daemon was not running"}
            
            lotus_process.terminate()
            
            try:
                lotus_process.wait(timeout=15)
            except psutil.TimeoutExpired:
                lotus_process.kill()
            
            self.status = BackendStatus.STOPPED
            return {"success": True, "message": "Lotus daemon stopped"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _find_lotus_process(self):
        """Find Lotus daemon process."""
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'lotus' in process.name() or 'lotus daemon' in ' '.join(process.cmdline()):
                    return process
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None


class StorachaBackend(StorageBackend):
    """Storacha (Web3.Storage) backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("storacha", config)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check Storacha backend health."""
        try:
            # Check for API token
            api_token = self.config.get('api_token') or os.environ.get('WEB3_STORAGE_TOKEN')
            if not api_token:
                self.status = BackendStatus.STOPPED
                self.error_message = "No API token configured"
                return {"success": False, "error": "No Storacha API token configured"}
            
            # Try to make a simple API call
            import requests
            headers = {'Authorization': f'Bearer {api_token}'}
            
            try:
                response = requests.get('https://api.web3.storage/user/account', 
                                      headers=headers, timeout=10)
                if response.status_code == 200:
                    user_info = response.json()
                    self.details['user'] = user_info
                    
                    self.status = BackendStatus.RUNNING
                    self.last_check = datetime.now()
                    self.error_message = None
                    
                    return {"success": True, "status": "running", "details": self.details}
                else:
                    self.status = BackendStatus.ERROR
                    self.error_message = f"API error: {response.status_code}"
                    return {"success": False, "error": f"API error: {response.status_code}"}
                    
            except requests.RequestException as e:
                self.status = BackendStatus.ERROR
                self.error_message = f"Network error: {e}"
                return {"success": False, "error": str(e)}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start Storacha backend."""
        health = await self.check_health()
        if health["success"]:
            return {"success": True, "message": "Storacha backend is ready"}
        else:
            return {"success": False, "error": "Storacha backend needs API token configuration"}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop Storacha backend."""
        self.status = BackendStatus.STOPPED
        return {"success": True, "message": "Storacha backend marked as stopped"}


class LassieBackend(StorageBackend):
    """Lassie backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("lassie", config)
        self.port = self.config.get("port", 7777)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check Lassie backend health."""
        try:
            # Check if Lassie daemon is running
            lassie_process = self._find_lassie_process()
            if not lassie_process:
                self.status = BackendStatus.STOPPED
                return {"success": False, "error": "Lassie daemon not running"}
            
            # Check port connectivity
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', self.port))
            sock.close()
            
            if result != 0:
                self.status = BackendStatus.ERROR
                self.error_message = f"Lassie not accessible on port {self.port}"
                return {"success": False, "error": self.error_message}
            
            self.status = BackendStatus.RUNNING
            self.last_check = datetime.now()
            self.error_message = None
            
            return {"success": True, "status": "running", "details": self.details}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start Lassie daemon."""
        try:
            if self._find_lassie_process():
                return {"success": True, "message": "Lassie daemon already running"}
            
            logger.info("Starting Lassie daemon")
            process = subprocess.Popen(['lassie', 'daemon'],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            
            await asyncio.sleep(3)
            
            health = await self.check_health()
            if health["success"]:
                return {"success": True, "message": "Lassie daemon started successfully"}
            else:
                return {"success": False, "error": "Lassie daemon failed to start properly"}
                
        except FileNotFoundError:
            return {"success": False, "error": "Lassie executable not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop Lassie daemon."""
        try:
            lassie_process = self._find_lassie_process()
            if not lassie_process:
                return {"success": True, "message": "Lassie daemon was not running"}
            
            lassie_process.terminate()
            
            try:
                lassie_process.wait(timeout=10)
            except psutil.TimeoutExpired:
                lassie_process.kill()
            
            self.status = BackendStatus.STOPPED
            return {"success": True, "message": "Lassie daemon stopped"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _find_lassie_process(self):
        """Find Lassie daemon process."""
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'lassie' in process.name() or 'lassie daemon' in ' '.join(process.cmdline()):
                    return process
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None


class LocalBackend(StorageBackend):
    """Local filesystem backend."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("local", config)
        self.storage_path = self.config.get("storage_path", os.path.expanduser("~/.ipfs_kit/local_storage"))
    
    async def check_health(self) -> Dict[str, Any]:
        """Check local backend health."""
        try:
            # Ensure storage directory exists
            os.makedirs(self.storage_path, exist_ok=True)
            
            # Check if directory is writable
            test_file = os.path.join(self.storage_path, ".health_check")
            try:
                with open(test_file, 'w') as f:
                    f.write("health_check")
                os.remove(test_file)
                
                # Get storage stats
                import shutil
                total, used, free = shutil.disk_usage(self.storage_path)
                self.details['storage_path'] = self.storage_path
                self.details['total_space'] = total
                self.details['used_space'] = used
                self.details['free_space'] = free
                
                self.status = BackendStatus.RUNNING
                self.last_check = datetime.now()
                self.error_message = None
                
                return {"success": True, "status": "running", "details": self.details}
                
            except OSError as e:
                self.status = BackendStatus.ERROR
                self.error_message = f"Storage directory not writable: {e}"
                return {"success": False, "error": self.error_message}
            
        except Exception as e:
            self.status = BackendStatus.ERROR
            self.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    async def start(self) -> Dict[str, Any]:
        """Start local backend."""
        health = await self.check_health()
        if health["success"]:
            return {"success": True, "message": "Local backend is ready"}
        else:
            return {"success": False, "error": "Local backend directory issues"}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop local backend."""
        # Local backend can't really be "stopped"
        self.status = BackendStatus.STOPPED
        return {"success": True, "message": "Local backend marked as stopped"}


class EnhancedStorageBackendManager:
    """
    Enhanced storage backend manager that provides comprehensive management
    of all storage backends and integrates with the MCP dashboard.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the storage backend manager."""
        self.config_path = config_path or os.path.expanduser("~/.ipfs_kit/storage_backends.json")
        self.config = self._load_config()
        
        # Initialize backends
        self.backends: Dict[str, StorageBackend] = {}
        self._initialize_backends()
        
        # Monitoring
        self.last_health_check = datetime.now()
        self.health_check_interval = 30  # seconds
    
    def _load_config(self) -> Dict[str, Any]:
        """Load backend configuration."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config from {self.config_path}: {e}")
        
        # Default configuration
        return {
            "backends": {
                "ipfs": {"enabled": True, "api_port": 5001},
                "s3": {"enabled": True},
                "huggingface": {"enabled": True},
                "filecoin": {"enabled": True, "lotus_port": 1234},
                "storacha": {"enabled": True},
                "lassie": {"enabled": True, "port": 7777},
                "local": {"enabled": True, "storage_path": "~/.ipfs_kit/local_storage"}
            }
        }
    
    def _save_config(self):
        """Save backend configuration."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
    
    def _initialize_backends(self):
        """Initialize all configured backends."""
        backend_configs = self.config.get("backends", {})
        
        # Initialize each backend type
        backend_classes = {
            "ipfs": IPFSBackend,
            "s3": S3Backend,
            "huggingface": HuggingFaceBackend,
            "filecoin": FilecoinBackend,
            "storacha": StorachaBackend,
            "lassie": LassieBackend,
            "local": LocalBackend
        }
        
        for backend_name, backend_class in backend_classes.items():
            if backend_configs.get(backend_name, {}).get("enabled", False):
                try:
                    backend_config = backend_configs[backend_name]
                    self.backends[backend_name] = backend_class(backend_config)
                    logger.info(f"Initialized {backend_name} backend")
                except Exception as e:
                    logger.error(f"Failed to initialize {backend_name} backend: {e}")
    
    async def check_all_backends_health(self) -> Dict[str, Any]:
        """Check health of all backends."""
        results = {}
        
        for backend_name, backend in self.backends.items():
            try:
                health = await backend.check_health()
                results[backend_name] = health
            except Exception as e:
                logger.error(f"Error checking {backend_name} health: {e}")
                results[backend_name] = {"success": False, "error": str(e)}
        
        self.last_health_check = datetime.now()
        return results
    
    async def get_backend_status(self, backend_name: str) -> Dict[str, Any]:
        """Get status of a specific backend."""
        if backend_name not in self.backends:
            return {"error": f"Backend '{backend_name}' not found"}
        
        backend = self.backends[backend_name]
        await backend.check_health()
        return backend.get_status_info()
    
    async def start_backend(self, backend_name: str) -> Dict[str, Any]:
        """Start a specific backend."""
        if backend_name not in self.backends:
            return {"success": False, "error": f"Backend '{backend_name}' not found"}
        
        backend = self.backends[backend_name]
        return await backend.start()
    
    async def stop_backend(self, backend_name: str) -> Dict[str, Any]:
        """Stop a specific backend."""
        if backend_name not in self.backends:
            return {"success": False, "error": f"Backend '{backend_name}' not found"}
        
        backend = self.backends[backend_name]
        return await backend.stop()
    
    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Restart a specific backend."""
        if backend_name not in self.backends:
            return {"success": False, "error": f"Backend '{backend_name}' not found"}
        
        backend = self.backends[backend_name]
        
        # Stop first
        stop_result = await backend.stop()
        if not stop_result["success"]:
            return stop_result
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Start again
        return await backend.start()
    
    async def configure_backend(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure a specific backend."""
        if backend_name not in self.backends:
            return {"success": False, "error": f"Backend '{backend_name}' not found"}
        
        backend = self.backends[backend_name]
        result = await backend.configure(config)
        
        # Update saved configuration
        if result["success"]:
            self.config["backends"][backend_name].update(config)
            self._save_config()
        
        return result
    
    def get_all_backend_statuses(self) -> Dict[str, Any]:
        """Get status of all backends."""
        statuses = {}
        for backend_name, backend in self.backends.items():
            statuses[backend_name] = backend.get_status_info()
        
        return {
            "backends": statuses,
            "last_health_check": self.last_health_check.isoformat(),
            "health_check_interval": self.health_check_interval
        }
    
    def add_backend(self, backend_name: str, backend_class: type, config: Dict[str, Any] = None):
        """Add a new backend."""
        try:
            self.backends[backend_name] = backend_class(config or {})
            
            # Update configuration
            if "backends" not in self.config:
                self.config["backends"] = {}
            self.config["backends"][backend_name] = {"enabled": True, **(config or {})}
            self._save_config()
            
            logger.info(f"Added new backend: {backend_name}")
            return {"success": True, "message": f"Backend '{backend_name}' added successfully"}
            
        except Exception as e:
            logger.error(f"Failed to add backend '{backend_name}': {e}")
            return {"success": False, "error": str(e)}
    
    def remove_backend(self, backend_name: str) -> Dict[str, Any]:
        """Remove a backend."""
        if backend_name not in self.backends:
            return {"success": False, "error": f"Backend '{backend_name}' not found"}
        
        try:
            del self.backends[backend_name]
            
            # Update configuration
            if backend_name in self.config.get("backends", {}):
                del self.config["backends"][backend_name]
                self._save_config()
            
            logger.info(f"Removed backend: {backend_name}")
            return {"success": True, "message": f"Backend '{backend_name}' removed successfully"}
            
        except Exception as e:
            logger.error(f"Failed to remove backend '{backend_name}': {e}")
            return {"success": False, "error": str(e)}


# Global backend manager instance
_backend_manager = None


def get_backend_manager() -> EnhancedStorageBackendManager:
    """Get the global backend manager instance."""
    global _backend_manager
    if _backend_manager is None:
        _backend_manager = EnhancedStorageBackendManager()
    return _backend_manager


async def main():
    """Test the storage backend manager."""
    manager = get_backend_manager()
    
    print("Checking all backend health...")
    health_results = await manager.check_all_backends_health()
    
    for backend_name, health in health_results.items():
        status = "✅" if health["success"] else "❌"
        print(f"{status} {backend_name}: {health}")
    
    print("\nAll backend statuses:")
    statuses = manager.get_all_backend_statuses()
    print(json.dumps(statuses, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())