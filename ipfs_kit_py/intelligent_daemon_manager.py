#!/usr/bin/env python3
"""
Intelligent Daemon Manager for IPFS Kit

This module provides a metadata-driven, efficient daemon management system that:
1. Uses metadata from ~/.ipfs_kit/ to make intelligent decisions
2. Monitors backend health using the backend_index instead of polling all backends
3. Provides backend-specific functions with isomorphic method names
4. Handles pin syncing, bucket backups, and metadata index backups per backend
5. Uses threading for efficient operations
"""

import anyio
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import pandas as pd

from .storage_wal import BackendHealthMonitor, BackendType
from .config_manager import get_config_manager
from .backend_manager import BackendManager

logger = logging.getLogger(__name__)


@dataclass
class BackendHealthStatus:
    """Health status for a single backend."""
    backend_name: str
    backend_type: str
    is_healthy: bool
    last_check: datetime
    response_time_ms: float
    error_message: Optional[str] = None
    needs_pin_sync: bool = False
    needs_bucket_backup: bool = False
    needs_metadata_backup: bool = False
    pin_count: int = 0
    storage_usage_bytes: int = 0


@dataclass
class DaemonTask:
    """Represents a task for the daemon to execute."""
    task_id: str
    backend_name: str
    task_type: str  # 'pin_sync', 'bucket_backup', 'metadata_backup', 'health_check'
    priority: int  # 1=highest, 10=lowest
    created_at: datetime
    scheduled_for: datetime
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = None


class IntelligentDaemonManager:
    """
    Intelligent daemon manager that uses metadata to optimize backend operations.
    
    This daemon manager uses metadata from ~/.ipfs_kit/ to intelligently monitor
    and manage backends without checking every single bucket unnecessarily.
    
    Key features:
    - Uses bucket_index metadata to identify unhealthy backends
    - Threaded approach for reading bucket indices and backend health
    - Selective bucket checking based on dirty state and health status
    - Intelligent backup and sync operations
    - Efficient metadata-driven operations
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the intelligent daemon manager.
        
        Args:
            config_manager: Optional config manager instance
        """
        self.config_manager = config_manager or get_config_manager()
        self.ipfs_kit_dir = Path.home() / '.ipfs_kit'
        self.backend_index_dir = self.ipfs_kit_dir / 'backend_index'
        self.bucket_index_dir = self.ipfs_kit_dir / 'bucket_index'
        self.pin_metadata_dir = self.ipfs_kit_dir / 'pin_metadata'
        self.backends_dir = self.ipfs_kit_dir / 'backends'
        self.bucket_configs_dir = self.ipfs_kit_dir / 'bucket_configs'
        self.dirty_metadata_dir = self.backend_index_dir / 'dirty_metadata'
        
        # Ensure directories exist
        for dir_path in [self.backend_index_dir, self.bucket_index_dir, self.pin_metadata_dir,
                         self.backends_dir, self.bucket_configs_dir, self.dirty_metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Backend health monitoring
        self.health_monitor = None
        self.backend_status: Dict[str, BackendHealthStatus] = {}
        
        # Metadata-driven state tracking
        self.dirty_backends: Set[str] = set()
        self.unhealthy_backends_cache: Set[str] = set()
        self.bucket_registry_cache: Optional[pd.DataFrame] = None
        self.last_bucket_scan = 0
        self.bucket_scan_interval = 60  # Scan bucket registry every minute
        
        # Task queue and execution
        self.task_queue: List[DaemonTask] = []
        self.active_tasks: Set[str] = set()
        self.completed_tasks: List[DaemonTask] = []
        
        # Threading - Enhanced for metadata-driven operations
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="IPFS-Kit-Daemon")
        self.metadata_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="IPFS-Kit-Metadata")
        
        # Intervals - Optimized based on metadata importance
        self.health_check_interval = 180  # 3 minutes (faster for critical backends)
        self.task_check_interval = 30     # 30 seconds (more responsive)
        self.dirty_check_interval = 15    # 15 seconds (very responsive for dirty backends)
        self.backup_check_interval = 600  # 10 minutes for backup operations
        
        # Control flags
        self._running = False
        self._stop_event = threading.Event()
        
        # Metadata reader thread for bucket index monitoring
        self._metadata_thread = None
        self._dirty_monitor_thread = None
        
        # Backend adapters with isomorphic interfaces
        self.backend_adapters = {}
        self._initialize_backend_adapters()
        
        logger.info("Enhanced Intelligent Daemon Manager initialized with metadata-driven operations")
    
    def _initialize_backend_adapters(self):
        """Initialize backend adapters based on configurations."""
        try:
            from .backend_manager import get_backend_manager
            self.backend_manager = get_backend_manager()
            
            # Discover backends and their configurations
            backends = self.backend_manager.discover_backends()
            
            for backend_name, config in backends.items():
                # Skip disabled backends
                if not config.get('enabled', True):
                    continue
                
                try:
                    # Get adapter through backend manager
                    adapter = self.backend_manager.get_backend_adapter(backend_name)
                    if adapter:
                        logger.info(f"Initialized adapter for backend: {backend_name}")
                    else:
                        logger.warning(f"Failed to initialize adapter for backend: {backend_name}")
                        
                except Exception as e:
                    logger.error(f"Error initializing adapter for {backend_name}: {e}")
            
            logger.info(f"Backend adapter initialization completed")
            
        except Exception as e:
            logger.error(f"Error initializing backend adapters: {e}")
            # Initialize empty backend manager
            self.backend_manager = None
    
    def get_backend_index(self) -> pd.DataFrame:
        """
        Load backend index from metadata files.
        
        Returns:
            DataFrame with backend information from the index
        """
        try:
            backend_registry_path = self.backend_index_dir / 'backend_registry.parquet'
            
            if backend_registry_path.exists():
                df = pd.read_parquet(backend_registry_path)
                logger.debug(f"Loaded {len(df)} backends from registry")
                return df
            else:
                logger.warning("Backend registry not found, returning empty DataFrame")
                return pd.DataFrame(columns=[
                    'name', 'type', 'endpoint', 'health_status', 'last_check',
                    'response_time_ms', 'error_count', 'pin_count', 'storage_usage'
                ])
                
        except Exception as e:
            logger.error(f"Error loading backend index: {e}")
            return pd.DataFrame()

    def get_bucket_index(self) -> Optional[pd.DataFrame]:
        """
        Load bucket index from metadata files with caching.
        
        Returns:
            DataFrame with bucket information from the index
        """
        try:
            current_time = time.time()
            
            # Check if we have a cached version that's still fresh
            if (self.bucket_registry_cache is not None and 
                current_time - self.last_bucket_scan < self.bucket_scan_interval):
                return self.bucket_registry_cache
            
            bucket_registry_path = self.bucket_index_dir / 'bucket_registry.parquet'
            
            if bucket_registry_path.exists():
                df = pd.read_parquet(bucket_registry_path)
                logger.debug(f"Loaded {len(df)} buckets from registry")
                
                # Cache the result
                self.bucket_registry_cache = df
                self.last_bucket_scan = current_time
                
                return df
            else:
                logger.debug("Bucket registry not found, returning empty DataFrame")
                return pd.DataFrame(columns=[
                    'bucket_name', 'backend_names', 'pin_count', 'last_updated',
                    'health_status', 'needs_backup', 'last_backup'
                ])
                
        except Exception as e:
            logger.error(f"Error loading bucket index: {e}")
            return pd.DataFrame()
    
    def scan_dirty_backends_from_metadata(self) -> Set[str]:
        """
        Scan dirty metadata directory to find backends that need synchronization.
        
        Returns:
            Set of backend names that are marked as dirty
        """
        dirty_backends = set()
        
        try:
            if not self.dirty_metadata_dir.exists():
                logger.debug("Dirty metadata directory does not exist")
                return dirty_backends
            
            for dirty_file in self.dirty_metadata_dir.glob('*_dirty.json'):
                try:
                    with open(dirty_file, 'r') as f:
                        dirty_data = json.load(f)
                    
                    # Check if backend is marked as dirty
                    if dirty_data.get('is_dirty', False):
                        backend_name = dirty_data.get('backend_name', 
                                                    dirty_file.stem.replace('_dirty', ''))
                        dirty_backends.add(backend_name)
                        
                        # Check for pending actions that haven't been synced
                        pending_actions = dirty_data.get('pending_actions', [])
                        unsynced_actions = [action for action in pending_actions 
                                          if not action.get('synced', True)]
                        
                        if unsynced_actions:
                            logger.info(f"Backend {backend_name} has {len(unsynced_actions)} unsynced actions")
                        
                except Exception as e:
                    logger.error(f"Error reading dirty file {dirty_file}: {e}")
            
            if dirty_backends:
                logger.info(f"Found {len(dirty_backends)} dirty backends: {list(dirty_backends)}")
            
        except Exception as e:
            logger.error(f"Error scanning dirty backends: {e}")
        
        return dirty_backends
    
    def get_backends_from_bucket_metadata(self) -> Dict[str, List[str]]:
        """
        Extract backend relationships from bucket metadata.
        
        Returns:
            Dictionary mapping bucket names to list of backend names
        """
        bucket_backend_map = {}
        
        try:
            bucket_df = self.get_bucket_index()
            if bucket_df is None or bucket_df.empty:
                return bucket_backend_map
            
            for _, bucket_row in bucket_df.iterrows():
                bucket_name = bucket_row.get('bucket_name', '')
                backend_names = bucket_row.get('backend_names', [])
                
                if isinstance(backend_names, str):
                    # Handle case where backend_names is stored as a string
                    try:
                        backend_names = json.loads(backend_names)
                    except json.JSONDecodeError:
                        backend_names = [backend_names]
                
                if bucket_name and backend_names:
                    bucket_backend_map[bucket_name] = backend_names
            
            logger.debug(f"Extracted {len(bucket_backend_map)} bucket-backend mappings")
            
        except Exception as e:
            logger.error(f"Error extracting backend relationships: {e}")
        
        return bucket_backend_map
    
    def identify_backends_needing_pin_sync(self) -> Set[str]:
        """
        Identify backends that need pin synchronization based on metadata analysis.
        
        Returns:
            Set of backend names that need pin sync
        """
        backends_needing_sync = set()
        
        try:
            # Get dirty backends first
            dirty_backends = self.scan_dirty_backends_from_metadata()
            backends_needing_sync.update(dirty_backends)
            
            # Check for backends with inconsistent pin counts
            bucket_backend_map = self.get_backends_from_bucket_metadata()
            backend_index = self.get_backend_index()
            
            for bucket_name, backend_names in bucket_backend_map.items():
                # Check if any backend for this bucket is unhealthy
                for backend_name in backend_names:
                    if backend_name in self.unhealthy_backends_cache:
                        backends_needing_sync.add(backend_name)
                        logger.debug(f"Backend {backend_name} needs sync (unhealthy)")
                    
                    # Check backend index for stale information
                    backend_mask = backend_index['name'] == backend_name
                    if backend_mask.any():
                        backend_info = backend_index[backend_mask].iloc[0]
                        last_check = pd.to_datetime(backend_info['last_check'])
                        
                        # If backend hasn't been checked in 6 hours, schedule sync
                        if (datetime.now() - last_check).total_seconds() > 21600:
                            backends_needing_sync.add(backend_name)
                            logger.debug(f"Backend {backend_name} needs sync (stale)")
            
            if backends_needing_sync:
                logger.info(f"Identified {len(backends_needing_sync)} backends needing pin sync")
                
        except Exception as e:
            logger.error(f"Error identifying backends needing pin sync: {e}")
        
        return backends_needing_sync
    
    def check_filesystem_backends_for_metadata_backup(self) -> List[str]:
        """
        Check which filesystem backends should receive metadata backups.
        
        Returns:
            List of filesystem backend names for metadata backup
        """
        filesystem_backends = []
        
        try:
            backend_index = self.get_backend_index()
            
            # Look for filesystem-type backends
            filesystem_mask = backend_index['type'].str.contains(
                'filesystem|local|file', case=False, na=False
            )
            filesystem_backends = backend_index[filesystem_mask]['name'].tolist()
            
            if filesystem_backends:
                logger.debug(f"Found {len(filesystem_backends)} filesystem backends for metadata backup")
            
        except Exception as e:
            logger.error(f"Error checking filesystem backends: {e}")
        
        return filesystem_backends
    
    def read_backend_pin_mappings(self, backend_name: str) -> pd.DataFrame:
        """
        Read pin mappings from standardized pin_mappings.parquet file.
        
        Args:
            backend_name: Name of the backend
            
        Returns:
            DataFrame with pin mappings or empty DataFrame if not found
        """
        try:
            backend_path = self.ipfs_kit_dir / "backends" / backend_name
            pin_mappings_path = backend_path / "pin_mappings.parquet"
            
            if pin_mappings_path.exists():
                df = pd.read_parquet(pin_mappings_path)
                logger.debug(f"Read {len(df)} pin mappings from {backend_name}")
                return df
            else:
                logger.debug(f"No pin_mappings.parquet found for {backend_name}")
                # Return empty DataFrame with correct schema
                return pd.DataFrame(columns=['cid', 'car_file_path', 'backend_name', 'created_at', 'status', 'metadata'])
                
        except Exception as e:
            logger.warning(f"Error reading pin mappings for {backend_name}: {e}")
            return pd.DataFrame(columns=['cid', 'car_file_path', 'backend_name', 'created_at', 'status', 'metadata'])
    
    def get_all_pin_mappings(self) -> Dict[str, pd.DataFrame]:
        """
        Get pin mappings from all backends.
        
        Returns:
            Dictionary mapping backend names to their pin mappings DataFrames
        """
        all_mappings = {}
        
        try:
            backends_path = self.ipfs_kit_dir / "backends"
            if not backends_path.exists():
                logger.warning("Backends directory not found")
                return all_mappings
            
            for backend_dir in backends_path.iterdir():
                if backend_dir.is_dir():
                    backend_name = backend_dir.name
                    mappings_df = self.read_backend_pin_mappings(backend_name)
                    
                    if not mappings_df.empty:
                        all_mappings[backend_name] = mappings_df
                        
            logger.debug(f"Read pin mappings from {len(all_mappings)} backends")
            
        except Exception as e:
            logger.error(f"Error getting all pin mappings: {e}")
        
        return all_mappings
    
    def analyze_pin_status_across_backends(self) -> Dict[str, Any]:
        """
        Analyze pin status distribution across all backends.
        
        Returns:
            Dictionary with pin status analysis
        """
        analysis = {
            'total_pins': 0,
            'backends_with_pins': 0,
            'pin_status_distribution': {},
            'backends_with_failed_pins': [],
            'backends_with_pending_pins': [],
            'cid_redundancy': {},
            'oldest_pin_date': None,
            'newest_pin_date': None
        }
        
        try:
            all_mappings = self.get_all_pin_mappings()
            
            if not all_mappings:
                return analysis
            
            all_pins = []
            cid_backend_map = {}
            
            for backend_name, mappings_df in all_mappings.items():
                if mappings_df.empty:
                    continue
                
                analysis['backends_with_pins'] += 1
                analysis['total_pins'] += len(mappings_df)
                
                # Status distribution
                status_counts = mappings_df['status'].value_counts()
                for status, count in status_counts.items():
                    analysis['pin_status_distribution'][status] = analysis['pin_status_distribution'].get(status, 0) + count
                
                # Backends with issues
                if 'failed' in status_counts:
                    analysis['backends_with_failed_pins'].append(backend_name)
                    
                if 'pending' in status_counts:
                    analysis['backends_with_pending_pins'].append(backend_name)
                
                # CID redundancy tracking
                for cid in mappings_df['cid'].unique():
                    if cid not in cid_backend_map:
                        cid_backend_map[cid] = []
                    cid_backend_map[cid].append(backend_name)
                
                # Date tracking
                mappings_df['created_at_dt'] = pd.to_datetime(mappings_df['created_at'])
                min_date = mappings_df['created_at_dt'].min()
                max_date = mappings_df['created_at_dt'].max()
                
                if analysis['oldest_pin_date'] is None or min_date < analysis['oldest_pin_date']:
                    analysis['oldest_pin_date'] = min_date
                    
                if analysis['newest_pin_date'] is None or max_date > analysis['newest_pin_date']:
                    analysis['newest_pin_date'] = max_date
                
                all_pins.extend(mappings_df.to_dict('records'))
            
            # Calculate CID redundancy
            redundancy_counts = {}
            for cid, backends in cid_backend_map.items():
                redundancy_level = len(backends)
                redundancy_counts[redundancy_level] = redundancy_counts.get(redundancy_level, 0) + 1
            
            analysis['cid_redundancy'] = redundancy_counts
            analysis['total_unique_cids'] = len(cid_backend_map)
            analysis['average_redundancy'] = sum(len(backends) for backends in cid_backend_map.values()) / len(cid_backend_map) if cid_backend_map else 0
            
            logger.debug(f"Pin analysis complete: {analysis['total_pins']} pins across {analysis['backends_with_pins']} backends")
            
        except Exception as e:
            logger.error(f"Error analyzing pin status: {e}")
        
        return analysis
        """
        Load backend index from metadata files.
        
        Returns:
            DataFrame with backend information from the index
        """
        try:
            backend_registry_path = self.backend_index_dir / 'backend_registry.parquet'
            
            if backend_registry_path.exists():
                df = pd.read_parquet(backend_registry_path)
                logger.debug(f"Loaded {len(df)} backends from registry")
                return df
            else:
                logger.warning("Backend registry not found, returning empty DataFrame")
                return pd.DataFrame(columns=[
                    'name', 'type', 'endpoint', 'health_status', 'last_check',
                    'response_time_ms', 'error_count', 'pin_count', 'storage_usage'
                ])
                
        except Exception as e:
            logger.error(f"Error loading backend index: {e}")
            return pd.DataFrame()
    
    def update_backend_index(self, backend_name: str, status: BackendHealthStatus):
        """
        Update the backend index with new health status.
        
        Args:
            backend_name: Name of the backend
            status: Health status information
        """
        try:
            df = self.get_backend_index()
            
            # Update or append backend status
            mask = df['name'] == backend_name
            if mask.any():
                # Update existing entry
                df.loc[mask, 'health_status'] = 'healthy' if status.is_healthy else 'unhealthy'
                df.loc[mask, 'last_check'] = status.last_check.isoformat()
                df.loc[mask, 'response_time_ms'] = status.response_time_ms
                df.loc[mask, 'pin_count'] = status.pin_count
                df.loc[mask, 'storage_usage'] = status.storage_usage_bytes
            else:
                # Add new entry
                new_row = {
                    'name': backend_name,
                    'type': status.backend_type,
                    'health_status': 'healthy' if status.is_healthy else 'unhealthy',
                    'last_check': status.last_check.isoformat(),
                    'response_time_ms': status.response_time_ms,
                    'error_count': 0 if status.is_healthy else 1,
                    'pin_count': status.pin_count,
                    'storage_usage': status.storage_usage_bytes
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            # Save updated index
            backend_registry_path = self.backend_index_dir / 'backend_registry.parquet'
            df.to_parquet(backend_registry_path, index=False)
            
            logger.debug(f"Updated backend index for {backend_name}")
            
        except Exception as e:
            logger.error(f"Error updating backend index: {e}")
    
    def get_unhealthy_backends(self) -> List[str]:
        """
        Get list of unhealthy backends from the index.
        
        Returns:
            List of backend names that are unhealthy
        """
        try:
            df = self.get_backend_index()
            if df.empty:
                return []
                
            unhealthy_mask = df['health_status'] != 'healthy'
            unhealthy_backends = df[unhealthy_mask]['name'].tolist()
            
            logger.info(f"Found {len(unhealthy_backends)} unhealthy backends")
            return unhealthy_backends
            
        except Exception as e:
            logger.error(f"Error getting unhealthy backends: {e}")
            return []
    
    def get_backends_needing_sync(self) -> Dict[str, List[str]]:
        """
        Determine which backends need pin synchronization based on metadata.
        
        Returns:
            Dictionary mapping sync types to list of backend names
        """
        try:
            sync_needs = {
                'pin_sync': [],
                'bucket_backup': [],
                'metadata_backup': []
            }
            
            df = self.get_backend_index()
            if df.empty:
                return sync_needs
            
            # Check for backends that haven't been checked recently
            now = datetime.now()
            stale_threshold = now - timedelta(hours=6)
            
            for _, backend in df.iterrows():
                backend_name = backend['name']
                last_check = pd.to_datetime(backend['last_check'])
                
                # Check if backend needs various types of sync
                if last_check < stale_threshold:
                    sync_needs['pin_sync'].append(backend_name)
                
                # Check if bucket backup is needed (based on pin count changes)
                if backend.get('pin_count', 0) > 0:
                    sync_needs['bucket_backup'].append(backend_name)
                
                # Always include in metadata backup
                sync_needs['metadata_backup'].append(backend_name)
            
            logger.info(f"Sync needs determined: {sync_needs}")
            return sync_needs
            
        except Exception as e:
            logger.error(f"Error determining sync needs: {e}")
            return {'pin_sync': [], 'bucket_backup': [], 'metadata_backup': []}
    
    async def check_backend_health(self, backend_name: str) -> BackendHealthStatus:
        """
        Check health of a specific backend using its adapter.
        
        Args:
            backend_name: Name of the backend to check
            
        Returns:
            BackendHealthStatus object
        """
        start_time = time.time()
        
        try:
            if not self.backend_manager:
                raise Exception("Backend manager not available")
            
            # Get health status from backend adapter
            health_result = await self.backend_manager.health_check_backend(backend_name)
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            status = BackendHealthStatus(
                backend_name=backend_name,
                backend_type=health_result.get('backend_type', 'unknown'),
                is_healthy=health_result.get('healthy', False),
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=health_result.get('error'),
                pin_count=health_result.get('pin_count', 0),
                storage_usage_bytes=health_result.get('storage_usage', 0)
            )
            
            # Determine if sync operations are needed
            status.needs_pin_sync = health_result.get('needs_pin_sync', False)
            status.needs_bucket_backup = health_result.get('needs_bucket_backup', False)
            status.needs_metadata_backup = health_result.get('needs_metadata_backup', False)
            
            logger.debug(f"Health check for {backend_name}: {'healthy' if status.is_healthy else 'unhealthy'}")
            return status
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Error checking health of {backend_name}: {e}")
            
            return BackendHealthStatus(
                backend_name=backend_name,
                backend_type='unknown',
                is_healthy=False,
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=str(e)
            )
    
    def schedule_task(self, task: DaemonTask):
        """
        Schedule a task for execution.
        
        Args:
            task: DaemonTask to schedule
        """
        # Check if similar task already exists
        existing_task = None
        for existing in self.task_queue:
            if (existing.backend_name == task.backend_name and 
                existing.task_type == task.task_type and
                existing.task_id not in self.active_tasks):
                existing_task = existing
                break
        
        if existing_task:
            # Update existing task priority if new one is higher priority
            if task.priority < existing_task.priority:
                existing_task.priority = task.priority
                existing_task.scheduled_for = task.scheduled_for
                logger.debug(f"Updated existing task {existing_task.task_id} priority")
            return
        
        # Add new task
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: (t.priority, t.scheduled_for))
        
        logger.info(f"Scheduled task {task.task_id}: {task.task_type} for {task.backend_name}")
    
    async def execute_task(self, task: DaemonTask) -> bool:
        """
        Execute a specific task.
        
        Args:
            task: DaemonTask to execute
            
        Returns:
            True if task succeeded, False otherwise
        """
        try:
            self.active_tasks.add(task.task_id)
            logger.info(f"Executing task {task.task_id}: {task.task_type} for {task.backend_name}")
            
            if not self.backend_manager:
                logger.error("Backend manager not available")
                return False
            
            # Execute task based on type
            success = False
            if task.task_type == 'health_check':
                status = await self.check_backend_health(task.backend_name)
                self.backend_status[task.backend_name] = status
                self.update_backend_index(task.backend_name, status)
                success = True
                
            elif task.task_type == 'pin_sync':
                success = await self.backend_manager.sync_pins_to_backend(task.backend_name)
                
            elif task.task_type == 'bucket_backup':
                success = await self.backend_manager.backup_buckets_to_backend(task.backend_name)
                
            elif task.task_type == 'metadata_backup':
                success = await self.backend_manager.backup_metadata_to_backend(task.backend_name)
                
            else:
                logger.error(f"Unknown task type: {task.task_type}")
                success = False
            
            if success:
                logger.info(f"Task {task.task_id} completed successfully")
                task.retry_count = 0  # Reset retry count on success
            else:
                logger.warning(f"Task {task.task_id} failed")
                task.retry_count += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            task.retry_count += 1
            return False
            
        finally:
            self.active_tasks.discard(task.task_id)
            self.completed_tasks.append(task)
            
            # Limit completed tasks history
            if len(self.completed_tasks) > 1000:
                self.completed_tasks = self.completed_tasks[-500:]
    
    def _metadata_reader_worker(self):
        """Worker thread for reading and analyzing bucket/backend metadata."""
        logger.info("Started metadata reader worker thread")
        
        while not self._stop_event.is_set():
            try:
                if not self._running:
                    time.sleep(1)
                    continue
                
                start_time = time.time()
                
                # Read bucket index metadata
                bucket_df = self.get_bucket_index()
                
                # Scan for dirty backends
                dirty_backends = self.scan_dirty_backends_from_metadata()
                self.dirty_backends = dirty_backends
                
                # Update unhealthy backends cache from backend index
                backend_df = self.get_backend_index()
                if not backend_df.empty:
                    unhealthy_mask = backend_df['health_status'] != 'healthy'
                    self.unhealthy_backends_cache = set(backend_df[unhealthy_mask]['name'].tolist())
                
                # Log metadata analysis results
                read_duration = time.time() - start_time
                logger.debug(f"Metadata scan completed in {read_duration:.2f}s - "
                           f"Dirty: {len(dirty_backends)}, Unhealthy: {len(self.unhealthy_backends_cache)}")
                
                # Wait for next metadata scan
                self._stop_event.wait(self.bucket_scan_interval)
                
            except Exception as e:
                logger.error(f"Error in metadata reader worker: {e}")
                time.sleep(30)  # Wait before retrying
    
    def _dirty_backend_monitor_worker(self):
        """Worker thread dedicated to monitoring dirty backends and scheduling immediate sync."""
        logger.info("Started dirty backend monitor worker thread")
        
        while not self._stop_event.is_set():
            try:
                if not self._running:
                    time.sleep(1)
                    continue
                
                # Check for newly dirty backends
                current_dirty = self.scan_dirty_backends_from_metadata()
                
                # Find backends that became dirty since last check
                newly_dirty = current_dirty - self.dirty_backends
                
                if newly_dirty:
                    logger.info(f"Detected newly dirty backends: {list(newly_dirty)}")
                    
                    # Schedule immediate sync tasks for newly dirty backends
                    now = datetime.now()
                    for backend_name in newly_dirty:
                        # High priority sync task
                        sync_task = DaemonTask(
                            task_id=f"urgent_pin_sync_{backend_name}_{int(now.timestamp())}",
                            backend_name=backend_name,
                            task_type='pin_sync',
                            priority=1,  # Highest priority
                            created_at=now,
                            scheduled_for=now + timedelta(seconds=30)  # Very quick scheduling
                        )
                        self.schedule_task(sync_task)
                
                # Update dirty backends cache
                self.dirty_backends = current_dirty
                
                # Wait for next dirty check (frequent for responsiveness)
                self._stop_event.wait(self.dirty_check_interval)
                
            except Exception as e:
                logger.error(f"Error in dirty backend monitor worker: {e}")
                time.sleep(15)  # Brief wait before retrying
    
    def _health_check_worker(self):
        """Worker thread for periodic health checks based on metadata priority."""
        logger.info("Started health check worker thread")
        
        while not self._stop_event.is_set():
            try:
                if not self._running:
                    time.sleep(1)
                    continue
                
                # Get backends from index with priority-based checking
                df = self.get_backend_index()
                
                # Priority order: dirty backends, unhealthy backends, then others
                backends_to_check = []
                
                # First priority: dirty backends
                for backend_name in self.dirty_backends:
                    backends_to_check.append((backend_name, 1))  # Highest priority
                
                # Second priority: previously unhealthy backends
                for backend_name in self.unhealthy_backends_cache:
                    if backend_name not in self.dirty_backends:
                        backends_to_check.append((backend_name, 2))
                
                # Third priority: all other backends
                for _, backend in df.iterrows():
                    backend_name = backend['name']
                    if (backend_name not in self.dirty_backends and 
                        backend_name not in self.unhealthy_backends_cache):
                        backends_to_check.append((backend_name, 3))
                
                # Schedule health checks with appropriate priority
                now = datetime.now()
                for backend_name, priority in backends_to_check:
                    # Schedule with staggered timing based on priority
                    delay_minutes = priority * 2  # 2, 4, 6 minute delays
                    
                    task = DaemonTask(
                        task_id=f"health_check_{backend_name}_{int(now.timestamp())}",
                        backend_name=backend_name,
                        task_type='health_check',
                        priority=priority + 4,  # 5, 6, 7 priority levels
                        created_at=now,
                        scheduled_for=now + timedelta(minutes=delay_minutes)
                    )
                    
                    self.schedule_task(task)
                
                # Wait for next health check interval
                self._stop_event.wait(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health check worker: {e}")
                time.sleep(60)  # Wait before retrying
    
    def _task_execution_worker(self):
        """Worker thread for executing scheduled tasks with metadata-driven intelligence."""
        logger.info("Started task execution worker thread")
        
        while not self._stop_event.is_set():
            try:
                if not self._running:
                    time.sleep(1)
                    continue
                
                now = datetime.now()
                
                # Find tasks ready for execution
                ready_tasks = []
                for task in self.task_queue[:]:
                    if (task.scheduled_for <= now and 
                        task.task_id not in self.active_tasks and
                        task.retry_count < task.max_retries):
                        ready_tasks.append(task)
                        self.task_queue.remove(task)
                
                # Execute ready tasks
                if ready_tasks:
                    # Sort by priority (lower number = higher priority)
                    ready_tasks.sort(key=lambda t: t.priority)
                    
                    # Execute up to 6 tasks concurrently (increased for better throughput)
                    tasks_to_execute = ready_tasks[:6]
                    
                    futures = []
                    for task in tasks_to_execute:
                        future = self.executor.submit(
                            anyio.run,
                            self.execute_task,
                            task,
                        )
                        futures.append((task, future))
                    
                    # Wait for completion
                    for task, future in futures:
                        try:
                            success = future.result(timeout=300)  # 5 minute timeout
                            if not success and task.retry_count < task.max_retries:
                                # Reschedule failed task with exponential backoff
                                backoff_minutes = min(30, 5 * (2 ** task.retry_count))
                                task.scheduled_for = now + timedelta(minutes=backoff_minutes)
                                self.schedule_task(task)
                                logger.warning(f"Rescheduled failed task {task.task_id} in {backoff_minutes} minutes")
                        except Exception as e:
                            logger.error(f"Task {task.task_id} execution error: {e}")
                
                # Intelligent scheduling based on metadata analysis
                self._schedule_metadata_driven_tasks()
                
                # Wait before next task check (more frequent for responsiveness)
                self._stop_event.wait(self.task_check_interval)
                
            except Exception as e:
                logger.error(f"Error in task execution worker: {e}")
                time.sleep(30)
    
    def _schedule_metadata_driven_tasks(self):
        """Schedule tasks based on intelligent metadata analysis."""
        now = datetime.now()
        
        try:
            # 1. Schedule pin sync for backends that need it based on metadata
            backends_needing_sync = self.identify_backends_needing_pin_sync()
            for backend_name in backends_needing_sync:
                # Check if there's already a recent sync task for this backend
                existing_sync = any(
                    task.backend_name == backend_name and 
                    task.task_type == 'pin_sync' and
                    (now - task.created_at).total_seconds() < 600  # 10 minutes
                    for task in self.task_queue + list(self.completed_tasks[-50:])
                )
                
                if not existing_sync:
                    # Higher priority for dirty/unhealthy backends
                    priority = 2 if backend_name in self.dirty_backends else 4
                    
                    task = DaemonTask(
                        task_id=f"metadata_pin_sync_{backend_name}_{int(now.timestamp())}",
                        backend_name=backend_name,
                        task_type='pin_sync',
                        priority=priority,
                        created_at=now,
                        scheduled_for=now + timedelta(minutes=1)
                    )
                    self.schedule_task(task)
            
            # 2. Schedule bucket backups based on bucket metadata
            bucket_df = self.get_bucket_index()
            if bucket_df is not None and not bucket_df.empty:
                for _, bucket_row in bucket_df.iterrows():
                    bucket_name = bucket_row.get('bucket_name', '')
                    last_backup = bucket_row.get('last_backup', 0)
                    backend_names = bucket_row.get('backend_names', [])
                    
                    # Check if bucket needs backup (older than 1 hour)
                    if isinstance(last_backup, str):
                        try:
                            last_backup = datetime.fromisoformat(last_backup).timestamp()
                        except:
                            last_backup = 0
                    
                    backup_age_hours = (time.time() - last_backup) / 3600
                    
                    if backup_age_hours > 1 and backend_names:  # Backup if older than 1 hour
                        # Schedule backup to filesystem backends
                        filesystem_backends = self.check_filesystem_backends_for_metadata_backup()
                        
                        for fs_backend in filesystem_backends:
                            task = DaemonTask(
                                task_id=f"bucket_backup_{bucket_name}_{fs_backend}_{int(now.timestamp())}",
                                backend_name=fs_backend,
                                task_type='bucket_backup',
                                priority=6,  # Lower priority
                                created_at=now,
                                scheduled_for=now + timedelta(minutes=15),
                                metadata={'bucket_name': bucket_name}
                            )
                            self.schedule_task(task)
            
            # 3. Schedule metadata backups to filesystem backends
            filesystem_backends = self.check_filesystem_backends_for_metadata_backup()
            for backend_name in filesystem_backends:
                # Check if there's a recent metadata backup task
                existing_backup = any(
                    task.backend_name == backend_name and 
                    task.task_type == 'metadata_backup' and
                    (now - task.created_at).total_seconds() < 1800  # 30 minutes
                    for task in self.task_queue + list(self.completed_tasks[-20:])
                )
                
                if not existing_backup:
                    task = DaemonTask(
                        task_id=f"metadata_backup_{backend_name}_{int(now.timestamp())}",
                        backend_name=backend_name,
                        task_type='metadata_backup',
                        priority=8,  # Lower priority
                        created_at=now,
                        scheduled_for=now + timedelta(minutes=30)
                    )
                    self.schedule_task(task)
        
        except Exception as e:
            logger.error(f"Error in metadata-driven task scheduling: {e}")
    
    def start(self):
        """Start the intelligent daemon manager with enhanced metadata-driven operations."""
        if self._running:
            logger.warning("Daemon manager already running")
            return
        
        logger.info("Starting Enhanced Intelligent Daemon Manager with metadata-driven operations")
        self._running = True
        self._stop_event.clear()
        
        # Start metadata reader thread - monitors bucket indices and metadata
        self._metadata_thread = threading.Thread(
            target=self._metadata_reader_worker,
            name="IPFS-Kit-Metadata-Reader",
            daemon=True
        )
        self._metadata_thread.start()
        
        # Start dirty backend monitor thread - immediate response to dirty backends
        self._dirty_monitor_thread = threading.Thread(
            target=self._dirty_backend_monitor_worker,
            name="IPFS-Kit-Dirty-Monitor",
            daemon=True
        )
        self._dirty_monitor_thread.start()
        
        # Start health check worker thread - prioritized health checking
        self.health_thread = threading.Thread(
            target=self._health_check_worker,
            name="IPFS-Kit-Health-Monitor",
            daemon=True
        )
        self.health_thread.start()
        
        # Start task execution worker thread - intelligent task processing
        self.task_thread = threading.Thread(
            target=self._task_execution_worker, 
            name="IPFS-Kit-Task-Executor",
            daemon=True
        )
        self.task_thread.start()
        
        logger.info("Enhanced Intelligent Daemon Manager started successfully with 4 worker threads")
        logger.info(f"Monitoring intervals - Metadata: {self.bucket_scan_interval}s, "
                   f"Dirty check: {self.dirty_check_interval}s, Health: {self.health_check_interval}s")
    
    def stop(self):
        """Stop the intelligent daemon manager and all worker threads."""
        if not self._running:
            return
        
        logger.info("Stopping Enhanced Intelligent Daemon Manager")
        self._running = False
        self._stop_event.set()
        
        # Wait for all threads to complete
        thread_list = [
            ('metadata_thread', getattr(self, '_metadata_thread', None)),
            ('dirty_monitor_thread', getattr(self, '_dirty_monitor_thread', None)),
            ('health_thread', getattr(self, 'health_thread', None)),
            ('task_thread', getattr(self, 'task_thread', None))
        ]
        
        for thread_name, thread in thread_list:
            if thread and thread.is_alive():
                logger.info(f"Waiting for {thread_name} to finish...")
                thread.join(timeout=10)
                if thread.is_alive():
                    logger.warning(f"Thread {thread_name} did not stop gracefully")
        
        # Shutdown executors
        self.executor.shutdown(wait=True)
        self.metadata_executor.shutdown(wait=True)
        
        logger.info("Enhanced Intelligent Daemon Manager stopped")
    
    def _get_pin_mapping_summary(self) -> Dict[str, Any]:
        """
        Get a quick summary of pin mappings for status reporting.
        
        Returns:
            Dictionary with pin mapping summary
        """
        try:
            pin_analysis = self.analyze_pin_status_across_backends()
            
            return {
                'total_pins': pin_analysis['total_pins'],
                'backends_with_pins': pin_analysis['backends_with_pins'],
                'total_unique_cids': pin_analysis['total_unique_cids'],
                'average_redundancy': round(pin_analysis['average_redundancy'], 2),
                'status_distribution': pin_analysis['pin_status_distribution'],
                'failed_pin_backends': len(pin_analysis['backends_with_failed_pins']),
                'pending_pin_backends': len(pin_analysis['backends_with_pending_pins'])
            }
        except Exception as e:
            logger.warning(f"Error getting pin mapping summary: {e}")
            return {
                'total_pins': 0,
                'backends_with_pins': 0,
                'total_unique_cids': 0,
                'average_redundancy': 0,
                'status_distribution': {},
                'failed_pin_backends': 0,
                'pending_pin_backends': 0
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of the enhanced intelligent daemon manager.
        
        Returns:
            Dictionary with detailed status information including metadata-driven insights
        """
        bucket_df = self.get_bucket_index()
        backend_df = self.get_backend_index()
        
        # Calculate metadata-driven statistics
        total_buckets = len(bucket_df) if bucket_df is not None else 0
        total_backends = len(backend_df) if not backend_df.empty else 0
        
        # Thread status
        thread_status = {
            'metadata_reader': getattr(self, '_metadata_thread', None) and self._metadata_thread.is_alive(),
            'dirty_monitor': getattr(self, '_dirty_monitor_thread', None) and self._dirty_monitor_thread.is_alive(),
            'health_monitor': getattr(self, 'health_thread', None) and self.health_thread.is_alive(),
            'task_executor': getattr(self, 'task_thread', None) and self.task_thread.is_alive()
        }
        
        # Get filesystem backends for backup status
        filesystem_backends = self.check_filesystem_backends_for_metadata_backup()
        
        return {
            'running': self._running,
            'thread_status': thread_status,
            'metadata_driven_stats': {
                'total_buckets': total_buckets,
                'total_backends': total_backends,
                'dirty_backends': list(self.dirty_backends),
                'dirty_count': len(self.dirty_backends),
                'unhealthy_backends': list(self.unhealthy_backends_cache),
                'unhealthy_count': len(self.unhealthy_backends_cache),
                'filesystem_backends': filesystem_backends,
                'last_bucket_scan': self.last_bucket_scan,
                'bucket_scan_age_seconds': time.time() - self.last_bucket_scan
            },
            'task_management': {
                'active_tasks': len(self.active_tasks),
                'queued_tasks': len(self.task_queue),
                'completed_tasks': len(self.completed_tasks),
                'active_task_ids': list(self.active_tasks)
            },
            'pin_mapping_summary': self._get_pin_mapping_summary(),
            'backend_health_summary': {
                'healthy_backends': len([s for s in self.backend_status.values() if s.is_healthy]),
                'total_monitored': len(self.backend_status),
                'health_percentage': (len([s for s in self.backend_status.values() if s.is_healthy]) / 
                                    max(len(self.backend_status), 1)) * 100
            },
            'intervals': {
                'bucket_scan_seconds': self.bucket_scan_interval,
                'dirty_check_seconds': self.dirty_check_interval,
                'health_check_seconds': self.health_check_interval,
                'task_check_seconds': self.task_check_interval,
                'backup_check_seconds': self.backup_check_interval
            },
            'last_health_check': max([s.last_check for s in self.backend_status.values()], default=None),
            'backend_status_details': {
                name: {
                    'healthy': status.is_healthy,
                    'last_check': status.last_check.isoformat() if status.last_check else None,
                    'response_time_ms': status.response_time_ms,
                    'pin_count': status.pin_count,
                    'needs_sync': status.needs_pin_sync or name in self.dirty_backends,
                    'needs_backup': status.needs_bucket_backup,
                    'error': status.error_message
                }
                for name, status in self.backend_status.items()
            }
        }
    
    def get_metadata_insights(self) -> Dict[str, Any]:
        """
        Get insights from metadata analysis for operational intelligence.
        
        Returns:
            Dictionary with metadata-driven insights
        """
        try:
            bucket_df = self.get_bucket_index()
            backend_df = self.get_backend_index()
            bucket_backend_map = self.get_backends_from_bucket_metadata()
            
            insights = {
                'bucket_analysis': {
                    'total_buckets': len(bucket_df) if bucket_df is not None else 0,
                    'buckets_needing_backup': 0,
                    'average_pins_per_bucket': 0,
                    'bucket_backend_distribution': {}
                },
                'backend_analysis': {
                    'total_backends': len(backend_df) if not backend_df.empty else 0,
                    'backend_types': {},
                    'response_time_stats': {},
                    'pin_distribution': {}
                },
                'sync_requirements': {
                    'backends_needing_pin_sync': list(self.identify_backends_needing_pin_sync()),
                    'metadata_backup_targets': self.check_filesystem_backends_for_metadata_backup(),
                    'dirty_backend_actions': {}
                },
                'operational_metrics': {
                    'metadata_freshness_seconds': time.time() - self.last_bucket_scan,
                    'avg_backend_health_check_age': 0,
                    'total_pending_actions': 0
                }
            }
            
            # Analyze bucket data
            if bucket_df is not None and not bucket_df.empty:
                # Buckets needing backup
                current_time = time.time()
                backup_threshold = current_time - 3600  # 1 hour
                
                buckets_needing_backup = 0
                total_pins = 0
                
                for _, bucket_row in bucket_df.iterrows():
                    last_backup = bucket_row.get('last_backup', 0)
                    if isinstance(last_backup, str):
                        try:
                            last_backup = datetime.fromisoformat(last_backup).timestamp()
                        except:
                            last_backup = 0
                    
                    if last_backup < backup_threshold:
                        buckets_needing_backup += 1
                    
                    pin_count = bucket_row.get('pin_count', 0)
                    total_pins += pin_count
                
                insights['bucket_analysis']['buckets_needing_backup'] = buckets_needing_backup
                insights['bucket_analysis']['average_pins_per_bucket'] = total_pins / len(bucket_df)
                insights['bucket_analysis']['bucket_backend_distribution'] = {
                    bucket: len(backends) for bucket, backends in bucket_backend_map.items()
                }
            
            # Analyze backend data
            if not backend_df.empty:
                # Backend type distribution
                type_counts = backend_df['type'].value_counts().to_dict()
                insights['backend_analysis']['backend_types'] = type_counts
                
                # Response time statistics
                response_times = backend_df['response_time_ms'].dropna()
                if not response_times.empty:
                    insights['backend_analysis']['response_time_stats'] = {
                        'average_ms': float(response_times.mean()),
                        'median_ms': float(response_times.median()),
                        'max_ms': float(response_times.max()),
                        'min_ms': float(response_times.min())
                    }
                
                # Pin distribution
                pin_counts = backend_df['pin_count'].dropna()
                if not pin_counts.empty:
                    insights['backend_analysis']['pin_distribution'] = {
                        'total_pins': int(pin_counts.sum()),
                        'average_per_backend': float(pin_counts.mean()),
                        'max_pins': int(pin_counts.max()),
                        'backends_with_pins': int((pin_counts > 0).sum())
                    }
                
                # Average health check age
                now = datetime.now()
                check_ages = []
                for _, backend in backend_df.iterrows():
                    try:
                        last_check = pd.to_datetime(backend['last_check'])
                        age_seconds = (now - last_check).total_seconds()
                        check_ages.append(age_seconds)
                    except:
                        pass
                
                if check_ages:
                    insights['operational_metrics']['avg_backend_health_check_age'] = sum(check_ages) / len(check_ages)
            
            # Analyze dirty backend actions
            try:
                total_pending = 0
                for dirty_file in self.dirty_metadata_dir.glob('*_dirty.json'):
                    try:
                        with open(dirty_file, 'r') as f:
                            dirty_data = json.load(f)
                        
                        backend_name = dirty_data.get('backend_name', dirty_file.stem.replace('_dirty', ''))
                        pending_actions = dirty_data.get('pending_actions', [])
                        unsynced_actions = [action for action in pending_actions if not action.get('synced', True)]
                        
                        insights['sync_requirements']['dirty_backend_actions'][backend_name] = {
                            'total_actions': len(pending_actions),
                            'unsynced_actions': len(unsynced_actions),
                            'is_dirty': dirty_data.get('is_dirty', False)
                        }
                        
                        total_pending += len(unsynced_actions)
                        
                    except Exception as e:
                        logger.debug(f"Error analyzing dirty file {dirty_file}: {e}")
                
                insights['operational_metrics']['total_pending_actions'] = total_pending
                
            except Exception as e:
                logger.error(f"Error analyzing dirty backend actions: {e}")
            
            # Add comprehensive pin mapping analysis
            try:
                pin_analysis = self.analyze_pin_status_across_backends()
                insights['pin_mapping_analysis'] = pin_analysis
                
                # Update backend analysis with pin mapping data
                if pin_analysis['total_pins'] > 0:
                    insights['backend_analysis']['total_pins'] = pin_analysis['total_pins']
                    insights['backend_analysis']['backends_with_pins'] = pin_analysis['backends_with_pins']
                    insights['backend_analysis']['pin_status_distribution'] = pin_analysis['pin_status_distribution']
                    insights['backend_analysis']['average_redundancy'] = pin_analysis['average_redundancy']
                
                # Update sync requirements with pin-specific needs
                if pin_analysis['backends_with_failed_pins']:
                    insights['sync_requirements']['backends_with_failed_pins'] = pin_analysis['backends_with_failed_pins']
                    
                if pin_analysis['backends_with_pending_pins']:
                    insights['sync_requirements']['backends_with_pending_pins'] = pin_analysis['backends_with_pending_pins']
                
            except Exception as e:
                logger.warning(f"Error analyzing pin mappings: {e}")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating metadata insights: {e}")
            return {
                'error': str(e),
                'bucket_analysis': {},
                'backend_analysis': {},
                'sync_requirements': {},
                'operational_metrics': {}
            }


# Global instance
_daemon_manager = None

def get_daemon_manager(config_manager=None) -> IntelligentDaemonManager:
    """Get singleton instance of the intelligent daemon manager."""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = IntelligentDaemonManager(config_manager)
    return _daemon_manager
