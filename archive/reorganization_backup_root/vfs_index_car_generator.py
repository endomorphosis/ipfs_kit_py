#!/usr/bin/env python3
"""
VFS Index CAR Generator

Generates CAR files from VFS index metadata instead of actual file contents.
This allows recipients to receive the complete file index and download individual
files in parallel using their CIDs.
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib
import tempfile
import os

# Try to import CAR generation libraries
try:
    import cbor2
    CBOR_AVAILABLE = True
except ImportError:
    CBOR_AVAILABLE = False
    print("⚠️  cbor2 not available, using JSON fallback for CAR simulation")

# Try to import multiformats
try:
    from multiformats import multibase, multihash, CID
    MULTIFORMATS_AVAILABLE = True
    print("✓ Using ipfs_multiformats for CID generation")
except ImportError:
    MULTIFORMATS_AVAILABLE = False
    print("⚠️  multiformats not available, using CID simulation")

# Import our VFS manager
import sys
sys.path.append('/home/devel/ipfs_kit_py')
from create_individual_bucket_parquet import BucketVFSManager


class VFSIndexCARGenerator:
    """Generates CAR files from VFS index metadata."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".ipfs_kit"
        self.vfs_root = self.base_path / "vfs" / "buckets"
        self.car_output_dir = self.base_path / "vfs" / "car_files"
        self.car_output_dir.mkdir(parents=True, exist_ok=True)
        
        self.vfs_manager = BucketVFSManager(base_path)
    
    def create_index_cid(self, data: bytes) -> str:
        """Create a CID for index data."""
        if MULTIFORMATS_AVAILABLE and multihash is not None and CID is not None:
            try:
                # Use IPFS-style hashing for index data
                hash_digest = multihash.digest(data, 'sha2-256')
                cid = CID('base58btc', 1, 'dag-pb', hash_digest)
                return str(cid)
            except Exception as e:
                print(f"⚠️  Multiformats CID creation failed: {e}")
        
        # Fallback to simulated CID
        hash_hex = hashlib.sha256(data).hexdigest()
        return f"QmIndex{hash_hex[:40]}"
    
    def prepare_bucket_index_for_car(self, bucket_name: str) -> Dict[str, Any]:
        """Prepare bucket VFS index for CAR generation."""
        try:
            bucket_parquet_path = self.vfs_root / f"{bucket_name}_vfs.parquet"
            
            if not bucket_parquet_path.exists():
                return {
                    'success': False,
                    'error': f'Bucket VFS Parquet not found: {bucket_parquet_path}'
                }
            
            # Read bucket VFS index
            df = pd.read_parquet(bucket_parquet_path)
            
            # Convert to index metadata structure
            index_data = {
                'bucket_name': bucket_name,
                'index_type': 'vfs_metadata',
                'created_at': datetime.now().isoformat(),
                'total_files': len(df),
                'total_size_bytes': int(df['size_bytes'].sum()) if 'size_bytes' in df.columns else 0,  # Convert to native int
                'files': []
            }
            
            # Add each file's metadata (not content)
            for _, row in df.iterrows():
                file_metadata = {
                    'name': str(row.get('name', '')),
                    'cid': str(row.get('cid', '')),  # Original file CID for downloading
                    'size_bytes': int(row.get('size_bytes', 0)),  # Convert to native int
                    'mime_type': str(row.get('mime_type', '')),
                    'path': str(row.get('path', '')),
                    'uploaded_at': str(row.get('uploaded_at', '')),
                    'tags': list(row.get('tags', [])) if isinstance(row.get('tags'), list) else [],
                    'bucket': bucket_name
                }
                index_data['files'].append(file_metadata)
            
            # Create CID for the index itself
            index_json = json.dumps(index_data, sort_keys=True).encode('utf-8')
            index_cid = self.create_index_cid(index_json)
            
            return {
                'success': True,
                'index_data': index_data,
                'index_cid': index_cid,
                'index_size_bytes': len(index_json),
                'bucket_parquet_path': str(bucket_parquet_path)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_car_from_index(self, bucket_name: str, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Generate a CAR file from bucket VFS index."""
        try:
            # Prepare index data
            index_result = self.prepare_bucket_index_for_car(bucket_name)
            
            if not index_result['success']:
                return index_result
            
            index_data = index_result['index_data']
            index_cid = index_result['index_cid']
            
            # Determine output path
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                car_filename = f"{bucket_name}_index_{timestamp}.car"
                output_path = self.car_output_dir / car_filename
            
            # Generate CAR file content
            car_content = self._create_car_content(index_data, index_cid)
            
            # Write CAR file
            with open(output_path, 'wb') as f:
                f.write(car_content)
            
            # Create accompanying metadata file
            metadata_path = output_path.with_suffix('.json')
            metadata = {
                'bucket_name': bucket_name,
                'index_cid': index_cid,
                'car_file': str(output_path),
                'created_at': datetime.now().isoformat(),
                'file_count': len(index_data['files']),
                'total_size_bytes': index_data['total_size_bytes'],
                'car_size_bytes': len(car_content),
                'download_instructions': {
                    'description': 'This CAR file contains VFS index metadata, not actual file contents',
                    'usage': 'Extract index to get file CIDs, then download individual files in parallel',
                    'individual_download': 'Use file CIDs to download from IPFS: ipfs get <cid>'
                }
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                'success': True,
                'car_file': str(output_path),
                'metadata_file': str(metadata_path),
                'index_cid': index_cid,
                'car_size_bytes': len(car_content),
                'file_count': len(index_data['files']),
                'bucket_name': bucket_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_car_content(self, index_data: Dict[str, Any], index_cid: str) -> bytes:
        """Create CAR file content from index data."""
        if CBOR_AVAILABLE:
            # Use CBOR encoding for efficient storage
            try:
                # CAR header
                car_header = {
                    'version': 1,
                    'roots': [index_cid]
                }
                
                # Encode index data as CBOR
                index_cbor = cbor2.dumps(index_data)
                
                # Simple CAR structure: header + data block
                header_cbor = cbor2.dumps(car_header)
                header_length = len(header_cbor).to_bytes(4, 'big')
                
                # Create CAR content
                car_content = header_length + header_cbor + index_cbor
                
                return car_content
                
            except Exception as e:
                print(f"⚠️  CBOR encoding failed: {e}, using JSON fallback")
        
        # Fallback to JSON-based CAR simulation
        car_structure = {
            'header': {
                'version': 1,
                'roots': [index_cid],
                'format': 'json_fallback'
            },
            'blocks': [
                {
                    'cid': index_cid,
                    'data': index_data
                }
            ]
        }
        
        return json.dumps(car_structure, indent=2).encode('utf-8')
    
    def generate_all_bucket_cars(self) -> Dict[str, Any]:
        """Generate CAR files for all buckets."""
        try:
            # Get all buckets
            snapshots = self.vfs_manager.get_all_bucket_snapshots()
            
            if not snapshots['success'] or not snapshots['buckets']:
                return {
                    'success': False,
                    'error': 'No buckets found'
                }
            
            results = []
            total_car_size = 0
            
            print(f"🚗 Generating CAR files for {len(snapshots['buckets'])} buckets...")
            
            for bucket_name in snapshots['buckets'].keys():
                print(f"   📦 Processing {bucket_name}...")
                
                result = self.generate_car_from_index(bucket_name)
                
                if result['success']:
                    results.append(result)
                    total_car_size += result['car_size_bytes']
                    print(f"      ✅ CAR: {result['car_size_bytes'] / 1024:.1f} KB, Files: {result['file_count']}")
                else:
                    print(f"      ❌ Failed: {result['error']}")
            
            # Create combined manifest for all CAR files
            combined_manifest = {
                'created_at': datetime.now().isoformat(),
                'total_buckets': len(results),
                'total_car_size_bytes': total_car_size,
                'car_files': results,
                'usage_instructions': {
                    'description': 'These CAR files contain VFS index metadata for parallel file downloads',
                    'workflow': [
                        '1. Extract index from CAR file',
                        '2. Parse file metadata to get individual CIDs',
                        '3. Download files in parallel using: ipfs get <cid>',
                        '4. Verify downloads against metadata'
                    ]
                }
            }
            
            manifest_path = self.car_output_dir / 'car_manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(combined_manifest, f, indent=2)
            
            return {
                'success': True,
                'car_files': results,
                'total_car_size_bytes': total_car_size,
                'manifest_file': str(manifest_path),
                'bucket_count': len(results)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_car_files(self) -> Dict[str, Any]:
        """List all generated CAR files."""
        try:
            car_files = list(self.car_output_dir.glob("*.car"))
            metadata_files = list(self.car_output_dir.glob("*.json"))
            
            car_info = []
            
            for car_file in car_files:
                metadata_file = car_file.with_suffix('.json')
                
                info = {
                    'car_file': str(car_file),
                    'size_bytes': car_file.stat().st_size,
                    'created_at': datetime.fromtimestamp(car_file.stat().st_mtime).isoformat(),
                    'metadata_available': metadata_file.exists()
                }
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        info.update({
                            'bucket_name': metadata.get('bucket_name', ''),
                            'index_cid': metadata.get('index_cid', ''),
                            'file_count': metadata.get('file_count', 0)
                        })
                    except Exception as e:
                        info['metadata_error'] = str(e)
                
                car_info.append(info)
            
            return {
                'success': True,
                'car_files': car_info,
                'car_count': len(car_files),
                'output_directory': str(self.car_output_dir)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """Demo the VFS index CAR generation."""
    print("🚗 VFS Index CAR Generator")
    print("=" * 60)
    
    generator = VFSIndexCARGenerator()
    
    # Generate CAR files for all buckets
    result = generator.generate_all_bucket_cars()
    
    if result['success']:
        print(f"\n✅ Successfully generated CAR files:")
        print(f"   Buckets processed: {result['bucket_count']}")
        print(f"   Total CAR size: {result['total_car_size_bytes'] / 1024:.1f} KB")
        print(f"   Manifest: {result['manifest_file']}")
        
        # List generated files
        list_result = generator.list_car_files()
        if list_result['success']:
            print(f"\n📋 Generated CAR files:")
            for car_info in list_result['car_files']:
                bucket = car_info.get('bucket_name', 'unknown')
                size_kb = car_info['size_bytes'] / 1024
                file_count = car_info.get('file_count', 0)
                print(f"   🗃️  {bucket}: {size_kb:.1f} KB ({file_count} files)")
        
        print(f"\n💡 Usage Instructions:")
        print(f"   1. Share CAR files with recipients")
        print(f"   2. Recipients extract index metadata from CAR")
        print(f"   3. Use individual file CIDs for parallel downloads")
        print(f"   4. Example: ipfs get QmD7T5VzMXR9Zz8qM4c8N5k2z8v3u1L4t6h9q3w2e5r4d")
        
    else:
        print(f"❌ CAR generation failed: {result['error']}")


if __name__ == "__main__":
    main()
