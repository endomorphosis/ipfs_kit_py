#!/usr/bin/env python3
"""
S3 Backend Adapter for IPFS Kit

Implements the isomorphic backend interface for S3-compatible storage.
"""

import anyio
import json
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
    
    def __init__(self, backend_name: str, config_manager=None):
        """Initialize S3 backend adapter."""
        super().__init__(backend_name, config_manager)
        
        # S3-specific configuration
        self.bucket_name = self.config.get('bucket_name', f'ipfs-kit-{backend_name}')
        self.endpoint_url = self.config.get('endpoint_url', '')
        self.region = self.config.get('region', 'us-east-1')
        self.access_key = self.config.get('access_key_id', '')
        self.secret_key = self.config.get('secret_access_key', '')
        self.use_ssl = self.config.get('use_ssl', True)
        
        # S3 prefixes for organization
        self.pins_prefix = 'pins/'
        self.buckets_prefix = 'buckets/'
        self.metadata_prefix = 'metadata/'
        
        # Initialize S3 client (lazy loading)
        self.s3_client = None
        
        self.logger.info(f"Initialized S3 adapter for {backend_name} (bucket: {self.bucket_name})")
    
    def _get_s3_client(self):
        """Get S3 client with lazy initialization."""
        if self.s3_client is None:
            try:
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
                raise Exception(f"Failed to initialize S3 client: {e}")
        
        return self.s3_client
    
    async def health_check(self) -> Dict[str, Any]:
        """Check S3 backend health."""
        start_time = time.time()
        
        try:
            s3_client = self._get_s3_client()
            
            # Test bucket access
            try:
                s3_client.head_bucket(Bucket=self.bucket_name)
            except s3_client.exceptions.NoSuchBucket:
                # Try to create bucket if it doesn't exist
                if self.region == 'us-east-1':
                    s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
            
            # Test read/write access
            test_key = 'health_check_test'
            test_content = f"health_check_{int(time.time())}"
            
            s3_client.put_object(
                Bucket=self.bucket_name,
                Key=test_key,
                Body=test_content.encode()
            )
            
            response = s3_client.get_object(Bucket=self.bucket_name, Key=test_key)
            read_content = response['Body'].read().decode()
            
            s3_client.delete_object(Bucket=self.bucket_name, Key=test_key)
            
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
                'bucket_name': self.bucket_name,
                'region': self.region
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
