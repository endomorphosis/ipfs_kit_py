#!/usr/bin/env python3
"""
Demonstration: CAR-based Write-Ahead Log (WAL) for IPFS Kit

This shows how we could convert the current Parquet-based WAL system 
to use CAR (Content Addressable Archive) files instead.

Benefits of CAR-based WAL:
1. Native IPFS/IPLD format - no conversion needed for IPFS storage
2. Content-addressable by design
3. Can contain multiple files in a single archive
4. Maintains cryptographic integrity
5. More efficient for IPFS network distribution
6. Better integration with IPFS ecosystem tools

Current WAL: file.content + metadata.parquet → daemon processes
Proposed WAL: file.car (contains content + metadata) → daemon processes
"""

import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

# Simulate CAR file creation (in reality, would use py-ipld-car or similar)
class MockCARFile:
    """Mock CAR file implementation for demonstration"""
    
    def __init__(self, car_path: Path):
        self.car_path = car_path
        self.blocks = []
        self.root_cid = None
    
    def add_file(self, path: str, content: bytes, metadata: Dict[str, Any] = None):
        """Add a file to the CAR archive"""
        # Generate CID for content (simplified)
        content_hash = hashlib.sha256(content).hexdigest()
        content_cid = f"bafybei{content_hash[:52]}"  # Simplified CID
        
        # Create IPLD block for file content
        file_block = {
            "path": path,
            "content": content.decode('utf-8', errors='replace') if len(content) < 1000 else f"<binary:{len(content)} bytes>",
            "size": len(content),
            "metadata": metadata or {}
        }
        
        self.blocks.append({
            "cid": content_cid,
            "type": "file_content",
            "data": file_block
        })
        
        return content_cid
    
    def add_metadata(self, operation_data: Dict[str, Any]):
        """Add operation metadata to the CAR archive"""
        meta_hash = hashlib.sha256(json.dumps(operation_data, sort_keys=True).encode()).hexdigest()
        meta_cid = f"bafybei{meta_hash[:52]}"
        
        self.blocks.append({
            "cid": meta_cid,
            "type": "operation_metadata", 
            "data": operation_data
        })
        
        return meta_cid
    
    def write(self):
        """Write the CAR file to disk"""
        # Create root block that references all other blocks
        root_data = {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "blocks": [block["cid"] for block in self.blocks],
            "block_count": len(self.blocks)
        }
        
        root_hash = hashlib.sha256(json.dumps(root_data, sort_keys=True).encode()).hexdigest()
        self.root_cid = f"bafybei{root_hash[:52]}"
        
        # Write CAR file (simplified structure)
        car_data = {
            "header": {
                "version": 1,
                "roots": [self.root_cid]
            },
            "blocks": {
                self.root_cid: root_data,
                **{block["cid"]: block["data"] for block in self.blocks}
            }
        }
        
        with open(self.car_path, 'w') as f:
            json.dump(car_data, f, indent=2, default=str)
        
        return self.root_cid


class CARBasedWALManager:
    """CAR-based Write-Ahead Log Manager"""
    
    def __init__(self, wal_dir: Path):
        self.wal_dir = wal_dir
        self.wal_dir.mkdir(parents=True, exist_ok=True)
        
    async def store_content_to_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store file content to WAL as CAR file instead of Parquet"""
        
        try:
            # Create CAR file named by operation timestamp and file CID
            timestamp = int(time.time() * 1000)  # milliseconds
            wal_car_path = self.wal_dir / f"wal_{timestamp}_{file_cid}.car"
            
            # Initialize CAR file
            car_file = MockCARFile(wal_car_path)
            
            # Add the actual file content to CAR
            content_cid = car_file.add_file(file_path, content, metadata)
            
            # Add operation metadata to CAR
            operation_metadata = {
                'operation_id': f"file-add-{file_cid}",
                'operation_type': 'file_add',
                'file_cid': file_cid,
                'content_cid': content_cid,  # CID of content within CAR
                'file_path': file_path,
                'content_size': len(content),
                'created_at_iso': datetime.utcnow().isoformat(),
                'status': 'pending',
                'content_hash': hashlib.sha256(content).hexdigest(),
                'metadata': metadata or {},
                'wal_format': 'car',
                'wal_version': '1.0'
            }
            
            meta_cid = car_file.add_metadata(operation_metadata)
            
            # Write CAR file
            root_cid = car_file.write()
            
            print(f"✅ Stored content to CAR-based WAL:")
            print(f"   WAL file: {wal_car_path}")
            print(f"   Root CID: {root_cid}")
            print(f"   Content CID: {content_cid}")
            print(f"   Metadata CID: {meta_cid}")
            print(f"   File size: {len(content)} bytes")
            
            return {
                "success": True,
                "wal_file": str(wal_car_path),
                "root_cid": root_cid,
                "content_cid": content_cid,
                "metadata_cid": meta_cid,
                "format": "car"
            }
            
        except Exception as e:
            print(f"❌ Error storing content to CAR WAL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_wal_entries(self) -> Dict[str, Any]:
        """List all WAL entries"""
        car_files = list(self.wal_dir.glob("wal_*.car"))
        
        entries = []
        for car_file in car_files:
            try:
                with open(car_file, 'r') as f:
                    car_data = json.load(f)
                
                root_cid = car_data["header"]["roots"][0]
                root_block = car_data["blocks"][root_cid]
                
                # Find operation metadata
                operation_metadata = None
                for block_cid in root_block["blocks"]:
                    block = car_data["blocks"][block_cid]
                    if isinstance(block, dict) and block.get("operation_type"):
                        operation_metadata = block
                        break
                
                if operation_metadata:
                    entries.append({
                        "wal_file": car_file.name,
                        "root_cid": root_cid,
                        "operation": operation_metadata,
                        "created_at": operation_metadata.get("created_at_iso"),
                        "status": operation_metadata.get("status", "unknown")
                    })
                    
            except Exception as e:
                print(f"⚠️ Error reading {car_file}: {e}")
        
        return {
            "success": True,
            "entries": sorted(entries, key=lambda x: x.get("created_at", "")),
            "total_count": len(entries)
        }


def compare_wal_formats():
    """Compare Parquet vs CAR WAL formats"""
    
    print("🔄 WAL Format Comparison: Parquet vs CAR")
    print("=" * 60)
    
    print("\n📊 Current Parquet-based WAL:")
    print("  Structure:")
    print("    - {cid}.parquet (operation metadata)")
    print("    - {cid}.content (raw file content)")
    print("  Advantages:")
    print("    ✅ Efficient for analytics/queries")
    print("    ✅ Schema enforcement")  
    print("    ✅ Columnar compression")
    print("  Disadvantages:")
    print("    ❌ Two separate files per operation")
    print("    ❌ Requires conversion to IPFS format")
    print("    ❌ Not content-addressable by default")
    print("    ❌ Extra step for IPFS integration")
    
    print("\n🚗 Proposed CAR-based WAL:")
    print("  Structure:")
    print("    - wal_{timestamp}_{cid}.car (content + metadata in one file)")
    print("  Advantages:")
    print("    ✅ Native IPFS/IPLD format")
    print("    ✅ Content-addressable by design")
    print("    ✅ Single file per operation")
    print("    ✅ Direct IPFS compatibility")
    print("    ✅ Cryptographic integrity")
    print("    ✅ Better for distribution")
    print("  Disadvantages:")
    print("    ❌ Less efficient for complex queries")
    print("    ❌ Requires CAR parsing tools")
    print("    ❌ Larger file sizes (no columnar compression)")
    
    print("\n🎯 Recommendation:")
    print("  Use CAR-based WAL for:")
    print("    • File ingestion/staging")
    print("    • IPFS-first workflows")
    print("    • Content distribution")
    print("    • Integrity-critical operations")
    print("  Keep Parquet for:")
    print("    • Analytics and queries")
    print("    • Final storage/indexing")
    print("    • Cross-bucket analysis")


async def demo_car_wal():
    """Demonstrate CAR-based WAL functionality"""
    
    print("\n🚗 CAR-based WAL Demonstration")
    print("=" * 50)
    
    # Setup
    wal_dir = Path("/tmp/car_wal_demo")
    car_wal = CARBasedWALManager(wal_dir)
    
    # Test data
    test_files = [
        {
            "path": "documents/readme.txt",
            "content": b"Hello, IPFS Kit! This is a test document for CAR-based WAL.",
            "metadata": {"type": "document", "author": "demo"}
        },
        {
            "path": "data/config.json", 
            "content": b'{"version": "1.0", "enabled": true, "features": ["car", "wal"]}',
            "metadata": {"type": "config", "format": "json"}
        },
        {
            "path": "images/logo.png",
            "content": b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00...',  # Mock binary
            "metadata": {"type": "image", "format": "png", "size": "small"}
        }
    ]
    
    print(f"\n📁 WAL Directory: {wal_dir}")
    
    # Store files in CAR-based WAL
    results = []
    for i, file_data in enumerate(test_files):
        print(f"\n📝 Storing file {i+1}/3: {file_data['path']}")
        
        # Generate file CID (in real system, would be computed properly)
        file_cid = f"bafybei{hashlib.sha256(file_data['content']).hexdigest()[:52]}"
        
        result = await car_wal.store_content_to_wal(
            file_cid=file_cid,
            content=file_data['content'],
            file_path=file_data['path'],
            metadata=file_data['metadata']
        )
        results.append(result)
    
    # List all WAL entries
    print(f"\n📋 WAL Entry Summary:")
    wal_list = car_wal.list_wal_entries()
    
    if wal_list["success"]:
        print(f"   Total entries: {wal_list['total_count']}")
        for entry in wal_list["entries"]:
            print(f"   • {entry['wal_file']}")
            print(f"     Operation: {entry['operation']['operation_type']}")
            print(f"     File: {entry['operation']['file_path']}")
            print(f"     Status: {entry['status']}")
    
    # Show daemon processing implications
    print(f"\n⚙️ Daemon Processing with CAR WAL:")
    print(f"   1. Daemon scans {wal_dir} for *.car files")
    print(f"   2. For each CAR file:")
    print(f"      • Parse CAR header to get root CID")
    print(f"      • Extract operation metadata")
    print(f"      • Extract file content (already in IPLD format)")
    print(f"      • Direct upload to IPFS (no conversion needed)")
    print(f"      • Update operation status")
    print(f"   3. Move processed CAR to completed/ directory")
    
    print(f"\n🔄 Migration Path:")
    print(f"   Phase 1: Support both Parquet and CAR WAL formats")
    print(f"   Phase 2: Migrate existing Parquet WAL to CAR format")
    print(f"   Phase 3: Switch new operations to CAR-only")
    print(f"   Phase 4: Remove Parquet WAL support")
    
    return results


if __name__ == "__main__":
    import asyncio
    
    print("🚗 CAR-based WAL Demonstration for IPFS Kit")
    print("=" * 60)
    
    # Run comparison
    compare_wal_formats()
    
    # Run demo
    asyncio.run(demo_car_wal())
    
    print(f"\n✅ Demonstration complete!")
    print(f"   Check /tmp/car_wal_demo/ for generated CAR files")
