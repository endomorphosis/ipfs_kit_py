#!/usr/bin/env python3
"""
Simple test to verify the lotus_kit daemon_status fix
"""
import sys
import os
from pathlib import Path
import pytest

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_lotus_daemon_status():
    """Test the lotus_kit daemon_status method"""
    print("=== Testing Lotus Daemon Status ===")
    
    try:
        from ipfs_kit_py.lotus_kit import lotus_kit
        print("✓ lotus_kit imported successfully")
        
        lotus = lotus_kit()
        print("✓ lotus_kit initialized")
        
        # Test daemon_status method
        print("\\nTesting daemon_status method...")
        result = lotus.daemon_status()
        print(f"✓ daemon_status completed: {result}")
        
        # Check if process is running
        process_running = result.get("process_running", False)
        print(f"Process running: {process_running}")
        
        assert isinstance(result, dict)
        assert "process_running" in result
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Lotus daemon status test failed: {e}")

if __name__ == "__main__":
    success = test_lotus_daemon_status()
    sys.exit(0 if success else 1)
