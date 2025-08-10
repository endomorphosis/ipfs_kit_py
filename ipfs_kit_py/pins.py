"""
Enhanced Pin Metadata Index for IPFS Kit - Parquet-based Virtual Filesystem Integration

This module provides a unified pin metadata index that integrates with ipfs_kit_py's
virtual filesystem, storage backends, and hierarchical storage management. It uses
DuckDB + Parquet for efficient analytical queries and storage.

Key Features:
- Integration with IPFSFileSystem and hierarchical storage
- DuckDB-powered analytical queries for traffic metrics
- Parquet columnar storage for efficiency
- Virtual filesystem integration for seamless CLI/API access
- Background synchronization with filesystem journal
- Multi-tier storage tracking and analytics

Usage:
    from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
    
    # Get the global index (integrates with filesystem)
    index = get_global_enhanced_pin_index()
    
    # Access from CLI, API, or dashboard
    metrics = index.get_comprehensive_metrics()
    pin_info = index.get_pin_details(cid)
"""

import os
import sys
import time
import json
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import tempfile

# DuckDB and analytics imports
try:
    import duckdb
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

# IPFS Kit imports
try:
    from .filesystem_journal import FilesystemJournal, JournalOperationType
    from .ipfs_fsspec import IPFSFileSystem
    from .hierarchical_storage_methods import _get_content_tiers
    IPFS_KIT_AVAILABLE = True
except ImportError:
    try:
        # Fallback for direct imports
        from filesystem_journal import FilesystemJournal, JournalOperationType
        from ipfs_fsspec import IPFSFileSystem
        IPFS_KIT_AVAILABLE = True
    except ImportError:
        IPFS_KIT_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class EnhancedPinMetadata:
    """Enhanced pin metadata with virtual filesystem integration."""
    cid: str
    size_bytes: int = 0
    type: str = "unknown"
    name: Optional[str] = None
    last_updated: float = 0
    access_count: int = 0
    last_accessed: float = 0
    
    # Virtual filesystem integration
    vfs_path: Optional[str] = None
    mount_point: Optional[str] = None
    is_directory: bool = False
    
    # Storage tier information
    storage_tiers: List[str] = None
    primary_tier: str = "ipfs"
    replication_factor: int = 1
    
    # Content integrity
    content_hash: Optional[str] = None
    last_verified: float = 0
    integrity_status: str = "unknown"  # verified, corrupted, unknown
    
    # Access patterns and analytics
    access_pattern: str = "random"  # sequential, random, streaming
    hotness_score: float = 0.0
    predicted_access_time: Optional[float] = None
    
    def __post_init__(self):
        if self.storage_tiers is None:
            self.storage_tiers = []
        if self.last_updated == 0:
            self.last_updated = time.time()

@dataclass 
@dataclass
class ComprehensiveTrafficMetrics:
    """Comprehensive traffic metrics with VFS and storage tier analytics."""
    # Basic metrics
    total_pins: int = 0
    total_size_bytes: int = 0
    total_size_human: str = ""
    
    # Access patterns
    pins_accessed_last_hour: int = 0
    pins_accessed_last_day: int = 0
    total_access_count: int = 0
    
    # Bandwidth and traffic
    bandwidth_estimate_bytes: int = 0
    bandwidth_estimate_human: str = ""
    hot_pins: List[str] = None
    
    # Analytics
    average_pin_size: float = 0.0
    median_pin_size: float = 0.0
    largest_pins: List[Dict[str, Any]] = None
    
    # Virtual filesystem metrics
    vfs_mounts: int = 0
    directory_pins: int = 0
    file_pins: int = 0
    
    # Storage tiers
    tier_distribution: Dict[str, int] = None
    replication_stats: Dict[str, int] = None
    
    # Content integrity
    verified_pins: int = 0
    corrupted_pins: int = 0
    unverified_pins: int = 0
    
    # Predictions and recommendations
    cache_efficiency: float = 0.0
    storage_recommendations: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.hot_pins is None:
            self.hot_pins = []
        if self.largest_pins is None:
            self.largest_pins = []
        if self.tier_distribution is None:
            self.tier_distribution = {}
        if self.replication_stats is None:
            self.replication_stats = {}
        if self.storage_recommendations is None:
            self.storage_recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_pins": self.total_pins,
            "total_size_bytes": self.total_size_bytes,
            "total_size_human": self.total_size_human,
            "pins_accessed_last_hour": self.pins_accessed_last_hour,
            "pins_accessed_last_day": self.pins_accessed_last_day,
            "total_access_count": self.total_access_count,
            "bandwidth_estimate_bytes": self.bandwidth_estimate_bytes,
            "bandwidth_estimate_human": self.bandwidth_estimate_human,
            "hot_pins": self.hot_pins or [],
            "average_pin_size": self.average_pin_size,
            "median_pin_size": self.median_pin_size,
            "largest_pins": self.largest_pins or [],
            "vfs_mounts": self.vfs_mounts,
            "directory_pins": self.directory_pins,
            "file_pins": self.file_pins,
            "tier_distribution": self.tier_distribution or {},
            "replication_stats": self.replication_stats or {},
            "verified_pins": self.verified_pins,
            "corrupted_pins": self.corrupted_pins,
            "unverified_pins": self.unverified_pins,
            "cache_efficiency": self.cache_efficiency,
            "storage_recommendations": self.storage_recommendations or []
        }

class EnhancedPinMetadataIndex:
    """
    Enhanced pin metadata index with virtual filesystem integration.
    
    This class provides comprehensive pin tracking that integrates with:
    - Virtual filesystem (VFS) operations
    - Hierarchical storage management
    - Content integrity verification
    - Predictive analytics for storage optimization
    - Real-time synchronization with filesystem journal
    """
    
    def __init__(self,
                 data_dir: Optional[str] = None,
                 ipfs_filesystem: Optional['IPFSFileSystem'] = None,
                 journal: Optional['FilesystemJournal'] = None,
                 update_interval: int = 300,
                 enable_analytics: bool = True,
                 enable_predictions: bool = True):
        """
        Initialize the enhanced pin metadata index.
        
        Args:
            data_dir: Directory for DuckDB and Parquet storage
            ipfs_filesystem: Optional IPFSFileSystem instance for VFS integration
            journal: Optional FilesystemJournal for real-time sync
            update_interval: Background update interval in seconds
            enable_analytics: Enable advanced analytics features
            enable_predictions: Enable predictive analytics
        """
        if not ANALYTICS_AVAILABLE:
            raise ImportError("Enhanced pin index requires DuckDB, pandas, and pyarrow. "
                            "Install with: pip install duckdb pandas pyarrow")
        
        # Configuration
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".ipfs_kit" / "enhanced_pin_index"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.update_interval = update_interval
        self.enable_analytics = enable_analytics
        self.enable_predictions = enable_predictions
        
        # Integration components
        self.ipfs_filesystem = ipfs_filesystem
        self.journal = journal
        
        # DuckDB setup
        self.db_path = self.data_dir / "enhanced_pin_metadata.duckdb"
        self.pins_parquet = self.data_dir / "enhanced_pins.parquet"
        self.metrics_parquet = self.data_dir / "traffic_metrics.parquet"
        self.analytics_parquet = self.data_dir / "pin_analytics.parquet"
        
        # Initialize fallback mode flag
        self.parquet_fallback_mode = False
        
        # Try to connect to DuckDB with retry logic and fallback to read-only
        self.conn = self._connect_with_retry()
        
        # In-memory cache for fast access
        self.pin_metadata: Dict[str, EnhancedPinMetadata] = {}
        self.access_history: deque = deque(maxlen=10000)  # Recent access patterns
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Background services
        self.background_task: Optional[asyncio.Task] = None
        self.running: bool = False
        
        # Performance metrics
        self.metrics = {
            "total_operations": 0,
            "vfs_integrations": 0,
            "journal_syncs": 0,
            "analytics_runs": 0,
            "predictions_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "last_update_duration": 0
        }
        
        # Initialize database schema and integrations
        self._initialize_enhanced_schema()
        self._load_enhanced_cache()
        self._setup_integrations()

    def _connect_with_retry(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Connect to DuckDB with retry logic and fallback options.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            DuckDB connection object
        """
        import time
        
        for attempt in range(max_retries):
            try:
                # Try normal connection first
                conn = duckdb.connect(str(self.db_path))
                logger.info(f"✓ Connected to DuckDB database at {self.db_path}")
                self.parquet_fallback_mode = False
                return conn
                
            except Exception as e:
                if "lock" in str(e).lower() or "conflicting" in str(e).lower():
                    logger.warning(f"Database lock detected (attempt {attempt + 1}/{max_retries}): {e}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        # Final attempt: try read-only mode
                        try:
                            logger.warning("Attempting read-only connection as fallback...")
                            conn = duckdb.connect(f"{self.db_path}", read_only=True)
                            logger.warning("⚠️  Connected in READ-ONLY mode - writes will be disabled")
                            self.parquet_fallback_mode = False
                            return conn
                        except Exception as readonly_error:
                            logger.error(f"Read-only connection also failed: {readonly_error}")
                            
                            # Check if parquet files exist for fallback
                            if self.pins_parquet.exists():
                                logger.warning("🔄 Using parquet files as fallback data source")
                                self.parquet_fallback_mode = True
                                # Return in-memory database for basic operations
                                conn = duckdb.connect(":memory:")
                                self._initialize_parquet_fallback(conn)
                                return conn
                            else:
                                logger.warning("No parquet files available for fallback, using empty in-memory database")
                                self.parquet_fallback_mode = True
                                return duckdb.connect(":memory:")
                else:
                    # Non-lock related error, re-raise immediately
                    logger.error(f"Database connection failed: {e}")
                    raise
        
        # This shouldn't be reached, but just in case
        logger.warning("All connection attempts failed, checking for parquet fallback")
        if self.pins_parquet.exists():
            logger.warning("🔄 Using parquet files as fallback data source")
            self.parquet_fallback_mode = True
            conn = duckdb.connect(":memory:")
            self._initialize_parquet_fallback(conn)
            return conn
        else:
            logger.warning("Using empty in-memory database as last resort")
            self.parquet_fallback_mode = True
            return duckdb.connect(":memory:")

    def _initialize_parquet_fallback(self, conn):
        """
        Initialize the in-memory database with data from parquet files.
        
        Args:
            conn: DuckDB connection to initialize
        """
        try:
            # Create basic schema
            self._initialize_enhanced_schema_in_memory(conn)
            
            # Load data from parquet files if they exist
            if self.pins_parquet.exists():
                try:
                    conn.execute(f"""
                        INSERT INTO enhanced_pins 
                        SELECT * FROM parquet_scan('{self.pins_parquet}')
                    """)
                    logger.info("✓ Loaded pin data from parquet fallback")
                except Exception as e:
                    logger.warning(f"Failed to load pins from parquet: {e}")
            
            if self.metrics_parquet.exists():
                try:
                    conn.execute(f"""
                        INSERT INTO traffic_metrics 
                        SELECT * FROM parquet_scan('{self.metrics_parquet}')
                    """)
                    logger.info("✓ Loaded metrics from parquet fallback")
                except Exception as e:
                    logger.warning(f"Failed to load metrics from parquet: {e}")
                    
            if self.analytics_parquet.exists():
                try:
                    conn.execute(f"""
                        INSERT INTO pin_analytics 
                        SELECT * FROM parquet_scan('{self.analytics_parquet}')
                    """)
                    logger.info("✓ Loaded analytics from parquet fallback")
                except Exception as e:
                    logger.warning(f"Failed to load analytics from parquet: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to initialize parquet fallback: {e}")

    def _initialize_enhanced_schema_in_memory(self, conn):
        """Initialize schema in memory database for parquet fallback."""
        try:
            # Create enhanced pins table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_pins (
                    cid VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    size INTEGER,
                    pin_time TIMESTAMP,
                    last_accessed TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 5,
                    storage_tiers VARCHAR,
                    metadata_hash VARCHAR,
                    verification_status VARCHAR DEFAULT 'pending',
                    replication_factor INTEGER DEFAULT 1,
                    bandwidth_usage INTEGER DEFAULT 0,
                    geographic_preference VARCHAR,
                    content_type VARCHAR,
                    tags VARCHAR
                )
            """)
            
            # Create traffic metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traffic_metrics (
                    id INTEGER PRIMARY KEY,
                    cid VARCHAR,
                    timestamp TIMESTAMP,
                    operation VARCHAR,
                    bytes_transferred INTEGER,
                    duration_ms INTEGER,
                    client_ip VARCHAR,
                    user_agent VARCHAR
                )
            """)
            
            # Create analytics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pin_analytics (
                    id INTEGER PRIMARY KEY,
                    cid VARCHAR,
                    analysis_date TIMESTAMP,
                    popularity_score REAL,
                    access_pattern VARCHAR,
                    predicted_demand REAL,
                    optimization_suggestions VARCHAR
                )
            """)
            
        except Exception as e:
            logger.error(f"Failed to create schema for parquet fallback: {e}")
        
        logger.info(f"✓ Enhanced Pin Metadata Index initialized")
        logger.info(f"  - Data directory: {self.data_dir}")
        logger.info(f"  - Analytics: {'enabled' if self.enable_analytics else 'disabled'}")
        logger.info(f"  - Predictions: {'enabled' if self.enable_predictions else 'disabled'}")
        logger.info(f"  - VFS integration: {'available' if self.ipfs_filesystem else 'not available'}")
        logger.info(f"  - Journal sync: {'available' if self.journal else 'not available'}")
        logger.info(f"  - Fallback mode: {'parquet' if getattr(self, 'parquet_fallback_mode', False) else 'normal'}")
    
    def _initialize_enhanced_schema(self):
        """Initialize enhanced DuckDB schema with VFS and analytics support."""
        try:
            # Enhanced pins table with VFS and storage tier info
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_pins (
                    cid VARCHAR PRIMARY KEY,
                    size_bytes BIGINT,
                    type VARCHAR,
                    name VARCHAR,
                    last_updated DOUBLE,
                    access_count INTEGER,
                    last_accessed DOUBLE,
                    
                    -- VFS integration
                    vfs_path VARCHAR,
                    mount_point VARCHAR,
                    is_directory BOOLEAN,
                    
                    -- Storage tiers
                    storage_tiers VARCHAR,  -- JSON array
                    primary_tier VARCHAR,
                    replication_factor INTEGER,
                    
                    -- Content integrity
                    content_hash VARCHAR,
                    last_verified DOUBLE,
                    integrity_status VARCHAR,
                    
                    -- Analytics
                    access_pattern VARCHAR,
                    hotness_score DOUBLE,
                    predicted_access_time DOUBLE
                )
            """)
            
            # Traffic analytics table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS traffic_analytics (
                    timestamp DOUBLE,
                    cid VARCHAR,
                    operation VARCHAR,
                    size_bytes BIGINT,
                    tier VARCHAR,
                    access_pattern VARCHAR,
                    response_time_ms DOUBLE
                )
            """)
            
            # Storage tier analytics
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS tier_analytics (
                    timestamp DOUBLE,
                    tier VARCHAR,
                    total_pins INTEGER,
                    total_size_bytes BIGINT,
                    read_operations INTEGER,
                    write_operations INTEGER,
                    average_response_time DOUBLE,
                    health_score DOUBLE
                )
            """)
            
            # VFS operations tracking
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS vfs_operations (
                    timestamp DOUBLE,
                    operation_type VARCHAR,
                    path VARCHAR,
                    cid VARCHAR,
                    mount_point VARCHAR,
                    success BOOLEAN,
                    duration_ms DOUBLE
                )
            """)
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_enhanced_pins_accessed ON enhanced_pins(last_accessed)",
                "CREATE INDEX IF NOT EXISTS idx_enhanced_pins_tier ON enhanced_pins(primary_tier)",
                "CREATE INDEX IF NOT EXISTS idx_enhanced_pins_hotness ON enhanced_pins(hotness_score)",
                "CREATE INDEX IF NOT EXISTS idx_traffic_timestamp ON traffic_analytics(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_vfs_timestamp ON vfs_operations(timestamp)",
            ]
            
            for idx_sql in indexes:
                try:
                    self.conn.execute(idx_sql)
                except Exception as e:
                    logger.debug(f"Index creation warning: {e}")
            
            logger.info("✓ Enhanced DuckDB schema initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced schema: {e}")
            raise
    
    def _load_enhanced_cache(self):
        """Load enhanced pin metadata from Parquet files."""
        try:
            # Load pins from Parquet if available
            if self.pins_parquet.exists():
                try:
                    self.conn.execute(f"""
                        INSERT OR REPLACE INTO enhanced_pins 
                        SELECT * FROM parquet_scan('{self.pins_parquet}')
                    """)
                    logger.info("✓ Loaded enhanced pins from Parquet")
                except Exception as e:
                    logger.warning(f"Failed to load enhanced pins from Parquet: {e}")
            
            # Load into memory cache
            result = self.conn.execute("SELECT * FROM enhanced_pins").fetchall()
            columns = [desc[0] for desc in self.conn.description]
            
            for row in result:
                pin_data = dict(zip(columns, row))
                cid = pin_data['cid']
                
                # Parse JSON fields
                storage_tiers = []
                if pin_data.get('storage_tiers'):
                    try:
                        storage_tiers = json.loads(pin_data['storage_tiers'])
                    except:
                        pass
                
                self.pin_metadata[cid] = EnhancedPinMetadata(
                    cid=cid,
                    size_bytes=pin_data['size_bytes'] or 0,
                    type=pin_data['type'] or 'unknown',
                    name=pin_data['name'],
                    last_updated=pin_data['last_updated'] or 0,
                    access_count=pin_data['access_count'] or 0,
                    last_accessed=pin_data['last_accessed'] or 0,
                    vfs_path=pin_data.get('vfs_path'),
                    mount_point=pin_data.get('mount_point'),
                    is_directory=pin_data.get('is_directory', False),
                    storage_tiers=storage_tiers,
                    primary_tier=pin_data.get('primary_tier', 'ipfs'),
                    replication_factor=pin_data.get('replication_factor', 1),
                    content_hash=pin_data.get('content_hash'),
                    last_verified=pin_data.get('last_verified', 0),
                    integrity_status=pin_data.get('integrity_status', 'unknown'),
                    access_pattern=pin_data.get('access_pattern', 'random'),
                    hotness_score=pin_data.get('hotness_score', 0.0),
                    predicted_access_time=pin_data.get('predicted_access_time')
                )
            
            logger.info(f"✓ Loaded {len(self.pin_metadata)} enhanced pins from cache")
            
        except Exception as e:
            logger.warning(f"Failed to load enhanced cache: {e}")
    
    def _setup_integrations(self):
        """Set up integrations with VFS and journal."""
        try:
            # Integrate with filesystem journal if available
            if self.journal and IPFS_KIT_AVAILABLE:
                self._setup_journal_sync()
            
            # Integrate with IPFS filesystem if available
            if self.ipfs_filesystem:
                self._setup_vfs_integration()
                
            self.metrics["vfs_integrations"] += 1
            
        except Exception as e:
            logger.warning(f"Integration setup warning: {e}")
    
    def _setup_journal_sync(self):
        """Set up real-time synchronization with filesystem journal."""
        if not self.journal:
            return
        
        # Register callback for journal operations
        def on_journal_operation(operation_type, path, cid=None, **kwargs):
            """Handle filesystem journal operations."""
            try:
                if operation_type in [JournalOperationType.CREATE, JournalOperationType.MOUNT]:
                    if cid:
                        self._sync_pin_from_journal(cid, path, operation_type, **kwargs)
                elif operation_type == JournalOperationType.DELETE:
                    if cid:
                        self._remove_pin_from_journal(cid, path)
                
                # Record VFS operation
                self._record_vfs_operation(operation_type, path, cid, **kwargs)
                self.metrics["journal_syncs"] += 1
                
            except Exception as e:
                logger.error(f"Journal sync error: {e}")
        
        # Note: This would require the journal to support callbacks
        # For now, we'll implement periodic sync
        logger.info("✓ Journal sync configured (periodic mode)")
    
    def _setup_vfs_integration(self):
        """Set up integration with IPFS virtual filesystem."""
        if not self.ipfs_filesystem:
            return
        
        # Hook into filesystem operations
        original_get = getattr(self.ipfs_filesystem, '_get_file', None)
        if original_get:
            def enhanced_get(path, *args, **kwargs):
                result = original_get(path, *args, **kwargs)
                # Extract CID from path if possible and record access
                if hasattr(result, 'cid') or 'cid' in kwargs:
                    cid = getattr(result, 'cid', kwargs.get('cid'))
                    if cid:
                        self.record_enhanced_access(cid, access_pattern="vfs_read", vfs_path=path)
                return result
            
            # Monkey patch (careful approach)
            # self.ipfs_filesystem._get_file = enhanced_get
        
        logger.info("✓ VFS integration configured")
    
    def _sync_pin_from_journal(self, cid: str, path: str, operation_type, **kwargs):
        """Sync pin metadata from journal operation."""
        with self.lock:
            try:
                # Create or update pin metadata from journal info
                if cid not in self.pin_metadata:
                    self.pin_metadata[cid] = EnhancedPinMetadata(
                        cid=cid,
                        vfs_path=path,
                        type="journal_sync",
                        last_updated=time.time()
                    )
                else:
                    pin = self.pin_metadata[cid]
                    pin.vfs_path = path
                    pin.last_updated = time.time()
                
                # Extract additional info from kwargs
                pin = self.pin_metadata[cid]
                if 'size' in kwargs:
                    pin.size_bytes = kwargs['size']
                if 'mount_point' in kwargs:
                    pin.mount_point = kwargs['mount_point']
                if 'is_directory' in kwargs:
                    pin.is_directory = kwargs['is_directory']
                
                logger.debug(f"Synced pin {cid} from journal: {path}")
                
            except Exception as e:
                logger.error(f"Failed to sync pin from journal: {e}")
    
    def _record_vfs_operation(self, operation_type, path: str, cid: Optional[str] = None, **kwargs):
        """Record VFS operation for analytics."""
        try:
            start_time = kwargs.get('start_time', time.time())
            duration_ms = (time.time() - start_time) * 1000
            success = kwargs.get('success', True)
            
            self.conn.execute("""
                INSERT INTO vfs_operations 
                (timestamp, operation_type, path, cid, mount_point, success, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                time.time(),
                str(operation_type),
                path,
                cid,
                kwargs.get('mount_point'),
                success,
                duration_ms
            ])
            
        except Exception as e:
            logger.debug(f"Failed to record VFS operation: {e}")
    
    def record_enhanced_access(self, cid: str, 
                              access_pattern: str = "random",
                              vfs_path: Optional[str] = None,
                              tier: str = "ipfs",
                              response_time_ms: Optional[float] = None,
                              **kwargs):
        """Record enhanced pin access with VFS and analytics integration."""
        with self.lock:
            current_time = time.time()
            
            # Update or create pin metadata
            if cid not in self.pin_metadata:
                self.pin_metadata[cid] = EnhancedPinMetadata(
                    cid=cid,
                    vfs_path=vfs_path,
                    access_pattern=access_pattern,
                    primary_tier=tier,
                    last_updated=current_time
                )
            
            pin = self.pin_metadata[cid]
            pin.access_count += 1
            pin.last_accessed = current_time
            
            # Update VFS path if provided
            if vfs_path:
                pin.vfs_path = vfs_path
            
            # Update access pattern analysis
            if access_pattern != "random":
                pin.access_pattern = access_pattern
            
            # Update storage tier info
            if tier not in pin.storage_tiers:
                pin.storage_tiers.append(tier)
            pin.primary_tier = tier
            
            # Calculate hotness score
            hour_ago = current_time - 3600
            recent_accesses = sum(1 for entry in self.access_history 
                                if entry.get('cid') == cid and entry.get('timestamp', 0) > hour_ago)
            pin.hotness_score = recent_accesses * 0.1 + (pin.access_count * 0.01)
            
            # Record in access history
            self.access_history.append({
                'timestamp': current_time,
                'cid': cid,
                'access_pattern': access_pattern,
                'tier': tier,
                'response_time_ms': response_time_ms or 0,
                'vfs_path': vfs_path
            })
            
            # Record in analytics table
            try:
                self.conn.execute("""
                    INSERT INTO traffic_analytics 
                    (timestamp, cid, operation, size_bytes, tier, access_pattern, response_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    current_time,
                    cid,
                    "access",
                    pin.size_bytes,
                    tier,
                    access_pattern,
                    response_time_ms or 0
                ])
            except Exception as e:
                logger.debug(f"Failed to record analytics: {e}")
            
            self.metrics["total_operations"] += 1
    
    def get_comprehensive_metrics(self) -> ComprehensiveTrafficMetrics:
        """Get comprehensive traffic metrics with VFS and storage analytics."""
        try:
            with self.lock:
                current_time = time.time()
                hour_ago = current_time - 3600
                day_ago = current_time - 86400
                
                # Use DuckDB for comprehensive analytics
                comprehensive_stats = self.conn.execute("""
                    SELECT 
                        COUNT(*) as total_pins,
                        COALESCE(SUM(size_bytes), 0) as total_size,
                        COALESCE(AVG(size_bytes), 0) as avg_size,
                        COALESCE(MEDIAN(size_bytes), 0) as median_size,
                        COUNT(CASE WHEN last_accessed > ? THEN 1 END) as pins_accessed_hour,
                        COUNT(CASE WHEN last_accessed > ? THEN 1 END) as pins_accessed_day,
                        COUNT(CASE WHEN is_directory = true THEN 1 END) as directory_pins,
                        COUNT(CASE WHEN vfs_path IS NOT NULL THEN 1 END) as vfs_mounts,
                        COUNT(CASE WHEN integrity_status = 'verified' THEN 1 END) as verified_pins,
                        COUNT(CASE WHEN integrity_status = 'corrupted' THEN 1 END) as corrupted_pins,
                        SUM(access_count) as total_accesses
                    FROM enhanced_pins
                """, [hour_ago, day_ago]).fetchone()
                
                # Storage tier distribution
                tier_stats = self.conn.execute("""
                    SELECT primary_tier, COUNT(*) as count
                    FROM enhanced_pins 
                    GROUP BY primary_tier
                """).fetchall()
                
                tier_distribution = {tier: count for tier, count in tier_stats}
                
                # Replication statistics
                replication_stats = self.conn.execute("""
                    SELECT replication_factor, COUNT(*) as count
                    FROM enhanced_pins 
                    GROUP BY replication_factor
                """).fetchall()
                
                replication_dist = {f"factor_{factor}": count for factor, count in replication_stats}
                
                # Top largest pins with VFS info
                largest_pins_result = self.conn.execute("""
                    SELECT cid, size_bytes, name, vfs_path, hotness_score
                    FROM enhanced_pins 
                    WHERE size_bytes > 0
                    ORDER BY size_bytes DESC 
                    LIMIT 10
                """).fetchall()
                
                largest_pins = [
                    {
                        'cid': row[0][:12] + '...' if len(row[0]) > 12 else row[0],
                        'size_bytes': row[1],
                        'size_human': self._format_bytes(row[1]),
                        'name': row[2] or 'unnamed',
                        'vfs_path': row[3],
                        'hotness_score': row[4] or 0.0
                    }
                    for row in largest_pins_result
                ]
                
                # Hot pins (most accessed)
                hot_pins_result = self.conn.execute("""
                    SELECT cid FROM enhanced_pins 
                    ORDER BY hotness_score DESC, access_count DESC 
                    LIMIT 10
                """).fetchall()
                
                hot_pins = [row[0] for row in hot_pins_result]
                
                # Bandwidth estimation
                recent_traffic = self.conn.execute("""
                    SELECT COALESCE(SUM(size_bytes), 0) as recent_bytes
                    FROM enhanced_pins 
                    WHERE last_accessed > ?
                """, [hour_ago]).fetchone()
                
                bandwidth_estimate = recent_traffic[0] if recent_traffic else 0
                
                # Extract stats
                (total_pins, total_size, avg_size, median_size, pins_hour, 
                 pins_day, dir_pins, vfs_mounts, verified, corrupted, total_accesses) = comprehensive_stats
                
                # Storage recommendations (simplified)
                recommendations = []
                if corrupted > 0:
                    recommendations.append({
                        "type": "integrity_check",
                        "priority": "high",
                        "message": f"{corrupted} pins have integrity issues"
                    })
                
                if pins_hour > total_pins * 0.1:  # High activity
                    recommendations.append({
                        "type": "cache_optimization",
                        "priority": "medium", 
                        "message": "Consider increasing cache size for hot content"
                    })
                
                return ComprehensiveTrafficMetrics(
                    total_pins=total_pins or 0,
                    total_size_bytes=total_size or 0,
                    total_size_human=self._format_bytes(total_size or 0),
                    pins_accessed_last_hour=pins_hour or 0,
                    pins_accessed_last_day=pins_day or 0,
                    total_access_count=total_accesses or 0,
                    bandwidth_estimate_bytes=int(bandwidth_estimate),
                    bandwidth_estimate_human=self._format_bytes(bandwidth_estimate) + "/hour",
                    hot_pins=hot_pins,
                    average_pin_size=float(avg_size or 0),
                    median_pin_size=float(median_size or 0),
                    largest_pins=largest_pins,
                    vfs_mounts=vfs_mounts or 0,
                    directory_pins=dir_pins or 0,
                    file_pins=max(0, (total_pins or 0) - (dir_pins or 0)),
                    tier_distribution=tier_distribution,
                    replication_stats=replication_dist,
                    verified_pins=verified or 0,
                    corrupted_pins=corrupted or 0,
                    unverified_pins=max(0, (total_pins or 0) - (verified or 0) - (corrupted or 0)),
                    cache_efficiency=min(1.0, (verified or 0) / max(1, total_pins or 1)),
                    storage_recommendations=recommendations
                )
                
        except Exception as e:
            logger.error(f"Error calculating comprehensive metrics: {e}")
            return ComprehensiveTrafficMetrics()
    
    def get_pin_details(self, cid: str) -> Optional[EnhancedPinMetadata]:
        """Get detailed pin information including VFS and analytics."""
        with self.lock:
            if cid in self.pin_metadata:
                self.metrics["cache_hits"] += 1
                return self.pin_metadata[cid]
            else:
                self.metrics["cache_misses"] += 1
                return None
    
    def get_all_pins(self) -> List[Dict[str, Any]]:
        """Get all pins from the metadata index."""
        try:
            with self.lock:
                # Return all pins from the in-memory cache
                all_pins = []
                for cid, pin_metadata in self.pin_metadata.items():
                    pin_dict = {
                        'cid': cid,
                        'name': pin_metadata.name,
                        'origin': pin_metadata.origin,
                        'size': pin_metadata.size,
                        'timestamp': pin_metadata.timestamp,
                        'metadata': pin_metadata.metadata,
                        'access_count': pin_metadata.access_count,
                        'last_access': pin_metadata.last_access,
                        'mount_point': getattr(pin_metadata, 'mount_point', None),
                        'storage_metrics': getattr(pin_metadata, 'storage_metrics', {}),
                        'optimization_metrics': getattr(pin_metadata, 'optimization_metrics', {})
                    }
                    all_pins.append(pin_dict)
                
                logger.info(f"Retrieved {len(all_pins)} pins from metadata index")
                return all_pins
                
        except Exception as e:
            logger.error(f"Error getting all pins: {e}")
            return []
    
    def get_vfs_analytics(self) -> Dict[str, Any]:
        """Get VFS-specific analytics."""
        try:
            # VFS operations summary
            vfs_ops = self.conn.execute("""
                SELECT 
                    operation_type,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration,
                    COUNT(CASE WHEN success = true THEN 1 END) as success_count
                FROM vfs_operations 
                WHERE timestamp > ?
                GROUP BY operation_type
            """, [time.time() - 86400]).fetchall()  # Last 24 hours
            
            operations_summary = {}
            for op_type, count, avg_duration, success_count in vfs_ops:
                operations_summary[op_type] = {
                    'count': count,
                    'avg_duration_ms': avg_duration or 0,
                    'success_rate': success_count / count if count > 0 else 0
                }
            
            # Mount points analysis
            mount_points = self.conn.execute("""
                SELECT mount_point, COUNT(*) as pin_count
                FROM enhanced_pins 
                WHERE mount_point IS NOT NULL
                GROUP BY mount_point
            """).fetchall()
            
            mount_analysis = {mp: count for mp, count in mount_points}
            
            return {
                "operations_summary": operations_summary,
                "mount_points": mount_analysis,
                "total_vfs_pins": len([p for p in self.pin_metadata.values() if p.vfs_path]),
                "vfs_integrations": self.metrics["vfs_integrations"]
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS analytics: {e}")
            return {}
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes as human-readable string."""
        if bytes_val == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} PB"
    
    def _save_enhanced_cache(self):
        """Save enhanced pin metadata to Parquet files."""
        try:
            with self.lock:
                # Prepare data for database
                pin_records = []
                for cid, pin in self.pin_metadata.items():
                    pin_records.append((
                        pin.cid,
                        pin.size_bytes,
                        pin.type,
                        pin.name,
                        pin.last_updated,
                        pin.access_count,
                        pin.last_accessed,
                        pin.vfs_path,
                        pin.mount_point,
                        pin.is_directory,
                        json.dumps(pin.storage_tiers),  # Store as JSON
                        pin.primary_tier,
                        pin.replication_factor,
                        pin.content_hash,
                        pin.last_verified,
                        pin.integrity_status,
                        pin.access_pattern,
                        pin.hotness_score,
                        pin.predicted_access_time
                    ))
                
                if pin_records:
                    # Update database
                    self.conn.execute("DELETE FROM enhanced_pins")
                    self.conn.executemany("""
                        INSERT INTO enhanced_pins (
                            cid, size_bytes, type, name, last_updated, access_count, last_accessed,
                            vfs_path, mount_point, is_directory, storage_tiers, primary_tier,
                            replication_factor, content_hash, last_verified, integrity_status,
                            access_pattern, hotness_score, predicted_access_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, pin_records)
                
                # Export to Parquet
                self.conn.execute(f"""
                    COPY enhanced_pins TO '{self.pins_parquet}' (FORMAT PARQUET)
                """)
                
                # Export recent analytics
                self.conn.execute(f"""
                    COPY (
                        SELECT * FROM traffic_analytics 
                        WHERE timestamp > {time.time() - 86400}  -- Last 24 hours
                        ORDER BY timestamp DESC 
                        LIMIT 50000
                    ) TO '{self.analytics_parquet}' (FORMAT PARQUET)
                """)
                
                logger.debug(f"✓ Saved {len(pin_records)} enhanced pins to Parquet")
                
        except Exception as e:
            logger.error(f"Failed to save enhanced cache: {e}")
    
    async def start_background_services(self):
        """Start background update and analytics services."""
        if self.running:
            return
        
        self.running = True
        self.background_task = asyncio.create_task(self._background_service_loop())
        logger.info("✓ Enhanced pin index background services started")
    
    async def stop_background_services(self):
        """Stop background services and save data."""
        self.running = False
        
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
        
        # Save data before stopping
        self._save_enhanced_cache()
        logger.info("✓ Enhanced pin index background services stopped")
    
    async def _background_service_loop(self):
        """Background service loop for updates and analytics."""
        while self.running:
            try:
                start_time = time.time()
                
                # Periodic updates
                await self._background_update_pins()
                
                # Analytics processing
                if self.enable_analytics:
                    await self._background_analytics()
                
                # Predictive analysis
                if self.enable_predictions:
                    await self._background_predictions()
                
                # Save cache periodically
                self._save_enhanced_cache()
                
                # Update metrics
                duration = time.time() - start_time
                self.metrics["last_update_duration"] = duration
                
                # Wait before next cycle
                await asyncio.sleep(min(60, self.update_interval // 5))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background service error: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _background_update_pins(self):
        """Background update of pin metadata from IPFS."""
        try:
            # This would integrate with actual IPFS API
            # For now, update hotness scores and predicted access times
            current_time = time.time()
            hour_ago = current_time - 3600
            
            with self.lock:
                for cid, pin in self.pin_metadata.items():
                    # Update hotness score based on recent activity
                    recent_accesses = sum(1 for entry in self.access_history 
                                        if entry.get('cid') == cid and entry.get('timestamp', 0) > hour_ago)
                    pin.hotness_score = recent_accesses * 0.1 + (pin.access_count * 0.01)
                    
                    # Simple prediction: likely to be accessed if hot
                    if pin.hotness_score > 1.0:
                        pin.predicted_access_time = current_time + 3600  # Next hour
                    elif pin.hotness_score > 0.5:
                        pin.predicted_access_time = current_time + 7200  # Next 2 hours
            
            logger.debug("Background pin update completed")
            
        except Exception as e:
            logger.error(f"Background pin update error: {e}")
    
    async def _background_analytics(self):
        """Background analytics processing."""
        try:
            # Update tier analytics
            current_time = time.time()
            
            # Calculate per-tier statistics
            tier_stats = {}
            for pin in self.pin_metadata.values():
                tier = pin.primary_tier
                if tier not in tier_stats:
                    tier_stats[tier] = {
                        'total_pins': 0,
                        'total_size': 0,
                        'total_accesses': 0,
                        'last_access': 0
                    }
                
                stats = tier_stats[tier]
                stats['total_pins'] += 1
                stats['total_size'] += pin.size_bytes
                stats['total_accesses'] += pin.access_count
                stats['last_access'] = max(stats['last_access'], pin.last_accessed)
            
            # Store tier analytics
            for tier, stats in tier_stats.items():
                # Calculate health score (simplified)
                recency = max(0, 1 - (current_time - stats['last_access']) / 86400)  # 1 day decay
                health_score = min(1.0, recency + (stats['total_accesses'] / 1000))
                
                self.conn.execute("""
                    INSERT INTO tier_analytics 
                    (timestamp, tier, total_pins, total_size_bytes, read_operations, 
                     write_operations, average_response_time, health_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    current_time,
                    tier,
                    stats['total_pins'],
                    stats['total_size'],
                    stats['total_accesses'],
                    0,  # write_operations (would need tracking)
                    0,  # average_response_time (would need tracking)
                    health_score
                ])
            
            self.metrics["analytics_runs"] += 1
            logger.debug("Background analytics completed")
            
        except Exception as e:
            logger.error(f"Background analytics error: {e}")
    
    async def _background_predictions(self):
        """Background predictive analytics."""
        try:
            # Simple predictive model based on access patterns
            current_time = time.time()
            
            with self.lock:
                for cid, pin in self.pin_metadata.items():
                    # Predict next access based on pattern
                    if pin.access_pattern == "sequential":
                        # Sequential access might continue
                        if pin.last_accessed > current_time - 3600:  # Recently accessed
                            pin.predicted_access_time = current_time + 1800  # 30 minutes
                    elif pin.access_pattern == "streaming":
                        # Streaming content might be accessed continuously
                        pin.predicted_access_time = current_time + 600  # 10 minutes
                    elif pin.hotness_score > 2.0:
                        # Very hot content
                        pin.predicted_access_time = current_time + 1800  # 30 minutes
            
            self.metrics["predictions_generated"] += 1
            logger.debug("Background predictions completed")
            
        except Exception as e:
            logger.error(f"Background predictions error: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance and operational metrics."""
        with self.lock:
            total_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
            cache_hit_rate = self.metrics["cache_hits"] / max(1, total_requests)
            
            return {
                "cache_performance": {
                    "total_pins_cached": len(self.pin_metadata),
                    "cache_hit_rate": cache_hit_rate,
                    "total_requests": total_requests
                },
                "integration_metrics": {
                    "vfs_integrations": self.metrics["vfs_integrations"],
                    "journal_syncs": self.metrics["journal_syncs"],
                    "analytics_runs": self.metrics["analytics_runs"],
                    "predictions_generated": self.metrics["predictions_generated"]
                },
                "background_services": {
                    "running": self.running,
                    "last_update_duration": self.metrics["last_update_duration"],
                    "update_interval": self.update_interval
                },
                "storage_info": {
                    "data_directory": str(self.data_dir),
                    "database_path": str(self.db_path),
                    "parquet_files": {
                        "pins": str(self.pins_parquet),
                        "analytics": str(self.analytics_parquet),
                        "pins_exists": self.pins_parquet.exists(),
                        "analytics_exists": self.analytics_parquet.exists()
                    }
                },
                "capabilities": {
                    "analytics_enabled": self.enable_analytics,
                    "predictions_enabled": self.enable_predictions,
                    "vfs_integration": self.ipfs_filesystem is not None,
                    "journal_sync": self.journal is not None
                }
            }


# Global instance management
_global_enhanced_pin_index: Optional[EnhancedPinMetadataIndex] = None


def get_global_enhanced_pin_index(
    data_dir: Optional[str] = None,
    ipfs_filesystem: Optional['IPFSFileSystem'] = None,
    journal: Optional['FilesystemJournal'] = None,
    **kwargs
) -> EnhancedPinMetadataIndex:
    """
    Get or create the global enhanced pin metadata index.
    
    This provides a singleton instance that can be used across the application,
    including CLI tools, API endpoints, and dashboard.
    
    Args:
        data_dir: Data directory for storage (default: ~/.ipfs_kit/enhanced_pin_index)
        ipfs_filesystem: IPFSFileSystem instance for VFS integration
        journal: FilesystemJournal for real-time sync
        **kwargs: Additional configuration options
    
    Returns:
        Global EnhancedPinMetadataIndex instance
    """
    global _global_enhanced_pin_index
    
    if _global_enhanced_pin_index is None:
        _global_enhanced_pin_index = EnhancedPinMetadataIndex(
            data_dir=data_dir,
            ipfs_filesystem=ipfs_filesystem,
            journal=journal,
            **kwargs
        )
    
    return _global_enhanced_pin_index


async def start_global_enhanced_pin_index(**kwargs):
    """Start the global enhanced pin metadata index background services."""
    index = get_global_enhanced_pin_index(**kwargs)
    await index.start_background_services()
    return index


async def stop_global_enhanced_pin_index():
    """Stop the global enhanced pin metadata index."""
    global _global_enhanced_pin_index
    if _global_enhanced_pin_index:
        await _global_enhanced_pin_index.stop_background_services()


# CLI Integration Helper
def get_cli_pin_metrics() -> Dict[str, Any]:
    """
    Get pin metrics for CLI usage.
    
    This function provides a simple interface for CLI tools to access
    pin metadata and analytics.
    
    Returns:
        Dictionary with comprehensive pin metrics
    """
    try:
        index = get_global_enhanced_pin_index()
        metrics = index.get_comprehensive_metrics()
        performance = index.get_performance_metrics()
        vfs_analytics = index.get_vfs_analytics()
        
        return {
            "traffic_metrics": asdict(metrics),
            "performance_metrics": performance,
            "vfs_analytics": vfs_analytics,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"CLI metrics error: {e}")
        return {"error": str(e), "timestamp": time.time()}


if __name__ == "__main__":
    # Simple test/demo
    import asyncio
    
    async def demo():
        print("🚀 Enhanced Pin Metadata Index Demo")
        
        # Initialize index
        index = EnhancedPinMetadataIndex(
            data_dir="/tmp/enhanced_pin_demo",
            enable_analytics=True,
            enable_predictions=True
        )
        
        # Start background services
        await index.start_background_services()
        
        # Record some test accesses
        test_cids = [
            ("QmTestDemo1234567890abcdef", "sequential", "/vfs/test1.txt"),
            ("QmTestDemo2345678901bcdefg", "streaming", "/vfs/video.mp4"),
            ("QmTestDemo3456789012cdefgh", "random", "/vfs/data.json")
        ]
        
        for cid, pattern, vfs_path in test_cids:
            index.record_enhanced_access(
                cid=cid,
                access_pattern=pattern,
                vfs_path=vfs_path,
                tier="ipfs"
            )
            print(f"✓ Recorded access: {cid[:16]}... ({pattern})")
        
        # Get comprehensive metrics
        metrics = index.get_comprehensive_metrics()
        print(f"\n📊 Comprehensive Metrics:")
        print(f"  - Total pins: {metrics.total_pins}")
        print(f"  - VFS mounts: {metrics.vfs_mounts}")
        print(f"  - Storage tiers: {list(metrics.tier_distribution.keys())}")
        
        # Get VFS analytics
        vfs_analytics = index.get_vfs_analytics()
        print(f"\n🔍 VFS Analytics:")
        print(f"  - VFS pins: {vfs_analytics.get('total_vfs_pins', 0)}")
        print(f"  - Mount points: {len(vfs_analytics.get('mount_points', {}))}")
        
        # Clean up
        await index.stop_background_services()
        print("\n✅ Demo completed successfully!")
    
    asyncio.run(demo())
