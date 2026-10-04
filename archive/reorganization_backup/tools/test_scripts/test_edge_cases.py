#!/usr/bin/env python3
"""
Edge Cases and Error Handling Test Suite

This test suite focuses on edge cases, error conditions, and boundary testing
for the IPFS tools implementation.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Add the current directory to the path to ensure imports work
current_dir = Path(__file__).parent
sys.path.insert(0, "/home/devel/ipfs_kit_py/tools")

# Import the unified IPFS tools
try:
    from unified_ipfs_tools import (
        ipfs_add, ipfs_cat, ipfs_version,
        ipfs_pin, ipfs_unpin, ipfs_list_pins,
        ipfs_files_ls, ipfs_files_mkdir, ipfs_files_write,
        ipfs_files_read, ipfs_files_rm, ipfs_files_stat,
        ipfs_files_cp, ipfs_files_mv, ipfs_files_flush
    )
    print("✅ Successfully imported all IPFS tools for edge case testing")
except ImportError as e:
    print(f"❌ Failed to import IPFS tools: {e}")
    sys.exit(1)

class TestIPFSEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def test_01_unicode_content(self):
        """Test handling of Unicode content."""
        print("\n🧪 Testing Unicode content handling...")
        unicode_content = "Hello 世界! 🌍 Testing émojis and special chars: àáâãäå"
        
        result = ipfs_add({'content': unicode_content})
        self.assertIsInstance(result, dict)
        self.assertIn('hash', result)
        print(f"   ✅ Unicode add result: {result}")
        
        # Test retrieving Unicode content
        hash_value = result.get('hash', 'QmTest123')
        cat_result = ipfs_cat({'hash': hash_value})
        self.assertIsInstance(cat_result, dict)
        print(f"   ✅ Unicode cat result: {cat_result}")
        
    def test_02_large_content(self):
        """Test handling of large content."""
        print("\n🧪 Testing large content handling...")
        large_content = "A" * 10000  # 10KB of content
        
        result = ipfs_add({'content': large_content})
        self.assertIsInstance(result, dict)
        self.assertIn('hash', result)
        print(f"   ✅ Large content add result: {result}")
        
    def test_03_deep_path_handling(self):
        """Test handling of deep file paths."""
        print("\n🧪 Testing deep path handling...")
        deep_path = "/test/very/deep/nested/path/structure/file.txt"
        
        # Create the directory structure
        ipfs_files_mkdir({'path': "/test/very/deep/nested/path/structure", 'parents': True})
        
        # Write to deep path
        result = ipfs_files_write({
            'path': deep_path,
            'content': "Deep path test content"
        })
        self.assertIsInstance(result, dict)
        print(f"   ✅ Deep path write result: {result}")
        
        # Read from deep path
        read_result = ipfs_files_read({'path': deep_path})
        self.assertIsInstance(read_result, dict)
        print(f"   ✅ Deep path read result: {read_result}")
        
    def test_04_invalid_parameters(self):
        """Test handling of invalid parameters."""
        print("\n🧪 Testing invalid parameter handling...")
        
        # Test with None parameters
        result = ipfs_add({'content': None})
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
        print(f"   ✅ None content handling: {result}")
        
        # Test with empty parameters
        result = ipfs_cat({})
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
        print(f"   ✅ Empty parameters handling: {result}")
        
        # Test with invalid hash
        result = ipfs_cat({'hash': 'invalid_hash'})
        self.assertIsInstance(result, dict)
        print(f"   ✅ Invalid hash handling: {result}")
        
    def test_05_error_recovery(self):
        """Test error recovery and graceful degradation."""
        print("\n🧪 Testing error recovery...")
        
        # Test operations that should succeed even in mock mode
        operations = [
            (ipfs_version, {}),
            (ipfs_list_pins, {}),
            (ipfs_files_ls, {'path': '/'}),
            (ipfs_add, {'content': 'test'}),
            (ipfs_cat, {'hash': 'QmTest123'})
        ]
        
        successful_operations = 0
        for operation, params in operations:
            try:
                result = operation(params)
                if isinstance(result, dict) and 'error' not in result:
                    successful_operations += 1
                print(f"   ✅ {operation.__name__} succeeded with result: {result}")
            except Exception as e:
                print(f"   ⚠️  {operation.__name__} failed: {e}")
        
        # At least 80% of operations should succeed
        success_rate = (successful_operations / len(operations)) * 100
        self.assertGreaterEqual(success_rate, 80, f"Success rate {success_rate}% too low")
        print(f"   🎯 Error recovery success rate: {success_rate}%")

def run_edge_case_tests():
    """Run all edge case tests."""
    print("🚀 Starting Edge Case Test Suite")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIPFSEdgeCases)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Edge Case Test Summary")
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
        print("🎉 All edge case tests passed! Implementation is robust.")
    elif success_rate >= 80:
        print("✅ Most edge case tests passed. Implementation handles errors well.")
    else:
        print("⚠️  Many edge case tests failed. Review error handling.")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_edge_case_tests()
    sys.exit(0 if success else 1)
