"""
IPFS Kit Storage Backends

This package contains storage backend implementations for IPFS Kit.
Each backend provides a standardized interface for different storage systems.
"""

from .synapse_storage import SynapseStorage
from .base_adapter import BackendAdapter
from .ipfs_backend import IPFSBackendAdapter
from .filesystem_backend import FilesystemBackendAdapter
from .s3_backend import S3BackendAdapter

__all__ = [
    'SynapseStorage',
    'BackendAdapter',
    'IPFSBackendAdapter', 
    'FilesystemBackendAdapter',
    'S3BackendAdapter'
]

# Backend adapter registry
BACKEND_ADAPTERS = {
    'ipfs': IPFSBackendAdapter,
    'filesystem': FilesystemBackendAdapter,
    'sshfs': FilesystemBackendAdapter,  # SSHFS uses filesystem adapter
    's3': S3BackendAdapter,
    'minio': S3BackendAdapter,  # MinIO uses S3 adapter
    'digitalocean': S3BackendAdapter,  # DigitalOcean Spaces uses S3 adapter
}

def get_backend_adapter(backend_type: str, backend_name: str, config_manager=None) -> BackendAdapter:
    """
    Factory function to get the appropriate backend adapter.
    
    Args:
        backend_type: Type of backend ('ipfs', 'filesystem', 's3', etc.)
        backend_name: Name of the specific backend instance
        config_manager: Configuration manager instance
        
    Returns:
        Backend adapter instance
        
    Raises:
        ValueError: If backend type is not supported
    """
    if backend_type not in BACKEND_ADAPTERS:
        supported_types = list(BACKEND_ADAPTERS.keys())
        raise ValueError(f"Unsupported backend type '{backend_type}'. Supported types: {supported_types}")
    
    adapter_class = BACKEND_ADAPTERS[backend_type]
    return adapter_class(backend_name, config_manager)

def list_supported_backends():
    """List all supported backend types."""
    return list(BACKEND_ADAPTERS.keys())
