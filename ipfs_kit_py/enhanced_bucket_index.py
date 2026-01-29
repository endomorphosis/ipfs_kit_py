"""
Enhanced Bucket Index System for Virtual Filesystem Discovery

Provides quick discovery and analytics for virtual filesystems stored in ~/.ipfs_kit/
Similar architecture to the pin index for consistent performance and usability.
"""

import os
import json
import logging
import anyio
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime

# Analytics dependencies
try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import duckdb
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

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
    accelerate_path = Path(__file__).parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute layer available")
except ImportError:
    HAS_ACCELERATE = False
    AccelerateCompute = None
    logger.info("ipfs_accelerate_py not available - using default compute")

logger = logging.getLogger(__name__)

@dataclass
class BucketMetadata:
    """Metadata for a virtual filesystem bucket."""
    bucket_name: str
    bucket_type: str
    created_at: str
    last_modified: str
    file_count: int
    total_size: int
    structure_type: str
    storage_path: str
    metadata: Dict[str, Any]
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BucketMetadata':
        """Create from dictionary."""
        return cls(**data)

class EnhancedBucketIndex:
    """
    Enhanced bucket index system for virtual filesystem discovery.
    
    Features:
    - Parquet-based storage for efficient querying
    - DuckDB analytics for complex queries
    - Background updates and synchronization
    - Comprehensive search and filtering
    - Storage and access analytics
    """
    
    def __init__(
        self,
        index_dir: Optional[str] = None,
        bucket_vfs_manager=None,
        enable_dataset_storage: bool = False,
        enable_compute_layer: bool = False,
        dataset_batch_size: int = 100
    ):
        """
        Initialize the enhanced bucket index.
        
        Args:
            index_dir: Directory for storing index data
            bucket_vfs_manager: Reference to bucket VFS manager
            enable_dataset_storage: Enable ipfs_datasets_py integration
            enable_compute_layer: Enable ipfs_accelerate_py compute acceleration
            dataset_batch_size: Batch size for dataset operations
        """
        self.index_dir = Path(index_dir or os.path.expanduser("~/.ipfs_kit/bucket_index"))
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.index_dir / "bucket_metadata.parquet"
        self.analytics_file = self.index_dir / "bucket_analytics.parquet"
        
        self.bucket_vfs_manager = bucket_vfs_manager
        self._bucket_cache: Dict[str, BucketMetadata] = {}
        self._update_thread = None
        self._stop_event = None
        
        # Dataset storage configuration
        self.enable_dataset_storage = enable_dataset_storage and HAS_DATASETS
        self.dataset_batch_size = dataset_batch_size
        self.dataset_manager = None
        self._index_buffer = []
        
        # Compute layer configuration
        self.enable_compute_layer = enable_compute_layer and HAS_ACCELERATE
        self.compute_layer = None
        
        # Initialize dataset manager if enabled
        if self.enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(enable=True)
                logger.info("Enhanced Bucket Index dataset storage enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
                self.enable_dataset_storage = False
        
        # Initialize compute layer if enabled
        if self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Enhanced Bucket Index compute layer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
                self.enable_compute_layer = False
        
        # Initialize analytics database
        self.analytics_db = self.index_dir / "bucket_analytics.db"
        self.duckdb_conn = None
        
        logger.info(f"Enhanced Bucket Index initialized at {self.index_dir}")
    
    def __del__(self):
        """Cleanup method to flush buffers on deletion."""
        try:
            self._flush_index_buffer()
        except Exception as e:
            logger.warning(f"Error flushing buffer during cleanup: {e}")
    
    def _initialize_index(self):
        """Initialize the bucket index with existing data."""
        try:
            # Initialize DuckDB connection
            if ANALYTICS_AVAILABLE:
                self._setup_analytics_db()
            
            # Load existing bucket data
            self._load_existing_buckets()
            
        except Exception as e:
            logger.error(f"Failed to initialize bucket index: {e}")
    
    def _track_index_update(self, bucket_name: str, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """Track index update to dataset storage if enabled."""
        if not self.enable_dataset_storage:
            return
        
        update_data = {
            "bucket_name": bucket_name,
            "operation": operation,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        
        self._index_buffer.append(update_data)
        
        # Flush buffer if it reaches batch size
        if len(self._index_buffer) >= self.dataset_batch_size:
            self._flush_index_buffer()
    
    def _flush_index_buffer(self):
        """Flush buffered index updates to dataset storage."""
        if not self.enable_dataset_storage or not self._index_buffer:
            return
        
        try:
            import tempfile
            # Write updates to temp file
            temp_file = Path(tempfile.gettempdir()) / f"index_updates_{int(time.time())}.json"
            with open(temp_file, 'w') as f:
                json.dump(self._index_buffer, f)
            
            # Store in dataset manager
            if self.dataset_manager and self.dataset_manager.is_available():
                self.dataset_manager.store(temp_file, metadata={
                    "type": "bucket_index_updates",
                    "count": len(self._index_buffer),
                    "timestamp": time.time()
                })
            
            # Clear buffer
            self._index_buffer.clear()
            
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
                
        except Exception as e:
            logger.warning(f"Failed to flush index buffer to dataset: {e}")
    
    def _setup_analytics_db(self):
        """Setup DuckDB analytics database."""
        if not ANALYTICS_AVAILABLE:
            return
        
        try:
            if not self.duckdb_conn:
                self.duckdb_conn = duckdb.connect(str(self.analytics_db))
            
            # Create bucket metadata table
            self.duckdb_conn.execute("""
                CREATE TABLE IF NOT EXISTS bucket_metadata (
                    bucket_name VARCHAR PRIMARY KEY,
                    bucket_type VARCHAR,
                    created_at TIMESTAMP,
                    last_modified TIMESTAMP,
                    file_count INTEGER,
                    total_size BIGINT,
                    structure_type VARCHAR,
                    storage_path VARCHAR,
                    metadata JSON,
                    version VARCHAR
                )
            """)
            
            # Create analytics summary table
            self.duckdb_conn.execute("""
                CREATE TABLE IF NOT EXISTS bucket_analytics (
                    analysis_date TIMESTAMP,
                    total_buckets INTEGER,
                    total_files BIGINT,
                    total_size BIGINT,
                    bucket_types JSON,
                    size_distribution JSON,
                    access_patterns JSON
                )
            """)
            
            logger.info("DuckDB analytics database initialized")
            
        except Exception as e:
            logger.error(f"Failed to setup analytics database: {e}")
    
    def _load_existing_buckets(self):
        """Load existing bucket metadata from storage."""
        try:
            if ANALYTICS_AVAILABLE and self.metadata_file.exists():
                df = pd.read_parquet(self.metadata_file)
                
                for _, row in df.iterrows():
                    bucket_metadata = BucketMetadata(
                        bucket_name=row['bucket_name'],
                        bucket_type=row['bucket_type'],
                        created_at=row['created_at'],
                        last_modified=row['last_modified'],
                        file_count=row['file_count'],
                        total_size=row['total_size'],
                        structure_type=row['structure_type'],
                        storage_path=row['storage_path'],
                        metadata=json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata'],
                        version=row.get('version', '1.0')
                    )
                    self._bucket_cache[bucket_metadata.bucket_name] = bucket_metadata
                
                logger.info(f"Loaded {len(self._bucket_cache)} buckets from existing index")
                
        except Exception as e:
            logger.error(f"Failed to load existing buckets: {e}")
    
    def update_from_bucket_manager(self):
        """Update bucket index from bucket VFS manager (sync version)."""
        try:
            if not self.bucket_vfs_manager:
                logger.warning("No bucket VFS manager provided")
                return
            
            # Get bucket list synchronously
            bucket_list = self._get_bucket_list_sync()
            if not bucket_list:
                logger.warning("No buckets found in manager")
                return
            
            updated_count = 0
            for bucket_info in bucket_list:
                try:
                    # Create bucket metadata
                    bucket_metadata = BucketMetadata(
                        bucket_name=bucket_info.get("name", "unknown"),
                        bucket_type=bucket_info.get("type", "general"),
                        created_at=bucket_info.get("created_at", datetime.now().isoformat()),
                        last_modified=bucket_info.get("last_modified", datetime.now().isoformat()),
                        file_count=bucket_info.get("file_count", 0),
                        total_size=bucket_info.get("total_size", 0),
                        structure_type=bucket_info.get("structure_type", "filesystem"),
                        storage_path=bucket_info.get("storage_path", ""),
                        metadata=bucket_info.get("metadata", {}),
                        version="1.0"
                    )
                    
                    # Update cache
                    self._bucket_cache[bucket_metadata.bucket_name] = bucket_metadata
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process bucket {bucket_info}: {e}")
            
            if updated_count > 0:
                self._save_to_storage()
                logger.info(f"Updated bucket index with {updated_count} buckets")
            
        except Exception as e:
            logger.error(f"Failed to update from bucket manager: {e}")
    
    def _get_bucket_list_sync(self) -> List[Dict[str, Any]]:
        """Get bucket list synchronously from bucket manager."""
        try:
            if hasattr(self.bucket_vfs_manager, 'buckets'):
                # Direct access to buckets if available
                bucket_list = []
                for name, bucket in self.bucket_vfs_manager.buckets.items():
                    bucket_info = {
                        "name": name,
                        "type": getattr(bucket, 'bucket_type', 'general'),
                        "created_at": datetime.now().isoformat(),
                        "last_modified": datetime.now().isoformat(),
                        "file_count": 0,
                        "total_size": 0,
                        "structure_type": "filesystem",
                        "storage_path": str(getattr(bucket, 'storage_path', '')),
                        "metadata": {}
                    }
                    bucket_list.append(bucket_info)
                return bucket_list
            else:
                logger.warning("Bucket manager doesn't have direct bucket access")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get bucket list: {e}")
            return []
    
    def _save_to_storage(self):
        """Save bucket metadata to Parquet storage."""
        try:
            if not ANALYTICS_AVAILABLE or not self._bucket_cache:
                return
            
            # Convert to DataFrame
            bucket_data = []
            for bucket_metadata in self._bucket_cache.values():
                data = bucket_metadata.to_dict()
                data['metadata'] = json.dumps(data['metadata'])
                bucket_data.append(data)
            
            df = pd.DataFrame(bucket_data)
            
            # Save to Parquet
            df.to_parquet(self.metadata_file, index=False)
            
            # Update DuckDB
            if self.duckdb_conn:
                self.duckdb_conn.execute("DELETE FROM bucket_metadata")
                self.duckdb_conn.execute(
                    "INSERT INTO bucket_metadata SELECT * FROM df"
                )
            
            logger.debug(f"Saved {len(bucket_data)} buckets to storage")
            
        except Exception as e:
            logger.error(f"Failed to save to storage: {e}")
    
    def list_buckets(self, detailed: bool = False) -> List[Dict[str, Any]]:
        """List all virtual filesystems."""
        buckets = []
        
        for bucket_metadata in self._bucket_cache.values():
            if detailed:
                buckets.append(bucket_metadata.to_dict())
            else:
                buckets.append({
                    'name': bucket_metadata.bucket_name,
                    'type': bucket_metadata.bucket_type,
                    'file_count': bucket_metadata.file_count,
                    'size': bucket_metadata.total_size
                })
        
        return sorted(buckets, key=lambda x: x['name'])
    
    def get_bucket_info(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific bucket."""
        if bucket_name in self._bucket_cache:
            return self._bucket_cache[bucket_name].to_dict()
        return None
    
    def search_buckets(self, query: str, search_type: str = "all") -> List[Dict[str, Any]]:
        """Search buckets by various criteria."""
        results = []
        query_lower = query.lower()
        
        for bucket_metadata in self._bucket_cache.values():
            match = False
            
            if search_type in ["name", "all"]:
                if query_lower in bucket_metadata.bucket_name.lower():
                    match = True
            
            if search_type in ["type", "all"]:
                if query_lower in bucket_metadata.bucket_type.lower():
                    match = True
            
            if search_type in ["structure", "all"]:
                if query_lower in bucket_metadata.structure_type.lower():
                    match = True
            
            if search_type in ["metadata", "all"]:
                metadata_str = json.dumps(bucket_metadata.metadata).lower()
                if query_lower in metadata_str:
                    match = True
            
            if match:
                results.append(bucket_metadata.to_dict())
        
        return sorted(results, key=lambda x: x['bucket_name'])
    
    def get_bucket_types(self) -> Dict[str, int]:
        """Get distribution of bucket types."""
        type_counts = {}
        
        for bucket_metadata in self._bucket_cache.values():
            bucket_type = bucket_metadata.bucket_type
            type_counts[bucket_type] = type_counts.get(bucket_type, 0) + 1
        
        return type_counts
    
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive bucket metrics."""
        total_buckets = len(self._bucket_cache)
        total_files = sum(b.file_count for b in self._bucket_cache.values())
        total_size = sum(b.total_size for b in self._bucket_cache.values())
        
        metrics = {
            'total_buckets': total_buckets,
            'total_files': total_files,
            'total_size': total_size,
            'bucket_types': self.get_bucket_types(),
            'average_files_per_bucket': total_files / total_buckets if total_buckets > 0 else 0,
            'average_size_per_bucket': total_size / total_buckets if total_buckets > 0 else 0,
        }
        
        if ANALYTICS_AVAILABLE and self.duckdb_conn:
            try:
                # Get additional analytics
                result = self.duckdb_conn.execute("""
                    SELECT 
                        MIN(total_size) as min_size,
                        MAX(total_size) as max_size,
                        AVG(total_size) as avg_size,
                        MIN(file_count) as min_files,
                        MAX(file_count) as max_files,
                        AVG(file_count) as avg_files
                    FROM bucket_metadata
                """).fetchone()
                
                if result:
                    metrics.update({
                        'size_stats': {
                            'min': result[0] or 0,
                            'max': result[1] or 0,
                            'avg': result[2] or 0
                        },
                        'file_stats': {
                            'min': result[3] or 0,
                            'max': result[4] or 0,
                            'avg': result[5] or 0
                        }
                    })
            except Exception as e:
                logger.error(f"Failed to get advanced analytics: {e}")
        
        return metrics
    
    def refresh_index(self):
        """Refresh the bucket index from the bucket manager."""
        # Initialize if not done
        if not hasattr(self, '_bucket_cache'):
            self._bucket_cache = {}
        
        # Initialize analytics if available
        if ANALYTICS_AVAILABLE and not self.duckdb_conn:
            self._setup_analytics_db()
        
        # Load existing data
        self._load_existing_buckets()
        
        # Update from bucket manager
        self.update_from_bucket_manager()
        
        return len(self._bucket_cache)

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
