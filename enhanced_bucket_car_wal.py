#!/usr/bin/env python3
"""
Enhanced BucketVFS with CAR-based WAL Integration

This demonstrates how to integrate CAR-based Write-Ahead Logging
into the existing BucketVFS system for better IPFS integration.
"""

import asyncio
import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class CARWALEnhancedBucketVFS:
    """Enhanced BucketVFS with CAR-based WAL support"""
    
    def __init__(self, bucket_name: str, storage_path: Path):
        self.bucket_name = bucket_name
        self.storage_path = storage_path
        
        # Setup directory structure
        self.dirs = {
            "files": storage_path / "files",
            "metadata": storage_path / "metadata", 
            "parquet": storage_path / "parquet",
            "car": storage_path / "car",
            "wal": storage_path / "wal",           # WAL directory
            "wal_car": storage_path / "wal" / "car",  # CAR-based WAL
            "wal_processed": storage_path / "wal" / "processed"  # Processed WAL entries
        }
        
        # Create directories
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
    
    async def add_file_with_car_wal(
        self, 
        file_path: str, 
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
        use_car_wal: bool = True
    ) -> Dict[str, Any]:
        """
        Add file with option to use CAR-based WAL instead of Parquet WAL
        """
        try:
            # Convert content to bytes if needed
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            # Generate file CID
            content_hash = hashlib.sha256(content).hexdigest()
            file_cid = f"bafybei{content_hash[:52]}"
            
            if use_car_wal:
                # Use CAR-based WAL
                wal_result = await self._store_to_car_wal(
                    file_cid, content, file_path, metadata
                )
                
                return {
                    "success": True,
                    "file_cid": file_cid,
                    "file_path": file_path,
                    "size": len(content),
                    "wal_type": "car",
                    "wal_file": wal_result.get("wal_file"),
                    "car_root_cid": wal_result.get("root_cid"),
                    "message": "File staged in CAR-based WAL for daemon processing"
                }
            else:
                # Use traditional Parquet WAL
                wal_result = await self._store_to_parquet_wal(
                    file_cid, content, file_path, metadata
                )
                
                return {
                    "success": True,
                    "file_cid": file_cid,
                    "file_path": file_path,
                    "size": len(content),
                    "wal_type": "parquet",
                    "wal_file": wal_result.get("wal_file"),
                    "message": "File staged in Parquet-based WAL for daemon processing"
                }
                
        except Exception as e:
            logger.error(f"Error adding file with WAL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_to_car_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store content to CAR-based WAL"""
        
        timestamp = int(time.time() * 1000)
        wal_car_path = self.dirs["wal_car"] / f"wal_{timestamp}_{file_cid}.car"
        
        # Create simplified CAR structure
        operation_data = {
            'operation_id': f"add-{file_cid}",
            'operation_type': 'file_add',
            'bucket_name': self.bucket_name,
            'file_cid': file_cid,
            'file_path': file_path,
            'content_size': len(content),
            'created_at_iso': datetime.utcnow().isoformat(),
            'status': 'pending',
            'content_hash': hashlib.sha256(content).hexdigest(),
            'metadata': metadata or {},
            'wal_format': 'car',
            'wal_version': '1.0'
        }
        
        # Create CAR-like structure (simplified)
        car_data = {
            "header": {
                "version": 1,
                "roots": [f"root_{file_cid}"]
            },
            "blocks": {
                f"root_{file_cid}": {
                    "operation": operation_data,
                    "content_block": f"content_{file_cid}"
                },
                f"content_{file_cid}": {
                    "type": "file_content",
                    "path": file_path,
                    "content": content.decode('utf-8', errors='replace') if len(content) < 10000 else f"<binary:{len(content)} bytes>",
                    "size": len(content),
                    "encoding": "utf-8" if len(content) < 10000 else "binary"
                }
            }
        }
        
        # Write CAR file
        with open(wal_car_path, 'w') as f:
            json.dump(car_data, f, indent=2, default=str)
        
        # If content is binary or large, store separately
        if len(content) >= 10000:
            content_path = wal_car_path.with_suffix('.content')
            with open(content_path, 'wb') as f:
                f.write(content)
        
        return {
            "success": True,
            "wal_file": str(wal_car_path),
            "root_cid": f"root_{file_cid}",
            "format": "car"
        }
    
    async def _store_to_parquet_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store content to traditional Parquet WAL (for comparison)"""
        
        # This would be the original implementation
        wal_parquet_path = self.dirs["wal"] / f"{file_cid}.parquet"
        content_file_path = self.dirs["wal"] / f"{file_cid}.content"
        
        # Simplified parquet-like data (JSON for demo)
        wal_data = {
            'operation_id': f"add-{file_cid}",
            'operation_type': 'file_add',
            'bucket_name': self.bucket_name,
            'file_cid': file_cid,
            'file_path': file_path,
            'content_size': len(content),
            'created_at_iso': datetime.utcnow().isoformat(),
            'status': 'pending',
            'content_hash': hashlib.sha256(content).hexdigest(),
            'metadata': json.dumps(metadata or {}),
            'wal_format': 'parquet',
            'wal_version': '1.0'
        }
        
        # Write metadata file (JSON for demo, would be Parquet in reality)
        with open(wal_parquet_path.with_suffix('.json'), 'w') as f:
            json.dump(wal_data, f, indent=2, default=str)
        
        # Write content file
        with open(content_file_path, 'wb') as f:
            f.write(content)
        
        return {
            "success": True,
            "wal_file": str(wal_parquet_path),
            "format": "parquet"
        }
    
    def get_wal_status(self) -> Dict[str, Any]:
        """Get status of WAL entries"""
        
        # Count CAR WAL entries
        car_files = list(self.dirs["wal_car"].glob("wal_*.car"))
        
        # Count Parquet WAL entries
        parquet_files = list(self.dirs["wal"].glob("*.json"))  # Would be *.parquet in reality
        
        # Count processed entries
        processed_files = list(self.dirs["wal_processed"].glob("*"))
        
        return {
            "success": True,
            "wal_stats": {
                "car_entries": len(car_files),
                "parquet_entries": len(parquet_files),
                "processed_entries": len(processed_files),
                "total_pending": len(car_files) + len(parquet_files)
            },
            "car_files": [f.name for f in car_files],
            "parquet_files": [f.name for f in parquet_files]
        }
    
    async def process_car_wal_entry(self, car_file_path: Path) -> Dict[str, Any]:
        """
        Simulate daemon processing of a CAR WAL entry
        (In reality, this would be done by a separate daemon process)
        """
        try:
            # Read CAR file
            with open(car_file_path, 'r') as f:
                car_data = json.load(f)
            
            # Extract operation data
            root_cid = car_data["header"]["roots"][0]
            root_block = car_data["blocks"][root_cid]
            operation_data = root_block["operation"]
            
            # Simulate IPFS upload (would use real IPFS client)
            print(f"🚀 Processing CAR WAL entry: {car_file_path.name}")
            print(f"   Operation: {operation_data['operation_type']}")
            print(f"   File: {operation_data['file_path']}")
            print(f"   Size: {operation_data['content_size']} bytes")
            
            # Simulate successful upload
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Move to processed directory
            processed_path = self.dirs["wal_processed"] / car_file_path.name
            car_file_path.rename(processed_path)
            
            print(f"   ✅ Uploaded to IPFS and moved to processed/")
            
            return {
                "success": True,
                "operation_id": operation_data["operation_id"],
                "file_cid": operation_data["file_cid"],
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"   ❌ Error processing CAR WAL entry: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_all_wal_entries(self) -> Dict[str, Any]:
        """Process all pending WAL entries"""
        
        car_files = list(self.dirs["wal_car"].glob("wal_*.car"))
        
        print(f"🔄 Processing {len(car_files)} CAR WAL entries...")
        
        results = []
        for car_file in car_files:
            result = await self.process_car_wal_entry(car_file)
            results.append(result)
        
        successful = len([r for r in results if r["success"]])
        
        return {
            "success": True,
            "processed_count": successful,
            "total_count": len(car_files),
            "results": results
        }


async def demo_car_wal_integration():
    """Demonstrate CAR WAL integration with BucketVFS"""
    
    print("\n🚗 CAR WAL Integration with BucketVFS")
    print("=" * 50)
    
    # Setup test bucket
    bucket_path = Path("/tmp/enhanced_bucket_demo")
    bucket = CARWALEnhancedBucketVFS("test-bucket", bucket_path)
    
    print(f"📁 Bucket: {bucket.bucket_name}")
    print(f"   Storage: {bucket_path}")
    
    # Test files
    test_files = [
        ("config.yaml", "version: 1.0\nfeatures:\n  - car_wal\n  - ipfs_integration", {"type": "config"}),
        ("data.json", '{"users": 100, "active": true}', {"type": "data", "format": "json"}),
        ("binary_file.dat", b'\x00\x01\x02\x03BINARY_DATA\xff\xfe\xfd', {"type": "binary"})
    ]
    
    print(f"\n📝 Adding files to bucket with CAR WAL...")
    
    # Add files using CAR WAL
    for file_path, content, metadata in test_files:
        print(f"\n  Adding: {file_path}")
        result = await bucket.add_file_with_car_wal(
            file_path=file_path,
            content=content,
            metadata=metadata,
            use_car_wal=True
        )
        
        if result["success"]:
            print(f"    ✅ File CID: {result['file_cid']}")
            print(f"    📦 CAR Root: {result['car_root_cid']}")
            print(f"    📁 WAL File: {Path(result['wal_file']).name}")
        else:
            print(f"    ❌ Error: {result['error']}")
    
    # Add one file using traditional Parquet WAL for comparison
    print(f"\n  Adding with Parquet WAL (for comparison): metadata.xml")
    result = await bucket.add_file_with_car_wal(
        file_path="metadata.xml",
        content="<metadata><version>1.0</version></metadata>",
        metadata={"type": "metadata", "format": "xml"},
        use_car_wal=False
    )
    
    # Show WAL status
    print(f"\n📊 WAL Status:")
    status = bucket.get_wal_status()
    stats = status["wal_stats"]
    print(f"   CAR entries: {stats['car_entries']}")
    print(f"   Parquet entries: {stats['parquet_entries']}")
    print(f"   Total pending: {stats['total_pending']}")
    
    # List CAR files
    print(f"\n📦 CAR WAL Files:")
    for car_file in status["car_files"]:
        print(f"   • {car_file}")
    
    # Simulate daemon processing
    print(f"\n⚙️ Simulating Daemon Processing...")
    process_result = await bucket.process_all_wal_entries()
    
    print(f"\n📈 Processing Results:")
    print(f"   Processed: {process_result['processed_count']}")
    print(f"   Total: {process_result['total_count']}")
    
    # Show final status
    final_status = bucket.get_wal_status()
    final_stats = final_status["wal_stats"]
    print(f"\n📊 Final WAL Status:")
    print(f"   Pending CAR entries: {final_stats['car_entries']}")
    print(f"   Processed entries: {final_stats['processed_entries']}")
    
    return bucket


def show_integration_benefits():
    """Show the benefits of CAR WAL integration"""
    
    print(f"\n💡 Benefits of CAR WAL Integration:")
    print(f"=" * 45)
    
    print(f"\n🚀 IPFS Integration:")
    print(f"   • Files already in IPLD format")
    print(f"   • No conversion needed for IPFS upload")
    print(f"   • Direct compatibility with IPFS tools")
    print(f"   • Content-addressable from the start")
    
    print(f"\n🔒 Integrity & Reliability:")
    print(f"   • Cryptographic verification built-in")
    print(f"   • Self-contained archives")
    print(f"   • Atomic operations (all-or-nothing)")
    print(f"   • Immutable content addressing")
    
    print(f"\n⚡ Performance:")
    print(f"   • Single file per operation")
    print(f"   • Reduced I/O operations")
    print(f"   • Better for network distribution")
    print(f"   • Streaming-friendly format")
    
    print(f"\n🔄 Operational:")
    print(f"   • Simplified daemon processing")
    print(f"   • Better error recovery")
    print(f"   • Easier monitoring/debugging")
    print(f"   • Standard IPFS tooling works")
    
    print(f"\n📊 Migration Strategy:")
    print(f"   1. Add CAR WAL support alongside Parquet")
    print(f"   2. Configure which operations use CAR vs Parquet")
    print(f"   3. Gradually migrate operations to CAR")
    print(f"   4. Keep Parquet for analytics/queries")
    print(f"   5. Optimize based on usage patterns")


if __name__ == "__main__":
    print("🚗 Enhanced BucketVFS with CAR WAL Integration")
    print("=" * 60)
    
    # Show benefits
    show_integration_benefits()
    
    # Run demo
    bucket = asyncio.run(demo_car_wal_integration())
    
    print(f"\n✅ Integration demonstration complete!")
    print(f"   Check {bucket.storage_path} for generated files")
    print(f"   WAL directories: wal/car/ and wal/processed/")
