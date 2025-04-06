"""
Advanced Partitioning Strategies for ParquetCIDCache.

This module implements sophisticated partitioning strategies for the ParquetCIDCache:
- Time-based partitioning for temporal access patterns
- Size-based partitioning to balance partition sizes
- Content-type based partitioning for workload specialization
- Hash-based partitioning for even distribution
- Dynamic partition management with adaptive strategies

These partitioning strategies help optimize data organization, query performance,
and resource utilization in the ParquetCIDCache system.
"""

import os
import time
import logging
import json
import uuid
import hashlib
import math
import re
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
from pyarrow.dataset import dataset, partitioning

# Configure logging
logger = logging.getLogger(__name__)


class PartitioningStrategy(Enum):
    """Enum representing different partitioning strategies."""
    TIME_BASED = "time_based"       # Partition by time periods
    SIZE_BASED = "size_based"       # Partition by size thresholds
    CONTENT_TYPE = "content_type"   # Partition by content MIME type
    HASH_BASED = "hash_based"       # Partition by hash of key for even distribution
    DYNAMIC = "dynamic"             # Dynamically select strategy based on data characteristics
    HYBRID = "hybrid"               # Combine multiple strategies
    NONE = "none"                   # No partitioning


@dataclass
class PartitionInfo:
    """Information about a partition."""
    partition_id: str
    path: str
    strategy: PartitioningStrategy
    created_at: float
    last_modified: float
    record_count: int
    size_bytes: int
    metadata: Dict[str, Any]
    statistics: Dict[str, Any]

    def get_age_days(self) -> float:
        """Get the age of the partition in days."""
        return (time.time() - self.created_at) / (24 * 3600)
    
    def get_activity_score(self) -> float:
        """
        Calculate an activity score for the partition.
        Higher scores indicate more recent/frequent activity.
        """
        age_factor = math.exp(-self.get_age_days() / 30)  # Decay factor based on age
        size_factor = min(1.0, self.size_bytes / (500 * 1024 * 1024))  # Size factor, max at 500MB
        record_density = self.record_count / max(1, self.size_bytes // 1024)  # Records per KB
        
        return age_factor * (0.7 + 0.3 * size_factor) * (1 + 0.2 * record_density)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "partition_id": self.partition_id,
            "path": self.path,
            "strategy": self.strategy.value,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "record_count": self.record_count,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
            "statistics": self.statistics
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PartitionInfo':
        """Create PartitionInfo from dictionary."""
        strategy_value = data.get("strategy", "none")
        try:
            strategy = PartitioningStrategy(strategy_value)
        except ValueError:
            logger.warning(f"Unknown partitioning strategy: {strategy_value}, using NONE")
            strategy = PartitioningStrategy.NONE
            
        return cls(
            partition_id=data.get("partition_id", ""),
            path=data.get("path", ""),
            strategy=strategy,
            created_at=data.get("created_at", 0.0),
            last_modified=data.get("last_modified", 0.0),
            record_count=data.get("record_count", 0),
            size_bytes=data.get("size_bytes", 0),
            metadata=data.get("metadata", {}),
            statistics=data.get("statistics", {})
        )


class TimeBasedPartitionStrategy:
    """Partitions data based on time periods."""
    
    PERIOD_FORMATS = {
        "hourly": "%Y-%m-%d-%H",
        "daily": "%Y-%m-%d",
        "weekly": "%Y-W%W",
        "monthly": "%Y-%m",
        "quarterly": "%Y-Q%q",
        "yearly": "%Y"
    }
    
    def __init__(self, 
                 timestamp_column: str = "timestamp", 
                 period: str = "daily",
                 base_path: str = "partitions/time"):
        """
        Initialize time-based partitioning.
        
        Args:
            timestamp_column: Column to use for time-based partitioning
            period: Time period for partitioning (hourly, daily, weekly, monthly, quarterly, yearly)
            base_path: Base directory for time-based partitions
        """
        if period not in self.PERIOD_FORMATS:
            raise ValueError(f"Invalid period: {period}. Must be one of: {list(self.PERIOD_FORMATS.keys())}")
            
        self.timestamp_column = timestamp_column
        self.period = period
        self.format_string = self.PERIOD_FORMATS[period]
        self.base_path = base_path
        
    def get_partition_path(self, timestamp: Union[float, datetime]) -> str:
        """
        Get the partition path for a given timestamp.
        
        Args:
            timestamp: Timestamp as float (Unix time) or datetime object
            
        Returns:
            Path string for the partition
        """
        # Convert to datetime if timestamp is a float
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
        else:
            dt = timestamp
            
        # Special handling for quarters
        if self.period == "quarterly":
            quarter = (dt.month - 1) // 3 + 1
            period_str = dt.strftime(self.format_string.replace('%q', str(quarter)))
        else:
            period_str = dt.strftime(self.format_string)
            
        return os.path.join(self.base_path, period_str)
    
    def partition_record(self, record: Dict[str, Any]) -> str:
        """
        Determine the partition path for a given record.
        
        Args:
            record: Record dictionary
            
        Returns:
            Path string for the record's partition
        """
        timestamp = record.get(self.timestamp_column)
        if timestamp is None:
            # Default to current time if timestamp not found
            logger.warning(f"Timestamp column '{self.timestamp_column}' not found in record, using current time")
            timestamp = time.time()
            
        return self.get_partition_path(timestamp)
    
    def create_partition_schema(self) -> pa.Schema:
        """
        Create the partition schema for PyArrow Dataset.
        
        Returns:
            PyArrow partition schema
        """
        if self.period == "hourly":
            return partitioning.DirectoryPartitioning(
                pa.schema([
                    pa.field("year", pa.int32()),
                    pa.field("month", pa.int32()),
                    pa.field("day", pa.int32()),
                    pa.field("hour", pa.int32())
                ])
            )
        elif self.period == "daily":
            return partitioning.DirectoryPartitioning(
                pa.schema([
                    pa.field("year", pa.int32()),
                    pa.field("month", pa.int32()),
                    pa.field("day", pa.int32())
                ])
            )
        elif self.period == "monthly":
            return partitioning.DirectoryPartitioning(
                pa.schema([
                    pa.field("year", pa.int32()),
                    pa.field("month", pa.int32())
                ])
            )
        elif self.period == "quarterly":
            return partitioning.DirectoryPartitioning(
                pa.schema([
                    pa.field("year", pa.int32()),
                    pa.field("quarter", pa.int32())
                ])
            )
        elif self.period == "yearly":
            return partitioning.DirectoryPartitioning(
                pa.schema([
                    pa.field("year", pa.int32())
                ])
            )
        else:  # weekly
            return partitioning.DirectoryPartitioning(
                pa.schema([
                    pa.field("year", pa.int32()),
                    pa.field("week", pa.int32())
                ])
            )
            
    def get_activity_timeframe(self, timeframe_days: int = 30) -> List[str]:
        """
        Get a list of partition paths that could be active in the given timeframe.
        
        Args:
            timeframe_days: Number of days to consider active
            
        Returns:
            List of partition paths that could contain active data
        """
        active_partitions = []
        now = datetime.now()
        
        # Generate partitions for the timeframe
        for days_ago in range(timeframe_days + 1):
            date = now - timedelta(days=days_ago)
            
            if self.period == "hourly":
                # For hourly, include all hours for the day
                for hour in range(24):
                    date_with_hour = date.replace(hour=hour)
                    active_partitions.append(self.get_partition_path(date_with_hour))
            else:
                active_partitions.append(self.get_partition_path(date))
                
        return active_partitions


class SizeBasedPartitionStrategy:
    """Partitions data to maintain balanced partition sizes."""
    
    def __init__(self, 
                 target_size_mb: int = 256,
                 max_size_mb: int = 512,
                 base_path: str = "partitions/size"):
        """
        Initialize size-based partitioning.
        
        Args:
            target_size_mb: Target size for partitions in MB
            max_size_mb: Maximum size for partitions in MB
            base_path: Base directory for size-based partitions
        """
        self.target_size_bytes = target_size_mb * 1024 * 1024
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.base_path = base_path
        self.current_partition_id = None
        self.current_partition_size = 0
        
    def initialize_partition(self) -> str:
        """
        Initialize a new partition.
        
        Returns:
            New partition ID
        """
        self.current_partition_id = f"size_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.current_partition_size = 0
        return self.current_partition_id
    
    def get_partition_path(self, partition_id: str = None) -> str:
        """
        Get the path for a partition.
        
        Args:
            partition_id: Partition ID (uses current partition if None)
            
        Returns:
            Partition path
        """
        pid = partition_id or self.current_partition_id
        if pid is None:
            pid = self.initialize_partition()
            
        return os.path.join(self.base_path, pid)
    
    def should_rotate_partition(self, record_size: int) -> bool:
        """
        Check if a new partition should be created based on size.
        
        Args:
            record_size: Size of the record being added
            
        Returns:
            True if partition should be rotated, False otherwise
        """
        # Initialize if needed
        if self.current_partition_id is None:
            self.initialize_partition()
            return False
            
        # Check if adding this record would exceed the maximum size
        if self.current_partition_size + record_size > self.max_size_bytes:
            return True
            
        # Check if we're already over the target size
        return self.current_partition_size >= self.target_size_bytes
    
    def add_record_size(self, size: int):
        """Track the size of a record added to the current partition."""
        self.current_partition_size += size
        
    def partition_record(self, record: Dict[str, Any], record_size: int = 1024) -> str:
        """
        Determine the partition path for a given record.
        
        Args:
            record: Record dictionary
            record_size: Estimated size of the record in bytes
            
        Returns:
            Path string for the record's partition
        """
        if self.current_partition_id is None or self.should_rotate_partition(record_size):
            self.initialize_partition()
            
        self.add_record_size(record_size)
        return self.get_partition_path()


class ContentTypePartitionStrategy:
    """Partitions data based on content MIME type."""
    
    # Predefined content type groups for common MIME types
    CONTENT_TYPE_GROUPS = {
        "image": [
            "image/jpeg", "image/png", "image/gif", "image/webp", 
            "image/svg+xml", "image/tiff", "image/bmp"
        ],
        "video": [
            "video/mp4", "video/webm", "video/ogg", "video/quicktime",
            "video/x-msvideo", "video/x-matroska"
        ],
        "audio": [
            "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm",
            "audio/aac", "audio/flac", "audio/midi"
        ],
        "document": [
            "application/pdf", "application/msword", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain", "text/html", "text/css", "text/javascript"
        ],
        "archive": [
            "application/zip", "application/x-rar-compressed", "application/x-tar",
            "application/gzip", "application/x-7z-compressed"
        ],
        "code": [
            "text/x-python", "text/x-java", "text/x-c", "text/x-cpp",
            "text/x-csharp", "text/x-javascript", "text/x-php",
            "text/x-ruby", "text/x-go", "text/x-rust", "text/x-typescript",
            "application/json", "application/xml"
        ]
    }
    
    def __init__(self, 
                 content_type_column: str = "mime_type", 
                 use_groups: bool = True,
                 base_path: str = "partitions/content_type"):
        """
        Initialize content-type partitioning.
        
        Args:
            content_type_column: Column name containing the content MIME type
            use_groups: Whether to group similar content types
            base_path: Base directory for content-type partitions
        """
        self.content_type_column = content_type_column
        self.use_groups = use_groups
        self.base_path = base_path
        
        # Build reverse lookup for content type to group
        self.type_to_group = {}
        if use_groups:
            for group, types in self.CONTENT_TYPE_GROUPS.items():
                for mime_type in types:
                    self.type_to_group[mime_type] = group
                    
    def get_content_group(self, content_type: str) -> str:
        """
        Get the content group for a MIME type.
        
        Args:
            content_type: MIME type string
            
        Returns:
            Content group or the content type itself if not grouped
        """
        if not self.use_groups:
            return self._normalize_content_type(content_type)
            
        # Check exact match in our predefined groups
        if content_type in self.type_to_group:
            return self.type_to_group[content_type]
            
        # Try to match by main type (e.g., "image/x-custom" -> "image")
        main_type = content_type.split('/')[0] if '/' in content_type else content_type
        if main_type in self.CONTENT_TYPE_GROUPS:
            return main_type
            
        # Default to "other" for unknown types
        return "other"
    
    def _normalize_content_type(self, content_type: str) -> str:
        """Normalize content type for use in file paths."""
        if not content_type:
            return "unknown"
            
        # Replace any characters that might cause issues in file paths
        normalized = re.sub(r'[^\w\-\.]', '_', content_type)
        return normalized
        
    def get_partition_path(self, content_type: str) -> str:
        """
        Get the partition path for a content type.
        
        Args:
            content_type: MIME type string
            
        Returns:
            Path string for the partition
        """
        group = self.get_content_group(content_type)
        return os.path.join(self.base_path, group)
        
    def partition_record(self, record: Dict[str, Any]) -> str:
        """
        Determine the partition path for a given record.
        
        Args:
            record: Record dictionary
            
        Returns:
            Path string for the record's partition
        """
        content_type = record.get(self.content_type_column, "unknown")
        return self.get_partition_path(content_type)
    
    def create_partition_schema(self) -> pa.Schema:
        """
        Create the partition schema for PyArrow Dataset.
        
        Returns:
            PyArrow partition schema
        """
        return partitioning.DirectoryPartitioning(
            pa.schema([
                pa.field("content_type", pa.string())
            ])
        )


class HashBasedPartitionStrategy:
    """Partitions data based on hash of a key for even distribution."""
    
    def __init__(self, 
                 key_column: str = "cid",
                 num_partitions: int = 16,
                 hash_algorithm: str = "xxh64",
                 base_path: str = "partitions/hash"):
        """
        Initialize hash-based partitioning.
        
        Args:
            key_column: Column to use as partition key
            num_partitions: Number of partitions (must be power of 2)
            hash_algorithm: Hash algorithm to use (md5, sha1, xxh64)
            base_path: Base directory for hash-based partitions
        """
        # Ensure num_partitions is a power of 2
        if num_partitions & (num_partitions - 1) != 0:
            # Round up to next power of 2
            num_partitions = 1 << (num_partitions - 1).bit_length()
            logger.warning(f"Adjusted num_partitions to next power of 2: {num_partitions}")
            
        self.key_column = key_column
        self.num_partitions = num_partitions
        self.hash_algorithm = hash_algorithm
        self.base_path = base_path
        self.partition_mask = num_partitions - 1  # Bitmask for hash partitioning
        
    def compute_hash(self, key: str) -> int:
        """
        Compute hash value for a key.
        
        Args:
            key: Key to hash
            
        Returns:
            Hash value (integer)
        """
        key_bytes = str(key).encode('utf-8')
        
        if self.hash_algorithm == "md5":
            hash_hex = hashlib.md5(key_bytes).hexdigest()
            return int(hash_hex[:8], 16)
        elif self.hash_algorithm == "sha1":
            hash_hex = hashlib.sha1(key_bytes).hexdigest()
            return int(hash_hex[:8], 16)
        elif self.hash_algorithm == "xxh64":
            try:
                import xxhash
                return xxhash.xxh64(key_bytes).intdigest()
            except ImportError:
                logger.warning("xxhash not available, falling back to md5")
                hash_hex = hashlib.md5(key_bytes).hexdigest()
                return int(hash_hex[:8], 16)
        else:
            # Default to md5 for unknown algorithm
            hash_hex = hashlib.md5(key_bytes).hexdigest()
            return int(hash_hex[:8], 16)
            
    def get_partition_number(self, key: str) -> int:
        """
        Get the partition number for a key.
        
        Args:
            key: Key to partition
            
        Returns:
            Partition number (0 to num_partitions-1)
        """
        hash_value = self.compute_hash(key)
        return hash_value & self.partition_mask
        
    def get_partition_path(self, key: str) -> str:
        """
        Get the partition path for a key.
        
        Args:
            key: Key to partition
            
        Returns:
            Path string for the partition
        """
        partition_number = self.get_partition_number(key)
        return os.path.join(self.base_path, f"{partition_number:04x}")
        
    def partition_record(self, record: Dict[str, Any]) -> str:
        """
        Determine the partition path for a given record.
        
        Args:
            record: Record dictionary
            
        Returns:
            Path string for the record's partition
        """
        key = record.get(self.key_column)
        if key is None:
            # Use a random key if the key column is missing
            logger.warning(f"Key column '{self.key_column}' not found in record, using random key")
            key = uuid.uuid4().hex
            
        return self.get_partition_path(key)
    
    def get_all_partition_paths(self) -> List[str]:
        """
        Get a list of all possible partition paths.
        
        Returns:
            List of all partition paths
        """
        return [
            os.path.join(self.base_path, f"{i:04x}")
            for i in range(self.num_partitions)
        ]


class DynamicPartitionManager:
    """Manages partitioning strategies dynamically based on data characteristics."""
    
    def __init__(self, 
                 base_path: str = "partitions",
                 partitions_file: str = "partition_registry.json",
                 default_strategy: PartitioningStrategy = PartitioningStrategy.HASH_BASED,
                 auto_rebalance: bool = True):
        """
        Initialize the dynamic partition manager.
        
        Args:
            base_path: Base directory for partitions
            partitions_file: File to store partition registry
            default_strategy: Default partitioning strategy
            auto_rebalance: Whether to automatically rebalance partitions
        """
        self.base_path = os.path.expanduser(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        
        self.partitions_file = os.path.join(self.base_path, partitions_file)
        self.default_strategy = default_strategy
        self.auto_rebalance = auto_rebalance
        
        # Initialize strategy instances
        self.time_strategy = TimeBasedPartitionStrategy(
            base_path=os.path.join(self.base_path, "time")
        )
        
        self.size_strategy = SizeBasedPartitionStrategy(
            base_path=os.path.join(self.base_path, "size")
        )
        
        self.content_strategy = ContentTypePartitionStrategy(
            base_path=os.path.join(self.base_path, "content")
        )
        
        self.hash_strategy = HashBasedPartitionStrategy(
            base_path=os.path.join(self.base_path, "hash")
        )
        
        # Load partition registry
        self.partitions = self._load_partitions()
        
        # Workload characteristics
        self.workload_stats = {
            "temporal_access_score": 0.0,  # Higher values indicate time-based access patterns
            "size_variance_score": 0.0,    # Higher values indicate varying record sizes
            "content_type_score": 0.0,     # Higher values indicate content type driven access
            "access_distribution_score": 0.0,  # Higher values indicate uneven key access
            "total_records": 0,
            "recent_access_patterns": []
        }
        
    def _load_partitions(self) -> Dict[str, PartitionInfo]:
        """
        Load partition registry from file.
        
        Returns:
            Dictionary mapping partition IDs to PartitionInfo objects
        """
        try:
            if os.path.exists(self.partitions_file):
                with open(self.partitions_file, 'r') as f:
                    data = json.load(f)
                    
                partitions = {}
                for partition_id, partition_data in data.items():
                    partitions[partition_id] = PartitionInfo.from_dict(partition_data)
                    
                return partitions
            else:
                logger.info(f"Partition registry file not found at {self.partitions_file}, initializing empty registry")
                return {}
        except Exception as e:
            logger.error(f"Error loading partition registry: {e}")
            return {}
            
    def _save_partitions(self):
        """Save partition registry to file."""
        try:
            data = {}
            for partition_id, partition_info in self.partitions.items():
                data[partition_id] = partition_info.to_dict()
                
            with open(self.partitions_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving partition registry: {e}")
    
    def get_strategy_for_record(self, record: Dict[str, Any]) -> PartitioningStrategy:
        """
        Determine the best partitioning strategy for a record based on data characteristics.
        
        Args:
            record: Record dictionary
            
        Returns:
            Selected partitioning strategy
        """
        # Use workload stats to make an informed decision
        max_score = 0.0
        selected_strategy = self.default_strategy
        
        scores = {
            PartitioningStrategy.TIME_BASED: self.workload_stats["temporal_access_score"],
            PartitioningStrategy.SIZE_BASED: self.workload_stats["size_variance_score"],
            PartitioningStrategy.CONTENT_TYPE: self.workload_stats["content_type_score"],
            PartitioningStrategy.HASH_BASED: self.workload_stats["access_distribution_score"]
        }
        
        # Apply specific rules for each record type
        # Time-based: prefer for records with timestamp
        if "timestamp" in record or "created_at" in record or "last_modified" in record:
            scores[PartitioningStrategy.TIME_BASED] += 0.2
            
        # Content-type: prefer for records with mime_type
        if "mime_type" in record and record["mime_type"]:
            scores[PartitioningStrategy.CONTENT_TYPE] += 0.3
            
        # Size-based: prefer for large records
        record_size = len(str(record))  # Simple size estimation
        if record_size > 10 * 1024:  # > 10KB
            scores[PartitioningStrategy.SIZE_BASED] += 0.2
            
        # Select strategy with highest score
        for strategy, score in scores.items():
            if score > max_score:
                max_score = score
                selected_strategy = strategy
                
        return selected_strategy
        
    def get_partition_for_record(self, record: Dict[str, Any]) -> str:
        """
        Get the partition path for a record.
        
        Args:
            record: Record dictionary
            
        Returns:
            Path string for the record's partition
        """
        strategy = self.get_strategy_for_record(record)
        
        if strategy == PartitioningStrategy.TIME_BASED:
            return self.time_strategy.partition_record(record)
        elif strategy == PartitioningStrategy.SIZE_BASED:
            return self.size_strategy.partition_record(record)
        elif strategy == PartitioningStrategy.CONTENT_TYPE:
            return self.content_strategy.partition_record(record)
        elif strategy == PartitioningStrategy.HASH_BASED:
            return self.hash_strategy.partition_record(record)
        else:
            # Default to hash-based if strategy not implemented
            return self.hash_strategy.partition_record(record)
            
    def register_partition(self, 
                           partition_path: str, 
                           strategy: PartitioningStrategy,
                           record_count: int = 0,
                           size_bytes: int = 0,
                           metadata: Dict[str, Any] = None) -> str:
        """
        Register a new partition in the registry.
        
        Args:
            partition_path: Path to the partition
            strategy: Partitioning strategy used
            record_count: Number of records in the partition
            size_bytes: Size of the partition in bytes
            metadata: Additional metadata for the partition
            
        Returns:
            Partition ID
        """
        # Generate partition ID
        partition_id = f"{strategy.value}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create partition info
        partition_info = PartitionInfo(
            partition_id=partition_id,
            path=partition_path,
            strategy=strategy,
            created_at=time.time(),
            last_modified=time.time(),
            record_count=record_count,
            size_bytes=size_bytes,
            metadata=metadata or {},
            statistics={}
        )
        
        # Add to registry
        self.partitions[partition_id] = partition_info
        
        # Save registry
        self._save_partitions()
        
        return partition_id
    
    def update_partition_stats(self, 
                              partition_id: str, 
                              record_count: int = None,
                              size_bytes: int = None,
                              statistics: Dict[str, Any] = None):
        """
        Update statistics for a partition.
        
        Args:
            partition_id: Partition ID
            record_count: New record count (if None, keep existing)
            size_bytes: New size in bytes (if None, keep existing)
            statistics: New statistics (if None, keep existing)
        """
        if partition_id not in self.partitions:
            logger.warning(f"Partition {partition_id} not found in registry")
            return
            
        partition = self.partitions[partition_id]
        
        # Update record count if provided
        if record_count is not None:
            partition.record_count = record_count
            
        # Update size if provided
        if size_bytes is not None:
            partition.size_bytes = size_bytes
            
        # Update statistics if provided
        if statistics is not None:
            partition.statistics.update(statistics)
            
        # Update last modified timestamp
        partition.last_modified = time.time()
        
        # Save registry
        self._save_partitions()
        
    def get_partitions_by_strategy(self, strategy: PartitioningStrategy) -> List[PartitionInfo]:
        """
        Get all partitions using a specific strategy.
        
        Args:
            strategy: Partitioning strategy
            
        Returns:
            List of PartitionInfo objects
        """
        return [
            partition for partition in self.partitions.values()
            if partition.strategy == strategy
        ]
        
    def update_workload_stats(self, 
                              temporal_access_score: float = None,
                              size_variance_score: float = None,
                              content_type_score: float = None,
                              access_distribution_score: float = None,
                              total_records: int = None,
                              recent_access: Dict[str, Any] = None):
        """
        Update workload statistics used for dynamic strategy selection.
        
        Args:
            temporal_access_score: Score for temporal access patterns
            size_variance_score: Score for size variance
            content_type_score: Score for content type driven access
            access_distribution_score: Score for uneven key access
            total_records: Total number of records
            recent_access: Recent access pattern information
        """
        # Update scores if provided
        if temporal_access_score is not None:
            self.workload_stats["temporal_access_score"] = temporal_access_score
            
        if size_variance_score is not None:
            self.workload_stats["size_variance_score"] = size_variance_score
            
        if content_type_score is not None:
            self.workload_stats["content_type_score"] = content_type_score
            
        if access_distribution_score is not None:
            self.workload_stats["access_distribution_score"] = access_distribution_score
            
        if total_records is not None:
            self.workload_stats["total_records"] = total_records
            
        # Add recent access pattern if provided
        if recent_access is not None:
            self.workload_stats["recent_access_patterns"].append({
                "timestamp": time.time(),
                **recent_access
            })
            
            # Keep only the last 100 access patterns
            if len(self.workload_stats["recent_access_patterns"]) > 100:
                self.workload_stats["recent_access_patterns"] = \
                    self.workload_stats["recent_access_patterns"][-100:]
                    
    def analyze_access_patterns(self, days: int = 7):
        """
        Analyze access patterns to update workload statistics.
        
        Args:
            days: Number of days of access history to analyze
        """
        # Filter recent access patterns by time
        cutoff_time = time.time() - (days * 24 * 3600)
        recent_patterns = [
            pattern for pattern in self.workload_stats["recent_access_patterns"]
            if pattern["timestamp"] >= cutoff_time
        ]
        
        if not recent_patterns:
            logger.info(f"No access patterns found in the last {days} days")
            return
            
        # Analyze temporal patterns
        timestamp_counts = {}
        for pattern in recent_patterns:
            if "timestamp" in pattern:
                # Round to hour
                hour = datetime.fromtimestamp(pattern["timestamp"]).strftime("%Y-%m-%d %H:00:00")
                timestamp_counts[hour] = timestamp_counts.get(hour, 0) + 1
                
        # Calculate temporal concentration
        if timestamp_counts:
            max_count = max(timestamp_counts.values())
            total_count = sum(timestamp_counts.values())
            temporal_concentration = max_count / total_count if total_count > 0 else 0
            self.workload_stats["temporal_access_score"] = temporal_concentration
            
        # Analyze content type patterns
        content_type_counts = {}
        for pattern in recent_patterns:
            if "content_type" in pattern:
                content_type = pattern["content_type"]
                content_type_counts[content_type] = content_type_counts.get(content_type, 0) + 1
                
        # Calculate content type concentration
        if content_type_counts:
            max_count = max(content_type_counts.values())
            total_count = sum(content_type_counts.values())
            content_type_concentration = max_count / total_count if total_count > 0 else 0
            self.workload_stats["content_type_score"] = content_type_concentration
            
        # Analyze key access patterns
        key_counts = {}
        for pattern in recent_patterns:
            if "key" in pattern:
                key = pattern["key"]
                key_counts[key] = key_counts.get(key, 0) + 1
                
        # Calculate key access distribution skew
        if key_counts:
            max_count = max(key_counts.values())
            total_count = sum(key_counts.values())
            key_concentration = max_count / total_count if total_count > 0 else 0
            self.workload_stats["access_distribution_score"] = 1.0 - key_concentration  # Invert for even distribution
            
        # Analyze record sizes
        if all("size" in pattern for pattern in recent_patterns):
            sizes = [pattern["size"] for pattern in recent_patterns if "size" in pattern]
            if sizes:
                avg_size = sum(sizes) / len(sizes)
                variance = sum((size - avg_size) ** 2 for size in sizes) / len(sizes)
                std_dev = math.sqrt(variance)
                size_variance_score = min(1.0, std_dev / avg_size) if avg_size > 0 else 0
                self.workload_stats["size_variance_score"] = size_variance_score
                
    def check_rebalance_partitions(self, force: bool = False) -> bool:
        """
        Check if partitions need rebalancing and perform rebalance if needed.
        
        Args:
            force: Force rebalance regardless of thresholds
            
        Returns:
            True if rebalance was performed, False otherwise
        """
        if not self.auto_rebalance and not force:
            return False
            
        # Analyze partitions
        strategy_counts = {}
        strategy_sizes = {}
        strategy_records = {}
        
        for partition in self.partitions.values():
            strategy = partition.strategy
            
            if strategy not in strategy_counts:
                strategy_counts[strategy] = 0
                strategy_sizes[strategy] = 0
                strategy_records[strategy] = 0
                
            strategy_counts[strategy] += 1
            strategy_sizes[strategy] += partition.size_bytes
            strategy_records[strategy] += partition.record_count
            
        # Make rebalance decision based on statistics
        needs_rebalance = False
        
        # Check for skewed distribution
        if strategy_counts:
            total_partitions = sum(strategy_counts.values())
            total_records = sum(strategy_records.values())
            
            # If one strategy has >80% of partitions but <20% of records, consider rebalancing
            for strategy, count in strategy_counts.items():
                if count / total_partitions > 0.8 and strategy_records.get(strategy, 0) / total_records < 0.2:
                    needs_rebalance = True
                    break
                    
        # If rebalance needed or forced, update strategy weights
        if needs_rebalance or force:
            logger.info("Partition rebalance needed, updating strategy weights")
            
            # Update workload stats based on actual data distribution
            self.analyze_access_patterns()
            
            # Perform any necessary rebalancing actions
            # In a real implementation, this might involve moving data between partitions
            
            return True
            
        return False
        
    def get_optimal_strategy(self) -> PartitioningStrategy:
        """
        Get the optimal partitioning strategy based on current workload stats.
        
        Returns:
            The optimal partitioning strategy
        """
        scores = {
            PartitioningStrategy.TIME_BASED: self.workload_stats["temporal_access_score"],
            PartitioningStrategy.SIZE_BASED: self.workload_stats["size_variance_score"],
            PartitioningStrategy.CONTENT_TYPE: self.workload_stats["content_type_score"],
            PartitioningStrategy.HASH_BASED: self.workload_stats["access_distribution_score"]
        }
        
        # Return strategy with highest score
        return max(scores.items(), key=lambda x: x[1])[0]
        
    def build_dataset(self, filter_expression=None) -> pa.dataset:
        """
        Build a PyArrow dataset from all partitions.
        
        Args:
            filter_expression: Optional filter expression for the dataset
            
        Returns:
            PyArrow dataset
        """
        # Get all partition paths
        partition_paths = [partition.path for partition in self.partitions.values()]
        
        # Create the dataset
        return dataset(
            partition_paths,
            format="parquet",
            partitioning="hive",  # Automatically discover partitioning
            filter=filter_expression
        )
        
    def get_active_partitions(self, days: int = 30) -> List[PartitionInfo]:
        """
        Get partitions that have been active in the specified timeframe.
        
        Args:
            days: Number of days to consider active
            
        Returns:
            List of active partitions
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        return [
            partition for partition in self.partitions.values()
            if partition.last_modified >= cutoff_time
        ]


class AdvancedPartitionManager:
    """
    High-level manager for advanced partitioning strategies.
    
    This class provides a single interface for all partitioning strategies:
    - Time-based partitioning for temporal access patterns
    - Size-based partitioning to balance partition sizes
    - Content-type based partitioning for workload specialization
    - Hash-based partitioning for even distribution
    - Dynamic partitioning with automatic strategy selection
    """
    
    def __init__(self, 
                 base_path: str = None, 
                 strategy: Union[str, PartitioningStrategy] = "dynamic",
                 config: Dict[str, Any] = None):
        """
        Initialize the advanced partition manager.
        
        Args:
            base_path: Base directory for partitions (defaults to ~/.ipfs_kit/partitions)
            strategy: Partitioning strategy to use
            config: Configuration options for the selected strategy
        """
        # Set default base path if not provided
        if base_path is None:
            base_path = os.path.expanduser("~/.ipfs_kit/partitions")
            
        # Create base directory if it doesn't exist
        os.makedirs(base_path, exist_ok=True)
        
        self.base_path = base_path
        self.config = config or {}
        
        # Convert string strategy to enum if needed
        if isinstance(strategy, str):
            try:
                self.strategy = PartitioningStrategy(strategy)
            except ValueError:
                logger.warning(f"Unknown partitioning strategy: {strategy}, using DYNAMIC")
                self.strategy = PartitioningStrategy.DYNAMIC
        else:
            self.strategy = strategy
            
        # Initialize the appropriate strategy
        if self.strategy == PartitioningStrategy.TIME_BASED:
            period = self.config.get("period", "daily")
            timestamp_column = self.config.get("timestamp_column", "timestamp")
            time_base_path = os.path.join(self.base_path, "time")
            self.strategy_impl = TimeBasedPartitionStrategy(
                timestamp_column=timestamp_column,
                period=period,
                base_path=time_base_path
            )
            
        elif self.strategy == PartitioningStrategy.SIZE_BASED:
            target_size_mb = self.config.get("target_size_mb", 256)
            max_size_mb = self.config.get("max_size_mb", 512)
            size_base_path = os.path.join(self.base_path, "size")
            self.strategy_impl = SizeBasedPartitionStrategy(
                target_size_mb=target_size_mb,
                max_size_mb=max_size_mb,
                base_path=size_base_path
            )
            
        elif self.strategy == PartitioningStrategy.CONTENT_TYPE:
            content_type_column = self.config.get("content_type_column", "mime_type")
            use_groups = self.config.get("use_groups", True)
            content_base_path = os.path.join(self.base_path, "content")
            self.strategy_impl = ContentTypePartitionStrategy(
                content_type_column=content_type_column,
                use_groups=use_groups,
                base_path=content_base_path
            )
            
        elif self.strategy == PartitioningStrategy.HASH_BASED:
            key_column = self.config.get("key_column", "cid")
            num_partitions = self.config.get("num_partitions", 16)
            hash_algorithm = self.config.get("hash_algorithm", "xxh64")
            hash_base_path = os.path.join(self.base_path, "hash")
            self.strategy_impl = HashBasedPartitionStrategy(
                key_column=key_column,
                num_partitions=num_partitions,
                hash_algorithm=hash_algorithm,
                base_path=hash_base_path
            )
            
        elif self.strategy == PartitioningStrategy.DYNAMIC:
            default_strategy_name = self.config.get("default_strategy", "hash_based")
            try:
                default_strategy = PartitioningStrategy(default_strategy_name)
            except ValueError:
                default_strategy = PartitioningStrategy.HASH_BASED
                
            auto_rebalance = self.config.get("auto_rebalance", True)
            self.strategy_impl = DynamicPartitionManager(
                base_path=self.base_path,
                default_strategy=default_strategy,
                auto_rebalance=auto_rebalance
            )
            
        elif self.strategy == PartitioningStrategy.HYBRID:
            # Hybrid uses DynamicPartitionManager but with fixed weights
            temporal_weight = self.config.get("temporal_weight", 0.25)
            content_weight = self.config.get("content_weight", 0.25)
            size_weight = self.config.get("size_weight", 0.25)
            distribution_weight = self.config.get("distribution_weight", 0.25)
            
            self.strategy_impl = DynamicPartitionManager(base_path=self.base_path)
            
            # Set fixed weights
            self.strategy_impl.update_workload_stats(
                temporal_access_score=temporal_weight,
                content_type_score=content_weight,
                size_variance_score=size_weight,
                access_distribution_score=distribution_weight
            )
            
        else:  # PartitioningStrategy.NONE or unknown
            # Default to hash-based with a single partition
            hash_base_path = os.path.join(self.base_path, "single")
            self.strategy_impl = HashBasedPartitionStrategy(
                num_partitions=1,
                base_path=hash_base_path
            )
            
        logger.info(f"Initialized {self.strategy.value} partitioning strategy at {self.base_path}")
        
    def get_partition_path(self, record: Dict[str, Any]) -> str:
        """
        Get the partition path for a record.
        
        Args:
            record: Record dictionary
            
        Returns:
            Path string for the record's partition
        """
        if isinstance(self.strategy_impl, DynamicPartitionManager):
            return self.strategy_impl.get_partition_for_record(record)
        else:
            return self.strategy_impl.partition_record(record)
            
    def register_access(self, record: Dict[str, Any], operation: str = "read", size: int = None):
        """
        Register a record access for workload analysis.
        
        Args:
            record: Record that was accessed
            operation: Operation performed (read, write, query)
            size: Size of the record in bytes
        """
        if isinstance(self.strategy_impl, DynamicPartitionManager):
            # Extract key information
            key = record.get("cid") or record.get("id")
            content_type = record.get("mime_type") or record.get("content_type")
            timestamp = record.get("timestamp") or record.get("created_at") or time.time()
            
            # Register access pattern
            self.strategy_impl.update_workload_stats(
                recent_access={
                    "key": key,
                    "content_type": content_type,
                    "timestamp": timestamp,
                    "operation": operation,
                    "size": size
                }
            )
            
    def analyze_workload(self, days: int = 7):
        """
        Analyze access patterns to optimize partitioning.
        
        Args:
            days: Number of days of access history to analyze
        """
        if isinstance(self.strategy_impl, DynamicPartitionManager):
            self.strategy_impl.analyze_access_patterns(days=days)
            self.strategy_impl.check_rebalance_partitions()
            
    def get_partition_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the current partitioning.
        
        Returns:
            Dictionary with partition statistics
        """
        stats = {
            "strategy": self.strategy.value,
            "base_path": self.base_path,
            "timestamp": time.time()
        }
        
        if isinstance(self.strategy_impl, DynamicPartitionManager):
            # Get partition counts by strategy
            strategy_counts = {}
            
            for partition in self.strategy_impl.partitions.values():
                strategy = partition.strategy.value
                if strategy not in strategy_counts:
                    strategy_counts[strategy] = 0
                    
                strategy_counts[strategy] += 1
                
            stats["partition_counts"] = strategy_counts
            stats["total_partitions"] = len(self.strategy_impl.partitions)
            stats["workload_stats"] = self.strategy_impl.workload_stats
            stats["optimal_strategy"] = self.strategy_impl.get_optimal_strategy().value
            
        elif self.strategy == PartitioningStrategy.TIME_BASED:
            # For time-based, estimate number of partitions based on configured period
            period_days = {
                "hourly": 1/24,
                "daily": 1,
                "weekly": 7,
                "monthly": 30,
                "quarterly": 90,
                "yearly": 365
            }
            
            days_per_partition = period_days.get(self.strategy_impl.period, 1)
            stats["estimated_partitions_per_year"] = round(365 / days_per_partition)
            stats["period"] = self.strategy_impl.period
            
        elif self.strategy == PartitioningStrategy.HASH_BASED:
            stats["num_partitions"] = self.strategy_impl.num_partitions
            stats["hash_algorithm"] = self.strategy_impl.hash_algorithm
            
        elif self.strategy == PartitioningStrategy.SIZE_BASED:
            stats["target_size_mb"] = self.strategy_impl.target_size_bytes // (1024 * 1024)
            stats["max_size_mb"] = self.strategy_impl.max_size_bytes // (1024 * 1024)
            stats["current_partition_id"] = self.strategy_impl.current_partition_id
            
        elif self.strategy == PartitioningStrategy.CONTENT_TYPE:
            stats["use_groups"] = self.strategy_impl.use_groups
            stats["content_groups"] = list(self.strategy_impl.CONTENT_TYPE_GROUPS.keys())
            
        return stats
        
    def create_partition_schema(self) -> Optional[pa.Schema]:
        """
        Create a PyArrow partition schema based on the current strategy.
        
        Returns:
            PyArrow partition schema or None if not applicable
        """
        if hasattr(self.strategy_impl, "create_partition_schema"):
            return self.strategy_impl.create_partition_schema()
        else:
            return None
            
    def optimize_partitions(self, max_partitions: int = None, min_records_per_partition: int = 1000):
        """
        Optimize partitions by merging small partitions or splitting large ones.
        
        Args:
            max_partitions: Maximum number of partitions to maintain
            min_records_per_partition: Minimum records per partition before considering merge
            
        Note:
            This is a placeholder for future functionality. Actual partition optimization
            would require moving data between partitions which is not implemented here.
        """
        if not isinstance(self.strategy_impl, DynamicPartitionManager):
            logger.warning("Partition optimization only supported with DynamicPartitionManager")
            return
            
        # Log what would happen in a real implementation
        logger.info(
            f"Partition optimization would merge partitions with fewer than {min_records_per_partition} "
            f"records and maintain at most {max_partitions} partitions"
        )
        
        # In a real implementation, this would:
        # 1. Identify small partitions to merge
        # 2. Identify large partitions to split
        # 3. Create a plan for partition optimization
        # 4. Execute the plan by moving data between partitions
        
        # Instead, just report current partition distribution
        active_partitions = self.strategy_impl.get_active_partitions()
        logger.info(f"Currently have {len(active_partitions)} active partitions")


# For backward compatibility with code using the single-strategy version
TimePartitioning = TimeBasedPartitionStrategy
SizePartitioning = SizeBasedPartitionStrategy
ContentTypePartitioning = ContentTypePartitionStrategy
HashPartitioning = HashBasedPartitionStrategy