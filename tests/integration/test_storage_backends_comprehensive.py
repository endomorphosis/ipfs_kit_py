#!/usr/bin/env python3
"""
Comprehensive test script for all storage backends.

This script tests all storage backends with real implementations:
- Hugging Face
- Storacha
- Filecoin
- Lassie
- S3

It performs complete round-trip tests where possible:
1. Upload content to IPFS
2. Transfer to each storage backend
3. Retrieve back from each backend
4. Verify content integrity
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
import requests
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class StorageBackendTester:
    """Comprehensive tester for storage backends."""
    
    def __init__(self, mcp_url="http://localhost:9993", api_prefix="/api/v0"):
        """Initialize the tester."""
        self.mcp_url = mcp_url
        self.api_prefix = api_prefix
        self.base_url = f"{mcp_url}{api_prefix}"
        
        # Available backends
        self.backends = [
            "huggingface",
            "storacha",
            "filecoin",
            "lassie",
            "s3"
        ]
        
        # Results storage
        self.results = {
            "timestamp": time.time(),
            "test_configuration": {
                "mcp_url": mcp_url,
                "api_prefix": api_prefix,
                "backends_tested": self.backends
            },
            "server_info": {},
            "backend_status": {},
            "ipfs_upload": {},
            "backend_transfers": {},
            "backend_retrievals": {},
            "content_verification": {}
        }
    
    def verify_mcp_server(self):
        """Verify MCP server is running and get server info."""
        logger.info(f"Verifying MCP server at {self.mcp_url}...")
        
        try:
            response = requests.get(self.mcp_url)
            if response.status_code == 200:
                self.results["server_info"] = response.json()
                logger.info("MCP server is running")
                return True
            else:
                logger.error(f"MCP server returned status code {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            return False
    
    def check_backend_status(self):
        """Check status of all storage backends."""
        logger.info("Checking status of all storage backends...")
        
        for backend in self.backends:
            try:
                response = requests.get(f"{self.base_url}/{backend}/status")
                if response.status_code == 200:
                    status = response.json()
                    self.results["backend_status"][backend] = status
                    logger.info(f"{backend}: {'✅ Available' if status.get('success', False) else '❌ Not available'}")
                else:
                    self.results["backend_status"][backend] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "response_text": response.text
                    }
                    logger.warning(f"{backend}: ❌ Error - HTTP {response.status_code}")
            except Exception as e:
                self.results["backend_status"][backend] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                logger.error(f"{backend}: ❌ Error - {e}")
    
    def create_test_content(self, size_kb=100):
        """Create test content for uploading."""
        logger.info(f"Creating {size_kb}KB test content...")
        
        # Create a temporary file
        fd, path = tempfile.mkstemp(suffix=".bin")
        try:
            with os.fdopen(fd, 'wb') as f:
                # Generate deterministic content based on timestamp
                seed = int(time.time())
                content = bytes([i % 256 for i in range(size_kb * 1024)])
                f.write(content)
            
            # Calculate hash for verification
            content_hash = hashlib.sha256(content).hexdigest()
            
            self.results["test_content"] = {
                "path": path,
                "size_bytes": size_kb * 1024,
                "hash": content_hash
            }
            
            logger.info(f"Created test content: {path} ({size_kb}KB, SHA256: {content_hash[:16]}...)")
            return path
            
        except Exception as e:
            logger.error(f"Error creating test content: {e}")
            return None
    
    def upload_to_ipfs(self, file_path):
        """Upload test content to IPFS."""
        logger.info(f"Uploading to IPFS: {file_path}")
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post(f"{self.base_url}/ipfs/add", files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Extract CID - handle different response formats
                    cid = None
                    if "cid" in result:
                        cid = result["cid"]
                    elif "Hash" in result:
                        cid = result["Hash"]
                    
                    if cid:
                        logger.info(f"Successfully uploaded to IPFS: {cid}")
                        self.results["ipfs_upload"] = {
                            "success": True,
                            "cid": cid,
                            "response": result
                        }
                        return cid
                    else:
                        logger.error(f"Failed to extract CID from response: {result}")
                        self.results["ipfs_upload"] = {
                            "success": False,
                            "error": "Could not extract CID from response",
                            "response": result
                        }
                else:
                    logger.error(f"Failed to upload to IPFS: {response.status_code} - {response.text}")
                    self.results["ipfs_upload"] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "response_text": response.text
                    }
                    
            return None
        
        except Exception as e:
            logger.error(f"Error uploading to IPFS: {e}")
            self.results["ipfs_upload"] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            return None
    
    def transfer_to_backend(self, backend, cid):
        """Transfer content from IPFS to storage backend."""
        logger.info(f"Transferring from IPFS to {backend}: {cid}")
        
        # Skip if backend doesn't support from_ipfs
        if backend == "lassie":
            logger.info(f"Skipping transfer to {backend} (retrieval-only backend)")
            self.results["backend_transfers"][backend] = {
                "success": False,
                "skipped": True,
                "reason": "Retrieval-only backend"
            }
            return None
        
        # Prepare parameters based on backend type
        params = {"cid": cid}
        
        if backend == "huggingface":
            params["repo_id"] = "test-ipfs-kit-repo"
        elif backend == "s3":
            params["bucket"] = "test-ipfs-kit-bucket"
        
        try:
            response = requests.post(
                f"{self.base_url}/{backend}/from_ipfs", 
                json=params,
                # Allow longer timeout for real implementations
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully transferred to {backend}")
                
                self.results["backend_transfers"][backend] = {
                    "success": True,
                    "params": params,
                    "response": result
                }
                return result
            else:
                logger.error(f"Failed to transfer to {backend}: {response.status_code} - {response.text}")
                self.results["backend_transfers"][backend] = {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "params": params
                }
                return None
        
        except Exception as e:
            logger.error(f"Error transferring to {backend}: {e}")
            self.results["backend_transfers"][backend] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "params": params
            }
            return None
    
    def retrieve_from_backend(self, backend):
        """Retrieve content from storage backend back to IPFS."""
        logger.info(f"Retrieving from {backend} back to IPFS")
        
        # For Lassie, use the original CID for retrieval (it's designed for IPFS retrieval)
        if backend == "lassie":
            try:
                # Get the original CID from the IPFS upload
                original_cid = self.results["ipfs_upload"].get("cid")
                if not original_cid:
                    logger.error("No original CID available for Lassie retrieval")
                    self.results["backend_retrievals"][backend] = {
                        "success": False,
                        "error": "No original CID available"
                    }
                    return None
                
                # Use Lassie to retrieve the CID
                response = requests.post(
                    f"{self.base_url}/{backend}/to_ipfs",
                    json={"cid": original_cid},
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully retrieved from {backend}")
                    
                    self.results["backend_retrievals"][backend] = {
                        "success": True,
                        "response": result,
                        "retrieved_cid": result.get("cid", original_cid)
                    }
                    return result
                else:
                    logger.error(f"Failed to retrieve from {backend}: {response.status_code} - {response.text}")
                    self.results["backend_retrievals"][backend] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    return None
            
            except Exception as e:
                logger.error(f"Error retrieving from {backend}: {e}")
                self.results["backend_retrievals"][backend] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                return None
        
        # For other backends, check if we have a successful transfer first
        if not self.results["backend_transfers"].get(backend, {}).get("success", False):
            logger.warning(f"Skipping retrieval from {backend} - previous transfer failed")
            self.results["backend_retrievals"][backend] = {
                "success": False,
                "skipped": True,
                "reason": "Previous transfer failed"
            }
            return None
        
        # Prepare parameters based on backend and previous transfer
        transfer_result = self.results["backend_transfers"][backend].get("response", {})
        params = {}
        
        if backend == "huggingface":
            params["repo_id"] = transfer_result.get("repo_id", "test-ipfs-kit-repo")
            params["path_in_repo"] = transfer_result.get("path_in_repo", f"ipfs/{transfer_result.get('cid')}")
        elif backend == "storacha":
            params["car_cid"] = transfer_result.get("car_cid")
        elif backend == "filecoin":
            params["deal_id"] = transfer_result.get("deal_id")
        elif backend == "s3":
            params["bucket"] = transfer_result.get("bucket", "test-ipfs-kit-bucket")
            params["key"] = transfer_result.get("key")
        
        # Make the request
        try:
            response = requests.post(
                f"{self.base_url}/{backend}/to_ipfs", 
                json=params,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully retrieved from {backend}")
                
                # Extract returned CID
                cid = result.get("cid")
                
                self.results["backend_retrievals"][backend] = {
                    "success": True,
                    "params": params,
                    "response": result,
                    "retrieved_cid": cid
                }
                return result
            else:
                logger.error(f"Failed to retrieve from {backend}: {response.status_code} - {response.text}")
                self.results["backend_retrievals"][backend] = {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "params": params
                }
                return None
        
        except Exception as e:
            logger.error(f"Error retrieving from {backend}: {e}")
            self.results["backend_retrievals"][backend] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "params": params
            }
            return None
    
    def download_and_verify(self, backend, cid):
        """Download content from IPFS and verify its integrity."""
        logger.info(f"Downloading and verifying content for {backend}: {cid}")
        
        try:
            # Download the content
            response = requests.get(f"{self.base_url}/ipfs/cat/{cid}")
            
            if response.status_code == 200:
                content = response.content
                
                # Calculate hash
                content_hash = hashlib.sha256(content).hexdigest()
                
                # Compare with original
                original_hash = self.results["test_content"]["hash"]
                match = content_hash == original_hash
                
                self.results["content_verification"][backend] = {
                    "success": True,
                    "downloaded_size": len(content),
                    "original_hash": original_hash,
                    "downloaded_hash": content_hash,
                    "match": match,
                    "verification_message": f"{'✅ Content verified' if match else '❌ Content mismatch'}"
                }
                
                logger.info(f"Content verification for {backend}: {'✅ Match' if match else '❌ Mismatch'}")
                return match
            else:
                logger.error(f"Failed to download content: {response.status_code} - {response.text}")
                self.results["content_verification"][backend] = {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                return False
        
        except Exception as e:
            logger.error(f"Error verifying content: {e}")
            self.results["content_verification"][backend] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            return False
    
    def run_test(self, size_kb=100):
        """Run comprehensive test for all storage backends."""
        logger.info("Starting comprehensive storage backend test...")
        
        # Step 1: Verify MCP server
        if not self.verify_mcp_server():
            logger.error("MCP server verification failed, aborting test")
            return self.results
        
        # Step 2: Check backend status
        self.check_backend_status()
        
        # Step 3: Create test content
        test_file = self.create_test_content(size_kb)
        if not test_file:
            logger.error("Failed to create test content, aborting test")
            return self.results
        
        # Step 4: Upload to IPFS
        cid = self.upload_to_ipfs(test_file)
        if not cid:
            logger.error("Failed to upload to IPFS, aborting test")
            return self.results
        
        # Steps 5-7: For each backend: transfer, retrieve, verify
        for backend in self.backends:
            # Step 5: Transfer to backend
            transfer_result = self.transfer_to_backend(backend, cid)
            
            # Step 6: Retrieve from backend
            retrieval_result = self.retrieve_from_backend(backend)
            
            # Step 7: Verify content if retrieval was successful
            if retrieval_result and self.results["backend_retrievals"][backend].get("success", False):
                retrieved_cid = self.results["backend_retrievals"][backend].get("retrieved_cid")
                if retrieved_cid:
                    self.download_and_verify(backend, retrieved_cid)
        
        # Save results to file
        output_file = f"storage_backends_comprehensive_test_results.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Test completed, results saved to {output_file}")
        
        # Print summary
        self.print_summary()
        
        # Cleanup
        if os.path.exists(test_file):
            os.unlink(test_file)
            
        return self.results
    
    def print_summary(self):
        """Print a summary of test results."""
        print("Test message")
        print("=== STORAGE BACKEND COMPREHENSIVE TEST RESULTS ===")
        
        # Server info
        print(f"MCP Server: {self.mcp_url}")
        
        # Backend status
        print("Test message")
        print("Backend Status:")
        for backend, status in self.results["backend_status"].items():
            status_text = "✅ Available" if status.get("success", False) else "❌ Not available"
            print(f"  {backend}: {status_text}")
        
        # IPFS upload
        ipfs_success = self.results["ipfs_upload"].get("success", False)
        ipfs_cid = self.results["ipfs_upload"].get("cid", "N/A")
        print(f"""
IPFS Upload: {'✅ Success' if ipfs_success else '❌ Failed'}""")
        if ipfs_success:
            print(f"  CID: {ipfs_cid}")
        
        # Backend transfers
        print("\nBackend Transfers:")
        for backend in self.backends:
            transfer = self.results["backend_transfers"].get(backend, {})
            if transfer.get("skipped", False):
                print(f"  {backend}: ⚠️ Skipped - {transfer.get('reason', 'N/A')}")
            else:
                success = transfer.get("success", False)
                print(f"  {backend}: {'✅ Success' if success else '❌ Failed'}")
        
        # Backend retrievals
        print("\nBackend Retrievals:")
        for backend in self.backends:
            retrieval = self.results["backend_retrievals"].get(backend, {})
            if retrieval.get("skipped", False):
                print(f"  {backend}: ⚠️ Skipped - {retrieval.get('reason', 'N/A')}")
            else:
                success = retrieval.get("success", False)
                print(f"  {backend}: {'✅ Success' if success else '❌ Failed'}")
        
        # Content verification
        print("\nContent Verification:")
        for backend in self.backends:
            verification = self.results["content_verification"].get(backend, {})
            if not verification:
                print(f"  {backend}: ⚠️ Not performed")
            elif not verification.get("success", False):
                print(f"  {backend}: ❌ Failed - {verification.get('error', 'N/A')}")
            else:
                match = verification.get("match", False)
                print(f"  {backend}: {'✅ Verified' if match else '❌ Mismatch'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test storage backends comprehensively")
    parser.add_argument("--url", default="http://localhost:9993", help="MCP server URL")
    parser.add_argument("--prefix", default="/api/v0", help="API prefix")
    parser.add_argument("--size", type=int, default=100, help="Test content size in KB")
    
    # Only parse args when running the script directly, not when imported by pytest
    
    if __name__ == "__main__":
    
        args = parser.parse_args()
    
    else:
    
        # When run under pytest, use default values
    
        args = parser.parse_args([])
    
    tester = StorageBackendTester(mcp_url=args.url, api_prefix=args.prefix)
    tester.run_test(size_kb=args.size)
