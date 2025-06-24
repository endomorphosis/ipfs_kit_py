#!/usr/bin/env python3
"""
Test API stability with a mock high-level API.
"""
import sys
import os
import importlib.util
from typing import Dict, Any, Optional, List, Union

# Get the absolute path to the api_stability.py file
api_stability_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ipfs_kit_py",
    "api_stability.py"
)

# Load the module directly
spec = importlib.util.spec_from_file_location("api_stability", api_stability_path)
api_stability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_stability)

# Get decorator functions from api_stability module
stable_api = api_stability.stable_api
beta_api = api_stability.beta_api
experimental_api = api_stability.experimental_api

# Mock High-Level API with our stability decorators
class MockHighLevelAPI:
    """Mock version of IPFSSimpleAPI with stability decorators."""

    @stable_api(since="0.1.0")
    def add(self, content, **kwargs) -> Dict[str, Any]:
        """Add content to IPFS."""
        return {"success": True}

    @stable_api(since="0.1.0")
    def get(self, cid, **kwargs) -> bytes:
        """Get content from IPFS."""
        return b"mock data"

    @stable_api(since="0.1.0")
    def pin(self, cid, **kwargs) -> Dict[str, Any]:
        """Pin content to IPFS."""
        return {"success": True}

    @stable_api(since="0.1.0")
    def unpin(self, cid, **kwargs) -> Dict[str, Any]:
        """Unpin content from IPFS."""
        return {"success": True}

    @stable_api(since="0.1.0")
    def list_pins(self, **kwargs) -> Dict[str, Any]:
        """List pinned content."""
        return {"success": True, "pins": {}}

    @stable_api(since="0.1.0")
    def add_json(self, data, **kwargs) -> Dict[str, Any]:
        """Add JSON data to IPFS."""
        return {"success": True}

    @beta_api(since="0.1.0")
    def get_filesystem(self, **kwargs) -> Any:
        """Get FSSpec filesystem interface."""
        return None

    @beta_api(since="0.1.0")
    def stream_media(self, path, **kwargs) -> Any:
        """Stream media content."""
        return None

    @beta_api(since="0.1.0")
    def publish(self, cid, **kwargs) -> Dict[str, Any]:
        """Publish to IPNS."""
        return {"success": True}

    @beta_api(since="0.1.0")
    def cluster_status(self, cid=None, **kwargs) -> Dict[str, Any]:
        """Get cluster status."""
        return {"success": True}

    @experimental_api(since="0.1.0")
    def ai_model_add(self, model, **kwargs) -> Dict[str, Any]:
        """Add AI model to IPFS."""
        return {"success": True}

    @experimental_api(since="0.1.0")
    def ai_model_get(self, model_id, **kwargs) -> Dict[str, Any]:
        """Get AI model from IPFS."""
        return {"success": True}

# Create an instance to register decorators
mock_api = MockHighLevelAPI()

def print_stability_summary():
    """Print a summary of API stability decorators."""
    print("\n=== API Stability Summary ===\n")

    total_apis = sum(len(apis) for apis in api_stability.API_REGISTRY.values())
    print(f"Total decorated APIs: {total_apis}")

    for stability_level, apis in api_stability.API_REGISTRY.items():
        if apis:
            print(f"\n{stability_level.upper()} APIs ({len(apis)}):")
            for func_id, metadata in sorted(apis.items()):
                print(f"  - {metadata['name']} (since {metadata['since']})")

if __name__ == "__main__":
    print_stability_summary()
