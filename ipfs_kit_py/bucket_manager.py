import os
import time
import shutil
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup logging
logger = logging.getLogger(__name__)

# Try relative import first, fallback to absolute import
try:
    from .config_manager import ConfigManager
except ImportError:
    from config_manager import ConfigManager

# Import ipfs_datasets_py integration with fallback
try:
    from .ipfs_datasets_integration import get_ipfs_datasets_manager
    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False
    get_ipfs_datasets_manager = None
    logger.info("ipfs_datasets_py not available - dataset storage disabled")

# Import ipfs_accelerate_py for compute acceleration
try:
    import sys
    from pathlib import Path as PathlibPath
    accelerate_path = PathlibPath(__file__).parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute layer available")
except ImportError:
    HAS_ACCELERATE = False
    AccelerateCompute = None
    logger.info("ipfs_accelerate_py not available - using default compute")

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
BUCKETS_PATH = IPFS_KIT_PATH / 'buckets'

class BucketManager:
    def __init__(
        self, 
        config_manager: Optional[ConfigManager] = None,
        enable_dataset_storage: bool = False,
        enable_compute_layer: bool = False,
        ipfs_client=None,
        dataset_batch_size: int = 100
    ):
        self.config_manager = config_manager or ConfigManager()
        BUCKETS_PATH.mkdir(parents=True, exist_ok=True)
        
        # Initialize bucket data directory for actual storage
        self.bucket_data_path = IPFS_KIT_PATH / 'bucket_data'
        self.bucket_data_path.mkdir(parents=True, exist_ok=True)
        
        # Dataset storage configuration
        self.enable_dataset_storage = enable_dataset_storage and HAS_DATASETS
        self.dataset_batch_size = dataset_batch_size
        self.dataset_manager = None
        self.ipfs_client = ipfs_client
        self._operation_buffer = []
        self._buffer_lock = threading.Lock()
        
        # Compute layer configuration
        self.enable_compute_layer = enable_compute_layer and HAS_ACCELERATE
        self.compute_layer = None
        
        # Initialize dataset manager if enabled
        if self.enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(enable=True, ipfs_client=ipfs_client)
                logger.info("Bucket Manager dataset storage enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
                self.enable_dataset_storage = False
        
        # Initialize compute layer if enabled
        if self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Bucket Manager compute layer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
                self.enable_compute_layer = False
    
    def __del__(self):
        """Cleanup method to flush buffers on deletion."""
        try:
            self.flush_to_dataset()
        except Exception as e:
            logger.warning(f"Error flushing buffer during cleanup: {e}")
    
    def _store_operation_to_dataset(self, operation: str, bucket_name: str, details: Dict[str, Any], result: Dict[str, Any]):
        """Buffer operation for dataset storage."""
        if not self.enable_dataset_storage:
            return
        
        operation_data = {
            "operation": operation,
            "timestamp": time.time(),
            "bucket_name": bucket_name,
            "details": details,
            "result": result
        }
        
        with self._buffer_lock:
            self._operation_buffer.append(operation_data)
            
            # Flush buffer if it reaches batch size
            if len(self._operation_buffer) >= self.dataset_batch_size:
                self._flush_operations_to_dataset()
    
    def _flush_operations_to_dataset(self):
        """Flush buffered operations to dataset storage."""
        if not self.enable_dataset_storage or not self._operation_buffer:
            return
        
        with self._buffer_lock:
            if not self._operation_buffer:
                return
            
            try:
                # Write operations to temp file
                temp_file = self.bucket_data_path / f"operations_{int(time.time())}.json"
                with open(temp_file, 'w') as f:
                    json.dump(self._operation_buffer, f)
                
                # Store in dataset manager
                if self.dataset_manager and self.dataset_manager.is_available():
                    self.dataset_manager.store(temp_file, metadata={
                        "type": "bucket_operations",
                        "count": len(self._operation_buffer),
                        "timestamp": time.time()
                    })
                
                # Clear buffer
                self._operation_buffer.clear()
                
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
                    
            except Exception as e:
                logger.warning(f"Failed to flush operations to dataset: {e}")
    
    def flush_to_dataset(self):
        """Public method to manually flush operations to dataset storage."""
        self._flush_operations_to_dataset()

    def list_buckets(self) -> List[Dict[str, Any]]:
        """List all configured buckets with detailed statistics."""
        buckets = []
        
        # Get buckets from configuration
        bucket_names = self.config_manager.list_buckets()
        
        for bucket_name in bucket_names:
            bucket_config = self.config_manager.get_bucket_config(bucket_name)
            bucket_path = self.bucket_data_path / bucket_name
            
            # Calculate storage statistics
            size = 0
            file_count = 0
            if bucket_path.exists():
                for file_path in bucket_path.rglob('*'):
                    if file_path.is_file():
                        size += file_path.stat().st_size
                        file_count += 1
            
            # Get quota information
            quota = bucket_config.get('quota', {})
            max_size = quota.get('max_size', None)
            max_files = quota.get('max_files', None)
            
            bucket_info = {
                "name": bucket_name,
                "size": size,
                "files": file_count,
                "quota": {
                    "max_size": max_size,
                    "max_files": max_files,
                    "size_usage_percent": (size / max_size * 100) if max_size else None,
                    "files_usage_percent": (file_count / max_files * 100) if max_files else None
                },
                "backend": bucket_config.get('backend', 'local'),
                "created_at": bucket_config.get('created_at'),
                "updated_at": bucket_config.get('updated_at'),
                "status": "active" if bucket_path.exists() else "inactive"
            }
            buckets.append(bucket_info)
        
        # Store operation to dataset
        result = {"bucket_count": len(buckets)}
        self._store_operation_to_dataset("list_buckets", "", {}, result)
        
        return buckets

    def create_bucket(self, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new bucket with configuration."""
        if not name or not name.strip():
            return {"status": "error", "message": "Bucket name is required"}
        
        # Check if bucket already exists
        if name in self.config_manager.list_buckets():
            return {"status": "error", "message": f"Bucket '{name}' already exists"}
        
        # Create bucket directory
        bucket_path = self.bucket_data_path / name
        bucket_path.mkdir(parents=True, exist_ok=True)
        
        # Set up bucket configuration
        config = {
            "name": name,
            "backend": kwargs.get('backend', 'local'),
            "quota": {
                "max_size": kwargs.get('max_size'),
                "max_files": kwargs.get('max_files')
            },
            "replication": kwargs.get('replication', {}),
            "encryption": kwargs.get('encryption', False),
            "compression": kwargs.get('compression', False),
            "created_at": time.time(),
            "created_by": kwargs.get('created_by', 'system')
        }
        
        self.config_manager.save_bucket_config(name, config)
        
        result = {"status": "success", "message": f"Bucket '{name}' created successfully"}
        
        # Store operation to dataset
        self._store_operation_to_dataset("create_bucket", name, kwargs, result)
        
        return result

    def update_bucket(self, name: str, **kwargs) -> Dict[str, Any]:
        """Update bucket configuration."""
        if name not in self.config_manager.list_buckets():
            return {"status": "error", "message": f"Bucket '{name}' not found"}
        
        config = self.config_manager.get_bucket_config(name)
        
        # Update quota settings
        if 'max_size' in kwargs:
            config.setdefault('quota', {})['max_size'] = kwargs['max_size']
        if 'max_files' in kwargs:
            config.setdefault('quota', {})['max_files'] = kwargs['max_files']
        
        # Update other settings
        for key in ['backend', 'replication', 'encryption', 'compression']:
            if key in kwargs:
                config[key] = kwargs[key]
        
        self.config_manager.save_bucket_config(name, config)
        
        result = {"status": "success", "message": f"Bucket '{name}' updated successfully"}
        
        # Store operation to dataset
        self._store_operation_to_dataset("update_bucket", name, kwargs, result)
        
        return result

    def remove_bucket(self, name: str, force: bool = False) -> Dict[str, Any]:
        """Remove a bucket and its configuration."""
        if name not in self.config_manager.list_buckets():
            return {"status": "error", "message": f"Bucket '{name}' not found"}
        
        bucket_path = self.bucket_data_path / name
        
        # Check if bucket has data and force flag
        if bucket_path.exists() and any(bucket_path.iterdir()) and not force:
            return {"status": "error", "message": f"Bucket '{name}' contains data. Use force=True to delete."}
        
        # Remove bucket data directory
        if bucket_path.exists():
            shutil.rmtree(bucket_path)
        
        # Remove configuration
        self.config_manager.delete_bucket_config(name)
        
        result = {"status": "success", "message": f"Bucket '{name}' removed successfully"}
        
        # Store operation to dataset
        self._store_operation_to_dataset("remove_bucket", name, {"force": force}, result)
        
        return result

    def get_bucket_stats(self, name: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific bucket."""
        if name not in self.config_manager.list_buckets():
            return {"status": "error", "message": f"Bucket '{name}' not found"}
        
        config = self.config_manager.get_bucket_config(name)
        bucket_path = self.bucket_data_path / name
        
        stats = {
            "name": name,
            "config": config,
            "storage": {
                "total_size": 0,
                "file_count": 0,
                "directory_count": 0,
                "largest_file": {"name": "", "size": 0},
                "file_types": {}
            },
            "health": {
                "status": "healthy",
                "issues": []
            }
        }
        
        if bucket_path.exists():
            for path in bucket_path.rglob('*'):
                if path.is_file():
                    size = path.stat().st_size
                    stats["storage"]["total_size"] += size
                    stats["storage"]["file_count"] += 1
                    
                    # Track largest file
                    if size > stats["storage"]["largest_file"]["size"]:
                        stats["storage"]["largest_file"] = {
                            "name": path.name,
                            "size": size
                        }
                    
                    # Track file types
                    ext = path.suffix.lower()
                    stats["storage"]["file_types"][ext] = stats["storage"]["file_types"].get(ext, 0) + 1
                
                elif path.is_dir():
                    stats["storage"]["directory_count"] += 1
            
            # Check quota violations
            quota = config.get('quota', {})
            if quota.get('max_size') and stats["storage"]["total_size"] > quota['max_size']:
                stats["health"]["status"] = "warning"
                stats["health"]["issues"].append("Size quota exceeded")
            
            if quota.get('max_files') and stats["storage"]["file_count"] > quota['max_files']:
                stats["health"]["status"] = "warning"
                stats["health"]["issues"].append("File count quota exceeded")
        else:
            stats["health"]["status"] = "inactive"
            stats["health"]["issues"].append("Bucket directory does not exist")
        
        return stats

    def upload_file(self, bucket_name: str, file_name: str, file_content: bytes) -> Dict[str, Any]:
        """Upload a file to a bucket."""
        if bucket_name not in self.config_manager.list_buckets():
            return {"status": "error", "message": f"Bucket '{bucket_name}' not found"}
        
        bucket_path = self.bucket_data_path / bucket_name
        bucket_path.mkdir(parents=True, exist_ok=True)
        
        file_path = bucket_path / file_name
        
        # Check quota before uploading
        config = self.config_manager.get_bucket_config(bucket_name)
        quota = config.get('quota', {})
        
        current_stats = self.get_bucket_stats(bucket_name)
        if quota.get('max_size'):
            if current_stats["storage"]["total_size"] + len(file_content) > quota['max_size']:
                return {"status": "error", "message": "Upload would exceed size quota"}
        
        if quota.get('max_files'):
            if current_stats["storage"]["file_count"] >= quota['max_files']:
                return {"status": "error", "message": "Upload would exceed file count quota"}
        
        # Write file
        file_path.write_bytes(file_content)
        
        return {
            "status": "success", 
            "message": f"File '{file_name}' uploaded to bucket '{bucket_name}'",
            "file_size": len(file_content)
        }

    def list_files(self, bucket_name: str) -> List[Dict[str, Any]]:
        """List files in a bucket."""
        if bucket_name not in self.config_manager.list_buckets():
            return []
        
        files = []
        bucket_path = self.bucket_data_path / bucket_name
        
        if bucket_path.exists():
            for file_path in bucket_path.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        "name": file_path.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "type": "file"
                    })
                elif file_path.is_dir():
                    files.append({
                        "name": file_path.name,
                        "size": 0,
                        "modified": file_path.stat().st_mtime,
                        "type": "directory"
                    })
        
        return files