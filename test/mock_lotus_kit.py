"""
Mock Lotus Kit module for testing.

This module provides mock implementations of lotus_kit classes and functions
allowing tests to run without the actual Lotus daemon.
"""

import logging
import os
import time
from unittest.mock import MagicMock
from typing import Dict, Any, List, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)

# Constants for testing
LOTUS_KIT_AVAILABLE = True
LOTUS_AVAILABLE = True

class MockLotusKit:
    """Mock implementation of the lotus_kit class."""

    def __init__(self, metadata=None):
        """Initialize a mock lotus_kit instance."""
        self.metadata = metadata or {}
        self.mock_mode = self.metadata.get("mock_mode", True)
        self.api_url = self.metadata.get("api_url", "http://localhost:1234/rpc/v0")
        self.token = self.metadata.get("token", "")
        logger.info(f"Initialized mock lotus_kit (mock_mode={self.mock_mode})")

    def check_connection(self):
        """Check connection to Lotus daemon."""
        return {
            "success": True,
            "available": True,
            "version": "1.23.0",
            "api_url": self.api_url
        }

    def get_chain_head(self):
        """Get current chain head."""
        return {
            "success": True,
            "head": {
                "Cids": [
                    {"/":'bafy2bzacec5tfqvmzze5bm2ko4blwjb5klkjkjklj3d42i3lkj4lkj43lkjlkj'},
                    {"/":'bafy2bzacec6tfgasde5bm2ko4blwjb5klkjkjklj3d42i3lkj4lkj43lkjlkj'},
                ]
            }
        }

    def list_miners(self):
        """List available miners."""
        return {
            "success": True,
            "miners": ["t01000", "t01001", "t01002"],
            "count": 3
        }

    def miner_info(self, miner_address):
        """Get information about a miner."""
        return {
            "success": True,
            "info": {
                "Owner": "t3abcdef",
                "Worker": "t3ghijkl",
                "NewWorker": "",
                "ControlAddresses": ["t3mnopqr"],
                "PeerId": "12D3KooWABC123456789",
                "Multiaddrs": ["/ip4/1.2.3.4/tcp/12345"],
                "SectorSize": 34359738368,
                "WindowPoStPartitionSectors": 10,
                "ConsensusFaultElapsed": -1
            }
        }

    def list_wallets(self):
        """List available wallets."""
        return {
            "success": True,
            "wallets": ["t3abcdef", "t3ghijkl"],
            "count": 2
        }

    def wallet_balance(self, address):
        """Get wallet balance."""
        return {
            "success": True,
            "balance": "1000000000000000000",
            "readable_balance": "1.0 FIL"
        }

    def create_wallet(self, wallet_type=None):
        """Create a new wallet."""
        wallet_type = wallet_type or "secp256k1"
        return {
            "success": True,
            "address": "t3newwallet123",
            "type": wallet_type
        }

    def import_file(self, file_path):
        """Import a file to Lotus."""
        return {
            "success": True,
            "root": {"/": "bafy2bzacectest123456789"},
            "import_id": 123
        }

    def list_imports(self):
        """List imported content."""
        return {
            "success": True,
            "imports": [
                {
                    "Key": 0,
                    "Err": "",
                    "Root": {"/": "bafy2bzacectest123456789"},
                    "Source": "lotus import",
                    "FilePath": "/tmp/test-file",
                    "CARPath": "/tmp/test-file.car"
                }
            ],
            "count": 1
        }

    def list_deals(self):
        """List storage deals."""
        return {
            "success": True,
            "deals": [
                {
                    "DealID": 123,
                    "State": 7,
                    "Provider": "t01000",
                    "Client": "t3abcdef",
                    "PieceCID": {"/": "baga6ea4seaqtest123456789"},
                    "Size": 34359738368,
                    "PricePerEpoch": "1000",
                    "Duration": 518400,
                    "CreationTime": time.time() - 86400,
                    "Verified": False,
                    "ProviderCollateral": "0",
                    "ClientCollateral": "0",
                }
            ],
            "count": 1
        }

    def deal_info(self, deal_id):
        """Get information about a specific deal."""
        return {
            "success": True,
            "deal": {
                "DealID": deal_id,
                "State": 7,
                "Provider": "t01000",
                "Client": "t3abcdef",
                "PieceCID": {"/": "baga6ea4seaqtest123456789"},
                "Size": 34359738368,
                "PricePerEpoch": "1000",
                "Duration": 518400,
                "CreationTime": time.time() - 86400,
                "Verified": False,
                "ProviderCollateral": "0",
                "ClientCollateral": "0",
            }
        }

    def start_deal(self, piece_cid, piece_size, wallet, miner, price="0", duration=518400, verified=False, fast_retrieval=True):
        """Start a storage deal."""
        return {
            "success": True,
            "deal_cid": {"/": "bafy2bzacecrandom123456789"},
            "proposal_cid": {"/": "bafyreiarandom123456789"}
        }

    def retrieve_data(self, data_cid, output_path=None, wallet=None, miner=None):
        """Retrieve data from Filecoin."""
        if output_path:
            # Create a mock file with random content
            with open(output_path, 'wb') as f:
                f.write(b"Mock retrieved data from Filecoin")

        return {
            "success": True,
            "data_cid": data_cid,
            "output_path": output_path,
            "size": 24
        }

    def cid_to_car(self, cid, output_path):
        """Convert CID to CAR file."""
        if output_path:
            # Create a mock CAR file
            with open(output_path, 'wb') as f:
                f.write(b"Mock CAR file data")

        return {
            "success": True,
            "cid": cid,
            "car_path": output_path,
            "size": 16
        }

    def export_car(self, cid, output_path):
        """Export data as CAR file."""
        if output_path:
            # Create a mock CAR file
            with open(output_path, 'wb') as f:
                f.write(b"Mock exported CAR file data")

        return {
            "success": True,
            "cid": cid,
            "car_path": output_path,
            "size": 25
        }

    def import_car(self, car_path):
        """Import CAR file."""
        return {
            "success": True,
            "root": {"/": "bafy2bzacecimport123456789"},
            "import_id": 456
        }

# Create a global instance of the mock
lotus_kit = MockLotusKit
