#!/usr/bin/env python3
"""
Solution Verification Tool

This script verifies that the enhanced MCP solution is working correctly by:
1. Testing the parameter handling fix
2. Testing the import fix
3. Verifying that the server can start and run properly
4. Running comprehensive tests on all tools
"""

import os
import sys
import json
import time
import signal
import logging
import importlib
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("solution_verification.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("solution-verification")

# Configuration
PORT = 9998
HOST = "localhost"
REQUIRED_FILES = [
    "fixed_ipfs_param_handling.py",
    "run_enhanced_mcp_server.py",
    "enhanced_diagnostics.py",
    "mcp_test_suite.py",
    "run_enhanced_solution.sh",
    "ENHANCED_SOLUTION.md"
]
REPORT_DIR = "verification_results"
REPORT_FILE = f"{REPORT_DIR}/verification_{int(time.time())}.md"
JSON_RPC_ENDPOINT = f"http://{HOST}:{PORT}/jsonrpc"

# Ensure report directory exists
Path(REPORT_DIR).mkdir(exist_ok=True)

def print_section_header(title):
    """Print a section header for better visibility."""
    logger.info("\n" + "="*80)
    logger.info(f" {title}")
    logger.info("="*80)

def verify_required_files():
    """Verify that all required files for the solution exist."""
    print_section_header("Verifying Required Files")
    
    results = {}
    success = True
    
    for file in REQUIRED_FILES:
        if os.path.exists(file):
            logger.info(f"✅ {file} exists")
            results[file] = True
        else:
            logger.error(f"❌ {file} does not exist")
            results[file] = False
            success = False
    
    return success, results

def test_parameter_handling():
    """Test the parameter handling fix."""
    print_section_header("Testing Parameter Handling Fix")
    
    try:
        # Import the parameter handling module
        param_handler = importlib.import_module("fixed_ipfs_param_handling")
        
        # Test cases for various IPFS tools
        test_cases = [
            {"tool": "ipfs_add", "params": {"content": "Hello IPFS!"}},
            {"tool": "ipfs_add", "params": {"content": "Test with filename", "filename": "test.txt"}},
            {"tool": "ipfs_add", "params": {"content": "Test with only_hash", "only_hash": "true"}},
            {"tool": "ipfs_add", "params": {"content": "Test with wrap_dir", "wrap_with_directory": True}},
            {"tool": "ipfs_files_ls", "params": {"path": "/"}},
            {"tool": "ipfs_cat", "params": {"hash": "QmTest", "offset": "10", "length": "100"}}
        ]
        
        results = {}
        success = True
        
        for test in test_cases:
            tool = test["tool"]
            params = test["params"]
            test_id = f"{tool}_{params.get('filename', '')}"
            
            try:
                logger.info(f"Testing {tool} with params: {params}")
                fixed_params = param_handler.IPFSParamHandler.validate_params(tool, params)
                logger.info(f"Fixed params: {fixed_params}")
                logger.info("✅ Test passed")
                results[test_id] = {"success": True, "params": params, "fixed_params": fixed_params}
            except Exception as e:
                logger.error(f"❌ Test failed: {e}")
                results[test_id] = {"success": False, "params": params, "error": str(e)}
                success = False
        
        return success, results
    except ImportError as e:
        logger.error(f"❌ Could not import fixed_ipfs_param_handling: {e}")
        return False, {"import_error": str(e)}
    except Exception as e:
        logger.error(f"❌ Error testing parameter handling: {e}")
        return False, {"error": str(e)}

def test_import_fix():
    """Test the import fix for hanging issues."""
    print_section_header("Testing Import Fix")
    
    modules = [
        "unified_ipfs_tools",
        "final_mcp_server",
        "fixed_ipfs_param_handling",
        "run_enhanced_mcp_server",
        "enhanced_diagnostics"
    ]
    
    results = {}
    success = True
    
    for module in modules:
        try:
            logger.info(f"Testing import of {module}...")
            # Use subprocess to prevent hanging in the current process
            cmd = [sys.executable, "-c", f"import {module}; print('{module} imported successfully')"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"✅ {module} imported successfully")
                results[module] = {"success": True, "output": result.stdout.strip()}
            else:
                logger.error(f"❌ {module} import failed: {result.stderr.strip()}")
                results[module] = {"success": False, "error": result.stderr.strip()}
                success = False
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {module} import timed out (possibly hanging)")
            results[module] = {"success": False, "error": "Import timed out (possibly hanging)"}
            success = False
        except Exception as e:
            logger.error(f"❌ Error testing import of {module}: {e}")
            results[module] = {"success": False, "error": str(e)}
            success = False
    
    return success, results

def start_server():
    """Start the server using the enhanced runner."""
    print_section_header("Starting Server")
    
    try:
        # Use subprocess to run the enhanced server
        cmd = [
            sys.executable, 
            "run_enhanced_mcp_server.py",
            "--module", "final_mcp_server",
            "--host", HOST,
            "--port", str(PORT),
            "--debug"
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Wait for server to start (check PID file creation)
        pid_file = "enhanced_mcp_server.pid"
        pid = None
        
        for _ in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            
            # Check if PID file was created
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                logger.info(f"Server started with PID {pid}")
                break
        
        if pid is None:
            logger.error("Server did not create PID file within timeout")
            output = process.stdout.read() if process else "No output available"
            logger.error(f"Server output: {output}")
            return None
        
        # Wait for server to respond to health checks
        for _ in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            try:
                response = requests.get(f"http://{HOST}:{PORT}/health", timeout=1)
                if response.status_code == 200:
                    logger.info("Server is responding to health checks")
                    return pid
            except Exception:
                pass
        
        logger.error("Server did not respond to health checks within timeout")
        return pid
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return None

def stop_server(pid):
    """Stop the server."""
    print_section_header("Stopping Server")
    
    if pid is None:
        logger.warning("No PID provided, cannot stop server")
        return
    
    try:
        logger.info(f"Stopping server with PID {pid}")
        os.kill(pid, signal.SIGTERM)
        
        # Wait for server to stop
        for _ in range(10):  # Wait up to 10 seconds
            time.sleep(1)
            try:
                os.kill(pid, 0)  # Check if process exists
            except OSError:
                logger.info("Server stopped")
                return True
        
        # If server is still running, force kill
        logger.warning("Server did not stop gracefully, force killing")
        os.kill(pid, signal.SIGKILL)
        return True
    except Exception as e:
        logger.error(f"Error stopping server: {e}")
        return False

def test_server_functionality():
    """Test server functionality by calling basic tools."""
    print_section_header("Testing Server Functionality")
    
    test_calls = [
        {"method": "ping", "params": {}, "expected": "pong"},
        {"method": "ipfs_version", "params": {}, "expected": "version"},
        {"method": "ipfs_add", "params": {"content": "Test content"}, "expected": "hash"},
        {"method": "ipfs_add", "params": {"content": "Test with filename", "filename": "test.txt"}, "expected": "hash"},
        {"method": "ipfs_add", "params": {"content": "Test with only_hash", "only_hash": True}, "expected": "hash"}
    ]
    
    results = {}
    success = True
    
    for test in test_calls:
        method = test["method"]
        params = test["params"]
        expected = test["expected"]
        
        try:
            logger.info(f"Testing {method} with params: {params}")
            
            # Make JSON-RPC call
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": int(time.time())
            }
            
            response = requests.post(
                JSON_RPC_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Response: {json.dumps(result, indent=2)}")
                
                if "result" in result and expected in str(result):
                    logger.info(f"✅ {method} test passed")
                    results[method] = {"success": True, "params": params, "result": result}
                else:
                    logger.error(f"❌ {method} test failed - unexpected response")
                    results[method] = {"success": False, "params": params, "result": result, "expected": expected}
                    success = False
            else:
                logger.error(f"❌ {method} test failed - status code {response.status_code}")
                results[method] = {"success": False, "params": params, "status_code": response.status_code}
                success = False
        except Exception as e:
            logger.error(f"❌ Error testing {method}: {e}")
            results[method] = {"success": False, "params": params, "error": str(e)}
            success = False
    
    return success, results

def generate_verification_report(all_results):
    """Generate a comprehensive verification report."""
    print_section_header("Generating Verification Report")
    
    # Calculate overall result
    overall_success = all(success for section, (success, _) in all_results.items())
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Start markdown content
    md = f"""# Enhanced IPFS MCP Solution Verification Report

Generated: {timestamp}

## Summary

Overall Status: {"✅ PASSED" if overall_success else "❌ FAILED"}

| Component | Status |
|-----------|--------|
"""
    
    for section, (success, _) in all_results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        md += f"| {section} | {status} |\n"
    
    # Add detailed results
    md += "\n## Detailed Results\n\n"
    
    # Required Files
    _, file_results = all_results["Required Files"]
    md += "### Required Files\n\n"
    md += "| File | Status |\n"
    md += "|------|--------|\n"
    for file, exists in file_results.items():
        status = "✅ Exists" if exists else "❌ Missing"
        md += f"| `{file}` | {status} |\n"
    
    # Parameter Handling
    _, param_results = all_results["Parameter Handling"]
    md += "\n### Parameter Handling Tests\n\n"
    
    if "import_error" in param_results:
        md += f"❌ Import Error: {param_results['import_error']}\n\n"
    elif "error" in param_results:
        md += f"❌ Error: {param_results['error']}\n\n"
    else:
        md += "| Test | Original Parameters | Fixed Parameters | Status |\n"
        md += "|------|---------------------|-----------------|--------|\n"
        for test_id, result in param_results.items():
            if result.get("success", False):
                status = "✅ Passed"
                orig_params = json.dumps(result.get("params", {}))
                fixed_params = json.dumps(result.get("fixed_params", {}))
                md += f"| `{test_id}` | `{orig_params}` | `{fixed_params}` | {status} |\n"
            else:
                status = "❌ Failed"
                error = result.get("error", "Unknown error")
                md += f"| `{test_id}` | `{json.dumps(result.get('params', {}))}` | Error | {status}: {error} |\n"
    
    # Import Fix
    _, import_results = all_results["Import Fix"]
    md += "\n### Import Fix Tests\n\n"
    md += "| Module | Status | Details |\n"
    md += "|--------|--------|--------|\n"
    for module, result in import_results.items():
        if result.get("success", False):
            status = "✅ Passed"
            details = result.get("output", "")
        else:
            status = "❌ Failed"
            details = result.get("error", "Unknown error")
        md += f"| `{module}` | {status} | {details} |\n"
    
    # Server Functionality
    if "Server Functionality" in all_results:
        _, func_results = all_results["Server Functionality"]
        md += "\n### Server Functionality Tests\n\n"
        md += "| Method | Parameters | Status | Details |\n"
        md += "|--------|------------|--------|--------|\n"
        for method, result in func_results.items():
            if result.get("success", False):
                status = "✅ Passed"
                details = result.get("result", {}).get("result", "")
                if isinstance(details, dict):
                    details = f"Hash: {details.get('hash', 'N/A')}" if "hash" in details else str(details)[:50]
            else:
                status = "❌ Failed"
                if "error" in result:
                    details = result["error"]
                elif "status_code" in result:
                    details = f"HTTP {result['status_code']}"
                else:
                    details = "Unexpected response"
            md += f"| `{method}` | `{json.dumps(result.get('params', {}))}` | {status} | {details} |\n"
    
    # Write report to file
    with open(REPORT_FILE, "w") as f:
        f.write(md)
    
    logger.info(f"Verification report written to {REPORT_FILE}")
    
    # Print summary
    logger.info(f"Verification {'PASSED' if overall_success else 'FAILED'}")
    return overall_success

def main():
    """Main function."""
    print_section_header("IPFS MCP Solution Verification")
    
    # Store all results
    all_results = {}
    
    # Verify required files
    success, results = verify_required_files()
    all_results["Required Files"] = (success, results)
    
    # Test parameter handling
    success, results = test_parameter_handling()
    all_results["Parameter Handling"] = (success, results)
    
    # Test import fix
    success, results = test_import_fix()
    all_results["Import Fix"] = (success, results)
    
    # Start server and test functionality
    server_pid = start_server()
    if server_pid:
        try:
            # Test server functionality
            success, results = test_server_functionality()
            all_results["Server Functionality"] = (success, results)
        finally:
            # Stop server
            stop_server(server_pid)
    else:
        logger.error("Could not start server, skipping functionality tests")
        all_results["Server Functionality"] = (False, {"error": "Could not start server"})
    
    # Generate verification report
    overall_success = generate_verification_report(all_results)
    
    return 0 if overall_success else 1

if __name__ == "__main__":
    sys.exit(main())
