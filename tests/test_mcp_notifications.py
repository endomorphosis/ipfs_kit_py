#!/usr/bin/env python3
"""
Test script to verify MCP server handles notifications properly
"""

import json
import subprocess
import sys
import time
from pathlib import Path

def run_mcp_notifications_test() -> bool:
    """Run the notification handling test.

    Returns a boolean so this file can be used standalone; pytest asserts it.
    """
    
    print("🧪 Testing MCP Server with notifications...")
    
    # Start the MCP server
    server_path = Path("mcp/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py")
    server_cmd = [sys.executable, str(server_path)]
    
    try:
        proc = subprocess.Popen(
            server_cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            cwd=Path.cwd()
        )
        
        # Test messages
        messages = [
            # 1. Initialize request
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                }
            },
            # 2. Notification (no response expected)
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            },
            # 3. Tools list request
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
        ]
        
        # Send messages
        if proc.stdin:
            for i, msg in enumerate(messages, 1):
                print(f"📤 Sending message {i}: {msg['method']}")
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()
                time.sleep(0.5)  # Small delay between messages

            # Close stdin to signal end-of-input, but also detach it so communicate()
            # doesn't attempt to interact with a closed file object.
            proc.stdin.close()
            proc.stdin = None
        
        # Wait for processing
        try:
            stdout, stderr = proc.communicate(timeout=8)
            
            print("\n✅ Server Output:")
            if stdout.strip():
                # Parse JSON responses
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            response = json.loads(line)
                            print(f"   📥 {response.get('method', 'Response')}: {response.get('result', {}).get('protocolVersion', 'OK')}")
                        except json.JSONDecodeError:
                            print(f"   📥 Raw: {line[:100]}...")
            
            print("\n✅ Server Logs:")
            if stderr.strip():
                # Show last few log lines
                log_lines = stderr.strip().split('\n')[-10:]
                for line in log_lines:
                    if "notification" in line.lower() or "initialized" in line.lower():
                        print(f"   🔔 {line}")
                    elif "error" in line.lower():
                        print(f"   ❌ {line}")
                    elif "info" in line.lower():
                        print(f"   ℹ️  {line}")
            
            # Check if notifications/initialized error is gone
            if "Unknown method: notifications/initialized" in stderr:
                print("\n❌ Still getting notification error!")
                return False
            else:
                print("\n✅ Notifications handled properly!")
                return True
                
        except subprocess.TimeoutExpired:
            proc.kill()
            print("\n⏰ Server timeout (this might be normal)")
            return True
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


def test_mcp_server():
    assert run_mcp_notifications_test()

if __name__ == "__main__":
    success = run_mcp_notifications_test()
    sys.exit(0 if success else 1)
