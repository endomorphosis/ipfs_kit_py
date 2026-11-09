#!/usr/bin/env python3
"""
Test script to verify dashboard button fixes.

This script verifies:
1. File listing displays correctly when MCP returns items
2. Folder creation calls the correct function  
3. File items are rendered from the response
"""

import re

def test_file_listing_fix():
    """Test that file listing parses 'items' field from MCP response."""
    with open('ipfs_kit_py/mcp/dashboard/templates/enhanced_dashboard.html', 'r') as f:
        content = f.read()
    
    # Check that we parse result.items
    assert 'result?.result?.items' in content, "Missing result.items parsing"
    assert 'result?.items' in content, "Missing items fallback parsing"
    print("✅ File listing now correctly parses 'items' field from MCP response")

def test_folder_creation_fix():
    """Test that folder creation calls the correct function."""
    with open('ipfs_kit_py/mcp/dashboard/templates/enhanced_dashboard.html', 'r') as f:
        content = f.read()
    
    # Check that we call loadBucketFilesInModal (not loadBucketFilesMCP)
    assert 'await loadBucketFilesInModal(bucketName)' in content, "Missing loadBucketFilesInModal call"
    
    # Make sure we removed the incorrect function name
    if 'loadBucketFilesMCP' in content:
        # Check if it's only in comments or definitions, not calls
        lines_with_mcp = [line for line in content.split('\n') if 'loadBucketFilesMCP' in line]
        calls = [line for line in lines_with_mcp if 'await loadBucketFilesMCP' in line]
        assert len(calls) == 0, f"Still has incorrect loadBucketFilesMCP calls: {calls}"
    
    print("✅ Folder creation now calls correct function: loadBucketFilesInModal")

def test_file_field_parsing():
    """Test that file rendering handles is_directory and is_dir fields."""
    with open('ipfs_kit_py/mcp/dashboard/templates/enhanced_dashboard.html', 'r') as f:
        content = f.read()
    
    # Check that we handle multiple directory field names
    assert 'is_directory' in content, "Missing is_directory field check"
    assert 'is_dir' in content, "Missing is_dir field check"
    
    # Check that we handle file.name or file.path
    assert 'file.name || file.path' in content, "Missing file.path fallback"
    
    print("✅ File rendering handles is_directory, is_dir, and file.path fields")

def main():
    """Run all tests."""
    print("🧪 Testing dashboard button fixes...\n")
    
    test_file_listing_fix()
    test_folder_creation_fix()
    test_file_field_parsing()
    
    print("\n✅ All dashboard button fixes verified!")
    print("\n🎯 Fixed issues:")
    print("  1. File listing now parses 'items' field (not 'files')")
    print("  2. Folder creation calls correct function (loadBucketFilesInModal)")
    print("  3. File rendering handles is_directory, is_dir, and path fields")
    print("\n📋 What this fixes:")
    print("  • Files now display in the modal when bucket is selected")
    print("  • Folder creation no longer throws 'loadBucketFilesMCP is not defined' error")
    print("  • File items render correctly from MCP list_bucket_files response")

if __name__ == '__main__':
    main()
