#!/usr/bin/env python3
"""
Comprehensive test script for MCP server storage backends.
Tests each backend's integration with the MCP server by:
1. Checking backend status endpoint
2. Uploading content to IPFS
3. Transferring content from IPFS to each backend
4. Transferring content back from each backend to IPFS
"""

import os
import json
import time
import sys
import uuid
import tempfile
import requests
import logging
import argparse
from typing import Dict, Any, List, Optional
import concurrent.futures

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
TEST_FILE = "/tmp/mcp_test_1mb.bin"
DEFAULT_SERVER_URL = "http://localhost:8000"  # Default MCP server URL

class MCPServerClient:
    """Client for interacting with the MCP server API."""

    def __init__(self, server_url=DEFAULT_SERVER_URL):
        """Initialize the MCP server client."""
        self.server_url = server_url
        logger.info(f"MCP Server client initialized with URL: {server_url}")

    def check_server_health(self) -> Dict[str, Any]:
        """Check if the MCP server is running and healthy."""
        try:
            response = requests.get(f"{self.server_url}/mcp/health")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return {"success": False, "error": str(e)}

    def upload_to_ipfs(self, file_path: str) -> Dict[str, Any]:
        """Upload a file to IPFS through the MCP server."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{self.server_url}/mcp/ipfs/add",
                    files=files
                )
                response.raise_for_status()
                return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to upload to IPFS: {e}")
            return {"success": False, "error": str(e)}

    def check_backend_status(self, backend: str) -> Dict[str, Any]:
        """Check the status of a storage backend."""
        try:
            response = requests.get(f"{self.server_url}/mcp/storage/{backend}/status")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to check {backend} status: {e}")
            return {"success": False, "error": str(e)}

    def transfer_ipfs_to_backend(self, backend: str, cid: str, **kwargs) -> Dict[str, Any]:
        """Transfer content from IPFS to a specific backend."""
        try:
            data = {"cid": cid, **kwargs}

            # Special handling for each backend
            endpoint = f"{self.server_url}/mcp/storage/{backend}/from_ipfs"

            # S3 backend specific parameters
            if backend == "s3":
                if "bucket" not in kwargs:
                    return {"success": False, "error": "bucket parameter required for S3"}
                data["key"] = kwargs.get("key", cid)

            # Storacha backend specific parameters
            elif backend == "storacha":
                # No additional parameters needed
                pass

            # HuggingFace backend specific parameters
            elif backend == "huggingface":
                if "repo_id" not in kwargs:
                    return {"success": False, "error": "repo_id parameter required for HuggingFace"}
                data["repo_id"] = kwargs["repo_id"]
                data["path_in_repo"] = kwargs.get("path_in_repo", f"ipfs/{cid}")

            # Filecoin backend specific parameters
            elif backend == "filecoin":
                # No additional parameters needed for demo mode
                pass

            # Lassie doesn't support from_ipfs (it's a retrieval service)
            elif backend == "lassie":
                return {"success": False, "error": "Lassie is a retrieval service, from_ipfs not supported"}

            # Make the request
            response = requests.post(endpoint, json=data)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to transfer from IPFS to {backend}: {e}")
            return {"success": False, "error": str(e)}

    def transfer_backend_to_ipfs(self, backend: str, **kwargs) -> Dict[str, Any]:
        """Transfer content from a specific backend to IPFS."""
        try:
            data = kwargs

            # Special handling for each backend
            endpoint = f"{self.server_url}/mcp/storage/{backend}/to_ipfs"

            # S3 backend specific parameters
            if backend == "s3":
                if "bucket" not in kwargs or "key" not in kwargs:
                    return {"success": False, "error": "bucket and key parameters required for S3"}

            # Storacha backend specific parameters
            elif backend == "storacha":
                if "car_cid" not in kwargs:
                    return {"success": False, "error": "car_cid parameter required for Storacha"}

            # HuggingFace backend specific parameters
            elif backend == "huggingface":
                if "repo_id" not in kwargs or "path_in_repo" not in kwargs:
                    return {"success": False, "error": "repo_id and path_in_repo parameters required for HuggingFace"}

            # Filecoin backend specific parameters
            elif backend == "filecoin":
                if "deal_id" not in kwargs:
                    return {"success": False, "error": "deal_id parameter required for Filecoin"}

            # Lassie specific parameters
            elif backend == "lassie":
                if "cid" not in kwargs:
                    return {"success": False, "error": "cid parameter required for Lassie"}

            # Make the request
            response = requests.post(endpoint, json=data)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to transfer from {backend} to IPFS: {e}")
            return {"success": False, "error": str(e)}


def create_test_file(size_mb=1):
    """Create a test file with random data."""
    if not os.path.exists(TEST_FILE):
        logger.info(f"Creating test file: {TEST_FILE} ({size_mb}MB)")
        os.system(f"dd if=/dev/urandom of={TEST_FILE} bs=1M count={size_mb}")

    logger.info(f"Test file size: {os.path.getsize(TEST_FILE)} bytes")
    return TEST_FILE


def test_backend(client: MCPServerClient, backend: str, ipfs_cid: str, backend_params: Dict[str, Any]) -> Dict[str, Any]:
    """Test a specific storage backend."""
    result = {
        "backend": backend,
        "status_check": {"success": False},
        "ipfs_to_backend": {"success": False},
        "backend_to_ipfs": {"success": False},
        "overall": False
    }

    # Step 1: Check backend status
    logger.info(f"Testing {backend} backend status...")
    status_result = client.check_backend_status(backend)
    result["status_check"] = status_result

    if not status_result.get("success", False):
        logger.error(f"❌ {backend} backend status check failed, skipping further tests")
        return result

    logger.info(f"✅ {backend} backend status check successful")

    # Skip further tests for Lassie (it's a retrieval service, not storage)
    if backend == "lassie":
        # For Lassie, we'll only test retrieval from a known CID to IPFS
        logger.info(f"Testing Lassie retrieval of public CID...")

        # Use a well-known public CID for testing
        test_cid = "QmQPeNsJPyVWPFDVHb77w8G42Fvo15z4bG2X8D2GhfbSXc"

        lassie_to_ipfs = client.transfer_backend_to_ipfs(backend, cid=test_cid)
        result["backend_to_ipfs"] = lassie_to_ipfs

        if lassie_to_ipfs.get("success", False):
            logger.info(f"✅ Lassie retrieval successful")
            result["overall"] = True
        else:
            logger.error(f"❌ Lassie retrieval failed")

        return result

    # Step 2: Transfer from IPFS to backend
    logger.info(f"Testing transfer from IPFS to {backend}...")
    ipfs_to_backend = client.transfer_ipfs_to_backend(backend, ipfs_cid, **backend_params)
    result["ipfs_to_backend"] = ipfs_to_backend

    if not ipfs_to_backend.get("success", False):
        logger.error(f"❌ Transfer from IPFS to {backend} failed, skipping backend_to_ipfs test")
        return result

    logger.info(f"✅ Transfer from IPFS to {backend} successful")

    # Step 3: Transfer from backend to IPFS
    logger.info(f"Testing transfer from {backend} to IPFS...")

    # Prepare parameters for backend_to_ipfs based on ipfs_to_backend response
    to_ipfs_params = {}

    if backend == "s3":
        to_ipfs_params = {
            "bucket": backend_params["bucket"],
            "key": ipfs_to_backend.get("key", backend_params.get("key", ipfs_cid))
        }
    elif backend == "storacha":
        to_ipfs_params = {
            "car_cid": ipfs_to_backend.get("car_cid")
        }
    elif backend == "huggingface":
        to_ipfs_params = {
            "repo_id": backend_params["repo_id"],
            "path_in_repo": backend_params.get("path_in_repo", f"ipfs/{ipfs_cid}")
        }
    elif backend == "filecoin":
        # For mock mode, use deal_id from the response
        to_ipfs_params = {
            "deal_id": ipfs_to_backend.get("deal_id", "mock-deal-id")
        }

    backend_to_ipfs = client.transfer_backend_to_ipfs(backend, **to_ipfs_params)
    result["backend_to_ipfs"] = backend_to_ipfs

    if not backend_to_ipfs.get("success", False):
        logger.error(f"❌ Transfer from {backend} to IPFS failed")
        return result

    logger.info(f"✅ Transfer from {backend} to IPFS successful")

    # Overall success if all steps succeeded
    result["overall"] = True
    return result


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test MCP server storage backends")
    parser.add_argument("--url", default=DEFAULT_SERVER_URL, help="MCP server URL")
    parser.add_argument("--size", type=int, default=1, help="Size of test file in MB")
    parser.add_argument("--backends", nargs="+", help="Specific backends to test (omit for all)")
    parser.add_argument("--s3-bucket", help="S3 bucket for testing")
    parser.add_argument("--hf-repo", help="HuggingFace repository for testing")
    parser.add_argument("--output", help="JSON file to save results to")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds for operations")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    # Create test file
    test_file = create_test_file(args.size)

    # Initialize MCP server client
    client = MCPServerClient(args.url)

    # Check server health
    health = client.check_server_health()
    if not health.get("success", False):
        logger.error(f"MCP server health check failed: {health.get('error', 'Unknown error')}")
        sys.exit(1)

    logger.info(f"MCP server health check successful: {health}")

    # Upload to IPFS
    logger.info("Uploading test file to IPFS...")
    ipfs_result = client.upload_to_ipfs(test_file)

    if not ipfs_result.get("success", False):
        logger.error(f"Failed to upload to IPFS: {ipfs_result.get('error', 'Unknown error')}")
        sys.exit(1)

    ipfs_cid = ipfs_result.get("cid")
    logger.info(f"File uploaded to IPFS: {ipfs_cid}")

    # Define backends to test
    all_backends = ["s3", "storacha", "huggingface", "filecoin", "lassie"]
    backends_to_test = args.backends if args.backends else all_backends

    # Prepare backend parameters
    backend_params = {
        "s3": {"bucket": args.s3_bucket or os.environ.get("S3_TEST_BUCKET", "ipfs-test-bucket")},
        "storacha": {},
        "huggingface": {"repo_id": args.hf_repo or os.environ.get("HF_TEST_REPO", "test-repo")},
        "filecoin": {},
        "lassie": {}
    }

    # Prepare results data
    test_results = {
        "test_info": {
            "timestamp": time.time(),
            "server_url": args.url,
            "file_size_mb": args.size,
            "ipfs_cid": ipfs_cid,
            "test_file": test_file
        },
        "backend_results": {},
        "summary": {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0
        }
    }

    # Test each backend
    for backend in backends_to_test:
        logger.info(f"\n=== Testing {backend.upper()} backend ===")

        # Check if required parameters are available
        if backend == "s3" and not backend_params["s3"]["bucket"]:
            logger.warning(f"⚠️  S3 bucket not provided, skipping S3 tests")
            skip_result = {
                "backend": backend,
                "overall": False,
                "error": "Missing S3 bucket",
                "status": "skipped"
            }
            test_results["backend_results"][backend] = skip_result
            test_results["summary"]["skipped"] += 1
            continue

        if backend == "huggingface" and not backend_params["huggingface"]["repo_id"]:
            logger.warning(f"⚠️  HuggingFace repo not provided, skipping HuggingFace tests")
            skip_result = {
                "backend": backend,
                "overall": False,
                "error": "Missing HuggingFace repo",
                "status": "skipped"
            }
            test_results["backend_results"][backend] = skip_result
            test_results["summary"]["skipped"] += 1
            continue

        # Test the backend
        result = test_backend(client, backend, ipfs_cid, backend_params[backend])
        test_results["backend_results"][backend] = result
        test_results["summary"]["total"] += 1

        if result.get("overall", False):
            test_results["summary"]["successful"] += 1
        else:
            test_results["summary"]["failed"] += 1

    # Print summary
    logger.info("\n=== Test Summary ===")
    successful_backends = []
    failed_backends = []
    skipped_backends = []

    for backend, result in test_results["backend_results"].items():
        if result.get("status") == "skipped":
            status = "⚠️ Skipped"
            skipped_backends.append(backend)
        elif result.get("overall", False):
            status = "✅ Success"
            successful_backends.append(backend)
        else:
            status = "❌ Failed"
            failed_backends.append(backend)

        logger.info(f"{backend.upper()}: {status}")

    logger.info(f"\nSuccessful backends: {len(successful_backends)}/{test_results['summary']['total']}")
    logger.info(f"Failed backends: {len(failed_backends)}/{test_results['summary']['total']}")

    if skipped_backends:
        logger.info(f"Skipped backends: {len(skipped_backends)}")

    # Save results to JSON file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(test_results, f, indent=2)
            logger.info(f"Test results saved to {args.output}")
        except Exception as e:
            logger.error(f"Failed to save results to {args.output}: {e}")

    # Exit with non-zero code if any backend failed
    if failed_backends:
        sys.exit(1)


if __name__ == "__main__":
    main()
