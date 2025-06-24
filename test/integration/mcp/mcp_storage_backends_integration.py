#!/usr/bin/env python3
"""
MCP Storage Backends Integration Example

This script demonstrates how the storage backends are integrated into the MCP
(Model-Controller-Persistence) server architecture, showing how each backend
is initialized, configured, and exposed through API endpoints.
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, Any, Optional, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_storage_backends")

def load_stored_credentials(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load stored credentials from config file."""
    if config_path is None:
        config_path = os.path.expanduser("~/.ipfs_kit/config.json")

    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                return config.get("credentials", {})
        return {}
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return {}

class StorageBackendModel:
    """Base class for storage backend models in MCP architecture."""

    def __init__(self, backend_name: str, credentials: Dict[str, Any] = None):
        self.backend_name = backend_name
        self.credentials = credentials or {}
        self.initialized = False
        self.operation_stats = {
            "uploads": 0,
            "downloads": 0,
            "errors": 0,
            "last_operation": None
        }
        self.backend_client = None

    def initialize(self) -> Dict[str, Any]:
        """Initialize the backend client."""
        logger.info(f"Initializing {self.backend_name} backend")
        self.initialized = True
        return {"success": True, "backend": self.backend_name, "status": "initialized"}

    def upload_content(self, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to the storage backend."""
        if not self.initialized:
            return {"success": False, "error": "Backend not initialized"}

        logger.info(f"[MOCK] Uploading content to {self.backend_name}")
        self.operation_stats["uploads"] += 1
        self.operation_stats["last_operation"] = time.time()

        return {
            "success": True,
            "backend": self.backend_name,
            "resource_id": f"mock.{self.backend_name}.1234567890abcdef",
            "size": len(content)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get backend operation statistics."""
        return {
            "backend": self.backend_name,
            "initialized": self.initialized,
            "stats": self.operation_stats
        }


class IPFSModel(StorageBackendModel):
    """IPFS backend model implementation."""

    def __init__(self, credentials: Dict[str, Any] = None):
        super().__init__("ipfs", credentials)

    def initialize(self) -> Dict[str, Any]:
        """Initialize the IPFS client."""
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            self.backend_client = ipfs_kit()
            logger.info("IPFS client initialized successfully")
            self.initialized = True
            return {"success": True, "backend": self.backend_name, "status": "initialized"}
        except Exception as e:
            logger.error(f"Failed to initialize IPFS client: {e}")
            return {"success": False, "backend": self.backend_name, "error": str(e)}

    def upload_content(self, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to IPFS."""
        if not self.initialized:
            return {"success": False, "error": "IPFS backend not initialized"}

        try:
            result = self.backend_client.ipfs_add(content)
            self.operation_stats["uploads"] += 1
            self.operation_stats["last_operation"] = time.time()

            return {
                "success": True,
                "backend": "ipfs",
                "resource_id": result.get("Hash"),
                "size": result.get("Size", len(content))
            }
        except Exception as e:
            logger.error(f"IPFS upload error: {e}")
            self.operation_stats["errors"] += 1
            return {"success": False, "error": str(e)}


class StorachaModel(StorageBackendModel):
    """Storacha/Web3.Storage backend model implementation."""

    def __init__(self, credentials: Dict[str, Any] = None):
        super().__init__("storacha", credentials)
        self.token = credentials.get("storacha", {}).get("token") if credentials else None

    def initialize(self) -> Dict[str, Any]:
        """Initialize the Storacha client."""
        try:
            from ipfs_kit_py.storacha_kit import StorachaKit
            # If token available, use real implementation
            if self.token:
                self.backend_client = StorachaKit(token=self.token)
                self.initialized = True
                logger.info("Storacha client initialized with token")
                return {"success": True, "backend": self.backend_name, "status": "initialized", "mode": "real"}
            else:
                # Use mock implementation
                self.backend_client = "MOCK_STORACHA_CLIENT"
                self.initialized = True
                logger.info("Storacha client initialized in mock mode")
                return {"success": True, "backend": self.backend_name, "status": "initialized", "mode": "mock"}
        except Exception as e:
            logger.error(f"Failed to initialize Storacha client: {e}")
            return {"success": False, "backend": self.backend_name, "error": str(e)}

    def upload_content(self, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to Storacha/Web3.Storage."""
        if not self.initialized:
            return {"success": False, "error": "Storacha backend not initialized"}

        try:
            # If using real implementation
            if self.token and isinstance(self.backend_client, object) and not isinstance(self.backend_client, str):
                # Use actual implementation
                result = self.backend_client.upload_content(content, filename=filename or "file.bin")
                self.operation_stats["uploads"] += 1
                self.operation_stats["last_operation"] = time.time()

                return {
                    "success": True,
                    "backend": "storacha",
                    "resource_id": result.get("cid"),
                    "size": len(content)
                }
            else:
                # Mock implementation
                logger.info("[MOCK] Uploading content to Storacha")
                self.operation_stats["uploads"] += 1
                self.operation_stats["last_operation"] = time.time()

                return {
                    "success": True,
                    "backend": "storacha",
                    "resource_id": "mockweb3.mockpin.1234567890abcdef",
                    "size": len(content)
                }
        except Exception as e:
            logger.error(f"Storacha upload error: {e}")
            self.operation_stats["errors"] += 1
            return {"success": False, "error": str(e)}


class S3Model(StorageBackendModel):
    """S3 backend model implementation."""

    def __init__(self, credentials: Dict[str, Any] = None):
        super().__init__("s3", credentials)
        s3_creds = credentials.get("s3", {}) if credentials else {}
        self.access_key = s3_creds.get("access_key")
        self.secret_key = s3_creds.get("secret_key")
        self.server = s3_creds.get("server")
        self.test_bucket = s3_creds.get("test_bucket", "ipfs-kit-test")

    def initialize(self) -> Dict[str, Any]:
        """Initialize the S3 client."""
        if not (self.access_key and self.secret_key):
            logger.warning("S3 credentials not found, initializing in mock mode")
            self.backend_client = "MOCK_S3_CLIENT"
            self.initialized = True
            return {"success": True, "backend": self.backend_name, "status": "initialized", "mode": "mock"}

        try:
            import boto3
            from botocore.client import Config

            # Set up endpoint URL if server is specified
            endpoint_url = f"https://{self.server}" if self.server else None

            # Create S3 client
            self.backend_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                endpoint_url=endpoint_url,
                config=Config(signature_version='s3v4')
            )

            # Test connection
            self.backend_client.list_buckets()

            self.initialized = True
            logger.info(f"S3 client initialized successfully with endpoint {endpoint_url}")
            return {
                "success": True,
                "backend": self.backend_name,
                "status": "initialized",
                "endpoint": endpoint_url
            }
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            return {"success": False, "backend": self.backend_name, "error": str(e)}

    def upload_content(self, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to S3."""
        if not self.initialized:
            return {"success": False, "error": "S3 backend not initialized"}

        if isinstance(self.backend_client, str) and self.backend_client == "MOCK_S3_CLIENT":
            # Mock implementation
            logger.info("[MOCK] Uploading content to S3")
            self.operation_stats["uploads"] += 1
            self.operation_stats["last_operation"] = time.time()

            return {
                "success": True,
                "backend": "s3",
                "resource_id": f"s3://{self.test_bucket}/mock-key-1234567890abcdef",
                "size": len(content)
            }

        try:
            # Generate key for S3 object
            key = filename or f"upload_{int(time.time())}.bin"

            # Upload to S3
            self.backend_client.put_object(
                Bucket=self.test_bucket,
                Key=key,
                Body=content
            )

            self.operation_stats["uploads"] += 1
            self.operation_stats["last_operation"] = time.time()

            return {
                "success": True,
                "backend": "s3",
                "resource_id": f"s3://{self.test_bucket}/{key}",
                "bucket": self.test_bucket,
                "key": key,
                "size": len(content)
            }
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            self.operation_stats["errors"] += 1
            return {"success": False, "error": str(e)}


class HuggingFaceModel(StorageBackendModel):
    """HuggingFace backend model implementation."""

    def __init__(self, credentials: Dict[str, Any] = None):
        super().__init__("huggingface", credentials)
        hf_creds = credentials.get("huggingface", {}) if credentials else {}
        self.token = hf_creds.get("token")
        self.test_repo = hf_creds.get("test_repo", "ipfs-kit-test")

    def initialize(self) -> Dict[str, Any]:
        """Initialize the HuggingFace client."""
        if not self.token:
            logger.warning("HuggingFace token not found, initializing in mock mode")
            self.backend_client = "MOCK_HF_CLIENT"
            self.initialized = True
            return {"success": True, "backend": self.backend_name, "status": "initialized", "mode": "mock"}

        try:
            # Set environment variable for HuggingFace token
            os.environ["HUGGINGFACE_TOKEN"] = self.token

            from ipfs_kit_py.huggingface_kit import HuggingFaceKit
            self.backend_client = HuggingFaceKit(token=self.token)

            # Verify authentication
            user_info = self.backend_client.whoami()

            self.initialized = True
            logger.info(f"HuggingFace client initialized successfully as {user_info.get('name')}")
            return {
                "success": True,
                "backend": self.backend_name,
                "status": "initialized",
                "user": user_info.get("name")
            }
        except Exception as e:
            logger.error(f"Failed to initialize HuggingFace client: {e}")
            return {"success": False, "backend": self.backend_name, "error": str(e)}

    def upload_content(self, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to HuggingFace Hub."""
        if not self.initialized:
            return {"success": False, "error": "HuggingFace backend not initialized"}

        if isinstance(self.backend_client, str) and self.backend_client == "MOCK_HF_CLIENT":
            # Mock implementation
            logger.info("[MOCK] Uploading content to HuggingFace")
            self.operation_stats["uploads"] += 1
            self.operation_stats["last_operation"] = time.time()

            return {
                "success": True,
                "backend": "huggingface",
                "resource_id": f"{self.test_repo}/mock-file-1234567890.bin",
                "size": len(content)
            }

        try:
            # Generate filename if not provided
            path = filename or f"upload_{int(time.time())}.bin"

            # Ensure repository exists
            try:
                self.backend_client.create_repo(self.test_repo)
                logger.info(f"Created repository {self.test_repo}")
            except Exception as e:
                # Repository might already exist, which is fine
                logger.info(f"Repository may already exist: {e}")

            # Upload file
            result = self.backend_client.upload_file(
                path_or_fileobj=content,
                path_in_repo=path,
                repo_id=self.test_repo
            )

            self.operation_stats["uploads"] += 1
            self.operation_stats["last_operation"] = time.time()

            return {
                "success": True,
                "backend": "huggingface",
                "resource_id": f"{self.test_repo}/{path}",
                "repo": self.test_repo,
                "path": path,
                "size": len(content),
                "url": result.get("url")
            }
        except Exception as e:
            logger.error(f"HuggingFace upload error: {e}")
            self.operation_stats["errors"] += 1
            return {"success": False, "error": str(e)}


class StorageBackendController:
    """Controller for storage backend operations in MCP architecture."""

    def __init__(self, models: Dict[str, StorageBackendModel]):
        self.models = models

    def list_backends(self) -> Dict[str, Any]:
        """List all available storage backends."""
        backends = {}
        for name, model in self.models.items():
            backends[name] = {
                "initialized": model.initialized,
                "stats": model.operation_stats
            }
        return {"success": True, "backends": backends}

    def upload_to_backend(self, backend_name: str, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to a specific backend."""
        if backend_name not in self.models:
            return {"success": False, "error": f"Backend {backend_name} not found"}

        model = self.models[backend_name]
        return model.upload_content(content, filename)

    def upload_to_all(self, content: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload content to all available backends."""
        results = {}
        for name, model in self.models.items():
            results[name] = model.upload_content(content, filename)
        return {"success": True, "results": results}

    def get_backend_stats(self, backend_name: str) -> Dict[str, Any]:
        """Get statistics for a specific backend."""
        if backend_name not in self.models:
            return {"success": False, "error": f"Backend {backend_name} not found"}

        model = self.models[backend_name]
        return model.get_stats()

    def initialize_all(self) -> Dict[str, Any]:
        """Initialize all storage backends."""
        results = {}
        for name, model in self.models.items():
            results[name] = model.initialize()
        return {"success": True, "initialization_results": results}


class MCPServer:
    """MCP Server with storage backends integration."""

    def __init__(self, credentials: Dict[str, Any] = None):
        # Initialize models
        self.models = {
            "ipfs": IPFSModel(credentials),
            "storacha": StorachaModel(credentials),
            "s3": S3Model(credentials),
            "huggingface": HuggingFaceModel(credentials)
        }

        # Initialize controllers
        self.controllers = {
            "storage": StorageBackendController(self.models)
        }

        logger.info("MCP Server initialized with storage backends")

    def start(self) -> Dict[str, Any]:
        """Start the MCP server and initialize all components."""
        # Initialize all storage backends
        init_results = self.controllers["storage"].initialize_all()
        logger.info("All storage backends initialized")

        return {
            "success": True,
            "status": "started",
            "initialization_results": init_results
        }

    def upload_test_file(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Upload a test file to verify storage backends."""
        # Create a 1MB test file
        content = os.urandom(1024 * 1024)  # 1MB of random data
        filename = f"test_file_{int(time.time())}.bin"

        if backend_name:
            # Upload to specific backend
            return self.controllers["storage"].upload_to_backend(backend_name, content, filename)
        else:
            # Upload to all backends
            return self.controllers["storage"].upload_to_all(content, filename)


def main():
    """Main function to demonstrate MCP server with storage backends."""
    parser = argparse.ArgumentParser(description="MCP Storage Backends Integration Example")
    parser.add_argument("--backend", help="Specific backend to test (ipfs, storacha, s3, huggingface)")
    parser.add_argument("--config", help="Path to configuration file with credentials")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    print("=== MCP Storage Backends Integration ===")

    # Load credentials
    credentials = load_stored_credentials(args.config)

    # Initialize MCP server
    server = MCPServer(credentials)
    start_result = server.start()

    # Print initialization results
    print("\nBackend Initialization Results:")
    for backend, result in start_result["initialization_results"]["initialization_results"].items():
        status = "✅ Initialized" if result["success"] else "❌ Failed"
        mode = result.get("mode", "standard")
        print(f"{backend.upper()}: {status} (Mode: {mode})")

    # Upload test file
    if args.backend:
        print(f"\nUploading test file to {args.backend.upper()}...")
        result = server.upload_test_file(args.backend)
        if isinstance(result, dict) and result.get("success"):
            print(f"✅ Upload successful!")
            print(f"Resource ID: {result.get('resource_id')}")
        else:
            print(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
    else:
        print("\nUploading test file to all backends...")
        results = server.upload_test_file()

        print("\nUpload Results:")
        for backend, result in results["results"].items():
            status = "✅ Success" if result.get("success") else "❌ Failed"
            resource = result.get("resource_id", "N/A")
            error = result.get("error", "")

            print(f"{backend.upper()}: {status}")
            if result.get("success"):
                print(f"  Resource ID: {resource}")
            else:
                print(f"  Error: {error}")

    # Print storage backend stats
    print("\nStorage Backend Statistics:")
    for backend, model in server.models.items():
        stats = model.get_stats()
        print(f"{backend.upper()}:")
        print(f"  Initialized: {stats['initialized']}")
        print(f"  Uploads: {stats['stats']['uploads']}")
        print(f"  Errors: {stats['stats']['errors']}")

    print("\nMCP Server with storage backends integration successfully demonstrated!")


if __name__ == "__main__":
    main()
