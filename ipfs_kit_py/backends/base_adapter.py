#!/usr/bin/env python3
"""
Base Backend Adapter for IPFS Kit

Defines the isomorphic interface that all backend adapters must implement.
This ensures consistent method names and signatures across different filesystem backends.
"""

import anyio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class BackendAdapter(ABC):
    """
    Abstract base class for all backend adapters.
    
    All backend adapters must implement these isomorphic methods to ensure
    consistent interface across different storage backends (IPFS, S3, filesystem, etc.).
    """
    
    def __init__(self, backend_name: str, config_manager=None):
        """
        Initialize the backend adapter.
        
        Args:
            backend_name: Name of the backend instance
            config_manager: Configuration manager instance
        """
        self.backend_name = backend_name
        self.config_manager = config_manager
        self.logger = logger.getChild(f"{self.__class__.__name__}.{backend_name}")
        
        # Common configuration
        self.ipfs_kit_dir = Path.home() / '.ipfs_kit'
        self.backend_metadata_dir = self.ipfs_kit_dir / 'backends' / backend_name
        self.backend_metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Backend-specific configuration
        self.config = self._load_backend_config()
    
    def _load_backend_config(self) -> Dict[str, Any]:
        """
        Load backend-specific configuration.
        
        Returns:
            Dictionary with backend configuration
        """
        try:
            if self.config_manager:
                config = self.config_manager.get_backend_config(self.backend_name)
                if config:
                    return config
            
            # Default configuration
            return {
                'enabled': True,
                'timeout': 30,
                'retry_count': 3,
                'health_check_interval': 300
            }
            
        except Exception as e:
            self.logger.error(f"Error loading backend config: {e}")
            return {}
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of this backend.
        
        Returns:
            Dictionary with health information:
            - healthy: bool - Whether backend is healthy
            - response_time_ms: float - Response time in milliseconds
            - error: str - Error message if unhealthy
            - pin_count: int - Number of pins on this backend
            - storage_usage: int - Storage usage in bytes
            - needs_pin_sync: bool - Whether pins need synchronization
            - needs_bucket_backup: bool - Whether buckets need backup
            - needs_metadata_backup: bool - Whether metadata needs backup
        """
        pass
    
    @abstractmethod
    async def sync_pins(self) -> bool:
        """
        Synchronize pins between local metadata and backend storage.
        
        This method should:
        1. Compare local pin metadata with backend pin state
        2. Upload missing pins to backend
        3. Download missing pins from backend
        4. Update local metadata with sync results
        
        Returns:
            True if sync completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def backup_buckets(self) -> bool:
        """
        Backup bucket configurations and data to this backend.
        
        This method should:
        1. Read bucket configurations from ~/.ipfs_kit/buckets/
        2. Create backup archives of bucket data
        3. Upload backup archives to backend storage
        4. Update backup metadata
        
        Returns:
            True if backup completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def backup_metadata(self) -> bool:
        """
        Backup IPFS Kit metadata indices to this backend.
        
        This method should:
        1. Backup pin metadata (DuckDB, parquet, CAR files)
        2. Backup backend index
        3. Backup configuration files
        4. Create incremental/differential backups when possible
        
        Returns:
            True if backup completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """
        Restore pins from backend storage to local system.
        
        Args:
            pin_list: Optional list of specific pins to restore. If None, restore all.
            
        Returns:
            True if restore completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """
        Restore bucket configurations and data from backend storage.
        
        Args:
            bucket_list: Optional list of specific buckets to restore. If None, restore all.
            
        Returns:
            True if restore completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def restore_metadata(self) -> bool:
        """
        Restore IPFS Kit metadata from backend storage.
        
        Returns:
            True if restore completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_pins(self) -> List[Dict[str, Any]]:
        """
        List all pins stored on this backend.
        
        Returns:
            List of dictionaries with pin information:
            - cid: str - Content identifier
            - name: str - Pin name
            - size: int - Size in bytes
            - created_at: str - Creation timestamp
            - metadata: dict - Additional metadata
        """
        pass
    
    @abstractmethod
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """
        List all bucket backups stored on this backend.
        
        Returns:
            List of dictionaries with bucket backup information:
            - bucket_name: str - Name of the bucket
            - backup_path: str - Path to backup file
            - size: int - Backup size in bytes
            - created_at: str - Backup timestamp
            - checksum: str - Backup checksum
        """
        pass
    
    @abstractmethod
    async def list_metadata_backups(self) -> List[Dict[str, Any]]:
        """
        List all metadata backups stored on this backend.
        
        Returns:
            List of dictionaries with metadata backup information:
            - backup_type: str - Type of metadata backup
            - backup_path: str - Path to backup file
            - size: int - Backup size in bytes
            - created_at: str - Backup timestamp
            - checksum: str - Backup checksum
        """
        pass
    
    @abstractmethod
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """
        Clean up old backups based on retention policy.
        
        Args:
            retention_days: Number of days to retain backups
            
        Returns:
            True if cleanup completed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_storage_usage(self) -> Dict[str, int]:
        """
        Get storage usage statistics for this backend.
        
        Returns:
            Dictionary with storage usage information:
            - total_usage: int - Total storage used in bytes
            - pin_usage: int - Storage used by pins
            - bucket_backup_usage: int - Storage used by bucket backups
            - metadata_backup_usage: int - Storage used by metadata backups
            - available_space: int - Available space (if applicable)
        """
        pass
    
    # Common utility methods that can be used by all adapters
    
    def _get_metadata_file_path(self, metadata_type: str) -> Path:
        """
        Get path to backend-specific metadata file.
        
        Args:
            metadata_type: Type of metadata (pins, buckets, backups, etc.)
            
        Returns:
            Path to metadata file
        """
        return self.backend_metadata_dir / f"{metadata_type}_metadata.json"
    
    def _save_metadata(self, metadata_type: str, data: Dict[str, Any]):
        """
        Save metadata to backend-specific file.
        
        Args:
            metadata_type: Type of metadata
            data: Metadata to save
        """
        try:
            import json
            metadata_file = self._get_metadata_file_path(metadata_type)
            
            with open(metadata_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            self.logger.debug(f"Saved {metadata_type} metadata for {self.backend_name}")
            
        except Exception as e:
            self.logger.error(f"Error saving {metadata_type} metadata: {e}")
    
    def _load_metadata(self, metadata_type: str) -> Dict[str, Any]:
        """
        Load metadata from backend-specific file.
        
        Args:
            metadata_type: Type of metadata
            
        Returns:
            Loaded metadata dictionary
        """
        try:
            import json
            metadata_file = self._get_metadata_file_path(metadata_type)
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    
                self.logger.debug(f"Loaded {metadata_type} metadata for {self.backend_name}")
                return data
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Error loading {metadata_type} metadata: {e}")
            return {}
    
    def _calculate_checksum(self, file_path: Union[str, Path]) -> str:
        """
        Calculate SHA256 checksum of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 checksum as hex string
        """
        import hashlib
        
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""
    
    def _create_backup_archive(self, source_dir: Path, backup_name: str) -> Optional[Path]:
        """
        Create a backup archive from a directory.
        
        Args:
            source_dir: Directory to backup
            backup_name: Name for the backup archive
            
        Returns:
            Path to created backup archive, or None if failed
        """
        try:
            import tarfile
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{backup_name}_{timestamp}.tar.gz"
            archive_path = self.backend_metadata_dir / archive_name
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(source_dir, arcname=backup_name)
            
            self.logger.info(f"Created backup archive: {archive_path}")
            return archive_path
            
        except Exception as e:
            self.logger.error(f"Error creating backup archive: {e}")
            return None
    
    def __str__(self) -> str:
        """String representation of the backend adapter."""
        return f"{self.__class__.__name__}({self.backend_name})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the backend adapter."""
        return f"{self.__class__.__name__}(backend_name='{self.backend_name}')"
