#!/usr/bin/env python3
"""
Final Validation Script

This script performs comprehensive validation of the IPFS Kit MCP Server
implementation, including server startup, tool registration, and functionality.
"""

import os
import sys
import json
import time
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# Add the current directory to the path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configuration
SERVER_HOST = "localhost"
SERVER_PORT = 9998
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEALTH_URL = f"{SERVER_URL}/health"
JSONRPC_URL = f"{SERVER_URL}/jsonrpc"
LOG_FILE = "final_validation.log"

def log_message(message, level="INFO"):
    """Log a message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")

def check_server_startup():
    """Check if the server starts up successfully."""
    log_message("🚀 Validation 1: Server Startup")
    
    # Check if server is already running
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            log_message("✅ Server is already running", "SUCCESS")
            return True
    except requests.exceptions.RequestException:
        pass
    
    # Start the server
    log_message("Starting MCP server...")
    try:
        # Use subprocess to start the server in background
        server_process = subprocess.Popen([
            sys.executable, "final_mcp_server.py",
            "--port", str(SERVER_PORT),
            "--host", SERVER_HOST
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        max_wait = 30
        for i in range(max_wait):
            try:
                response = requests.get(HEALTH_URL, timeout=2)
                if response.status_code == 200:
                    log_message("✅ Server started successfully", "SUCCESS")
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
            
        log_message("❌ Server failed to start within timeout", "ERROR")
        return False
        
    except Exception as e:
        log_message(f"❌ Failed to start server: {e}", "ERROR")
        return False

def check_health_endpoint():
    """Check if the health endpoint is accessible."""
    log_message("🏥 Validation 2: Health Endpoint")
    
    try:
        response = requests.get(HEALTH_URL, timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            log_message(f"✅ Health endpoint accessible: {health_data}", "SUCCESS")
            return True
        else:
            log_message(f"❌ Health endpoint returned status {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log_message(f"❌ Health endpoint check failed: {e}", "ERROR")
        return False

def check_tool_registration():
    """Check if IPFS tools are properly registered."""
    log_message("🛠️  Validation 3: Tool Registration")
    
    try:
        # Test JSON-RPC call to list available tools
        jsonrpc_payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": 1
        }
        
        response = requests.post(
            JSONRPC_URL,
            json=jsonrpc_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                tools = result["result"]
                tool_count = len(tools) if isinstance(tools, list) else len(tools) if isinstance(tools, dict) else 0
                log_message(f"✅ {tool_count} tools registered", "SUCCESS")
                
                # Check for key IPFS tools
                expected_tools = [
                    "ipfs_add", "ipfs_cat", "ipfs_version",
                    "ipfs_pin", "ipfs_unpin", "ipfs_list_pins"
                ]
                
                found_tools = []
                if isinstance(tools, list):
                    tool_names = [tool.get('name', '') for tool in tools if isinstance(tool, dict)]
                elif isinstance(tools, dict):
                    tool_names = list(tools.keys())
                else:
                    tool_names = []
                
                for tool in expected_tools:
                    if tool in tool_names:
                        found_tools.append(tool)
                
                log_message(f"✅ Found {len(found_tools)}/{len(expected_tools)} expected IPFS tools", "SUCCESS")
                return True
            else:
                log_message("❌ No tools result in response", "ERROR")
                return False
        else:
            log_message(f"❌ Tool registration check failed with status {response.status_code}", "ERROR")
            return False
            
    except Exception as e:
        log_message(f"❌ Tool registration check failed: {e}", "ERROR")
        return False

def check_tool_execution():
    """Check if IPFS tools can be executed."""
    log_message("⚙️  Validation 4: Tool Execution")
    
    try:
        # Test executing the ipfs_version tool
        jsonrpc_payload = {
            "jsonrpc": "2.0",
            "method": "execute_tool",
            "params": {
                "tool_name": "ipfs_version",
                "arguments": {}
            },
            "id": 2
        }
        
        response = requests.post(
            JSONRPC_URL,
            json=jsonrpc_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                tool_result = result["result"]
                log_message(f"✅ Tool execution successful: {tool_result}", "SUCCESS")
                
                # Test ipfs_add tool
                add_payload = {
                    "jsonrpc": "2.0",
                    "method": "execute_tool",
                    "params": {
                        "tool_name": "ipfs_add",
                        "arguments": {"content": "Test validation content"}
                    },
                    "id": 3
                }
                
                add_response = requests.post(
                    JSONRPC_URL,
                    json=add_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if add_response.status_code == 200:
                    add_result = add_response.json()
                    if "result" in add_result:
                        log_message(f"✅ IPFS add tool working: {add_result['result']}", "SUCCESS")
                        return True
                    else:
                        log_message("❌ IPFS add tool failed", "ERROR")
                        return False
                else:
                    log_message(f"❌ IPFS add tool request failed with status {add_response.status_code}", "ERROR")
                    return False
            else:
                log_message("❌ Tool execution failed - no result", "ERROR")
                return False
        else:
            log_message(f"❌ Tool execution failed with status {response.status_code}", "ERROR")
            return False
            
    except Exception as e:
        log_message(f"❌ Tool execution check failed: {e}", "ERROR")
        return False

def run_validation():
    """Run complete validation suite."""
    log_message("🎯 Starting Final Validation Suite")
    log_message("=" * 60)
    
    # Clear previous log
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    # Run validations
    validations = [
        ("Server Startup", check_server_startup),
        ("Health Endpoint", check_health_endpoint),
        ("Tool Registration", check_tool_registration),
        ("Tool Execution", check_tool_execution)
    ]
    
    passed = 0
    total = len(validations)
    
    for name, validation_func in validations:
        if validation_func():
            passed += 1
    
    # Print final summary
    log_message("=" * 60)
    log_message("📊 Final Validation Summary")
    log_message("=" * 60)
    log_message(f"Validations passed: {passed}/{total}")
    
    success_rate = (passed / total) * 100
    log_message(f"Success rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        log_message("🎉 ALL VALIDATIONS PASSED! Implementation is complete and working.", "SUCCESS")
    elif success_rate >= 75:
        log_message("✅ Most validations passed. Implementation is functional.", "SUCCESS")
    else:
        log_message("⚠️  Many validations failed. Review implementation.", "ERROR")
    
    log_message("=" * 60)
    return success_rate >= 75

if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
