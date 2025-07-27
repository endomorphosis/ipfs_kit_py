"""
VFS Version Tracking System with IPFS CID-based Versioning.

This module implements Git-like version tracking for the virtual filesystem using
IPFS content addressing. Features include:

1. ~/.ipfs_kit/ folder for VFS index storage in Parquet format
2. IPFS CID-based filesystem hashing using ipfs_multiformats_py
3. CAR file generation for version snapshots
4. Version chain linking using IPFS CIDs
5. Content-addressable storage for all files and metadata
"""

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
import hashlib

logger = logging.getLogger(__name__)

# IPFS Kit imports
try:
    from ipfs_kit_py.error import create_result_dict, handle_error
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    ERROR_HANDLING_AVAILABLE = True
except ImportError:
    ERROR_HANDLING_AVAILABLE = False
    def create_result_dict(success: bool, **kwargs):
        return {"success": success, **kwargs}
    def handle_error(operation: str, error: Exception):
        return {"success": False, "error": str(error)}

# IPFS Multiformats for CID generation
try:
    import multiformats
    from multiformats import CID, multicodec, multihash
    MULTIFORMATS_AVAILABLE = True
except ImportError:
    MULTIFORMATS_AVAILABLE = False
    logger.warning("multiformats not available, using fallback hashing")

# Arrow/Parquet for VFS index storage
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pandas as pd
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False
    logger.warning("Arrow/Parquet not available, using JSON fallback")

# CAR file generation
try:
    from ipfs_kit_py.parquet_car_bridge import ParquetCARBridge
    CAR_BRIDGE_AVAILABLE = True
except ImportError:
    CAR_BRIDGE_AVAILABLE = False
    logger.warning("CAR bridge not available, using manual CAR generation")

# Bucket VFS integration
try:
    from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
    BUCKET_VFS_AVAILABLE = True
except ImportError:
    BUCKET_VFS_AVAILABLE = False


class VFSVersionTracker:
    """
    Git-like version tracking system for virtual filesystems using IPFS CIDs.
    """
    
    def __init__(
        self,
        vfs_root: Optional[str] = None,
        ipfs_client: Optional[Any] = None,
        enable_auto_versioning: bool = True
    ):
        """Initialize VFS version tracker."""
        self.vfs_root = Path(vfs_root) if vfs_root else Path.home() / ".ipfs_kit"
        self.ipfs_client = ipfs_client
        self.enable_auto_versioning = enable_auto_versioning
        
        # VFS structure
        self.vfs_root.mkdir(parents=True, exist_ok=True)
        self.index_dir = self.vfs_root / "index"
        self.versions_dir = self.vfs_root / "versions"
        self.objects_dir = self.vfs_root / "objects"
        self.refs_dir = self.vfs_root / "refs"
        
        # Create directory structure
        for directory in [self.index_dir, self.versions_dir, self.objects_dir, self.refs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Current filesystem state
        self.current_head_file = self.refs_dir / "HEAD"
        self.filesystem_index_file = self.index_dir / "filesystem.parquet"
        self.version_log_file = self.index_dir / "version_log.parquet"
        
        # Initialize IPFS client if not provided
        if not self.ipfs_client:
            try:
                self.ipfs_client = IPFSSimpleAPI()
            except Exception as e:
                logger.warning(f"Could not initialize IPFS client: {e}")
                self.ipfs_client = None
        
        # Initialize tracker
        self._initialize_tracker()
    
    def _initialize_tracker(self):
        """Initialize version tracking system."""
        logger.info(f"Initializing VFS version tracker in {self.vfs_root}")
        
        # Create initial HEAD reference if not exists
        if not self.current_head_file.exists():
            self.current_head_file.write_text("0000000000000000000000000000000000000000000000")
            logger.info("Created initial HEAD reference")
        
        # Create initial filesystem index if not exists
        if not self.filesystem_index_file.exists():
            self._create_empty_filesystem_index()
            logger.info("Created initial filesystem index")
        
        # Create initial version log if not exists  
        if not self.version_log_file.exists():
            self._create_empty_version_log()
            logger.info("Created initial version log")
    
    def _create_empty_filesystem_index(self):
        """Create empty filesystem index in Parquet format."""
        if ARROW_AVAILABLE:
            # Create empty filesystem index schema
            schema = pa.schema([
                ("file_path", pa.string()),
                ("file_cid", pa.string()),
                ("file_size", pa.int64()),
                ("file_type", pa.string()),
                ("content_hash", pa.string()),
                ("metadata", pa.string()),  # JSON encoded
                ("bucket_name", pa.string()),
                ("created_at", pa.timestamp('s')),
                ("modified_at", pa.timestamp('s')),
                ("version_cid", pa.string()),
                ("parent_cid", pa.string())
            ])
            
            # Create empty table
            empty_table = pa.table({
                "file_path": [],
                "file_cid": [],
                "file_size": [],
                "file_type": [],
                "content_hash": [],
                "metadata": [],
                "bucket_name": [],
                "created_at": [],
                "modified_at": [],
                "version_cid": [],
                "parent_cid": []
            }, schema=schema)
            
            # Write to Parquet
            pq.write_table(empty_table, self.filesystem_index_file)
        else:
            # JSON fallback
            empty_index = {
                "files": [],
                "schema_version": "1.0",
                "created_at": datetime.utcnow().isoformat()
            }
            with open(self.filesystem_index_file.with_suffix('.json'), 'w') as f:
                json.dump(empty_index, f, indent=2)
    
    def _create_empty_version_log(self):
        """Create empty version log in Parquet format."""
        if ARROW_AVAILABLE:
            # Create version log schema
            schema = pa.schema([
                ("version_cid", pa.string()),
                ("parent_cid", pa.string()),
                ("commit_message", pa.string()),
                ("author", pa.string()),
                ("created_at", pa.timestamp('ms')),  # Use milliseconds for consistency
                ("file_count", pa.int64()),
                ("total_size", pa.int64()),
                ("filesystem_tree_cid", pa.string()),
                ("car_file_cid", pa.string()),
                ("changes_summary", pa.string()),  # JSON encoded
                ("metadata", pa.string())  # JSON encoded
            ])
            
            # Create empty table
            empty_table = pa.table({
                "version_cid": [],
                "parent_cid": [],
                "commit_message": [],
                "author": [],
                "created_at": [],
                "file_count": [],
                "total_size": [],
                "filesystem_tree_cid": [],
                "car_file_cid": [],
                "changes_summary": [],
                "metadata": []
            }, schema=schema)
            
            # Write to Parquet
            pq.write_table(empty_table, self.version_log_file)
        else:
            # JSON fallback
            empty_log = {
                "versions": [],
                "schema_version": "1.0",
                "created_at": datetime.utcnow().isoformat()
            }
            with open(self.version_log_file.with_suffix('.json'), 'w') as f:
                json.dump(empty_log, f, indent=2)
    
    async def get_current_head(self) -> str:
        """Get current HEAD commit CID."""
        try:
            return self.current_head_file.read_text().strip()
        except Exception as e:
            logger.error(f"Error reading HEAD: {e}")
            return "0000000000000000000000000000000000000000000000"
    
    async def set_current_head(self, version_cid: str):
        """Set current HEAD commit CID."""
        try:
            self.current_head_file.write_text(version_cid)
            logger.info(f"Updated HEAD to {version_cid}")
        except Exception as e:
            logger.error(f"Error updating HEAD: {e}")
    
    async def scan_filesystem(
        self, 
        include_buckets: bool = True,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Scan the current filesystem state and build comprehensive index.
        
        Returns:
            Dict containing filesystem state with all file CIDs and metadata
        """
        logger.info("Scanning filesystem for version tracking...")
        
        filesystem_state = {
            "files": [],
            "buckets": [],
            "metadata": {
                "scan_time": datetime.utcnow().isoformat(),
                "scanner_version": "1.0",
                "total_files": 0,
                "total_size": 0
            }
        }
        
        # Scan bucket VFS if available
        if include_buckets and BUCKET_VFS_AVAILABLE:
            try:
                bucket_manager = get_global_bucket_manager(
                    storage_path=str(self.vfs_root / "buckets"),
                    ipfs_client=self.ipfs_client
                )
                
                # List all buckets
                buckets_result = await bucket_manager.list_buckets()
                if buckets_result["success"]:
                    buckets = buckets_result["data"]["buckets"]
                    
                    for bucket_info in buckets:
                        bucket_name = bucket_info["name"]
                        bucket = await bucket_manager.get_bucket(bucket_name)
                        
                        if bucket:
                            # Scan bucket files
                            bucket_files = await self._scan_bucket_files(bucket)
                            filesystem_state["files"].extend(bucket_files)
                            
                            # Add bucket metadata
                            filesystem_state["buckets"].append({
                                "name": bucket_name,
                                "type": bucket_info.get("type"),
                                "structure": bucket_info.get("vfs_structure"),
                                "root_cid": bucket_info.get("root_cid"),
                                "file_count": len(bucket_files),
                                "created_at": bucket_info.get("created_at")
                            })
                
            except Exception as e:
                logger.warning(f"Error scanning bucket VFS: {e}")
        
        # Scan traditional filesystem paths
        await self._scan_traditional_filesystem(filesystem_state)
        
        # Update metadata
        filesystem_state["metadata"]["total_files"] = len(filesystem_state["files"])
        filesystem_state["metadata"]["total_size"] = sum(
            f.get("file_size", 0) for f in filesystem_state["files"]
        )
        
        logger.info(f"Filesystem scan complete: {filesystem_state['metadata']['total_files']} files")
        return filesystem_state
    
    async def _scan_bucket_files(self, bucket) -> List[Dict[str, Any]]:
        """Scan files within a bucket and generate CIDs."""
        files = []
        
        try:
            files_dir = bucket.dirs.get("files")
            if files_dir and files_dir.exists():
                for file_path in files_dir.rglob("*"):
                    if file_path.is_file():
                        # Generate file info with CID
                        file_info = await self._generate_file_info(
                            file_path, 
                            bucket_name=bucket.name,
                            relative_to=files_dir
                        )
                        if file_info:
                            files.append(file_info)
        
        except Exception as e:
            logger.error(f"Error scanning bucket files: {e}")
        
        return files
    
    async def _scan_traditional_filesystem(self, filesystem_state: Dict[str, Any]):
        """Scan traditional filesystem paths for tracking."""
        # Add common IPFS Kit paths
        scan_paths = [
            self.vfs_root / "cache",
            self.vfs_root / "temp",
            Path.cwd() / "data" if (Path.cwd() / "data").exists() else None
        ]
        
        for scan_path in scan_paths:
            if scan_path and scan_path.exists():
                try:
                    for file_path in scan_path.rglob("*"):
                        if file_path.is_file() and not file_path.name.startswith('.'):
                            file_info = await self._generate_file_info(
                                file_path,
                                bucket_name="system",
                                relative_to=scan_path
                            )
                            if file_info:
                                filesystem_state["files"].append(file_info)
                
                except Exception as e:
                    logger.warning(f"Error scanning {scan_path}: {e}")
    
    async def _generate_file_info(
        self, 
        file_path: Path, 
        bucket_name: str = "system",
        relative_to: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate comprehensive file information with IPFS CID."""
        try:
            # Get file stats
            stat = file_path.stat()
            relative_path = file_path.relative_to(relative_to) if relative_to else file_path.name
            
            # Read file content for CID generation
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                return None
            
            # Generate IPFS CID
            file_cid = await self._generate_content_cid(content)
            
            # Generate content hash
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Extract metadata
            metadata = {
                "permissions": oct(stat.st_mode)[-3:],
                "uid": stat.st_uid,
                "gid": stat.st_gid,
                "absolute_path": str(file_path)
            }
            
            return {
                "file_path": str(relative_path),
                "file_cid": file_cid,
                "file_size": stat.st_size,
                "file_type": self._detect_file_type(file_path),
                "content_hash": content_hash,
                "metadata": json.dumps(metadata),
                "bucket_name": bucket_name,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
                "version_cid": "",  # Will be set during commit
                "parent_cid": ""   # Will be set during commit
            }
            
        except Exception as e:
            logger.error(f"Error generating file info for {file_path}: {e}")
            return None
    
    async def _generate_content_cid(self, content: bytes) -> str:
        """Generate IPFS CID for content using multiformats."""
        if MULTIFORMATS_AVAILABLE:
            try:
                # Create multihash of content (SHA-256)
                digest = multihash.digest(content, "sha2-256")
                
                # Create CID with DAG-PB codec
                cid = CID("base58btc", 1, "dag-pb", digest)
                return str(cid)
                
            except Exception as e:
                logger.warning(f"Multiformats CID generation failed: {e}")
        
        # Fallback to simple hash-based pseudo-CID
        content_hash = hashlib.sha256(content).hexdigest()
        return f"bafybei{content_hash[:52]}"  # Pseudo CIDv1 format
    
    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type from extension and content."""
        suffix = file_path.suffix.lower()
        
        type_mappings = {
            '.json': 'application/json',
            '.parquet': 'application/parquet',
            '.car': 'application/car',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.py': 'text/x-python',
            '.yaml': 'application/yaml',
            '.yml': 'application/yaml',
            '.csv': 'text/csv',
            '.log': 'text/plain'
        }
        
        return type_mappings.get(suffix, 'application/octet-stream')
    
    async def compute_filesystem_hash(self, filesystem_state: Dict[str, Any]) -> str:
        """
        Compute overall filesystem hash using IPFS multiformats.
        Similar to Git's tree hashing but using IPFS CIDs.
        """
        logger.info("Computing filesystem hash...")
        
        # Create deterministic representation of filesystem
        fs_representation = {
            "version": "1.0",
            "files": sorted(filesystem_state["files"], key=lambda x: x["file_path"]),
            "buckets": sorted(filesystem_state["buckets"], key=lambda x: x["name"]),
            "metadata": filesystem_state["metadata"]
        }
        
        # Serialize to JSON with deterministic ordering
        fs_json = json.dumps(fs_representation, sort_keys=True, separators=(',', ':'))
        fs_bytes = fs_json.encode('utf-8')
        
        # Generate IPFS CID for filesystem state
        filesystem_cid = await self._generate_content_cid(fs_bytes)
        
        logger.info(f"Computed filesystem hash: {filesystem_cid}")
        return filesystem_cid
    
    async def has_filesystem_changed(self) -> Tuple[bool, str, str]:
        """
        Check if filesystem has changed since last commit.
        
        Returns:
            Tuple of (has_changed, current_hash, previous_hash)
        """
        logger.info("Checking for filesystem changes...")
        
        # Get current filesystem state
        current_state = await self.scan_filesystem()
        current_hash = await self.compute_filesystem_hash(current_state)
        
        # Get previous HEAD hash
        previous_hash = await self.get_current_head()
        
        # Compare hashes
        has_changed = current_hash != previous_hash
        
        logger.info(f"Filesystem changed: {has_changed} (current: {current_hash[:12]}..., previous: {previous_hash[:12]}...)")
        
        return has_changed, current_hash, previous_hash
    
    async def create_version_snapshot(
        self,
        commit_message: str = "Automated filesystem snapshot",
        author: str = "VFS-Tracker",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new version snapshot of the filesystem.
        
        This is similar to Git commit but creates IPFS CIDs and CAR files.
        """
        logger.info(f"Creating version snapshot: {commit_message}")
        
        try:
            # Check if filesystem has changed
            has_changed, current_hash, previous_hash = await self.has_filesystem_changed()
            
            if not has_changed and not force:
                return create_result_dict(
                    False,
                    message="No changes detected in filesystem",
                    current_version=previous_hash
                )
            
            # Scan current filesystem state
            filesystem_state = await self.scan_filesystem()
            
            # Update filesystem index
            await self._update_filesystem_index(filesystem_state, current_hash)
            
            # Generate CAR file for this version
            car_file_cid = await self._generate_version_car_file(
                filesystem_state, 
                current_hash
            )
            
            # Create version entry
            version_entry = {
                "version_cid": current_hash,
                "parent_cid": previous_hash,
                "commit_message": commit_message,
                "author": author,
                "created_at": datetime.utcnow(),
                "file_count": len(filesystem_state["files"]),
                "total_size": filesystem_state["metadata"]["total_size"],
                "filesystem_tree_cid": current_hash,
                "car_file_cid": car_file_cid,
                "changes_summary": json.dumps(await self._compute_changes_summary(previous_hash, current_hash)),
                "metadata": json.dumps({
                    "buckets": len(filesystem_state["buckets"]),
                    "scanner_version": filesystem_state["metadata"]["scanner_version"]
                })
            }
            
            # Update version log
            await self._update_version_log(version_entry)
            
            # Update HEAD
            await self.set_current_head(current_hash)
            
            # Store version object
            await self._store_version_object(current_hash, version_entry, filesystem_state)
            
            logger.info(f"Created version snapshot: {current_hash}")
            
            return create_result_dict(
                True,
                message=f"Created version snapshot",
                version_cid=current_hash,
                parent_cid=previous_hash,
                car_file_cid=car_file_cid,
                file_count=version_entry["file_count"],
                total_size=version_entry["total_size"]
            )
            
        except Exception as e:
            logger.error(f"Error creating version snapshot: {e}")
            return create_result_dict(False, error=str(e))
    
    async def _update_filesystem_index(self, filesystem_state: Dict[str, Any], version_cid: str):
        """Update the filesystem index with current state."""
        logger.debug("Updating filesystem index...")
        
        if ARROW_AVAILABLE:
            # Prepare data for Parquet
            files_data = []
            for file_info in filesystem_state["files"]:
                file_record = {
                    **file_info,
                    "version_cid": version_cid,
                    "created_at": pd.to_datetime(file_info["created_at"]),
                    "modified_at": pd.to_datetime(file_info["modified_at"])
                }
                files_data.append(file_record)
            
            if files_data:
                # Create Arrow table
                df = pd.DataFrame(files_data)
                table = pa.Table.from_pandas(df)
                
                # Write to Parquet (append mode)
                if self.filesystem_index_file.exists():
                    # Read existing data
                    existing_table = pq.read_table(self.filesystem_index_file)
                    combined_table = pa.concat_tables([existing_table, table])
                    pq.write_table(combined_table, self.filesystem_index_file)
                else:
                    pq.write_table(table, self.filesystem_index_file)
        else:
            # JSON fallback
            index_data = {
                "files": filesystem_state["files"],
                "version_cid": version_cid,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            with open(self.filesystem_index_file.with_suffix('.json'), 'w') as f:
                json.dump(index_data, f, indent=2, default=str)
    
    async def _update_version_log(self, version_entry: Dict[str, Any]):
        """Update the version log with new version entry."""
        logger.debug("Updating version log...")
        
        if ARROW_AVAILABLE:
            # Convert to DataFrame with proper timestamp handling
            df_data = dict(version_entry)
            # Ensure created_at is properly formatted for Arrow
            if isinstance(df_data["created_at"], datetime):
                df_data["created_at"] = pd.to_datetime(df_data["created_at"])
            
            df = pd.DataFrame([df_data])
            table = pa.Table.from_pandas(df)
            
            # Append to existing log
            if self.version_log_file.exists():
                try:
                    existing_table = pq.read_table(self.version_log_file)
                    # Ensure schema compatibility
                    if existing_table.schema.equals(table.schema):
                        combined_table = pa.concat_tables([existing_table, table])
                    else:
                        # Schema mismatch, create new table with updated schema
                        logger.warning("Schema mismatch detected, recreating version log")
                        combined_table = table
                    pq.write_table(combined_table, self.version_log_file)
                except Exception as e:
                    logger.warning(f"Error reading existing version log: {e}")
                    # Create new log file
                    pq.write_table(table, self.version_log_file)
            else:
                pq.write_table(table, self.version_log_file)
        else:
            # JSON fallback
            log_data = {"versions": [version_entry]}
            
            log_file = self.version_log_file.with_suffix('.json')
            if log_file.exists():
                with open(log_file, 'r') as f:
                    existing_log = json.load(f)
                existing_log["versions"].append(version_entry)
                log_data = existing_log
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2, default=str)
    
    async def _generate_version_car_file(
        self, 
        filesystem_state: Dict[str, Any], 
        version_cid: str
    ) -> str:
        """Generate CAR file for version snapshot."""
        logger.debug(f"Generating CAR file for version {version_cid}")
        
        try:
            car_file_path = self.versions_dir / f"{version_cid}.car"
            
            if CAR_BRIDGE_AVAILABLE:
                # Use CAR bridge if available
                car_bridge = ParquetCARBridge()
                
                # Convert filesystem state to Arrow table
                if ARROW_AVAILABLE:
                    df = pd.DataFrame(filesystem_state["files"])
                    table = pa.Table.from_pandas(df)
                    
                    # Export to CAR
                    car_result = await car_bridge.export_table_to_car(
                        table, 
                        str(car_file_path),
                        metadata=filesystem_state["metadata"]
                    )
                    
                    if car_result["success"]:
                        return car_result["data"]["car_cid"]
            
            # Fallback: Manual CAR generation
            car_data = {
                "version": "1.0",
                "filesystem_state": filesystem_state,
                "version_cid": version_cid,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Write JSON representation as CAR
            with open(car_file_path, 'w') as f:
                json.dump(car_data, f, indent=2, default=str)
            
            # Generate CID for CAR file
            with open(car_file_path, 'rb') as f:
                car_content = f.read()
            
            car_cid = await self._generate_content_cid(car_content)
            
            # Rename file to include CID
            final_car_path = self.versions_dir / f"{car_cid}.car"
            car_file_path.rename(final_car_path)
            
            logger.info(f"Generated CAR file: {car_cid}")
            return car_cid
            
        except Exception as e:
            logger.error(f"Error generating CAR file: {e}")
            # Return pseudo-CID as fallback
            return f"bafybei{'0' * 52}"
    
    async def _store_version_object(
        self, 
        version_cid: str, 
        version_entry: Dict[str, Any], 
        filesystem_state: Dict[str, Any]
    ):
        """Store version object in objects directory."""
        try:
            # Create object directory structure (like Git)
            obj_dir = self.objects_dir / version_cid[:2]
            obj_dir.mkdir(exist_ok=True)
            
            obj_file = obj_dir / version_cid[2:]
            
            # Store version object
            version_object = {
                "type": "commit",
                "version_entry": version_entry,
                "filesystem_state": filesystem_state,
                "stored_at": datetime.utcnow().isoformat()
            }
            
            with open(obj_file, 'w') as f:
                json.dump(version_object, f, indent=2, default=str)
            
            logger.debug(f"Stored version object: {version_cid}")
            
        except Exception as e:
            logger.error(f"Error storing version object: {e}")
    
    async def _compute_changes_summary(self, previous_cid: str, current_cid: str) -> Dict[str, Any]:
        """Compute summary of changes between versions."""
        try:
            # For now, return basic summary
            # In full implementation, would compare filesystem states
            return {
                "files_added": 0,
                "files_modified": 0,
                "files_deleted": 0,
                "summary": f"Transition from {previous_cid[:12]} to {current_cid[:12]}"
            }
        except Exception as e:
            logger.error(f"Error computing changes summary: {e}")
            return {"error": str(e)}
    
    async def get_version_history(self, limit: int = 20) -> Dict[str, Any]:
        """Get version history with CID chain."""
        try:
            if ARROW_AVAILABLE and self.version_log_file.exists():
                # Read from Parquet
                table = pq.read_table(self.version_log_file)
                df = table.to_pandas()
                
                # Sort by created_at descending
                df_sorted = df.sort_values('created_at', ascending=False)
                
                # Limit results
                df_limited = df_sorted.head(limit)
                
                versions = df_limited.to_dict('records')
                
            else:
                # JSON fallback
                log_file = self.version_log_file.with_suffix('.json')
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        log_data = json.load(f)
                    versions = sorted(
                        log_data.get("versions", []),
                        key=lambda x: x.get("created_at", ""),
                        reverse=True
                    )[:limit]
                else:
                    versions = []
            
            return create_result_dict(
                True,
                versions=versions,
                total_count=len(versions)
            )
            
        except Exception as e:
            logger.error(f"Error getting version history: {e}")
            return create_result_dict(False, error=str(e))
    
    async def checkout_version(self, version_cid: str) -> Dict[str, Any]:
        """Checkout a specific version (update HEAD pointer)."""
        try:
            logger.info(f"Checking out version: {version_cid}")
            
            # Verify version exists
            version_obj = await self._load_version_object(version_cid)
            if not version_obj:
                return create_result_dict(
                    False,
                    error=f"Version {version_cid} not found"
                )
            
            # Update HEAD
            await self.set_current_head(version_cid)
            
            return create_result_dict(
                True,
                message=f"Checked out version {version_cid}",
                version_cid=version_cid
            )
            
        except Exception as e:
            logger.error(f"Error checking out version: {e}")
            return create_result_dict(False, error=str(e))
    
    async def _load_version_object(self, version_cid: str) -> Optional[Dict[str, Any]]:
        """Load version object from objects directory."""
        try:
            obj_dir = self.objects_dir / version_cid[:2]
            obj_file = obj_dir / version_cid[2:]
            
            if obj_file.exists():
                with open(obj_file, 'r') as f:
                    return json.load(f)
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading version object {version_cid}: {e}")
            return None
    
    async def get_filesystem_status(self) -> Dict[str, Any]:
        """Get current filesystem status and version information."""
        try:
            current_head = await self.get_current_head()
            has_changed, current_hash, _ = await self.has_filesystem_changed()
            
            # Get recent history
            history_result = await self.get_version_history(limit=5)
            recent_versions = history_result.get("versions", [])
            
            return create_result_dict(
                True,
                current_head=current_head,
                current_filesystem_hash=current_hash,
                has_uncommitted_changes=has_changed,
                recent_versions=recent_versions,
                vfs_root=str(self.vfs_root),
                auto_versioning=self.enable_auto_versioning
            )
            
        except Exception as e:
            logger.error(f"Error getting filesystem status: {e}")
            return create_result_dict(False, error=str(e))


# Global VFS version tracker instance
_global_vfs_tracker = None

def get_global_vfs_tracker(
    vfs_root: Optional[str] = None,
    ipfs_client: Optional[Any] = None,
    enable_auto_versioning: bool = True
) -> VFSVersionTracker:
    """Get or create global VFS version tracker instance."""
    global _global_vfs_tracker
    if _global_vfs_tracker is None:
        _global_vfs_tracker = VFSVersionTracker(
            vfs_root=vfs_root,
            ipfs_client=ipfs_client,
            enable_auto_versioning=enable_auto_versioning
        )
    return _global_vfs_tracker


# Utility functions for integration

async def auto_version_filesystem(
    commit_message: str = "Automated versioning",
    force: bool = False
) -> Dict[str, Any]:
    """Automatically version the filesystem if changes are detected."""
    tracker = get_global_vfs_tracker()
    return await tracker.create_version_snapshot(
        commit_message=commit_message,
        force=force
    )

async def get_vfs_status() -> Dict[str, Any]:
    """Get current VFS status and version information."""
    tracker = get_global_vfs_tracker()
    return await tracker.get_filesystem_status()

async def get_vfs_history(limit: int = 20) -> Dict[str, Any]:
    """Get VFS version history."""
    tracker = get_global_vfs_tracker()
    return await tracker.get_version_history(limit=limit)
