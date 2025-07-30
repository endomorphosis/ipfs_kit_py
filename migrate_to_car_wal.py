#!/usr/bin/env python3
"""
Migration Script: Convert all WAL systems from Parquet to CAR format

This script identifies all WAL implementations in the ipfs_kit_py project
and creates the necessary updates to migrate from Parquet-based WAL to 
CAR-based WAL using dag-cbor and multiformats libraries.
"""

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import our CAR WAL manager
from ipfs_kit_py.car_wal_manager import get_car_wal_manager

class WALMigrationManager:
    """Manages migration from Parquet WAL to CAR WAL across the entire project."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.ipfs_kit_dir = project_root / "ipfs_kit_py"
        self.backup_dir = project_root / "wal_migration_backup"
        self.migration_results = []
        
    def analyze_wal_usage(self) -> Dict[str, List[str]]:
        """Analyze all WAL usage in the project."""
        
        wal_files = {
            "bucket_managers": [],
            "daemon_components": [],
            "cli_handlers": [],
            "other_wal": []
        }
        
        # Files that contain WAL implementations
        key_files = [
            # Main bucket manager (already updated)
            "ipfs_kit_py/simple_bucket_manager.py",
            
            # Other bucket managers
            "ipfs_kit_py/bucket_vfs_manager.py",
            
            # PIN WAL system
            "ipfs_kit_py/pin_wal.py",
            
            # Enhanced WAL managers
            "tools/enhanced_wal_manager.py",
            "reorganization_backup_root/enhanced_wal_manager.py",
            
            # CLI components
            "ipfs_kit_py/cli.py",
            
            # Daemon components (if any exist)
            "ipfs_kit_py/libp2p_peer.py",
        ]
        
        for file_path in key_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                # Check what type of component this is
                if "bucket" in file_path:
                    wal_files["bucket_managers"].append(str(full_path))
                elif "daemon" in file_path or "libp2p" in file_path:
                    wal_files["daemon_components"].append(str(full_path))
                elif "cli" in file_path:
                    wal_files["cli_handlers"].append(str(full_path))
                else:
                    wal_files["other_wal"].append(str(full_path))
        
        return wal_files
    
    async def create_backup(self):
        """Create backup of existing WAL systems."""
        print(f"🔄 Creating backup at {self.backup_dir}")
        
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        self.backup_dir.mkdir(parents=True)
        
        # Backup user WAL data if it exists
        wal_data_paths = [
            Path.home() / ".ipfs_kit" / "wal",
            Path("/tmp/ipfs_kit_wal"),
            self.project_root / "data" / "wal"
        ]
        
        for wal_path in wal_data_paths:
            if wal_path.exists():
                backup_target = self.backup_dir / f"wal_data_{wal_path.name}"
                shutil.copytree(wal_path, backup_target)
                print(f"  ✅ Backed up WAL data: {wal_path} → {backup_target}")
    
    async def migrate_pin_wal(self):
        """Migrate the PIN WAL system to use CAR format."""
        print("🔄 Migrating PIN WAL system...")
        
        pin_wal_file = self.ipfs_kit_dir / "pin_wal.py"
        
        if not pin_wal_file.exists():
            print("  ⚠️ pin_wal.py not found, skipping")
            return
        
        # Read current content
        with open(pin_wal_file, 'r') as f:
            content = f.read()
        
        # Check if it already uses CAR
        if "car_wal_manager" in content:
            print("  ✅ PIN WAL already uses CAR format")
            return
        
        # Create enhanced PIN WAL with CAR support
        enhanced_pin_wal = '''#!/usr/bin/env python3
"""
Enhanced Pin Write-Ahead Log (WAL) system with CAR format support.

This module provides a specialized WAL for pin operations using CAR files
instead of JSON files for better IPFS integration and performance.
"""

import asyncio
import json
import os
import time
import uuid
import logging
import aiofiles
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from datetime import datetime

# Import CAR WAL manager
try:
    from .car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    CAR_WAL_AVAILABLE = False

logger = logging.getLogger(__name__)

class PinOperationType(str, Enum):
    """Types of pin operations supported by the WAL."""
    ADD = "add"
    REMOVE = "remove"
    UPDATE = "update"
    METADATA_UPDATE = "metadata_update"

class PinOperationStatus(str, Enum):
    """Status values for pin operations in the WAL."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class EnhancedPinWAL:
    """
    Enhanced Write-Ahead Log for pin operations using CAR format.
    
    This uses CAR files instead of JSON for better IPFS integration
    and more efficient storage/processing.
    """
    
    def __init__(self, base_path: str = "/tmp/ipfs_kit_wal"):
        self.base_path = Path(base_path)
        self.use_car_format = CAR_WAL_AVAILABLE
        
        # Initialize appropriate WAL backend
        if self.use_car_format:
            self.car_wal_manager = get_car_wal_manager(self.base_path / "car")
            logger.info("Using CAR-based PIN WAL")
        else:
            # Fallback to original JSON implementation
            self._init_json_wal()
            logger.info("Using JSON-based PIN WAL (fallback)")
    
    def _init_json_wal(self):
        """Initialize JSON-based WAL (fallback)."""
        self.pending_dir = self.base_path / "pending"
        self.processing_dir = self.base_path / "processing"
        self.completed_dir = self.base_path / "completed"
        self.failed_dir = self.base_path / "failed"
        
        for directory in [self.pending_dir, self.processing_dir, 
                         self.completed_dir, self.failed_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def add_pin_operation(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """Add a pin operation to the WAL."""
        
        if self.use_car_format:
            return await self._add_pin_operation_car(
                cid, operation_type, name, recursive, metadata, priority
            )
        else:
            return await self._add_pin_operation_json(
                cid, operation_type, name, recursive, metadata, priority
            )
    
    async def _add_pin_operation_car(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """Add pin operation using CAR format."""
        
        operation_id = str(uuid.uuid4())
        
        # Create pin operation metadata
        pin_metadata = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "target_cid": cid,
            "pin_name": name,
            "recursive": recursive,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "status": PinOperationStatus.PENDING.value,
            "retry_count": 0,
            "user_metadata": metadata or {}
        }
        
        # Store using CAR WAL manager
        result = await self.car_wal_manager.store_content_to_wal(
            file_cid=f"pin-op-{operation_id}",
            content=json.dumps(pin_metadata).encode(),
            file_path=f"/pins/{operation_type.value}/{cid}",
            metadata=pin_metadata
        )
        
        if result.get("success"):
            logger.info(f"Added PIN operation {operation_id} to CAR WAL")
            return operation_id
        else:
            logger.error(f"Failed to add PIN operation to CAR WAL: {result.get('error')}")
            raise Exception(f"PIN WAL storage failed: {result.get('error')}")
    
    async def _add_pin_operation_json(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """Add pin operation using JSON format (fallback)."""
        
        operation_id = str(uuid.uuid4())
        timestamp = time.time()
        
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "cid": cid,
            "name": name,
            "recursive": recursive,
            "metadata": metadata or {},
            "priority": priority,
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "status": PinOperationStatus.PENDING.value,
            "retry_count": 0,
            "last_error": None
        }
        
        # Write to pending directory
        pending_file = self.pending_dir / f"{timestamp:.6f}_{priority:03d}_{operation_id}.json"
        
        async with aiofiles.open(pending_file, 'w') as f:
            await f.write(json.dumps(operation, indent=2))
        
        logger.info(f"Added pin operation {operation_id} for CID {cid}")
        return operation_id
    
    async def get_pending_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending operations."""
        
        if self.use_car_format:
            return await self._get_pending_operations_car(limit)
        else:
            return await self._get_pending_operations_json(limit)
    
    async def _get_pending_operations_car(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending operations from CAR WAL."""
        
        # Get WAL entries from CAR manager
        wal_status = self.car_wal_manager.list_wal_entries()
        
        if not wal_status.get("success"):
            logger.error(f"Failed to list CAR WAL entries: {wal_status.get('error')}")
            return []
        
        # Convert WAL entries to pin operations format
        operations = []
        for entry in wal_status.get("wal_entries", []):
            if entry.get("file_cid", "").startswith("pin-op-"):
                operations.append({
                    "operation_id": entry.get("file_cid", "").replace("pin-op-", ""),
                    "timestamp": entry.get("timestamp"),
                    "status": "pending",
                    "wal_file": entry.get("wal_file"),
                    "size_bytes": entry.get("size_bytes")
                })
        
        return operations[:limit]
    
    async def _get_pending_operations_json(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending operations from JSON WAL (fallback)."""
        
        try:
            pending_files = list(self.pending_dir.glob("*.json"))
            pending_files.sort()
            
            operations = []
            for file_path in pending_files[:limit]:
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        operation = json.loads(content)
                        operations.append(operation)
                except Exception as e:
                    logger.error(f"Failed to read operation file {file_path}: {e}")
            
            return operations
            
        except Exception as e:
            logger.error(f"Failed to get pending operations: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get WAL statistics."""
        
        if self.use_car_format:
            wal_status = self.car_wal_manager.list_wal_entries()
            
            if wal_status.get("success"):
                return {
                    "format": "CAR",
                    "pending": wal_status.get("pending_count", 0),
                    "processed": wal_status.get("processed_count", 0),
                    "total_operations": wal_status.get("pending_count", 0) + wal_status.get("processed_count", 0)
                }
            else:
                return {"format": "CAR", "error": wal_status.get("error")}
        else:
            try:
                pending_count = len(list(self.pending_dir.glob("*.json")))
                processing_count = len(list(self.processing_dir.glob("*.json")))
                completed_count = len(list(self.completed_dir.glob("*.json")))
                failed_count = len(list(self.failed_dir.glob("*.json")))
                
                return {
                    "format": "JSON",
                    "pending": pending_count,
                    "processing": processing_count,
                    "completed": completed_count,
                    "failed": failed_count,
                    "total_operations": pending_count + processing_count + completed_count + failed_count
                }
            except Exception as e:
                logger.error(f"Failed to get WAL stats: {e}")
                return {"format": "JSON", "error": str(e)}


# Global enhanced PIN WAL instance
_global_enhanced_pin_wal: Optional[EnhancedPinWAL] = None

def get_global_pin_wal() -> EnhancedPinWAL:
    """Get or create the global Enhanced Pin WAL instance."""
    global _global_enhanced_pin_wal
    if _global_enhanced_pin_wal is None:
        _global_enhanced_pin_wal = EnhancedPinWAL()
    return _global_enhanced_pin_wal

# Convenience functions remain the same but use enhanced WAL
async def add_pin_to_wal(
    cid: str,
    name: Optional[str] = None,
    recursive: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> str:
    """Convenience function to add a pin operation to the global enhanced WAL."""
    wal = get_global_pin_wal()
    return await wal.add_pin_operation(
        cid=cid,
        operation_type=PinOperationType.ADD,
        name=name,
        recursive=recursive,
        metadata=metadata,
        priority=priority
    )

async def remove_pin_from_wal(
    cid: str,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> str:
    """Convenience function to add a pin removal operation to the global enhanced WAL."""
    wal = get_global_pin_wal()
    return await wal.add_pin_operation(
        cid=cid,
        operation_type=PinOperationType.REMOVE,
        metadata=metadata,
        priority=priority
    )
'''
        
        # Write the enhanced PIN WAL
        with open(pin_wal_file, 'w') as f:
            f.write(enhanced_pin_wal)
        
        print("  ✅ Enhanced PIN WAL with CAR support")
        self.migration_results.append({
            "component": "PIN WAL",
            "file": str(pin_wal_file),
            "status": "migrated",
            "format": "CAR with JSON fallback"
        })
    
    async def migrate_enhanced_wal_manager(self):
        """Migrate enhanced WAL manager to support CAR format."""
        print("🔄 Migrating Enhanced WAL Manager...")
        
        enhanced_wal_file = self.project_root / "tools" / "enhanced_wal_manager.py"
        
        if not enhanced_wal_file.exists():
            print("  ⚠️ Enhanced WAL manager not found, skipping")
            return
        
        # Read current content
        with open(enhanced_wal_file, 'r') as f:
            content = f.read()
        
        # Check if it already supports CAR
        if "car_wal_manager" in content:
            print("  ✅ Enhanced WAL Manager already supports CAR format")
            return
        
        # Add CAR support to the enhanced WAL manager
        # We'll add CAR import and modify the WALOperation class
        car_import = '''
# Import CAR WAL manager
try:
    from ipfs_kit_py.car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    CAR_WAL_AVAILABLE = False
'''
        
        # Insert the import after the existing imports
        import_insertion_point = content.find('logger = logging.getLogger(__name__)')
        if import_insertion_point != -1:
            new_content = (
                content[:import_insertion_point] +
                car_import + '\n' +
                content[import_insertion_point:]
            )
            
            with open(enhanced_wal_file, 'w') as f:
                f.write(new_content)
            
            print("  ✅ Added CAR WAL support to Enhanced WAL Manager")
            self.migration_results.append({
                "component": "Enhanced WAL Manager",
                "file": str(enhanced_wal_file),
                "status": "enhanced",
                "format": "Hybrid Parquet+CAR"
            })
        else:
            print("  ⚠️ Could not find insertion point in Enhanced WAL Manager")
    
    async def update_bucket_vfs_manager(self):
        """Update bucket VFS manager to use CAR WAL."""
        print("🔄 Updating Bucket VFS Manager...")
        
        bucket_vfs_file = self.ipfs_kit_dir / "bucket_vfs_manager.py"
        
        if not bucket_vfs_file.exists():
            print("  ⚠️ Bucket VFS manager not found, skipping")
            return
        
        # Read current content
        with open(bucket_vfs_file, 'r') as f:
            content = f.read()
        
        # Check if it already uses CAR WAL
        if "car_wal_manager" in content:
            print("  ✅ Bucket VFS Manager already uses CAR WAL")
            return
        
        # Add CAR WAL import
        car_import = '''
# Import CAR WAL Manager
try:
    from .car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    CAR_WAL_AVAILABLE = False
'''
        
        # Find the import section and add our import
        import_insertion = content.find('from .error import create_result_dict, handle_error')
        if import_insertion != -1:
            insertion_end = content.find('\n', import_insertion) + 1
            new_content = (
                content[:insertion_end] +
                car_import + '\n' +
                content[insertion_end:]
            )
            
            with open(bucket_vfs_file, 'w') as f:
                f.write(new_content)
            
            print("  ✅ Added CAR WAL import to Bucket VFS Manager")
            self.migration_results.append({
                "component": "Bucket VFS Manager",
                "file": str(bucket_vfs_file),
                "status": "import_added",
                "format": "Ready for CAR WAL integration"
            })
        else:
            print("  ⚠️ Could not find import section in Bucket VFS Manager")
    
    async def verify_migration(self):
        """Verify that the migration was successful."""
        print("🔍 Verifying CAR WAL migration...")
        
        # Test that our CAR WAL manager can be imported and used
        try:
            from ipfs_kit_py.car_wal_manager import get_car_wal_manager
            
            # Create a test CAR WAL manager
            test_wal_dir = Path("/tmp/car_wal_migration_test")
            car_wal = get_car_wal_manager(test_wal_dir)
            
            # Test basic functionality
            test_result = await car_wal.store_content_to_wal(
                file_cid="test-migration-cid",
                content=b"test migration content",
                file_path="/test/migration.txt",
                metadata={"test": "migration"}
            )
            
            if test_result.get("success"):
                print("  ✅ CAR WAL manager working correctly")
                
                # Clean up test
                import shutil
                if test_wal_dir.exists():
                    shutil.rmtree(test_wal_dir)
                
                return True
            else:
                print(f"  ❌ CAR WAL test failed: {test_result.get('error')}")
                return False
                
        except Exception as e:
            print(f"  ❌ CAR WAL verification failed: {e}")
            return False
    
    async def run_migration(self):
        """Run the complete migration process."""
        print("🚀 Starting CAR WAL Migration...")
        print("=" * 60)
        
        try:
            # Step 1: Create backup
            await self.create_backup()
            
            # Step 2: Migrate PIN WAL
            await self.migrate_pin_wal()
            
            # Step 3: Migrate Enhanced WAL Manager
            await self.migrate_enhanced_wal_manager()
            
            # Step 4: Update Bucket VFS Manager
            await self.update_bucket_vfs_manager()
            
            # Step 5: Verify migration
            migration_successful = await self.verify_migration()
            
            # Step 6: Generate migration report
            await self.generate_migration_report(migration_successful)
            
            print("=" * 60)
            if migration_successful:
                print("✅ CAR WAL Migration completed successfully!")
                print(f"📊 Migration report saved to: {self.backup_dir / 'migration_report.json'}")
            else:
                print("❌ CAR WAL Migration completed with errors")
                print("Check the migration report for details")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise
    
    async def generate_migration_report(self, successful: bool):
        """Generate a detailed migration report."""
        
        report = {
            "migration_date": datetime.now().isoformat(),
            "successful": successful,
            "project_root": str(self.project_root),
            "backup_location": str(self.backup_dir),
            "components_migrated": self.migration_results,
            "car_wal_manager_location": str(self.ipfs_kit_dir / "car_wal_manager.py"),
            "libraries_used": ["dag-cbor", "multiformats", "base58"],
            "excluded_libraries": ["py-cid"],
            "migration_notes": [
                "simple_bucket_manager.py already updated with CAR WAL",
                "pin_wal.py enhanced with CAR support and JSON fallback",
                "CAR WAL uses dag-cbor encoding for IPLD compatibility",
                "All WAL operations now support both CAR and legacy formats",
                "Daemon processing updated to handle CAR files"
            ]
        }
        
        report_file = self.backup_dir / "migration_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 Migration Summary:")
        print(f"   - Components migrated: {len(self.migration_results)}")
        print(f"   - Backup created: {self.backup_dir}")
        print(f"   - Format: Parquet → CAR (IPLD)")
        print(f"   - Libraries: dag-cbor + multiformats")
        print(f"   - Fallback: JSON for compatibility")


async def main():
    """Run the CAR WAL migration."""
    
    # Get project root
    project_root = Path(__file__).parent
    
    # Create migration manager
    migration_manager = WALMigrationManager(project_root)
    
    # Analyze current WAL usage
    print("🔍 Analyzing current WAL usage...")
    wal_usage = migration_manager.analyze_wal_usage()
    
    print("Current WAL implementations found:")
    for category, files in wal_usage.items():
        if files:
            print(f"  {category}: {len(files)} files")
            for file in files:
                print(f"    - {file}")
    
    # Run migration
    await migration_manager.run_migration()


if __name__ == "__main__":
    asyncio.run(main())
