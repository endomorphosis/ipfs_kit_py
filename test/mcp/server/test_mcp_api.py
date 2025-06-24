#!/usr/bin/env python3
import requests
import json
import time
import logging
import sys
from pprint import pformat

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("mcp-api-tester")

class MCPAPITester:
    """Comprehensive MCP API tester."""

    def __init__(self, base_url="http://localhost:9990"):
        """Initialize the API tester with a base URL."""
        self.base_url = base_url
        self.session = requests.Session()
        # Track results for reporting
        self.results = {
            "passed": [],
            "failed": [],
            "skipped": []
        }

    def test_endpoint(self, method, endpoint, expect_status=200, **kwargs):
        """
        Test a specific API endpoint.

        Args:
            method: HTTP method (get, post, etc.)
            endpoint: Endpoint to test
            expect_status: Expected HTTP status code
            **kwargs: Arguments for the request method

        Returns:
            Response data or error dictionary
        """
        url = f"{self.base_url}{endpoint}"
        method_fn = getattr(self.session, method.lower())

        test_name = f"{method.upper()} {endpoint}"
        logger.info(f"Testing: {test_name}")

        try:
            start_time = time.time()
            response = method_fn(url, **kwargs)
            elapsed = time.time() - start_time

            status_code = response.status_code

            try:
                data = response.json()
                logger.info(f"Response: {status_code} - {json.dumps(data, indent=2)[:1000]}")
            except:
                data = {"text": response.text[:1000], "non_json": True}
                logger.info(f"Response: {status_code} - (Non-JSON) {response.text[:1000]}")

            result = {
                "status_code": status_code,
                "elapsed": elapsed,
                "data": data
            }

            if status_code == expect_status:
                logger.info(f"✅ Passed: {test_name} ({elapsed:.3f}s)")
                self.results["passed"].append({"test": test_name, "result": result})
            else:
                logger.error(f"❌ Failed: {test_name} - Expected status {expect_status}, got {status_code}")
                self.results["failed"].append({"test": test_name, "result": result})

            return result

        except Exception as e:
            logger.error(f"❌ Error: {test_name} - {e}")
            result = {"error": str(e), "exception": type(e).__name__}
            self.results["failed"].append({"test": test_name, "result": result})
            return result

    def test_health(self):
        """Test the health endpoint."""
        return self.test_endpoint("get", "/health")

    def test_root(self):
        """Test the root endpoint."""
        return self.test_endpoint("get", "/")

    def test_api_versions(self):
        """Test the API version endpoints."""
        return self.test_endpoint("get", "/api/v0/versions")

    def test_mcp_health(self):
        """Test the MCP health endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/health")

    def test_ipfs_version(self):
        """Test the IPFS version endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/ipfs/version")

    def test_ipfs_id(self):
        """Test the IPFS ID endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/ipfs/id")

    def test_ipfs_add(self):
        """Test the IPFS add endpoint."""
        # Create a simple text file to upload
        test_data = b"Hello, MCP Server! This is a test file."
        files = {"file": ("test.txt", test_data)}
        return self.test_endpoint("post", "/api/v0/mcp/ipfs/add", files=files)

    def test_ipfs_cat(self, cid="QmPHPs7vLTJN7nB4ryQ6MiQEyF6DmcrdAHJRbQXFXxsdvq"):
        """Test the IPFS cat endpoint with a known CID."""
        # Try the path parameter version first
        result = self.test_endpoint("get", f"/api/v0/mcp/ipfs/cat/{cid}")

        # If that fails, try the query parameter version
        if result.get("status_code") != 200:
            return self.test_endpoint("get", f"/api/v0/mcp/ipfs/cat?arg={cid}")

        return result

    def test_ipfs_pin_add(self, cid="QmPHPs7vLTJN7nB4ryQ6MiQEyF6DmcrdAHJRbQXFXxsdvq"):
        """Test the IPFS pin add endpoint."""
        return self.test_endpoint("post", f"/api/v0/mcp/ipfs/pin/add?arg={cid}")

    def test_ipfs_pin_ls(self):
        """Test the IPFS pin list endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/ipfs/pin/ls")

    def test_ipfs_pin_rm(self, cid="QmPHPs7vLTJN7nB4ryQ6MiQEyF6DmcrdAHJRbQXFXxsdvq"):
        """Test the IPFS pin remove endpoint."""
        return self.test_endpoint("post", f"/api/v0/mcp/ipfs/pin/rm?arg={cid}")

    def test_storage_backends(self):
        """Test the storage backends endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/storage/backends")

    def test_webrtc_status(self):
        """Test the WebRTC status endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/webrtc/status")

    def test_webrtc_check(self):
        """Test the WebRTC dependency check endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/webrtc/check")

    def test_libp2p_status(self):
        """Test the libp2p status endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/libp2p/status")

    def test_peer_websocket_status(self):
        """Test the peer websocket status endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/peer_websocket/status")

    def test_fs_journal_status(self):
        """Test the filesystem journal status endpoint."""
        return self.test_endpoint("get", "/api/v0/mcp/fs_journal/status")

    def test_all_endpoints(self):
        """Test all key endpoints."""
        # Basic endpoints
        self.test_root()
        self.test_health()
        self.test_api_versions()
        self.test_mcp_health()

        # IPFS core endpoints
        self.test_ipfs_version()
        self.test_ipfs_id()
        add_result = self.test_ipfs_add()

        # If add was successful, use that CID for subsequent tests
        if add_result.get("status_code") == 200 and add_result.get("data", {}).get("success"):
            cid = add_result["data"].get("cid")
            if cid:
                self.test_ipfs_cat(cid)
                self.test_ipfs_pin_add(cid)
                self.test_ipfs_pin_ls()
                self.test_ipfs_pin_rm(cid)
            else:
                # Use default CID if we couldn't get one from add
                self.test_ipfs_cat()
                self.test_ipfs_pin_add()
                self.test_ipfs_pin_ls()
                self.test_ipfs_pin_rm()
        else:
            # Use default CID if add failed
            self.test_ipfs_cat()
            self.test_ipfs_pin_add()
            self.test_ipfs_pin_ls()
            self.test_ipfs_pin_rm()

        # Storage backends
        self.test_storage_backends()

        # Optional controllers
        self.test_webrtc_status()
        self.test_webrtc_check()
        self.test_libp2p_status()
        self.test_peer_websocket_status()
        self.test_fs_journal_status()

        return self.generate_report()

    def analyze_failures(self):
        """Analyze failures to identify patterns."""
        if not self.results["failed"]:
            return "No failures to analyze"

        patterns = {}
        for test in self.results["failed"]:
            result = test["result"]
            error_type = result.get("exception") or str(result.get("status_code"))

            if error_type not in patterns:
                patterns[error_type] = []

            patterns[error_type].append(test["test"])

        return {
            "error_patterns": patterns,
            "total_failures": len(self.results["failed"]),
            "recommendation": self._generate_fix_recommendations(patterns)
        }

    def _generate_fix_recommendations(self, patterns):
        """Generate recommendations based on error patterns."""
        recommendations = []

        for error_type, tests in patterns.items():
            if error_type == "ConnectionError":
                recommendations.append("Check if the MCP server is running and accessible")
            elif error_type == "500":
                recommendations.append("Server internal errors detected - check logs for exceptions")
            elif error_type == "404":
                recommendations.append("Endpoints not found - check URL paths and API version")
            elif error_type == "ConnectionRefusedError":
                recommendations.append("MCP server is not accepting connections - restart it")

        return recommendations

    def generate_report(self):
        """Generate a summary report of test results."""
        total_tests = len(self.results["passed"]) + len(self.results["failed"]) + len(self.results["skipped"])
        pass_rate = len(self.results["passed"]) / total_tests * 100 if total_tests > 0 else 0

        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": len(self.results["passed"]),
                "failed": len(self.results["failed"]),
                "skipped": len(self.results["skipped"]),
                "pass_rate": f"{pass_rate:.1f}%"
            },
            "failed_tests": [f['test'] for f in self.results["failed"]],
            "issues": self.analyze_failures() if self.results["failed"] else "No issues detected"
        }

        logger.info("\n" + "="*50)
        logger.info("MCP API TEST REPORT")
        logger.info("="*50)
        logger.info(f"Total Tests: {report['summary']['total_tests']}")
        logger.info(f"Passed: {report['summary']['passed']} ({report['summary']['pass_rate']})")
        logger.info(f"Failed: {report['summary']['failed']}")
        logger.info(f"Skipped: {report['summary']['skipped']}")

        if report['summary']['failed'] > 0:
            logger.info("\nFailed Tests:")
            for test in report["failed_tests"]:
                logger.info(f"  - {test}")

            logger.info("\nIssue Analysis:")
            if isinstance(report["issues"], dict):
                for key, value in report["issues"].items():
                    if key == "error_patterns":
                        logger.info("  Error Patterns:")
                        for err_type, tests in value.items():
                            logger.info(f"    - {err_type}: {len(tests)} tests")
                    elif key == "recommendation":
                        logger.info("  Recommendations:")
                        for rec in value:
                            logger.info(f"    - {rec}")
                    else:
                        logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {report['issues']}")

        logger.info("="*50)
        return report

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Test MCP API endpoints")
    parser.add_argument("--url", default="http://localhost:9990", help="Base URL of the MCP server")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    logger.info(f"Testing MCP API at {args.url}")
    tester = MCPAPITester(args.url)
    report = tester.test_all_endpoints()

    # Return exit code based on test results
    return 0 if report["summary"]["failed"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
