import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import anyio

# Adjust imports based on actual file structure
from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel

class TestFilecoinController:
    @pytest.fixture
    def mock_model(self):
        """Create mock model with appropriate return values."""
        model = MagicMock(spec=FilecoinModel)
        # Configure default mock return values for common methods
        model.check_connection.return_value = {"success": True, "connected": True, "version": "mock_version"}
        model.list_wallets.return_value = {"success": True, "wallets": ["mock_wallet1"], "count": 1}
        model.get_wallet_balance.return_value = {"success": True, "address": "mock_wallet1", "balance": "1000"}
        model.create_wallet.return_value = {"success": True, "address": "new_mock_wallet", "wallet_type": "bls"}
        model.import_file.return_value = {"success": True, "root": "mock_cid_root", "file_path": "/path/to/file", "size_bytes": 1024}
        model.list_imports.return_value = {"success": True, "imports": [{"Root": {"/": "mock_cid_root"}}], "count": 1}
        model.list_deals.return_value = {"success": True, "deals": [{"DealID": 1}], "count": 1}
        model.get_deal_info.return_value = {"success": True, "deal_id": 1, "deal_info": {"State": 0}}
        model.start_deal.return_value = {"success": True, "deal_cid": "mock_deal_cid"}
        model.retrieve_data.return_value = {"success": True, "cid": "mock_data_cid", "file_path": "/output/path", "size_bytes": 1024}
        model.list_miners.return_value = {"success": True, "miners": ["f01000"], "count": 1}
        model.get_miner_info.return_value = {"success": True, "miner_address": "f01000", "miner_info": {"PeerId": "mock_peerid"}}
        model.ipfs_to_filecoin.return_value = {"success": True, "ipfs_cid": "ipfs_cid", "filecoin_cid": "filecoin_cid", "deal_cid": "deal_cid"}
        model.filecoin_to_ipfs.return_value = {"success": True, "filecoin_cid": "filecoin_cid", "ipfs_cid": "ipfs_cid"}
        return model

    @pytest.fixture
    def app(self, mock_model):
        """Create FastAPI app with controller routes."""
        app = FastAPI()
        # Pass the mocked model to the controller
        controller = FilecoinController(filecoin_model=mock_model)
        controller.register_routes(app.router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    # --- Test Methods Will Go Here ---

    def test_status_endpoint(self, client, mock_model):
        """Test the /filecoin/status endpoint."""
        response = client.get("/filecoin/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "check_connection"
        assert data["is_available"] is True
        assert data["backend"] == "filecoin"
        assert data["version"] == "mock_version"
        mock_model.check_connection.assert_called_once()

    def test_list_wallets_endpoint(self, client, mock_model):
        """Test the /filecoin/wallets endpoint."""
        response = client.get("/filecoin/wallets")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "list_wallets"
        assert data["wallets"] == ["mock_wallet1"]
        assert data["count"] == 1
        mock_model.list_wallets.assert_called_once()

    def test_wallet_balance_endpoint(self, client, mock_model):
        """Test the /filecoin/wallet/balance/{address} endpoint."""
        address = "mock_wallet1"
        response = client.get(f"/filecoin/wallet/balance/{address}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "get_wallet_balance"
        assert data["address"] == address
        assert data["balance"] == "1000"
        mock_model.get_wallet_balance.assert_called_once_with(address)

    def test_create_wallet_endpoint(self, client, mock_model):
        """Test the /filecoin/wallet/create endpoint."""
        request_data = {"wallet_type": "bls"}
        response = client.post("/filecoin/wallet/create", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "create_wallet"
        assert data["address"] == "new_mock_wallet"
        assert data["wallet_type"] == "bls"
        mock_model.create_wallet.assert_called_once_with(wallet_type="bls")

    def test_import_file_endpoint(self, client, mock_model):
        """Test the /filecoin/import endpoint."""
        request_data = {"file_path": "/path/to/file"}
        response = client.post("/filecoin/import", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "import_file"
        assert data["root"] == "mock_cid_root"
        assert data["file_path"] == "/path/to/file"
        assert data["size_bytes"] == 1024
        mock_model.import_file.assert_called_once_with(file_path="/path/to/file")

    def test_list_imports_endpoint(self, client, mock_model):
        """Test the /filecoin/imports endpoint."""
        response = client.get("/filecoin/imports")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "list_imports"
        assert data["imports"] == [{"Root": {"/": "mock_cid_root"}}]
        assert data["count"] == 1
        mock_model.list_imports.assert_called_once()

    def test_list_deals_endpoint(self, client, mock_model):
        """Test the /filecoin/deals endpoint."""
        response = client.get("/filecoin/deals")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "list_deals"
        assert data["deals"] == [{"DealID": 1}]
        assert data["count"] == 1
        mock_model.list_deals.assert_called_once()

    def test_deal_info_endpoint(self, client, mock_model):
        """Test the /filecoin/deal/{deal_id} endpoint."""
        deal_id = 1
        response = client.get(f"/filecoin/deal/{deal_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "get_deal_info"
        assert data["deal_id"] == deal_id
        assert data["deal_info"] == {"State": 0}
        mock_model.get_deal_info.assert_called_once_with(deal_id)

    def test_start_deal_endpoint(self, client, mock_model):
        """Test the /filecoin/deal/start endpoint."""
        request_data = {
            "data_cid": "mock_data_cid",
            "miner": "f01000",
            "price": "100",
            "duration": 518400, # Example duration
            "wallet": "mock_wallet1",
            "verified": False,
            "fast_retrieval": True
        }
        response = client.post("/filecoin/deal/start", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "start_deal"
        assert data["deal_cid"] == "mock_deal_cid"
        mock_model.start_deal.assert_called_once_with(
            data_cid="mock_data_cid",
            miner="f01000",
            price="100",
            duration=518400,
            wallet="mock_wallet1",
            verified=False,
            fast_retrieval=True
        )

    def test_retrieve_data_endpoint(self, client, mock_model):
        """Test the /filecoin/retrieve endpoint."""
        request_data = {
            "data_cid": "mock_data_cid",
            "out_file": "/output/path"
        }
        response = client.post("/filecoin/retrieve", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "retrieve_data"
        assert data["cid"] == "mock_data_cid"
        assert data["file_path"] == "/output/path"
        assert data["size_bytes"] == 1024
        mock_model.retrieve_data.assert_called_once_with(
            data_cid="mock_data_cid",
            out_file="/output/path"
        )

    def test_list_miners_endpoint(self, client, mock_model):
        """Test the /filecoin/miners endpoint."""
        response = client.get("/filecoin/miners")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "list_miners"
        assert data["miners"] == ["f01000"]
        assert data["count"] == 1
        mock_model.list_miners.assert_called_once()

    def test_miner_info_endpoint(self, client, mock_model):
        """Test the /filecoin/miner/info endpoint."""
        request_data = {"miner_address": "f01000"}
        response = client.post("/filecoin/miner/info", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "get_miner_info"
        assert data["miner_address"] == "f01000"
        assert data["miner_info"] == {"PeerId": "mock_peerid"}
        mock_model.get_miner_info.assert_called_once_with(miner_address="f01000")

    def test_ipfs_to_filecoin_endpoint(self, client, mock_model):
        """Test the /filecoin/from_ipfs endpoint."""
        request_data = {
            "cid": "ipfs_cid",
            "miner": "f01000",
            "price": "100",
            "duration": 518400,
            "wallet": "mock_wallet1",
            "verified": False,
            "fast_retrieval": True,
            "pin": True
        }
        response = client.post("/filecoin/from_ipfs", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "ipfs_to_filecoin"
        assert data["ipfs_cid"] == "ipfs_cid"
        assert data["filecoin_cid"] == "filecoin_cid"
        assert data["deal_cid"] == "deal_cid"
        mock_model.ipfs_to_filecoin.assert_called_once_with(
            cid="ipfs_cid",
            miner="f01000",
            price="100",
            duration=518400,
            wallet="mock_wallet1",
            verified=False,
            fast_retrieval=True,
            pin=True
        )

    def test_filecoin_to_ipfs_endpoint(self, client, mock_model):
        """Test the /filecoin/to_ipfs endpoint."""
        request_data = {
            "data_cid": "filecoin_cid",
            "pin": True
        }
        response = client.post("/filecoin/to_ipfs", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation"] == "filecoin_to_ipfs"
        assert data["filecoin_cid"] == "filecoin_cid"
        assert data["ipfs_cid"] == "ipfs_cid"
        mock_model.filecoin_to_ipfs.assert_called_once_with(
            data_cid="filecoin_cid",
            pin=True
        )

    # --- Test Error Handling ---

    def test_status_endpoint_error(self, client, mock_model):
        """Test the /filecoin/status endpoint when model fails."""
        mock_model.check_connection.return_value = {"success": False, "error": "Connection failed", "error_type": "ConnectionError"}
        response = client.get("/filecoin/status")
        # Status endpoint should still return 200 but indicate failure in the body
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True # The endpoint call itself succeeded
        assert data["is_available"] is False
        assert data["error"] == "Connection failed"
        mock_model.check_connection.assert_called_once()

    def test_list_wallets_endpoint_error(self, client, mock_model):
        """Test the /filecoin/wallets endpoint when model fails."""
        mock_model.list_wallets.return_value = {"success": False, "error": "Cannot list wallets", "error_type": "WalletListError"}
        response = client.get("/filecoin/wallets")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "Cannot list wallets"
        assert data["detail"]["error_type"] == "WalletListError"
        mock_model.list_wallets.assert_called_once()

    def test_start_deal_endpoint_error(self, client, mock_model):
        """Test the /filecoin/deal/start endpoint when model fails."""
        mock_model.start_deal.return_value = {"success": False, "error": "Deal failed", "error_type": "StartDealError"}
        request_data = {
            "data_cid": "mock_data_cid", "miner": "f01000", "price": "100", "duration": 518400
        }
        response = client.post("/filecoin/deal/start", json=request_data)
        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "Deal failed"
        assert data["detail"]["error_type"] == "StartDealError"
        # Check that the model method was called with the correct arguments
        mock_model.start_deal.assert_called_once_with(
            data_cid="mock_data_cid",
            miner="f01000",
            price="100",
            duration=518400,
            wallet=None, # Default value if not provided
            verified=False, # Default value
            fast_retrieval=True # Default value
        )
