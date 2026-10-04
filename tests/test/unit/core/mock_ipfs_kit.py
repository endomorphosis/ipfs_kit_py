"""
Mock IPFS Kit for testing.

This module provides a simple mock implementation of the IPFSKit class
for testing purposes.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Callable

logger = logging.getLogger(__name__)

class MockIPFSKit:
    """Mock implementation of IPFSKit for testing."""
    
    def __init__(self, role="leecher", **kwargs):
        """Initialize the mock kit."""
        self.role = role
        self.config = kwargs.get("config", {})
        self.ipfs = MockIPFS()
        self.lotus = MockLotus()
        self.storacha = MockStoracha()
        self.lassie = MockLassie()
        self.libp2p = MockLibp2p()
        self.daemons_running = {"ipfs": False, "lotus": False}
        
        # Store all kwargs for inspection in tests
        self.kwargs = kwargs
        
        logger.info(f"Initialized MockIPFSKit with role: {role}")
        
    def start_daemons(self, daemons=None):
        """Start the specified daemons."""
        if daemons is None:
            daemons = ["ipfs"]
            
        for daemon in daemons:
            self.daemons_running[daemon] = True
            
        logger.info(f"Started daemons: {daemons}")
        return True
        
    def stop_daemons(self, daemons=None):
        """Stop the specified daemons."""
        if daemons is None:
            daemons = ["ipfs"]
            
        for daemon in daemons:
            self.daemons_running[daemon] = False
            
        logger.info(f"Stopped daemons: {daemons}")
        return True
        
    def add(self, path, **kwargs):
        """Add a file to IPFS."""
        return self.ipfs.add(path, **kwargs)
        
    def get(self, cid, **kwargs):
        """Get a file from IPFS."""
        return self.ipfs.get(cid, **kwargs)
        
    def cat(self, cid, **kwargs):
        """Get the contents of a file from IPFS."""
        return self.ipfs.cat(cid, **kwargs)
        
    def connect_to_peer(self, peer_id, **kwargs):
        """Connect to a peer."""
        return self.ipfs.connect_to_peer(peer_id, **kwargs)
        
    def create_dag(self, data, **kwargs):
        """Create a DAG node."""
        return self.ipfs.create_dag(data, **kwargs)
        
    def get_dag(self, cid, **kwargs):
        """Get a DAG node."""
        return self.ipfs.get_dag(cid, **kwargs)
        
    def pin(self, cid, **kwargs):
        """Pin a CID."""
        return self.ipfs.pin(cid, **kwargs)
        
    def unpin(self, cid, **kwargs):
        """Unpin a CID."""
        return self.ipfs.unpin(cid, **kwargs)
        
    def list_pins(self, **kwargs):
        """List pinned CIDs."""
        return self.ipfs.list_pins(**kwargs)
        
    def store_with_lotus(self, cid, **kwargs):
        """Store a CID with Lotus."""
        return self.lotus.store(cid, **kwargs)
        
    def retrieve_with_lotus(self, cid, **kwargs):
        """Retrieve a CID with Lotus."""
        return self.lotus.retrieve(cid, **kwargs)
        
    def store_with_storacha(self, path, **kwargs):
        """Store a file with Storacha."""
        return self.storacha.store(path, **kwargs)
        
    def retrieve_with_storacha(self, cid, **kwargs):
        """Retrieve a file from Storacha."""
        return self.storacha.retrieve(cid, **kwargs)


class MockIPFS:
    """Mock implementation of IPFS API for testing."""
    
    def __init__(self):
        """Initialize the mock IPFS API."""
        self.files = {}
        self.pins = set()
        self.dags = {}
        self.peers = set()
        
    def add(self, path, **kwargs):
        """Add a file to IPFS."""
        cid = f"QmMock{hash(path) % 1000000:06d}"
        self.files[cid] = {"path": path, "data": f"Content of {path}"}
        return {"Hash": cid, "Name": path}
        
    def get(self, cid, **kwargs):
        """Get a file from IPFS."""
        if cid in self.files:
            return self.files[cid]
        return None
        
    def cat(self, cid, **kwargs):
        """Get the contents of a file from IPFS."""
        if cid in self.files:
            return self.files[cid]["data"].encode('utf-8')
        return None
        
    def connect_to_peer(self, peer_id, **kwargs):
        """Connect to a peer."""
        self.peers.add(peer_id)
        return {"Success": True}
        
    def create_dag(self, data, **kwargs):
        """Create a DAG node."""
        cid = f"bafy{hash(str(data)) % 1000000:06d}"
        self.dags[cid] = data
        return {"Cid": cid}
        
    def get_dag(self, cid, **kwargs):
        """Get a DAG node."""
        if cid in self.dags:
            return self.dags[cid]
        return None
        
    def pin(self, cid, **kwargs):
        """Pin a CID."""
        self.pins.add(cid)
        return {"Pins": [cid]}
        
    def unpin(self, cid, **kwargs):
        """Unpin a CID."""
        if cid in self.pins:
            self.pins.remove(cid)
        return {"Pins": [cid]}
        
    def list_pins(self, **kwargs):
        """List pinned CIDs."""
        return {"Keys": {cid: {"Type": "recursive"} for cid in self.pins}}


class MockLotus:
    """Mock implementation of Lotus API for testing."""
    
    def __init__(self):
        """Initialize the mock Lotus API."""
        self.deals = {}
        self.retrievals = {}
        
    def store(self, cid, **kwargs):
        """Store a CID with Lotus."""
        deal_id = len(self.deals) + 1
        self.deals[deal_id] = {"Cid": cid, "Status": "active"}
        return {"DealID": deal_id}
        
    def retrieve(self, cid, **kwargs):
        """Retrieve a CID with Lotus."""
        retrieval_id = len(self.retrievals) + 1
        self.retrievals[retrieval_id] = {"Cid": cid, "Status": "success"}
        return {"RetrievalID": retrieval_id}


class MockStoracha:
    """Mock implementation of Storacha API for testing."""
    
    def __init__(self):
        """Initialize the mock Storacha API."""
        self.uploads = {}
        self.downloads = {}
        
    def store(self, path, **kwargs):
        """Store a file with Storacha."""
        cid = f"QmStoracha{hash(path) % 1000000:06d}"
        self.uploads[cid] = {"path": path}
        return {"cid": cid}
        
    def retrieve(self, cid, **kwargs):
        """Retrieve a file from Storacha."""
        if cid in self.uploads:
            self.downloads[cid] = {"status": "success"}
            return {"data": f"Content of {self.uploads[cid]['path']}".encode('utf-8')}
        return None


class MockLassie:
    """Mock implementation of Lassie API for testing."""
    
    def __init__(self):
        """Initialize the mock Lassie API."""
        self.fetches = {}
        
    def fetch(self, cid, **kwargs):
        """Fetch a CID with Lassie."""
        fetch_id = len(self.fetches) + 1
        self.fetches[fetch_id] = {"Cid": cid, "Status": "success"}
        return {"FetchID": fetch_id, "Data": f"Lassie content for {cid}".encode('utf-8')}


class MockLibp2p:
    """Mock implementation of libp2p for testing."""
    
    def __init__(self):
        """Initialize the mock libp2p API."""
        self.peers = {}
        self.messages = []
        
    def connect(self, peer_id, **kwargs):
        """Connect to a peer."""
        self.peers[peer_id] = {"status": "connected"}
        return True
        
    def disconnect(self, peer_id, **kwargs):
        """Disconnect from a peer."""
        if peer_id in self.peers:
            self.peers[peer_id] = {"status": "disconnected"}
        return True
        
    def publish(self, topic, message, **kwargs):
        """Publish a message to a topic."""
        self.messages.append({"topic": topic, "message": message})
        return True
        
    def subscribe(self, topic, **kwargs):
        """Subscribe to a topic."""
        return lambda: True  # Return a dummy unsubscribe function