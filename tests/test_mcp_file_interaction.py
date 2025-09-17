import pytest
import os
import shutil
from pathlib import Path
from unittest import mock

# Define a temporary .ipfs_kit directory for testing
TEST_IPFS_KIT_PATH = Path.home() / ".ipfs_kit_test"

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    with mock.patch.dict(os.environ, {'HOME': str(TEST_IPFS_KIT_PATH.parent)}):
        # Import EnhancedMCPServerWithDaemonMgmt after patching HOME
        from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt

        # Create a temporary .ipfs_kit directory for testing
        if TEST_IPFS_KIT_PATH.exists():
            shutil.rmtree(TEST_IPFS_KIT_PATH)
        TEST_IPFS_KIT_PATH.mkdir(parents=True, exist_ok=True)

        # Create dummy config files
        (TEST_IPFS_KIT_PATH / "bucket_config.yaml").write_text("test_key: test_value")
        (TEST_IPFS_KIT_PATH / "daemon_config.yaml").write_text("daemon_port: 5001")

        # Create dummy pin metadata file
        (TEST_IPFS_KIT_PATH / "pin_metadata" / "parquet_storage").mkdir(parents=True, exist_ok=True)
        # Using pandas to create a dummy parquet file
        import pandas as pd
        df_pins = pd.DataFrame([{"cid": "QmTestPin1", "name": "test_file1"}, {"cid": "QmTestPin2", "name": "test_file2"}])
        df_pins.to_parquet(TEST_IPFS_KIT_PATH / "pin_metadata" / "parquet_storage" / "pins.parquet", engine='pyarrow')

        # Create dummy program state data
        (TEST_IPFS_KIT_PATH / "program_state" / "parquet").mkdir(parents=True, exist_ok=True)
        df_state = pd.DataFrame([{"state_key": "state_value1"}, {"state_key": "state_value2"}])
        df_state.to_parquet(TEST_IPFS_KIT_PATH / "program_state" / "parquet" / "test_state.parquet", engine='pyarrow')

        # Create dummy bucket registry
        (TEST_IPFS_KIT_PATH / "bucket_index").mkdir(parents=True, exist_ok=True)
        df_buckets = pd.DataFrame([{"name": "bucket1", "cid": "QmBucket1"}, {"name": "bucket2", "cid": "QmBucket2"}])
        df_buckets.to_parquet(TEST_IPFS_KIT_PATH / "bucket_index" / "bucket_registry.parquet", engine='pyarrow')

        yield
        # Clean up
        shutil.rmtree(TEST_IPFS_KIT_PATH)

def test_get_all_configs():
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
    server = EnhancedMCPServerWithDaemonMgmt()
    configs = server.get_all_configs()
    assert "bucket" in configs
    assert configs["bucket"]["test_key"] == "test_value"
    assert "daemon" in configs
    assert configs["daemon"]["daemon_port"] == 5001

def test_get_pin_metadata():
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
    server = EnhancedMCPServerWithDaemonMgmt()
    pin_metadata = server.get_pin_metadata()
    assert len(pin_metadata) == 2
    assert pin_metadata[0]["cid"] == "QmTestPin1"

def test_get_program_state_data():
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
    server = EnhancedMCPServerWithDaemonMgmt()
    program_state = server.get_program_state_data()
    assert "test_state" in program_state
    assert program_state["test_state"]["state_key"] == "state_value2" # Should get the last entry

def test_get_bucket_registry():
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
    server = EnhancedMCPServerWithDaemonMgmt()
    bucket_registry = server.get_bucket_registry()
    assert len(bucket_registry) == 2
    assert bucket_registry[0]["name"] == "bucket1"

def test_get_backend_status_data():
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
    server = EnhancedMCPServerWithDaemonMgmt()
    backend_status = server.get_backend_status_data()
    assert "bucket" in backend_status
    assert backend_status["bucket"]["configured"] == True
    assert backend_status["daemon"]["configured"] == True