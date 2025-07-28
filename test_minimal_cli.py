#!/usr/bin/env python3
"""
Minimal CLI test to isolate import issues
"""

import asyncio
import argparse
import socket
import subprocess
import sys
import requests

class MinimalCLI:
    """Minimal CLI for testing without heavy imports."""
    
    async def _is_daemon_running(self, port: int = 9999) -> bool:
        """Check if the IPFS-Kit daemon is running."""
        try:
            # Quick socket check first
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            if result != 0:
                return False
            
            # If socket is open, try HTTP request with very short timeout
            try:
                response = requests.get(f'http://localhost:{port}/health', timeout=2)
                return response.status_code == 200
            except requests.exceptions.Timeout:
                # Socket is open but HTTP not responding - daemon may be stuck
                return False
            except requests.exceptions.ConnectionError:
                # Connection refused or reset
                return False
            except Exception:
                # Any other error - assume not running properly
                return False
                
        except Exception:
            return False
    
    async def cmd_daemon_status(self):
        """Check daemon status."""
        print("📊 Checking IPFS-Kit daemon status...")
        
        daemon_running = await self._is_daemon_running()
        if daemon_running:
            print("✅ Daemon is running and responding")
            return 0
        else:
            print("❌ Daemon is not running or not responding")
            return 1

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Minimal IPFS-Kit CLI Test')
    parser.add_argument('command', nargs='?', default='status', help='Command to run')
    
    args = parser.parse_args()
    
    cli = MinimalCLI()
    
    if args.command == 'status':
        return await cli.cmd_daemon_status()
    else:
        print(f"Unknown command: {args.command}")
        return 1

def sync_main():
    """Synchronous entry point."""
    return asyncio.run(main())

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
