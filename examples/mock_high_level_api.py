"""Mock High Level API for Testing

This module provides mock implementations of the high-level API for testing.
"""

import logging
from typing import Dict, List, Optional, Any, Union, Callable
import os
import json

logger = logging.getLogger(__name__)


class MockIPFSSimpleAPI:
    """Mock implementation of the IPFS Simple API for testing."""

    def __init__(self, config=None):
        """Initialize the mock API."""
        self.config = config or {}
        self.data_store = {}  # CID -> content mapping
        self.pins = set()
        self.files = {}  # path -> content mapping
        self.ipns_records = {}  # name -> CID mapping
        logger.info("Initialized Mock IPFS Simple API")

    async def add_async(self, data, **kwargs):
        """Add content to IPFS asynchronously."""
        if isinstance(data, str):
            data = data.encode('utf-8')

        # Generate a mock CID based on data content
        import hashlib
        cid = f"Qm{hashlib.sha256(data).hexdigest()[:44]}"

        self.data_store[cid] = data
        logger.info(f"Added content to mock IPFS with CID: {cid}")
        return {"Hash": cid, "Name": kwargs.get("name", "mockfile")}

    def add(self, data, **kwargs):
        """Add content to IPFS."""
        import asyncio
        return asyncio.run(self.add_async(data, **kwargs))

    async def cat_async(self, cid, **kwargs):
        """Cat content from IPFS asynchronously."""
        if cid in self.data_store:
            return self.data_store[cid]
        logger.warning(f"CID not found in mock IPFS: {cid}")
        return b""

    def cat(self, cid, **kwargs):
        """Cat content from IPFS."""
        import asyncio
        return asyncio.run(self.cat_async(cid, **kwargs))

    async def get_async(self, cid, **kwargs):
        """Get content from IPFS asynchronously."""
        return await self.cat_async(cid, **kwargs)

    def get(self, cid, **kwargs):
        """Get content from IPFS."""
        import asyncio
        return asyncio.run(self.get_async(cid, **kwargs))

    async def pin_add_async(self, cid, **kwargs):
        """Pin content in IPFS asynchronously."""
        self.pins.add(cid)
        logger.info(f"Pinned CID in mock IPFS: {cid}")
        return {"Pins": [cid]}

    def pin_add(self, cid, **kwargs):
        """Pin content in IPFS."""
        import asyncio
        return asyncio.run(self.pin_add_async(cid, **kwargs))

    async def pin_rm_async(self, cid, **kwargs):
        """Unpin content from IPFS asynchronously."""
        if cid in self.pins:
            self.pins.remove(cid)
            logger.info(f"Unpinned CID from mock IPFS: {cid}")
            return {"Pins": [cid]}
        return {"Pins": []}

    def pin_rm(self, cid, **kwargs):
        """Unpin content from IPFS."""
        import asyncio
        return asyncio.run(self.pin_rm_async(cid, **kwargs))

    async def pin_ls_async(self, **kwargs):
        """List pinned content in IPFS asynchronously."""
        pins_dict = {pin: {"Type": "recursive"} for pin in self.pins}
        return {"Keys": pins_dict}

    def pin_ls(self, **kwargs):
        """List pinned content in IPFS."""
        import asyncio
        return asyncio.run(self.pin_ls_async(**kwargs))

    async def files_write_async(self, path, data, **kwargs):
        """Write to MFS asynchronously."""
        if isinstance(data, str):
            data = data.encode('utf-8')

        self.files[path] = data
        logger.info(f"Wrote to MFS path in mock IPFS: {path}")
        return True

    def files_write(self, path, data, **kwargs):
        """Write to MFS."""
        import asyncio
        return asyncio.run(self.files_write_async(path, data, **kwargs))

    async def files_read_async(self, path, **kwargs):
        """Read from MFS asynchronously."""
        if path in self.files:
            return self.files[path]
        logger.warning(f"MFS path not found in mock IPFS: {path}")
        return b""

    def files_read(self, path, **kwargs):
        """Read from MFS."""
        import asyncio
        return asyncio.run(self.files_read_async(path, **kwargs))

    async def files_rm_async(self, path, **kwargs):
        """Remove from MFS asynchronously."""
        if path in self.files:
            del self.files[path]
            logger.info(f"Removed MFS path from mock IPFS: {path}")
            return True
        return False

    def files_rm(self, path, **kwargs):
        """Remove from MFS."""
        import asyncio
        return asyncio.run(self.files_rm_async(path, **kwargs))

    async def files_ls_async(self, path="/", **kwargs):
        """List MFS directory asynchronously."""
        entries = []
        for filepath in self.files:
            if filepath.startswith(path) and filepath != path:
                relative = filepath[len(path):].lstrip("/")
                if "/" not in relative:
                    entries.append({"Name": relative, "Type": 0, "Size": len(self.files[filepath])})
        return {"Entries": entries}

    def files_ls(self, path="/", **kwargs):
        """List MFS directory."""
        import asyncio
        return asyncio.run(self.files_ls_async(path, **kwargs))

    async def name_publish_async(self, cid, **kwargs):
        """Publish to IPNS asynchronously."""
        name = kwargs.get("key", "self")
        self.ipns_records[name] = cid
        logger.info(f"Published to IPNS in mock IPFS: {name} -> {cid}")
        return {"Name": name, "Value": f"/ipfs/{cid}"}

    def name_publish(self, cid, **kwargs):
        """Publish to IPNS."""
        import asyncio
        return asyncio.run(self.name_publish_async(cid, **kwargs))

    async def name_resolve_async(self, name, **kwargs):
        """Resolve from IPNS asynchronously."""
        if name in self.ipns_records:
            cid = self.ipns_records[name]
            return {"Path": f"/ipfs/{cid}"}
        logger.warning(f"IPNS name not found in mock IPFS: {name}")
        return {"Path": ""}

    def name_resolve(self, name, **kwargs):
        """Resolve from IPNS."""
        import asyncio
        return asyncio.run(self.name_resolve_async(name, **kwargs))

    async def ls_async(self, cid, **kwargs):
        """List object content asynchronously."""
        return {"Objects": [{"Hash": cid, "Links": []}]}

    def ls(self, cid, **kwargs):
        """List object content."""
        import asyncio
        return asyncio.run(self.ls_async(cid, **kwargs))

    def create_wallet(self, **kwargs):
        """Create a mock wallet."""
        return {"address": "mock_wallet_address", "private_key": "mock_private_key"}

    def get_balance(self, address=None, **kwargs):
        """Get mock wallet balance."""
        return {"balance": 1000.0, "address": address or "mock_wallet_address"}

    def get_filesystem(self, **kwargs):
        """Get a mock filesystem interface."""
        class MockFileSystem:
            protocol = "ipfs"
            role = "mock"

            def ls(self, path):
                return [{"name": "mock_file", "size": 1024, "type": "file"}]

            def get(self, path):
                return b"Mock file content"

            def put(self, data, path):
                return {"path": path, "status": "success"}

        return MockFileSystem()


class IPFSKit:
    """Mock implementation of IPFSKit for testing."""

    def __init__(self, role="leecher", **kwargs):
        """Initialize the mock IPFSKit."""
        self.role = role
        self.options = kwargs
        self.ipfs = MockIPFSSimpleAPI()
        self.filecoin = self._create_mock_filecoin()
        self.storj = self._create_mock_storj()
        self.config = {
            "role": role,
            "ipfs": {"api_port": 5001, "gateway_port": 8080},
            "filecoin": {"enable": True},
            "storj": {"enable": False}
        }
        logger.info(f"Initialized Mock IPFSKit with role: {role}")

    def _create_mock_filecoin(self):
        """Create a mock Filecoin interface."""
        class MockFilecoin:
            def create_deal(self, cid, **kwargs):
                return {"deal_id": "mock_deal_id", "cid": cid, "status": "active"}

            def list_deals(self, **kwargs):
                return [{"deal_id": "mock_deal_id", "status": "active"}]

            def get_deal_status(self, deal_id):
                return {"deal_id": deal_id, "status": "active"}

            async def create_deal_async(self, cid, **kwargs):
                return {"deal_id": "mock_deal_id", "cid": cid, "status": "active"}

            async def list_deals_async(self, **kwargs):
                return [{"deal_id": "mock_deal_id", "status": "active"}]

            async def get_deal_status_async(self, deal_id):
                return {"deal_id": deal_id, "status": "active"}

        return MockFilecoin()

    def _create_mock_storj(self):
        """Create a mock Storj interface."""
        class MockStorj:
            def upload(self, data, **kwargs):
                return {"id": "mock_storj_id", "status": "success"}

            def download(self, file_id, **kwargs):
                return b"Mock Storj content"

            def list_files(self, **kwargs):
                return [{"id": "mock_storj_id", "name": "mock_file", "size": 1024}]

            async def upload_async(self, data, **kwargs):
                return {"id": "mock_storj_id", "status": "success"}

            async def download_async(self, file_id, **kwargs):
                return b"Mock Storj content"

            async def list_files_async(self, **kwargs):
                return [{"id": "mock_storj_id", "name": "mock_file", "size": 1024}]

        return MockStorj()

    def get_config(self):
        """Get the configuration."""
        return self.config

    def save_config(self):
        """Save the configuration."""
        config_path = os.path.expanduser("~/.ipfs_kit/config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(self.config, f)
        return True

    def start_daemons(self):
        """Start mock daemons."""
        logger.info("Started mock IPFS daemons")
        return True

    def stop_daemons(self):
        """Stop mock daemons."""
        logger.info("Stopped mock IPFS daemons")
        return True

    def get_daemon_status(self):
        """Get mock daemon status."""
        return {
            "ipfs": {"running": True, "pid": 12345},
            "filecoin": {"running": True, "pid": 12346},
            "storj": {"running": False, "pid": None}
        }


# Create instances for direct import
ipfs_kit = IPFSKit
ipfs_simple_api = MockIPFSSimpleAPI
