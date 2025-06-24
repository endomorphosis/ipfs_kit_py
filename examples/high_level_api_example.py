"""
High-Level API Example for IPFS Kit.

This example demonstrates the usage of the High-Level API for IPFS Kit,
including basic operations, declarative configuration, and plugin architecture.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the High-Level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI, PluginBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Example plugin
class ExamplePlugin(PluginBase):
    """Example plugin with additional functionality."""

    def hash_file(self, file_path):
        """
        Calculate hash of file without uploading to IPFS.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with file hash
        """
        import hashlib

        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            return {
                "success": True,
                "file_path": file_path,
                "hash": file_hash,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def search_content(self, query, max_results=10):
        """
        Search for content in IPFS based on metadata.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            Dictionary with search results
        """
        # In a real implementation, this would use an index or database
        # For this example, we'll just return a mock result
        return {
            "success": True,
            "query": query,
            "results": [
                {
                    "cid": f"QmExample{i}",
                    "name": f"Example {i}",
                    "size": i * 1024,
                    "score": 1.0 - (i / max_results)
                }
                for i in range(1, max_results + 1)
            ],
            "total_results": max_results
        }


def main():
    """Run the example."""
    logger.info("Starting High-Level API Example")

    # Step 1: Create a temporary configuration file
    config_path = "example_config.yaml"
    with open(config_path, 'w') as f:
        f.write("""
role: worker
resources:
  max_memory: 2GB
  max_storage: 20GB
cache:
  memory_size: 200MB
  disk_size: 2GB
  disk_path: ~/.ipfs_kit/example_cache
timeouts:
  api: 30
  gateway: 60
  peer_connect: 30
plugins:
  - name: ExamplePlugin
    path: __main__
    enabled: true
    config:
      search_index: "example_index"
""")

    try:
        # Step 2: Initialize the API with configuration file
        logger.info("Initializing API with configuration file")
        api = IPFSSimpleAPI(config_path=config_path)

        # Step 3: Basic operations
        logger.info("Performing basic operations")

        # Create test file
        test_file_path = "example_content.txt"
        with open(test_file_path, 'w') as f:
            f.write("This is an example file for IPFS Kit.")

        try:
            # Add file to IPFS
            logger.info("Adding file to IPFS")
            add_result = api.add(test_file_path)
            logger.info(f"Add result: {add_result}")

            cid = add_result["cid"]

            # Pin content
            logger.info(f"Pinning content with CID: {cid}")
            pin_result = api.pin(cid)
            logger.info(f"Pin result: {pin_result}")

            # List pins
            logger.info("Listing pins")
            pins_result = api.list_pins()
            logger.info(f"Pins: {pins_result}")

            # Get content
            logger.info(f"Getting content with CID: {cid}")
            content = api.get(cid)
            logger.info(f"Content: {content.decode('utf-8')}")

            # List peers
            logger.info("Listing peers")
            peers_result = api.peers()
            logger.info(f"Peers: {peers_result}")

            # Step 4: Use plugin
            logger.info("Using plugin")

            # Hash file using plugin
            logger.info("Hashing file using plugin")
            hash_result = api.call_extension("ExamplePlugin.hash_file", test_file_path)
            logger.info(f"Hash result: {hash_result}")

            # Search content using plugin
            logger.info("Searching content using plugin")
            search_result = api.call_extension("ExamplePlugin.search_content", "example", max_results=3)
            logger.info(f"Search result: {search_result}")

            # Alternate way to call extensions
            logger.info("Calling extension using __call__")
            search_result2 = api("ExamplePlugin.search_content", "another example", max_results=2)
            logger.info(f"Search result: {search_result2}")

            # Step 5: Generate SDK
            logger.info("Generating SDK")

            # Create output directory
            sdk_dir = "sdk_output"
            os.makedirs(sdk_dir, exist_ok=True)

            # Generate Python SDK
            python_result = api.generate_sdk("python", sdk_dir)
            logger.info(f"Python SDK generated: {python_result}")

            # Generate JavaScript SDK
            js_result = api.generate_sdk("javascript", sdk_dir)
            logger.info(f"JavaScript SDK generated: {js_result}")

            # Step 6: Save configuration
            logger.info("Saving configuration")
            save_result = api.save_config("saved_config.yaml")
            logger.info(f"Save result: {save_result}")

        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    finally:
        # Clean up configuration file
        if os.path.exists(config_path):
            os.remove(config_path)

        # Clean up saved configuration
        if os.path.exists("saved_config.yaml"):
            os.remove("saved_config.yaml")

        # Clean up SDK output
        import shutil
        if os.path.exists("sdk_output"):
            shutil.rmtree("sdk_output")

    logger.info("Example completed")


if __name__ == "__main__":
    main()
