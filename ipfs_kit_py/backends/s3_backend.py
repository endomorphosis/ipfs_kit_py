#!/usr/bin/env python3
"""
S3 Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for S3-compatible storage.
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

from .base_adapter import BackendAdapter


class S3BackendAdapter(BackendAdapter):
    """
    S3 backend adapter implementing the isomorphic interface.
    Supports AWS S3 and S3-compatible storage providers.
    """
    
    # These aliases deliberately describe the shared S3 API only.  In
    # particular, a DigitalOcean token is not an S3 signing credential.
    SERVICE_OPERATIONS = frozenset({"put", "get", "range", "list", "delete"})

    def __init__(self, backend_name: str = "s3", config_manager=None, *, client=None,
                 client_factory=None):
        """Construct lazily; no directory, client, or network work happens here."""
        self.backend_name = backend_name
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__).getChild(f"{self.__class__.__name__}.{backend_name}")
        # Do not call BackendAdapter.__init__: it writes under the caller's home.
        self.ipfs_kit_dir = Path.home() / '.ipfs_kit'
        self.backend_metadata_dir = self.ipfs_kit_dir / 'backends' / backend_name
        self.pin_metadata_dir = self.ipfs_kit_dir / 'pins'
        self.config = self._load_backend_config_inert()
        
        # S3-specific configuration
        self.bucket_name = self.config.get('bucket_name', f'ipfs-kit-{backend_name}')
        self.endpoint_url = self.config.get('endpoint_url', '')
        self.region = self.config.get('region', 'us-east-1')
        self.access_key = self.config.get('access_key_id', self.config.get('access_key', ''))
        self.secret_key = self.config.get('secret_access_key', self.config.get('secret_key', ''))
        self.use_ssl = self.config.get('use_ssl', True)
        
        # S3 prefixes for organization
        self.pins_prefix = 'pins/'
        self.buckets_prefix = 'buckets/'
        self.metadata_prefix = 'metadata/'
        
        # Initialize S3 client (lazy loading)
        self.s3_client = client
        self._client_factory = client_factory
        # A caller-provided test/client object is deliberately not discarded
        # between retries.  Factory-created and SDK-created clients are
        # recreated after transport failures to exercise reconnect behaviour.
        self._injected_client = client is not None and client_factory is None
        
        self.logger.debug("Initialized lazy S3-compatible adapter for %s", backend_name)

    def _load_backend_config_inert(self) -> Dict[str, Any]:
        try:
            value = self.config_manager.get_backend_config(self.backend_name) if self.config_manager else None
            return dict(value) if value else {'enabled': True, 'timeout': 30, 'retry_count': 3}
        except Exception as exc:
            self.logger.warning("Could not load S3 configuration: %s", self._redact(exc))
            return {'enabled': False, 'timeout': 30, 'retry_count': 0}

    def _redact(self, value: Any) -> str:
        text = str(value)
        for secret in (self.__dict__.get('access_key', ''), self.__dict__.get('secret_key', '')):
            if secret:
                text = text.replace(str(secret), '<redacted>')
        text = re.sub(r'(?i)(\b(?:secret|token|password|access[_-]?key|credential)[^=:\s]*[=:]\s*)[^\s,&]+', r'\1<redacted>', text)
        return re.sub(r'([a-z][a-z0-9+.-]*://)[^/@\s]+@', r'\1<redacted>@', text)

    def _save_metadata(self, metadata_type: str, data: Dict[str, Any]) -> None:
        """Retain legacy persistence, but make it an explicit I/O operation."""
        self.backend_metadata_dir.mkdir(parents=True, exist_ok=True)
        return super()._save_metadata(metadata_type, data)
    
    def _get_s3_client(self):
        """Get S3 client with lazy initialization."""
        if self.s3_client is None:
            try:
                if self._client_factory is not None:
                    self.s3_client = self._client_factory()
                    return self.s3_client
                import boto3
                from botocore.config import Config
                
                config = Config(
                    region_name=self.region,
                    retries={'max_attempts': 3, 'mode': 'adaptive'},
                    max_pool_connections=50
                )
                
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint_url if self.endpoint_url else None,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                    use_ssl=self.use_ssl,
                    config=config
                )
                
            except ImportError:
                raise Exception("boto3 library is required for S3 backend. Install with: pip install boto3")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize S3 client: {self._redact(e)}")
        
        return self.s3_client
    
    async def _call(self, method: str, **kwargs: Any) -> Any:
        """Call the blocking SDK off-loop and retry only transient transport errors."""
        attempts = max(1, int(self.config.get('retry_count', 3)) + 1)
        last_error = None
        for attempt in range(attempts):
            try:
                client = self._get_s3_client()
                return await anyio.to_thread.run_sync(lambda: getattr(client, method)(**kwargs), abandon_on_cancel=True)
            except BaseException as exc:
                if isinstance(exc, anyio.get_cancelled_exc_class()):
                    raise
                last_error = exc
                # Recreate a client after a connection failure; never substitute local storage.
                if not self._injected_client:
                    self.s3_client = None
                if attempt + 1 < attempts:
                    await anyio.sleep(min(.05 * (2 ** attempt), .25))
        raise RuntimeError(self._redact(last_error)) from last_error

    async def certify_live_service(self) -> Dict[str, Any]:
        """Non-mutating endpoint proof.  An absent bucket/service is blocked."""
        started = time.monotonic()
        try:
            await self._call('head_bucket', Bucket=self.bucket_name)
            return {'status': 'passed', 'healthy': True, 'provider': 's3-compatible',
                    'alias': self.backend_name, 'operations': sorted(self.SERVICE_OPERATIONS),
                    'response_time_ms': round((time.monotonic() - started) * 1000, 2)}
        except Exception as exc:
            return {'status': 'blocked', 'healthy': False, 'provider': 's3-compatible',
                    'alias': self.backend_name, 'reason': self._redact(exc),
                    'response_time_ms': round((time.monotonic() - started) * 1000, 2)}

    async def health_check(self) -> Dict[str, Any]:
        """Check only a pre-provisioned bucket; certification never mutates it."""
        receipt = await self.certify_live_service()
        return {
            'healthy': receipt['healthy'], 'response_time_ms': receipt['response_time_ms'],
            'error': receipt.get('reason'), 'certification': receipt,
            'pin_count': 0, 'storage_usage': 0, 'needs_pin_sync': False,
            'needs_bucket_backup': False, 'needs_metadata_backup': False,
            'bucket_name': self.bucket_name, 'region': self.region,
        }

    async def put_object(self, key: str, data: bytes, *, expected_sha256: Optional[str] = None,
                         multipart_threshold: int = 8 * 1024 * 1024,
                         part_size: int = 5 * 1024 * 1024) -> Dict[str, Any]:
        if not isinstance(data, bytes):
            raise TypeError('data must be bytes')
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 and expected_sha256 != digest:
            raise ValueError('source SHA-256 does not match expected_sha256')
        if len(data) < multipart_threshold:
            result = await self._call('put_object', Bucket=self.bucket_name, Key=key, Body=data)
            return {'key': key, 'size': len(data), 'sha256': digest, 'etag': result.get('ETag') if isinstance(result, dict) else None, 'multipart': False}
        upload = await self._call('create_multipart_upload', Bucket=self.bucket_name, Key=key)
        upload_id = upload['UploadId']
        parts = []
        try:
            for number, start in enumerate(range(0, len(data), part_size), 1):
                result = await self._call('upload_part', Bucket=self.bucket_name, Key=key, UploadId=upload_id,
                                          PartNumber=number, Body=data[start:start + part_size])
                parts.append({'PartNumber': number, 'ETag': result['ETag']})
            await self._call('complete_multipart_upload', Bucket=self.bucket_name, Key=key, UploadId=upload_id,
                             MultipartUpload={'Parts': parts})
        except BaseException:
            try:
                await self._call('abort_multipart_upload', Bucket=self.bucket_name, Key=key, UploadId=upload_id)
            finally:
                raise
        return {'key': key, 'size': len(data), 'sha256': digest, 'multipart': True}

    async def get_object(self, key: str, *, byte_range: Optional[tuple[int, int]] = None,
                         expected_sha256: Optional[str] = None) -> bytes:
        kwargs: Dict[str, Any] = {'Bucket': self.bucket_name, 'Key': key}
        if byte_range is not None:
            start, end = byte_range
            if isinstance(start, bool) or isinstance(end, bool) or start < 0 or end < start:
                raise ValueError('byte_range must be an inclusive non-negative range')
            kwargs['Range'] = f'bytes={start}-{end}'
        result = await self._call('get_object', **kwargs)
        body = result['Body']
        payload = await anyio.to_thread.run_sync(body.read, abandon_on_cancel=True)
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise ValueError('download SHA-256 does not match expected_sha256')
        return payload

    async def list_objects(self, prefix: str = '', *, continuation_token: Optional[str] = None,
                           page_size: int = 1000) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {'Bucket': self.bucket_name, 'Prefix': prefix, 'MaxKeys': page_size}
        if continuation_token:
            kwargs['ContinuationToken'] = continuation_token
        result = await self._call('list_objects_v2', **kwargs)
        return {'objects': result.get('Contents', []), 'next_token': result.get('NextContinuationToken'),
                'truncated': bool(result.get('IsTruncated'))}

    async def delete_object(self, key: str) -> None:
        await self._call('delete_object', Bucket=self.bucket_name, Key=key)
    
    async def sync_pins(self) -> bool:
        """Synchronize pins with S3 storage."""
        try:
            self.logger.info(f"Starting pin sync for {self.backend_name}")
            
            s3_client = self._get_s3_client()
            
            # Get local pin metadata
            local_pins = await self._get_local_pins()
            
            # Get pins already stored in S3
            stored_pins = await self._get_stored_pins()
            
            # Find pins that need to be backed up
            local_cids = set(pin['cid'] for pin in local_pins)
            stored_cids = set(pin['cid'] for pin in stored_pins)
            
            missing_in_storage = local_cids - stored_cids
            
            success_count = 0
            total_operations = len(missing_in_storage)
            
            # Upload missing pins to S3
            for cid in missing_in_storage:
                try:
                    pin_info = next(pin for pin in local_pins if pin['cid'] == cid)
                    if await self._backup_pin_to_s3(pin_info):
                        success_count += 1
                        self.logger.debug(f"Backed up pin {cid} to S3")
                    else:
                        self.logger.warning(f"Failed to backup pin {cid}")
                except Exception as e:
                    self.logger.error(f"Error backing up pin {cid}: {e}")
            
            # Update sync metadata
            await self._save_metadata_to_s3('sync', {
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
        """Backup bucket configurations to S3."""
        try:
            self.logger.info(f"Starting bucket backup for {self.backend_name}")
            
            s3_client = self._get_s3_client()
            
            # Source buckets directory
            source_buckets_dir = self.ipfs_kit_dir / 'buckets'
            if not source_buckets_dir.exists():
                self.logger.warning("No buckets directory found")
                return True
            
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_key_prefix = f"{self.buckets_prefix}backup_{timestamp}/"
            
            # Upload buckets directory
            total_size = 0
            file_count = 0
            
            for file_path in source_buckets_dir.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(source_buckets_dir)
                    s3_key = f"{backup_key_prefix}{relative_path}"
                    
                    with open(file_path, 'rb') as f:
                        s3_client.put_object(
                            Bucket=self.bucket_name,
                            Key=s3_key,
                            Body=f.read()
                        )
                    
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            # Create backup metadata
            backup_metadata = {
                'timestamp': timestamp,
                'backup_prefix': backup_key_prefix,
                'source_path': str(source_buckets_dir),
                'size': total_size,
                'file_count': file_count,
                'bucket_name': self.bucket_name
            }
            
            # Update bucket backup metadata
            bucket_backups = await self._load_metadata_from_s3('bucket_backups')
            bucket_backups[timestamp] = backup_metadata
            await self._save_metadata_to_s3('bucket_backups', bucket_backups)
            
            self.logger.info(f"Bucket backup completed: {backup_key_prefix}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during bucket backup: {e}")
            return False
    
    async def backup_metadata(self) -> bool:
        """Backup IPFS Kit metadata to S3."""
        try:
            self.logger.info(f"Starting metadata backup for {self.backend_name}")
            
            s3_client = self._get_s3_client()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_key_prefix = f"{self.metadata_prefix}backup_{timestamp}/"
            backup_info = {}
            
            # Backup pin metadata
            pin_metadata_source = self.ipfs_kit_dir / 'pin_metadata'
            if pin_metadata_source.exists():
                pin_metadata_prefix = f"{backup_key_prefix}pin_metadata/"
                total_size = await self._upload_directory_to_s3(
                    pin_metadata_source, pin_metadata_prefix
                )
                backup_info['pin_metadata'] = {
                    'backup_prefix': pin_metadata_prefix,
                    'size': total_size
                }
            
            # Backup backend index
            backend_index_source = self.ipfs_kit_dir / 'backend_index'
            if backend_index_source.exists():
                backend_index_prefix = f"{backup_key_prefix}backend_index/"
                total_size = await self._upload_directory_to_s3(
                    backend_index_source, backend_index_prefix
                )
                backup_info['backend_index'] = {
                    'backup_prefix': backend_index_prefix,
                    'size': total_size
                }
            
            # Backup configuration files
            config_prefix = f"{backup_key_prefix}config/"
            config_size = 0
            
            for config_file in self.ipfs_kit_dir.glob('*.yaml'):
                if config_file.is_file():
                    s3_key = f"{config_prefix}{config_file.name}"
                    
                    with open(config_file, 'rb') as f:
                        s3_client.put_object(
                            Bucket=self.bucket_name,
                            Key=s3_key,
                            Body=f.read()
                        )
                    
                    config_size += config_file.stat().st_size
            
            backup_info['config'] = {
                'backup_prefix': config_prefix,
                'size': config_size
            }
            
            # Save metadata backup record
            metadata_backups = await self._load_metadata_from_s3('metadata_backups')
            metadata_backups[timestamp] = {
                'timestamp': timestamp,
                'backups': backup_info,
                'total_size': sum(info['size'] for info in backup_info.values()),
                'bucket_name': self.bucket_name
            }
            await self._save_metadata_to_s3('metadata_backups', metadata_backups)
            
            self.logger.info(f"Metadata backup completed: {backup_key_prefix}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during metadata backup: {e}")
            return False
    
    async def restore_pins(self, pin_list: List[str] = None) -> bool:
        """Restore pins from S3 storage."""
        try:
            stored_pins = await self._get_stored_pins()
            
            if pin_list:
                stored_pins = [p for p in stored_pins if p['cid'] in pin_list]
            
            success_count = 0
            for pin in stored_pins:
                try:
                    await self._restore_pin_from_s3(pin)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Error restoring pin {pin['cid']}: {e}")
            
            self.logger.info(f"Restored {success_count}/{len(stored_pins)} pins")
            return success_count == len(stored_pins)
            
        except Exception as e:
            self.logger.error(f"Error during pin restore: {e}")
            return False
    
    async def restore_buckets(self, bucket_list: List[str] = None) -> bool:
        """Restore bucket configurations from S3."""
        try:
            bucket_backups = await self._load_metadata_from_s3('bucket_backups')
            if not bucket_backups:
                self.logger.warning("No bucket backups found")
                return False
            
            # Get latest backup
            latest_backup = max(bucket_backups.items(), key=lambda x: x[0])
            backup_prefix = latest_backup[1]['backup_prefix']
            
            # Download and restore buckets
            target_buckets_dir = self.ipfs_kit_dir / 'buckets'
            
            # Backup existing buckets
            if target_buckets_dir.exists():
                backup_existing = target_buckets_dir.parent / f"buckets_backup_{int(time.time())}"
                import shutil
                shutil.move(target_buckets_dir, backup_existing)
            
            target_buckets_dir.mkdir(parents=True, exist_ok=True)
            
            await self._download_directory_from_s3(backup_prefix, target_buckets_dir)
            
            self.logger.info(f"Restored buckets from {backup_prefix}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during bucket restore: {e}")
            return False
    
    async def restore_metadata(self) -> bool:
        """Restore metadata from S3 storage."""
        try:
            metadata_backups = await self._load_metadata_from_s3('metadata_backups')
            if not metadata_backups:
                self.logger.warning("No metadata backups found")
                return False
            
            # Get latest backup
            latest_backup = max(metadata_backups.items(), key=lambda x: x[0])
            backup_info = latest_backup[1]['backups']
            
            success = True
            
            # Restore pin metadata
            if 'pin_metadata' in backup_info:
                backup_prefix = backup_info['pin_metadata']['backup_prefix']
                target_path = self.ipfs_kit_dir / 'pin_metadata'
                
                if target_path.exists():
                    import shutil
                    shutil.rmtree(target_path)
                
                target_path.mkdir(parents=True, exist_ok=True)
                await self._download_directory_from_s3(backup_prefix, target_path)
                self.logger.info("Restored pin metadata")
            
            # Restore backend index
            if 'backend_index' in backup_info:
                backup_prefix = backup_info['backend_index']['backup_prefix']
                target_path = self.ipfs_kit_dir / 'backend_index'
                
                if target_path.exists():
                    import shutil
                    shutil.rmtree(target_path)
                
                target_path.mkdir(parents=True, exist_ok=True)
                await self._download_directory_from_s3(backup_prefix, target_path)
                self.logger.info("Restored backend index")
            
            # Restore configuration
            if 'config' in backup_info:
                backup_prefix = backup_info['config']['backup_prefix']
                await self._download_directory_from_s3(backup_prefix, self.ipfs_kit_dir)
                self.logger.info("Restored configuration files")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during metadata restore: {e}")
            return False
    
    async def list_pins(self) -> List[Dict[str, Any]]:
        """List all pins stored in S3."""
        return await self._get_stored_pins()
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List bucket backups in S3."""
        bucket_backups = await self._load_metadata_from_s3('bucket_backups')
        return [
            {
                'bucket_name': 'all_buckets',
                'backup_path': info['backup_prefix'],
                'size': info['size'],
                'created_at': timestamp,
                'checksum': ''
            }
            for timestamp, info in bucket_backups.items()
        ]
    
    async def list_metadata_backups(self) -> List[Dict[str, Any]]:
        """List metadata backups in S3."""
        metadata_backups = await self._load_metadata_from_s3('metadata_backups')
        return [
            {
                'backup_type': 'metadata',
                'backup_path': f"S3: {len(info['backups'])} components",
                'size': info['total_size'],
                'created_at': timestamp,
                'checksum': ''
            }
            for timestamp, info in metadata_backups.items()
        ]
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> bool:
        """Clean up old backups in S3."""
        try:
            s3_client = self._get_s3_client()
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Clean bucket backups
            bucket_backups = await self._load_metadata_from_s3('bucket_backups')
            cleaned_bucket_backups = {}
            
            for timestamp, info in bucket_backups.items():
                backup_date = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                if backup_date >= cutoff_date:
                    cleaned_bucket_backups[timestamp] = info
                else:
                    # Delete old backup objects
                    await self._delete_s3_prefix(info['backup_prefix'])
            
            await self._save_metadata_to_s3('bucket_backups', cleaned_bucket_backups)
            
            # Clean metadata backups
            metadata_backups = await self._load_metadata_from_s3('metadata_backups')
            cleaned_metadata_backups = {}
            
            for timestamp, info in metadata_backups.items():
                backup_date = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                if backup_date >= cutoff_date:
                    cleaned_metadata_backups[timestamp] = info
                else:
                    # Delete old backup objects
                    for backup_info in info['backups'].values():
                        await self._delete_s3_prefix(backup_info['backup_prefix'])
            
            await self._save_metadata_to_s3('metadata_backups', cleaned_metadata_backups)
            
            self.logger.info(f"Cleaned up S3 backups older than {retention_days} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during S3 backup cleanup: {e}")
            return False
    
    async def get_storage_usage(self) -> Dict[str, int]:
        """Get S3 storage usage."""
        return await self._get_storage_usage_internal()
    
    # S3-specific helper methods
    
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
            import pandas as pd
            
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
            s3_client = self._get_s3_client()
            stored_pins = []
            
            # List all pin objects
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.pins_prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.json'):
                            try:
                                response = s3_client.get_object(Bucket=self.bucket_name, Key=key)
                                pin_data = json.loads(response['Body'].read().decode())
                                stored_pins.append(pin_data)
                            except Exception as e:
                                self.logger.error(f"Error reading pin object {key}: {e}")
            
            return stored_pins
            
        except Exception as e:
            self.logger.error(f"Error getting stored pins from S3: {e}")
            return []
    
    async def _backup_pin_to_s3(self, pin_info: Dict[str, Any]) -> bool:
        """Backup a pin to S3."""
        try:
            s3_client = self._get_s3_client()
            cid = pin_info['cid']
            s3_key = f"{self.pins_prefix}{cid}.json"
            
            # Upload pin metadata
            s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(pin_info, indent=2, default=str).encode()
            )
            
            # TODO: Upload actual pin content if available
            # This would require integration with IPFS to fetch and upload the actual content
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error backing up pin to S3: {e}")
            return False
    
    async def _restore_pin_from_s3(self, pin_info: Dict[str, Any]):
        """Restore a pin from S3 to local metadata."""
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
            self.logger.error(f"Error restoring pin from S3: {e}")
    
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
            
            bucket_backups = await self._load_metadata_from_s3('bucket_backups')
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
            metadata_backups = await self._load_metadata_from_s3('metadata_backups')
            if not metadata_backups:
                return True
            
            # Check if backup is older than 24 hours
            latest_backup = max(metadata_backups.keys())
            latest_backup_time = datetime.strptime(latest_backup, "%Y%m%d_%H%M%S")
            
            return datetime.now() - latest_backup_time > timedelta(hours=24)
            
        except:
            return True
    
    async def _get_storage_usage_internal(self) -> Dict[str, int]:
        """Get storage usage from S3."""
        try:
            s3_client = self._get_s3_client()
            
            total_usage = 0
            pin_usage = 0
            bucket_backup_usage = 0
            metadata_backup_usage = 0
            
            # Calculate usage for each prefix
            prefixes = {
                'pin_usage': self.pins_prefix,
                'bucket_backup_usage': self.buckets_prefix,
                'metadata_backup_usage': self.metadata_prefix
            }
            
            for usage_type, prefix in prefixes.items():
                prefix_usage = 0
                
                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
                
                for page in pages:
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            prefix_usage += obj['Size']
                
                if usage_type == 'pin_usage':
                    pin_usage = prefix_usage
                elif usage_type == 'bucket_backup_usage':
                    bucket_backup_usage = prefix_usage
                elif usage_type == 'metadata_backup_usage':
                    metadata_backup_usage = prefix_usage
                
                total_usage += prefix_usage
            
            return {
                'total_usage': total_usage,
                'pin_usage': pin_usage,
                'bucket_backup_usage': bucket_backup_usage,
                'metadata_backup_usage': metadata_backup_usage,
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
    
    async def _upload_directory_to_s3(self, local_dir: Path, s3_prefix: str) -> int:
        """Upload a directory to S3 and return total size."""
        s3_client = self._get_s3_client()
        total_size = 0
        
        for file_path in local_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                s3_key = f"{s3_prefix}{relative_path}"
                
                with open(file_path, 'rb') as f:
                    s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        Body=f.read()
                    )
                
                total_size += file_path.stat().st_size
        
        return total_size
    
    async def _download_directory_from_s3(self, s3_prefix: str, local_dir: Path):
        """Download all objects with a prefix to a local directory."""
        s3_client = self._get_s3_client()
        
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    s3_key = obj['Key']
                    relative_path = s3_key[len(s3_prefix):]
                    
                    if relative_path:  # Skip the prefix itself
                        local_file = local_dir / relative_path
                        local_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        response = s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                        with open(local_file, 'wb') as f:
                            f.write(response['Body'].read())
    
    async def _delete_s3_prefix(self, prefix: str):
        """Delete all objects with a given prefix."""
        s3_client = self._get_s3_client()
        
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
        
        for page in pages:
            if 'Contents' in page:
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                
                if objects_to_delete:
                    s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
    
    async def _load_metadata_from_s3(self, metadata_type: str) -> Dict[str, Any]:
        """Load metadata from S3."""
        try:
            s3_client = self._get_s3_client()
            s3_key = f"{self.metadata_prefix}internal/{metadata_type}.json"
            
            response = s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return json.loads(response['Body'].read().decode())
            
        except s3_client.exceptions.NoSuchKey:
            return {}
        except Exception as e:
            self.logger.error(f"Error loading metadata from S3: {e}")
            return {}
    
    async def _save_metadata_to_s3(self, metadata_type: str, data: Dict[str, Any]):
        """Save metadata to S3."""
        try:
            s3_client = self._get_s3_client()
            s3_key = f"{self.metadata_prefix}internal/{metadata_type}.json"
            
            s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(data, indent=2, default=str).encode()
            )
            
        except Exception as e:
            self.logger.error(f"Error saving metadata to S3: {e}")
