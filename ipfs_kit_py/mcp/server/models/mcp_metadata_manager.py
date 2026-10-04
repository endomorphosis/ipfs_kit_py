#!/usr/bin/env python3
"""
MCP Metadata Manager - Efficient metadata reading from ~/.ipfs_kit/

This module provides efficient access to IPFS Kit metadata stored in ~/.ipfs_kit/
for the MCP server. It mirrors the CLI's approach to metadata management while
optimizing for MCP protocol usage patterns.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BackendMetadata:
    """Metadata for a single backend."""
    name: str
    type: str
    config_path: str
    index_path: str
    last_updated: datetime
    pin_count: int
    storage_usage_bytes: int
    health_status: str
    pin_mappings_available: bool
    car_files_available: bool


@dataclass
class PinMetadata:
    """Metadata for a pinned content item."""
    cid: str
    backend: str
    status: str
    created_at: datetime
    car_file_path: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BucketMetadata:
    """Metadata for a bucket."""
    name: str
    backend: str
    path: str
    created_at: datetime
    last_synced: Optional[datetime] = None
    file_count: int = 0
    total_size_bytes: int = 0


class MCPMetadataManager:
    """
    Efficient metadata manager for MCP server that reads from ~/.ipfs_kit/
    
    This manager provides fast access to metadata by:
    1. Using SQLite for queryable metadata caching
    2. Reading Parquet files efficiently 
    3. Maintaining metadata freshness with TTL
    4. Providing CLI-aligned data access patterns
    """
    
    def __init__(self, data_dir: Path, cache_ttl: int = 300):
        """Initialize the metadata manager."""
        self.data_dir = Path(data_dir).expanduser()
        self.cache_ttl = cache_ttl
        self.cache_db_path = self.data_dir / "mcp_metadata_cache.db"
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize cache database
        self._init_cache_db()
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mcp-metadata")
        
        logger.info(f"MCP Metadata Manager initialized with data_dir: {self.data_dir}")
    
    def _init_cache_db(self) -> None:
        """Initialize the SQLite cache database."""
        with sqlite3.connect(self.cache_db_path) as conn:
            # Backend metadata cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backend_cache (
                    name TEXT PRIMARY KEY,
                    type TEXT,
                    config_path TEXT,
                    index_path TEXT,
                    last_updated TIMESTAMP,
                    pin_count INTEGER,
                    storage_usage_bytes INTEGER,
                    health_status TEXT,
                    pin_mappings_available BOOLEAN,
                    car_files_available BOOLEAN,
                    cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Pin metadata cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pin_cache (
                    cid TEXT,
                    backend TEXT,
                    status TEXT,
                    created_at TIMESTAMP,
                    car_file_path TEXT,
                    size_bytes INTEGER,
                    metadata TEXT,
                    cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (cid, backend)
                )
            """)
            
            # Bucket metadata cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bucket_cache (
                    name TEXT,
                    backend TEXT,
                    path TEXT,
                    created_at TIMESTAMP,
                    last_synced TIMESTAMP,
                    file_count INTEGER,
                    total_size_bytes INTEGER,
                    cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (name, backend)
                )
            """)
            
            conn.commit()
    
    def _is_cache_fresh(self, cache_timestamp: datetime) -> bool:
        """Check if cached data is still fresh."""
        return (datetime.now() - cache_timestamp).total_seconds() < self.cache_ttl
    
    async def get_backend_metadata(self, backend_name: Optional[str] = None, 
                                 refresh: bool = False) -> Union[List[BackendMetadata], BackendMetadata]:
        """Get backend metadata efficiently."""
        if not refresh:
            # Try cache first
            cached_data = self._get_cached_backend_metadata(backend_name)
            if cached_data:
                return cached_data
        
        # Refresh from filesystem
        return await self._refresh_backend_metadata(backend_name)
    
    def _get_cached_backend_metadata(self, backend_name: Optional[str] = None) -> Optional[Union[List[BackendMetadata], BackendMetadata]]:
        """Get backend metadata from cache if fresh."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if backend_name:
                row = conn.execute(
                    "SELECT * FROM backend_cache WHERE name = ? AND cache_timestamp > ?",
                    (backend_name, datetime.now() - timedelta(seconds=self.cache_ttl))
                ).fetchone()
                
                if row:
                    return BackendMetadata(
                        name=row['name'],
                        type=row['type'],
                        config_path=row['config_path'],
                        index_path=row['index_path'],
                        last_updated=datetime.fromisoformat(row['last_updated']),
                        pin_count=row['pin_count'],
                        storage_usage_bytes=row['storage_usage_bytes'],
                        health_status=row['health_status'],
                        pin_mappings_available=bool(row['pin_mappings_available']),
                        car_files_available=bool(row['car_files_available'])
                    )
            else:
                rows = conn.execute(
                    "SELECT * FROM backend_cache WHERE cache_timestamp > ?",
                    (datetime.now() - timedelta(seconds=self.cache_ttl),)
                ).fetchall()
                
                if rows:
                    return [BackendMetadata(
                        name=row['name'],
                        type=row['type'],
                        config_path=row['config_path'],
                        index_path=row['index_path'],
                        last_updated=datetime.fromisoformat(row['last_updated']),
                        pin_count=row['pin_count'],
                        storage_usage_bytes=row['storage_usage_bytes'],
                        health_status=row['health_status'],
                        pin_mappings_available=bool(row['pin_mappings_available']),
                        car_files_available=bool(row['car_files_available'])
                    ) for row in rows]
        
        return None
    
    async def _refresh_backend_metadata(self, backend_name: Optional[str] = None) -> Union[List[BackendMetadata], BackendMetadata]:
        """Refresh backend metadata from filesystem."""
        backends_dir = self.data_dir / "backends"
        backend_configs_dir = self.data_dir / "backend_configs"
        
        backend_metadata = []
        
        if backend_name:
            # Single backend
            backend_dirs = [backends_dir / backend_name] if (backends_dir / backend_name).exists() else []
        else:
            # All backends
            backend_dirs = [d for d in backends_dir.iterdir() if d.is_dir()] if backends_dir.exists() else []
        
        for backend_dir in backend_dirs:
            name = backend_dir.name
            
            # Read backend config to get type
            config_file = backend_configs_dir / f"{name}.json"
            backend_type = "unknown"
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                        backend_type = config.get('type', 'unknown')
                except Exception as e:
                    logger.warning(f"Error reading config for backend {name}: {e}")
            
            # Check pin mappings availability
            pin_mappings_file = backend_dir / "pin_mappings.parquet"
            car_file = backend_dir / "pin_mappings.car"
            pin_mappings_available = pin_mappings_file.exists()
            car_files_available = car_file.exists()
            
            # Count pins and calculate usage if pin mappings exist
            pin_count = 0
            storage_usage = 0
            last_updated = datetime.now()
            
            if pin_mappings_available:
                try:
                    pin_df = pd.read_parquet(pin_mappings_file)
                    pin_count = len(pin_df)
                    # Calculate storage usage from metadata if available
                    if 'metadata' in pin_df.columns:
                        for metadata_str in pin_df['metadata'].dropna():
                            try:
                                metadata = json.loads(metadata_str)
                                storage_usage += metadata.get('size_bytes', 0)
                            except:
                                pass
                    last_updated = datetime.fromtimestamp(pin_mappings_file.stat().st_mtime)
                except Exception as e:
                    logger.warning(f"Error reading pin mappings for backend {name}: {e}")
            
            # Determine health status (simplified)
            health_status = "healthy" if pin_mappings_available and car_files_available else "partial"
            
            metadata = BackendMetadata(
                name=name,
                type=backend_type,
                config_path=str(config_file),
                index_path=str(backend_dir),
                last_updated=last_updated,
                pin_count=pin_count,
                storage_usage_bytes=storage_usage,
                health_status=health_status,
                pin_mappings_available=pin_mappings_available,
                car_files_available=car_files_available
            )
            
            backend_metadata.append(metadata)
            
            # Cache the metadata
            self._cache_backend_metadata(metadata)
        
        if backend_name:
            return backend_metadata[0] if backend_metadata else None
        else:
            return backend_metadata
    
    def _cache_backend_metadata(self, metadata: BackendMetadata) -> None:
        """Cache backend metadata in SQLite."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO backend_cache 
                (name, type, config_path, index_path, last_updated, pin_count, 
                 storage_usage_bytes, health_status, pin_mappings_available, 
                 car_files_available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.name, metadata.type, metadata.config_path, metadata.index_path,
                metadata.last_updated.isoformat(), metadata.pin_count, metadata.storage_usage_bytes,
                metadata.health_status, metadata.pin_mappings_available, metadata.car_files_available
            ))
            conn.commit()
    
    async def get_pin_metadata(self, backend_name: Optional[str] = None, 
                             cid: Optional[str] = None, refresh: bool = False) -> List[PinMetadata]:
        """Get pin metadata efficiently."""
        if not refresh:
            # Try cache first
            cached_data = self._get_cached_pin_metadata(backend_name, cid)
            if cached_data is not None:
                return cached_data
        
        # Refresh from filesystem
        return await self._refresh_pin_metadata(backend_name, cid)
    
    def _get_cached_pin_metadata(self, backend_name: Optional[str] = None, 
                                cid: Optional[str] = None) -> Optional[List[PinMetadata]]:
        """Get pin metadata from cache if fresh."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM pin_cache WHERE cache_timestamp > ?"
            params = [datetime.now() - timedelta(seconds=self.cache_ttl)]
            
            if backend_name:
                query += " AND backend = ?"
                params.append(backend_name)
            
            if cid:
                query += " AND cid = ?"
                params.append(cid)
            
            rows = conn.execute(query, params).fetchall()
            
            if rows:
                return [PinMetadata(
                    cid=row['cid'],
                    backend=row['backend'],
                    status=row['status'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    car_file_path=row['car_file_path'],
                    size_bytes=row['size_bytes'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else None
                ) for row in rows]
        
        return None
    
    async def _refresh_pin_metadata(self, backend_name: Optional[str] = None, 
                                  cid: Optional[str] = None) -> List[PinMetadata]:
        """Refresh pin metadata from filesystem."""
        backends_dir = self.data_dir / "backends"
        pin_metadata = []
        
        if backend_name:
            backend_dirs = [backends_dir / backend_name] if (backends_dir / backend_name).exists() else []
        else:
            backend_dirs = [d for d in backends_dir.iterdir() if d.is_dir()] if backends_dir.exists() else []
        
        for backend_dir in backend_dirs:
            name = backend_dir.name
            pin_mappings_file = backend_dir / "pin_mappings.parquet"
            
            if not pin_mappings_file.exists():
                continue
            
            try:
                pin_df = pd.read_parquet(pin_mappings_file)
                
                # Filter by CID if specified
                if cid:
                    pin_df = pin_df[pin_df['cid'] == cid]
                
                for _, row in pin_df.iterrows():
                    metadata_dict = None
                    if 'metadata' in row and pd.notna(row['metadata']):
                        try:
                            metadata_dict = json.loads(row['metadata'])
                        except:
                            pass
                    
                    pin_meta = PinMetadata(
                        cid=row['cid'],
                        backend=name,
                        status=row.get('status', 'unknown'),
                        created_at=pd.to_datetime(row['created_at']).to_pydatetime() if 'created_at' in row else datetime.now(),
                        car_file_path=row.get('car_file_path'),
                        size_bytes=metadata_dict.get('size_bytes') if metadata_dict else None,
                        metadata=metadata_dict
                    )
                    
                    pin_metadata.append(pin_meta)
                    
                    # Cache the pin metadata
                    self._cache_pin_metadata(pin_meta)
                    
            except Exception as e:
                logger.warning(f"Error reading pin metadata for backend {name}: {e}")
        
        return pin_metadata
    
    def _cache_pin_metadata(self, metadata: PinMetadata) -> None:
        """Cache pin metadata in SQLite."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pin_cache 
                (cid, backend, status, created_at, car_file_path, size_bytes, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.cid, metadata.backend, metadata.status, 
                metadata.created_at.isoformat(), metadata.car_file_path, 
                metadata.size_bytes, json.dumps(metadata.metadata) if metadata.metadata else None
            ))
            conn.commit()
    
    async def get_bucket_metadata(self, backend_name: Optional[str] = None,
                                bucket_name: Optional[str] = None, refresh: bool = False) -> List[BucketMetadata]:
        """Get bucket metadata efficiently."""
        if not refresh:
            # Try cache first
            cached_data = self._get_cached_bucket_metadata(backend_name, bucket_name)
            if cached_data is not None:
                return cached_data
        
        # Refresh from filesystem
        return await self._refresh_bucket_metadata(backend_name, bucket_name)
    
    def _get_cached_bucket_metadata(self, backend_name: Optional[str] = None,
                                  bucket_name: Optional[str] = None) -> Optional[List[BucketMetadata]]:
        """Get bucket metadata from cache if fresh."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM bucket_cache WHERE cache_timestamp > ?"
            params = [datetime.now() - timedelta(seconds=self.cache_ttl)]
            
            if backend_name:
                query += " AND backend = ?"
                params.append(backend_name)
            
            if bucket_name:
                query += " AND name = ?"
                params.append(bucket_name)
            
            rows = conn.execute(query, params).fetchall()
            
            if rows:
                return [BucketMetadata(
                    name=row['name'],
                    backend=row['backend'],
                    path=row['path'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_synced=datetime.fromisoformat(row['last_synced']) if row['last_synced'] else None,
                    file_count=row['file_count'],
                    total_size_bytes=row['total_size_bytes']
                ) for row in rows]
        
        return None
    
    async def _refresh_bucket_metadata(self, backend_name: Optional[str] = None,
                                     bucket_name: Optional[str] = None) -> List[BucketMetadata]:
        """Refresh bucket metadata from filesystem."""
        buckets_dir = self.data_dir / "buckets"
        bucket_metadata = []
        
        if not buckets_dir.exists():
            return bucket_metadata
        
        if bucket_name:
            bucket_dirs = [buckets_dir / bucket_name] if (buckets_dir / bucket_name).exists() else []
        else:
            bucket_dirs = [d for d in buckets_dir.iterdir() if d.is_dir()]
        
        for bucket_dir in bucket_dirs:
            name = bucket_dir.name
            
            # Read bucket metadata file if exists
            metadata_file = bucket_dir / "bucket_metadata.json"
            bucket_backend = "default"
            created_at = datetime.fromtimestamp(bucket_dir.stat().st_ctime)
            last_synced = None
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        bucket_meta = json.load(f)
                        bucket_backend = bucket_meta.get('backend', 'default')
                        if 'created_at' in bucket_meta:
                            created_at = datetime.fromisoformat(bucket_meta['created_at'])
                        if 'last_synced' in bucket_meta:
                            last_synced = datetime.fromisoformat(bucket_meta['last_synced'])
                except Exception as e:
                    logger.warning(f"Error reading bucket metadata for {name}: {e}")
            
            # Filter by backend if specified
            if backend_name and bucket_backend != backend_name:
                continue
            
            # Calculate file count and size
            file_count = 0
            total_size = 0
            
            try:
                for file_path in bucket_dir.rglob("*"):
                    if file_path.is_file() and file_path.name != "bucket_metadata.json":
                        file_count += 1
                        total_size += file_path.stat().st_size
            except Exception as e:
                logger.warning(f"Error calculating bucket statistics for {name}: {e}")
            
            bucket_meta = BucketMetadata(
                name=name,
                backend=bucket_backend,
                path=str(bucket_dir),
                created_at=created_at,
                last_synced=last_synced,
                file_count=file_count,
                total_size_bytes=total_size
            )
            
            bucket_metadata.append(bucket_meta)
            
            # Cache the bucket metadata
            self._cache_bucket_metadata(bucket_meta)
        
        return bucket_metadata
    
    def _cache_bucket_metadata(self, metadata: BucketMetadata) -> None:
        """Cache bucket metadata in SQLite."""
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO bucket_cache 
                (name, backend, path, created_at, last_synced, file_count, total_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.name, metadata.backend, metadata.path,
                metadata.created_at.isoformat(),
                metadata.last_synced.isoformat() if metadata.last_synced else None,
                metadata.file_count, metadata.total_size_bytes
            ))
            conn.commit()
    
    async def get_metadata_summary(self) -> Dict[str, Any]:
        """Get a summary of all metadata for dashboard/status purposes."""
        # Get backend summary
        backends = await self.get_backend_metadata()
        backend_summary = {
            "total_backends": len(backends),
            "healthy_backends": sum(1 for b in backends if b.health_status == "healthy"),
            "total_pins": sum(b.pin_count for b in backends),
            "total_storage_bytes": sum(b.storage_usage_bytes for b in backends),
            "backends_with_pin_mappings": sum(1 for b in backends if b.pin_mappings_available)
        }
        
        # Get pin summary
        pins = await self.get_pin_metadata()
        pin_summary = {
            "total_pins": len(pins),
            "unique_cids": len(set(p.cid for p in pins)),
            "backends_with_pins": len(set(p.backend for p in pins)),
            "average_redundancy": len(pins) / len(set(p.cid for p in pins)) if pins else 0
        }
        
        # Get bucket summary
        buckets = await self.get_bucket_metadata()
        bucket_summary = {
            "total_buckets": len(buckets),
            "total_files": sum(b.file_count for b in buckets),
            "total_bucket_size_bytes": sum(b.total_size_bytes for b in buckets)
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "data_dir": str(self.data_dir),
            "cache_ttl": self.cache_ttl,
            "backend_summary": backend_summary,
            "pin_summary": pin_summary,
            "bucket_summary": bucket_summary
        }
    
    async def close(self) -> None:
        """Clean up resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
        logger.info("MCP Metadata Manager closed")
