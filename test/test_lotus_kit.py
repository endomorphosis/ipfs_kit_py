import json
import os
import tempfile
import unittest
from unittest import mock
import subprocess

import pytest
import requests

from ipfs_kit_py.lotus_kit import (
    LotusConnectionError,
    LotusError,
    LotusTimeoutError,
    lotus_kit,
    create_result_dict,
    handle_error,
)


# Mock responses for Lotus API calls
MOCK_VERSION_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "Version": "1.23.0+git.5a722a82f",
        "APIVersion": "v1.10.0",
        "BlockDelay": 30
    },
    "id": 1
}

MOCK_CHAIN_HEAD_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "Cids": [
            {"/": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4"}
        ],
        "Blocks": [
            {
                "Miner": "t01000",
                "Ticket": {
                    "VRFProof": "vdFSBHrMdtSHUmxH/CcJQM1k7DtKRYZr0URnc/7Jpf/gCA/9nN8PJ9YZZ7dEFgkb"
                },
                "Height": 100000
            }
        ],
        "Height": 100000
    },
    "id": 1
}

MOCK_WALLET_LIST_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        "t1abcdefghijklmnopqrstuvwxyz",
        "t1zyxwvutsrqponmlkjihgfedcba"
    ],
    "id": 1
}

MOCK_WALLET_BALANCE_RESPONSE = {
    "jsonrpc": "2.0",
    "result": "100000000000000000000",
    "id": 1
}

MOCK_WALLET_NEW_RESPONSE = {
    "jsonrpc": "2.0",
    "result": "t1newgeneratedwalletaddress",
    "id": 1
}

MOCK_CLIENT_IMPORT_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "Root": {
            "/": "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"
        },
        "ImportID": 12345
    },
    "id": 1
}

MOCK_CLIENT_LIST_IMPORTS_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {
            "Key": 1,
            "Err": "",
            "Root": {"/": "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"},
            "Source": "import",
            "FilePath": "/path/to/file.txt",
            "CARPath": ""
        }
    ],
    "id": 1
}

MOCK_CLIENT_FIND_DATA_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "Info": [
            {
                "PieceCID": {"/": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"},
                "Size": 65536,
                "Miners": ["t01000", "t02000"]
            }
        ]
    },
    "id": 1
}

MOCK_CLIENT_DEAL_INFO_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "ProposalCid": {"/": "bafyreihpebm7w2tyzctwvepvujvyl5zh5n6n3cpmj7m3advkjdvjdwrpwm"},
        "State": 7,
        "Message": "",
        "Provider": "t01000",
        "DataRef": {
            "TransferType": "graphsync",
            "Root": {"/": "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"}
        },
        "PieceCID": {"/": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"},
        "Size": 65536,
        "PricePerEpoch": "1000",
        "Duration": 1500,
        "DealID": 5,
        "VerifiedDeal": True,
        "FastRetrieval": True
    },
    "id": 1
}

MOCK_CLIENT_LIST_DEALS_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {
            "ProposalCid": {"/": "bafyreihpebm7w2tyzctwvepvujvyl5zh5n6n3cpmj7m3advkjdvjdwrpwm"},
            "State": 7,
            "Provider": "t01000",
            "PieceCID": {"/": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"},
            "Size": 65536,
            "PricePerEpoch": "1000",
            "Duration": 1500,
            "DealID": 5
        }
    ],
    "id": 1
}

MOCK_CLIENT_START_DEAL_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "/": "bafyreihpebm7w2tyzctwvepvujvyl5zh5n6n3cpmj7m3advkjdvjdwrpwm"
    },
    "id": 1
}

MOCK_CLIENT_RETRIEVE_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "DealID": 12345
    },
    "id": 1
}

MOCK_MARKET_LIST_STORAGE_DEALS_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {
            "Proposal": {
                "PieceCID": {"/": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"},
                "PieceSize": 65536,
                "VerifiedDeal": True,
                "Client": "t1abcdefghijklmnopqrstuvwxyz",
                "Provider": "t01000",
                "StartEpoch": 100000,
                "EndEpoch": 101500,
                "StoragePricePerEpoch": "1000",
                "ProviderCollateral": "0",
                "ClientCollateral": "0"
            },
            "State": {
                "SectorStartEpoch": 100100,
                "LastUpdatedEpoch": 100200,
                "SlashEpoch": -1
            }
        }
    ],
    "id": 1
}

MOCK_ERROR_RESPONSE = {
    "jsonrpc": "2.0",
    "error": {
        "code": -32603,
        "message": "internal error: failed to make API request: API not running (are you offline?)"
    },
    "id": 1
}


class TestLotusKit(unittest.TestCase):
    """Test the lotus_kit module functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.metadata = {
            "api_url": "http://localhost:1234/rpc/v0",
            "token": "test-token",
            "lotus_path": "/path/to/lotus",
        }
        self.lotus = lotus_kit(resources=None, metadata=self.metadata)
        self.mock_response = mock.Mock()
        self.mock_response.status_code = 200
        
    @mock.patch("requests.post")
    def test_check_connection(self, mock_post):
        """Test checking connection to Lotus API."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_VERSION_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.check_connection()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["Version"], "1.23.0+git.5a722a82f")
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.Version")
        self.assertEqual(call_args["headers"]["Authorization"], "Bearer test-token")

    @mock.patch("requests.post")
    def test_get_chain_head(self, mock_post):
        """Test getting the chain head."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_CHAIN_HEAD_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.get_chain_head()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["Height"], 100000)
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.ChainHead")

    @mock.patch("requests.post")
    def test_list_wallets(self, mock_post):
        """Test listing wallets."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_WALLET_LIST_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.list_wallets()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]), 2)
        self.assertEqual(result["result"][0], "t1abcdefghijklmnopqrstuvwxyz")
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.WalletList")
    
    @mock.patch("requests.post")
    def test_wallet_balance(self, mock_post):
        """Test getting wallet balance."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_WALLET_BALANCE_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        address = "t1abcdefghijklmnopqrstuvwxyz"
        result = self.lotus.wallet_balance(address)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], "100000000000000000000")
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.WalletBalance")
        self.assertEqual(call_args["json"]["params"], [address])
    
    @mock.patch("requests.post")
    def test_create_wallet(self, mock_post):
        """Test creating a new wallet."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_WALLET_NEW_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.create_wallet(wallet_type="bls")
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], "t1newgeneratedwalletaddress")
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.WalletNew")
        self.assertEqual(call_args["json"]["params"], ["bls"])
        
    @mock.patch("requests.post")
    def test_client_import(self, mock_post):
        """Test importing a file."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_CLIENT_IMPORT_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            file_path = temp_file.name
        
        try:
            # Execute method
            result = self.lotus.client_import(file_path)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(
                result["result"]["Root"]["/"], 
                "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"
            )
            self.assertEqual(result["result"]["ImportID"], 12345)
            
            # Verify request
            mock_post.assert_called_once()
            call_args = mock_post.call_args[1]
            self.assertEqual(call_args["json"]["method"], "Filecoin.ClientImport")
            self.assertEqual(call_args["json"]["params"][0]["Path"], file_path)
            self.assertEqual(call_args["json"]["params"][0]["IsCAR"], False)
        finally:
            # Clean up the temporary file
            os.unlink(file_path)
            
    @mock.patch("requests.post")
    def test_client_list_imports(self, mock_post):
        """Test listing imported files."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_CLIENT_LIST_IMPORTS_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.client_list_imports()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]), 1)
        self.assertEqual(result["result"][0]["Key"], 1)
        self.assertEqual(
            result["result"][0]["Root"]["/"],
            "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"
        )
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.ClientListImports")

    @mock.patch("requests.post")
    def test_client_start_deal(self, mock_post):
        """Test starting a storage deal."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_CLIENT_START_DEAL_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        data_cid = "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"
        miner = "t01000"
        price = "1000"
        duration = 1500
        wallet = "t1abcdefghijklmnopqrstuvwxyz"
        
        result = self.lotus.client_start_deal(
            data_cid=data_cid,
            miner=miner,
            price=price,
            duration=duration,
            wallet=wallet,
            verified=True
        )
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(
            result["result"]["/"],
            "bafyreihpebm7w2tyzctwvepvujvyl5zh5n6n3cpmj7m3advkjdvjdwrpwm"
        )
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.ClientStartDeal")
        params = call_args["json"]["params"][0]
        self.assertEqual(params["Data"]["Root"]["/"], data_cid)
        self.assertEqual(params["Miner"], miner)
        self.assertEqual(params["EpochPrice"], price)
        self.assertEqual(params["MinBlocksDuration"], duration)
        self.assertEqual(params["Wallet"], wallet)
        self.assertEqual(params["VerifiedDeal"], True)
        self.assertEqual(params["FastRetrieval"], True)

    @mock.patch("requests.post")
    def test_client_list_deals(self, mock_post):
        """Test listing storage deals."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_CLIENT_LIST_DEALS_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.client_list_deals()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]), 1)
        self.assertEqual(result["result"][0]["DealID"], 5)
        self.assertEqual(result["result"][0]["Provider"], "t01000")
        self.assertEqual(
            result["result"][0]["ProposalCid"]["/"],
            "bafyreihpebm7w2tyzctwvepvujvyl5zh5n6n3cpmj7m3advkjdvjdwrpwm"
        )
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.ClientListDeals")

    @mock.patch("requests.post")
    def test_client_retrieve(self, mock_post):
        """Test retrieving data from Filecoin."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_CLIENT_RETRIEVE_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        data_cid = "bafybeihykld6tqtlabodxzs5wy2fjpjypgbdxbazlxppcnc5zvvlzggowe"
        out_file = "/tmp/retrieved_file.txt"
        result = self.lotus.client_retrieve(data_cid, out_file)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["DealID"], 12345)
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.ClientRetrieve")
        self.assertEqual(call_args["json"]["params"][0]["/"], data_cid)
        self.assertEqual(call_args["json"]["params"][1]["Path"], out_file)
        self.assertEqual(call_args["json"]["params"][1]["IsCAR"], False)

    @mock.patch("requests.post")
    def test_api_error_handling(self, mock_post):
        """Test API error handling."""
        # Set up mock
        self.mock_response.json.return_value = MOCK_ERROR_RESPONSE
        mock_post.return_value = self.mock_response
        
        # Execute method
        result = self.lotus.check_connection()
        
        # Verify result
        self.assertFalse(result["success"])
        self.assertIn("Error -32603", result["error"])
        self.assertEqual(result["error_type"], "LotusError")

    @mock.patch("requests.post")
    def test_connection_error_handling(self, mock_post):
        """Test connection error handling."""
        # Set up mock
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        # Execute method
        result = self.lotus.check_connection()
        
        # Verify result
        self.assertFalse(result["success"])
        self.assertIn("Failed to connect to Lotus API", result["error"])
        self.assertEqual(result["error_type"], "LotusConnectionError")

    @mock.patch("requests.post")
    def test_timeout_error_handling(self, mock_post):
        """Test timeout error handling."""
        # Set up mock
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        # Execute method
        result = self.lotus.check_connection()
        
        # Verify result
        self.assertFalse(result["success"])
        self.assertIn("Request timed out after", result["error"])
        self.assertEqual(result["error_type"], "LotusTimeoutError")

    @mock.patch("subprocess.run")
    def test_run_lotus_command(self, mock_run):
        """Test running a Lotus CLI command."""
        # Set up mock
        mock_process = mock.Mock()
        mock_process.returncode = 0
        mock_process.stdout = b"Command output"
        mock_process.stderr = b"No errors"
        mock_run.return_value = mock_process
        
        # Execute method
        cmd_args = ["lotus", "wallet", "list"]
        result = self.lotus.run_lotus_command(cmd_args)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "Command output")
        self.assertEqual(result["stderr"], "No errors")
        
        # Verify call
        mock_run.assert_called_once_with(
            cmd_args,
            capture_output=True,
            check=True,
            timeout=60,
            shell=False,
            env=self.lotus.env
        )

    @mock.patch("subprocess.run")
    def test_run_lotus_command_error(self, mock_run):
        """Test error handling when running a Lotus CLI command."""
        # Set up mock
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "lotus wallet list", b"", b"Error message"
        )
        
        # Execute method
        cmd_args = ["lotus", "wallet", "list"]
        result = self.lotus.run_lotus_command(cmd_args)
        
        # Verify result
        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["error_type"], "process_error")
        self.assertIn("Command failed with return code 1", result["error"])
        
    def test_format_bytes(self):
        """Test formatting bytes into human-readable strings."""
        test_cases = [
            (0, "0 B"),
            (1023, "1023.00 B"),
            (1024, "1.00 KiB"),
            (1024 * 1024, "1.00 MiB"),
            (1024 * 1024 * 1024, "1.00 GiB"),
            (1024 * 1024 * 1024 * 1024, "1.00 TiB"),
            (1240 * 1024, "1.21 MiB"),
        ]
        
        for size, expected in test_cases:
            result = self.lotus.format_bytes(size)
            self.assertEqual(result, expected)
            
    def test_format_timestamp(self):
        """Test formatting Unix timestamps."""
        # Test regular timestamp (seconds)
        ts = 1609459200  # 2021-01-01 00:00:00
        result = self.lotus.format_timestamp(ts)
        self.assertEqual(result, "2021-01-01 00:00:00")
        
        # Test custom format
        result = self.lotus.format_timestamp(ts, format_str="%Y-%m-%d")
        self.assertEqual(result, "2021-01-01")
        
        # Test millisecond timestamp
        ms_ts = 1609459200000  # 2021-01-01 00:00:00 in ms
        result = self.lotus.format_timestamp(ms_ts)
        self.assertEqual(result, "2021-01-01 00:00:00")
        
        # Test invalid timestamp
        result = self.lotus.format_timestamp("invalid")
        self.assertEqual(result, "Invalid timestamp")
            
    def test_validate_export_format(self):
        """Test validation of export formats."""
        # Valid format
        format_result, error = self.lotus.validate_export_format("json")
        self.assertEqual(format_result, "json")
        self.assertIsNone(error)
        
        # Valid format with custom supported formats
        format_result, error = self.lotus.validate_export_format(
            "csv", supported_formats=["csv", "parquet"]
        )
        self.assertEqual(format_result, "csv")
        self.assertIsNone(error)
        
        # Invalid format
        format_result, error = self.lotus.validate_export_format("xml")
        self.assertIsNone(format_result)
        self.assertIn("Unsupported format: xml", error)
        
        # Null format defaults to JSON
        format_result, error = self.lotus.validate_export_format(None)
        self.assertEqual(format_result, "json")
        self.assertIsNone(error)
        
    def test_validate_filepath(self):
        """Test filepath validation."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test valid file path (doesn't need to exist)
            path = os.path.join(temp_dir, "test_file.txt")
            is_valid, error = self.lotus.validate_filepath(path)
            self.assertTrue(is_valid)
            self.assertIsNone(error)
            
            # Test path that must exist but doesn't
            is_valid, error = self.lotus.validate_filepath(path, must_exist=True)
            self.assertFalse(is_valid)
            self.assertIn("File does not exist", error)
            
            # Create the file and test again
            with open(path, 'w') as f:
                f.write("test")
                
            is_valid, error = self.lotus.validate_filepath(path, must_exist=True)
            self.assertTrue(is_valid)
            self.assertIsNone(error)
            
            # Test writeable path
            is_valid, error = self.lotus.validate_filepath(
                os.path.join(temp_dir, "new_dir/new_file.txt"), 
                check_writeable=True
            )
            self.assertTrue(is_valid)
            self.assertIsNone(error)
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "new_dir")))
    
    def test_parse_wallet_data(self):
        """Test parsing wallet data from different formats."""
        # Test JSON format
        json_data = '{"Type": "secp256k1", "PrivateKey": "abcd1234", "Address": "t1test"}'
        result = self.lotus.parse_wallet_data(json_data)
        self.assertEqual(result["type"], "secp256k1")
        self.assertEqual(result["private_key"], "abcd1234")
        self.assertEqual(result["address"], "t1test")
        
        # Test key file format
        key_data = "Type: secp256k1\nPrivateKey: abcd1234\nAddress: t1test"
        result = self.lotus.parse_wallet_data(key_data)
        self.assertEqual(result["type"], "secp256k1")
        self.assertEqual(result["private_key"], "abcd1234")
        self.assertEqual(result["address"], "t1test")
        
        # Test hex format
        hex_data = "a" * 64  # 64 hex characters
        result = self.lotus.parse_wallet_data(hex_data)
        self.assertEqual(result["type"], "secp256k1")  # Default type
        self.assertEqual(result["private_key"], hex_data)
        
        # Test auto-detection
        result = self.lotus.parse_wallet_data(json_data, format_type=None)
        self.assertEqual(result["type"], "secp256k1")
        self.assertEqual(result["private_key"], "abcd1234")
        
        # Test invalid data
        self.assertIsNone(self.lotus.parse_wallet_data("invalid data"))
    
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("os.path.getsize")
    def test_export_data_to_json(self, mock_getsize, mock_open):
        """Test exporting data to JSON."""
        # Setup
        mock_getsize.return_value = 100
        data = {"key1": "value1", "key2": 123}
        output_path = "/tmp/test.json"
        
        # Test with mocked file operations
        result = self.lotus.export_data_to_json(data, output_path)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], output_path)
        self.assertEqual(result["file_size"], 100)
        
        # Verify file operations
        mock_open.assert_called_once_with(output_path, 'w')
        mock_open().write.assert_called()  # JSON was written
        
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("os.path.getsize")
    def test_export_data_to_csv(self, mock_getsize, mock_open):
        """Test exporting data to CSV."""
        # Setup
        mock_getsize.return_value = 100
        data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25}
        ]
        output_path = "/tmp/test.csv"
        
        # Test with mocked file operations
        result = self.lotus.export_data_to_csv(data, output_path)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], output_path)
        self.assertEqual(result["file_size"], 100)
        self.assertEqual(result["row_count"], 2)
        
        # Verify file operations
        mock_open.assert_called_once_with(output_path, 'w', newline='')
        mock_open().write.assert_called()  # CSV was written
        
    @mock.patch("os.path.getsize")
    @mock.patch("json.dump")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("requests.post")
    def test_export_miner_data(self, mock_post, mock_open, mock_json_dump, mock_getsize):
        """Test exporting miner data."""
        # Setup
        self.mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "Miners": [
                    {"Addr": "t01000", "Power": "1000", "Location": "US"},
                    {"Addr": "t02000", "Power": "2000", "Location": "EU"}
                ]
            },
            "id": 1
        }
        mock_post.return_value = self.mock_response
        mock_getsize.return_value = 500
        
        # Execute method
        output_path = "/tmp/miner_data.json"
        result = self.lotus.export_miner_data(output_path)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], output_path)
        self.assertEqual(result["miner_count"], 2)
        
        # Verify file operations
        mock_open.assert_called_once_with(output_path, 'w')
        mock_json_dump.assert_called_once()
        
    @mock.patch("os.path.getsize")
    @mock.patch("json.dump")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("requests.post")
    def test_export_deals_metrics(self, mock_post, mock_open, mock_json_dump, mock_getsize):
        """Test exporting deals metrics."""
        # Setup - mock the client_list_deals response
        self.mock_response.json.return_value = MOCK_CLIENT_LIST_DEALS_RESPONSE
        mock_post.return_value = self.mock_response
        mock_getsize.return_value = 500
        
        # Execute method
        output_path = "/tmp/deals_metrics.json"
        result = self.lotus.export_deals_metrics(output_path)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], output_path)
        
        # Verify file operations
        mock_open.assert_called_once_with(output_path, 'w')
        mock_json_dump.assert_called_once()
        
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data='{"Type":"secp256k1","PrivateKey":"abcd1234","Address":"t1test"}')
    @mock.patch("requests.post")
    def test_import_wallet_data(self, mock_post, mock_open):
        """Test importing wallet data."""
        # Setup - mock the WalletImport response
        self.mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": "t1imported",
            "id": 1
        }
        mock_post.return_value = self.mock_response
        
        # Execute method
        wallet_file = "/tmp/wallet.json"
        result = self.lotus.import_wallet_data(wallet_file)
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["address"], "t1imported")
        self.assertEqual(result["wallet_type"], "secp256k1")
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["method"], "Filecoin.WalletImport")
        
    @mock.patch("requests.post")
    def test_process_chain_messages(self, mock_post):
        """Test processing chain messages."""
        # Setup - mock the chain head and tipset responses
        chain_head_response = {
            "jsonrpc": "2.0",
            "result": {
                "Height": 100,
                "Blocks": [{"Miner": "t01000"}]
            },
            "id": 1
        }
        
        tipset_response = {
            "jsonrpc": "2.0",
            "result": {
                "Height": 99,
                "Blocks": [{"Miner": "t01000"}],
                "Messages": [
                    {
                        "From": "t1sender",
                        "To": "t01000",
                        "Method": 0,
                        "Value": "1000",
                        "GasUsed": 100
                    }
                ],
                "Timestamp": 1609459200
            },
            "id": 1
        }
        
        # Set up the mock to return different responses based on the method
        def side_effect_func(url, **kwargs):
            method = kwargs.get("json", {}).get("method", "")
            if method == "Filecoin.ChainHead":
                self.mock_response.json.return_value = chain_head_response
            elif method == "Filecoin.ChainGetTipSetByHeight":
                self.mock_response.json.return_value = tipset_response
            return self.mock_response
            
        mock_post.side_effect = side_effect_func
        
        # Execute method with a temporary output file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            output_path = temp_file.name
            
        try:
            result = self.lotus.process_chain_messages(height=99, count=1, output_path=output_path)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertIn("messages_analyzed", result)
            self.assertIn("tipsets_processed", result)
            self.assertEqual(result["file_path"], output_path)
            
        finally:
            # Clean up temporary file
            if os.path.exists(output_path):
                os.unlink(output_path)
                
    def test_get_actor_type(self):
        """Test determining actor type from address."""
        test_cases = [
            ("f01000", "system"),
            ("f02000", "miner"),
            ("f03000", "multisig"),
            ("f04000", "init"),
            ("f05000", "reward"),
            ("f099000", "burnt_funds"),
            ("f0other", "builtin"),
            ("f1address", "account"),
            ("f2address", "contract"),
            ("f3address", "multisig"),
            ("other", "unknown"),
            ("", "unknown"),
            (None, "unknown")
        ]
        
        for address, expected_type in test_cases:
            result = self.lotus._get_actor_type(address)
            self.assertEqual(result, expected_type)
            
    def test_analyze_chain_data(self):
        """Test analyzing chain data for statistics."""
        # Create sample tipset data
        tipsets = [
            {
                "Height": 100,
                "Timestamp": 1609459200,
                "Blocks": [
                    {"Miner": "t02000"},
                    {"Miner": "t02001"}
                ],
                "Messages": [
                    {
                        "From": "f1sender",
                        "To": "f2recipient",
                        "Method": 0,
                        "Value": "1000",
                        "GasUsed": 100
                    },
                    {
                        "From": "f1sender",
                        "To": "f02000",
                        "Method": 1,
                        "Value": "2000",
                        "GasUsed": 200
                    }
                ]
            },
            {
                "Height": 99,
                "Timestamp": 1609459170,
                "Blocks": [
                    {"Miner": "t02000"}
                ],
                "Messages": [
                    {
                        "From": "f1other",
                        "To": "f2other",
                        "Method": 2,
                        "Value": "0",
                        "GasUsed": 150
                    }
                ]
            }
        ]
        
        # Analyze the data
        result = self.lotus.analyze_chain_data(tipsets)
        
        # Verify basic metrics
        self.assertEqual(result["blocks_analyzed"], 3)
        self.assertEqual(result["messages_analyzed"], 3)
        self.assertEqual(result["timespan"]["start_height"], 99)
        self.assertEqual(result["timespan"]["end_height"], 100)
        
        # Verify miner statistics
        self.assertIn("t02000", result["miners"])
        self.assertEqual(result["miners"]["t02000"]["blocks"], 2)
        
        # Verify message statistics
        self.assertEqual(result["message_stats"]["gas_usage"]["total"], 450)
        self.assertEqual(result["message_stats"]["gas_usage"]["min"], 100)
        self.assertEqual(result["message_stats"]["gas_usage"]["max"], 200)
        
        # Verify address activity
        self.assertEqual(result["address_activity"]["f1sender"]["sent"], 2)
        self.assertEqual(result["address_activity"]["f2recipient"]["received"], 1)
        
        # Verify value transfers
        self.assertEqual(result["value_transfers"]["total"], 3000)
        self.assertEqual(result["value_transfers"]["min"], 1000)
        self.assertEqual(result["value_transfers"]["max"], 2000)
        
        # Verify rankings
        self.assertEqual(len(result["top_miners"]), 2)
        self.assertTrue(any(m["miner"] == "t02000" for m in result["top_miners"]))
        
        # Verify most active addresses
        self.assertEqual(len(result["most_active_addresses"]), 4)  # All addresses from our test data


# Function to run the tests directly if needed
def run_tests():
    unittest.main()


if __name__ == "__main__":
    run_tests()