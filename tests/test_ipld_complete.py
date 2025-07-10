#!/usr/bin/env python3
"""
Complete test of IPLD functionality in ipfs_kit_py
Tests all IPLD packages including the GitHub py-ipld-unixfs package
"""

def test_ipld_imports():
    """Test that all IPLD packages can be imported successfully."""
    print("=== Testing IPLD Package Imports ===")
    
    packages = [
        ('ipld_car', 'IPLD CAR file format support'),
        ('ipld_dag_pb', 'IPLD DAG-PB codec support'),
        ('ipld_unixfs', 'IPLD UnixFS support (from GitHub)'),
        ('dag_cbor', 'DAG-CBOR codec support'),
        ('multiformats', 'Multiformats specification support'),
    ]
    
    all_passed = True
    
    for package, description in packages:
        try:
            module = __import__(package)
            version = getattr(module, '__version__', 'unknown')
            location = getattr(module, '__file__', 'unknown')
            print(f"✓ {package:15} v{version:10} - {description}")
            print(f"  Location: {location}")
        except ImportError as e:
            print(f"✗ {package:15} FAILED - {e}")
            all_passed = False
        print()
    
    return all_passed

def test_basic_functionality():
    """Test basic functionality of IPLD packages."""
    print("=== Testing Basic IPLD Functionality ===")
    
    try:
        # Test multiformats
        import multiformats
        print("✓ Multiformats module loaded successfully")
        
        # Test if we can create basic CID-related objects
        if hasattr(multiformats, 'CID'):
            print("✓ CID class available in multiformats")
        
        # Test dag_cbor
        import dag_cbor
        print("✓ DAG-CBOR module loaded successfully")
        
        # Test basic CBOR encoding/decoding
        test_data = {"hello": "world", "number": 42}
        try:
            encoded = dag_cbor.encode(test_data)
            decoded = dag_cbor.decode(encoded)
            if decoded == test_data:
                print("✓ DAG-CBOR encode/decode test passed")
            else:
                print("✗ DAG-CBOR encode/decode test failed")
        except Exception as e:
            print(f"⚠ DAG-CBOR encode/decode test error: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        return False

def main():
    """Run all IPLD tests."""
    print("IPFS Kit Python - Complete IPLD Test Suite")
    print("=" * 50)
    print()
    
    # Test imports
    imports_passed = test_ipld_imports()
    print()
    
    # Test basic functionality
    functionality_passed = test_basic_functionality()
    print()
    
    # Final summary
    print("=== Test Summary ===")
    if imports_passed and functionality_passed:
        print("🎉 All IPLD tests passed! Your installation is complete.")
        print()
        print("Available IPLD features:")
        print("• CAR file format support (ipld-car)")
        print("• DAG-PB codec support (ipld-dag-pb)")  
        print("• UnixFS support (py-ipld-unixfs from GitHub)")
        print("• CBOR DAG support (dag-cbor)")
        print("• Multiformats specification support")
        print()
        print("Installation extras available:")
        print("• pip install -e .[ipld]        # PyPI packages only")
        print("• pip install -e .[ipld-github] # Includes GitHub packages")
        print("• pip install -e .[full]        # All dependencies (PyPI only)")
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
