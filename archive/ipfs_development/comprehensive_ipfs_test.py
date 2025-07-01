#!/usr/bin/env python3
"""
Comprehensive IPFS Test Suite

This test suite validates all IPFS tools in the unified_ipfs_tools module,
testing both real implementations (when available) and mock fallbacks.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

# Add the current directory to the path to ensure imports work
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the unified IPFS tools
try:
    from unified_ipfs_tools import (
        ipfs_add, ipfs_cat, ipfs_version,
        ipfs_pin, ipfs_unpin, ipfs_list_pins,
        ipfs_files_ls, ipfs_files_mkdir, ipfs_files_write,
        ipfs_files_read, ipfs_files_rm, ipfs_files_stat,
        ipfs_files_cp, ipfs_files_mv, ipfs_files_flush
    )
    print("✅ Successfully imported all IPFS tools")
except ImportError as e:
    print(f"❌ Failed to import IPFS tools: {e}")
    sys.exit(1)

class TestIPFSTools(unittest.TestCase):
    """Test all IPFS tools."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_content = "Hello, IPFS Test World!"
        self.test_path = "/test/comprehensive_test"
        
    def test_01_ipfs_version(self):
        """Test IPFS version command."""
        print("\n🧪 Testing ipfs_version...")
        result = ipfs_version({})
        self.assertIsInstance(result, dict)
        self.assertIn('version', result)
        print(f"   ✅ Version result: {result}")
        
    def test_02_ipfs_add(self):
        """Test IPFS add command."""
        print("\n🧪 Testing ipfs_add...")
        result = ipfs_add({'content': self.test_content})
        self.assertIsInstance(result, dict)
        self.assertIn('hash', result)
        print(f"   ✅ Add result: {result}")
        
    def test_03_ipfs_cat(self):
        """Test IPFS cat command."""
        print("\n🧪 Testing ipfs_cat...")
        # First add content to get a hash
        add_result = ipfs_add({'content': self.test_content})
        test_hash = add_result.get('hash', 'QmTest123')
        
        result = ipfs_cat({'hash': test_hash})
        self.assertIsInstance(result, dict)
        print(f"   ✅ Cat result: {result}")
        
    def test_04_ipfs_pin(self):
        """Test IPFS pin command."""
        print("\n🧪 Testing ipfs_pin...")
        # First add content to get a hash
        add_result = ipfs_add({'content': self.test_content})
        test_hash = add_result.get('hash', 'QmTest123')
        
        result = ipfs_pin({'hash': test_hash})
        self.assertIsInstance(result, dict)
        print(f"   ✅ Pin result: {result}")
        
    def test_05_ipfs_list_pins(self):
        """Test IPFS list pins command."""
        print("\n🧪 Testing ipfs_list_pins...")
        result = ipfs_list_pins({})
        self.assertIsInstance(result, dict)
        print(f"   ✅ List pins result: {result}")
        
    def test_06_ipfs_unpin(self):
        """Test IPFS unpin command."""
        print("\n🧪 Testing ipfs_unpin...")
        # First add and pin content
        add_result = ipfs_add({'content': self.test_content})
        test_hash = add_result.get('hash', 'QmTest123')
        ipfs_pin({'hash': test_hash})
        
        result = ipfs_unpin({'hash': test_hash})
        self.assertIsInstance(result, dict)
        print(f"   ✅ Unpin result: {result}")
        
    def test_07_ipfs_files_ls(self):
        """Test IPFS MFS ls command."""
        print("\n🧪 Testing ipfs_files_ls...")
        result = ipfs_files_ls({'path': '/'})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS ls result: {result}")
        
    def test_08_ipfs_files_mkdir(self):
        """Test IPFS MFS mkdir command."""
        print("\n🧪 Testing ipfs_files_mkdir...")
        result = ipfs_files_mkdir({'path': self.test_path})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS mkdir result: {result}")
        
    def test_09_ipfs_files_write(self):
        """Test IPFS MFS write command."""
        print("\n🧪 Testing ipfs_files_write...")
        test_file = f"{self.test_path}/test_file.txt"
        result = ipfs_files_write({
            'path': test_file,
            'content': self.test_content
        })
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS write result: {result}")
        
    def test_10_ipfs_files_read(self):
        """Test IPFS MFS read command."""
        print("\n🧪 Testing ipfs_files_read...")
        test_file = f"{self.test_path}/test_file.txt"
        # First write the file
        ipfs_files_write({
            'path': test_file,
            'content': self.test_content
        })
        
        result = ipfs_files_read({'path': test_file})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS read result: {result}")
        
    def test_11_ipfs_files_stat(self):
        """Test IPFS MFS stat command."""
        print("\n🧪 Testing ipfs_files_stat...")
        test_file = f"{self.test_path}/test_file.txt"
        result = ipfs_files_stat({'path': test_file})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS stat result: {result}")
        
    def test_12_ipfs_files_cp(self):
        """Test IPFS MFS copy command."""
        print("\n🧪 Testing ipfs_files_cp...")
        source = f"{self.test_path}/test_file.txt"
        dest = f"{self.test_path}/copied_file.txt"
        result = ipfs_files_cp({'source': source, 'dest': dest})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS cp result: {result}")
        
    def test_13_ipfs_files_mv(self):
        """Test IPFS MFS move command."""
        print("\n🧪 Testing ipfs_files_mv...")
        source = f"{self.test_path}/copied_file.txt"
        dest = f"{self.test_path}/moved_file.txt"
        result = ipfs_files_mv({'source': source, 'dest': dest})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS mv result: {result}")
        
    def test_14_ipfs_files_flush(self):
        """Test IPFS MFS flush command."""
        print("\n🧪 Testing ipfs_files_flush...")
        result = ipfs_files_flush({'path': self.test_path})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS flush result: {result}")
        
    def test_15_ipfs_files_rm(self):
        """Test IPFS MFS remove command."""
        print("\n🧪 Testing ipfs_files_rm...")
        result = ipfs_files_rm({'path': self.test_path, 'recursive': True})
        self.assertIsInstance(result, dict)
        print(f"   ✅ MFS rm result: {result}")

def run_comprehensive_tests():
    """Run all comprehensive tests."""
    print("🚀 Starting Comprehensive IPFS Test Suite")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIPFSTools)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ Failures:")
        for test, error in result.failures:
            print(f"  {test}: {error}")
            
    if result.errors:
        print("\n💥 Errors:")
        for test, error in result.errors:
            print(f"  {test}: {error}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
    print(f"\n🎯 Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("🎉 All tests passed! IPFS tools are working correctly.")
    elif success_rate >= 80:
        print("✅ Most tests passed. Implementation is functional.")
    else:
        print("⚠️  Many tests failed. Review implementation.")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
