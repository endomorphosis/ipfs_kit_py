import os
import time
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Try relative import first, fallback to absolute import
try:
    from .config_manager import ConfigManager
except ImportError:
    from config_manager import ConfigManager

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
BUCKETS_PATH = IPFS_KIT_PATH / 'buckets'

class BucketManager:
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        BUCKETS_PATH.mkdir(parents=True, exist_ok=True)
        
        # Initialize bucket data directory for actual storage
        self.bucket_data_path = IPFS_KIT_PATH / 'bucket_data'
        self.bucket_data_path.mkdir(parents=True, exist_ok=True)

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
        
        return {"status": "success", "message": f"Bucket '{name}' created successfully"}

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
        
        return {"status": "success", "message": f"Bucket '{name}' updated successfully"}

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
        
        return {"status": "success", "message": f"Bucket '{name}' removed successfully"}

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