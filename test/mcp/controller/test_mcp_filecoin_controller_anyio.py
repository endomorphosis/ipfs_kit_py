"""
Test module for FilecoinControllerAnyIO in MCP server.

This module tests the AnyIO version of FilecoinController which provides
async/await support for both asyncio and trio backends.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import anyio


@pytest.fixture
def mock_filecoin_model():
    """Create a mock filecoin model with async methods."""
    model = MagicMock()

    # Configure async method mocks
    model.check_connection_async = MagicMock()
    model.list_wallets_async = MagicMock()
    model.get_wallet_balance_async = MagicMock()
    model.create_wallet_async = MagicMock()
    model.import_file_async = MagicMock()
    model.list_imports_async = MagicMock()
    model.list_deals_async = MagicMock()
    model.get_deal_info_async = MagicMock()
    model.start_deal_async = MagicMock()
    model.retrieve_data_async = MagicMock()
    model.list_miners_async = MagicMock()
    model.get_miner_info_async = MagicMock()
    model.ipfs_to_filecoin_async = MagicMock()
    model.filecoin_to_ipfs_async = MagicMock()

    return model


@pytest.fixture
def controller(mock_filecoin_model):
    """Create FilecoinControllerAnyIO instance with mock model."""
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller_anyio import FilecoinControllerAnyIO
    return FilecoinControllerAnyIO(mock_filecoin_model)


@pytest.fixture
def app(controller):
    """Create FastAPI app with controller routes."""
    app = FastAPI()
    router = APIRouter()
    controller.register_routes(router)
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestFilecoinControllerAnyIO:
    """Test cases for FilecoinControllerAnyIO."""

    def test_initialization(self, controller, mock_filecoin_model):
        """Test FilecoinControllerAnyIO initialization."""
        assert controller.filecoin_model == mock_filecoin_model

    def test_route_registration(self, controller):
        """Test that routes are registered correctly."""
        router = APIRouter()
        controller.register_routes(router)

        # Extract route paths
        route_paths = [route.path for route in router.routes]

        # Check core endpoints
        assert "/filecoin/status" in route_paths
        assert "/filecoin/wallets" in route_paths
        assert "/filecoin/wallet/balance/{address}" in route_paths
        assert "/filecoin/wallet/create" in route_paths
        assert "/filecoin/import" in route_paths
        assert "/filecoin/imports" in route_paths
        assert "/filecoin/deals" in route_paths
        assert "/filecoin/deal/{deal_id}" in route_paths
        assert "/filecoin/deal/start" in route_paths
        assert "/filecoin/retrieve" in route_paths
        assert "/filecoin/miners" in route_paths
        assert "/filecoin/miner/info" in route_paths
        assert "/filecoin/from_ipfs" in route_paths
        assert "/filecoin/to_ipfs" in route_paths

    @pytest.mark.anyio
    async def test_handle_status_request(self, client, mock_filecoin_model):
        """Test handling status request."""
        # Configure mock response
        mock_filecoin_model.check_connection_async.return_value = {
            "success": True,
            "connected": True,
            "version": "1.19.1+calibnet",
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/status")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["backend"] == "filecoin"
        assert response_data["is_available"] is True
        assert response_data["connected"] is True
        assert response_data["version"] == "1.19.1+calibnet"

        # Check that async model method was called
        mock_filecoin_model.check_connection_async.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_status_request_error(self, client, mock_filecoin_model):
        """Test handling status request with error."""
        # Configure mock response
        mock_filecoin_model.check_connection_async.return_value = {
            "success": False,
            "error": "Failed to connect to Lotus API",
            "error_type": "ConnectionError",
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/status")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True  # Overall operation success
        assert response_data["is_available"] is False
        assert response_data["error"] == "Failed to connect to Lotus API"

        # Check that async model method was called
        mock_filecoin_model.check_connection_async.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_list_wallets_request(self, client, mock_filecoin_model):
        """Test handling list wallets request."""
        # Configure mock response
        mock_filecoin_model.list_wallets_async.return_value = {
            "success": True,
            "wallets": ["f1test123", "f1test456"],
            "count": 2,
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/wallets")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["wallets"] == ["f1test123", "f1test456"]
        assert response_data["count"] == 2

        # Check that async model method was called
        mock_filecoin_model.list_wallets_async.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_wallet_balance_request(self, client, mock_filecoin_model):
        """Test handling wallet balance request."""
        # Configure mock response
        mock_filecoin_model.get_wallet_balance_async.return_value = {
            "success": True,
            "address": "f1test123",
            "balance": "10000000000000000000",
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/wallet/balance/f1test123")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["address"] == "f1test123"
        assert response_data["balance"] == "10000000000000000000"

        # Check that async model method was called with correct parameters
        mock_filecoin_model.get_wallet_balance_async.assert_called_once_with("f1test123")

    @pytest.mark.anyio
    async def test_handle_create_wallet_request(self, client, mock_filecoin_model):
        """Test handling create wallet request."""
        # Configure mock response
        mock_filecoin_model.create_wallet_async.return_value = {
            "success": True,
            "address": "f1test789",
            "wallet_type": "bls",
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "wallet_type": "bls"
        }

        # Send request
        response = client.post("/filecoin/wallet/create", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["address"] == "f1test789"
        assert response_data["wallet_type"] == "bls"

        # Check that async model method was called with correct parameters
        mock_filecoin_model.create_wallet_async.assert_called_once_with(wallet_type="bls")

    @pytest.mark.anyio
    async def test_handle_import_file_request(self, client, mock_filecoin_model):
        """Test handling import file request."""
        # Configure mock response
        mock_filecoin_model.import_file_async.return_value = {
            "success": True,
            "root": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "file_path": "/tmp/test_file.txt",
            "importid": 12345,
            "status": "Importing",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "file_path": "/tmp/test_file.txt"
        }

        # Send request
        response = client.post("/filecoin/import", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["root"] == "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
        assert response_data["file_path"] == "/tmp/test_file.txt"
        assert response_data["size_bytes"] == 100

        # Check that async model method was called with correct parameters
        mock_filecoin_model.import_file_async.assert_called_once_with(file_path="/tmp/test_file.txt")

    @pytest.mark.anyio
    async def test_handle_list_imports_request(self, client, mock_filecoin_model):
        """Test handling list imports request."""
        # Configure mock response
        mock_imports = [
            {
                "Key": 1,
                "Root": {"/" : "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"},
                "Source": "import1.txt",
                "FilePath": "/path/to/import1.txt",
                "Size": 100
            },
            {
                "Key": 2,
                "Root": {"/" : "bafk2bzaceduagzgkqswfl32ycl7yofkweru2a63jvkkszp3xuinhna6l3dq2"},
                "Source": "import2.txt",
                "FilePath": "/path/to/import2.txt",
                "Size": 200
            }
        ]
        mock_filecoin_model.list_imports_async.return_value = {
            "success": True,
            "imports": mock_imports,
            "count": 2,
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/imports")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["count"] == 2
        assert len(response_data["imports"]) == 2

        # Check that async model method was called
        mock_filecoin_model.list_imports_async.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_list_deals_request(self, client, mock_filecoin_model):
        """Test handling list deals request."""
        # Configure mock response
        mock_deals = [
            {
                "DealID": 1,
                "Provider": "f01000",
                "State": 7,
                "ClientDealProposal": {
                    "Proposal": {
                        "PieceCID": {
                            "/": "baga6ea4seaqntdmgrqcgbaanqpdf2kzfrgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                        },
                        "Client": "f1test123",
                        "Provider": "f01000",
                        "StartEpoch": 100000,
                        "EndEpoch": 200000,
                        "StoragePricePerEpoch": "1000000000",
                        "ProviderCollateral": "1000000000000",
                        "ClientCollateral": "1000000000000"
                    }
                }
            },
            {
                "DealID": 2,
                "Provider": "f01001",
                "State": 5,
                "ClientDealProposal": {
                    "Proposal": {
                        "PieceCID": {
                            "/": "baga6ea4seaqas5frgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                        },
                        "Client": "f1test123",
                        "Provider": "f01001",
                        "StartEpoch": 100000,
                        "EndEpoch": 200000,
                        "StoragePricePerEpoch": "1000000000",
                        "ProviderCollateral": "1000000000000",
                        "ClientCollateral": "1000000000000"
                    }
                }
            }
        ]
        mock_filecoin_model.list_deals_async.return_value = {
            "success": True,
            "deals": mock_deals,
            "count": 2,
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/deals")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["count"] == 2
        assert len(response_data["deals"]) == 2

        # Check that async model method was called
        mock_filecoin_model.list_deals_async.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_deal_info_request(self, client, mock_filecoin_model):
        """Test handling deal info request."""
        # Configure mock response
        mock_deal_info = {
            "DealID": 1,
            "Provider": "f01000",
            "State": 7,
            "ClientDealProposal": {
                "Proposal": {
                    "PieceCID": {
                        "/": "baga6ea4seaqntdmgrqcgbaanqpdf2kzfrgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                    },
                    "Client": "f1test123",
                    "Provider": "f01000",
                    "StartEpoch": 100000,
                    "EndEpoch": 200000,
                    "StoragePricePerEpoch": "1000000000",
                    "ProviderCollateral": "1000000000000",
                    "ClientCollateral": "1000000000000"
                }
            }
        }
        mock_filecoin_model.get_deal_info_async.return_value = {
            "success": True,
            "deal_id": 1,
            "deal_info": mock_deal_info,
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/deal/1")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["deal_id"] == 1
        assert response_data["deal_info"] == mock_deal_info

        # Check that async model method was called with correct parameters
        mock_filecoin_model.get_deal_info_async.assert_called_once_with(1)

    @pytest.mark.anyio
    async def test_handle_start_deal_request(self, client, mock_filecoin_model):
        """Test handling start deal request."""
        # Configure mock response
        mock_filecoin_model.start_deal_async.return_value = {
            "success": True,
            "deal_cid": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4",
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "wallet": "f1test123",
            "verified": True,
            "fast_retrieval": True,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "wallet": "f1test123",
            "verified": True,
            "fast_retrieval": True
        }

        # Send request
        response = client.post("/filecoin/deal/start", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["deal_cid"] == "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4"
        assert response_data["data_cid"] == "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
        assert response_data["miner"] == "f01000"

        # Check that async model method was called with correct parameters
        mock_filecoin_model.start_deal_async.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            miner="f01000",
            price="1000000000",
            duration=100000,
            wallet="f1test123",
            verified=True,
            fast_retrieval=True
        )

    @pytest.mark.anyio
    async def test_handle_retrieve_data_request(self, client, mock_filecoin_model):
        """Test handling retrieve data request."""
        # Configure mock response
        mock_filecoin_model.retrieve_data_async.return_value = {
            "success": True,
            "cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "file_path": "/tmp/test_output.txt",
            "size_bytes": 1000,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "out_file": "/tmp/test_output.txt"
        }

        # Send request
        response = client.post("/filecoin/retrieve", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["cid"] == "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
        assert response_data["file_path"] == "/tmp/test_output.txt"
        assert response_data["size_bytes"] == 1000

        # Check that async model method was called with correct parameters
        mock_filecoin_model.retrieve_data_async.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            out_file="/tmp/test_output.txt"
        )

    @pytest.mark.anyio
    async def test_handle_list_miners_request(self, client, mock_filecoin_model):
        """Test handling list miners request."""
        # Configure mock response
        mock_filecoin_model.list_miners_async.return_value = {
            "success": True,
            "miners": ["f01000", "f01001", "f01002"],
            "count": 3,
            "duration_ms": 50.5
        }

        # Send request
        response = client.get("/filecoin/miners")

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["miners"] == ["f01000", "f01001", "f01002"]
        assert response_data["count"] == 3

        # Check that async model method was called
        mock_filecoin_model.list_miners_async.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_miner_info_request(self, client, mock_filecoin_model):
        """Test handling miner info request."""
        # Configure mock response
        mock_miner_info = {
            "MinerAddress": "f01000",
            "SectorSize": 34359738368,
            "Multiaddrs": ["/ip4/10.0.0.1/tcp/1234"],
            "PeerID": "12D3KooWJvW4tVa7A1huRyuLivLzS64KndQgYYEir233uJrExHTF"
        }
        mock_filecoin_model.get_miner_info_async.return_value = {
            "success": True,
            "miner_address": "f01000",
            "miner_info": mock_miner_info,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "miner_address": "f01000"
        }

        # Send request
        response = client.post("/filecoin/miner/info", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["miner_address"] == "f01000"
        assert response_data["miner_info"] == mock_miner_info

        # Check that async model method was called with correct parameters
        mock_filecoin_model.get_miner_info_async.assert_called_once_with(miner_address="f01000")

    @pytest.mark.anyio
    async def test_handle_ipfs_to_filecoin_request(self, client, mock_filecoin_model):
        """Test handling IPFS to Filecoin request."""
        # Configure mock response
        mock_filecoin_model.ipfs_to_filecoin_async.return_value = {
            "success": True,
            "ipfs_cid": "QmTestCid",
            "filecoin_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "deal_cid": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "cid": "QmTestCid",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "wallet": "f1test123",
            "verified": True,
            "fast_retrieval": True,
            "pin": True
        }

        # Send request
        response = client.post("/filecoin/from_ipfs", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["ipfs_cid"] == "QmTestCid"
        assert response_data["filecoin_cid"] == "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
        assert response_data["deal_cid"] == "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4"

        # Check that async model method was called with correct parameters
        mock_filecoin_model.ipfs_to_filecoin_async.assert_called_once_with(
            cid="QmTestCid",
            miner="f01000",
            price="1000000000",
            duration=100000,
            wallet="f1test123",
            verified=True,
            fast_retrieval=True,
            pin=True
        )

    @pytest.mark.anyio
    async def test_handle_filecoin_to_ipfs_request(self, client, mock_filecoin_model):
        """Test handling Filecoin to IPFS request."""
        # Configure mock response
        mock_filecoin_model.filecoin_to_ipfs_async.return_value = {
            "success": True,
            "filecoin_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "ipfs_cid": "QmNewTestCid",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "pin": True
        }

        # Send request
        response = client.post("/filecoin/to_ipfs", json=request_data)

        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["filecoin_cid"] == "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
        assert response_data["ipfs_cid"] == "QmNewTestCid"
        assert response_data["size_bytes"] == 100

        # Check that async model method was called with correct parameters
        mock_filecoin_model.filecoin_to_ipfs_async.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            pin=True
        )

    @pytest.mark.anyio
    async def test_handle_request_with_error(self, client, mock_filecoin_model):
        """Test handling a request that results in an error response."""
        # Configure mock to return error
        mock_filecoin_model.start_deal_async.return_value = {
            "success": False,
            "error": "Failed to start deal",
            "error_type": "StartDealError"
        }

        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000
        }

        # Send request
        response = client.post("/filecoin/deal/start", json=request_data)

        # Check response
        assert response.status_code == 500
        response_data = response.json()
        assert response_data["detail"]["error"] == "Failed to start deal"
        assert response_data["detail"]["error_type"] == "StartDealError"

        # Check that async model method was called
        mock_filecoin_model.start_deal_async.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
