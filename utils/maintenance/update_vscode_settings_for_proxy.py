#!/usr/bin/env python3
"""
Update VS Code settings for MCP proxy integration

This script updates VS Code settings to point to our MCP proxy server
instead of directly to the MCP server.
"""

import os
import json
import sys

# Configuration
PROXY_PORT = 9996
PROXY_URL = f"http://localhost:{PROXY_PORT}"

def update_vscode_settings():
    """Update VS Code settings to use the MCP proxy server."""
    vscode_settings_paths = [
        os.path.expanduser("~/.config/Code - Insiders/User/settings.json"),
        os.path.expanduser("~/.config/Code/User/settings.json")
    ]

    updated_files = []

    for settings_path in vscode_settings_paths:
        if not os.path.exists(settings_path):
            print(f"❌ VS Code settings not found at {settings_path}")
            continue

        try:
            # Create backup
            backup_path = f"{settings_path}.bak.mcp"
            if not os.path.exists(backup_path):
                with open(settings_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
                print(f"✅ Created backup at {backup_path}")

            # Read current settings
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            # Update MCP server URL to use proxy
            if "mcp" in settings and "servers" in settings["mcp"]:
                for server_id, server in settings["mcp"]["servers"].items():
                    if "url" in server and "localhost" in server["url"] and "/api/v0/sse" in server["url"]:
                        old_url = server["url"]
                        server["url"] = f"{PROXY_URL}/api/v0/sse"
                        print(f"✅ Updated MCP server URL from {old_url} to {server['url']}")

            # Write updated settings back to file
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            print(f"✅ Successfully updated settings in {settings_path}")
            updated_files.append(settings_path)

        except Exception as e:
            print(f"❌ Error updating settings in {settings_path}: {e}")

    return len(updated_files) > 0

def update_claude_mcp_settings():
    """Update Claude-specific MCP settings if they exist."""
    claude_settings_paths = [
        os.path.expanduser("~/.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
        os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")
    ]

    updated_files = []

    for settings_path in claude_settings_paths:
        if not os.path.exists(settings_path):
            print(f"❌ Claude MCP settings not found at {settings_path}")
            continue

        try:
            # Create backup
            backup_path = f"{settings_path}.bak.mcp"
            if not os.path.exists(backup_path):
                with open(settings_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
                print(f"✅ Created backup at {backup_path}")

            # Read current settings
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            # Update MCP server URLs to use proxy
            if "mcpServers" in settings:
                for server in settings["mcpServers"]:
                    if "url" in server and "localhost" in server["url"]:
                        old_url = server["url"]
                        server["url"] = PROXY_URL
                        server["transportType"] = "http"  # Use HTTP transport type
                        server["initializeEndpoint"] = "/api/v0/initialize"  # Point to our initialization endpoint
                        server["sseEndpoint"] = "/api/v0/sse"  # Point to SSE endpoint
                        print(f"✅ Updated Claude MCP server URL from {old_url} to {server['url']}")

            # Write updated settings back to file
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            print(f"✅ Successfully updated settings in {settings_path}")
            updated_files.append(settings_path)

        except Exception as e:
            print(f"❌ Error updating settings in {settings_path}: {e}")

    return len(updated_files) > 0

def update_local_storage_settings():
    """Update local storage tools settings in VS Code."""
    vscode_settings_paths = [
        os.path.expanduser("~/.config/Code - Insiders/User/settings.json"),
        os.path.expanduser("~/.config/Code/User/settings.json")
    ]

    updated_files = []

    for settings_path in vscode_settings_paths:
        if not os.path.exists(settings_path):
            continue

        try:
            # Read current settings
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            # Update local storage tools settings
            if "localStorageNetworkingTools" in settings:
                if "lspEndpoint" in settings["localStorageNetworkingTools"]:
                    if "url" in settings["localStorageNetworkingTools"]["lspEndpoint"]:
                        old_url = settings["localStorageNetworkingTools"]["lspEndpoint"]["url"]
                        settings["localStorageNetworkingTools"]["lspEndpoint"]["url"] = f"{PROXY_URL}/jsonrpc"
                        print(f"✅ Updated local storage LSP endpoint from {old_url} to {settings['localStorageNetworkingTools']['lspEndpoint']['url']}")

            # Write updated settings back to file
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            updated_files.append(settings_path)

        except Exception as e:
            print(f"❌ Error updating local storage settings in {settings_path}: {e}")

    return len(updated_files) > 0

def main():
    """Main entry point."""
    print("=== Updating VS Code Settings for MCP Proxy ===")

    vs_code_updated = update_vscode_settings()
    claude_updated = update_claude_mcp_settings()
    storage_updated = update_local_storage_settings()

    if vs_code_updated or claude_updated or storage_updated:
        print("\n✅ Settings successfully updated!")
        print(f"All MCP requests will now be proxied through {PROXY_URL}")
        print("\nNext steps:")
        print("1. Start the MCP proxy server: python ./mcp_vscode_proxy.py")
        print("2. Reload VS Code window (F1 -> Reload Window)")
    else:
        print("\n❌ No settings were updated.")
        print("Please check if VS Code settings files exist and are accessible.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
