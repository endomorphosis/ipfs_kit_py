#!/usr/bin/env python3
"""
Enhanced JSON-RPC Test Script for MCP Server

This script performs more comprehensive testing of the JSON-RPC endpoint
with detailed diagnostics to help identify and solve issues.
"""

import sys
import json
import time
import argparse
import requests
from typing import Dict, Any, Optional, List

# Default configuration
DEFAULT_PORT = 9997
DEFAULT_HOST = "localhost"
DEFAULT_TIMEOUT = 10
TESTS = [
    "ping",
    "get_tools",
    "list_tools",
    "get_server_info",
]

class JsonRpcTester:
    def __init__(self, host: str, port: int, verbose: bool = False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.jsonrpc_url = f"http://{host}:{port}/jsonrpc"
        self.success_count = 0
        self.failure_count = 0
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp and level."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}")
        
    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None, 
                    timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """Make a JSON-RPC call to the MCP server with enhanced error logging."""
        if params is None:
            params = {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000) 
        }
        
        self.log(f"Calling {method} with params: {json.dumps(params)}")
        
        response_text = "N/A"
        try:
            # Set a short timeout to avoid hanging
            self.log(f"Sending request to {self.jsonrpc_url} with timeout {timeout}s")
            response = requests.post(self.jsonrpc_url, json=payload, timeout=timeout)
            response_text = response.text
            self.log(f"HTTP Status: {response.status_code}")
            self.log(f"Response: {response_text}")
                
            response.raise_for_status() 
            json_response = response.json()
            
            if "error" in json_response:
                self.log(f"Error in JSON-RPC response for {method}: {json.dumps(json_response.get('error'))}", "ERROR")
                return json_response
                
            if "result" in json_response:
                try:
                    if isinstance(json_response['result'], str):
                        # Try parsing the result if it's a string that looks like JSON
                        if json_response['result'].startswith('{') or json_response['result'].startswith('['):
                            try:
                                parsed_result = json.loads(json_response['result'])
                                self.log(f"Warning: Result is a JSON string, parsed as: {json.dumps(parsed_result)[:200]}", "WARNING")
                                json_response['result'] = parsed_result
                            except json.JSONDecodeError:
                                pass
                    
                    if self.verbose:
                        result_str = str(json_response['result'])
                        self.log(f"Result: {result_str[:200]}{'...' if len(result_str) > 200 else ''}")
                except Exception as e:
                    self.log(f"Error processing result: {e}", "ERROR")
                
            return json_response
            
        except requests.exceptions.HTTPError as http_err:
            self.log(f"HTTP error calling {method}: {http_err}. Response text: {response_text}", "ERROR")
            return {"error": {"message": f"HTTP error: {http_err}", "details": response_text}}
            
        except requests.exceptions.RequestException as req_err: 
            self.log(f"RequestException calling {method}: {req_err}", "ERROR")
            return {"error": {"message": f"RequestException: {req_err}"}}
            
        except json.JSONDecodeError as json_err:
            self.log(f"JSONDecodeError calling {method}: {json_err}. Response text: {response_text}", "ERROR")
            return {"error": {"message": f"JSONDecodeError: {json_err}", "details": response_text}}
            
        except Exception as e: 
            self.log(f"Unexpected error calling {method}: {e}. Response text: {response_text}", "ERROR")
            return {"error": {"message": f"Unexpected error: {e}", "details": response_text}}

    def test_ping(self) -> bool:
        """Test the JSON-RPC ping endpoint."""
        self.log("Testing ping endpoint...")
        response = self.call_jsonrpc("ping")
        
        if "result" in response and response["result"] == "pong":
            self.log("✅ Success: ping endpoint returned 'pong'", "SUCCESS")
            self.success_count += 1
            return True
        else:
            self.log("❌ Failure: ping endpoint did not return 'pong'", "ERROR")
            self.failure_count += 1
            return False

    def test_get_tools(self) -> bool:
        """Test the JSON-RPC get_tools endpoint."""
        self.log("Testing get_tools endpoint...")
        response = self.call_jsonrpc("get_tools")
        
        if "result" in response:
            result = response["result"]
            
            if isinstance(result, dict) and "tools" in result and isinstance(result["tools"], list):
                self.log(f"✅ Success: get_tools returned {len(result['tools'])} tools", "SUCCESS")
                self.success_count += 1
                return True
            elif isinstance(result, list):
                self.log(f"⚠️ Warning: get_tools returned a list directly instead of {'tools': [...]} format", "WARNING")
                self.log(f"✅ Success: get_tools returned {len(result)} tools", "SUCCESS")
                self.success_count += 1
                return True
            else:
                self.log(f"❌ Failure: get_tools returned unexpected format: {type(result)}", "ERROR")
                self.failure_count += 1
                return False
        else:
            self.log("❌ Failure: get_tools endpoint did not return a result", "ERROR")
            self.failure_count += 1
            return False

    def test_list_tools(self) -> bool:
        """Test the JSON-RPC list_tools endpoint."""
        self.log("Testing list_tools endpoint...")
        response = self.call_jsonrpc("list_tools")
        
        if "result" in response:
            result = response["result"]
            
            if isinstance(result, dict) and "tools" in result and isinstance(result["tools"], list):
                self.log(f"✅ Success: list_tools returned {len(result['tools'])} tools", "SUCCESS")
                self.success_count += 1
                return True
            elif isinstance(result, list):
                self.log(f"⚠️ Warning: list_tools returned a list directly instead of {'tools': [...]} format", "WARNING")
                self.log(f"✅ Success: list_tools returned {len(result)} tools", "SUCCESS")
                self.success_count += 1
                return True
            else:
                self.log(f"❌ Failure: list_tools returned unexpected format: {type(result)}", "ERROR")
                self.failure_count += 1
                return False
        else:
            self.log("❌ Failure: list_tools endpoint did not return a result", "ERROR")
            self.failure_count += 1
            return False

    def test_get_server_info(self) -> bool:
        """Test the JSON-RPC get_server_info endpoint."""
        self.log("Testing get_server_info endpoint...")
        response = self.call_jsonrpc("get_server_info")
        
        if "result" in response:
            result = response["result"]
            
            if isinstance(result, dict) and "version" in result:
                self.log(f"✅ Success: get_server_info returned version {result.get('version')}", "SUCCESS")
                self.success_count += 1
                return True
            else:
                self.log(f"❌ Failure: get_server_info returned unexpected format", "ERROR")
                self.failure_count += 1
                return False
        else:
            self.log("❌ Failure: get_server_info endpoint did not return a result", "ERROR")
            self.failure_count += 1
            return False

    def run_test(self, test_name: str) -> bool:
        """Run a specific test by name."""
        test_method = getattr(self, f"test_{test_name}", None)
        if test_method is None:
            self.log(f"❌ Test '{test_name}' is not implemented", "ERROR")
            self.failure_count += 1
            return False
            
        return test_method()

    def run_all_tests(self, tests: Optional[List[str]] = None) -> bool:
        """Run all tests or a specified list of tests."""
        if tests is None:
            tests = TESTS
            
        self.log(f"Starting JSON-RPC tests against {self.host}:{self.port}")
        
        for test in tests:
            self.run_test(test)
            
        self.log(f"Test summary: {self.success_count} passed, {self.failure_count} failed")
        return self.failure_count == 0

def check_server_health(host, port, max_retries=5, retry_interval=3):
    """Check if the MCP server is healthy and running."""
    health_url = f"http://{host}:{port}/health"
    
    print(f"Checking server health at {health_url}...")
    
    for i in range(max_retries):
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Server is healthy. Response: {response.text[:100]}")
                return True
        except requests.RequestException as e:
            print(f"⚠️ Server health check attempt {i+1}/{max_retries} failed: {str(e)}")
        
        if i < max_retries - 1:
            print(f"Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
    
    print("❌ Server health check failed after all retries.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Enhanced JSON-RPC Test Script for MCP Server")
    parser.add_argument("port", type=int, nargs="?", default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"Host (default: {DEFAULT_HOST})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--tests", type=str, nargs="+", choices=TESTS, help="Specific tests to run")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip initial server health check")
    
    args = parser.parse_args()
    
    # Check if server is healthy before running tests
    if not args.skip_health_check:
        if not check_server_health(args.host, args.port):
            print("Skipping tests since server isn't healthy.")
            sys.exit(1)
    
    tester = JsonRpcTester(host=args.host, port=args.port, verbose=args.verbose)
    success = tester.run_all_tests(args.tests)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
