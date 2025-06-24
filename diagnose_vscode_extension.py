#!/usr/bin/env python3
"""
VS Code Extension Integration Tester

This script tests the specific VS Code extensions that integrate with the MCP server.
It performs deeper diagnostics to identify issues with the Extensions themselves.
"""

import os
import sys
import json
import subprocess
import time
import requests

def check_vscode_extensions():
    """Check if the required VS Code extensions are installed."""
    print("Checking for required VS Code extensions...")

    # Run the VS Code command to list extensions
    result = subprocess.run(
        "code --list-extensions",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Error running VS Code extension command: {result.stderr}")
        return False

    # Get the list of installed extensions
    extensions = result.stdout.strip().split('\n')
    print(f"Found {len(extensions)} installed extensions")

    # Look for extensions related to MCP/IPFS/Storage
    mcp_extensions = []
    for extension in extensions:
        if any(keyword in extension.lower() for keyword in ['mcp', 'ipfs', 'storage', 'network']):
            mcp_extensions.append(extension)

    if mcp_extensions:
        print(f"Found {len(mcp_extensions)} extensions related to MCP/IPFS/Storage:")
        for ext in mcp_extensions:
            print(f"  - {ext}")
        return True
    else:
        print("❌ No extensions related to MCP/IPFS/Storage were found.")
        print("You may need to install the required extensions.")
        return False

def get_vscode_settings():
    """Get the VS Code settings."""
    print("Checking VS Code settings for MCP configuration...")

    settings_paths = [
        os.path.expanduser("~/.config/Code/User/settings.json"),
        os.path.expanduser("~/.config/Code - Insiders/User/settings.json")
    ]

    for path in settings_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    settings = json.load(f)

                mcp_settings = settings.get('mcp', {})
                jsonrpc_settings = settings.get('localStorageNetworkingTools', {}).get('lspEndpoint', {})

                print(f"Found settings in: {path}")
                print("MCP settings:")
                print(json.dumps(mcp_settings, indent=2))
                print("\nJSON-RPC settings:")
                print(json.dumps(jsonrpc_settings, indent=2))

                return settings, path
            except Exception as e:
                print(f"❌ Error reading VS Code settings: {e}")

    print("❌ Could not find VS Code settings.")
    return None, None

def check_extension_logs():
    """Check for extension logs that might indicate issues."""
    print("\nChecking VS Code extension logs...")

    log_paths = [
        os.path.expanduser("~/.config/Code/logs"),
        os.path.expanduser("~/.config/Code - Insiders/logs")
    ]

    for base_path in log_paths:
        if os.path.exists(base_path):
            print(f"Looking for logs in: {base_path}")

            # Find the most recent log files
            log_files = []
            for root, _, files in os.walk(base_path):
                for file in files:
                    if file.endswith('.log'):
                        full_path = os.path.join(root, file)
                        log_files.append((full_path, os.path.getmtime(full_path)))

            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x[1], reverse=True)

            # Check the 5 most recent log files
            found_errors = False
            for path, _ in log_files[:5]:
                print(f"Checking log file: {os.path.basename(path)}")

                try:
                    # Look for MCP or JSON-RPC related errors
                    grep_result = subprocess.run(
                        f"grep -i 'mcp\\|jsonrpc\\|initialize\\|network\\|connection\\|error' {path} | tail -50",
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    if grep_result.stdout.strip():
                        print("Found potentially relevant log entries:")
                        print("-" * 50)
                        print(grep_result.stdout.strip())
                        print("-" * 50)
                        found_errors = True
                except Exception as e:
                    print(f"❌ Error searching log file: {e}")

            if not found_errors:
                print("No relevant log entries found.")

            return True

    print("❌ Could not find any VS Code log directories.")
    return False

def test_jsonrpc_connection():
    """Test the JSON-RPC connection with more specific error diagnostics."""
    print("\nTesting JSON-RPC connection with enhanced diagnostics...")

    url = "http://localhost:9995/jsonrpc"
    headers = {
        "Content-Type": "application/json",
    }

    # Try different initialization payloads
    payloads = [
        # Standard lightweight initialize request
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": 12345,
                "rootUri": None,
                "capabilities": {}
            }
        },

        # More comprehensive initialize request
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "processId": 12345,
                "clientInfo": {
                    "name": "Visual Studio Code",
                    "version": "1.82.0"
                },
                "rootPath": None,
                "rootUri": None,
                "capabilities": {
                    "workspace": {
                        "applyEdit": True,
                        "workspaceEdit": {
                            "documentChanges": True
                        }
                    },
                    "textDocument": {
                        "synchronization": {
                            "dynamicRegistration": True,
                            "willSave": True,
                            "willSaveWaitUntil": True,
                            "didSave": True
                        },
                        "completion": {
                            "dynamicRegistration": True,
                            "completionItem": {
                                "snippetSupport": True
                            }
                        }
                    }
                },
                "trace": "off"
            }
        },

        # Simplified initialize request
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "initialize",
            "params": {}
        }
    ]

    for i, payload in enumerate(payloads):
        print(f"\nTrying initialize payload variant {i+1}...")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {response.headers}")

            if response.status_code == 200:
                result = response.json()
                print(f"Response content type: {response.headers.get('Content-Type', 'Not specified')}")
                print("Response body summary:")

                if "result" in result and "capabilities" in result["result"]:
                    print("✅ Server returned capabilities")
                    # Test if capabilities contain expected fields
                    caps = result["result"]["capabilities"]
                    if "textDocumentSync" in caps and "completionProvider" in caps:
                        print("✅ Server capabilities look good")
                    else:
                        print("⚠️ Server capabilities might be incomplete")
                else:
                    print("❌ Server response doesn't contain expected capabilities")
            else:
                print(f"❌ Server returned status code {response.status_code}")
                print(f"Response text: {response.text}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Could not connect to {url}. Is the server running?")
        except requests.exceptions.Timeout:
            print(f"❌ Request to {url} timed out after 10 seconds")
        except Exception as e:
            print(f"❌ An error occurred: {e}")

def test_sse_connection():
    """Test the SSE connection with more specific error diagnostics."""
    print("\nTesting SSE connection with enhanced diagnostics...")

    url = "http://localhost:9994/api/v0/sse"

    try:
        # Use curl for better SSE handling
        process = subprocess.Popen(
            f"curl -N -H 'Accept: text/event-stream' {url}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for a few seconds to get some events
        time.sleep(3)

        # Try to terminate the process gracefully
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)

        if "data:" in stdout:
            print("✅ SSE endpoint returned events:")
            events = [line for line in stdout.splitlines() if line.strip()]
            for event in events[:3]:  # Show just the first few events
                print(f"  {event}")
            print(f"  ... ({len(events)} events total)")
            return True
        else:
            print("❌ No events received from SSE endpoint")
            if stderr:
                print(f"Error: {stderr}")
            return False

    except subprocess.TimeoutExpired:
        process.kill()
        print("✅ SSE endpoint is streaming (had to forcefully terminate curl)")
        return True
    except Exception as e:
        print(f"❌ An error occurred while testing SSE endpoint: {e}")
        return False

def suggest_fixes(settings_path):
    """Suggest fixes based on diagnostic results."""
    print("\n=== Suggested Fixes ===")

    # Check if servers are running
    mcp_running = subprocess.run(
        "curl -s http://localhost:9994/ > /dev/null",
        shell=True,
        check=False
    ).returncode == 0

    jsonrpc_running = subprocess.run(
        "curl -s http://localhost:9995/ > /dev/null",
        shell=True,
        check=False
    ).returncode == 0

    if not mcp_running or not jsonrpc_running:
        print("1. One or both servers are not running. Run:")
        print("   ./start_mcp_stack.sh")

    # Suggest VS Code settings update
    if settings_path:
        print(f"2. Update your VS Code settings at {settings_path}:")
        print("""
   Make sure these settings are correctly added:

   "mcp": {
     "servers": {
       "my-mcp-server": {
         "url": "http://localhost:9994/api/v0/sse"
       }
     }
   },
   "localStorageNetworkingTools": {
     "lspEndpoint": {
       "url": "http://localhost:9995/jsonrpc"
     }
   }
   """)

    # Suggest VS Code reload
    print("3. Reload VS Code:")
    print("   - Press F1, type 'Reload Window', and press Enter")
    print("   - Or close and reopen VS Code")

    # Suggest checking extensions
    print("4. Check if the MCP/IPFS extensions are properly installed:")
    print("   - Open Extensions view (Ctrl+Shift+X)")
    print("   - Search for 'IPFS' or 'MCP'")
    print("   - Make sure they're installed and enabled")

    # Suggest DNS/network checks
    print("5. Check for network/DNS issues:")
    print("   - Make sure 'localhost' resolves correctly")
    print("   - Try using '127.0.0.1' instead of 'localhost' in settings")

def main():
    """Main entry point."""
    print("=== VS Code Extension Integration Tester ===\n")

    check_vscode_extensions()
    settings, settings_path = get_vscode_settings()
    check_extension_logs()
    test_jsonrpc_connection()
    test_sse_connection()
    suggest_fixes(settings_path)

    print("\nDiagnostic completed. Please review the output above for issues.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
