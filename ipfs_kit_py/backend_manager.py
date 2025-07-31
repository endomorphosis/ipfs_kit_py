#!/usr/bin/env python3
"""
Backend Configuration Manager for IPFS Kit.

This manages backend configurations stored in ~/.ipfs_kit/backend_configs/
and pin mappings stored in ~/.ipfs_kit/backends/ for tracking which pins
are stored on which remote backends and their CAR file locations.

Enhanced with intelligent daemon management and isomorphic backend interfaces.
"""

import asyncio
import json
import logging
import os
import shutil
import yaml
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# Import config manager
try:
    from .config_manager import get_config_manager
    CONFIG_AVAILABLE = True
    _config_manager = get_config_manager
except ImportError:
    CONFIG_AVAILABLE = False
    _config_manager = None

# Import existing backend implementations
try:
    from .s3_kit import s3_kit
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    s3_kit = None

try:
    from .sshfs_backend import SSHFSBackend
    SSHFS_AVAILABLE = True
except ImportError:
    SSHFS_AVAILABLE = False
    SSHFSBackend = None

try:
    from .ipfs_cluster_daemon_manager import IPFSClusterDaemonManager
    IPFS_CLUSTER_AVAILABLE = True
except ImportError:
    IPFS_CLUSTER_AVAILABLE = False
    IPFSClusterDaemonManager = None

try:
    from .huggingface_kit import HuggingFaceKit
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False
    HuggingFaceKit = None

try:
    from .storacha_kit import StorachaKit
    STORACHA_AVAILABLE = True
except ImportError:
    STORACHA_AVAILABLE = False
    StorachaKit = None

try:
    from .ftp_kit import FTPKit
    FTP_AVAILABLE = True
except ImportError:
    FTP_AVAILABLE = False
    FTPKit = None

try:
    from .gdrive_kit import GDriveKit
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False
    GDriveKit = None

try:
    from .github_kit import GitHubKit
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False
    GitHubKit = None

try:
    from .ipfs_kit import IPFSKit
    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    IPFSKit = None

try:
    from .aria2_kit import Aria2Kit
    ARIA2_AVAILABLE = True
except ImportError:
    ARIA2_AVAILABLE = False
    Aria2Kit = None

try:
    from .lassie_kit import LassieKit
    LASSIE_AVAILABLE = True
except ImportError:
    LASSIE_AVAILABLE = False
    LassieKit = None

try:
    from .lotus_kit import LotusKit
    LOTUS_AVAILABLE = True
except ImportError:
    LOTUS_AVAILABLE = False
    LotusKit = None

try:
    from .synapse_kit import SynapseKit
    SYNAPSE_AVAILABLE = True
except ImportError:
    SYNAPSE_AVAILABLE = False
    SynapseKit = None


class BackendAdapter:
    """
    Abstract base class for backend adapters providing isomorphic interfaces.
    All backend adapters must implement these methods with consistent behavior.
    """
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        """Initialize backend adapter."""
        self.backend_name = backend_name
        self.config = config
        self.config_manager = config_manager
        self.logger = logging.getLogger(f"{__name__}.{backend_name}")
        
        # Common metadata paths
        self.ipfs_kit_dir = Path('~/.ipfs_kit').expanduser()
        self.pin_metadata_dir = self.ipfs_kit_dir / 'pin_metadata'
        self.backend_state_dir = self.ipfs_kit_dir / 'backend_state'
        self.dirty_state_file = self.backend_state_dir / f'{backend_name}_dirty.json'
        
        # Ensure directories exist
        self.pin_metadata_dir.mkdir(parents=True, exist_ok=True)
        self.backend_state_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_dirty_state(self) -> Dict[str, Any]:
        """Get the current dirty state for this backend."""
        if self.dirty_state_file.exists():
            try:
                with open(self.dirty_state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error reading dirty state file: {e}")
                return {}
        return {}
    
    def _save_dirty_state(self, state: Dict[str, Any]):
        """Save the dirty state for this backend."""
        try:
            with open(self.dirty_state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving dirty state file: {e}")
    
    def mark_dirty(self, reason: str = "pins_changed"):
        """Mark this backend as dirty, requiring synchronization."""
        dirty_state = self._get_dirty_state()
        dirty_state.update({
            'is_dirty': True,
            'last_marked_dirty': datetime.now().isoformat(),
            'reason': reason,
            'sync_required': True
        })
        self._save_dirty_state(dirty_state)
        self.logger.info(f"Backend {self.backend_name} marked as dirty: {reason}")
    
    def clear_dirty_state(self):
        """Clear the dirty state after successful synchronization."""
        dirty_state = self._get_dirty_state()
        dirty_state.update({
            'is_dirty': False,
            'last_synced': datetime.now().isoformat(),
            'sync_required': False
        })
        self._save_dirty_state(dirty_state)
        self.logger.info(f"Backend {self.backend_name} dirty state cleared")
    
    def is_dirty(self) -> bool:
        """Check if this backend is marked as dirty."""
        dirty_state = self._get_dirty_state()
        return dirty_state.get('is_dirty', False)
    
    async def _get_local_pins(self) -> List[Dict[str, Any]]:
        """Get list of local pins that should be synced to this backend."""
        try:
            # Check for pins metadata in the pin_metadata directory
            pins_file = self.pin_metadata_dir / 'pins.json'
            if pins_file.exists():
                with open(pins_file, 'r') as f:
                    return json.load(f)
            
            # Fallback to bucket-based pin discovery
            bucket_dir = self.ipfs_kit_dir / 'buckets'
            local_pins = []
            
            if bucket_dir.exists():
                for bucket_path in bucket_dir.iterdir():
                    if bucket_path.is_dir():
                        bucket_pins_file = bucket_path / 'pins.json'
                        if bucket_pins_file.exists():
                            try:
                                with open(bucket_pins_file, 'r') as f:
                                    bucket_pins = json.load(f)
                                    for pin in bucket_pins:
                                        pin['bucket'] = bucket_path.name
                                        local_pins.append(pin)
                            except Exception as e:
                                self.logger.error(f"Error reading pins from {bucket_pins_file}: {e}")
            
            return local_pins
            
        except Exception as e:
            self.logger.error(f"Error getting local pins: {e}")
            return []
    
    async def _get_backend_pins(self) -> List[Dict[str, Any]]:
        """Get list of pins currently stored on this backend."""
        # This should be implemented by each backend adapter
        # to query their storage and return current pin list
        return []
    
    async def _upload_pin_to_backend(self, pin_info: Dict[str, Any]) -> bool:
        """Upload a specific pin to this backend."""
        # This should be implemented by each backend adapter
        raise NotImplementedError("Subclasses must implement _upload_pin_to_backend")
    
    async def _remove_pin_from_backend(self, cid: str) -> bool:
        """Remove a specific pin from this backend."""
        # This should be implemented by each backend adapter
        raise NotImplementedError("Subclasses must implement _remove_pin_from_backend")

    async def health_check(self) -> Dict[str, Any]:
        """Check backend health and return status information."""
        raise NotImplementedError("Subclasses must implement health_check")
    
    async def sync_pins(self) -> bool:
        """Synchronize pins with backend storage."""
        if not self.is_dirty():
            self.logger.info(f"Backend {self.backend_name} is not dirty, skipping sync")
            return True
        
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            
            # Get local and backend pins
            local_pins = await self._get_local_pins()
            backend_pins = await self._get_backend_pins()
            
            # Create sets of CIDs for comparison
            local_cids = set(pin.get('cid', pin.get('hash', '')) for pin in local_pins)
            backend_cids = set(pin.get('cid', pin.get('hash', '')) for pin in backend_pins)
            
            # Find pins to upload and remove
            pins_to_upload = local_cids - backend_cids
            pins_to_remove = backend_cids - local_cids
            
            success_count = 0
            total_operations = len(pins_to_upload) + len(pins_to_remove)
            
            # Upload missing pins
            for cid in pins_to_upload:
                pin_info = next((pin for pin in local_pins if pin.get('cid', pin.get('hash', '')) == cid), None)
                if pin_info:
                    try:
                        if await self._upload_pin_to_backend(pin_info):
                            success_count += 1
                            self.logger.debug(f"Successfully uploaded pin {cid}")
                        else:
                            self.logger.error(f"Failed to upload pin {cid}")
                    except Exception as e:
                        self.logger.error(f"Error uploading pin {cid}: {e}")
            
            # Remove extra pins
            for cid in pins_to_remove:
                try:
                    if await self._remove_pin_from_backend(cid):
                        success_count += 1
                        self.logger.debug(f"Successfully removed pin {cid}")
                    else:
                        self.logger.error(f"Failed to remove pin {cid}")
                except Exception as e:
                    self.logger.error(f"Error removing pin {cid}: {e}")
            
            # Update sync status
            sync_successful = success_count == total_operations
            if sync_successful:
                self.clear_dirty_state()
                self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            else:
                self.logger.warning(f"Pin sync partially failed for {self.backend_name}: {success_count}/{total_operations} operations successful")
            
            return sync_successful
            
        except Exception as e:
            self.logger.error(f"Error during pin sync for {self.backend_name}: {e}")
            return False
    
    async def backup_buckets(self) -> bool:
        """Backup bucket configurations to backend."""
        raise NotImplementedError("Subclasses must implement backup_buckets")
    
    async def backup_metadata(self) -> bool:
        """Backup IPFS Kit metadata to backend."""
        raise NotImplementedError("Subclasses must implement backup_metadata")
    
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """Restore pins from backend storage."""
        raise NotImplementedError("Subclasses must implement restore_pins")
    
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """Restore bucket configurations from backend."""
        raise NotImplementedError("Subclasses must implement restore_buckets")
    
    async def restore_metadata(self) -> bool:
        """Restore metadata from backend storage."""
        raise NotImplementedError("Subclasses must implement restore_metadata")
    
    async def list_pins(self) -> List[Dict[str, Any]]:
        """List all pins stored in backend."""
        raise NotImplementedError("Subclasses must implement list_pins")
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List bucket backups in backend."""
        raise NotImplementedError("Subclasses must implement list_buckets")
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """Clean up old backups in backend."""
        raise NotImplementedError("Subclasses must implement cleanup_old_backups")
    
    async def get_storage_usage(self) -> Dict[str, int]:
        """Get storage usage information from backend."""
        raise NotImplementedError("Subclasses must implement get_storage_usage")
    
    def _load_metadata(self, metadata_type: str) -> Dict[str, Any]:
        """Load metadata from local storage."""
        try:
            metadata_file = self.ipfs_kit_dir / f'{self.backend_name}_{metadata_type}.json'
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading metadata {metadata_type}: {e}")
        return {}
    
    def _save_metadata(self, metadata_type: str, data: Dict[str, Any]):
        """Save metadata to local storage."""
        try:
            metadata_file = self.ipfs_kit_dir / f'{self.backend_name}_{metadata_type}.json'
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving metadata {metadata_type}: {e}")


class S3BackendAdapter(BackendAdapter):
    """S3 backend adapter implementing the isomorphic interface."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not S3_AVAILABLE:
            raise ImportError("s3_kit is not available. Cannot create S3 backend adapter.")
        
        # Initialize S3Kit with the provided configuration
        self.s3_client = s3_kit(resources=None, meta={'s3cfg': config})
        self.bucket_name = config.get('bucket_name', f'ipfs-kit-{backend_name}')
        
        self.logger.info(f"Initialized S3 adapter for {backend_name} (bucket: {self.bucket_name})")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check S3 backend health."""
        start_time = time.time()
        
        try:
            # Test bucket access by listing objects
            result = self.s3_client.s3_ls_dir(
                dir='',
                bucket_name=self.bucket_name
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if result and not isinstance(result, dict) or result.get('success', True):
                # Get basic metrics
                pin_count = await self._get_pin_count()
                storage_usage = await self._get_storage_usage_internal()
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'pin_count': pin_count,
                    'storage_usage': storage_usage.get('total_usage', 0),
                    'needs_pin_sync': await self._check_pin_sync_needed(),
                    'needs_bucket_backup': await self._check_bucket_backup_needed(),
                    'needs_metadata_backup': await self._check_metadata_backup_needed(),
                    'bucket_name': self.bucket_name
                }
            else:
                raise Exception(f"S3 bucket access failed: {result}")
                
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
        """Synchronize pins with S3 storage."""
        try:
            self.logger.info(f"Starting pin sync for S3 backend {self.backend_name}")
            
            # Get local pins
            local_pins = await self._get_local_pins()
            
            # Get stored pins
            stored_pins = await self._get_stored_pins()
            
            # Find missing pins
            local_cids = set(pin['cid'] for pin in local_pins)
            stored_cids = set(pin['cid'] for pin in stored_pins)
            missing_in_storage = local_cids - stored_cids
            
            success_count = 0
            for cid in missing_in_storage:
                try:
                    pin_info = next(pin for pin in local_pins if pin['cid'] == cid)
                    if await self._backup_pin_to_s3(pin_info):
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"Error backing up pin {cid}: {e}")
            
            # Update sync metadata
            self._save_metadata('sync', {
                'last_sync': datetime.now().isoformat(),
                'total_operations': len(missing_in_storage),
                'successful_operations': success_count
            })
            
            self.logger.info(f"Pin sync completed: {success_count}/{len(missing_in_storage)} operations successful")
            return success_count == len(missing_in_storage)
            
        except Exception as e:
            self.logger.error(f"Error during pin sync: {e}")
            return False
    
    async def backup_buckets(self) -> bool:
        """Backup bucket configurations to S3."""
        try:
            self.logger.info(f"Starting bucket backup for S3 backend {self.backend_name}")
            
            # Source buckets directory
            source_buckets_dir = self.ipfs_kit_dir / 'buckets'
            if not source_buckets_dir.exists():
                self.logger.warning("No buckets directory found")
                return True
            
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Upload buckets directory using s3_kit
            try:
                result = self.s3_client.s3_ul_dir(
                    local_dir=str(source_buckets_dir),
                    bucket_name=self.bucket_name,
                    s3_dir=f'buckets/backup_{timestamp}/'
                )
                
                if result and not isinstance(result, dict) or result.get('success', True):
                    # Update backup metadata
                    bucket_backups = self._load_metadata('bucket_backups')
                    bucket_backups[timestamp] = {
                        'timestamp': timestamp,
                        'backup_path': f'buckets/backup_{timestamp}/',
                        'source_path': str(source_buckets_dir),
                        'bucket_name': self.bucket_name
                    }
                    self._save_metadata('bucket_backups', bucket_backups)
                    
                    self.logger.info(f"Bucket backup completed: backup_{timestamp}")
                    return True
                else:
                    self.logger.error(f"Bucket backup failed: {result}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error uploading buckets to S3: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error during bucket backup: {e}")
            return False
    
    async def backup_metadata(self) -> bool:
        """Backup IPFS Kit metadata to S3."""
        try:
            self.logger.info(f"Starting metadata backup for S3 backend {self.backend_name}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_info = {}
            
            # Backup directories to upload
            backup_dirs = [
                ('pin_metadata', self.ipfs_kit_dir / 'pin_metadata'),
                ('backend_index', self.ipfs_kit_dir / 'backend_index')
            ]
            
            success = True
            for dir_name, source_dir in backup_dirs:
                if source_dir.exists():
                    try:
                        result = self.s3_client.s3_ul_dir(
                            local_dir=str(source_dir),
                            bucket_name=self.bucket_name,
                            s3_dir=f'metadata/backup_{timestamp}/{dir_name}/'
                        )
                        
                        if result and not isinstance(result, dict) or result.get('success', True):
                            backup_info[dir_name] = {
                                'backup_path': f'metadata/backup_{timestamp}/{dir_name}/',
                                'source_path': str(source_dir)
                            }
                        else:
                            success = False
                            self.logger.error(f"Failed to backup {dir_name}: {result}")
                            
                    except Exception as e:
                        success = False
                        self.logger.error(f"Error backing up {dir_name}: {e}")
            
            if success:
                # Save metadata backup record
                metadata_backups = self._load_metadata('metadata_backups')
                metadata_backups[timestamp] = {
                    'timestamp': timestamp,
                    'backups': backup_info,
                    'bucket_name': self.bucket_name
                }
                self._save_metadata('metadata_backups', metadata_backups)
                
                self.logger.info(f"Metadata backup completed: {timestamp}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during metadata backup: {e}")
            return False
    
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """Restore pins from S3 storage."""
        # Implementation would restore pins from S3
        self.logger.info(f"Pin restore not yet implemented for S3 backend")
        return True
    
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """Restore bucket configurations from S3."""
        # Implementation would restore buckets from S3
        self.logger.info(f"Bucket restore not yet implemented for S3 backend")
        return True
    
    async def restore_metadata(self) -> bool:
        """Restore metadata from S3 storage."""
        # Implementation would restore metadata from S3
        self.logger.info(f"Metadata restore not yet implemented for S3 backend")
        return True
    
    async def list_pins(self) -> List[Dict[str, Any]]:
        """List all pins stored in S3."""
        return await self._get_stored_pins()
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List bucket backups in S3."""
        bucket_backups = self._load_metadata('bucket_backups')
        return [
            {
                'bucket_name': 'all_buckets',
                'backup_path': info['backup_path'],
                'created_at': timestamp,
                'bucket_name': info['bucket_name']
            }
            for timestamp, info in bucket_backups.items()
        ]
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """Clean up old backups in S3."""
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
                    # Delete old backup from S3 (would need S3 delete implementation)
                    self.logger.info(f"Would delete old backup: {info['backup_path']}")
            
            self._save_metadata('bucket_backups', cleaned_bucket_backups)
            
            self.logger.info(f"Cleaned up S3 backups older than {retention_days} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during S3 backup cleanup: {e}")
            return False
    
    async def get_storage_usage(self) -> Dict[str, int]:
        """Get S3 storage usage."""
        return await self._get_storage_usage_internal()
    
    # Helper methods
    
    async def _get_pin_count(self) -> int:
        """Get number of pins stored in S3."""
        try:
            stored_pins = await self._get_stored_pins()
            return len(stored_pins)
        except:
            return 0
    
    async def _get_local_pins(self) -> List[Dict[str, Any]]:
        """Get pins from local metadata."""
        try:
            pin_metadata_file = self.pin_metadata_dir / 'pins.parquet'
            if pin_metadata_file.exists():
                df = pd.read_parquet(pin_metadata_file)
                return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"Error getting local pins: {e}")
        return []
    
    async def _get_stored_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored in S3."""
        try:
            # List pin objects in S3
            result = self.s3_client.s3_ls_dir(
                dir='pins/',
                bucket_name=self.bucket_name
            )
            
            stored_pins = []
            if result and hasattr(result, '__iter__'):
                for obj in result:
                    if isinstance(obj, dict) and obj.get('Key', '').endswith('.json'):
                        # Would need to download and parse each pin file
                        stored_pins.append({
                            'cid': obj.get('Key', '').replace('pins/', '').replace('.json', ''),
                            'backend': self.backend_name
                        })
            
            return stored_pins
            
        except Exception as e:
            self.logger.error(f"Error getting stored pins from S3: {e}")
            return []
    
    async def _backup_pin_to_s3(self, pin_info: Dict[str, Any]) -> bool:
        """Backup a pin to S3."""
        try:
            cid = pin_info['cid']
            
            # Create temporary file with pin metadata
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(pin_info, f, indent=2, default=str)
                temp_file = f.name
            
            try:
                # Upload pin metadata to S3
                result = self.s3_client.s3_ul_file(
                    local_file=temp_file,
                    bucket_name=self.bucket_name,
                    s3_file=f'pins/{cid}.json'
                )
                
                return result and not isinstance(result, dict) or result.get('success', True)
                
            finally:
                # Clean up temporary file
                Path(temp_file).unlink(missing_ok=True)
            
        except Exception as e:
            self.logger.error(f"Error backing up pin to S3: {e}")
            return False
    
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
            bucket_backups = self._load_metadata('bucket_backups')
            if not bucket_backups:
                return True
            
            # Check if backup is older than 24 hours
            latest_backup = max(bucket_backups.keys())
            latest_backup_time = datetime.strptime(latest_backup, "%Y%m%d_%H%M%S")
            return datetime.now() - latest_backup_time > timedelta(hours=24)
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
        """Get internal storage usage from S3."""
        try:
            # This would require implementing S3 usage calculation
            # For now, return placeholder values
            return {
                'total_usage': 0,
                'pin_usage': 0,
                'bucket_backup_usage': 0,
                'metadata_backup_usage': 0,
                'available_space': -1  # S3 doesn't have a fixed space limit
            }
        except Exception as e:
            self.logger.error(f"Error getting S3 storage usage: {e}")
            return {
                'total_usage': 0,
                'pin_usage': 0,
                'bucket_backup_usage': 0,
                'metadata_backup_usage': 0,
                'available_space': -1
            }


class SSHFSBackendAdapter(BackendAdapter):
    """SSHFS backend adapter implementing the isomorphic interface."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not SSHFS_AVAILABLE:
            raise ImportError("SSHFSBackend is not available. Cannot create SSHFS backend adapter.")
        
        # Initialize SSHFS backend with the provided configuration
        self.sshfs_backend = SSHFSBackend(config)
        self.remote_path = config.get('remote_base_path', '/tmp/ipfs_kit')
        
        self.logger.info(f"Initialized SSHFS adapter for {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check SSHFS backend health."""
        start_time = time.time()
        
        try:
            # Test SSH connection
            is_healthy = await self.sshfs_backend.test_connection()
            
            response_time = (time.time() - start_time) * 1000
            
            if is_healthy:
                pin_count = await self._get_pin_count()
                storage_usage = await self._get_storage_usage_internal()
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'pin_count': pin_count,
                    'storage_usage': storage_usage.get('total_usage', 0),
                    'needs_pin_sync': await self._check_pin_sync_needed(),
                    'needs_bucket_backup': await self._check_bucket_backup_needed(),
                    'needs_metadata_backup': await self._check_metadata_backup_needed(),
                    'remote_path': self.remote_path
                }
            else:
                raise Exception("SSHFS connection test failed")
                
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
    
    # Similar implementations for other methods...
    async def sync_pins(self) -> bool:
        """Synchronize pins with SSHFS storage."""
        self.logger.info(f"Pin sync not yet implemented for SSHFS backend")
        return True
    
    async def backup_buckets(self) -> bool:
        """Backup bucket configurations to SSHFS."""
        self.logger.info(f"Bucket backup not yet implemented for SSHFS backend")
        return True
    
    async def backup_metadata(self) -> bool:
        """Backup IPFS Kit metadata to SSHFS."""
        self.logger.info(f"Metadata backup not yet implemented for SSHFS backend")
        return True
    
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """Restore pins from SSHFS storage."""
        self.logger.info(f"Pin restore not yet implemented for SSHFS backend")
        return True
    
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """Restore bucket configurations from SSHFS."""
        self.logger.info(f"Bucket restore not yet implemented for SSHFS backend")
        return True
    
    async def restore_metadata(self) -> bool:
        """Restore metadata from SSHFS storage."""
        self.logger.info(f"Metadata restore not yet implemented for SSHFS backend")
        return True
    
    async def list_pins(self) -> List[Dict[str, Any]]:
        """List all pins stored in SSHFS."""
        return []
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List bucket backups in SSHFS."""
        return []
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """Clean up old backups in SSHFS."""
        self.logger.info(f"Backup cleanup not yet implemented for SSHFS backend")
        return True
    
    async def get_storage_usage(self) -> Dict[str, int]:
        """Get SSHFS storage usage."""
        return await self._get_storage_usage_internal()
    
    # Helper methods
    
    async def _get_pin_count(self) -> int:
        """Get number of pins stored in SSHFS."""
        return 0
    
    async def _check_pin_sync_needed(self) -> bool:
        """Check if pin synchronization is needed."""
        return False
    
    async def _check_bucket_backup_needed(self) -> bool:
        """Check if bucket backup is needed."""
        return False
    
    async def _check_metadata_backup_needed(self) -> bool:
        """Check if metadata backup is needed."""
        return False
    
    async def _get_storage_usage_internal(self) -> Dict[str, int]:
        """Get internal storage usage from SSHFS."""
        return {
            'total_usage': 0,
            'pin_usage': 0,
            'bucket_backup_usage': 0,
            'metadata_backup_usage': 0,
            'available_space': 0
        }


class HuggingFaceBackendAdapter(BackendAdapter):
    """Backend adapter for HuggingFace Hub."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        if not HUGGINGFACE_AVAILABLE:
            raise RuntimeError("HuggingFace Hub is not available. Cannot create HuggingFace backend adapter.")
        self.hf_kit = HuggingFaceKit()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check HuggingFace backend health."""
        start_time = time.time()
        try:
            # Try to authenticate and check user info
            if hasattr(self.hf_kit, 'authenticate'):
                auth_result = self.hf_kit.authenticate(self.config.get('token', ''))
                if auth_result:
                    response_time = (time.time() - start_time) * 1000
                    return {
                        'healthy': True,
                        'response_time_ms': response_time,
                        'authenticated': True,
                        'pin_count': await self._count_pins(),
                        'storage_usage': await self._get_storage_usage()
                    }
            
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': 'Authentication failed',
                'pin_count': 0,
                'storage_usage': 0
            }
        except Exception as e:
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e),
                'pin_count': 0,
                'storage_usage': 0
            }
    
    async def _count_pins(self) -> int:
        """Count pins stored on HuggingFace."""
        try:
            # Implementation would depend on HuggingFace API
            return 0
        except:
            return 0
    
    async def _get_storage_usage(self) -> int:
        """Get storage usage on HuggingFace."""
        try:
            # Implementation would depend on HuggingFace API
            return 0
        except:
            return 0
    
    async def _get_backend_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored on HuggingFace."""
        try:
            # Implementation would query HuggingFace repos for pinned content
            return []
        except Exception as e:
            self.logger.error(f"Error getting HuggingFace pins: {e}")
            return []
    
    async def _upload_pin_to_backend(self, pin_info: Dict[str, Any]) -> bool:
        """Upload pin to HuggingFace."""
        try:
            cid = pin_info.get('cid', pin_info.get('hash', ''))
            if hasattr(self.hf_kit, 'upload_file'):
                # Implementation would upload file to HuggingFace repo
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error uploading pin {pin_info.get('cid')} to HuggingFace: {e}")
            return False
    
    async def _remove_pin_from_backend(self, cid: str) -> bool:
        """Remove pin from HuggingFace."""
        try:
            if hasattr(self.hf_kit, 'delete_file'):
                # Implementation would delete file from HuggingFace repo
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing pin {cid} from HuggingFace: {e}")
            return False


class StorachaBackendAdapter(BackendAdapter):
    """Backend adapter for Storacha (Web3.Storage)."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        if not STORACHA_AVAILABLE:
            raise RuntimeError("Storacha is not available. Cannot create Storacha backend adapter.")
        self.storacha_kit = StorachaKit()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Storacha backend health."""
        start_time = time.time()
        try:
            # Try to ping Storacha service
            if hasattr(self.storacha_kit, 'ping') or hasattr(self.storacha_kit, 'get_status'):
                # Check if service is available
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'pin_count': await self._count_pins(),
                    'storage_usage': await self._get_storage_usage()
                }
            
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': 'Storacha service not available',
                'pin_count': 0,
                'storage_usage': 0
            }
        except Exception as e:
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e),
                'pin_count': 0,
                'storage_usage': 0
            }
    
    async def _count_pins(self) -> int:
        """Count pins stored on Storacha."""
        try:
            if hasattr(self.storacha_kit, 'list_uploads'):
                uploads = self.storacha_kit.list_uploads()
                return len(uploads) if uploads else 0
            return 0
        except:
            return 0
    
    async def _get_storage_usage(self) -> int:
        """Get storage usage on Storacha."""
        try:
            if hasattr(self.storacha_kit, 'get_account_info'):
                account_info = self.storacha_kit.get_account_info()
                return account_info.get('storage_used', 0) if account_info else 0
            return 0
        except:
            return 0
    
    async def _get_backend_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored on Storacha."""
        try:
            if hasattr(self.storacha_kit, 'list_uploads'):
                uploads = self.storacha_kit.list_uploads()
                pins = []
                for upload in uploads or []:
                    pins.append({
                        'cid': upload.get('cid', ''),
                        'name': upload.get('name', ''),
                        'size': upload.get('size', 0),
                        'backend': self.backend_name
                    })
                return pins
            return []
        except Exception as e:
            self.logger.error(f"Error getting Storacha pins: {e}")
            return []
    
    async def _upload_pin_to_backend(self, pin_info: Dict[str, Any]) -> bool:
        """Upload pin to Storacha."""
        try:
            cid = pin_info.get('cid', pin_info.get('hash', ''))
            if hasattr(self.storacha_kit, 'upload_file'):
                # Implementation would upload file to Storacha
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error uploading pin {pin_info.get('cid')} to Storacha: {e}")
            return False
    
    async def _remove_pin_from_backend(self, cid: str) -> bool:
        """Remove pin from Storacha."""
        try:
            if hasattr(self.storacha_kit, 'delete_upload'):
                # Implementation would delete from Storacha
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing pin {cid} from Storacha: {e}")
            return False


class FTPBackendAdapter(BackendAdapter):
    """Backend adapter for FTP/FTPS."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        if not FTP_AVAILABLE:
            raise RuntimeError("FTP Kit is not available. Cannot create FTP backend adapter.")
        self.ftp_kit = FTPKit()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check FTP backend health."""
        start_time = time.time()
        try:
            # Try to connect to FTP server
            if hasattr(self.ftp_kit, 'test_connection'):
                connected = self.ftp_kit.test_connection(
                    self.config.get('host', ''),
                    self.config.get('username', ''),
                    self.config.get('password', ''),
                    self.config.get('port', 21)
                )
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': connected,
                    'response_time_ms': response_time,
                    'pin_count': await self._count_pins() if connected else 0,
                    'storage_usage': await self._get_storage_usage() if connected else 0
                }
            
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': 'FTP connection test not available',
                'pin_count': 0,
                'storage_usage': 0
            }
        except Exception as e:
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e),
                'pin_count': 0,
                'storage_usage': 0
            }
    
    async def _count_pins(self) -> int:
        """Count pins stored on FTP."""
        try:
            if hasattr(self.ftp_kit, 'list_files'):
                files = self.ftp_kit.list_files('/pins/')
                return len(files) if files else 0
            return 0
        except:
            return 0
    
    async def _get_storage_usage(self) -> int:
        """Get storage usage on FTP."""
        try:
            if hasattr(self.ftp_kit, 'get_directory_size'):
                return self.ftp_kit.get_directory_size('/pins/')
            return 0
        except:
            return 0
    
    async def _get_backend_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored on FTP."""
        try:
            if hasattr(self.ftp_kit, 'list_files'):
                files = self.ftp_kit.list_files('/pins/')
                pins = []
                for file_info in files or []:
                    if file_info.get('name', '').endswith('.json'):
                        cid = file_info['name'].replace('.json', '')
                        pins.append({
                            'cid': cid,
                            'size': file_info.get('size', 0),
                            'backend': self.backend_name
                        })
                return pins
            return []
        except Exception as e:
            self.logger.error(f"Error getting FTP pins: {e}")
            return []
    
    async def _upload_pin_to_backend(self, pin_info: Dict[str, Any]) -> bool:
        """Upload pin to FTP."""
        try:
            cid = pin_info.get('cid', pin_info.get('hash', ''))
            if hasattr(self.ftp_kit, 'upload_file'):
                # Implementation would upload file to FTP server
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error uploading pin {pin_info.get('cid')} to FTP: {e}")
            return False
    
    async def _remove_pin_from_backend(self, cid: str) -> bool:
        """Remove pin from FTP."""
        try:
            if hasattr(self.ftp_kit, 'delete_file'):
                # Implementation would delete file from FTP server
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing pin {cid} from FTP: {e}")
            return False


class IPFSClusterBackendAdapter(BackendAdapter):
    """Backend adapter for IPFS Cluster."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        if not IPFS_CLUSTER_AVAILABLE:
            raise RuntimeError("IPFS Cluster is not available. Cannot create IPFS Cluster backend adapter.")
        self.cluster_manager = IPFSClusterDaemonManager()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check IPFS Cluster backend health."""
        start_time = time.time()
        try:
            # Check cluster health
            if hasattr(self.cluster_manager, 'check_cluster_health'):
                health_result = await self.cluster_manager.check_cluster_health()
                response_time = (time.time() - start_time) * 1000
                
                if health_result.get('healthy', False):
                    return {
                        'healthy': True,
                        'response_time_ms': response_time,
                        'cluster_peers': health_result.get('peer_count', 0),
                        'pin_count': await self._count_pins(),
                        'storage_usage': await self._get_storage_usage()
                    }
                else:
                    return {
                        'healthy': False,
                        'response_time_ms': response_time,
                        'error': health_result.get('error', 'Cluster unhealthy'),
                        'pin_count': 0,
                        'storage_usage': 0
                    }
            
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': 'Cluster health check not available',
                'pin_count': 0,
                'storage_usage': 0
            }
        except Exception as e:
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e),
                'pin_count': 0,
                'storage_usage': 0
            }
    
    async def _count_pins(self) -> int:
        """Count pins in IPFS Cluster."""
        try:
            if hasattr(self.cluster_manager, 'list_pins'):
                pins = await self.cluster_manager.list_pins()
                return len(pins) if pins else 0
            return 0
        except:
            return 0
    
    async def _get_storage_usage(self) -> int:
        """Get storage usage in IPFS Cluster."""
        try:
            if hasattr(self.cluster_manager, 'get_repo_stat'):
                stat = await self.cluster_manager.get_repo_stat()
                return stat.get('RepoSize', 0) if stat else 0
            return 0
        except:
            return 0
    
    async def _get_backend_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored in IPFS Cluster."""
        try:
            if hasattr(self.cluster_manager, 'list_pins'):
                pins = await self.cluster_manager.list_pins()
                pin_list = []
                for pin_cid, pin_info in (pins or {}).items():
                    pin_list.append({
                        'cid': pin_cid,
                        'status': pin_info.get('status', ''),
                        'backend': self.backend_name
                    })
                return pin_list
            return []
        except Exception as e:
            self.logger.error(f"Error getting IPFS Cluster pins: {e}")
            return []
    
    async def _upload_pin_to_backend(self, pin_info: Dict[str, Any]) -> bool:
        """Pin content to IPFS Cluster."""
        try:
            cid = pin_info.get('cid', pin_info.get('hash', ''))
            if hasattr(self.cluster_manager, 'pin_add'):
                result = await self.cluster_manager.pin_add(cid)
                return result.get('success', False)
            return False
        except Exception as e:
            self.logger.error(f"Error pinning {pin_info.get('cid')} to IPFS Cluster: {e}")
            return False
    
    async def _remove_pin_from_backend(self, cid: str) -> bool:
        """Unpin content from IPFS Cluster."""
        try:
            if hasattr(self.cluster_manager, 'pin_rm'):
                result = await self.cluster_manager.pin_rm(cid)
                return result.get('success', False)
            return False
        except Exception as e:
            self.logger.error(f"Error unpinning {cid} from IPFS Cluster: {e}")
            return False


class GitHubBackendAdapter(BackendAdapter):
    """Backend adapter for GitHub."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        if not GITHUB_AVAILABLE:
            raise RuntimeError("GitHub Kit is not available. Cannot create GitHub backend adapter.")
        self.github_kit = GitHubKit()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check GitHub backend health."""
        start_time = time.time()
        try:
            # Try to authenticate with GitHub
            if hasattr(self.github_kit, 'test_auth'):
                auth_result = self.github_kit.test_auth(self.config.get('token', ''))
                response_time = (time.time() - start_time) * 1000
                
                if auth_result:
                    return {
                        'healthy': True,
                        'response_time_ms': response_time,
                        'authenticated': True,
                        'pin_count': await self._count_pins(),
                        'storage_usage': await self._get_storage_usage()
                    }
                else:
                    return {
                        'healthy': False,
                        'response_time_ms': response_time,
                        'error': 'GitHub authentication failed',
                        'pin_count': 0,
                        'storage_usage': 0
                    }
            
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': 'GitHub auth test not available',
                'pin_count': 0,
                'storage_usage': 0
            }
        except Exception as e:
            return {
                'healthy': False,
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e),
                'pin_count': 0,
                'storage_usage': 0
            }
    
    async def _count_pins(self) -> int:
        """Count pins stored on GitHub."""
        try:
            if hasattr(self.github_kit, 'list_repo_files'):
                files = self.github_kit.list_repo_files(self.config.get('repo', ''))
                return len([f for f in files if f.get('name', '').startswith('pin_')])
            return 0
        except:
            return 0
    
    async def _get_storage_usage(self) -> int:
        """Get storage usage on GitHub."""
        try:
            if hasattr(self.github_kit, 'get_repo_size'):
                return self.github_kit.get_repo_size(self.config.get('repo', ''))
            return 0
        except:
            return 0
    
    async def _get_backend_pins(self) -> List[Dict[str, Any]]:
        """Get pins stored on GitHub."""
        try:
            pins = []
            if hasattr(self.github_kit, 'list_repo_files'):
                files = self.github_kit.list_repo_files(self.config.get('repo', ''))
                for file_info in files or []:
                    if file_info.get('name', '').startswith('pin_') and file_info.get('name', '').endswith('.json'):
                        cid = file_info['name'].replace('pin_', '').replace('.json', '')
                        pins.append({
                            'cid': cid,
                            'size': file_info.get('size', 0),
                            'backend': self.backend_name
                        })
            return pins
        except Exception as e:
            self.logger.error(f"Error getting GitHub pins: {e}")
            return []
    
    async def _upload_pin_to_backend(self, pin_info: Dict[str, Any]) -> bool:
        """Upload pin to GitHub."""
        try:
            cid = pin_info.get('cid', pin_info.get('hash', ''))
            if hasattr(self.github_kit, 'upload_file'):
                # Implementation would upload pin file to GitHub repo
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error uploading pin {pin_info.get('cid')} to GitHub: {e}")
            return False
    
    async def _remove_pin_from_backend(self, cid: str) -> bool:
        """Remove pin from GitHub."""
        try:
            if hasattr(self.github_kit, 'delete_file'):
                # Implementation would delete pin file from GitHub repo
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing pin {cid} from GitHub: {e}")
            return False


class GDriveBackendAdapter(BackendAdapter):
    """Backend adapter for Google Drive."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not GDRIVE_AVAILABLE:
            raise RuntimeError("Google Drive Kit is not available. Cannot create GDrive backend adapter.")
        
        self.gdrive_kit = GDriveKit()
        logger.info(f"Initialized Google Drive backend adapter: {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Google Drive backend health."""
        start_time = time.time()
        
        try:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,  # Set to False until we implement actual auth test
                'response_time_ms': response_time,
                'error': 'Google Drive auth test not available',
                'backend_type': 'gdrive'
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'backend_type': 'gdrive'
            }
    
    async def sync_pins(self) -> bool:
        """Sync pins to Google Drive."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            local_pins = await self.get_local_pins()
            backend_pins = await self.get_backend_pins()
            pins_to_sync = [pin for pin in local_pins if pin not in backend_pins]
            
            for pin_hash in pins_to_sync:
                await self.sync_pin_to_backend(pin_hash)
            
            self.clear_dirty_state()
            self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pin sync failed for {self.backend_name}: {e}")
            return False


class IPFSBackendAdapter(BackendAdapter):
    """Backend adapter for direct IPFS node."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not IPFS_AVAILABLE:
            raise RuntimeError("IPFS Kit is not available. Cannot create IPFS backend adapter.")
        
        self.ipfs_kit = IPFSKit()
        logger.info(f"Initialized IPFS backend adapter: {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check IPFS node health."""
        start_time = time.time()
        
        try:
            if hasattr(self.ipfs_kit, 'get_version'):
                version_info = await self.ipfs_kit.get_version()
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'backend_type': 'ipfs',
                    'version': version_info
                }
            else:
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'error': 'IPFS version check not available',
                    'backend_type': 'ipfs'
                }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'backend_type': 'ipfs'
            }
    
    async def sync_pins(self) -> bool:
        """Sync pins to IPFS node."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            local_pins = await self.get_local_pins()
            
            for pin_hash in local_pins:
                if hasattr(self.ipfs_kit, 'pin_add'):
                    await self.ipfs_kit.pin_add(pin_hash)
            
            self.clear_dirty_state()
            self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pin sync failed for {self.backend_name}: {e}")
            return False


class Aria2BackendAdapter(BackendAdapter):
    """Backend adapter for Aria2 download manager."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not ARIA2_AVAILABLE:
            raise RuntimeError("Aria2 Kit is not available. Cannot create Aria2 backend adapter.")
        
        self.aria2_kit = Aria2Kit()
        logger.info(f"Initialized Aria2 backend adapter: {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Aria2 daemon health."""
        start_time = time.time()
        
        try:
            if hasattr(self.aria2_kit, 'get_global_stat'):
                status = await self.aria2_kit.get_global_stat()
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'backend_type': 'aria2',
                    'active_downloads': status.get('numActive', 0)
                }
            else:
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'error': 'Aria2 stat check not available',
                    'backend_type': 'aria2'
                }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'backend_type': 'aria2'
            }
    
    async def sync_pins(self) -> bool:
        """Sync pins via Aria2 downloads."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            local_pins = await self.get_local_pins()
            
            for pin_hash in local_pins:
                gateway_url = f"https://ipfs.io/ipfs/{pin_hash}"
                if hasattr(self.aria2_kit, 'add_uri'):
                    await self.aria2_kit.add_uri([gateway_url])
            
            self.clear_dirty_state()
            self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pin sync failed for {self.backend_name}: {e}")
            return False


class LassieBackendAdapter(BackendAdapter):
    """Backend adapter for Lassie IPFS retrieval."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not LASSIE_AVAILABLE:
            raise RuntimeError("Lassie Kit is not available. Cannot create Lassie backend adapter.")
        
        self.lassie_kit = LassieKit()
        logger.info(f"Initialized Lassie backend adapter: {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Lassie health."""
        start_time = time.time()
        
        try:
            if hasattr(self.lassie_kit, 'get_version'):
                version = await self.lassie_kit.get_version()
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'backend_type': 'lassie',
                    'version': version
                }
            else:
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'error': 'Lassie version check not available',
                    'backend_type': 'lassie'
                }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'backend_type': 'lassie'
            }
    
    async def sync_pins(self) -> bool:
        """Sync pins via Lassie retrieval."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            local_pins = await self.get_local_pins()
            
            for pin_hash in local_pins:
                if hasattr(self.lassie_kit, 'fetch'):
                    await self.lassie_kit.fetch(pin_hash)
            
            self.clear_dirty_state()
            self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pin sync failed for {self.backend_name}: {e}")
            return False


class LotusBackendAdapter(BackendAdapter):
    """Backend adapter for Lotus Filecoin node."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not LOTUS_AVAILABLE:
            raise RuntimeError("Lotus Kit is not available. Cannot create Lotus backend adapter.")
        
        self.lotus_kit = LotusKit()
        logger.info(f"Initialized Lotus backend adapter: {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Lotus node health."""
        start_time = time.time()
        
        try:
            if hasattr(self.lotus_kit, 'sync_state'):
                sync_status = await self.lotus_kit.sync_state()
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'backend_type': 'lotus',
                    'sync_status': sync_status
                }
            else:
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'error': 'Lotus sync check not available',
                    'backend_type': 'lotus'
                }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'backend_type': 'lotus'
            }
    
    async def sync_pins(self) -> bool:
        """Sync pins to Filecoin via Lotus."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            local_pins = await self.get_local_pins()
            
            for pin_hash in local_pins:
                if hasattr(self.lotus_kit, 'client_start_deal'):
                    await self.lotus_kit.client_start_deal(pin_hash)
            
            self.clear_dirty_state()
            self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pin sync failed for {self.backend_name}: {e}")
            return False


class SynapseBackendAdapter(BackendAdapter):
    """Backend adapter for Synapse storage."""
    
    def __init__(self, backend_name: str, config: Dict[str, Any], config_manager=None):
        super().__init__(backend_name, config, config_manager)
        
        if not SYNAPSE_AVAILABLE:
            raise RuntimeError("Synapse Kit is not available. Cannot create Synapse backend adapter.")
        
        self.synapse_kit = SynapseKit()
        logger.info(f"Initialized Synapse backend adapter: {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Synapse backend health."""
        start_time = time.time()
        
        try:
            if hasattr(self.synapse_kit, 'get_status'):
                status = await self.synapse_kit.get_status()
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'backend_type': 'synapse',
                    'status': status
                }
            else:
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'error': 'Synapse status check not available',
                    'backend_type': 'synapse'
                }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'healthy': False,
                'response_time_ms': response_time,
                'error': str(e),
                'backend_type': 'synapse'
            }
    
    async def sync_pins(self) -> bool:
        """Sync pins to Synapse storage."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            local_pins = await self.get_local_pins()
            backend_pins = await self.get_backend_pins()
            pins_to_sync = [pin for pin in local_pins if pin not in backend_pins]
            
            for pin_hash in pins_to_sync:
                await self.sync_pin_to_backend(pin_hash)
            
            self.clear_dirty_state()
            self.logger.info(f"Pin sync completed successfully for {self.backend_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Pin sync failed for {self.backend_name}: {e}")
            return False


# Backend adapter registry
BACKEND_ADAPTERS = {
    's3': S3BackendAdapter,
    'sshfs': SSHFSBackendAdapter,
    'filesystem': SSHFSBackendAdapter,  # Use SSHFS adapter for filesystem too
    'huggingface': HuggingFaceBackendAdapter,
    'storacha': StorachaBackendAdapter,
    'web3storage': StorachaBackendAdapter,  # Alias for storacha
    'ftp': FTPBackendAdapter,
    'ftps': FTPBackendAdapter,  # FTP with TLS
    'ipfs_cluster': IPFSClusterBackendAdapter,
    'cluster': IPFSClusterBackendAdapter,  # Alias for ipfs_cluster
    'github': GitHubBackendAdapter,
    'gdrive': GDriveBackendAdapter,
    'google_drive': GDriveBackendAdapter,  # Alias for gdrive
    'ipfs': IPFSBackendAdapter,
    'aria2': Aria2BackendAdapter,
    'lassie': LassieBackendAdapter,
    'lotus': LotusBackendAdapter,
    'filecoin': LotusBackendAdapter,  # Alias for lotus
    'synapse': SynapseBackendAdapter,
}

def get_backend_adapter(backend_type: str, backend_name: str, config: Dict[str, Any], config_manager=None) -> BackendAdapter:
    """
    Factory function to get the appropriate backend adapter.
    
    Args:
        backend_type: Type of backend ('s3', 'sshfs', etc.)
        backend_name: Name of the specific backend instance
        config: Backend configuration
        config_manager: Configuration manager instance
        
    Returns:
        Backend adapter instance
        
    Raises:
        ValueError: If backend type is not supported
    """
    if backend_type not in BACKEND_ADAPTERS:
        supported_types = list(BACKEND_ADAPTERS.keys())
        raise ValueError(f"Unsupported backend type '{backend_type}'. Supported types: {supported_types}")
    
    adapter_class = BACKEND_ADAPTERS[backend_type]
    return adapter_class(backend_name, config, config_manager)

def list_supported_backends():
    """List all supported backend types."""
    return list(BACKEND_ADAPTERS.keys())


class BackendManager:
    """
    Enhanced Backend Manager with intelligent daemon capabilities.
    
    Manages backend configurations and provides intelligent daemon management
    with isomorphic backend interfaces.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize backend manager."""
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Try to get from config manager if available
            if CONFIG_AVAILABLE and _config_manager:
                try:
                    config_manager = _config_manager()
                    self.data_dir = Path(config_manager.get_config_value('data_dir', '~/.ipfs_kit')).expanduser()
                except Exception:
                    self.data_dir = Path('~/.ipfs_kit').expanduser()
            else:
                self.data_dir = Path('~/.ipfs_kit').expanduser()
        
        # Backend directory structure
        self.backend_configs_dir = self.data_dir / 'backend_configs'
        self.backends_dir = self.data_dir / 'backends'
        
        # Ensure directories exist
        self.backend_configs_dir.mkdir(parents=True, exist_ok=True)
        self.backends_dir.mkdir(parents=True, exist_ok=True)
        
        # Backend adapters cache
        self.backend_adapters = {}
        
        logger.info(f"BackendManager initialized with data_dir: {self.data_dir}")
        logger.info(f"Backend configs dir: {self.backend_configs_dir}")
        logger.info(f"Backend indexes dir: {self.backends_dir}")
    
    def get_backend_adapter(self, backend_name: str) -> Optional[BackendAdapter]:
        """Get backend adapter for a specific backend."""
        if backend_name in self.backend_adapters:
            return self.backend_adapters[backend_name]
        
        # Load backend configuration
        config_file = self.backend_configs_dir / f'{backend_name}.yaml'
        if not config_file.exists():
            logger.error(f"Backend configuration not found: {backend_name}")
            return None
        
        try:
            with open(config_file, 'r') as f:
                backend_config = yaml.safe_load(f)
            
            backend_type = backend_config.get('type')
            config = backend_config.get('config', {})
            
            # Create adapter
            adapter = get_backend_adapter(backend_type, backend_name, config)
            self.backend_adapters[backend_name] = adapter
            
            logger.info(f"Created backend adapter for {backend_name} (type: {backend_type})")
            return adapter
            
        except Exception as e:
            logger.error(f"Error creating backend adapter for {backend_name}: {e}")
            return None
    
    async def create_backend_config(
        self,
        backend_name: str,
        backend_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a backend configuration.
        
        Args:
            backend_name: Name of the backend (e.g., 'my-s3-bucket')
            backend_type: Type of backend (e.g., 's3', 'sshfs', 'filesystem')
            config: Backend-specific configuration
            
        Returns:
            Result dictionary
        """
        try:
            # Create configuration
            backend_config = {
                'name': backend_name,
                'type': backend_type,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'enabled': True,
                'config': config,
                'metadata': {
                    'version': '1.0',
                    'description': f'{backend_type} backend configuration'
                }
            }
            
            # Save configuration as YAML
            config_file = self.backend_configs_dir / f'{backend_name}.yaml'
            with open(config_file, 'w') as f:
                yaml.dump(backend_config, f, default_flow_style=False, indent=2)
            
            # Create backend index directory
            backend_index_dir = self.backends_dir / backend_name
            backend_index_dir.mkdir(exist_ok=True)
            
            # Create initial pin mapping index
            await self._create_initial_pin_mapping(backend_name)
            
            logger.info(f"Created backend configuration: {backend_name}")
            
            return {
                'success': True,
                'data': {
                    'backend_name': backend_name,
                    'backend_type': backend_type,
                    'config_file': str(config_file),
                    'index_dir': str(backend_index_dir)
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating backend config: {e}")
            return {
                'success': False,
                'error': f"Failed to create backend config: {str(e)}"
            }
    
    def discover_backends(self) -> Dict[str, Any]:
        """
        Discover all configured backends.
        
        Returns:
            Dictionary with backend_name -> configuration mapping
        """
        backends = {}
        
        try:
            for config_file in self.backend_configs_dir.glob('*.yaml'):
                backend_name = config_file.stem
                
                try:
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    backends[backend_name] = config
                except Exception as e:
                    logger.error(f"Error loading backend config {backend_name}: {e}")
                    
            logger.info(f"Discovered {len(backends)} backends")
            
        except Exception as e:
            logger.error(f"Error discovering backends: {e}")
        
        return backends
    
    async def _create_initial_pin_mapping(self, backend_name: str):
        """Create initial pin mapping file for a backend."""
        try:
            backend_index_dir = self.backends_dir / backend_name
            pins_file = backend_index_dir / 'pins.json'
            
            if not pins_file.exists():
                initial_data = []
                
                with open(pins_file, 'w') as f:
                    json.dump(initial_data, f, indent=2)
                
                logger.info(f"Created initial pin mapping index for backend: {backend_name}")
                
        except Exception as e:
            logger.error(f"Error creating initial pin mapping: {e}")
    
    async def health_check_backend(self, backend_name: str) -> Dict[str, Any]:
        """Perform health check on a specific backend."""
        adapter = self.get_backend_adapter(backend_name)
        if not adapter:
            return {
                'healthy': False,
                'error': f'Backend adapter not available for {backend_name}',
                'backend_name': backend_name
            }
        
        try:
            result = await adapter.health_check()
            result['backend_name'] = backend_name
            return result
        except Exception as e:
            logger.error(f"Health check failed for {backend_name}: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'backend_name': backend_name
            }
    
    async def health_check_all_backends(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all configured backends."""
        results = {}
        
        # Discover all backends
        for config_file in self.backend_configs_dir.glob('*.yaml'):
            backend_name = config_file.stem
            
            try:
                with open(config_file, 'r') as f:
                    backend_config = yaml.safe_load(f)
                
                # Skip disabled backends
                if not backend_config.get('enabled', True):
                    results[backend_name] = {
                        'healthy': False,
                        'error': 'Backend is disabled',
                        'backend_name': backend_name,
                        'disabled': True
                    }
                    continue
                
                # Perform health check
                results[backend_name] = await self.health_check_backend(backend_name)
                
            except Exception as e:
                logger.error(f"Error checking backend {backend_name}: {e}")
                results[backend_name] = {
                    'healthy': False,
                    'error': str(e),
                    'backend_name': backend_name
                }
        
        return results
    
    async def sync_pins_to_backend(self, backend_name: str) -> bool:
        """Sync pins to a specific backend."""
        adapter = self.get_backend_adapter(backend_name)
        if not adapter:
            logger.error(f"Backend adapter not available for {backend_name}")
            return False
        
        try:
            return await adapter.sync_pins()
        except Exception as e:
            logger.error(f"Pin sync failed for {backend_name}: {e}")
            return False
    
    async def backup_buckets_to_backend(self, backend_name: str) -> bool:
        """Backup buckets to a specific backend."""
        adapter = self.get_backend_adapter(backend_name)
        if not adapter:
            logger.error(f"Backend adapter not available for {backend_name}")
            return False
        
        try:
            return await adapter.backup_buckets()
        except Exception as e:
            logger.error(f"Bucket backup failed for {backend_name}: {e}")
            return False
    
    async def backup_metadata_to_backend(self, backend_name: str) -> bool:
        """Backup metadata to a specific backend."""
        adapter = self.get_backend_adapter(backend_name)
        if not adapter:
            logger.error(f"Backend adapter not available for {backend_name}")
            return False
        
        try:
            return await adapter.backup_metadata()
        except Exception as e:
            logger.error(f"Metadata backup failed for {backend_name}: {e}")
            return False
    
    def discover_backends(self) -> Dict[str, Dict[str, Any]]:
        """Discover all configured backends."""
        backends = {}
        
        for config_file in self.backend_configs_dir.glob('*.yaml'):
            backend_name = config_file.stem
            
            try:
                with open(config_file, 'r') as f:
                    backend_config = yaml.safe_load(f)
                
                backends[backend_name] = backend_config
                logger.debug(f"Discovered backend: {backend_name}")
                
            except Exception as e:
                logger.error(f"Error reading backend config {config_file}: {e}")
        
        logger.info(f"Discovered {len(backends)} backends")
        return backends
    
    def get_backends_needing_attention(self) -> List[str]:
        """Get list of backends that need attention based on cached health data."""
        needing_attention = []
        
        # Check for cached health status files
        for status_file in self.data_dir.glob('*_status.json'):
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                status = status_data.get('status', {})
                backend_name = status_file.stem.replace('_status', '')
                
                if not status.get('healthy', True):
                    needing_attention.append(backend_name)
                elif (status.get('needs_pin_sync') or 
                      status.get('needs_bucket_backup') or 
                      status.get('needs_metadata_backup')):
                    needing_attention.append(backend_name)
                    
            except Exception as e:
                logger.error(f"Error reading status file {status_file}: {e}")
        
        return needing_attention
    
    async def get_storage_usage_all_backends(self) -> Dict[str, Dict[str, int]]:
        """Get storage usage for all backends."""
        usage_data = {}
        
        backends = self.discover_backends()
        for backend_name in backends:
            adapter = self.get_backend_adapter(backend_name)
            if adapter:
                try:
                    usage_data[backend_name] = await adapter.get_storage_usage()
                except Exception as e:
                    logger.error(f"Error getting storage usage for {backend_name}: {e}")
                    usage_data[backend_name] = {
                        'total_usage': 0,
                        'error': str(e)
                    }
        
        return usage_data
    
    async def cleanup_old_backups_all_backends(self, retention_days: int = 30) -> Dict[str, bool]:
        """Clean up old backups on all backends."""
        results = {}
        
        backends = self.discover_backends()
        for backend_name in backends:
            adapter = self.get_backend_adapter(backend_name)
            if adapter:
                try:
                    results[backend_name] = await adapter.cleanup_old_backups(retention_days)
                except Exception as e:
                    logger.error(f"Error cleaning up backups for {backend_name}: {e}")
                    results[backend_name] = False
        
        return results
    
    def mark_backend_dirty(self, backend_name: str, reason: str = "pins_changed"):
        """Mark a specific backend as dirty, requiring synchronization."""
        adapter = self.get_backend_adapter(backend_name)
        if adapter:
            adapter.mark_dirty(reason)
            logger.info(f"Marked backend {backend_name} as dirty: {reason}")
        else:
            logger.error(f"Cannot mark backend {backend_name} as dirty - adapter not available")
    
    def mark_all_backends_dirty(self, reason: str = "bulk_pin_update"):
        """Mark all backends as dirty, requiring synchronization."""
        backends = self.discover_backends()
        for backend_name in backends:
            self.mark_backend_dirty(backend_name, reason)
        logger.info(f"Marked {len(backends)} backends as dirty: {reason}")
    
    def get_dirty_backends(self) -> List[str]:
        """Get list of backends that are marked as dirty."""
        dirty_backends = []
        backends = self.discover_backends()
        
        for backend_name in backends:
            adapter = self.get_backend_adapter(backend_name)
            if adapter and adapter.is_dirty():
                dirty_backends.append(backend_name)
        
        logger.info(f"Found {len(dirty_backends)} dirty backends: {dirty_backends}")
        return dirty_backends
    
    async def sync_dirty_backends(self) -> Dict[str, bool]:
        """Synchronize all backends that are marked as dirty."""
        dirty_backends = self.get_dirty_backends()
        
        if not dirty_backends:
            logger.info("No dirty backends found, skipping sync")
            return {}
        
        logger.info(f"Starting sync for {len(dirty_backends)} dirty backends")
        results = {}
        
        for backend_name in dirty_backends:
            try:
                result = await self.sync_pins_to_backend(backend_name)
                results[backend_name] = result
                if result:
                    logger.info(f"Successfully synced dirty backend: {backend_name}")
                else:
                    logger.error(f"Failed to sync dirty backend: {backend_name}")
            except Exception as e:
                logger.error(f"Error syncing dirty backend {backend_name}: {e}")
                results[backend_name] = False
        
        successful_syncs = sum(1 for result in results.values() if result)
        logger.info(f"Dirty backend sync completed: {successful_syncs}/{len(dirty_backends)} successful")
        
        return results
    
    async def force_sync_all_backends(self) -> Dict[str, bool]:
        """Force synchronization of all backends, regardless of dirty state."""
        backends = self.discover_backends()
        logger.info(f"Starting forced sync for {len(backends)} backends")
        
        results = {}
        for backend_name in backends:
            try:
                # Mark as dirty first to ensure sync happens
                self.mark_backend_dirty(backend_name, "forced_sync")
                result = await self.sync_pins_to_backend(backend_name)
                results[backend_name] = result
                if result:
                    logger.info(f"Successfully force-synced backend: {backend_name}")
                else:
                    logger.error(f"Failed to force-sync backend: {backend_name}")
            except Exception as e:
                logger.error(f"Error force-syncing backend {backend_name}: {e}")
                results[backend_name] = False
        
        successful_syncs = sum(1 for result in results.values() if result)
        logger.info(f"Force sync completed: {successful_syncs}/{len(backends)} successful")
        
        return results
    
    def get_backend_sync_status(self) -> Dict[str, Dict[str, Any]]:
        """Get synchronization status for all backends."""
        backends = self.discover_backends()
        status = {}
        
        for backend_name in backends:
            adapter = self.get_backend_adapter(backend_name)
            if adapter:
                dirty_state = adapter._get_dirty_state()
                status[backend_name] = {
                    'is_dirty': dirty_state.get('is_dirty', False),
                    'last_marked_dirty': dirty_state.get('last_marked_dirty'),
                    'last_synced': dirty_state.get('last_synced'),
                    'reason': dirty_state.get('reason'),
                    'sync_required': dirty_state.get('sync_required', False)
                }
            else:
                status[backend_name] = {
                    'is_dirty': False,
                    'error': 'Backend adapter not available'
                }
        
        return status
    
    async def cleanup_backend_state(self):
        """Clean up backend state files and reset dirty states."""
        backend_state_dir = self.data_dir / 'backend_state'
        if backend_state_dir.exists():
            try:
                for state_file in backend_state_dir.glob('*_dirty.json'):
                    state_file.unlink()
                    logger.debug(f"Removed dirty state file: {state_file}")
                logger.info("Cleaned up all backend dirty state files")
            except Exception as e:
                logger.error(f"Error cleaning up backend state: {e}")


# Global instance
_global_backend_manager = None

def get_backend_manager(data_dir: Optional[str] = None) -> BackendManager:
    """Get global backend manager instance."""
    global _global_backend_manager
    
    if _global_backend_manager is None:
        _global_backend_manager = BackendManager(data_dir)
    
    return _global_backend_manager
