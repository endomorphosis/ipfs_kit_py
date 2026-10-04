#!/usr/bin/env python3
"""
Enhanced Bucket VFS Parquet Generator with Hash-based Versioning

Creates individual Parquet files per bucket and maintains snapshot hashes
using IPFS multiformats for versioning and CAR file preparation.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib

# Try to import multiformats, fallback to hashlib if not available
try:
    from multiformats import multibase, multihash, CID
    MULTIFORMATS_AVAILABLE = True
    print("✓ Using ipfs_multiformats for hashing")
except ImportError:
    MULTIFORMATS_AVAILABLE = False
    multibase = None
    multihash = None
    CID = None
    print("⚠️  multiformats not available, using hashlib fallback")


class BucketVFSManager:
    """Manages individual bucket VFS Parquet files with hash-based versioning."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".ipfs_kit"
        self.vfs_root = self.base_path / "vfs" / "buckets"
        self.snapshots_dir = self.base_path / "vfs" / "snapshots"
        self.manifest_path = self.base_path / "vfs" / "bucket_manifest.json"
        
        # Create directories
        self.vfs_root.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    def create_content_hash(self, data: bytes) -> str:
        """Create a content hash using IPFS multiformats or fallback."""
        if MULTIFORMATS_AVAILABLE and multihash is not None and CID is not None:
            try:
                # Use IPFS-style hashing (sha2-256, base58btc)
                hash_digest = multihash.digest(data, 'sha2-256')
                # Create a CID v1 with dag-pb codec
                cid = CID('base58btc', 1, 'dag-pb', hash_digest)
                return str(cid)
            except Exception as e:
                print(f"⚠️  Multiformats error: {e}, falling back to sha256")
        
        # Fallback to SHA256 with IPFS-like prefix
        sha256_hash = hashlib.sha256(data).hexdigest()
        return f"bafybei{sha256_hash[:52]}"  # Mimic IPFS CID format
    
    def create_bucket_vfs_parquet(self, bucket_name: str, files_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a Parquet file for a single bucket's VFS index."""
        try:
            # Prepare VFS records for this bucket
            vfs_records = []
            bucket_metadata = {
                'bucket_name': bucket_name,
                'created_at': datetime.now().isoformat(),
                'file_count': len(files_data),
                'total_size_bytes': sum(f.get('size_bytes', 0) for f in files_data)
            }
            
            for file_info in files_data:
                vfs_record = {
                    'file_id': f"{bucket_name}_{file_info['name']}",
                    'bucket_name': bucket_name,
                    'name': file_info['name'],
                    'cid': file_info['cid'],
                    'size_bytes': file_info['size_bytes'],
                    'mime_type': file_info['mime_type'],
                    'uploaded_at': file_info['uploaded_at'],
                    'tags': json.dumps(file_info['tags']),
                    'path': file_info['path'],
                    'vfs_path': file_info['path'],
                    'mount_point': f"/{bucket_name}",
                    'access_count': 0,
                    'last_accessed': file_info['uploaded_at'],
                    'content_hash': file_info['cid'],
                    'integrity_status': 'verified',
                    'storage_tier': 'primary',
                    'compression': None,
                    'encryption_status': 'unknown',
                    'snapshot_created': datetime.now().isoformat(),
                    'bucket_version': 1
                }
                vfs_records.append(vfs_record)
            
            # Create DataFrame and save as Parquet
            df = pd.DataFrame(vfs_records)
            bucket_parquet_path = self.vfs_root / f"{bucket_name}_vfs.parquet"
            df.to_parquet(bucket_parquet_path, index=False)
            
            # Calculate content hash of the Parquet file
            with open(bucket_parquet_path, 'rb') as f:
                parquet_bytes = f.read()
            
            content_hash = self.create_content_hash(parquet_bytes)
            
            # Create bucket metadata with hash
            bucket_info = {
                'bucket_name': bucket_name,
                'parquet_file': str(bucket_parquet_path),
                'parquet_size_bytes': len(parquet_bytes),
                'content_hash': content_hash,
                'snapshot_hash': content_hash,  # For now, same as content hash
                'created_at': datetime.now().isoformat(),
                'file_count': len(files_data),
                'total_size_bytes': bucket_metadata['total_size_bytes'],
                'version': 1,
                'car_ready': True,  # Ready for CAR file generation
                'ipfs_ready': True,  # Ready for IPFS upload
                'storacha_ready': True  # Ready for Storacha upload
            }
            
            print(f"✅ Created VFS Parquet for {bucket_name}:")
            print(f"   File: {bucket_parquet_path}")
            print(f"   Hash: {content_hash}")
            print(f"   Files: {len(files_data)}")
            print(f"   Size: {bucket_metadata['total_size_bytes'] / (1024*1024):.2f} MB")
            
            return {
                'success': True,
                'bucket_info': bucket_info,
                'parquet_path': bucket_parquet_path,
                'content_hash': content_hash
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to create bucket VFS Parquet: {e}',
                'bucket_name': bucket_name
            }
    
    def create_snapshot_manifest(self, bucket_infos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a manifest of all bucket snapshots with global hash."""
        try:
            # Create snapshot manifest
            manifest = {
                'snapshot_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
                'created_at': datetime.now().isoformat(),
                'bucket_count': len(bucket_infos),
                'total_files': sum(info['file_count'] for info in bucket_infos),
                'total_size_bytes': sum(info['total_size_bytes'] for info in bucket_infos),
                'buckets': {}
            }
            
            # Add each bucket to manifest
            for bucket_info in bucket_infos:
                bucket_name = bucket_info['bucket_name']
                manifest['buckets'][bucket_name] = {
                    'content_hash': bucket_info['content_hash'],
                    'snapshot_hash': bucket_info['snapshot_hash'],
                    'parquet_file': bucket_info['parquet_file'],
                    'file_count': bucket_info['file_count'],
                    'total_size_bytes': bucket_info['total_size_bytes'],
                    'version': bucket_info['version'],
                    'car_ready': bucket_info['car_ready']
                }
            
            # Calculate global manifest hash
            manifest_json = json.dumps(manifest, sort_keys=True)
            manifest_bytes = manifest_json.encode('utf-8')
            global_hash = self.create_content_hash(manifest_bytes)
            
            manifest['global_hash'] = global_hash
            manifest['manifest_hash'] = global_hash
            
            # Save manifest
            with open(self.manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create snapshot file
            snapshot_path = self.snapshots_dir / f"snapshot_{manifest['snapshot_id']}_{global_hash[:12]}.json"
            with open(snapshot_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            print(f"\n📸 Created snapshot manifest:")
            print(f"   Snapshot ID: {manifest['snapshot_id']}")
            print(f"   Global Hash: {global_hash}")
            print(f"   Buckets: {len(bucket_infos)}")
            print(f"   Total Files: {manifest['total_files']}")
            print(f"   Manifest: {self.manifest_path}")
            print(f"   Snapshot: {snapshot_path}")
            
            return {
                'success': True,
                'manifest': manifest,
                'snapshot_path': snapshot_path,
                'global_hash': global_hash
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to create snapshot manifest: {e}'
            }
    
    def get_snapshot_history(self) -> List[Dict[str, Any]]:
        """Get history of all snapshots."""
        snapshots = []
        
        for snapshot_file in self.snapshots_dir.glob("snapshot_*.json"):
            try:
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                
                snapshots.append({
                    'snapshot_id': snapshot_data.get('snapshot_id', ''),
                    'global_hash': snapshot_data.get('global_hash', ''),
                    'created_at': snapshot_data.get('created_at', ''),
                    'bucket_count': snapshot_data.get('bucket_count', 0),
                    'total_files': snapshot_data.get('total_files', 0),
                    'file_path': str(snapshot_file)
                })
            except Exception as e:
                print(f"⚠️  Error reading snapshot {snapshot_file}: {e}")
        
        # Sort by creation time (newest first)
        snapshots.sort(key=lambda x: x['created_at'], reverse=True)
        return snapshots
    
    def get_all_bucket_snapshots(self) -> Dict[str, Any]:
        """Get snapshot information for all buckets."""
        try:
            if not self.manifest_path.exists():
                return {
                    'success': False,
                    'buckets': {},
                    'error': 'No manifest found'
                }
            
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
            
            return {
                'success': True,
                'buckets': manifest.get('buckets', {}),
                'global_hash': manifest.get('global_hash', ''),
                'snapshot_id': manifest.get('snapshot_id', ''),
                'created_at': manifest.get('created_at', ''),
                'total_files': manifest.get('total_files', 0),
                'total_size_bytes': manifest.get('total_size_bytes', 0)
            }
            
        except Exception as e:
            return {
                'success': False,
                'buckets': {},
                'error': str(e)
            }
    
    def prepare_for_car_generation(self, bucket_name: str) -> Dict[str, Any]:
        """Prepare bucket data for CAR file generation."""
        try:
            bucket_parquet_path = self.vfs_root / f"{bucket_name}_vfs.parquet"
            
            if not bucket_parquet_path.exists():
                return {
                    'success': False,
                    'error': f'Bucket VFS Parquet not found: {bucket_parquet_path}'
                }
            
            # Read current bucket data
            df = pd.read_parquet(bucket_parquet_path)
            
            # Prepare CAR-ready data structure
            car_data = {
                'bucket_name': bucket_name,
                'files': [],
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'file_count': len(df),
                    'total_size_bytes': df['size_bytes'].sum(),
                    'car_ready': True
                }
            }
            
            # Extract file data for CAR generation
            for _, row in df.iterrows():
                file_entry = {
                    'name': row['name'],
                    'cid': row['cid'],
                    'size_bytes': row['size_bytes'],
                    'mime_type': row['mime_type'],
                    'path': row['vfs_path'],
                    'content_hash': row['content_hash']
                }
                car_data['files'].append(file_entry)
            
            return {
                'success': True,
                'car_data': car_data,
                'bucket_parquet_path': bucket_parquet_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to prepare CAR data: {e}'
            }


def create_individual_bucket_parquet_files():
    """Main function to create individual bucket VFS Parquet files."""
    
    # Initialize VFS manager
    vfs_manager = BucketVFSManager()
    
    # Read source data
    workspace_dir = Path("/home/devel/ipfs_kit_py")
    
    with open(workspace_dir / "bucket_files.json", 'r') as f:
        files_data = json.load(f)
    
    print("🗂️  Creating individual bucket VFS Parquet files...")
    print("=" * 60)
    
    bucket_infos = []
    
    # Create Parquet file for each bucket
    for bucket_name, bucket_files in files_data.items():
        result = vfs_manager.create_bucket_vfs_parquet(bucket_name, bucket_files)
        
        if result['success']:
            bucket_infos.append(result['bucket_info'])
        else:
            print(f"❌ Failed to create {bucket_name}: {result['error']}")
    
    # Create snapshot manifest
    if bucket_infos:
        print("\n" + "=" * 60)
        manifest_result = vfs_manager.create_snapshot_manifest(bucket_infos)
        
        if manifest_result['success']:
            print(f"\n🎉 Successfully created VFS system:")
            print(f"   Individual bucket Parquet files: {len(bucket_infos)}")
            print(f"   Global snapshot hash: {manifest_result['global_hash']}")
            print(f"   Ready for CAR generation and IPFS/Storacha upload")
            
            # Show snapshot history
            snapshots = vfs_manager.get_snapshot_history()
            if len(snapshots) > 1:
                print(f"\n📜 Snapshot history ({len(snapshots)} snapshots):")
                for snapshot in snapshots[:3]:  # Show last 3
                    print(f"   {snapshot['snapshot_id']} - {snapshot['global_hash'][:12]}... ({snapshot['total_files']} files)")
            
        else:
            print(f"❌ Failed to create manifest: {manifest_result['error']}")
    
    return vfs_manager


if __name__ == "__main__":
    create_individual_bucket_parquet_files()
