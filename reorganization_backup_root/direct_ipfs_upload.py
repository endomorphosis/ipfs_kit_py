#!/usr/bin/env python3
"""
Direct IPFS Index Upload

Upload VFS index data directly to IPFS without CAR files,
then generate shareable index CIDs.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd


class DirectIPFSUpload:
    """Upload VFS indexes directly to IPFS."""
    
    def __init__(self):
        self.base_path = Path.home() / ".ipfs_kit"
        self.vfs_root = self.base_path / "vfs" / "buckets"
        self.temp_dir = self.base_path / "temp_ipfs"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_log = self.base_path / "ipfs_direct_uploads.json"
    
    def check_ipfs(self) -> bool:
        """Check if IPFS is available."""
        try:
            result = subprocess.run(['ipfs', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def create_bucket_index_file(self, bucket_name: str) -> Dict[str, Any]:
        """Create JSON index file for bucket."""
        try:
            bucket_parquet_path = self.vfs_root / f"{bucket_name}_vfs.parquet"
            
            if not bucket_parquet_path.exists():
                return {
                    'success': False,
                    'error': f'Bucket VFS not found: {bucket_parquet_path}'
                }
            
            # Read bucket data
            df = pd.read_parquet(bucket_parquet_path)
            
            # Create index structure
            files_index = []
            total_size = 0
            
            for _, row in df.iterrows():
                file_info = {
                    'name': str(row.get('name', '')),
                    'cid': str(row.get('cid', '')),
                    'size_bytes': int(row.get('size_bytes', 0)),
                    'mime_type': str(row.get('mime_type', '')),
                    'uploaded_at': str(row.get('uploaded_at', '')),
                    'tags': row.get('tags', []) if isinstance(row.get('tags'), list) else [],
                    'path': str(row.get('path', ''))
                }
                files_index.append(file_info)
                total_size += file_info['size_bytes']
            
            # Create bucket index
            bucket_index = {
                'bucket_name': bucket_name,
                'index_type': 'vfs_bucket_index',
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'metadata': {
                    'file_count': len(files_index),
                    'total_size_bytes': total_size,
                    'size_mb': round(total_size / (1024 * 1024), 2)
                },
                'files': files_index,
                'usage_instructions': {
                    'description': 'This is a VFS index. Use individual file CIDs to download content.',
                    'example': 'ipfs get <file_cid>',
                    'parallel_download': 'Use multiple ipfs get commands in parallel for faster downloads'
                }
            }
            
            # Save to temporary JSON file
            index_filename = f"{bucket_name}_index.json"
            index_path = self.temp_dir / index_filename
            
            with open(index_path, 'w') as f:
                json.dump(bucket_index, f, indent=2)
            
            return {
                'success': True,
                'index_path': str(index_path),
                'index_filename': index_filename,
                'file_count': len(files_index),
                'total_size_bytes': total_size
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_index_to_ipfs(self, index_path: Path) -> Dict[str, Any]:
        """Upload index file to IPFS."""
        try:
            # Add file to IPFS
            result = subprocess.run([
                'ipfs', 'add', 
                '--pin=true',
                '--quieter',  # Only output the hash
                str(index_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                ipfs_hash = result.stdout.strip()
                
                # Get file size
                file_size = index_path.stat().st_size
                
                return {
                    'success': True,
                    'ipfs_hash': ipfs_hash,
                    'file_size': file_size,
                    'method': 'direct_add'
                }
            else:
                return {
                    'success': False,
                    'error': f'IPFS add failed: {result.stderr or result.stdout}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_bucket_index(self, bucket_name: str) -> Dict[str, Any]:
        """Create and upload bucket index to IPFS."""
        if not self.check_ipfs():
            return {
                'success': False,
                'error': 'IPFS not available'
            }
        
        # Create index file
        index_result = self.create_bucket_index_file(bucket_name)
        if not index_result['success']:
            return index_result
        
        # Upload to IPFS
        index_path = Path(index_result['index_path'])
        upload_result = self.upload_index_to_ipfs(index_path)
        
        if upload_result['success']:
            # Log successful upload
            self.log_upload(bucket_name, index_result, upload_result)
            
            # Clean up temp file
            index_path.unlink()
            
            return {
                'success': True,
                'bucket_name': bucket_name,
                'ipfs_hash': upload_result['ipfs_hash'],
                'file_count': index_result['file_count'],
                'total_size_bytes': index_result['total_size_bytes'],
                'index_size_bytes': upload_result['file_size']
            }
        else:
            return upload_result
    
    def upload_all_buckets(self) -> Dict[str, Any]:
        """Upload indexes for all buckets."""
        bucket_files = list(self.vfs_root.glob("*_vfs.parquet"))
        
        if not bucket_files:
            return {
                'success': False,
                'error': 'No bucket VFS files found'
            }
        
        results = []
        successful_uploads = 0
        failed_uploads = 0
        
        for bucket_file in bucket_files:
            bucket_name = bucket_file.stem.replace('_vfs', '')
            
            result = self.upload_bucket_index(bucket_name)
            
            if result['success']:
                results.append(result)
                successful_uploads += 1
            else:
                results.append({
                    'bucket_name': bucket_name,
                    'success': False,
                    'error': result['error']
                })
                failed_uploads += 1
        
        # Create master index
        if successful_uploads > 0:
            master_result = self.create_master_index(results)
        else:
            master_result = {'success': False, 'error': 'No successful uploads'}
        
        return {
            'success': successful_uploads > 0,
            'bucket_uploads': results,
            'successful_uploads': successful_uploads,
            'failed_uploads': failed_uploads,
            'master_index': master_result
        }
    
    def create_master_index(self, bucket_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create and upload master index."""
        try:
            successful_buckets = [r for r in bucket_results if r['success']]
            
            master_index = {
                'index_type': 'master_vfs_index',
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'bucket_count': len(successful_buckets),
                'buckets': {}
            }
            
            total_files = 0
            total_size = 0
            
            for bucket in successful_buckets:
                bucket_name = bucket['bucket_name']
                master_index['buckets'][bucket_name] = {
                    'ipfs_hash': bucket['ipfs_hash'],
                    'file_count': bucket['file_count'],
                    'size_bytes': bucket['total_size_bytes']
                }
                
                total_files += bucket['file_count']
                total_size += bucket['total_size_bytes']
            
            master_index['summary'] = {
                'total_files': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
            
            master_index['usage_instructions'] = {
                'description': 'Master index of all bucket VFS indexes',
                'access_bucket': 'ipfs get <bucket_ipfs_hash>',
                'example_workflow': [
                    '1. Download master index: ipfs get <master_hash>',
                    '2. Select bucket and get its IPFS hash',
                    '3. Download bucket index: ipfs get <bucket_hash>',
                    '4. Extract file CIDs from bucket index',
                    '5. Download files in parallel: ipfs get <file_cid>'
                ]
            }
            
            # Save master index
            master_filename = "master_vfs_index.json"
            master_path = self.temp_dir / master_filename
            
            with open(master_path, 'w') as f:
                json.dump(master_index, f, indent=2)
            
            # Upload master index
            upload_result = self.upload_index_to_ipfs(master_path)
            
            if upload_result['success']:
                # Clean up
                master_path.unlink()
                
                return {
                    'success': True,
                    'master_hash': upload_result['ipfs_hash'],
                    'bucket_count': len(successful_buckets),
                    'total_files': total_files,
                    'total_size_bytes': total_size
                }
            else:
                return upload_result
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_upload(self, bucket_name: str, index_result: Dict[str, Any], upload_result: Dict[str, Any]) -> None:
        """Log upload to tracking file."""
        try:
            if self.uploads_log.exists():
                with open(self.uploads_log, 'r') as f:
                    log_data = json.load(f)
            else:
                log_data = {'uploads': []}
            
            upload_entry = {
                'bucket_name': bucket_name,
                'ipfs_hash': upload_result['ipfs_hash'],
                'file_count': index_result['file_count'],
                'total_size_bytes': index_result['total_size_bytes'],
                'index_size_bytes': upload_result['file_size'],
                'uploaded_at': datetime.now().isoformat(),
                'method': 'direct_ipfs_add'
            }
            
            log_data['uploads'].append(upload_entry)
            
            with open(self.uploads_log, 'w') as f:
                json.dump(log_data, f, indent=2)
                
        except Exception as e:
            print(f"⚠️  Failed to log upload: {e}")
    
    def get_upload_history(self) -> List[Dict[str, Any]]:
        """Get upload history."""
        try:
            if not self.uploads_log.exists():
                return []
            
            with open(self.uploads_log, 'r') as f:
                log_data = json.load(f)
            
            uploads = log_data.get('uploads', [])
            uploads.sort(key=lambda x: x['uploaded_at'], reverse=True)
            return uploads
            
        except Exception as e:
            print(f"⚠️  Failed to read upload history: {e}")
            return []


def test_direct_ipfs_upload():
    """Test direct IPFS upload."""
    uploader = DirectIPFSUpload()
    
    print("🌐 Testing Direct IPFS Index Upload")
    print("=" * 60)
    
    if not uploader.check_ipfs():
        print("❌ IPFS not available")
        return
    
    print("✅ IPFS is available")
    
    # Test single bucket
    print(f"\n📦 Uploading media-bucket index...")
    result = uploader.upload_bucket_index("media-bucket")
    
    if result['success']:
        print(f"   ✅ Success!")
        print(f"   IPFS Hash: {result['ipfs_hash']}")
        print(f"   Files: {result['file_count']}")
        print(f"   Total Size: {result['total_size_bytes'] / (1024*1024):.2f} MB")
        print(f"   Index Size: {result['index_size_bytes']} bytes")
    else:
        print(f"   ❌ Failed: {result['error']}")
    
    # Test all buckets
    print(f"\n🌍 Uploading all bucket indexes...")
    all_result = uploader.upload_all_buckets()
    
    if all_result['success']:
        print(f"   ✅ Bulk upload successful!")
        print(f"   Successful: {all_result['successful_uploads']}")
        print(f"   Failed: {all_result['failed_uploads']}")
        
        if all_result['master_index']['success']:
            print(f"   Master Hash: {all_result['master_index']['master_hash']}")
        
        print(f"\n📋 Individual bucket hashes:")
        for bucket in all_result['bucket_uploads']:
            if bucket['success']:
                bucket_name = bucket['bucket_name']
                ipfs_hash = bucket['ipfs_hash']
                files = bucket['file_count']
                print(f"   {bucket_name}: {ipfs_hash} ({files} files)")
    else:
        print(f"   ❌ Bulk upload failed")


if __name__ == "__main__":
    test_direct_ipfs_upload()
