"""
Service Registry for IPFS Kit

This module provides a centralized registry for managing storage and infrastructure services.
It replaces the incorrect services mentioned in the issue (cars, docker, kubectl) with
proper storage services like IPFS, S3, Storacha, etc.
"""

import logging
import importlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional, Type, Protocol
from datetime import datetime, timezone
import asyncio

from .metadata_manager import get_metadata_manager

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of services supported by IPFS Kit."""
    STORAGE = "storage"
    NETWORK = "network"
    INDEX = "index"
    COMPUTE = "compute"
    INTEGRATION = "integration"


class ServiceStatus(Enum):
    """Service status states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    UNKNOWN = "unknown"


class ServiceInterface(Protocol):
    """Protocol defining the interface all services must implement."""
    
    async def start(self) -> bool:
        """Start the service."""
        ...
    
    async def stop(self) -> bool:
        """Stop the service."""
        ...
    
    async def status(self) -> Dict[str, Any]:
        """Get service status."""
        ...
    
    async def health_check(self) -> bool:
        """Perform health check."""
        ...
    
    def get_config(self) -> Dict[str, Any]:
        """Get service configuration."""
        ...
    
    def set_config(self, config: Dict[str, Any]) -> bool:
        """Set service configuration."""
        ...


class BaseService(ABC):
    """Base class for all services."""
    
    def __init__(self, name: str, service_type: ServiceType, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.service_type = service_type
        self.config = config or {}
        self.current_status = ServiceStatus.STOPPED  # Changed from 'status' to avoid conflicts
        self.metadata_manager = get_metadata_manager()
        self._instance = None
        
        # Load saved configuration
        saved_config = self.metadata_manager.get_service_config(name)
        if saved_config and "config" in saved_config:
            self.config.update(saved_config["config"])
    
    @abstractmethod
    async def _create_instance(self) -> Any:
        """Create the service instance. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _start_instance(self) -> bool:
        """Start the service instance. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _stop_instance(self) -> bool:
        """Stop the service instance. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _get_instance_status(self) -> Dict[str, Any]:
        """Get instance-specific status. Must be implemented by subclasses."""
        pass
    
    async def start(self) -> bool:
        """Start the service."""
        try:
            self.current_status = ServiceStatus.STARTING
            self._update_state()
            
            if self._instance is None:
                self._instance = await self._create_instance()
            
            success = await self._start_instance()
            self.current_status = ServiceStatus.RUNNING if success else ServiceStatus.ERROR
            self._update_state()
            
            return success
        except Exception as e:
            logger.error(f"Failed to start service {self.name}: {e}")
            self.current_status = ServiceStatus.ERROR
            self._update_state()
            return False
    
    async def stop(self) -> bool:
        """Stop the service."""
        try:
            success = await self._stop_instance()
            self.current_status = ServiceStatus.STOPPED if success else ServiceStatus.ERROR
            self._update_state()
            
            return success
        except Exception as e:
            logger.error(f"Failed to stop service {self.name}: {e}")
            self.current_status = ServiceStatus.ERROR
            self._update_state()
            return False
    
    async def status(self) -> Dict[str, Any]:
        """Get service status."""
        base_status = {
            "name": self.name,
            "type": self.service_type.value,
            "status": self.current_status.value,
            "config": self.config
        }
        
        try:
            instance_status = await self._get_instance_status()
            base_status.update(instance_status)
        except Exception as e:
            logger.error(f"Failed to get instance status for {self.name}: {e}")
            base_status["error"] = str(e)
        
        return base_status
    
    async def health_check(self) -> bool:
        """Perform health check."""
        try:
            status = await self.status()
            return status.get("status") == "running"
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get service configuration."""
        return self.config.copy()
    
    def set_config(self, config: Dict[str, Any]) -> bool:
        """Set service configuration."""
        try:
            self.config.update(config)
            self.metadata_manager.set_service_config(self.name, self.config)
            return True
        except Exception as e:
            logger.error(f"Failed to set config for {self.name}: {e}")
            return False
    
    def _update_state(self):
        """Update service state in metadata."""
        state = {
            "status": self.current_status.value,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "config_hash": hash(str(sorted(self.config.items())))
        }
        self.metadata_manager.set_service_state(self.name, state)


class StorageServiceMixin:
    """Mixin for storage services."""
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            "total_size": 0,
            "used_size": 0,
            "available_size": 0,
            "quota": self.config.get("quota", "unlimited")
        }


class NetworkServiceMixin:
    """Mixin for network services."""
    
    async def get_network_stats(self) -> Dict[str, Any]:
        """Get network statistics."""
        return {
            "peers": 0,
            "connections": 0,
            "bandwidth_in": 0,
            "bandwidth_out": 0
        }


# Define the correct storage services as mentioned in the requirements
class IPFSService(BaseService, StorageServiceMixin):
    """IPFS storage service."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ipfs", ServiceType.STORAGE, config)
    
    async def _create_instance(self):
        from ..ipfs import ipfs_py
        return ipfs_py(metadata={"role": "daemon"})
    
    async def _start_instance(self) -> bool:
        if hasattr(self._instance, 'start_daemon'):
            result = await self._instance.start_daemon()
            return result.get("success", False)
        return True
    
    async def _stop_instance(self) -> bool:
        if hasattr(self._instance, 'stop_daemon'):
            result = await self._instance.stop_daemon()
            return result.get("success", False)
        return True
    
    async def _get_instance_status(self) -> Dict[str, Any]:
        status = {"backend_type": "ipfs"}
        if self._instance:
            try:
                if hasattr(self._instance, 'id'):
                    peer_id = await self._instance.id()
                    status["peer_id"] = peer_id.get("ID")
                
                storage_stats = await self.get_storage_stats()
                status.update(storage_stats)
            except Exception as e:
                status["error"] = str(e)
        return status


class IPFSClusterService(BaseService, StorageServiceMixin, NetworkServiceMixin):
    """IPFS Cluster service."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ipfs_cluster", ServiceType.STORAGE, config)
    
    async def _create_instance(self):
        from ..ipfs_cluster_service import ipfs_cluster_service
        return ipfs_cluster_service()
    
    async def _start_instance(self) -> bool:
        if hasattr(self._instance, 'start'):
            return await self._instance.start()
        return True
    
    async def _stop_instance(self) -> bool:
        if hasattr(self._instance, 'stop'):
            return await self._instance.stop()
        return True
    
    async def _get_instance_status(self) -> Dict[str, Any]:
        status = {"backend_type": "ipfs_cluster"}
        if self._instance:
            try:
                if hasattr(self._instance, 'status'):
                    cluster_status = await self._instance.status()
                    status.update(cluster_status)
                
                network_stats = await self.get_network_stats()
                status.update(network_stats)
            except Exception as e:
                status["error"] = str(e)
        return status


class S3Service(BaseService, StorageServiceMixin):
    """S3 storage service."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("s3", ServiceType.STORAGE, config)
    
    async def _create_instance(self):
        from ..s3_kit import s3_kit
        return s3_kit(resources=self.config.get("resources"))
    
    async def _start_instance(self) -> bool:
        # S3 doesn't need explicit starting
        return True
    
    async def _stop_instance(self) -> bool:
        # S3 doesn't need explicit stopping
        return True
    
    async def _get_instance_status(self) -> Dict[str, Any]:
        status = {"backend_type": "s3"}
        if self._instance:
            try:
                # Check S3 connectivity
                if hasattr(self._instance, 'list_buckets'):
                    buckets = await self._instance.list_buckets()
                    status["buckets"] = len(buckets)
                
                storage_stats = await self.get_storage_stats()
                status.update(storage_stats)
            except Exception as e:
                status["error"] = str(e)
        return status


class StorachaService(BaseService, StorageServiceMixin):
    """Storacha (Web3.Storage) service."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("storacha", ServiceType.STORAGE, config)
    
    async def _create_instance(self):
        from ..storacha_kit import storacha_kit
        return storacha_kit(resources=self.config.get("resources"))
    
    async def _start_instance(self) -> bool:
        return True
    
    async def _stop_instance(self) -> bool:
        return True
    
    async def _get_instance_status(self) -> Dict[str, Any]:
        status = {"backend_type": "storacha"}
        if self._instance:
            try:
                storage_stats = await self.get_storage_stats()
                status.update(storage_stats)
            except Exception as e:
                status["error"] = str(e)
        return status


class HuggingFaceService(BaseService, StorageServiceMixin):
    """HuggingFace Hub service."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("huggingface", ServiceType.INTEGRATION, config)
    
    async def _create_instance(self):
        from ..huggingface_kit import huggingface_kit
        return huggingface_kit(resources=self.config.get("resources"))
    
    async def _start_instance(self) -> bool:
        return True
    
    async def _stop_instance(self) -> bool:
        return True
    
    async def _get_instance_status(self) -> Dict[str, Any]:
        status = {"backend_type": "huggingface"}
        if self._instance:
            try:
                # Get HF status
                storage_stats = await self.get_storage_stats()
                status.update(storage_stats)
            except Exception as e:
                status["error"] = str(e)
        return status


# Add more services as needed...

class ServiceRegistry:
    """Registry for managing all services."""
    
    def __init__(self):
        self.services: Dict[str, BaseService] = {}
        self.service_classes: Dict[str, Type[BaseService]] = {
            "ipfs": IPFSService,
            "ipfs_cluster": IPFSClusterService,
            "s3": S3Service,
            "storacha": StorachaService,
            "huggingface": HuggingFaceService,
            # Add more services here as they're implemented
        }
        self.metadata_manager = get_metadata_manager()
        self._lock = asyncio.Lock()
    
    async def register_service(self, service_name: str, service_class: Type[BaseService]):
        """Register a service class."""
        async with self._lock:
            self.service_classes[service_name] = service_class
    
    async def create_service(self, service_name: str, config: Optional[Dict[str, Any]] = None) -> Optional[BaseService]:
        """Create a service instance."""
        if service_name not in self.service_classes:
            logger.error(f"Unknown service type: {service_name}")
            return None
        
        try:
            service_class = self.service_classes[service_name]
            service = service_class(config)
            return service
        except Exception as e:
            logger.error(f"Failed to create service {service_name}: {e}")
            return None
    
    async def add_service(self, service_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Add a service to the registry."""
        async with self._lock:
            if service_name in self.services:
                logger.warning(f"Service {service_name} already exists")
                return False
            
            service = await self.create_service(service_name, config)
            if service:
                self.services[service_name] = service
                # Save configuration
                service.set_config(config or {})
                return True
            return False
    
    async def remove_service(self, service_name: str) -> bool:
        """Remove a service from the registry."""
        async with self._lock:
            if service_name not in self.services:
                return False
            
            # Stop the service first
            service = self.services[service_name]
            await service.stop()
            
            # Remove from registry
            del self.services[service_name]
            
            # Remove configuration
            self.metadata_manager.remove_service_config(service_name)
            
            return True
    
    async def start_service(self, service_name: str) -> bool:
        """Start a service."""
        if service_name not in self.services:
            logger.error(f"Service {service_name} not found")
            return False
        
        return await self.services[service_name].start()
    
    async def stop_service(self, service_name: str) -> bool:
        """Stop a service."""
        if service_name not in self.services:
            logger.error(f"Service {service_name} not found")
            return False
        
        return await self.services[service_name].stop()
    
    async def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service status."""
        if service_name not in self.services:
            return None
        
        return await self.services[service_name].status()
    
    async def list_services(self) -> List[str]:
        """List all registered services."""
        return list(self.services.keys())
    
    async def get_all_service_status(self) -> Dict[str, Any]:
        """Get status of all services."""
        status = {}
        for service_name, service in self.services.items():
            try:
                status[service_name] = await service.status()
            except Exception as e:
                status[service_name] = {"error": str(e)}
        return status
    
    async def start_all_services(self) -> Dict[str, bool]:
        """Start all services."""
        results = {}
        for service_name in self.services:
            results[service_name] = await self.start_service(service_name)
        return results
    
    async def stop_all_services(self) -> Dict[str, bool]:
        """Stop all services."""
        results = {}
        for service_name in self.services:
            results[service_name] = await self.stop_service(service_name)
        return results
    
    def get_available_service_types(self) -> List[str]:
        """Get list of available service types."""
        return list(self.service_classes.keys())


# Global service registry
_service_registry = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    global _service_registry
    if _service_registry is None:
        _service_registry = ServiceRegistry()
    return _service_registry