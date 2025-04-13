#!/usr/bin/env python3
"""
Script to fix MCP server storage backends by enabling simulation mode via API calls.
"""

import os
import sys
import json
import time
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MCP_URL = "http://localhost:9991"
API_PREFIX = "/api/v0"
TEST_FILE = "/tmp/mcp_test_1mb.bin"
RESULTS_FILE = "storage_backend_test_results.json"

class StorageBackendManager:
    """Configure and test MCP server storage backends."""
    
    def __init__(self, server_url=MCP_URL, api_prefix=API_PREFIX):
        """Initialize with server URL."""
        self.server_url = server_url
        self.api_prefix = api_prefix
        self.base_url = f"{server_url}{api_prefix}"
        logger.info(f"Storage Backend Manager initialized for URL: {self.base_url}")
    
    def check_server_health(self):
        """Check if the MCP server is running and healthy."""
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return {"success": False, "error": str(e)}
    
    def get_controllers(self):
        """Get list of controllers from health check."""
        health = self.check_server_health()
        if health.get("success", False):
            controllers = health.get("controllers", {})
            return {k: v for k, v in controllers.items() if k.startswith("storage_") or k == "s3"}
        return {}
    
    def create_test_file(self, size_mb=1):
        """Create a test file with random data."""
        if not os.path.exists(TEST_FILE):
            logger.info(f"Creating test file: {TEST_FILE} ({size_mb}MB)")
            os.system(f"dd if=/dev/urandom of={TEST_FILE} bs=1M count={size_mb} 2>/dev/null")
            
        logger.info(f"Test file size: {os.path.getsize(TEST_FILE)} bytes")
        return TEST_FILE
    
    def upload_to_ipfs(self, file_path):
        """Upload a file to IPFS through the MCP server."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{self.base_url}/ipfs/add",
                    files=files
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract CID based on response format
                cid = None
                if "cid" in result:
                    cid = result["cid"]
                elif "Hash" in result:
                    cid = result["Hash"]
                elif "result" in result and isinstance(result["result"], dict) and "pins" in result["result"]:
                    pins = result["result"]["pins"]
                    if pins:
                        cid = list(pins.keys())[0]
                
                if cid:
                    logger.info(f"IPFS upload successful. CID: {cid}")
                else:
                    logger.warning(f"IPFS upload successful but couldn't extract CID. Response: {result}")
                
                return {"success": True, "cid": cid, "result": result}
                
        except Exception as e:
            logger.error(f"Error uploading to IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    def check_backend_status(self, backend):
        """Check status of a storage backend."""
        endpoints = [
            f"{self.base_url}/storage/{backend}/status",
            f"{self.base_url}/{backend}/status",
            f"{self.base_url}/storage/{backend.replace('storage_', '')}/status",
            f"{self.base_url}/{backend.replace('storage_', '')}/status"
        ]
        
        for endpoint in endpoints:
            try:
                logger.debug(f"Trying endpoint: {endpoint}")
                response = requests.get(endpoint)
                if response.status_code == 200:
                    return {"success": True, "endpoint": endpoint, "result": response.json()}
            except requests.RequestException:
                continue
        
        logger.error(f"Failed to check status for {backend} - all endpoints failed")
        return {"success": False, "error": "All status endpoints failed"}
    
    def enable_simulation_mode(self, backend):
        """Enable simulation mode for a backend by configuration or API call."""
        endpoints = [
            f"{self.base_url}/storage/{backend}/enable_simulation",
            f"{self.base_url}/{backend}/enable_simulation",
            f"{self.base_url}/storage/{backend.replace('storage_', '')}/enable_simulation",
            f"{self.base_url}/{backend.replace('storage_', '')}/enable_simulation"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.post(endpoint, json={"enabled": True})
                if response.status_code == 200:
                    logger.info(f"Successfully enabled simulation mode for {backend}")
                    return {"success": True, "endpoint": endpoint, "result": response.json()}
            except requests.RequestException:
                continue
        
        # If no direct simulation mode endpoint, try mocking endpoint configuration
        # This is done as a fallback and may not work without server-side support
        logger.warning(f"No simulation mode endpoint found for {backend}, creating a workaround")
        
        # Try enabling it through admin endpoint if available
        try:
            response = requests.post(f"{self.base_url}/admin/backend/configure", 
                                    json={"backend": backend, "simulation_mode": True})
            if response.status_code == 200:
                logger.info(f"Enabled simulation mode via admin endpoint for {backend}")
                return {"success": True, "method": "admin", "result": response.json()}
        except:
            pass
        
        return {"success": False, "error": "No compatible simulation mode endpoint found"}
    
    def test_backend_operations(self, backend, cid):
        """Test backend operations using the uploaded CID."""
        results = {
            "from_ipfs": {"success": False, "tried": False},
            "to_ipfs": {"success": False, "tried": False}
        }
        
        # Adjust endpoints based on backend name
        clean_name = backend.replace("storage_", "")
        
        # Test from_ipfs operation (where applicable)
        if backend not in ["storage_lassie", "lassie"]:  # Lassie is retrieval only
            results["from_ipfs"]["tried"] = True
            
            # Build test parameters based on backend
            params = {"cid": cid}
            
            if backend in ["storage_huggingface", "huggingface"]:
                params["repo_id"] = "test-repo"
                params["path_in_repo"] = f"test/{cid}"
            elif backend in ["s3"]:
                params["bucket"] = "test-bucket"
                params["key"] = f"test/{cid}"
            
            # Try different endpoint patterns
            endpoints = [
                f"{self.base_url}/storage/{backend}/from_ipfs",
                f"{self.base_url}/{backend}/from_ipfs",
                f"{self.base_url}/storage/{clean_name}/from_ipfs",
                f"{self.base_url}/{clean_name}/from_ipfs"
            ]
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Testing {backend} from_ipfs with {endpoint}")
                    response = requests.post(endpoint, json=params)
                    if response.status_code == 200:
                        results["from_ipfs"] = {
                            "success": True, 
                            "endpoint": endpoint,
                            "result": response.json()
                        }
                        logger.info(f"✅ Successfully tested {backend} from_ipfs")
                        break
                    else:
                        logger.warning(f"Failed with status {response.status_code}: {response.text}")
                except Exception as e:
                    logger.warning(f"Error testing {endpoint}: {e}")
        
        # Test to_ipfs operation (where applicable)
        # Use a standard test CID for retrieval services
        test_cid = "QmQPeNsJPyVWPFDVHb77w8G42Fvo15z4bG2X8D2GhfbSXc"  # IPFS docs folder
        
        results["to_ipfs"]["tried"] = True
        
        # Build test parameters based on backend
        params = {}
        
        if backend in ["storage_lassie", "lassie"]:
            params["cid"] = test_cid
        elif backend in ["storage_huggingface", "huggingface"]:
            params["repo_id"] = "test-repo"
            params["path_in_repo"] = f"test/{cid}"
        elif backend in ["storage_storacha", "storacha"]:
            params["car_cid"] = f"mock-car-{cid[:10]}"
        elif backend in ["storage_filecoin", "filecoin"]:
            params["deal_id"] = f"mock-deal-{cid[:8]}"
        elif backend in ["s3"]:
            params["bucket"] = "test-bucket"
            params["key"] = f"test/{cid}"
        
        # Try different endpoint patterns
        endpoints = [
            f"{self.base_url}/storage/{backend}/to_ipfs",
            f"{self.base_url}/{backend}/to_ipfs",
            f"{self.base_url}/storage/{clean_name}/to_ipfs",
            f"{self.base_url}/{clean_name}/to_ipfs"
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Testing {backend} to_ipfs with {endpoint}")
                response = requests.post(endpoint, json=params)
                if response.status_code == 200:
                    results["to_ipfs"] = {
                        "success": True, 
                        "endpoint": endpoint,
                        "result": response.json()
                    }
                    logger.info(f"✅ Successfully tested {backend} to_ipfs")
                    break
                else:
                    logger.warning(f"Failed with status {response.status_code}: {response.text}")
            except Exception as e:
                logger.warning(f"Error testing {endpoint}: {e}")
        
        return results
    
    def create_backend_simulation_endpoints(self, backend):
        """Create custom simulation endpoint handlers for the backend."""
        # This function creates new simulation endpoints directly on the API server
        # Note: This requires that the MCP server has dynamic endpoint registration capabilities
        
        # Return immediately if we don't have dynamic endpoint capabilities
        return {"success": False, "error": "Dynamic endpoint registration not supported on this server"}
    
    def run_backend_diagnostic(self):
        """Run diagnostics on all storage backends and enable simulation mode."""
        # First check server health
        health = self.check_server_health()
        if not health.get("success", False):
            logger.error("Failed to connect to MCP server")
            return {"success": False, "error": "Server not reachable"}
        
        # Get list of storage backends
        backends = self.get_controllers()
        if not backends:
            logger.error("No storage backends found")
            return {"success": False, "error": "No storage backends found"}
        
        logger.info(f"Found {len(backends)} storage backends: {', '.join(backends.keys())}")
        
        # Create test file and upload to IPFS
        test_file = self.create_test_file()
        ipfs_result = self.upload_to_ipfs(test_file)
        
        if not ipfs_result.get("success", False) or not ipfs_result.get("cid"):
            logger.error("Failed to upload test file to IPFS")
            return {"success": False, "error": "IPFS upload failed"}
        
        cid = ipfs_result.get("cid")
        
        # Test each backend
        backend_results = {}
        
        for backend_name in backends:
            logger.info(f"\n=== Testing {backend_name} backend ===")
            
            # 1. Check status
            status = self.check_backend_status(backend_name)
            logger.info(f"Status check result: {status.get('success', False)}")
            
            # 2. Enable simulation mode
            simulation = self.enable_simulation_mode(backend_name)
            logger.info(f"Simulation mode enabled: {simulation.get('success', False)}")
            
            # 3. Check status again after enabling simulation
            status_after = self.check_backend_status(backend_name)
            logger.info(f"Status after simulation enabled: {status_after.get('result', {}).get('is_available', False)}")
            
            # 4. Test operations
            operations = self.test_backend_operations(backend_name, cid)
            
            # 5. Record results
            backend_results[backend_name] = {
                "initial_status": status,
                "simulation_mode": simulation,
                "status_after_simulation": status_after,
                "operations": operations,
                "overall_success": (
                    status.get("success", False) and
                    (status_after.get("result", {}).get("is_available", False) or 
                     (operations["from_ipfs"]["tried"] and operations["from_ipfs"]["success"]) or
                     (operations["to_ipfs"]["tried"] and operations["to_ipfs"]["success"]))
                )
            }
            
            logger.info(f"Overall success for {backend_name}: {backend_results[backend_name]['overall_success']}")
        
        # Collect results
        results = {
            "timestamp": time.time(),
            "server_url": self.server_url,
            "health": health,
            "ipfs_upload": ipfs_result,
            "backend_results": backend_results,
            "summary": {
                "total_backends": len(backends),
                "successful_backends": sum(1 for r in backend_results.values() if r["overall_success"]),
                "simulation_enabled": sum(1 for r in backend_results.values() if r["simulation_mode"].get("success", False))
            }
        }
        
        # Save results to file
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=2)
        
        return results
        
def run_test_with_backends():
    """Run practical tests with each storage backend."""
    # Create a test file
    test_file_path = "/tmp/backend_test_file.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test file for storage backends\n" * 100)
    
    logger.info(f"Created test file: {test_file_path}")
    
    # Configure test parameters for each backend
    backend_tests = {
        "storage_huggingface": {
            "from_ipfs": {"repo_id": "test-repo", "path_in_repo": "test-file.txt"},
            "to_ipfs": {"repo_id": "test-repo", "path_in_repo": "test-file.txt"}
        },
        "storage_storacha": {
            "from_ipfs": {},
            "to_ipfs": {"car_cid": "mock-car-abcdef1234"}
        },
        "storage_filecoin": {
            "from_ipfs": {},
            "to_ipfs": {"deal_id": "mock-deal-12345678"}
        },
        "storage_lassie": {
            "to_ipfs": {"cid": "QmQPeNsJPyVWPFDVHb77w8G42Fvo15z4bG2X8D2GhfbSXc"}
        },
        "s3": {
            "from_ipfs": {"bucket": "test-bucket", "key": "test-file.txt"},
            "to_ipfs": {"bucket": "test-bucket", "key": "test-file.txt"}
        }
    }
    
    # Create API client and upload test file to IPFS
    manager = StorageBackendManager()
    
    # Upload to IPFS
    with open(test_file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(f"{manager.base_url}/ipfs/add", files=files)
        
        if response.status_code != 200:
            logger.error(f"Failed to upload to IPFS: {response.status_code}")
            return {"success": False, "error": "IPFS upload failed"}
        
        result = response.json()
        cid = result.get("cid") or result.get("Hash")
        
        if not cid:
            logger.error("Failed to extract CID from IPFS upload response")
            return {"success": False, "error": "CID extraction failed"}
        
        logger.info(f"Uploaded test file to IPFS: {cid}")
    
    # Test each backend
    backend_results = {}
    
    for backend_name, test_params in backend_tests.items():
        logger.info(f"\n=== Testing {backend_name} backend with actual operations ===")
        
        # Set up results structure
        backend_results[backend_name] = {
            "from_ipfs": {"success": False, "tried": False, "error": None},
            "to_ipfs": {"success": False, "tried": False, "error": None}
        }
        
        # Clean backend name (remove 'storage_' prefix if present)
        clean_name = backend_name.replace("storage_", "")
        
        # Try from_ipfs if this backend supports it
        if "from_ipfs" in test_params:
            backend_results[backend_name]["from_ipfs"]["tried"] = True
            
            # Create request parameters
            params = {**test_params["from_ipfs"], "cid": cid}
            
            # Try different endpoint patterns
            endpoints = [
                f"{manager.base_url}/storage/{backend_name}/from_ipfs",
                f"{manager.base_url}/{backend_name}/from_ipfs",
                f"{manager.base_url}/storage/{clean_name}/from_ipfs",
                f"{manager.base_url}/{clean_name}/from_ipfs"
            ]
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Testing {backend_name} from_ipfs with {endpoint}")
                    response = requests.post(endpoint, json=params)
                    
                    if response.status_code == 200:
                        result = response.json()
                        backend_results[backend_name]["from_ipfs"] = {
                            "success": True,
                            "result": result,
                            "endpoint": endpoint
                        }
                        logger.info(f"✅ Successfully tested {backend_name} from_ipfs")
                        break
                    else:
                        logger.warning(f"Failed with status {response.status_code}: {response.text}")
                        backend_results[backend_name]["from_ipfs"]["error"] = response.text
                except Exception as e:
                    logger.warning(f"Error testing {endpoint}: {e}")
                    backend_results[backend_name]["from_ipfs"]["error"] = str(e)
        
        # Try to_ipfs if this backend supports it
        if "to_ipfs" in test_params:
            backend_results[backend_name]["to_ipfs"]["tried"] = True
            
            # Create request parameters
            params = test_params["to_ipfs"]
            
            # Try different endpoint patterns
            endpoints = [
                f"{manager.base_url}/storage/{backend_name}/to_ipfs",
                f"{manager.base_url}/{backend_name}/to_ipfs",
                f"{manager.base_url}/storage/{clean_name}/to_ipfs",
                f"{manager.base_url}/{clean_name}/to_ipfs"
            ]
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Testing {backend_name} to_ipfs with {endpoint}")
                    response = requests.post(endpoint, json=params)
                    
                    if response.status_code == 200:
                        result = response.json()
                        backend_results[backend_name]["to_ipfs"] = {
                            "success": True,
                            "result": result,
                            "endpoint": endpoint
                        }
                        logger.info(f"✅ Successfully tested {backend_name} to_ipfs")
                        break
                    else:
                        logger.warning(f"Failed with status {response.status_code}: {response.text}")
                        backend_results[backend_name]["to_ipfs"]["error"] = response.text
                except Exception as e:
                    logger.warning(f"Error testing {endpoint}: {e}")
                    backend_results[backend_name]["to_ipfs"]["error"] = str(e)
        
        # Overall success if at least one operation succeeded
        backend_results[backend_name]["overall_success"] = (
            backend_results[backend_name]["from_ipfs"].get("success", False) or
            backend_results[backend_name]["to_ipfs"].get("success", False)
        )
        
        logger.info(f"Overall success for {backend_name}: {backend_results[backend_name]['overall_success']}")
    
    # Save practical test results
    with open("storage_backend_practical_tests.json", "w") as f:
        json.dump(backend_results, f, indent=2)
    
    return backend_results

def main():
    """Run the storage backend fixer."""
    logger.info("\n=== MCP Storage Backend Testing Tool ===\n")
    
    try:
        # First run diagnostic
        manager = StorageBackendManager()
        diagnostic_results = manager.run_backend_diagnostic()
        
        # Then run practical tests
        practical_results = run_test_with_backends()
        
        # Print summary
        print("\n=== STORAGE BACKEND TEST SUMMARY ===")
        
        if diagnostic_results.get("success", False) == False:
            print(f"❌ Diagnostic failed: {diagnostic_results.get('error', 'Unknown error')}")
        else:
            print(f"✅ Server health check: Passed")
            print(f"✅ IPFS upload test: Passed")
            
            summary = diagnostic_results.get("summary", {})
            print(f"Total backends: {summary.get('total_backends', 0)}")
            print(f"Successful backends: {summary.get('successful_backends', 0)}")
            print(f"Simulation mode enabled: {summary.get('simulation_enabled', 0)}")
        
        print("\n=== BACKEND OPERATION RESULTS ===")
        for backend, result in practical_results.items():
            status = "✅ PASSED" if result.get("overall_success", False) else "❌ FAILED"
            print(f"{backend}: {status}")
            
            if "from_ipfs" in result and result["from_ipfs"].get("tried", False):
                from_status = "✅ Success" if result["from_ipfs"].get("success", False) else "❌ Failed"
                print(f"  - from_ipfs: {from_status}")
            
            if "to_ipfs" in result and result["to_ipfs"].get("tried", False):
                to_status = "✅ Success" if result["to_ipfs"].get("success", False) else "❌ Failed"
                print(f"  - to_ipfs: {to_status}")
        
        print(f"\nDetailed results saved to {RESULTS_FILE} and storage_backend_practical_tests.json")
        
    except Exception as e:
        logger.error(f"Error running backend tests: {e}")
        print(f"❌ An error occurred during testing: {e}")

if __name__ == "__main__":
    main()