#!/usr/bin/env python3
"""
Quick smoke for ipfs-kit MCP CLI status.
- Prints PID/alive and HTTP initialized/tools for a given port.
Usage:
  python scripts/smoke_cli_status.py --port 8004 [--host 127.0.0.1]
"""
import argparse
import json
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8004)
    args = ap.parse_args()

    # Prefer CLI output if available
    try:
        import subprocess, sys
        cmd = [sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'status', '--host', args.host, '--port', str(args.port)]
        out = subprocess.check_output(cmd, cwd='..', text=True, stderr=subprocess.STDOUT)
        print(out.strip())
    except Exception as e:
        print(f"CLI status unavailable: {e}")

    # Raw HTTP status
    try:
        with urllib.request.urlopen(f'http://{args.host}:{args.port}/api/mcp/status', timeout=2.0) as r:
            body = r.read().decode('utf-8', 'ignore')
            j = json.loads(body)
            data = j.get('data') or j
            print(json.dumps({'http_ok': True, 'initialized': data.get('initialized'), 'tools': data.get('total_tools')}, indent=2))
    except Exception as e:
        print(f"HTTP status unavailable: {e}")


if __name__ == '__main__':
    main()
