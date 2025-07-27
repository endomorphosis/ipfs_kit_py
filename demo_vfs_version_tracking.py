#!/usr/bin/env python3
"""
Comprehensive demonstration of the VFS Version Tracking system.

This script demonstrates the Git-like version control capabilities for virtual
filesystems using IPFS content addressing. Features include:

1. VFS initialization in ~/.ipfs_kit/
2. Filesystem scanning and indexing
3. IPFS CID-based version tracking
4. Git-like commit, log, and checkout operations
5. CAR file generation for version snapshots
6. Integration with bucket VFS system
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# VFS Version Tracker
try:
    from ipfs_kit_py.vfs_version_tracker import (
        get_global_vfs_tracker,
        auto_version_filesystem,
        get_vfs_status,
        get_vfs_history
    )
    VFS_TRACKER_AVAILABLE = True
except ImportError as e:
    logger.error(f"VFS version tracker not available: {e}")
    VFS_TRACKER_AVAILABLE = False

# Bucket VFS for integration testing
try:
    from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
    BUCKET_VFS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Bucket VFS not available: {e}")
    BUCKET_VFS_AVAILABLE = False

# IPFS client
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    IPFS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"IPFS client not available: {e}")
    IPFS_AVAILABLE = False


class VFSVersionDemo:
    """Comprehensive demonstration of VFS version tracking."""
    
    def __init__(self, demo_dir: Optional[str] = None):
        """Initialize demo environment."""
        self.demo_dir = Path(demo_dir) if demo_dir else Path.home() / ".ipfs_kit_demo"
        self.demo_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up demo data directory
        self.data_dir = self.demo_dir / "demo_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize clients
        self.ipfs_client = None
        self.vfs_tracker = None
        self.bucket_manager = None
        
        logger.info(f"Demo environment: {self.demo_dir}")
    
    async def initialize_clients(self):
        """Initialize IPFS and VFS clients."""
        logger.info("Initializing clients...")
        
        # Initialize IPFS client
        if IPFS_AVAILABLE:
            try:
                self.ipfs_client = IPFSSimpleAPI()
                logger.info("✓ IPFS client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize IPFS client: {e}")
        
        # Initialize VFS tracker
        if VFS_TRACKER_AVAILABLE:
            try:
                self.vfs_tracker = get_global_vfs_tracker(
                    vfs_root=str(self.demo_dir),
                    ipfs_client=self.ipfs_client,
                    enable_auto_versioning=True
                )
                logger.info("✓ VFS version tracker initialized")
            except Exception as e:
                logger.error(f"Failed to initialize VFS tracker: {e}")
                return False
        
        # Initialize bucket manager for integration testing
        if BUCKET_VFS_AVAILABLE:
            try:
                self.bucket_manager = get_global_bucket_manager(
                    storage_path=str(self.demo_dir / "buckets"),
                    ipfs_client=self.ipfs_client
                )
                logger.info("✓ Bucket VFS manager initialized")
            except Exception as e:
                logger.warning(f"Could not initialize bucket manager: {e}")
        
        return True
    
    async def create_demo_data(self):
        """Create sample data for version tracking demo."""
        logger.info("Creating demo data...")
        
        # Create sample files
        files_to_create = [
            ("README.md", "# VFS Version Tracking Demo\n\nThis is a demonstration of Git-like VFS versioning."),
            ("config.json", json.dumps({"version": "1.0", "features": ["versioning", "ipfs", "car"]}, indent=2)),
            ("data.txt", "Sample data file\nLine 1\nLine 2\n"),
            ("logs/app.log", "2024-01-01 10:00:00 INFO Application started\n"),
            ("temp/cache.dat", b"Binary cache data"),
        ]
        
        for file_path, content in files_to_create:
            full_path = self.data_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            if isinstance(content, str):
                full_path.write_text(content)
            else:
                full_path.write_bytes(content)
            
            logger.debug(f"Created: {file_path}")
        
        # Create bucket data if available
        if self.bucket_manager:
            await self.create_bucket_demo_data()
        
        logger.info(f"✓ Demo data created in {self.data_dir}")
    
    async def create_bucket_demo_data(self):
        """Create demo data in bucket VFS."""
        try:
            # Create demo bucket
            bucket_result = await self.bucket_manager.create_bucket(
                name="demo-bucket",
                bucket_type=BucketType.UNIXFS,
                vfs_structure=VFSStructureType.UNIXFS,
                description="Demo bucket for VFS versioning"
            )
            
            if bucket_result["success"]:
                bucket = await self.bucket_manager.get_bucket("demo-bucket")
                
                # Add files to bucket
                demo_files = {
                    "project.json": {"name": "VFS Demo Project", "version": "1.0"},
                    "notes.txt": "Project notes\n- VFS versioning\n- IPFS integration",
                    "metadata.json": {"created": datetime.now().isoformat(), "type": "demo"}
                }
                
                for filename, content in demo_files.items():
                    content_str = json.dumps(content, indent=2) if isinstance(content, dict) else content
                    await bucket.add_content(filename, content_str)
                
                logger.info("✓ Demo bucket data created")
        
        except Exception as e:
            logger.warning(f"Could not create bucket demo data: {e}")
    
    async def demonstrate_vfs_init(self):
        """Demonstrate VFS initialization."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: VFS Initialization")
        logger.info("="*50)
        
        # Get initial status
        status_result = await self.vfs_tracker.get_filesystem_status()
        
        if status_result["success"]:
            logger.info("VFS Version Tracking Status:")
            logger.info(f"  - VFS Root: {status_result['vfs_root']}")
            logger.info(f"  - Current HEAD: {status_result['current_head'][:12]}...")
            logger.info(f"  - Auto-versioning: {'enabled' if status_result['auto_versioning'] else 'disabled'}")
            
            if status_result.get("has_uncommitted_changes", False):
                logger.info("  - Status: Changes detected")
            else:
                logger.info("  - Status: No changes")
        
        return status_result
    
    async def demonstrate_filesystem_scan(self):
        """Demonstrate filesystem scanning."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Filesystem Scanning")
        logger.info("="*50)
        
        # Scan filesystem
        filesystem_state = await self.vfs_tracker.scan_filesystem(
            include_buckets=True,
            include_metadata=True
        )
        
        logger.info("Filesystem Scan Results:")
        logger.info(f"  - Files found: {len(filesystem_state['files'])}")
        logger.info(f"  - Buckets found: {len(filesystem_state['buckets'])}")
        logger.info(f"  - Total size: {filesystem_state['metadata']['total_size']:,} bytes")
        
        # Show file breakdown by bucket
        bucket_files = {}
        for file_info in filesystem_state['files']:
            bucket = file_info.get('bucket_name', 'system')
            if bucket not in bucket_files:
                bucket_files[bucket] = []
            bucket_files[bucket].append(file_info)
        
        logger.info("\nFiles by bucket:")
        for bucket, files in bucket_files.items():
            logger.info(f"  - {bucket}: {len(files)} files")
            for file_info in files[:3]:  # Show first 3 files
                logger.info(f"    • {file_info['file_path']} ({file_info['file_size']} bytes)")
            if len(files) > 3:
                logger.info(f"    ... and {len(files) - 3} more files")
        
        # Compute filesystem hash
        fs_hash = await self.vfs_tracker.compute_filesystem_hash(filesystem_state)
        logger.info(f"\nFilesystem Hash: {fs_hash}")
        
        return filesystem_state, fs_hash
    
    async def demonstrate_version_commit(self):
        """Demonstrate version commit creation."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Version Commit")
        logger.info("="*50)
        
        # Create initial commit
        commit_result = await self.vfs_tracker.create_version_snapshot(
            commit_message="Initial demo filesystem state",
            author="VFS-Demo",
            force=True
        )
        
        if commit_result["success"]:
            logger.info("✓ Version commit created:")
            logger.info(f"  - Version CID: {commit_result['version_cid']}")
            logger.info(f"  - Parent CID: {commit_result['parent_cid']}")
            logger.info(f"  - Files: {commit_result['file_count']}")
            logger.info(f"  - Total Size: {commit_result['total_size']:,} bytes")
            logger.info(f"  - CAR File: {commit_result['car_file_cid']}")
        else:
            logger.error(f"✗ Commit failed: {commit_result.get('error', 'Unknown error')}")
        
        return commit_result
    
    async def demonstrate_filesystem_changes(self):
        """Demonstrate filesystem changes and detection."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Filesystem Changes")
        logger.info("="*50)
        
        # Modify existing files
        changes = [
            ("config.json", json.dumps({"version": "1.1", "features": ["versioning", "ipfs", "car", "changes"]}, indent=2)),
            ("data.txt", "Sample data file\nLine 1\nLine 2\nLine 3 - Added!\n"),
            ("new_file.txt", "This is a new file added after initial commit"),
        ]
        
        for file_path, content in changes:
            full_path = self.data_dir / file_path
            full_path.write_text(content)
            logger.info(f"Modified: {file_path}")
        
        # Check for changes
        has_changed, current_hash, previous_hash = await self.vfs_tracker.has_filesystem_changed()
        
        logger.info(f"\nChange Detection:")
        logger.info(f"  - Has changes: {has_changed}")
        logger.info(f"  - Current hash: {current_hash[:12]}...")
        logger.info(f"  - Previous hash: {previous_hash[:12]}...")
        
        if has_changed:
            # Create another commit
            commit_result = await self.vfs_tracker.create_version_snapshot(
                commit_message="Added new features and files",
                author="VFS-Demo"
            )
            
            if commit_result["success"]:
                logger.info(f"✓ Changes committed: {commit_result['version_cid'][:12]}...")
            
            return commit_result
        
        return {"success": False, "message": "No changes detected"}
    
    async def demonstrate_version_history(self):
        """Demonstrate version history display."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Version History")
        logger.info("="*50)
        
        history_result = await self.vfs_tracker.get_version_history(limit=10)
        
        if history_result["success"]:
            versions = history_result.get("versions", [])
            
            logger.info(f"Version History ({len(versions)} entries):")
            
            for i, version in enumerate(versions):
                created_at = version.get("created_at", "Unknown")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                logger.info(f"\n  Commit {i+1}:")
                logger.info(f"    CID: {version.get('version_cid', 'Unknown')}")
                logger.info(f"    Parent: {version.get('parent_cid', 'None')}")
                logger.info(f"    Author: {version.get('author', 'Unknown')}")
                logger.info(f"    Date: {created_at}")
                logger.info(f"    Files: {version.get('file_count', 0)} ({version.get('total_size', 0):,} bytes)")
                logger.info(f"    Message: {version.get('commit_message', 'No message')}")
                logger.info(f"    CAR File: {version.get('car_file_cid', 'None')}")
                
                if i == 0:
                    logger.info("    ^HEAD")
        
        return history_result
    
    async def demonstrate_version_checkout(self):
        """Demonstrate version checkout functionality."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Version Checkout")
        logger.info("="*50)
        
        # Get version history to find a version to checkout
        history_result = await self.vfs_tracker.get_version_history(limit=5)
        
        if history_result["success"] and len(history_result["versions"]) > 1:
            # Checkout previous version
            previous_version = history_result["versions"][1]
            version_cid = previous_version["version_cid"]
            
            logger.info(f"Checking out previous version: {version_cid[:12]}...")
            
            checkout_result = await self.vfs_tracker.checkout_version(version_cid)
            
            if checkout_result["success"]:
                logger.info(f"✓ Checked out version: {version_cid}")
                
                # Show current status
                status_result = await self.vfs_tracker.get_filesystem_status()
                if status_result["success"]:
                    logger.info(f"Current HEAD: {status_result['current_head'][:12]}...")
                
                # Checkout back to latest
                logger.info("\nChecking out back to latest...")
                latest_version = history_result["versions"][0]
                await self.vfs_tracker.checkout_version(latest_version["version_cid"])
                logger.info(f"✓ Back to latest: {latest_version['version_cid'][:12]}...")
                
                return checkout_result
        
        logger.info("Not enough versions for checkout demo")
        return {"success": False, "message": "Insufficient versions"}
    
    async def demonstrate_auto_versioning(self):
        """Demonstrate automatic versioning."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Auto-Versioning")
        logger.info("="*50)
        
        # Create some changes
        auto_changes = [
            ("auto_file1.txt", "Auto-generated file 1"),
            ("auto_file2.json", json.dumps({"auto": True, "timestamp": datetime.now().isoformat()})),
        ]
        
        for file_path, content in auto_changes:
            full_path = self.data_dir / file_path
            full_path.write_text(content)
            logger.info(f"Auto-created: {file_path}")
        
        # Use auto-versioning
        auto_result = await auto_version_filesystem(
            commit_message=f"Auto-commit at {datetime.now().strftime('%H:%M:%S')}"
        )
        
        if auto_result["success"]:
            logger.info("✓ Auto-versioning successful:")
            logger.info(f"  - Version CID: {auto_result['version_cid']}")
            logger.info(f"  - Files: {auto_result['file_count']}")
        else:
            logger.info(f"Auto-versioning result: {auto_result.get('message', 'No changes')}")
        
        return auto_result
    
    async def demonstrate_integration_summary(self):
        """Show integration summary and final status."""
        logger.info("\n" + "="*50)
        logger.info("DEMO: Integration Summary")
        logger.info("="*50)
        
        # Get final status
        status_result = await get_vfs_status()
        
        if status_result["success"]:
            logger.info("Final VFS Status:")
            logger.info(f"  - VFS Root: {status_result['vfs_root']}")
            logger.info(f"  - Current HEAD: {status_result['current_head'][:12]}...")
            logger.info(f"  - Has Changes: {'Yes' if status_result.get('has_uncommitted_changes') else 'No'}")
            
            recent_versions = status_result.get("recent_versions", [])
            if recent_versions:
                logger.info(f"  - Recent Versions: {len(recent_versions)}")
                for version in recent_versions[:3]:
                    logger.info(f"    • {version['version_cid'][:12]}... - {version['commit_message']}")
        
        # Show directory structure
        logger.info(f"\nDemo Directory Structure ({self.demo_dir}):")
        for item in sorted(self.demo_dir.rglob("*")):
            if item.is_file():
                relative_path = item.relative_to(self.demo_dir)
                size = item.stat().st_size
                logger.info(f"  {relative_path} ({size} bytes)")
        
        return status_result
    
    async def run_full_demo(self):
        """Run the complete VFS version tracking demonstration."""
        logger.info("Starting VFS Version Tracking Demo")
        logger.info("=" * 60)
        
        if not VFS_TRACKER_AVAILABLE:
            logger.error("VFS version tracker not available - cannot run demo")
            return False
        
        try:
            # Initialize
            await self.initialize_clients()
            await self.create_demo_data()
            
            # Run demonstrations
            await self.demonstrate_vfs_init()
            await self.demonstrate_filesystem_scan()
            await self.demonstrate_version_commit()
            await self.demonstrate_filesystem_changes()
            await self.demonstrate_version_history()
            await self.demonstrate_version_checkout()
            await self.demonstrate_auto_versioning()
            await self.demonstrate_integration_summary()
            
            logger.info("\n" + "="*60)
            logger.info("✓ VFS Version Tracking Demo Completed Successfully!")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"Demo failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main demo function."""
    # Use temporary directory for demo
    with tempfile.TemporaryDirectory(prefix="vfs_demo_") as temp_dir:
        demo = VFSVersionDemo(demo_dir=temp_dir)
        success = await demo.run_full_demo()
        
        if success:
            print(f"\n🎉 Demo completed successfully!")
            print(f"📁 Demo data was in: {temp_dir} (now cleaned up)")
        else:
            print(f"\n❌ Demo failed - check logs above")
            return 1
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
