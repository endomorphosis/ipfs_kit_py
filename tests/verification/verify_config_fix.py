#!/usr/bin/env python3
"""
Quick verification script for dashboard configuration fix.

This script:
1. Creates a test backends.json file
2. Verifies the dashboard can load it
3. Tests updating a backend config
4. Confirms persistence works

Run this to verify the fix is working correctly.
"""

import anyio
import json
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.mcp.servers.dashboard.refactored_unified_mcp_dashboard import RefactoredUnifiedMCPDashboard


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_success(text):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text):
    """Print error message."""
    print(f"❌ {text}")


def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")


async def verify_config_fix():
    """Run verification tests."""
    
    print_header("Dashboard Configuration Fix Verification")
    
    # Use ~/.ipfs_kit directory
    ipfs_kit_dir = Path.home() / ".ipfs_kit"
    ipfs_kit_dir.mkdir(parents=True, exist_ok=True)
    
    backends_file = ipfs_kit_dir / "backends.json"
    
    print_info(f"Using config directory: {ipfs_kit_dir}")
    print_info(f"Backends file: {backends_file}")
    
    # Step 1: Create test configuration
    print_header("Step 1: Creating Test Configuration")
    
    test_config = {
        "backends": {
            "s3_test": {
                "name": "s3_test",
                "config": {
                    "type": "s3",
                    "endpoint": "https://s3.amazonaws.com",
                    "access_key": "AKIAIOSFODNN7EXAMPLE",
                    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "bucket": "verification-test-bucket",
                    "region": "us-east-1"
                }
            },
            "ipfs_test": {
                "name": "ipfs_test",
                "config": {
                    "type": "ipfs",
                    "api_url": "http://localhost:5001",
                    "gateway_url": "http://localhost:8080"
                }
            }
        }
    }
    
    # Backup existing file if it exists
    backup_file = None
    if backends_file.exists():
        backup_file = backends_file.with_suffix('.json.backup')
        backends_file.rename(backup_file)
        print_info(f"Backed up existing config to: {backup_file}")
    
    # Write test config
    with open(backends_file, 'w') as f:
        json.dump(test_config, f, indent=2)
    backends_file.chmod(0o600)
    
    print_success(f"Created test configuration with 2 backends")
    
    # Step 2: Initialize dashboard
    print_header("Step 2: Initializing Dashboard")
    
    try:
        dashboard_config = {
            'host': '127.0.0.1',
            'port': 8004,
            'data_dir': str(ipfs_kit_dir),
            'debug': False,
            'update_interval': 3
        }
        
        dashboard = RefactoredUnifiedMCPDashboard(dashboard_config)
        print_success("Dashboard initialized successfully")
    except Exception as e:
        print_error(f"Failed to initialize dashboard: {e}")
        return False
    
    # Step 3: Test config loading
    print_header("Step 3: Testing Configuration Loading")
    
    try:
        config_data = await dashboard._get_config_data()
        
        # Verify structure
        assert "config" in config_data, "Missing 'config' key"
        assert "backends" in config_data["config"], "Missing 'backends' key"
        
        backends = config_data["config"]["backends"]
        assert "s3_test" in backends, "Missing 's3_test' backend"
        assert "ipfs_test" in backends, "Missing 'ipfs_test' backend"
        
        print_success("Config data structure is correct")
        
        # Verify S3 backend details
        s3_backend = backends["s3_test"]
        assert s3_backend["config"]["type"] == "s3", "Incorrect S3 type"
        assert s3_backend["config"]["bucket"] == "verification-test-bucket", "Incorrect S3 bucket"
        assert s3_backend["config"]["access_key"] == "AKIAIOSFODNN7EXAMPLE", "Incorrect S3 access_key"
        
        print_success("S3 backend loaded correctly")
        print(f"  - Type: {s3_backend['config']['type']}")
        print(f"  - Endpoint: {s3_backend['config']['endpoint']}")
        print(f"  - Bucket: {s3_backend['config']['bucket']}")
        print(f"  - Access Key: {s3_backend['config']['access_key'][:10]}...")
        
        # Verify IPFS backend details
        ipfs_backend = backends["ipfs_test"]
        assert ipfs_backend["config"]["type"] == "ipfs", "Incorrect IPFS type"
        assert ipfs_backend["config"]["api_url"] == "http://localhost:5001", "Incorrect IPFS API URL"
        
        print_success("IPFS backend loaded correctly")
        print(f"  - Type: {ipfs_backend['config']['type']}")
        print(f"  - API URL: {ipfs_backend['config']['api_url']}")
        print(f"  - Gateway URL: {ipfs_backend['config']['gateway_url']}")
        
    except Exception as e:
        print_error(f"Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Test backend configs endpoint
    print_header("Step 4: Testing Backend Configs Endpoint")
    
    try:
        backend_configs = await dashboard._get_backend_configs()
        
        assert "s3_test" in backend_configs, "Missing s3_test in backend configs"
        assert "ipfs_test" in backend_configs, "Missing ipfs_test in backend configs"
        
        print_success("Backend configs endpoint works correctly")
        print(f"  - Loaded {len(backend_configs)} backends")
        
    except Exception as e:
        print_error(f"Backend configs failed: {e}")
        return False
    
    # Step 5: Test config update
    print_header("Step 5: Testing Configuration Update")
    
    try:
        updated_config = {
            "config": {
                "type": "s3",
                "endpoint": "https://s3.us-west-2.amazonaws.com",  # Changed
                "access_key": "AKIAI_UPDATED_KEY",  # Changed
                "secret_key": "UPDATED_SECRET_KEY",  # Changed
                "bucket": "updated-verification-bucket",  # Changed
                "region": "us-west-2"  # Changed
            }
        }
        
        update_result = await dashboard._update_backend_config("s3_test", updated_config)
        
        assert update_result["status"] == "updated", "Update failed"
        assert update_result["backend"] == "s3_test", "Wrong backend updated"
        
        print_success("Backend config updated successfully")
        
    except Exception as e:
        print_error(f"Config update failed: {e}")
        return False
    
    # Step 6: Verify persistence
    print_header("Step 6: Verifying Update Persistence")
    
    try:
        # Re-load config
        refreshed_config = await dashboard._get_config_data()
        updated_backend = refreshed_config["config"]["backends"]["s3_test"]
        
        assert updated_backend["config"]["endpoint"] == "https://s3.us-west-2.amazonaws.com", "Endpoint not persisted"
        assert updated_backend["config"]["access_key"] == "AKIAI_UPDATED_KEY", "Access key not persisted"
        assert updated_backend["config"]["bucket"] == "updated-verification-bucket", "Bucket not persisted"
        assert updated_backend["config"]["region"] == "us-west-2", "Region not persisted"
        
        print_success("Updated config persisted correctly in memory")
        
        # Verify file on disk
        with open(backends_file, 'r') as f:
            file_content = json.load(f)
        
        assert file_content["backends"]["s3_test"]["config"]["endpoint"] == "https://s3.us-west-2.amazonaws.com", "File not updated"
        assert file_content["backends"]["s3_test"]["config"]["bucket"] == "updated-verification-bucket", "File not updated"
        
        print_success("Updated config persisted correctly on disk")
        
    except Exception as e:
        print_error(f"Persistence verification failed: {e}")
        return False
    
    # Step 7: Cleanup
    print_header("Step 7: Cleanup")
    
    if backup_file and backup_file.exists():
        # Restore original file
        backends_file.unlink()
        backup_file.rename(backends_file)
        print_success(f"Restored original config from backup")
    else:
        # Remove test file
        backends_file.unlink()
        print_success("Removed test configuration")
    
    # Final summary
    print_header("Verification Complete")
    print()
    print_success("All verification tests passed!")
    print()
    print("The dashboard configuration fix is working correctly:")
    print("  ✅ Reads backends.json from ~/.ipfs_kit/")
    print("  ✅ Returns correctly structured data")
    print("  ✅ Form fields will populate with saved credentials")
    print("  ✅ Updates persist back to configuration file")
    print()
    print_info("You can now start the dashboard and verify in the browser:")
    print("     python3 -m mcp.dashboard.launch_refactored_dashboard")
    print()
    
    return True


async def main():
    """Main entry point."""
    try:
        success = await verify_config_fix()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
