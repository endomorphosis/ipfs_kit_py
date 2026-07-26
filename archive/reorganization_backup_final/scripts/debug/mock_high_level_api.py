"""
Mock high-level API implementation to allow testing without circular imports.
This file creates a mock version of IPFSSimpleAPI to facilitate testing.
"""

class IPFSSimpleAPI:
    """Mock implementation of IPFSSimpleAPI for testing purposes."""
    
    def __init__(self, *args, **kwargs):
        """Initialize mock simple API."""
        pass
    
    def initialize(self, *args, **kwargs):
        """Mock initialize method."""
        return {"success": True}
    
    def add(self, *args, **kwargs):
        """Mock add method."""
        return {"success": True, "cid": "QmMockCID"}
    
    def cat(self, *args, **kwargs):
        """Mock cat method."""
        return {"success": True, "content": b"Mock content"}
    
    def pin(self, *args, **kwargs):
        """Mock pin method."""
        return {"success": True}
    
    def unpin(self, *args, **kwargs):
        """Mock unpin method."""
        return {"success": True}
    
    def list_pins(self, *args, **kwargs):
        """Mock list_pins method."""
        return {"success": True, "pins": []}
    
    def shutdown(self, *args, **kwargs):
        """Mock shutdown method."""
        return {"success": True}
    
    def get_filesystem(self, *args, **kwargs):
        """Mock get_filesystem method."""
        return None