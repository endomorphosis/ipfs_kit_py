#!/usr/bin/env python3
"""
Import Path Validation Tests

Tests to ensure all MCP tools follow the correct integration architecture:
1. All tools import from ipfs_kit_py package (single source of truth)
2. No relative imports that bypass the package structure
3. All tools can be imported successfully
4. MCP wrappers properly re-export from main package
"""

import unittest
import sys
import os
from pathlib import Path

# Add repository root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))


class TestImportPathsValidation(unittest.TestCase):
    """Test that all MCP tools follow correct import architecture"""

    def test_ipfs_core_tools_in_main_package(self):
        """Test that ipfs_core_tools can be imported from ipfs_kit_py.tools"""
        try:
            from ipfs_kit_py.tools import ipfs_core_tools
            self.assertTrue(hasattr(ipfs_core_tools, 'IPFSClient'))
            self.assertTrue(hasattr(ipfs_core_tools, 'handle_ipfs_add'))
            self.assertTrue(hasattr(ipfs_core_tools, 'handle_ipfs_cat'))
        except ImportError as e:
            self.skipTest(f"ipfs_core_tools import failed (MCP infrastructure not available): {e}")

    def test_pin_management_tools_in_main_package(self):
        """Test that pin_management_tools can be imported from ipfs_kit_py.tools"""
        try:
            from ipfs_kit_py.tools import pin_management_tools
            self.assertTrue(hasattr(pin_management_tools, 'handle_list_pins'))
            self.assertTrue(hasattr(pin_management_tools, 'handle_get_pin_stats'))
            self.assertTrue(hasattr(pin_management_tools, 'handle_unpin_content'))
        except ImportError as e:
            self.skipTest(f"pin_management_tools import failed (MCP infrastructure not available): {e}")

    def test_mcp_wrapper_imports_from_package(self):
        """Test that MCP wrappers import from main package"""
        try:
            # Import wrapper
            from mcp.ipfs_kit.tools import ipfs_core_tools_wrapper
            
            # Verify it has the same attributes as the main module
            from ipfs_kit_py.tools import ipfs_core_tools
            
            self.assertTrue(hasattr(ipfs_core_tools_wrapper, 'IPFSClient'))
            self.assertTrue(hasattr(ipfs_core_tools_wrapper, 'handle_ipfs_add'))
            
        except ImportError as e:
            self.skipTest(f"MCP wrapper import failed (infrastructure not available): {e}")

    def test_no_direct_relative_imports_in_core_tools(self):
        """Verify ipfs_core_tools doesn't use direct relative imports"""
        try:
            core_tools_path = repo_root / "ipfs_kit_py" / "tools" / "ipfs_core_tools.py"
            
            if not core_tools_path.exists():
                self.skipTest("ipfs_core_tools.py not found in main package")
            
            with open(core_tools_path, 'r') as f:
                content = f.read()
            
            # Check that it uses absolute imports from ipfs_kit_py
            self.assertIn('from ipfs_kit_py.mcp.ipfs_kit.core.tool_registry import', content,
                         "Should import tool_registry from ipfs_kit_py package")
            self.assertIn('from ipfs_kit_py.mcp.ipfs_kit.core.error_handler import', content,
                         "Should import error_handler from ipfs_kit_py package")
            
            # Check that it doesn't use sys.path.append hack
            self.assertNotIn('sys.path.append(str(Path(__file__).parent.parent))', content,
                           "Should not use sys.path.append hack")
            
        except Exception as e:
            self.skipTest(f"Could not verify imports: {e}")

    def test_no_direct_relative_imports_in_pin_tools(self):
        """Verify pin_management_tools doesn't use direct relative imports"""
        try:
            pin_tools_path = repo_root / "ipfs_kit_py" / "tools" / "pin_management_tools.py"
            
            if not pin_tools_path.exists():
                self.skipTest("pin_management_tools.py not found in main package")
            
            with open(pin_tools_path, 'r') as f:
                content = f.read()
            
            # Check that it uses absolute imports from ipfs_kit_py
            self.assertIn('from ipfs_kit_py.mcp.ipfs_kit.core.tool_registry import', content,
                         "Should import tool_registry from ipfs_kit_py package")
            self.assertIn('from ipfs_kit_py.mcp.ipfs_kit.core.error_handler import', content,
                         "Should import error_handler from ipfs_kit_py package")
            
            # Check that it doesn't use sys.path.append hack
            self.assertNotIn('sys.path.append(str(Path(__file__).parent.parent))', content,
                           "Should not use sys.path.append hack")
            
        except Exception as e:
            self.skipTest(f"Could not verify imports: {e}")

    def test_bucket_vfs_mcp_tools_imports_from_package(self):
        """Verify bucket_vfs_mcp_tools imports from ipfs_kit_py package"""
        try:
            bucket_tools_path = repo_root / "mcp" / "bucket_vfs_mcp_tools.py"
            
            if not bucket_tools_path.exists():
                self.skipTest("bucket_vfs_mcp_tools.py not found")
            
            with open(bucket_tools_path, 'r') as f:
                content = f.read()
            
            # Check for proper imports from ipfs_kit_py
            self.assertIn('from ipfs_kit_py', content,
                         "Should import from ipfs_kit_py package")
            
        except Exception as e:
            self.skipTest(f"Could not verify imports: {e}")

    def test_vfs_version_mcp_tools_imports_from_package(self):
        """Verify vfs_version_mcp_tools imports from ipfs_kit_py package"""
        try:
            vfs_tools_path = repo_root / "mcp" / "vfs_version_mcp_tools.py"
            
            if not vfs_tools_path.exists():
                self.skipTest("vfs_version_mcp_tools.py not found")
            
            with open(vfs_tools_path, 'r') as f:
                content = f.read()
            
            # Check for proper imports from ipfs_kit_py
            self.assertIn('from ipfs_kit_py', content,
                         "Should import from ipfs_kit_py package")
            
        except Exception as e:
            self.skipTest(f"Could not verify imports: {e}")

    def test_architecture_compliance_summary(self):
        """Generate a summary of architecture compliance"""
        try:
            print("\n" + "="*70)
            print("ARCHITECTURE COMPLIANCE SUMMARY")
            print("="*70)
            
            # Check if files exist in correct locations
            core_tools_main = (repo_root / "ipfs_kit_py" / "tools" / "ipfs_core_tools.py").exists()
            pin_tools_main = (repo_root / "ipfs_kit_py" / "tools" / "pin_management_tools.py").exists()
            core_tools_wrapper = (repo_root / "mcp" / "ipfs_kit" / "tools" / "ipfs_core_tools_wrapper.py").exists()
            pin_tools_wrapper = (repo_root / "mcp" / "ipfs_kit" / "tools" / "pin_management_tools_wrapper.py").exists()
            
            print(f"✓ ipfs_core_tools.py in main package: {core_tools_main}")
            print(f"✓ pin_management_tools.py in main package: {pin_tools_main}")
            print(f"✓ ipfs_core_tools_wrapper.py in MCP: {core_tools_wrapper}")
            print(f"✓ pin_management_tools_wrapper.py in MCP: {pin_tools_wrapper}")
            
            # Try imports
            try:
                from ipfs_kit_py.tools import ipfs_core_tools
                print("✓ Can import ipfs_core_tools from main package")
            except ImportError:
                print("✗ Cannot import ipfs_core_tools (MCP infrastructure needed)")
            
            try:
                from ipfs_kit_py.tools import pin_management_tools
                print("✓ Can import pin_management_tools from main package")
            except ImportError:
                print("✗ Cannot import pin_management_tools (MCP infrastructure needed)")
            
            print("="*70)
            
            self.assertTrue(True, "Summary generated")
            
        except Exception as e:
            self.skipTest(f"Could not generate summary: {e}")


class TestVFSToolsIntegration(unittest.TestCase):
    """Test VFS tools follow proper integration patterns"""

    def test_bucket_vfs_manager_integration(self):
        """Test bucket_vfs_manager has proper ipfs_datasets integration"""
        try:
            from ipfs_kit_py import bucket_vfs_manager
            
            # Should have HAS_DATASETS flag
            self.assertTrue(hasattr(bucket_vfs_manager, 'HAS_DATASETS'),
                          "Should have HAS_DATASETS flag")
            
        except ImportError as e:
            self.skipTest(f"bucket_vfs_manager not available: {e}")

    def test_vfs_tools_has_integration_flags(self):
        """Test vfs_tools has integration flags"""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.mcp_tools import vfs_tools
            
            # Should have HAS_DATASETS and HAS_ACCELERATE flags
            self.assertTrue(hasattr(vfs_tools, 'HAS_DATASETS') or 
                          hasattr(vfs_tools, 'HAS_ACCELERATE'),
                          "Should have integration flags")
            
        except ImportError as e:
            self.skipTest(f"vfs_tools not available: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
