#!/usr/bin/env python3
"""
Quick Fix Test for ipfs_ls
==========================

Test the ipfs_ls tool with a CID that we know exists.
"""

import json
import subprocess
import asyncio
import sys
import os
import tempfile
from datetime import datetime

async def test_ipfs_ls_fix():
    """Test ipfs_ls with an existing CID."""
    
    # Start the server
    process = await asyncio.create_subprocess_exec(
        "python3", "enhanced_mcp_server_phase1.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        # Initialize
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
        
        process.stdin.write((json.dumps(init_request) + "\n").encode())
        await process.stdin.drain()
        await process.stdout.readline()  # Read response
        
        # First, add a directory structure to IPFS
        # Create a temp directory with files
        temp_dir = tempfile.mkdtemp()
        try:
            # Create some test files
            with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
                f.write("Content of file 1")
            with open(os.path.join(temp_dir, "file2.txt"), "w") as f:
                f.write("Content of file 2")
            
            # Add the directory to IPFS directly
            result = subprocess.run([
                "ipfs", "add", "-r", "-q", temp_dir
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                dir_cid = lines[-1]  # Last line is the directory CID
                print(f"Created directory with CID: {dir_cid}")
                
                # Now test ipfs_ls with this CID
                ls_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "ipfs_ls",
                        "arguments": {
                            "cid": dir_cid,
                            "headers": True
                        }
                    }
                }
                
                process.stdin.write((json.dumps(ls_request) + "\n").encode())
                await process.stdin.drain()
                response_line = await process.stdout.readline()
                response = json.loads(response_line.decode().strip())
                
                if "error" in response:
                    print(f"✗ ipfs_ls failed: {response['error']}")
                    return False
                else:
                    content = response.get("result", {}).get("content", [])
                    if content:
                        result = json.loads(content[0]["text"])
                        if result.get("success"):
                            print(f"✓ ipfs_ls succeeded with directory CID!")
                            print(f"  Contents: {result.get('contents', 'No contents')}")
                            return True
                        else:
                            print(f"✗ ipfs_ls failed: {result.get('error')}")
                            return False
            else:
                print(f"✗ Failed to create test directory: {result.stderr}")
                return False
                
        finally:
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir)
            
    finally:
        process.terminate()
        await process.wait()

async def main():
    print("Testing ipfs_ls fix...")
    success = await test_ipfs_ls_fix()
    if success:
        print("🎉 ipfs_ls now working!")
    else:
        print("❌ ipfs_ls still has issues")

if __name__ == "__main__":
    asyncio.run(main())
