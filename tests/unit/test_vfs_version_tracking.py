#!/usr/bin/env python3
"""
Simple test of VFS version tracking functionality.

This script performs basic validation of the VFS version tracking system
to ensure core functionality works as expected.
"""

import anyio
import json
import logging
import tempfile
from pathlib import Path
import pytest

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.anyio

async def test_vfs_version_tracking():
    """Test basic VFS version tracking functionality."""
    
    # Test imports
    try:
        from ipfs_kit_py.vfs_version_tracker import get_global_vfs_tracker
        logger.info("✓ VFS version tracker import successful")
    except ImportError as e:
        logger.error(f"✗ VFS version tracker import failed: {e}")
        return False
    
    # Create temporary test directory
    with tempfile.TemporaryDirectory(prefix="vfs_test_") as temp_dir:
        temp_path = Path(temp_dir)
        test_data_dir = temp_path / "test_data"
        test_data_dir.mkdir()
        
        logger.info(f"Using test directory: {temp_dir}")
        
        try:
            # Initialize VFS tracker
            vfs_tracker = get_global_vfs_tracker(vfs_root=str(temp_path))
            logger.info("✓ VFS tracker initialized")
            
            # Create test files
            test_files = [
                ("test1.txt", "Test file 1 content"),
                ("test2.json", json.dumps({"test": "data"})),
                ("subdir/test3.txt", "Test file 3 in subdirectory")
            ]
            
            for file_path, content in test_files:
                full_path = test_data_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
            
            logger.info(f"✓ Created {len(test_files)} test files")
            
            # Test filesystem scan
            filesystem_state = await vfs_tracker.scan_filesystem()
            logger.info(f"✓ Filesystem scan found {len(filesystem_state['files'])} files")
            
            # Test filesystem hashing
            fs_hash = await vfs_tracker.compute_filesystem_hash(filesystem_state)
            logger.info(f"✓ Computed filesystem hash: {fs_hash[:12]}...")
            
            # Test change detection
            has_changed, current_hash, previous_hash = await vfs_tracker.has_filesystem_changed()
            logger.info(f"✓ Change detection: has_changed={has_changed}")
            
            # Test version commit
            commit_result = await vfs_tracker.create_version_snapshot(
                commit_message="Test commit",
                author="VFS-Test",
                force=True
            )
            
            if commit_result["success"]:
                logger.info(f"✓ Version commit successful: {commit_result['version_cid'][:12]}...")
            else:
                logger.error(f"✗ Version commit failed: {commit_result.get('error')}")
                return False
            
            # Test version history
            history_result = await vfs_tracker.get_version_history(limit=5)
            if history_result["success"]:
                versions = history_result["versions"]
                logger.info(f"✓ Version history retrieved: {len(versions)} versions")
            else:
                logger.error(f"✗ Version history failed: {history_result.get('error')}")
                return False
            
            # Test filesystem status
            status_result = await vfs_tracker.get_filesystem_status()
            if status_result["success"]:
                logger.info(f"✓ Filesystem status retrieved")
            else:
                logger.error(f"✗ Filesystem status failed: {status_result.get('error')}")
                return False
            
            logger.info("✓ All VFS version tracking tests passed!")
            return True
            
        except Exception as e:
            logger.error(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False

async def test_vfs_cli():
    """Test VFS CLI functionality."""
    
    try:
        from ipfs_kit_py.vfs_version_cli import VFSVersionCLI
        logger.info("✓ VFS CLI import successful")
        
        # Basic CLI instantiation test
        cli = VFSVersionCLI()
        logger.info("✓ VFS CLI instantiation successful")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ VFS CLI import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ VFS CLI test failed: {e}")
        return False

async def test_vfs_mcp_tools():
    """Test VFS MCP tools functionality."""
    
    try:
        from mcp.vfs_version_mcp_tools import get_vfs_version_tools, get_vfs_version_handlers
        logger.info("✓ VFS MCP tools import successful")
        
        # Test tools and handlers
        tools = get_vfs_version_tools()
        handlers = get_vfs_version_handlers()
        
        logger.info(f"✓ VFS MCP tools available: {len(tools)} tools, {len(handlers)} handlers")
        
        # Check tool names
        tool_names = [tool.name for tool in tools]
        expected_tools = ["vfs_init", "vfs_status", "vfs_commit", "vfs_log", "vfs_scan"]
        
        for expected_tool in expected_tools:
            if expected_tool in tool_names:
                logger.info(f"✓ Tool '{expected_tool}' available")
            else:
                logger.warning(f"⚠ Tool '{expected_tool}' missing")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ VFS MCP tools import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ VFS MCP tools test failed: {e}")
        return False

async def main():
    """Run all VFS version tracking tests."""
    logger.info("Starting VFS Version Tracking Tests")
    logger.info("="*50)
    
    all_passed = True
    
    # Test core functionality
    logger.info("\n1. Testing Core VFS Version Tracking...")
    if not await test_vfs_version_tracking():
        all_passed = False
    
    # Test CLI
    logger.info("\n2. Testing VFS CLI...")
    if not await test_vfs_cli():
        all_passed = False
    
    # Test MCP tools
    logger.info("\n3. Testing VFS MCP Tools...")
    if not await test_vfs_mcp_tools():
        all_passed = False
    
    # Summary
    logger.info("\n" + "="*50)
    if all_passed:
        logger.info("🎉 All VFS version tracking tests PASSED!")
    else:
        logger.info("❌ Some VFS version tracking tests FAILED!")
    logger.info("="*50)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    import sys
    exit_code = anyio.run(main)
    sys.exit(exit_code)
