#!/usr/bin/env python3
"""
Filesystem Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for filesystem storage (including SSHFS).
"""

import anyio
import json
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import BackendAdapter


class FilesystemBackendAdapter(BackendAdapter):
    """
    Filesystem backend adapter implementing the isomorphic interface.
    Supports local filesystem and SSHFS mounts.
    """
    
    def __init__(self, backend_name: str, config_manager=None):
        """Initialize filesystem backend adapter."""
        super().__init__(backend_name, config_manager)
        
        # Filesystem-specific configuration
        self.storage_path = Path(self.config.get('storage_path', f'/mnt/ipfs_kit_{backend_name}'))
        self.is_sshfs = self.config.get('type') == 'sshfs'
        self.ssh_host = self.config.get('ssh_host', '')
        self.ssh_user = self.config.get('ssh_user', '')
        self.mount_point = self.config.get('mount_point', str(self.storage_path))
        
        # Ensure storage directory structure
        self.pins_dir = self.storage_path / 'pins'
        self.buckets_dir = self.storage_path / 'buckets'
        self.metadata_dir = self.storage_path / 'metadata'
        
        self.logger.info(f"Initialized filesystem adapter for {backend_name} at {self.storage_path}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check filesystem backend health."""
        start_time = time.time()
        
        try:
            # Check if storage path exists and is accessible
            if not self.storage_path.exists():
                self.storage_path.mkdir(parents=True, exist_ok=True)
            
            # Test read/write access
            test_file = self.storage_path / '.health_check'
            test_content = f"health_check_{int(time.time())}"
            
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            with open(test_file, 'r') as f:
                read_content = f.read()
            
            test_file.unlink()  # Clean up
            
            if read_content != test_content:
                raise Exception("Read/write test failed")
            
            # Get storage statistics
            storage_usage = await self._get_storage_usage_internal()
            pin_count = await self._get_pin_count()
            
            # Check sync needs
            needs_pin_sync = await self._check_pin_sync_needed()
            needs_bucket_backup = await self._check_bucket_backup_needed()
            needs_metadata_backup = await self._check_metadata_backup_needed()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'healthy': True,
                'response_time_ms': response_time,
                'error': None,
                'pin_count': pin_count,
                'storage_usage': storage_usage.get('total_usage', 0),
                'needs_pin_sync': needs_pin_sync,
                'needs_bucket_backup': needs_bucket_backup,
                'needs_metadata_backup': needs_metadata_backup,
                'mount_point': str(self.storage_path),
                'available_space': storage_usage.get('available_space', 0)
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'pin_count': 0,
                'storage_usage': 0,
                'needs_pin_sync': False,
                'needs_bucket_backup': False,
                'needs_metadata_backup': False
            }
    
    async def sync_pins(self) -> bool:
        """Synchronize pins with filesystem storage."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            
            # Ensure pins directory exists
            self.pins_dir.mkdir(parents=True, exist_ok=True)
            
            # Get local pin metadata
            local_pins = await self._get_local_pins()
            
            # Get pins already stored in filesystem
            stored_pins = await self._get_stored_pins()
            
            # Find pins that need to be backed up
            local_cids = set(pin['cid'] for pin in local_pins)
            stored_cids = set(pin['cid'] for pin in stored_pins)
            
            missing_in_storage = local_cids - stored_cids
            
            success_count = 0
            total_operations = len(missing_in_storage)
            
            # Copy missing pins to storage
            for cid in missing_in_storage:
                try:
                    pin_info = next(pin for pin in local_pins if pin['cid'] == cid)
                    if await self._backup_pin_to_storage(pin_info):
                        success_count += 1
                        self.logger.debug(f"Backed up pin {cid} to storage")
                    else:
                        self.logger.warning(f"Failed to backup pin {cid}")
                except Exception as e:
                    self.logger.error(f"Error backing up pin {cid}: {e}")
            
            # Update sync metadata
            self._save_metadata('sync', {
                'last_sync': datetime.now().isoformat(),
                'total_operations': total_operations,
                'successful_operations': success_count,
                'missing_in_storage': len(missing_in_storage),
                'total_stored_pins': len(stored_cids) + success_count
            })
            
            self.logger.info(f"Pin sync completed: {success_count}/{total_operations} operations successful")
            return success_count == total_operations
            
        except Exception as e:
            self.logger.error(f"Error during pin sync: {e}")
            return False
    
    async def backup_buckets(self) -> bool:
        """Backup bucket configurations to filesystem."""
        try:
            self.logger.info(f"Starting bucket backup for {self.backend_name}")
            
            # Ensure buckets backup directory exists
            self.buckets_dir.mkdir(parents=True, exist_ok=True)
            
            # Source buckets directory
            source_buckets_dir = self.ipfs_kit_dir / 'buckets'
            if not source_buckets_dir.exists():
                self.logger.warning("No buckets directory found")
                return True
            
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.buckets_dir / f"backup_{timestamp}"
            
            # Copy buckets directory
            shutil.copytree(source_buckets_dir, backup_dir)
            
            # Create backup metadata
            backup_metadata = {
                'timestamp': timestamp,
                'backup_path': str(backup_dir),
                'source_path': str(source_buckets_dir),
                'size': await self._get_directory_size(backup_dir),
                'file_count': len(list(backup_dir.rglob('*'))),
                'checksum': await self._calculate_directory_checksum(backup_dir)
            }
            
            # Update bucket backup metadata
            bucket_backups = self._load_metadata('bucket_backups')
            bucket_backups[timestamp] = backup_metadata
            self._save_metadata('bucket_backups', bucket_backups)
            
            self.logger.info(f"Bucket backup completed: {backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during bucket backup: {e}")
            return False
    
    async def backup_metadata(self) -> bool:
        """Backup IPFS Kit metadata to filesystem."""
        try:
            self.logger.info(f"Starting metadata backup for {self.backend_name}")
            
            # Ensure metadata backup directory exists
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_info = {}
            
            # Backup pin metadata
            pin_metadata_source = self.ipfs_kit_dir / 'pin_metadata'
            if pin_metadata_source.exists():
                pin_metadata_backup = self.metadata_dir / f"pin_metadata_{timestamp}"
                shutil.copytree(pin_metadata_source, pin_metadata_backup)
                backup_info['pin_metadata'] = {
                    'backup_path': str(pin_metadata_backup),
                    'size': await self._get_directory_size(pin_metadata_backup)
                }
            
            # Backup backend index
            backend_index_source = self.ipfs_kit_dir / 'backend_index'
            if backend_index_source.exists():
                backend_index_backup = self.metadata_dir / f"backend_index_{timestamp}"
                shutil.copytree(backend_index_source, backend_index_backup)
                backup_info['backend_index'] = {
                    'backup_path': str(backend_index_backup),
                    'size': await self._get_directory_size(backend_index_backup)
                }
            
            # Backup configuration files
            config_backup_dir = self.metadata_dir / f"config_{timestamp}"
            config_backup_dir.mkdir(exist_ok=True)
            
            for config_file in self.ipfs_kit_dir.glob('*.yaml'):
                if config_file.is_file():
                    shutil.copy2(config_file, config_backup_dir)
            
            backup_info['config'] = {
                'backup_path': str(config_backup_dir),
                'size': await self._get_directory_size(config_backup_dir)
            }
            
            # Save metadata backup record
            metadata_backups = self._load_metadata('metadata_backups')
            metadata_backups[timestamp] = {
                'timestamp': timestamp,
                'backups': backup_info,
                'total_size': sum(info['size'] for info in backup_info.values())
            }
            self._save_metadata('metadata_backups', metadata_backups)
            
            self.logger.info(f"Metadata backup completed: {timestamp}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during metadata backup: {e}")
            return False
    
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """Restore pins from filesystem storage."""
        try:
            stored_pins = await self._get_stored_pins()
            
            if pin_list:
                stored_pins = [p for p in stored_pins if p['cid'] in pin_list]
            
            success_count = 0
            for pin in stored_pins:
                try:
                    await self._restore_pin_from_storage(pin)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Error restoring pin {pin['cid']}: {e}")
            
            self.logger.info(f"Restored {success_count}/{len(stored_pins)} pins")
            return success_count == len(stored_pins)
            
        except Exception as e:
            self.logger.error(f"Error during pin restore: {e}")
            return False
    
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """Restore bucket configurations from filesystem."""
        try:
            bucket_backups = self._load_metadata('bucket_backups')
            if not bucket_backups:
                self.logger.warning("No bucket backups found")
                return False
            
            # Get latest backup
            latest_backup = max(bucket_backups.items(), key=lambda x: x[0])
            backup_path = Path(latest_backup[1]['backup_path'])
            
            if not backup_path.exists():
                self.logger.error(f"Backup path does not exist: {backup_path}")
                return False
            
            # Restore buckets
            target_buckets_dir = self.ipfs_kit_dir / 'buckets'
            if target_buckets_dir.exists():
                # Backup existing buckets
                backup_existing = target_buckets_dir.parent / f"buckets_backup_{int(time.time())}"
                shutil.move(target_buckets_dir, backup_existing)
            
            shutil.copytree(backup_path, target_buckets_dir)
            
            self.logger.info(f"Restored buckets from {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during bucket restore: {e}")
            return False
    
    async def restore_metadata(self) -> bool:
        """Restore metadata from filesystem storage."""
        try:
            metadata_backups = self._load_metadata('metadata_backups')
            if not metadata_backups:
                self.logger.warning("No metadata backups found")
                return False
            
            # Get latest backup
            latest_backup = max(metadata_backups.items(), key=lambda x: x[0])
            backup_info = latest_backup[1]['backups']
            
            success = True
            
            # Restore pin metadata
            if 'pin_metadata' in backup_info:
                backup_path = Path(backup_info['pin_metadata']['backup_path'])
                if backup_path.exists():
                    target_path = self.ipfs_kit_dir / 'pin_metadata'
                    if target_path.exists():
                        shutil.rmtree(target_path)
                    shutil.copytree(backup_path, target_path)
                    self.logger.info("Restored pin metadata")
                else:
                    success = False
            
            # Restore backend index
            if 'backend_index' in backup_info:
                backup_path = Path(backup_info['backend_index']['backup_path'])
                if backup_path.exists():
                    target_path = self.ipfs_kit_dir / 'backend_index'
                    if target_path.exists():
                        shutil.rmtree(target_path)
                    shutil.copytree(backup_path, target_path)
                    self.logger.info("Restored backend index")
                else:
                    success = False
            
            # Restore configuration
            if 'config' in backup_info:
                backup_path = Path(backup_info['config']['backup_path'])
                if backup_path.exists():
                    for config_file in backup_path.glob('*.yaml'):
                        target_file = self.ipfs_kit_dir / config_file.name
                        shutil.copy2(config_file, target_file)
                    self.logger.info("Restored configuration files")
                else:
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during metadata restore: {e}")
            return False
    
    async def list_pins(self) -> List[Dict[str, Any]]:
        """List all pins stored in filesystem."""
        return await self._get_stored_pins()
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List bucket backups in filesystem."""
        bucket_backups = self._load_metadata('bucket_backups')
        return [
            {
                'bucket_name': 'all_buckets',
                'backup_path': info['backup_path'],
                'size': info['size'],
                'created_at': timestamp,
                'checksum': info.get('checksum', '')
            }
            for timestamp, info in bucket_backups.items()
        ]
    
    async def list_metadata_backups(self) -> List[Dict[str, Any]]:
        """List metadata backups in filesystem."""
        metadata_backups = self._load_metadata('metadata_backups')
        return [
            {
                'backup_type': 'metadata',
                'backup_path': f"Multiple: {len(info['backups'])} components",
                'size': info['total_size'],
                'created_at': timestamp,
                'checksum': ''
            }
            for timestamp, info in metadata_backups.items()
        ]
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """Clean up old backups in filesystem."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Clean bucket backups
            bucket_backups = self._load_metadata('bucket_backups')
            cleaned_bucket_backups = {}
            for timestamp, info in bucket_backups.items():
                backup_date = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                if backup_date >= cutoff_date:
                    cleaned_bucket_backups[timestamp] = info
                else:
                    # Remove old backup directory
                    backup_path = Path(info['backup_path'])
                    if backup_path.exists():
                        shutil.rmtree(backup_path)
            
            self._save_metadata('bucket_backups', cleaned_bucket_backups)
            
            # Clean metadata backups
            metadata_backups = self._load_metadata('metadata_backups')
            cleaned_metadata_backups = {}
            for timestamp, info in metadata_backups.items():
                backup_date = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                if backup_date >= cutoff_date:
                    cleaned_metadata_backups[timestamp] = info
                else:
                    # Remove old backup directories
                    for backup_info in info['backups'].values():
                        backup_path = Path(backup_info['backup_path'])
                        if backup_path.exists():
                            shutil.rmtree(backup_path)
            
            self._save_metadata('metadata_backups', cleaned_metadata_backups)
            
            self.logger.info(f"Cleaned up backups older than {retention_days} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during backup cleanup: {e}")
            return False
    
    async def get_storage_usage(self) -> Dict[str, int]:
        """Get filesystem storage usage."""
        return await self._get_storage_usage_internal()
    
    # Filesystem-specific helper methods
    
    async def _get_pin_count(self) -> int:
        """Get number of pins stored in filesystem."""
        try:
            stored_pins = await self._get_stored_pins()
            return len(stored_pins)
        except:
            return 0
    
    async def _get_local_pins(self) -> List[Dict[str, Any]]:
        """Get pins from local metadata."""
        try:
            import pandas as pd
            
            pin_metadata_file = self.pin_metadata_dir / 'pins.parquet'
            if pin_metadata_file.exists():
                df = pd.read_parquet(pin_metadata_file)
                return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"Error getting local pins: {e}")
        
        return []
    
    async def _get_stored_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored in filesystem backend."""
        try:
            stored_pins = []
            
            if not self.pins_dir.exists():
                return stored_pins
            
            # Read pin metadata files
            for pin_file in self.pins_dir.glob('*.json'):
                try:
                    with open(pin_file, 'r') as f:
                        pin_data = json.load(f)
                        stored_pins.append(pin_data)
                except Exception as e:
                    self.logger.error(f"Error reading pin file {pin_file}: {e}")
            
            return stored_pins
            
        except Exception as e:
            self.logger.error(f"Error getting stored pins: {e}")
            return []
    
    async def _backup_pin_to_storage(self, pin_info: Dict[str, Any]) -> bool:
        """Backup a pin to filesystem storage."""
        try:
            cid = pin_info['cid']
            pin_file = self.pins_dir / f"{cid}.json"
            
            # Save pin metadata
            with open(pin_file, 'w') as f:
                json.dump(pin_info, f, indent=2, default=str)
            
            # TODO: Copy actual pin data if available
            # This would require integration with IPFS to fetch the actual content
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error backing up pin to storage: {e}")
            return False
    
    async def _restore_pin_from_storage(self, pin_info: Dict[str, Any]):
        """Restore a pin from filesystem storage to local metadata."""
        try:
            import pandas as pd
            
            pin_metadata_file = self.pin_metadata_dir / 'pins.parquet'
            
            # Create new pin entry
            new_pin = {
                'cid': pin_info['cid'],
                'name': pin_info.get('name', ''),
                'pin_type': pin_info.get('pin_type', 'recursive'),
                'timestamp': pin_info.get('timestamp', datetime.now().timestamp()),
                'size_bytes': pin_info.get('size_bytes', 0),
                'backend': self.backend_name
            }
            
            if pin_metadata_file.exists():
                df = pd.read_parquet(pin_metadata_file)
                # Check if pin already exists
                if not (df['cid'] == pin_info['cid']).any():
                    df = pd.concat([df, pd.DataFrame([new_pin])], ignore_index=True)
                    df.to_parquet(pin_metadata_file, index=False)
            else:
                df = pd.DataFrame([new_pin])
                df.to_parquet(pin_metadata_file, index=False)
                
        except Exception as e:
            self.logger.error(f"Error restoring pin from storage: {e}")
    
    async def _check_pin_sync_needed(self) -> bool:
        """Check if pin synchronization is needed."""
        try:
            local_pins = await self._get_local_pins()
            stored_pins = await self._get_stored_pins()
            
            return len(local_pins) != len(stored_pins)
        except:
            return True
    
    async def _check_bucket_backup_needed(self) -> bool:
        """Check if bucket backup is needed."""
        try:
            # Check if buckets directory has been modified since last backup
            buckets_source = self.ipfs_kit_dir / 'buckets'
            if not buckets_source.exists():
                return False
            
            bucket_backups = self._load_metadata('bucket_backups')
            if not bucket_backups:
                return True
            
            # Get latest backup timestamp
            latest_backup = max(bucket_backups.keys())
            latest_backup_time = datetime.strptime(latest_backup, "%Y%m%d_%H%M%S")
            
            # Check if source has been modified since last backup
            source_mtime = datetime.fromtimestamp(buckets_source.stat().st_mtime)
            
            return source_mtime > latest_backup_time
            
        except:
            return True
    
    async def _check_metadata_backup_needed(self) -> bool:
        """Check if metadata backup is needed."""
        try:
            metadata_backups = self._load_metadata('metadata_backups')
            if not metadata_backups:
                return True
            
            # Check if backup is older than 24 hours
            latest_backup = max(metadata_backups.keys())
            latest_backup_time = datetime.strptime(latest_backup, "%Y%m%d_%H%M%S")
            
            return datetime.now() - latest_backup_time > timedelta(hours=24)
            
        except:
            return True
    
    async def _get_storage_usage_internal(self) -> Dict[str, int]:
        """Get internal storage usage from filesystem."""
        try:
            import shutil
            
            total_usage = 0
            pin_usage = 0
            bucket_backup_usage = 0
            metadata_backup_usage = 0
            
            # Calculate pin storage usage
            if self.pins_dir.exists():
                pin_usage = await self._get_directory_size(self.pins_dir)
            
            # Calculate bucket backup usage
            if self.buckets_dir.exists():
                bucket_backup_usage = await self._get_directory_size(self.buckets_dir)
            
            # Calculate metadata backup usage
            if self.metadata_dir.exists():
                metadata_backup_usage = await self._get_directory_size(self.metadata_dir)
            
            total_usage = pin_usage + bucket_backup_usage + metadata_backup_usage
            
            # Get available space
            available_space = 0
            if self.storage_path.exists():
                statvfs = shutil.disk_usage(self.storage_path)
                available_space = statvfs.free
            
            return {
                'total_usage': total_usage,
                'pin_usage': pin_usage,
                'bucket_backup_usage': bucket_backup_usage,
                'metadata_backup_usage': metadata_backup_usage,
                'available_space': available_space
            }
            
        except Exception as e:
            self.logger.error(f"Error getting storage usage: {e}")
            return {
                'total_usage': 0,
                'pin_usage': 0,
                'bucket_backup_usage': 0,
                'metadata_backup_usage': 0,
                'available_space': 0
            }
    
    async def _get_directory_size(self, directory: Path) -> int:
        """Calculate total size of a directory."""
        try:
            total_size = 0
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            self.logger.error(f"Error calculating directory size: {e}")
            return 0
    
    async def _calculate_directory_checksum(self, directory: Path) -> str:
        """Calculate checksum for all files in a directory."""
        try:
            import hashlib
            
            hash_sha256 = hashlib.sha256()
            
            # Sort files for consistent checksum
            files = sorted(directory.rglob('*'))
            
            for file_path in files:
                if file_path.is_file():
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_sha256.update(chunk)
                    
                    # Include file path in hash for completeness
                    hash_sha256.update(str(file_path.relative_to(directory)).encode())
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Error calculating directory checksum: {e}")
            return ""
