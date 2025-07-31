#!/usr/bin/env python3
"""
IPFS Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for IPFS storage.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .base_adapter import BackendAdapter


class IPFSBackendAdapter(BackendAdapter):
    """
    IPFS backend adapter implementing the isomorphic interface.
    """
    
    def __init__(self, backend_name: str, config_manager=None):
        """Initialize IPFS backend adapter."""
        super().__init__(backend_name, config_manager)
        
        # IPFS-specific configuration
        self.api_url = self.config.get('api_url', 'http://localhost:5001')
        self.gateway_url = self.config.get('gateway_url', 'http://localhost:8080')
        self.timeout = self.config.get('timeout', 30)
        
        self.logger.info(f"Initialized IPFS adapter for {backend_name}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check IPFS node health."""
        start_time = time.time()
        
        try:
            # Check IPFS API
            response = requests.get(
                f"{self.api_url}/api/v0/version",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                version_info = response.json()
                
                # Get pin count
                pin_count = await self._get_pin_count()
                
                # Get storage usage
                storage_usage = await self._get_storage_usage_internal()
                
                # Check if sync is needed
                needs_pin_sync = await self._check_pin_sync_needed()
                
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'error': None,
                    'pin_count': pin_count,
                    'storage_usage': storage_usage.get('total_usage', 0),
                    'needs_pin_sync': needs_pin_sync,
                    'needs_bucket_backup': True,  # Always backup buckets
                    'needs_metadata_backup': True,  # Always backup metadata
                    'version': version_info.get('Version', 'unknown'),
                    'peer_id': await self._get_peer_id()
                }
            else:
                response_time = (time.time() - start_time) * 1000
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'error': f"IPFS API returned status {response.status_code}",
                    'pin_count': 0,
                    'storage_usage': 0,
                    'needs_pin_sync': False,
                    'needs_bucket_backup': False,
                    'needs_metadata_backup': False
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
        """Synchronize pins with IPFS node."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            
            # Get current pins from IPFS
            ipfs_pins = await self._get_ipfs_pins()
            
            # Get local pin metadata
            local_pins = await self._get_local_pins()
            
            # Find pins that need to be added to IPFS
            local_cids = set(pin['cid'] for pin in local_pins)
            ipfs_cids = set(pin['cid'] for pin in ipfs_pins)
            
            missing_in_ipfs = local_cids - ipfs_cids
            missing_locally = ipfs_cids - local_cids
            
            success_count = 0
            total_operations = len(missing_in_ipfs) + len(missing_locally)
            
            # Add missing pins to IPFS
            for cid in missing_in_ipfs:
                try:
                    if await self._pin_to_ipfs(cid):
                        success_count += 1
                        self.logger.debug(f"Pinned {cid} to IPFS")
                    else:
                        self.logger.warning(f"Failed to pin {cid} to IPFS")
                except Exception as e:
                    self.logger.error(f"Error pinning {cid}: {e}")
            
            # Update local metadata for pins found in IPFS
            for cid in missing_locally:
                try:
                    pin_info = next((p for p in ipfs_pins if p['cid'] == cid), None)
                    if pin_info:
                        await self._add_local_pin_metadata(pin_info)
                        success_count += 1
                        self.logger.debug(f"Added local metadata for {cid}")
                except Exception as e:
                    self.logger.error(f"Error adding local metadata for {cid}: {e}")
            
            # Update sync metadata
            self._save_metadata('sync', {
                'last_sync': datetime.now().isoformat(),
                'total_operations': total_operations,
                'successful_operations': success_count,
                'missing_in_ipfs': len(missing_in_ipfs),
                'missing_locally': len(missing_locally)
            })
            
            self.logger.info(f"Pin sync completed: {success_count}/{total_operations} operations successful")
            return success_count == total_operations
            
        except Exception as e:
            self.logger.error(f"Error during pin sync: {e}")
            return False
    
    async def backup_buckets(self) -> bool:
        """Backup bucket configurations to IPFS."""
        try:
            self.logger.info(f"Starting bucket backup for {self.backend_name}")
            
            buckets_dir = self.ipfs_kit_dir / 'buckets'
            if not buckets_dir.exists():
                self.logger.warning("No buckets directory found")
                return True
            
            # Create bucket backup archive
            backup_archive = self._create_backup_archive(buckets_dir, 'buckets')
            if not backup_archive:
                return False
            
            # Add backup to IPFS
            backup_cid = await self._add_file_to_ipfs(backup_archive)
            if not backup_cid:
                return False
            
            # Pin the backup
            if not await self._pin_to_ipfs(backup_cid):
                return False
            
            # Update backup metadata
            bucket_backups = self._load_metadata('bucket_backups')
            bucket_backups[datetime.now().isoformat()] = {
                'cid': backup_cid,
                'archive_path': str(backup_archive),
                'size': backup_archive.stat().st_size,
                'checksum': self._calculate_checksum(backup_archive)
            }
            self._save_metadata('bucket_backups', bucket_backups)
            
            self.logger.info(f"Bucket backup completed: {backup_cid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during bucket backup: {e}")
            return False
    
    async def backup_metadata(self) -> bool:
        """Backup IPFS Kit metadata to IPFS."""
        try:
            self.logger.info(f"Starting metadata backup for {self.backend_name}")
            
            # Backup pin metadata
            pin_metadata_dir = self.ipfs_kit_dir / 'pin_metadata'
            if pin_metadata_dir.exists():
                pin_backup = self._create_backup_archive(pin_metadata_dir, 'pin_metadata')
                if pin_backup:
                    pin_backup_cid = await self._add_file_to_ipfs(pin_backup)
                    if pin_backup_cid:
                        await self._pin_to_ipfs(pin_backup_cid)
            
            # Backup backend index
            backend_index_dir = self.ipfs_kit_dir / 'backend_index'
            if backend_index_dir.exists():
                index_backup = self._create_backup_archive(backend_index_dir, 'backend_index')
                if index_backup:
                    index_backup_cid = await self._add_file_to_ipfs(index_backup)
                    if index_backup_cid:
                        await self._pin_to_ipfs(index_backup_cid)
            
            # Update metadata backup records
            metadata_backups = self._load_metadata('metadata_backups')
            metadata_backups[datetime.now().isoformat()] = {
                'pin_metadata_cid': pin_backup_cid if 'pin_backup_cid' in locals() else None,
                'backend_index_cid': index_backup_cid if 'index_backup_cid' in locals() else None,
                'created_at': datetime.now().isoformat()
            }
            self._save_metadata('metadata_backups', metadata_backups)
            
            self.logger.info("Metadata backup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during metadata backup: {e}")
            return False
    
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """Restore pins from IPFS."""
        try:
            # Get pins from IPFS
            ipfs_pins = await self._get_ipfs_pins()
            
            if pin_list:
                ipfs_pins = [p for p in ipfs_pins if p['cid'] in pin_list]
            
            success_count = 0
            for pin in ipfs_pins:
                try:
                    await self._add_local_pin_metadata(pin)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Error restoring pin {pin['cid']}: {e}")
            
            self.logger.info(f"Restored {success_count}/{len(ipfs_pins)} pins")
            return success_count == len(ipfs_pins)
            
        except Exception as e:
            self.logger.error(f"Error during pin restore: {e}")
            return False
    
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """Restore bucket configurations from IPFS."""
        try:
            bucket_backups = self._load_metadata('bucket_backups')
            if not bucket_backups:
                self.logger.warning("No bucket backups found")
                return False
            
            # Get latest backup
            latest_backup = max(bucket_backups.items(), key=lambda x: x[0])
            backup_cid = latest_backup[1]['cid']
            
            # Download and extract backup
            backup_file = await self._download_from_ipfs(backup_cid)
            if backup_file:
                return await self._extract_backup(backup_file, 'buckets')
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error during bucket restore: {e}")
            return False
    
    async def restore_metadata(self) -> bool:
        """Restore metadata from IPFS."""
        try:
            metadata_backups = self._load_metadata('metadata_backups')
            if not metadata_backups:
                self.logger.warning("No metadata backups found")
                return False
            
            # Get latest backup
            latest_backup = max(metadata_backups.items(), key=lambda x: x[0])
            backup_info = latest_backup[1]
            
            success = True
            
            # Restore pin metadata
            if backup_info.get('pin_metadata_cid'):
                pin_backup_file = await self._download_from_ipfs(backup_info['pin_metadata_cid'])
                if pin_backup_file:
                    success &= await self._extract_backup(pin_backup_file, 'pin_metadata')
            
            # Restore backend index
            if backup_info.get('backend_index_cid'):
                index_backup_file = await self._download_from_ipfs(backup_info['backend_index_cid'])
                if index_backup_file:
                    success &= await self._extract_backup(index_backup_file, 'backend_index')
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during metadata restore: {e}")
            return False
    
    async def list_pins(self) -> List[Dict[str, Any]]:
        """List all pins in IPFS."""
        return await self._get_ipfs_pins()
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List bucket backups in IPFS."""
        bucket_backups = self._load_metadata('bucket_backups')
        return [
            {
                'bucket_name': 'all_buckets',
                'backup_path': info['cid'],
                'size': info['size'],
                'created_at': timestamp,
                'checksum': info['checksum']
            }
            for timestamp, info in bucket_backups.items()
        ]
    
    async def list_metadata_backups(self) -> List[Dict[str, Any]]:
        """List metadata backups in IPFS."""
        metadata_backups = self._load_metadata('metadata_backups')
        return [
            {
                'backup_type': 'metadata',
                'backup_path': f"pin:{info.get('pin_metadata_cid')}, index:{info.get('backend_index_cid')}",
                'size': 0,  # TODO: Get actual sizes
                'created_at': timestamp,
                'checksum': ''  # TODO: Calculate checksums
            }
            for timestamp, info in metadata_backups.items()
        ]
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """Clean up old backups in IPFS."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Clean bucket backups
            bucket_backups = self._load_metadata('bucket_backups')
            cleaned_bucket_backups = {}
            for timestamp, info in bucket_backups.items():
                backup_date = datetime.fromisoformat(timestamp)
                if backup_date >= cutoff_date:
                    cleaned_bucket_backups[timestamp] = info
                else:
                    # Unpin old backup
                    await self._unpin_from_ipfs(info['cid'])
            
            self._save_metadata('bucket_backups', cleaned_bucket_backups)
            
            # Clean metadata backups
            metadata_backups = self._load_metadata('metadata_backups')
            cleaned_metadata_backups = {}
            for timestamp, info in metadata_backups.items():
                backup_date = datetime.fromisoformat(timestamp)
                if backup_date >= cutoff_date:
                    cleaned_metadata_backups[timestamp] = info
                else:
                    # Unpin old backups
                    if info.get('pin_metadata_cid'):
                        await self._unpin_from_ipfs(info['pin_metadata_cid'])
                    if info.get('backend_index_cid'):
                        await self._unpin_from_ipfs(info['backend_index_cid'])
            
            self._save_metadata('metadata_backups', cleaned_metadata_backups)
            
            self.logger.info(f"Cleaned up backups older than {retention_days} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during backup cleanup: {e}")
            return False
    
    async def get_storage_usage(self) -> Dict[str, int]:
        """Get IPFS storage usage."""
        return await self._get_storage_usage_internal()
    
    # IPFS-specific helper methods
    
    async def _get_peer_id(self) -> str:
        """Get IPFS peer ID."""
        try:
            response = requests.get(f"{self.api_url}/api/v0/id", timeout=self.timeout)
            if response.status_code == 200:
                return response.json().get('ID', '')
        except:
            pass
        return ''
    
    async def _get_pin_count(self) -> int:
        """Get number of pins in IPFS."""
        try:
            pins = await self._get_ipfs_pins()
            return len(pins)
        except:
            return 0
    
    async def _get_ipfs_pins(self) -> List[Dict[str, Any]]:
        """Get all pins from IPFS."""
        try:
            response = requests.post(
                f"{self.api_url}/api/v0/pin/ls",
                params={'type': 'all'},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                pins = []
                for cid, info in data.get('Keys', {}).items():
                    pins.append({
                        'cid': cid,
                        'name': info.get('name', ''),
                        'type': info.get('Type', ''),
                        'size': 0  # TODO: Get actual size
                    })
                return pins
        except Exception as e:
            self.logger.error(f"Error getting IPFS pins: {e}")
        
        return []
    
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
    
    async def _pin_to_ipfs(self, cid: str) -> bool:
        """Pin a CID to IPFS."""
        try:
            response = requests.post(
                f"{self.api_url}/api/v0/pin/add",
                params={'arg': cid},
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error pinning {cid}: {e}")
            return False
    
    async def _unpin_from_ipfs(self, cid: str) -> bool:
        """Unpin a CID from IPFS."""
        try:
            response = requests.post(
                f"{self.api_url}/api/v0/pin/rm",
                params={'arg': cid},
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error unpinning {cid}: {e}")
            return False
    
    async def _add_file_to_ipfs(self, file_path: Path) -> Optional[str]:
        """Add a file to IPFS and return its CID."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{self.api_url}/api/v0/add",
                    files=files,
                    timeout=self.timeout
                )
            
            if response.status_code == 200:
                return response.json()['Hash']
        except Exception as e:
            self.logger.error(f"Error adding file to IPFS: {e}")
        
        return None
    
    async def _download_from_ipfs(self, cid: str) -> Optional[Path]:
        """Download a file from IPFS."""
        try:
            response = requests.get(
                f"{self.gateway_url}/ipfs/{cid}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                download_path = self.backend_metadata_dir / f"download_{cid}"
                with open(download_path, 'wb') as f:
                    f.write(response.content)
                return download_path
        except Exception as e:
            self.logger.error(f"Error downloading from IPFS: {e}")
        
        return None
    
    async def _extract_backup(self, backup_file: Path, target_dir: str) -> bool:
        """Extract a backup archive."""
        try:
            import tarfile
            
            target_path = self.ipfs_kit_dir / target_dir
            target_path.mkdir(exist_ok=True)
            
            with tarfile.open(backup_file, 'r:gz') as tar:
                tar.extractall(target_path)
            
            return True
        except Exception as e:
            self.logger.error(f"Error extracting backup: {e}")
            return False
    
    async def _add_local_pin_metadata(self, pin_info: Dict[str, Any]):
        """Add pin metadata to local storage."""
        try:
            import pandas as pd
            
            pin_metadata_file = self.pin_metadata_dir / 'pins.parquet'
            
            # Create new pin entry
            new_pin = {
                'cid': pin_info['cid'],
                'name': pin_info.get('name', ''),
                'pin_type': pin_info.get('type', 'recursive'),
                'timestamp': datetime.now().timestamp(),
                'size_bytes': pin_info.get('size', 0),
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
            self.logger.error(f"Error adding local pin metadata: {e}")
    
    async def _check_pin_sync_needed(self) -> bool:
        """Check if pin synchronization is needed."""
        try:
            # Simple check: compare local and IPFS pin counts
            local_pins = await self._get_local_pins()
            ipfs_pins = await self._get_ipfs_pins()
            
            return len(local_pins) != len(ipfs_pins)
        except:
            return True  # Assume sync needed if check fails
    
    async def _get_storage_usage_internal(self) -> Dict[str, int]:
        """Get internal storage usage from IPFS."""
        try:
            response = requests.post(
                f"{self.api_url}/api/v0/repo/stat",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'total_usage': data.get('RepoSize', 0),
                    'pin_usage': data.get('StorageMax', 0) - data.get('RepoSize', 0),
                    'bucket_backup_usage': 0,  # TODO: Calculate
                    'metadata_backup_usage': 0,  # TODO: Calculate
                    'available_space': data.get('StorageMax', 0) - data.get('RepoSize', 0)
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
