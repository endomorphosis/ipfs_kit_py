#!/usr/bin/env python3
"""
Check VS Code Extension Settings and MCP Integration

This tool verifies VS Code settings and checks if the current setup
matches what the extensions expect for MCP integration.
"""

import os
import json
import sys
import requests
import time

def check_vscode_settings():
    """Check VS Code settings for MCP integration."""
    print("Checking VS Code settings...")

    # Try to find VS Code settings file in common locations
    possible_locations = [
        os.path.expanduser("~/.config/Code - Insiders/User/settings.json"),
        os.path.expanduser("~/.config/Code/User/settings.json"),
        os.path.expanduser("~/Library/Application Support/Code - Insiders/User/settings.json"),
        os.path.expanduser("~/Library/Application Support/Code/User/settings.json"),
        os.path.expanduser("%APPDATA%/Code - Insiders/User/settings.json"),
        os.path.expanduser("%APPDATA%/Code/User/settings.json")
    ]

    settings_file = None
    for loc in possible_locations:
        if os.path.exists(loc):
            settings_file = loc
            break

    if not settings_file:
        print("❌ Could not find VS Code settings file")
        return False

    print(f"Found VS Code settings file: {settings_file}")

    # Read settings file
    try:
        with open(settings_file, 'r') as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                print("❌ VS Code settings file is not valid JSON")
                return False
    except Exception as e:
        print(f"❌ Error reading VS Code settings file: {e}")
        return False

    # Check MCP settings
    mcp_settings = settings.get("mcp", {}).get("servers", {})
    if not mcp_settings:
        print("❌ No MCP server settings found in VS Code settings")
        return False

    print(f"Found MCP server settings: {json.dumps(mcp_settings, indent=2)}")

    # Check for server entry with SSE URL
    sse_urls = []
    for server_id, server in mcp_settings.items():
        if "url" in server:
            sse_urls.append(server["url"])

    if not sse_urls:
        print("❌ No SSE URL found in MCP server settings")
        return False

    print(f"Found SSE URLs: {sse_urls}")

    # Check LSP endpoint settings
    lsp_settings = settings.get("localStorageNetworkingTools", {}).get("lspEndpoint", {})
    if not lsp_settings:
        print("❌ No LSP endpoint settings found in VS Code settings")
        return False

    lsp_url = lsp_settings.get("url")
    if not lsp_url:
        print("❌ No LSP URL found in LSP endpoint settings")
        return False

    print(f"Found LSP URL: {lsp_url}")

    # Verify MCP server is running
    for sse_url in sse_urls:
        print(f"\nChecking SSE endpoint: {sse_url}")
        try:
            response = requests.get(sse_url, stream=True, timeout=5)
            if response.status_code == 200:
                print(f"✅ SSE endpoint {sse_url} is accessible")
            else:
                print(f"❌ SSE endpoint {sse_url} returned status code {response.status_code}")
        except Exception as e:
            print(f"❌ Error connecting to SSE endpoint {sse_url}: {e}")

    # Verify JSON-RPC server is running
    print(f"\nChecking LSP endpoint: {lsp_url}")
    try:
        # First check if we can reach the server
        base_url = lsp_url.rsplit('/', 1)[0]
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print(f"✅ LSP server base URL {base_url} is accessible")
        else:
            print(f"❌ LSP server base URL {base_url} returned status code {response.status_code}")

        # Try initialize request
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": 12345,
                "rootUri": None,
                "capabilities": {}
            }
        }

        response = requests.post(
            lsp_url,
            headers={"Content-Type": "application/json"},
            json=initialize_payload,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if "result" in result and "capabilities" in result["result"]:
                print(f"✅ LSP endpoint {lsp_url} responded correctly to initialize request")
                print(f"Server capabilities: {json.dumps(result['result']['capabilities'], indent=2)}")
            else:
                print(f"❌ LSP endpoint {lsp_url} response doesn't contain expected capabilities")
                print(f"Response: {json.dumps(result, indent=2)}")
        else:
            print(f"❌ LSP endpoint {lsp_url} returned status code {response.status_code}")
    except Exception as e:
        print(f"❌ Error connecting to LSP endpoint {lsp_url}: {e}")

    print("\n=== VS Code Extension Installation Check ===")
    # Check if the required extensions are installed
    vscode_extensions_dir = os.path.expanduser("~/.vscode/extensions")
    vscode_insiders_extensions_dir = os.path.expanduser("~/.vscode-insiders/extensions")

    mcp_extensions = [
        "storage-networking-tools",
        "mcp-tools",
        "ipfs-tools"
    ]

    for ext_dir in [vscode_extensions_dir, vscode_insiders_extensions_dir]:
        if os.path.exists(ext_dir):
            print(f"\nChecking extensions in {ext_dir}")
            extensions = os.listdir(ext_dir)
            for mcp_ext in mcp_extensions:
                found = False
                for ext in extensions:
                    if mcp_ext.lower() in ext.lower():
                        print(f"✅ Found extension matching '{mcp_ext}': {ext}")
                        found = True
                if not found:
                    print(f"❌ Could not find extension matching '{mcp_ext}'")

    print("\n=== Summary ===")
    print("The debug check is complete.")
    print("If VS Code is still not connecting to the MCP server, try the following:")
    print("1. Restart VS Code")
    print("2. Make sure you have the latest version of the MCP extensions")
    print("3. Check VS Code network settings (proxy, etc.)")
    print("4. Check if there are any error messages in the VS Code Developer Console")
    print("   (Help > Toggle Developer Tools)")

    return True

def main():
    """Main function."""
    print("=== VS Code MCP Integration Check ===\n")
    check_vscode_settings()
    return 0

if __name__ == "__main__":
    sys.exit(main())
