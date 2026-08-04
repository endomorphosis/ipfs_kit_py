#!/usr/bin/env python3
"""
IPFS Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for IPFS storage.
"""

import anyio
import hashlib
import json
import logging
import re
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
    
    SERVICE_OPERATIONS = frozenset({"add", "cat", "range", "pin", "unpin", "list-pins"})

    def __init__(self, backend_name: str = "ipfs", config_manager=None, *, http_client=None):
        """Construct without touching the API, filesystem, or a gateway."""
        self.backend_name = backend_name
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__).getChild(f"{self.__class__.__name__}.{backend_name}")
        # BackendAdapter.__init__ persists metadata.  Service adapters must be inert.
        self.ipfs_kit_dir = Path.home() / '.ipfs_kit'
        self.backend_metadata_dir = self.ipfs_kit_dir / 'backends' / backend_name
        self.pin_metadata_dir = self.ipfs_kit_dir / 'pins'
        self.config = self._load_backend_config_inert()
        
        # IPFS-specific configuration
        self.api_url = self.config.get('api_url', 'http://localhost:5001')
        self.gateway_url = self.config.get('gateway_url', 'http://localhost:8080')
        self.timeout = self.config.get('timeout', 30)
        self.service_kind = self.config.get('service_kind', 'kubo')
        self.http_client = http_client
        
        self.logger.debug("Initialized lazy %s IPFS adapter", self.service_kind)

    def _load_backend_config_inert(self) -> Dict[str, Any]:
        try:
            value = self.config_manager.get_backend_config(self.backend_name) if self.config_manager else None
            return dict(value) if value else {'enabled': True, 'timeout': 30, 'retry_count': 2}
        except Exception as exc:
            self.logger.warning("Could not load IPFS configuration: %s", self._redact(exc))
            return {'enabled': False, 'timeout': 30, 'retry_count': 0}

    def _redact(self, value: Any) -> str:
        text = str(value)
        for secret_key in ('token', 'secret', 'password', 'api_key', 'authorization'):
            text = re.sub(rf'(?i)({secret_key}[^=:\s]*[=:]\s*)[^\s,&]+', r'\1<redacted>', text)
        return re.sub(r'([a-z][a-z0-9+.-]*://)[^/@\s]+@', r'\1<redacted>@', text)

    def _save_metadata(self, metadata_type: str, data: Dict[str, Any]) -> None:
        self.backend_metadata_dir.mkdir(parents=True, exist_ok=True)
        return super()._save_metadata(metadata_type, data)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        attempts = max(1, int(self.config.get('retry_count', 2)) + 1)
        error = None
        for attempt in range(attempts):
            try:
                client = self.http_client or requests
                response = await anyio.to_thread.run_sync(
                    lambda: client.request(method, f"{self.api_url}{path}", timeout=self.timeout, **kwargs),
                    abandon_on_cancel=True,
                )
                if getattr(response, 'status_code', 200) >= 400:
                    raise RuntimeError(f"IPFS API returned status {response.status_code}")
                return response
            except BaseException as exc:
                if isinstance(exc, anyio.get_cancelled_exc_class()):
                    raise
                error = exc
                if attempt + 1 < attempts:
                    await anyio.sleep(min(.05 * (2 ** attempt), .25))
        raise RuntimeError(self._redact(error)) from error

    @staticmethod
    def _content(response: Any) -> bytes:
        value = getattr(response, 'content', None)
        if value is not None:
            return bytes(value)
        return bytes(getattr(response, 'text', ''), 'utf-8')

    async def certify_live_service(self) -> Dict[str, Any]:
        started = time.monotonic()
        path = '/api/v0/version' if self.service_kind == 'kubo' else '/version'
        try:
            response = await self._request('GET', path)
            payload = response.json() if hasattr(response, 'json') else {}
            return {'status': 'passed', 'healthy': True, 'provider': self.service_kind,
                    'alias': self.backend_name, 'operations': sorted(self.SERVICE_OPERATIONS),
                    'version': payload.get('Version', payload.get('version', 'unknown')),
                    'response_time_ms': round((time.monotonic() - started) * 1000, 2)}
        except Exception as exc:
            return {'status': 'blocked', 'healthy': False, 'provider': self.service_kind,
                    'alias': self.backend_name, 'reason': self._redact(exc),
                    'response_time_ms': round((time.monotonic() - started) * 1000, 2)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Return a non-mutating certification receipt for this IPFS API kind."""
        receipt = await self.certify_live_service()
        return {
            'healthy': receipt['healthy'], 'response_time_ms': receipt['response_time_ms'],
            'error': receipt.get('reason'), 'certification': receipt, 'pin_count': 0,
            'storage_usage': 0, 'needs_pin_sync': False, 'needs_bucket_backup': False,
            'needs_metadata_backup': False, 'version': receipt.get('version', 'unknown'),
            'peer_id': None,
        }

    async def add_bytes(self, data: bytes, *, expected_sha256: Optional[str] = None) -> Dict[str, Any]:
        if not isinstance(data, bytes):
            raise TypeError('data must be bytes')
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise ValueError('source SHA-256 does not match expected_sha256')
        response = await self._request('POST', '/api/v0/add', files={'file': ('payload', data)})
        result = response.json()
        return {'cid': result.get('Hash', result.get('Cid')), 'size': len(data), 'sha256': digest}

    async def cat(self, cid: str, *, byte_range: Optional[tuple[int, int]] = None,
                  expected_sha256: Optional[str] = None) -> bytes:
        headers = {}
        if byte_range is not None:
            start, end = byte_range
            if isinstance(start, bool) or isinstance(end, bool) or start < 0 or end < start:
                raise ValueError('byte_range must be an inclusive non-negative range')
            headers['Range'] = f'bytes={start}-{end}'
        response = await self._request('POST', '/api/v0/cat', params={'arg': cid}, headers=headers)
        payload = self._content(response)
        if expected_sha256 and hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError('download SHA-256 does not match expected_sha256')
        return payload

    async def pin(self, cid: str) -> None:
        await self._request('POST', '/api/v0/pin/add', params={'arg': cid})

    async def unpin(self, cid: str) -> None:
        await self._request('POST', '/api/v0/pin/rm', params={'arg': cid})

    async def list_pins_page(self, *, offset: int = 0, limit: int = 1000) -> Dict[str, Any]:
        if offset < 0 or limit < 1:
            raise ValueError('offset must be non-negative and limit must be positive')
        response = await self._request('POST', '/api/v0/pin/ls', params={'offset': offset, 'limit': limit})
        pins = response.json().get('Keys', {})
        keys = list(pins)
        return {'pins': keys[:limit], 'next_offset': offset + len(keys) if len(keys) == limit else None}

    async def legacy_health_check(self) -> Dict[str, Any]:
        """Deprecated historical probe retained only for callers that explicitly need it."""
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


# This fixture intentionally shares only the hermetic local semantics of the
# reference filesystem adapter.  It never contacts a daemon, gateway, or other
# network provider and must not be used to certify a live IPFS deployment.
from .filesystem_backend import HermeticFilesystemAdapter


class HermeticIPFSFixtureAdapter(HermeticFilesystemAdapter):
    """An IPFS-shaped, hermetic fixture for adapter conformance tests."""

    backend_id = "hermetic_ipfs_fixture"
    provider_kind = "ipfs"
    fixture_kind = "hermetic-ipfs-reference"
    is_hermetic = True
    live_provider = False
    provider_certified = False
    certification_scope = "fixture-only; not live IPFS provider certification"

    def provider_identity(self) -> Dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "provider_kind": self.provider_kind,
            "fixture_kind": self.fixture_kind,
            "is_hermetic": self.is_hermetic,
            "live_provider": self.live_provider,
            "provider_certified": self.provider_certified,
            "certification_scope": self.certification_scope,
        }


HermeticIPFSAdapter = HermeticIPFSFixtureAdapter
