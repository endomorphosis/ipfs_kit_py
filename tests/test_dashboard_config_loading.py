"""
Test dashboard configuration loading functionality.

This test verifies that the dashboard properly loads backend configurations
from ~/.ipfs_kit/backends.json and populates form fields correctly.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add the parent directory to the path to import the dashboard module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default import error message for skip reason
DASHBOARD_IMPORT_ERROR = ""

# Try to import the dashboard module - skip tests if dependencies are missing or import-time errors occur
try:
    from mcp.dashboard.refactored_unified_mcp_dashboard import RefactoredUnifiedMCPDashboard
    DASHBOARD_AVAILABLE = True
except Exception as e:  # Catch broad exceptions to prevent collection-time failures (e.g., NameError in optional deps)
    DASHBOARD_AVAILABLE = False
    DASHBOARD_IMPORT_ERROR = str(e)
    # Create a dummy class for when dashboard is not available
    class RefactoredUnifiedMCPDashboard:
        pass

import pytest


@pytest.fixture
def temp_ipfs_kit_dir():
    """Create a temporary ~/.ipfs_kit directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_backends_config():
    """Sample backends configuration."""
    return {
        "backends": {
            "s3_main": {
                "name": "s3_main",
                "config": {
                    "type": "s3",
                    "endpoint": "https://s3.amazonaws.com",
                    "access_key": "AKIAIOSFODNN7EXAMPLE",
                    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "bucket": "my-test-bucket",
                    "region": "us-east-1"
                }
            },
            "hf_storage": {
                "name": "hf_storage",
                "config": {
                    "type": "huggingface",
                    "token": "hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "endpoint": "https://huggingface.co"
                }
            },
            "ipfs_local": {
                "name": "ipfs_local",
                "config": {
                    "type": "ipfs",
                    "api_url": "http://localhost:5001",
                    "gateway_url": "http://localhost:8080"
                }
            }
        }
    }


@pytest.mark.asyncio
@pytest.mark.skipif(not DASHBOARD_AVAILABLE, reason=f"Dashboard dependencies not available: {DASHBOARD_IMPORT_ERROR if not DASHBOARD_AVAILABLE else ''}")
async def test_get_config_data_with_backends(temp_ipfs_kit_dir, sample_backends_config):
    """Test that _get_config_data properly loads backends.json."""
    # Create backends.json in temp directory
    backends_file = temp_ipfs_kit_dir / "backends.json"
    with open(backends_file, 'w') as f:
        json.dump(sample_backends_config, f, indent=2)
    
    # Create dashboard instance with temp directory
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': str(temp_ipfs_kit_dir),
        'debug': False,
        'update_interval': 3
    }
    
    dashboard = RefactoredUnifiedMCPDashboard(config)
    
    # Get config data
    result = await dashboard._get_config_data()
    
    # Verify structure
    assert "config" in result
    assert "backends" in result["config"]
    assert "main" in result["config"]
    
    # Verify backends are loaded
    backends = result["config"]["backends"]
    assert "s3_main" in backends
    
    # Check for expected backends from sample_backends_config
    expected_backends = list(sample_backends_config["backends"].keys())
    for backend_name in expected_backends:
        assert backend_name in backends, f"Missing backend: {backend_name}"
    
    # Verify S3 backend details
    s3_backend = backends["s3_main"]
    assert s3_backend["config"]["type"] == "s3"
    assert s3_backend["config"]["endpoint"] == sample_backends_config["backends"]["s3_main"]["config"]["endpoint"]
    assert s3_backend["config"]["access_key"] == sample_backends_config["backends"]["s3_main"]["config"]["access_key"]
    
    print("✅ Test passed: Config data properly loaded from backends.json")


@pytest.mark.asyncio
@pytest.mark.skipif(not DASHBOARD_AVAILABLE, reason=f"Dashboard dependencies not available: {DASHBOARD_IMPORT_ERROR if not DASHBOARD_AVAILABLE else ''}")
async def test_get_backend_configs(temp_ipfs_kit_dir, sample_backends_config):
    """Test that _get_backend_configs returns backend configurations."""
    # Create backends.json in temp directory
    backends_file = temp_ipfs_kit_dir / "backends.json"
    with open(backends_file, 'w') as f:
        json.dump(sample_backends_config, f, indent=2)
    
    # Create dashboard instance with temp directory
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': str(temp_ipfs_kit_dir),
        'debug': False,
        'update_interval': 3
    }
    
    dashboard = RefactoredUnifiedMCPDashboard(config)
    
    # Get backend configs
    result = await dashboard._get_backend_configs()
    
    # Verify backends are loaded
    expected_backends = list(sample_backends_config["backends"].keys())
    for backend_name in expected_backends:
        assert backend_name in result, f"Missing backend: {backend_name}"
    
    print("✅ Test passed: Backend configs properly loaded")


@pytest.mark.asyncio
@pytest.mark.skipif(not DASHBOARD_AVAILABLE, reason=f"Dashboard dependencies not available: {DASHBOARD_IMPORT_ERROR if not DASHBOARD_AVAILABLE else ''}")
async def test_update_backend_config(temp_ipfs_kit_dir, sample_backends_config):
    """Test updating a backend configuration."""
    # Create backends.json in temp directory
    backends_file = temp_ipfs_kit_dir / "backends.json"
    with open(backends_file, 'w') as f:
        json.dump(sample_backends_config, f, indent=2)
    
    # Create dashboard instance with temp directory
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': str(temp_ipfs_kit_dir),
        'debug': False,
        'update_interval': 3
    }
    
    dashboard = RefactoredUnifiedMCPDashboard(config)
    
    # Update S3 backend config
    new_config = {
        "config": {
            "type": "s3",
            "endpoint": "https://s3.us-west-2.amazonaws.com",
            "access_key": "AKIAIOSFODNN7UPDATED",
            "secret_key": "UPDATED_SECRET_KEY",
            "bucket": "updated-bucket",
            "region": "us-west-2"
        }
    }
    
    result = await dashboard._update_backend_config("s3_main", new_config)
    
    # Verify update was successful
    assert result["status"] == "updated"
    assert result["backend"] == "s3_main"
    
    # Verify the file was updated
    with open(backends_file, 'r') as f:
        updated_config = json.load(f)
    
    assert updated_config["backends"]["s3_main"]["config"]["endpoint"] == "https://s3.us-west-2.amazonaws.com"
    assert updated_config["backends"]["s3_main"]["config"]["access_key"] == "AKIAIOSFODNN7UPDATED"
    assert updated_config["backends"]["s3_main"]["config"]["bucket"] == "updated-bucket"
    
    print("✅ Test passed: Backend config successfully updated")


@pytest.mark.asyncio
@pytest.mark.skipif(not DASHBOARD_AVAILABLE, reason=f"Dashboard dependencies not available: {DASHBOARD_IMPORT_ERROR if not DASHBOARD_AVAILABLE else ''}")
async def test_empty_backends_file(temp_ipfs_kit_dir):
    """Test handling of non-existent backends.json file."""
    # Don't create backends.json - test default behavior
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': str(temp_ipfs_kit_dir),
        'debug': False,
        'update_interval': 3
    }
    
    dashboard = RefactoredUnifiedMCPDashboard(config)
    
    # Get config data - should create default file
    result = await dashboard._get_config_data()
    
    # Verify structure exists even if empty
    assert "config" in result
    assert "backends" in result["config"]
    
    print("✅ Test passed: Gracefully handles missing backends.json")


@pytest.mark.asyncio
@pytest.mark.skipif(not DASHBOARD_AVAILABLE, reason=f"Dashboard dependencies not available: {DASHBOARD_IMPORT_ERROR if not DASHBOARD_AVAILABLE else ''}")
async def test_comprehensive_config_flow(temp_ipfs_kit_dir):
    """Test the complete config loading, updating, and persistence flow."""
    # Create comprehensive backends config with multiple backend types
    backends_config = {
        "backends": {
            "s3_main": {
                "name": "s3_main",
                "config": {
                    "type": "s3",
                    "endpoint": "https://s3.amazonaws.com",
                    "access_key": "AKIAIOSFODNN7EXAMPLE",
                    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "bucket": "my-production-bucket",
                    "region": "us-east-1"
                }
            },
            "hf_models": {
                "name": "hf_models",
                "config": {
                    "type": "huggingface",
                    "token": "hf_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890",
                    "endpoint": "https://huggingface.co"
                }
            },
            "ipfs_local": {
                "name": "ipfs_local",
                "config": {
                    "type": "ipfs",
                    "api_url": "http://localhost:5001",
                    "gateway_url": "http://localhost:8080"
                }
            }
        }
    }
    
    # Write backends.json
    backends_file = temp_ipfs_kit_dir / "backends.json"
    with open(backends_file, 'w') as f:
        json.dump(backends_config, f, indent=2)
    
    # Create dashboard instance
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': str(temp_ipfs_kit_dir),
        'debug': True,
        'update_interval': 3
    }
    
    dashboard = RefactoredUnifiedMCPDashboard(config)
    
    # Test 1: Load all backends
    result = await dashboard._get_config_data()
    backends = result['config']['backends']
    assert len(backends) == 3
    assert 's3_main' in backends
    assert 'hf_models' in backends
    assert 'ipfs_local' in backends
    
    # Test 2: Verify S3 config details
    s3_config = backends['s3_main']['config']
    assert s3_config['endpoint'] == 'https://s3.amazonaws.com'
    assert s3_config['access_key'] == 'AKIAIOSFODNN7EXAMPLE'
    
    # Test 3: Update S3 backend
    updated_s3_config = {
        'config': {
            'type': 's3',
            'endpoint': 'https://s3.us-west-2.amazonaws.com',
            'access_key': 'AKIAI_UPDATED_KEY',
            'secret_key': 'UPDATED_SECRET_KEY',
            'bucket': 'my-updated-bucket',
            'region': 'us-west-2'
        }
    }
    
    update_result = await dashboard._update_backend_config('s3_main', updated_s3_config)
    assert update_result['status'] == 'updated'
    
    # Test 4: Verify update persisted
    refreshed_config = await dashboard._get_config_data()
    updated_backend = refreshed_config['config']['backends']['s3_main']
    assert updated_backend['config']['endpoint'] == 'https://s3.us-west-2.amazonaws.com'
    assert updated_backend['config']['access_key'] == 'AKIAI_UPDATED_KEY'
    
    # Test 5: Verify file on disk was updated
    with open(backends_file, 'r') as f:
        file_content = json.load(f)
    assert file_content['backends']['s3_main']['config']['endpoint'] == 'https://s3.us-west-2.amazonaws.com'
    
    print("✅ Comprehensive config flow test passed!")


if __name__ == "__main__":
    # Run tests directly
    async def run_tests():
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            
            # Sample config
            sample_config = {
                "backends": {
                    "s3_main": {
                        "name": "s3_main",
                        "config": {
                            "type": "s3",
                            "endpoint": "https://s3.amazonaws.com",
                            "access_key": "AKIAIOSFODNN7EXAMPLE",
                            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                            "bucket": "my-test-bucket",
                            "region": "us-east-1"
                        }
                    }
                }
            }
            
            print("Running dashboard config loading tests...")
            print("-" * 50)
            
            try:
                await test_get_config_data_with_backends(temp_dir, sample_config)
                await test_get_backend_configs(temp_dir, sample_config)
                await test_update_backend_config(temp_dir, sample_config)
                await test_empty_backends_file(temp_dir)
                await test_comprehensive_config_flow(temp_dir)
                
                print("-" * 50)
                print("✅ All tests passed!")
            except Exception as e:
                print(f"❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
    
    asyncio.run(run_tests())
