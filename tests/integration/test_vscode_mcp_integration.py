#!/usr/bin/env python3
"""
Quick test script to verify the enhanced MCP server works with VS Code configuration
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

async def test_mcp_server():
    """Test the enhanced MCP server directly."""
    print("Testing Enhanced MCP Server...")
    
    # Start the server
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str((REPO_ROOT / "enhanced_mcp_server_phase1.py").resolve()),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        # Test initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        # Send request
        request_json = json.dumps(init_request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()
        
        # Read response
        response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        response = json.loads(response_line.decode().strip())
        
        if "error" in response:
            print(f"❌ Initialize failed: {response['error']}")
            return False
        
        print("✅ Initialize successful")
        
        # Test tools list
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        request_json = json.dumps(tools_request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()
        
        response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        response = json.loads(response_line.decode().strip())
        
        if "error" in response:
            print(f"❌ Tools list failed: {response['error']}")
            return False
        
        tools = response.get("result", {}).get("tools", [])
        print(f"✅ Tools list successful: {len(tools)} tools available")
        
        # List some key tools
        tool_names = [tool["name"] for tool in tools]
        core_tools = ["ipfs_add", "ipfs_cat", "ipfs_ls", "ipfs_version", "ipfs_id"]
        
        print("Core IPFS tools:")
        for tool in core_tools:
            if tool in tool_names:
                print(f"  ✅ {tool}")
            else:
                print(f"  ❌ {tool} (missing)")
        
        return True
        
    except asyncio.TimeoutError:
        print("❌ Server response timeout")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        # Clean up
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()

def test_vscode_config():
    """Test VS Code configuration files."""
    print("\nTesting VS Code Configuration...")
    
    # Check .vscode/settings.json
    try:
        with open((REPO_ROOT / ".vscode" / "settings.json"), "r") as f:
            settings = json.load(f)
        
        # Check for MCP servers
        if "mcp.servers" in settings:
            servers = settings["mcp.servers"]
            print(f"✅ Found {len(servers)} MCP servers in settings.json")
            for name in servers.keys():
                print(f"  • {name}")
        else:
            print("❌ No mcp.servers found in settings.json")
        
        # Check for Cline MCP servers
        if "cline.mcpServers" in settings:
            cline_servers = settings["cline.mcpServers"]
            print(f"✅ Found {len(cline_servers)} Cline MCP servers")
            for name, config in cline_servers.items():
                disabled = config.get("disabled", False)
                status = "disabled" if disabled else "enabled"
                print(f"  • {name} ({status})")
        else:
            print("❌ No cline.mcpServers found in settings.json")
            
    except FileNotFoundError:
        print("❌ .vscode/settings.json not found")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in settings.json: {e}")
    
    # Check .vscode/mcp.json  
    try:
        with open((REPO_ROOT / ".vscode" / "mcp.json"), "r") as f:
            mcp_config = json.load(f)
        
        if "mcpServers" in mcp_config:
            servers = mcp_config["mcpServers"]
            print(f"✅ Found {len(servers)} servers in mcp.json")
            for name, config in servers.items():
                disabled = config.get("disabled", False)
                status = "disabled" if disabled else "enabled"
                auto_approve = len(config.get("autoApprove", []))
                print(f"  • {name} ({status}, {auto_approve} auto-approved tools)")
        else:
            print("❌ No mcpServers found in mcp.json")
            
    except FileNotFoundError:
        print("❌ .vscode/mcp.json not found")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in mcp.json: {e}")

async def main():
    """Main test function."""
    print("=" * 60)
    print("Enhanced MCP Server VS Code Integration Test")
    print("=" * 60)
    
    # Test server functionality
    server_ok = await test_mcp_server()
    
    # Test configuration
    test_vscode_config()
    
    print("\n" + "=" * 60)
    if server_ok:
        print("✅ Enhanced MCP server is ready for VS Code integration!")
        print("\nNext steps:")
        print("1. Make sure VS Code MCP extension is installed")
        print("2. Restart VS Code to load the new configuration")
        print("3. The enhanced server should appear in the MCP extension")
    else:
        print("❌ Enhanced MCP server has issues - check the logs")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
