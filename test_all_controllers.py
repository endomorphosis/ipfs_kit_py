"""
Comprehensive test script for all MCP server controllers.
This script tests each controller's endpoints and reports on functionality.
"""

import os
import time
import json
import sys
import requests
import tempfile
import random
import string

# Configuration
MCP_SERVER_URL = "http://localhost:8000"
MCP_API_PREFIX = "/api/v0/mcp"
TEST_CONTENT = "Hello, MCP Server! This is test content from comprehensive test script."

def random_string(length=10):
    """Generate a random string for testing."""
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))

def make_request(method, endpoint, **kwargs):
    """Make HTTP request with unified error handling."""
    url = f"{MCP_SERVER_URL}{endpoint}"
    
    try:
        response = getattr(requests, method.lower())(url, **kwargs)
        response.raise_for_status()
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json() if response.content and response.headers.get("content-type", "").startswith("application/json") else response.content,
            "headers": dict(response.headers)
        }
    except requests.exceptions.RequestException as e:
        error_data = {
            "success": False,
            "error": str(e),
            "status_code": getattr(e.response, "status_code", None) if hasattr(e, "response") else None
        }
        
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data["response"] = e.response.json()
            except ValueError:
                error_data["response_text"] = e.response.text
                
        return error_data

def test_core_endpoints():
    """Test the core MCP server endpoints."""
    results = {
        "health": make_request("GET", f"{MCP_API_PREFIX}/health"),
        "debug": make_request("GET", f"{MCP_API_PREFIX}/debug"),
        "operations": make_request("GET", f"{MCP_API_PREFIX}/operations"),
        "daemon_status": make_request("GET", f"{MCP_API_PREFIX}/daemon/status")
    }
    
    # Test daemon operations if the server is running
    if results["daemon_status"]["success"]:
        results["daemon_operations"] = {
            "start_daemon": make_request("POST", f"{MCP_API_PREFIX}/daemon/start/ipfs"),
            "stop_daemon": make_request("POST", f"{MCP_API_PREFIX}/daemon/stop/ipfs"),
            "start_monitor": make_request("POST", f"{MCP_API_PREFIX}/daemon/monitor/start"),
            "stop_monitor": make_request("POST", f"{MCP_API_PREFIX}/daemon/monitor/stop")
        }
    
    return results

def test_ipfs_controller():
    """Test all IPFS controller endpoints."""
    results = {"endpoints": {}}
    
    # Test add with JSON payload - the one endpoint we know works
    add_response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/add", 
        json={"content": TEST_CONTENT}
    )
    results["endpoints"]["add_json"] = add_response
    
    # If add was successful, use the CID for other operations
    if add_response["success"] and "cid" in add_response["data"]:
        cid = add_response["data"]["cid"]
        results["test_cid"] = cid
        
        # Test content retrieval
        results["endpoints"]["cat"] = make_request("GET", f"{MCP_API_PREFIX}/ipfs/cat/{cid}")
        results["endpoints"]["get"] = make_request("GET", f"{MCP_API_PREFIX}/ipfs/get/{cid}")
        
        # Test pin operations 
        results["endpoints"]["pin"] = make_request("POST", f"{MCP_API_PREFIX}/ipfs/pin", json={"cid": cid})
        results["endpoints"]["pins_list"] = make_request("GET", f"{MCP_API_PREFIX}/ipfs/pins")
        results["endpoints"]["unpin"] = make_request("POST", f"{MCP_API_PREFIX}/ipfs/unpin", json={"cid": cid})
    
    # Test form-based file upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        file_content = f"Test file content: {random_string(20)}"
        temp_file.write(file_content.encode())
        temp_file_path = temp_file.name
    
    try:
        with open(temp_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = requests.post(
                f"{MCP_SERVER_URL}{MCP_API_PREFIX}/ipfs/add",
                files=files
            )
        
        if response.status_code == 200:
            results["endpoints"]["add_form"] = {
                "success": True,
                "status_code": response.status_code,
                "data": response.json()
            }
        else:
            results["endpoints"]["add_form"] = {
                "success": False,
                "status_code": response.status_code,
                "error": "Form upload failed"
            }
            try:
                results["endpoints"]["add_form"]["response"] = response.json()
            except ValueError:
                results["endpoints"]["add_form"]["response_text"] = response.text
    except Exception as e:
        results["endpoints"]["add_form"] = {
            "success": False,
            "error": str(e)
        }
    finally:
        os.unlink(temp_file_path)
    
    return results

def test_cli_controller():
    """Test CLI controller endpoints."""
    results = {
        "version": make_request("GET", f"{MCP_API_PREFIX}/cli/version"),
        "command": make_request(
            "POST", 
            f"{MCP_API_PREFIX}/cli/command", 
            json={"command": "ipfs", "args": ["--version"]}
        )
    }
    
    # Additional possible CLI endpoints
    for endpoint in ["help", "commands", "status"]:
        results[endpoint] = make_request("GET", f"{MCP_API_PREFIX}/cli/{endpoint}")
    
    return results

def test_credential_controller():
    """Test credential controller endpoints."""
    results = {
        "list": make_request("GET", f"{MCP_API_PREFIX}/credentials/list"),
        "info": make_request("GET", f"{MCP_API_PREFIX}/credentials/info"),
        "types": make_request("GET", f"{MCP_API_PREFIX}/credentials/types")
    }
    
    # Test credential operations with a test credential
    test_credential = {
        "service": "test_service",
        "type": "api_key",
        "key": "test_key_" + random_string(8),
        "secret": "test_secret_" + random_string(16)
    }
    
    results["add"] = make_request(
        "POST",
        f"{MCP_API_PREFIX}/credentials/add",
        json=test_credential
    )
    
    # If add was successful, test deletion
    if results["add"]["success"]:
        results["delete"] = make_request(
            "POST",
            f"{MCP_API_PREFIX}/credentials/delete",
            json={"service": test_credential["service"]}
        )
    
    return results

def test_distributed_controller():
    """Test distributed controller endpoints."""
    results = {
        "status": make_request("GET", f"{MCP_API_PREFIX}/distributed/status"),
        "peers": make_request("GET", f"{MCP_API_PREFIX}/distributed/peers"),
        "ping": make_request("POST", f"{MCP_API_PREFIX}/distributed/ping", json={"peer_id": "test_peer"})
    }
    
    return results

def test_webrtc_controller():
    """Test WebRTC controller endpoints."""
    results = {
        "capabilities": make_request("GET", f"{MCP_API_PREFIX}/webrtc/capabilities"),
        "status": make_request("GET", f"{MCP_API_PREFIX}/webrtc/status"),
        "peers": make_request("GET", f"{MCP_API_PREFIX}/webrtc/peers")
    }
    
    return results

def test_fs_journal_controller():
    """Test filesystem journal controller endpoints."""
    results = {
        "status": make_request("GET", f"{MCP_API_PREFIX}/fs_journal/status"),
        "operations": make_request("GET", f"{MCP_API_PREFIX}/fs_journal/operations"),
        "stats": make_request("GET", f"{MCP_API_PREFIX}/fs_journal/stats")
    }
    
    # Test journal operations
    journal_entry = {
        "operation": "test_operation",
        "path": "/test/path",
        "data": {"test_key": "test_value"},
        "timestamp": time.time()
    }
    
    results["add_entry"] = make_request(
        "POST",
        f"{MCP_API_PREFIX}/fs_journal/add",
        json=journal_entry
    )
    
    return results

def run_all_tests():
    """Run tests for all controllers and report results."""
    all_results = {
        "core": test_core_endpoints(),
        "ipfs": test_ipfs_controller(),
        "cli": test_cli_controller(),
        "credentials": test_credential_controller(),
        "distributed": test_distributed_controller(),
        "webrtc": test_webrtc_controller(),
        "fs_journal": test_fs_journal_controller(),
        "timestamp": time.time()
    }
    
    # Count successful endpoints
    success_count = 0
    total_count = 0
    
    def count_successes(results):
        nonlocal success_count, total_count
        if isinstance(results, dict):
            for k, v in results.items():
                if k == "success":
                    total_count += 1
                    if v:
                        success_count += 1
                elif isinstance(v, (dict, list)):
                    count_successes(v)
        elif isinstance(results, list):
            for item in results:
                count_successes(item)
    
    count_successes(all_results)
    all_results["success_rate"] = {
        "successful": success_count,
        "total": total_count,
        "percentage": round(success_count / max(total_count, 1) * 100, 2)
    }
    
    return all_results

def generate_report(results):
    """Generate a human-readable report from the test results."""
    report = "# MCP Server Test Report\n\n"
    report += f"Test run completed at: {time.ctime()}\n\n"
    
    report += "## Success Rate\n\n"
    rate = results["success_rate"]
    report += f"* Successful endpoints: {rate['successful']} / {rate['total']} ({rate['percentage']}%)\n\n"
    
    report += "## Core Functionality\n\n"
    core = results["core"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in core.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    report += "\n## IPFS Controller\n\n"
    ipfs = results["ipfs"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in ipfs.get("endpoints", {}).items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    report += "\n## CLI Controller\n\n"
    cli = results["cli"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in cli.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    report += "\n## Credentials Controller\n\n"
    creds = results["credentials"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in creds.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    report += "\n## Distributed Controller\n\n"
    dist = results["distributed"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in dist.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    report += "\n## WebRTC Controller\n\n"
    webrtc = results["webrtc"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in webrtc.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    report += "\n## Filesystem Journal Controller\n\n"
    fs_journal = results["fs_journal"]
    report += "| Endpoint | Status |\n|----------|--------|\n"
    for name, result in fs_journal.items():
        if isinstance(result, dict) and "success" in result:
            status = "✅ Working" if result["success"] else f"❌ Failed ({result.get('status_code', 'unknown')})"
            report += f"| {name} | {status} |\n"
    
    return report

if __name__ == "__main__":
    print("Starting comprehensive MCP server tests...")
    results = run_all_tests()
    
    # Save raw JSON results
    with open("mcp_comprehensive_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Generate and save human-readable report
    report = generate_report(results)
    with open("MCP_COMPREHENSIVE_TEST_REPORT.md", "w") as f:
        f.write(report)
    
    print("\nTest Summary:")
    rate = results["success_rate"]
    print(f"Successful endpoints: {rate['successful']} / {rate['total']} ({rate['percentage']}%)")
    print("\nDetailed results saved to:")
    print("- mcp_comprehensive_test_results.json (raw data)")
    print("- MCP_COMPREHENSIVE_TEST_REPORT.md (human-readable report)")