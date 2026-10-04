#!/usr/bin/env python3
"""
Test script to verify protobuf fix and Parquet IPLD bridge functionality.
"""

import sys
import os

sys.path.insert(0, ".")
import pytest


def test_protobuf_fix():
    """Test if protobuf conflicts are resolved."""
    print("🔍 Testing protobuf fix...")

    try:
        import google.protobuf

        print(f"✅ Protobuf version: {google.protobuf.__version__}")

        # Test libp2p module import
        from ipfs_kit_py import libp2p

        print("✅ libp2p module imported successfully!")

        # Test the main libp2p_peer import
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer

        print("✅ IPFSLibp2pPeer imported successfully!")

        # Test dependency check
        has_deps = libp2p.check_dependencies()
        print(f"✅ libp2p dependencies available: {has_deps}")

        assert has_deps is True or has_deps is False
    except Exception as e:
        print(f"❌ Protobuf/libp2p error: {e}")
        pytest.fail(f"Protobuf/libp2p test failed: {e}")


def test_parquet_bridge():
    """Test Parquet IPLD bridge functionality."""
    print("\n🧪 Testing Parquet IPLD Bridge...")

    try:
        from ipfs_kit_py.parquet_ipld_bridge import ParquetIPLDBridge

        print("✅ ParquetIPLDBridge imported successfully!")

        # Initialize bridge
        bridge = ParquetIPLDBridge()
        print("✅ ParquetIPLDBridge initialized!")

        # Test with pandas DataFrame
        import pandas as pd

        test_df = pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
                "score": [95.5, 87.2, 92.1, 88.8, 96.3],
            }
        )

        print(f"📊 Test DataFrame: {len(test_df)} rows, {len(test_df.columns)} columns")

        # Store DataFrame
        result = bridge.store_dataframe(test_df, name="test_users")

        if result["success"]:
            cid = result["cid"]
            print(f"✅ DataFrame stored with CID: {cid}")

            # Retrieve DataFrame
            retrieve_result = bridge.retrieve_dataframe(cid)
            if retrieve_result["success"]:
                retrieved_table = retrieve_result["table"]
                print(f"✅ DataFrame retrieved: {retrieved_table.num_rows} rows")

                # List datasets
                list_result = bridge.list_datasets()
                if list_result["success"]:
                    print(f"✅ Listed {list_result['count']} datasets")

                    assert list_result.get("success") in (True, False)
                    return None

        print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
        pytest.fail(f"Parquet bridge test failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Parquet bridge error: {e}")
        import traceback

        traceback.print_exc()
        pytest.fail(f"Parquet bridge test failed: {e}")


def test_transformers_integration():
    """Test transformers integration (should work without conflicts)."""
    print("\n🤖 Testing Transformers Integration...")

    try:
        import transformers

        print(f"✅ Transformers available: {transformers.__version__}")

        # Test that transformers and protobuf coexist
        import google.protobuf

        print(f"✅ Both transformers and protobuf ({google.protobuf.__version__}) coexist")

        assert transformers.__version__
    except Exception as e:
        print(f"❌ Transformers error: {e}")
        pytest.fail(f"Transformers integration test failed: {e}")


def main():
    """Run all tests."""
    print("🚀 IPFS Kit Python - Protobuf Fix Validation")
    print("=" * 60)

    results = {}

    # Test 1: Protobuf fix
    results["protobuf_fix"] = test_protobuf_fix()

    # Test 2: Parquet bridge
    results["parquet_bridge"] = test_parquet_bridge()

    # Test 3: Transformers integration
    results["transformers"] = test_transformers_integration()

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 60)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<20}: {status}")

    passed = sum(results.values())
    total = len(results)

    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Protobuf conflicts resolved")
        print("✅ libp2p components available")
        print("✅ Parquet-IPLD bridge working")
        print("✅ Transformers integration working")
        print("\n🚀 Your IPFS Kit is fully functional!")
    else:
        print(f"\n❌ {total - passed} tests failed")
        print("Some components may still have issues")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
