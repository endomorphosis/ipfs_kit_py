import pytest
import os
import shutil
from pathlib import Path
from unittest import mock

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment(tmp_path_factory):
    old_home = os.environ.get("HOME")
    home_dir = tmp_path_factory.mktemp("home")

    with mock.patch.dict(os.environ, {"HOME": str(home_dir)}):
        # Import after HOME is patched so any Path.home() usage is isolated.
        from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt

        test_ipfs_kit_path = Path.home() / ".ipfs_kit"
        test_ipfs_kit_path.mkdir(parents=True, exist_ok=True)

        # Create dummy config files
        (test_ipfs_kit_path / "bucket_config.yaml").write_text("test_key: test_value")
        (test_ipfs_kit_path / "daemon_config.yaml").write_text("daemon_port: 5001")

        # Create dummy pin metadata file
        (test_ipfs_kit_path / "pin_metadata" / "parquet_storage").mkdir(parents=True, exist_ok=True)
        import pandas as pd
        df_pins = pd.DataFrame([
            {"cid": "QmTestPin1", "name": "test_file1"},
            {"cid": "QmTestPin2", "name": "test_file2"},
        ])
        df_pins.to_parquet(test_ipfs_kit_path / "pin_metadata" / "parquet_storage" / "pins.parquet", engine="pyarrow")

        # Create dummy program state data
        (test_ipfs_kit_path / "program_state" / "parquet").mkdir(parents=True, exist_ok=True)
        df_state = pd.DataFrame([
            {"state_key": "state_value1"},
            {"state_key": "state_value2"},
        ])
        df_state.to_parquet(test_ipfs_kit_path / "program_state" / "parquet" / "test_state.parquet", engine="pyarrow")

        # Create dummy bucket registry
        (test_ipfs_kit_path / "bucket_index").mkdir(parents=True, exist_ok=True)
        df_buckets = pd.DataFrame([
            {"name": "bucket1", "cid": "QmBucket1"},
            {"name": "bucket2", "cid": "QmBucket2"},
        ])
        df_buckets.to_parquet(test_ipfs_kit_path / "bucket_index" / "bucket_registry.parquet", engine="pyarrow")

        yield

    if old_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = old_home

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