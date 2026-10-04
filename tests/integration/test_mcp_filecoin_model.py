import pytest
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
import anyio
import os
import time
import tempfile

# Adjust import based on actual file structure
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
# Mock base class methods if necessary, or mock dependencies directly
# from ipfs_kit_py.mcp.models.storage.base_storage_model import BaseStorageModel
from ipfs_kit_py.lotus_kit import lotus_kit # To spec the mock

# Mock IPFS Model for cross-service tests
# Using AsyncMock for async methods as the real model likely uses them
class MockIPFSModel:
    async def get_content(self, cid):
        if cid == "valid_ipfs_cid":
            # Simulate returning bytes content
            return {"success": True, "data": b"ipfs_content", "size_bytes": len(b"ipfs_content")}
        else:
            return {"success": False, "error": "IPFS Get Error", "error_type": "IPFSGetError"}

    async def add_content(self, content):
        if content == b"filecoin_content":
             # Simulate adding content and returning a CID
            return {"success": True, "cid": "new_ipfs_cid", "size_bytes": len(content)}
        else:
            return {"success": False, "error": "IPFS Add Error", "error_type": "IPFSAddError"}

    async def pin_content(self, cid):
        if cid == "new_ipfs_cid":
            return {"success": True}
        else:
            # Simulate potential pin failure but don't stop the main flow
            print(f"Mock warning: Failed to pin {cid}")
            return {"success": False, "error": "Pin failed"}


class TestFilecoinModel:
    @pytest.fixture
    def mock_lotus_kit(self):
        """Mock the lotus_kit instance."""
        kit = MagicMock(spec=lotus_kit)
        kit.check_connection.return_value = {"success": True, "result": "mock_version"}
        kit.list_wallets.return_value = {"success": True, "result": ["mock_wallet1"]}
        kit.wallet_balance.return_value = {"success": True, "result": "1000"}
        kit.create_wallet.return_value = {"success": True, "result": "new_mock_wallet"}
        # Simulate successful import returning a Root CID
        kit.client_import.return_value = {"success": True, "result": {"Root": {"/": "imported_cid"}, "ImportID": 1, "Size": 100, "Status": "Complete"}}
        kit.client_list_imports.return_value = {"success": True, "result": [{"Root": {"/": "imported_cid"}}]}
        kit.client_find_data.return_value = {"success": True, "result": [{"Miner": "f01000"}]}
        kit.client_list_deals.return_value = {"success": True, "result": [{"DealID": 1}]}
        kit.client_deal_info.return_value = {"success": True, "result": {"State": 0}}
        # Simulate successful deal start returning a Deal CID
        kit.client_start_deal.return_value = {"success": True, "result": {"/": "deal_cid"}}
        # Simulate successful retrieval (lotus_kit doesn't return content, just success/fail)
        kit.client_retrieve.return_value = {"success": True}
        kit.list_miners.return_value = {"success": True, "result": ["f01000"]}
        kit.miner_get_info.return_value = {"success": True, "result": {"PeerId": "mock_peerid"}}
        return kit

    @pytest.fixture
    def mock_ipfs_model(self):
        """Mock the IPFS model instance using AsyncMock."""
        # Use AsyncMock for async methods
        mock = AsyncMock(spec=MockIPFSModel) # Spec against our simple mock class or a real one if available
        mock.get_content = AsyncMock(side_effect=MockIPFSModel().get_content)
        mock.add_content = AsyncMock(side_effect=MockIPFSModel().add_content)
        mock.pin_content = AsyncMock(side_effect=MockIPFSModel().pin_content)
        return mock

    @pytest.fixture
    def mock_cache_manager(self):
        """Mock the Cache Manager."""
        return MagicMock()

    @pytest.fixture
    def mock_credential_manager(self):
        """Mock the Credential Manager."""
        return MagicMock()

    @pytest.fixture
    def model(self, mock_lotus_kit, mock_ipfs_model, mock_cache_manager, mock_credential_manager):
        """Create FilecoinModel instance with mocked dependencies."""
        model = FilecoinModel(
            lotus_kit_instance=mock_lotus_kit,
            ipfs_model=mock_ipfs_model,
            cache_manager=mock_cache_manager,
            credential_manager=mock_credential_manager
        )
        # Mock the internal _get_file_size helper to avoid actual file system access in most tests
        model._get_file_size = MagicMock(return_value=1234) # Default mock size
        return model

    # --- Test Basic Operations ---

    def test_check_connection_success(self, model, mock_lotus_kit):
        """Test successful connection check."""
        result = model.check_connection()
        assert result["success"] is True
        assert result["connected"] is True
        assert result["version"] == "mock_version"
        mock_lotus_kit.check_connection.assert_called_once()

    def test_check_connection_failure(self, model, mock_lotus_kit):
        """Test failed connection check."""
        mock_lotus_kit.check_connection.return_value = {"success": False, "error": "Connection Refused"}
        result = model.check_connection()
        assert result["success"] is False
        assert result.get("connected") is None # Should not be present on failure
        assert result["error"] == "Connection Refused"
        mock_lotus_kit.check_connection.assert_called_once()

    def test_list_wallets_success(self, model, mock_lotus_kit):
        """Test listing wallets successfully."""
        result = model.list_wallets()
        assert result["success"] is True
        assert result["wallets"] == ["mock_wallet1"]
        assert result["count"] == 1
        mock_lotus_kit.list_wallets.assert_called_once()

    def test_get_wallet_balance_success(self, model, mock_lotus_kit):
        """Test getting wallet balance successfully."""
        address = "mock_wallet1"
        result = model.get_wallet_balance(address)
        assert result["success"] is True
        assert result["address"] == address
        assert result["balance"] == "1000"
        mock_lotus_kit.wallet_balance.assert_called_once_with(address)

    def test_create_wallet_success(self, model, mock_lotus_kit):
        """Test creating a wallet successfully."""
        wallet_type = "bls"
        result = model.create_wallet(wallet_type)
        assert result["success"] is True
        assert result["address"] == "new_mock_wallet"
        assert result["wallet_type"] == wallet_type
        mock_lotus_kit.create_wallet.assert_called_once_with(wallet_type)

    # --- Test File/Deal Operations ---

    @patch("os.path.exists", return_value=True) # Mock file existence check
    def test_import_file_success(self, mock_exists, model, mock_lotus_kit):
        """Test importing a file successfully."""
        file_path = "/fake/path/to/file.txt"
        model._get_file_size = MagicMock(return_value=100) # Set specific size for this test
        result = model.import_file(file_path)
        assert result["success"] is True
        assert result["root"] == "imported_cid"
        assert result["file_path"] == file_path
        assert result["size_bytes"] == 100
        mock_lotus_kit.client_import.assert_called_once_with(file_path)
        mock_exists.assert_called_once_with(file_path)
        model._get_file_size.assert_called_once_with(file_path)

    @patch("os.path.exists", return_value=False) # Mock file non-existence
    def test_import_file_not_found(self, mock_exists, model):
        """Test importing a file that does not exist."""
        file_path = "/fake/path/to/nonexistent.txt"
        result = model.import_file(file_path)
        assert result["success"] is False
        assert result["error_type"] == "FileNotFoundError"
        mock_exists.assert_called_once_with(file_path)

    def test_list_imports_success(self, model, mock_lotus_kit):
        """Test listing imports successfully."""
        result = model.list_imports()
        assert result["success"] is True
        assert result["imports"] == [{"Root": {"/": "imported_cid"}}]
        assert result["count"] == 1
        mock_lotus_kit.client_list_imports.assert_called_once()

    def test_find_data_success(self, model, mock_lotus_kit):
        """Test finding data successfully."""
        data_cid = "find_this_cid"
        result = model.find_data(data_cid)
        assert result["success"] is True
        assert result["cid"] == data_cid
        assert result["locations"] == [{"Miner": "f01000"}]
        assert result["count"] == 1
        mock_lotus_kit.client_find_data.assert_called_once_with(data_cid)

    def test_list_deals_success(self, model, mock_lotus_kit):
        """Test listing deals successfully."""
        result = model.list_deals()
        assert result["success"] is True
        assert result["deals"] == [{"DealID": 1}]
        assert result["count"] == 1
        mock_lotus_kit.client_list_deals.assert_called_once()

    def test_get_deal_info_success(self, model, mock_lotus_kit):
        """Test getting deal info successfully."""
        deal_id = 1
        result = model.get_deal_info(deal_id)
        assert result["success"] is True
        assert result["deal_id"] == deal_id
        assert result["deal_info"] == {"State": 0}
        mock_lotus_kit.client_deal_info.assert_called_once_with(deal_id)

    def test_start_deal_success(self, model, mock_lotus_kit):
        """Test starting a deal successfully."""
        data_cid = "imported_cid"
        miner = "f01000"
        price = "100"
        duration = 518400
        wallet = "mock_wallet1" # Explicitly provide wallet
        result = model.start_deal(data_cid, miner, price, duration, wallet=wallet)
        assert result["success"] is True
        assert result["deal_cid"] == "deal_cid"
        assert result["data_cid"] == data_cid
        assert result["miner"] == miner
        mock_lotus_kit.client_start_deal.assert_called_once_with(
            data_cid=data_cid, miner=miner, price=price, duration=duration,
            wallet=wallet, verified=False, fast_retrieval=True
        )

    def test_start_deal_default_wallet(self, model, mock_lotus_kit):
        """Test starting a deal using the default wallet."""
        data_cid = "imported_cid"
        miner = "f01000"
        price = "100"
        duration = 518400
        # Don't provide wallet, expect it to be fetched
        result = model.start_deal(data_cid, miner, price, duration)
        assert result["success"] is True
        assert result["deal_cid"] == "deal_cid"
        mock_lotus_kit.list_wallets.assert_called_once() # Should be called to get default
        mock_lotus_kit.client_start_deal.assert_called_once_with(
            data_cid=data_cid, miner=miner, price=price, duration=duration,
            wallet="mock_wallet1", # The default fetched wallet
            verified=False, fast_retrieval=True
        )

    @patch("os.makedirs") # Mock directory creation
    @patch("ipfs_kit_py.mcp.models.storage.filecoin_model.FilecoinModel._get_file_size", return_value=500) # Mock file size check after retrieval
    def test_retrieve_data_success(self, mock_get_size, mock_makedirs, model, mock_lotus_kit):
        """Test retrieving data successfully."""
        data_cid = "retrieve_cid"
        out_file = "/tmp/output/retrieved_file.dat"
        result = model.retrieve_data(data_cid, out_file)
        assert result["success"] is True
        assert result["cid"] == data_cid
        assert result["file_path"] == out_file
        assert result["size_bytes"] == 500
        mock_makedirs.assert_called_once_with(os.path.dirname(out_file), exist_ok=True)
        mock_lotus_kit.client_retrieve.assert_called_once_with(data_cid, out_file)
        mock_get_size.assert_called_once_with(out_file)

    # --- Test Miner Operations ---

    def test_list_miners_success(self, model, mock_lotus_kit):
        """Test listing miners successfully."""
        result = model.list_miners()
        assert result["success"] is True
        assert result["miners"] == ["f01000"]
        assert result["count"] == 1
        mock_lotus_kit.list_miners.assert_called_once()

    def test_get_miner_info_success(self, model, mock_lotus_kit):
        """Test getting miner info successfully."""
        miner_address = "f01000"
        result = model.get_miner_info(miner_address)
        assert result["success"] is True
        assert result["miner_address"] == miner_address
        assert result["miner_info"] == {"PeerId": "mock_peerid"}
        mock_lotus_kit.miner_get_info.assert_called_once_with(miner_address)

    # --- Test Cross-Service Operations (Async) ---

    @pytest.mark.anyio
    @patch("os.path.exists", return_value=True)
    @patch("os.unlink") # Mock file deletion
    @patch("tempfile.NamedTemporaryFile") # Mock temporary file creation
    async def test_ipfs_to_filecoin_success(self, mock_tempfile, mock_unlink, mock_exists, model, mock_lotus_kit, mock_ipfs_model):
        """Test transferring content from IPFS to Filecoin successfully."""
        # Setup mock temporary file
        mock_file_handle = MagicMock()
        mock_file_handle.__enter__.return_value.name = "/tmp/fake_temp_file"
        mock_file_handle.__enter__.return_value.write = MagicMock()
        mock_file_handle.__enter__.return_value.flush = MagicMock()
        mock_tempfile.return_value = mock_file_handle

        # Mock import_file call within the method
        model.import_file = MagicMock(return_value={"success": True, "root": "imported_cid", "size_bytes": 12})
        # Mock start_deal call within the method
        model.start_deal = MagicMock(return_value={"success": True, "deal_cid": "deal_cid"})

        ipfs_cid = "valid_ipfs_cid"
        miner = "f01000"
        price = "100"
        duration = 518400

        result = await model.ipfs_to_filecoin(ipfs_cid, miner, price, duration)

        assert result["success"] is True
        assert result["ipfs_cid"] == ipfs_cid
        assert result["filecoin_cid"] == "imported_cid"
        assert result["deal_cid"] == "deal_cid"
        assert result["size_bytes"] == 12 # From mocked import_file

        # Check mocks
        mock_ipfs_model.get_content.assert_awaited_once_with(ipfs_cid)
        mock_tempfile.assert_called_once() # Temp file created
        mock_file_handle.__enter__.return_value.write.assert_called_once_with(b"ipfs_content")
        mock_unlink.assert_called_once_with("/tmp/fake_temp_file") # Temp file deleted
        model.import_file.assert_called_once_with("/tmp/fake_temp_file")
        model.start_deal.assert_called_once_with(
            data_cid="imported_cid", miner=miner, price=price, duration=duration,
            wallet=None, verified=False, fast_retrieval=True, pin=True # Default pin=True
        )
        # Pinning happens in IPFS model, check if it was called
        mock_ipfs_model.pin_content.assert_not_called() # Pinning happens *after* successful IPFS add in the other direction

    @pytest.mark.anyio
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    @patch("builtins.open", new_callable=mock_open, read_data=b"filecoin_content") # Mock reading the temp file, use imported mock_open
    async def test_filecoin_to_ipfs_success(self, mock_open_func, mock_tempfile, mock_unlink, model, mock_lotus_kit, mock_ipfs_model): # Renamed mock_open fixture param
        """Test transferring content from Filecoin to IPFS successfully."""
        # Setup mock temporary file
        mock_file_handle = MagicMock()
        mock_file_handle.__enter__.return_value.name = "/tmp/fake_temp_file_fc"
        mock_tempfile.return_value = mock_file_handle

        # Mock retrieve_data call within the method
        model.retrieve_data = MagicMock(return_value={"success": True, "size_bytes": 16}) # Simulate retrieval success
        # Mock _get_file_size called after retrieval
        model._get_file_size = MagicMock(return_value=16)

        data_cid = "valid_filecoin_cid"

        result = await model.filecoin_to_ipfs(data_cid, pin=True)

        assert result["success"] is True
        assert result["filecoin_cid"] == data_cid
        assert result["ipfs_cid"] == "new_ipfs_cid"
        assert result["size_bytes"] == 16

        # Check mocks
        model.retrieve_data.assert_called_once_with(data_cid, "/tmp/fake_temp_file_fc")
        mock_tempfile.assert_called_once()
        mock_open_func.assert_called_once_with("/tmp/fake_temp_file_fc", "rb") # Check file was opened for reading
        mock_unlink.assert_called_once_with("/tmp/fake_temp_file_fc")
        mock_ipfs_model.add_content.assert_awaited_once_with(b"filecoin_content")
        mock_ipfs_model.pin_content.assert_awaited_once_with("new_ipfs_cid") # Pinning should happen

    # --- Test Error Handling ---

    def test_operation_failure_propagates(self, model, mock_lotus_kit):
        """Test that errors from lotus_kit are propagated correctly."""
        mock_lotus_kit.list_wallets.return_value = {"success": False, "error": "Lotus Daemon Down", "error_type": "ConnectionError"}
        result = model.list_wallets()
        assert result["success"] is False
        assert result["error"] == "Lotus Daemon Down"
        assert result["error_type"] == "ConnectionError"

    def test_missing_dependency(self, mock_ipfs_model, mock_cache_manager, mock_credential_manager):
        """Test model initialization and operation with missing lotus_kit."""
        model_no_kit = FilecoinModel(
            lotus_kit_instance=None, # Explicitly None
            ipfs_model=mock_ipfs_model,
            cache_manager=mock_cache_manager,
            credential_manager=mock_credential_manager
        )
        result = model_no_kit.list_wallets()
        assert result["success"] is False
        assert result["error"] == "Lotus kit not available"
        assert result["error_type"] == "DependencyError"

    @pytest.mark.anyio
    async def test_ipfs_to_filecoin_ipfs_failure(self, model, mock_ipfs_model):
        """Test ipfs_to_filecoin when IPFS retrieval fails."""
        # Mock IPFS get_content to fail
        mock_ipfs_model.get_content = AsyncMock(return_value={"success": False, "error": "IPFS Not Found"})

        result = await model.ipfs_to_filecoin("invalid_ipfs_cid", "f01000", "100", 518400)
        assert result["success"] is False
        assert "Failed to retrieve content from IPFS" in result["error"]
        assert result["error_type"] == "IPFSGetError"
        # Ensure no further operations (like import or deal) were attempted
        assert "import_result" not in result
        assert "deal_result" not in result

    @pytest.mark.anyio
    @patch("os.path.exists", return_value=True)
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    async def test_ipfs_to_filecoin_import_failure(self, mock_tempfile, mock_unlink, mock_exists, model, mock_ipfs_model):
        """Test ipfs_to_filecoin when Lotus import fails."""
        # Setup mock temporary file
        mock_file_handle = MagicMock()
        mock_file_handle.__enter__.return_value.name = "/tmp/fake_temp_file"
        mock_tempfile.return_value = mock_file_handle

        # Mock IPFS success
        mock_ipfs_model.get_content = AsyncMock(return_value={"success": True, "data": b"ipfs_content"})
        # Mock import_file failure
        model.import_file = MagicMock(return_value={"success": False, "error": "Import Failed"})
        # Mock start_deal should not be called
        model.start_deal = MagicMock()

        result = await model.ipfs_to_filecoin("valid_ipfs_cid", "f01000", "100", 518400)

        assert result["success"] is False
        assert "Failed to import content to Lotus" in result["error"]
        assert result["error_type"] == "LotusImportError"
        model.import_file.assert_called_once()
        model.start_deal.assert_not_called() # Deal should not be started
        mock_unlink.assert_called_once() # Temp file should still be cleaned up
