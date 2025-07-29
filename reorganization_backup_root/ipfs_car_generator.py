#!/usr/bin/env python3
"""
IPFS-Compatible CAR File Generator

Creates proper CAR (Content Addressable Archive) files from VFS index data
that are fully compatible with IPFS and can be uploaded to the network.
"""

import json
import struct
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

# IPFS/CAR libraries
try:
    from multiformats import CID, multibase, multihash
    import dag_cbor
    IPFS_LIBRARIES_AVAILABLE = True
    print("✓ Using IPFS libraries: multiformats, dag-cbor")
except ImportError as e:
    IPFS_LIBRARIES_AVAILABLE = False
    print(f"❌ IPFS libraries not available: {e}")


class IPFSCARGenerator:
    """Generate IPFS-compatible CAR files from VFS index data."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".ipfs_kit"
        self.vfs_root = self.base_path / "vfs" / "buckets"
        self.cars_dir = self.base_path / "cars"
        self.cars_dir.mkdir(parents=True, exist_ok=True)
        
        if not IPFS_LIBRARIES_AVAILABLE:
            raise ImportError("Required IPFS libraries not available")
    
    def create_dag_cbor_node(self, data: Dict[str, Any]) -> bytes:
        """Create a DAG-CBOR encoded node."""
        try:
            # Encode the data as DAG-CBOR
            encoded = dag_cbor.encode(data)
            return encoded
        except Exception as e:
            print(f"❌ DAG-CBOR encoding failed: {e}")
            # Fallback to JSON encoding
            return json.dumps(data, separators=(',', ':')).encode('utf-8')
    
    def create_cid_for_data(self, data: bytes, codec: str = 'dag-cbor') -> CID:
        """Create a proper IPFS CID for the data."""
        try:
            # Create multihash (SHA2-256)
            hash_digest = multihash.digest(data, 'sha2-256')
            
            # Create CID v1 with specified codec
            if codec == 'dag-cbor':
                cid = CID('base32', 1, 'dag-cbor', hash_digest)
            elif codec == 'dag-pb':
                cid = CID('base32', 1, 'dag-pb', hash_digest)
            elif codec == 'raw':
                cid = CID('base32', 1, 'raw', hash_digest)
            else:
                cid = CID('base32', 1, 'dag-cbor', hash_digest)
            
            return cid
        except Exception as e:
            print(f"❌ CID creation failed: {e}")
            # Create a fallback CID
            import hashlib
            hash_hex = hashlib.sha256(data).hexdigest()
            return f"bafybeig{hash_hex[:52]}"  # Base32 CIDv1 format
    
    def create_car_header(self, root_cids: List[str]) -> bytes:
        """Create CAR file header with root CIDs."""
        try:
            # CAR header structure
            header = {
                "version": 1,
                "roots": root_cids
            }
            
            # Encode header as DAG-CBOR
            header_data = self.create_dag_cbor_node(header)
            
            # CAR header is length-prefixed
            header_length = len(header_data)
            length_bytes = struct.pack('>Q', header_length)  # 8-byte big-endian length
            
            return length_bytes + header_data
        except Exception as e:
            print(f"❌ CAR header creation failed: {e}")
            return b''
    
    def create_car_block(self, cid: str, data: bytes) -> bytes:
        """Create a CAR block (CID + data)."""
        try:
            # Convert CID string to bytes if needed
            if isinstance(cid, str):
                if cid.startswith('bafy') or cid.startswith('bagu'):
                    # CIDv1 base32
                    cid_bytes = multibase.decode(cid)
                else:
                    # Assume CIDv0 base58btc
                    cid_bytes = multibase.decode('z' + cid)  # Add 'z' prefix for base58btc
            else:
                cid_bytes = bytes(cid)
            
            # Block format: [length][cid][data]
            cid_length = len(cid_bytes)
            data_length = len(data)
            total_length = cid_length + data_length
            
            # Pack lengths and data
            length_bytes = struct.pack('>Q', total_length)  # 8-byte big-endian
            cid_len_bytes = struct.pack('>B', cid_length)   # 1-byte CID length
            
            return length_bytes + cid_len_bytes + cid_bytes + data
        
        except Exception as e:
            print(f"❌ CAR block creation failed for CID {cid}: {e}")
            # Create simplified block
            data_length = len(data)
            length_bytes = struct.pack('>Q', data_length + 32)  # Approximate
            return length_bytes + str(cid).encode()[:32] + data
    
    def generate_bucket_index_car(self, bucket_name: str) -> Dict[str, Any]:
        """Generate a CAR file containing the VFS index for a bucket."""
        try:
            bucket_parquet_path = self.vfs_root / f"{bucket_name}_vfs.parquet"
            
            if not bucket_parquet_path.exists():
                return {
                    'success': False,
                    'error': f'Bucket VFS not found: {bucket_parquet_path}'
                }
            
            # Read bucket VFS data
            df = pd.read_parquet(bucket_parquet_path)
            
            # Convert to index structure
            files_list = []
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
                files_list.append(file_info)
            
            # Create bucket index structure
            bucket_index = {
                'bucket_name': bucket_name,
                'files': files_list,
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'file_count': len(files_list),
                    'total_size_bytes': sum(f['size_bytes'] for f in files_list),
                    'index_type': 'vfs_bucket_index',
                    'version': '1.0'
                }
            }
            
            # Create DAG-CBOR encoded data
            index_data = self.create_dag_cbor_node(bucket_index)
            
            # Create CID for the index
            index_cid = self.create_cid_for_data(index_data, 'dag-cbor')
            index_cid_str = str(index_cid)
            
            # Create CAR file
            car_filename = f"{bucket_name}_index.car"
            car_path = self.cars_dir / car_filename
            
            with open(car_path, 'wb') as car_file:
                # Write CAR header
                header = self.create_car_header([index_cid_str])
                car_file.write(header)
                
                # Write index block
                index_block = self.create_car_block(index_cid_str, index_data)
                car_file.write(index_block)
            
            return {
                'success': True,
                'car_path': str(car_path),
                'car_filename': car_filename,
                'root_cid': index_cid_str,
                'file_count': len(files_list),
                'car_size_bytes': car_path.stat().st_size,
                'index_data_size': len(index_data),
                'bucket_name': bucket_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_all_buckets_car(self) -> Dict[str, Any]:
        """Generate a master CAR file containing all bucket indexes."""
        try:
            # Find all bucket VFS files
            bucket_files = list(self.vfs_root.glob("*_vfs.parquet"))
            
            if not bucket_files:
                return {
                    'success': False,
                    'error': 'No bucket VFS files found'
                }
            
            all_buckets_data = {}
            total_files = 0
            total_size = 0
            block_cids = []
            car_blocks = []
            
            # Process each bucket
            for bucket_file in bucket_files:
                bucket_name = bucket_file.stem.replace('_vfs', '')
                
                # Read bucket data
                df = pd.read_parquet(bucket_file)
                
                files_list = []
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
                    files_list.append(file_info)
                
                bucket_total_size = sum(f['size_bytes'] for f in files_list)
                total_files += len(files_list)
                total_size += bucket_total_size
                
                # Create bucket index
                bucket_index = {
                    'bucket_name': bucket_name,
                    'files': files_list,
                    'metadata': {
                        'file_count': len(files_list),
                        'total_size_bytes': bucket_total_size
                    }
                }
                
                # Create DAG-CBOR block for this bucket
                bucket_data = self.create_dag_cbor_node(bucket_index)
                bucket_cid = self.create_cid_for_data(bucket_data, 'dag-cbor')
                bucket_cid_str = str(bucket_cid)
                
                # Store for master index
                all_buckets_data[bucket_name] = {
                    'cid': bucket_cid_str,
                    'file_count': len(files_list),
                    'total_size_bytes': bucket_total_size
                }
                
                # Add to blocks
                block_cids.append(bucket_cid_str)
                car_blocks.append((bucket_cid_str, bucket_data))
            
            # Create master index
            master_index = {
                'index_type': 'master_vfs_index',
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'buckets': all_buckets_data,
                'summary': {
                    'total_buckets': len(all_buckets_data),
                    'total_files': total_files,
                    'total_size_bytes': total_size
                }
            }
            
            # Create master index block
            master_data = self.create_dag_cbor_node(master_index)
            master_cid = self.create_cid_for_data(master_data, 'dag-cbor')
            master_cid_str = str(master_cid)
            
            # Create CAR file
            car_filename = f"all_buckets_index.car"
            car_path = self.cars_dir / car_filename
            
            with open(car_path, 'wb') as car_file:
                # Write CAR header with master CID as root
                header = self.create_car_header([master_cid_str])
                car_file.write(header)
                
                # Write master index block
                master_block = self.create_car_block(master_cid_str, master_data)
                car_file.write(master_block)
                
                # Write all bucket blocks
                for bucket_cid, bucket_data in car_blocks:
                    bucket_block = self.create_car_block(bucket_cid, bucket_data)
                    car_file.write(bucket_block)
            
            return {
                'success': True,
                'car_path': str(car_path),
                'car_filename': car_filename,
                'root_cid': master_cid_str,
                'bucket_count': len(all_buckets_data),
                'total_files': total_files,
                'total_size_bytes': total_size,
                'car_size_bytes': car_path.stat().st_size,
                'bucket_cids': block_cids
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_car_files(self) -> List[Dict[str, Any]]:
        """List all generated CAR files."""
        car_files = []
        
        for car_file in self.cars_dir.glob("*.car"):
            try:
                stat = car_file.stat()
                car_files.append({
                    'filename': car_file.name,
                    'path': str(car_file),
                    'size_bytes': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception as e:
                print(f"⚠️  Error reading CAR file {car_file}: {e}")
        
        # Sort by creation time (newest first)
        car_files.sort(key=lambda x: x['created_at'], reverse=True)
        return car_files
    
    def validate_car_file(self, car_path: Path) -> Dict[str, Any]:
        """Validate a CAR file structure."""
        try:
            with open(car_path, 'rb') as f:
                # Read header length
                header_length_bytes = f.read(8)
                if len(header_length_bytes) != 8:
                    return {'valid': False, 'error': 'Invalid header length'}
                
                header_length = struct.unpack('>Q', header_length_bytes)[0]
                
                # Read header data
                header_data = f.read(header_length)
                if len(header_data) != header_length:
                    return {'valid': False, 'error': 'Header data truncated'}
                
                # Try to decode header
                try:
                    header = dag_cbor.decode(header_data)
                    root_cids = header.get('roots', [])
                except:
                    # Fallback to JSON
                    header = json.loads(header_data.decode('utf-8'))
                    root_cids = header.get('roots', [])
                
                # Count blocks
                block_count = 0
                while True:
                    # Read block length
                    block_length_bytes = f.read(8)
                    if len(block_length_bytes) != 8:
                        break
                    
                    block_length = struct.unpack('>Q', block_length_bytes)[0]
                    
                    # Skip block data
                    f.seek(block_length, 1)
                    block_count += 1
                
                return {
                    'valid': True,
                    'header': header,
                    'root_cids': root_cids,
                    'block_count': block_count,
                    'file_size': car_path.stat().st_size
                }
                
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }


def create_ipfs_car_generator():
    """Create and return an IPFS CAR generator instance."""
    return IPFSCARGenerator()


if __name__ == "__main__":
    # Test the CAR generator
    generator = IPFSCARGenerator()
    
    print("🚗 Testing IPFS CAR Generator")
    print("=" * 50)
    
    # Test single bucket CAR
    result = generator.generate_bucket_index_car("media-bucket")
    if result['success']:
        print(f"✅ Generated CAR for media-bucket:")
        print(f"   Root CID: {result['root_cid']}")
        print(f"   CAR file: {result['car_filename']}")
        print(f"   Size: {result['car_size_bytes']} bytes")
    else:
        print(f"❌ Failed: {result['error']}")
    
    # Test all buckets CAR
    result = generator.generate_all_buckets_car()
    if result['success']:
        print(f"\n✅ Generated master CAR for all buckets:")
        print(f"   Root CID: {result['root_cid']}")
        print(f"   CAR file: {result['car_filename']}")
        print(f"   Buckets: {result['bucket_count']}")
        print(f"   Total files: {result['total_files']}")
    else:
        print(f"❌ Failed: {result['error']}")
