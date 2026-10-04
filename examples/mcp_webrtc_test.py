#!/usr/bin/env python3
"""
Test script for WebRTC streaming capabilities in the MCP server.

This script:
1. Connects to the MCP server
2. Checks WebRTC dependencies
3. Adds test content to IPFS
4. Starts a WebRTC stream for the content
5. Lists active connections
6. Gets connection statistics
7. Stops the stream

Usage:
    python mcp_webrtc_test.py [--server-url URL] [--port PORT]
"""

import os
import sys
import time
import json
import argparse
import requests
import tempfile
import random
from pathlib import Path

def check_webrtc_dependencies(server_url):
    """Check if WebRTC dependencies are available on the server."""
    print("\n[1] Checking WebRTC dependencies...")
    
    try:
        response = requests.get(f"{server_url}/webrtc/check")
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            webrtc_available = data.get("webrtc_available", False)
            if webrtc_available:
                print("✅ WebRTC is available!")
                print("Dependencies:")
                for dep, available in data.get("dependencies", {}).items():
                    status = "✅" if available else "❌"
                    print(f"  {status} {dep}")
                return True
            else:
                print("❌ WebRTC is not available.")
                missing_deps = [dep for dep, available in data.get("dependencies", {}).items() if not available]
                print(f"Missing dependencies: {', '.join(missing_deps)}")
                print(f"Installation command: {data.get('installation_command', 'N/A')}")
                return False
        else:
            print(f"❌ Failed to check WebRTC dependencies: {data.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Error checking WebRTC dependencies: {e}")
        return False

def add_test_content(server_url):
    """Add test content to IPFS for streaming."""
    print("\n[2] Adding test content to IPFS...")
    
    # Create a temporary file with random content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp:
        temp_path = temp.name
        # Generate some random content
        content = f"Test content for WebRTC streaming. Random ID: {random.randint(10000, 99999)}\n"
        content += "=" * 80 + "\n"
        for i in range(100):
            content += f"Line {i}: {random.randint(1000, 9999)}\n"
        
        temp.write(content.encode('utf-8'))
    
    try:
        # Add the file to IPFS
        with open(temp_path, 'rb') as f:
            response = requests.post(
                f"{server_url}/ipfs/add",
                files={"file": (os.path.basename(temp_path), f, "text/plain")}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success", False):
                cid = data.get("cid") or data.get("Hash")
                print(f"✅ Content added to IPFS with CID: {cid}")
                print(f"Content size: {len(content)} bytes")
                
                # Clean up the temporary file
                os.unlink(temp_path)
                
                return cid
            else:
                print(f"❌ Failed to add content to IPFS: {data.get('error', 'Unknown error')}")
                return None
    except Exception as e:
        print(f"❌ Error adding content to IPFS: {e}")
        
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            
        return None

def start_webrtc_stream(server_url, cid):
    """Start a WebRTC stream for the given CID."""
    print(f"\n[3] Starting WebRTC stream for CID: {cid}...")
    
    try:
        # Prepare stream request
        stream_request = {
            "cid": cid,
            "address": "127.0.0.1",
            "port": 8080,
            "quality": "medium",
            "ice_servers": [
                {"urls": ["stun:stun.l.google.com:19302"]}
            ],
            "benchmark": True  # Enable benchmarking for testing
        }
        
        # Start the stream
        response = requests.post(
            f"{server_url}/webrtc/stream",
            json=stream_request
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            server_id = data.get("server_id")
            url = data.get("url")
            print(f"✅ WebRTC stream started successfully!")
            print(f"Server ID: {server_id}")
            print(f"Stream URL: {url}")
            return server_id
        else:
            print(f"❌ Failed to start WebRTC stream: {data.get('error', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Error starting WebRTC stream: {e}")
        return None

def list_connections(server_url):
    """List active WebRTC connections."""
    print("\n[4] Listing active WebRTC connections...")
    
    try:
        response = requests.get(f"{server_url}/webrtc/connections")
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            connections = data.get("connections", [])
            
            if connections:
                print(f"✅ Found {len(connections)} active connection(s):")
                for i, conn in enumerate(connections, 1):
                    conn_id = conn.get("connection_id") or conn.get("id")
                    print(f"  Connection {i}:")
                    print(f"  - ID: {conn_id}")
                    print(f"  - Status: {conn.get('status') or conn.get('connection_state', 'N/A')}")
                    print(f"  - ICE State: {conn.get('ice_state', 'N/A')}")
                    if "quality" in conn:
                        print(f"  - Quality: {conn.get('quality')}")
                    print()
                    
                # Return the first connection ID for further operations
                if connections:
                    return connections[0].get("connection_id") or connections[0].get("id")
            else:
                print("ℹ️ No active connections found.")
                return None
        else:
            print(f"❌ Failed to list connections: {data.get('error', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Error listing connections: {e}")
        return None

def get_connection_stats(server_url, connection_id):
    """Get statistics for a WebRTC connection."""
    if not connection_id:
        print("\n[5] Skipping connection statistics (no connection ID)...")
        return
        
    print(f"\n[5] Getting statistics for connection: {connection_id}...")
    
    try:
        response = requests.get(f"{server_url}/webrtc/connections/{connection_id}/stats")
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            stats = data.get("stats", {})
            
            if stats:
                print("✅ Connection statistics:")
                
                # Display relevant statistics
                relevant_stats = [
                    ("bytes_sent", "Bytes Sent", lambda x: f"{int(x) / 1024:.2f} KB"),
                    ("bytes_received", "Bytes Received", lambda x: f"{int(x) / 1024:.2f} KB"),
                    ("packets_sent", "Packets Sent", str),
                    ("packets_received", "Packets Received", str),
                    ("nack_count", "NACK Count", str),
                    ("frame_rate", "Frame Rate", lambda x: f"{float(x):.1f} fps"),
                    ("resolution", "Resolution", str),
                    ("bandwidth", "Bandwidth", lambda x: f"{int(x) / 1000:.2f} Kbps"),
                    ("jitter", "Jitter", lambda x: f"{float(x):.2f} ms"),
                    ("latency", "Latency", lambda x: f"{float(x):.2f} ms"),
                    ("packet_loss", "Packet Loss", lambda x: f"{float(x) * 100:.2f}%")
                ]
                
                for key, label, formatter in relevant_stats:
                    if key in stats:
                        try:
                            value = formatter(stats[key])
                            print(f"  {label}: {value}")
                        except (ValueError, TypeError):
                            print(f"  {label}: {stats[key]}")
            else:
                print("ℹ️ No statistics available for this connection.")
        else:
            print(f"❌ Failed to get connection statistics: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error getting connection statistics: {e}")

def set_connection_quality(server_url, connection_id, quality):
    """Set the quality for a WebRTC connection."""
    if not connection_id:
        print("\n[6] Skipping quality adjustment (no connection ID)...")
        return
        
    print(f"\n[6] Setting quality to '{quality}' for connection: {connection_id}...")
    
    try:
        # Prepare quality request
        quality_request = {
            "connection_id": connection_id,
            "quality": quality
        }
        
        # Set the quality
        response = requests.post(
            f"{server_url}/webrtc/connections/quality",
            json=quality_request
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            print(f"✅ Quality set to '{quality}' successfully!")
            if "previous_quality" in data:
                print(f"Previous quality was: {data['previous_quality']}")
        else:
            print(f"❌ Failed to set quality: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error setting quality: {e}")

def stop_stream(server_url, server_id):
    """Stop a WebRTC stream."""
    if not server_id:
        print("\n[7] Skipping stream stop (no server ID)...")
        return
        
    print(f"\n[7] Stopping WebRTC stream for server ID: {server_id}...")
    
    try:
        response = requests.post(f"{server_url}/webrtc/stream/stop/{server_id}")
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            print("✅ WebRTC stream stopped successfully!")
        else:
            print(f"❌ Failed to stop WebRTC stream: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error stopping WebRTC stream: {e}")

def close_all_connections(server_url):
    """Close all active WebRTC connections."""
    print("\n[8] Closing all WebRTC connections...")
    
    try:
        response = requests.post(f"{server_url}/webrtc/connections/close-all")
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            count = data.get("connections_closed", 0)
            print(f"✅ Closed {count} connection(s) successfully!")
        else:
            print(f"❌ Failed to close connections: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error closing connections: {e}")

def run_benchmark(server_url, cid):
    """Run a WebRTC streaming benchmark."""
    print(f"\n[9] Running WebRTC benchmark for CID: {cid}...")
    
    try:
        # Create a temporary directory for benchmark output
        output_dir = tempfile.mkdtemp(prefix="webrtc_benchmark_")
        
        # Prepare benchmark request
        benchmark_request = {
            "cid": cid,
            "duration": 10,  # Short duration for testing
            "format": "json",
            "output_dir": output_dir
        }
        
        # Run the benchmark
        response = requests.post(
            f"{server_url}/webrtc/benchmark",
            json=benchmark_request
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success", False):
            benchmark_id = data.get("benchmark_id")
            report_path = data.get("report_path")
            summary = data.get("summary", {})
            
            print(f"✅ WebRTC benchmark completed successfully!")
            print(f"Benchmark ID: {benchmark_id}")
            print(f"Report path: {report_path}")
            
            if summary:
                print("\nBenchmark Summary:")
                for key, value in summary.items():
                    print(f"  {key}: {value}")
            
            return benchmark_id
        else:
            print(f"❌ Failed to run benchmark: {data.get('error', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")
        return None

def main():
    """Main function to test WebRTC functionality."""
    parser = argparse.ArgumentParser(description="Test WebRTC functionality in MCP server")
    parser.add_argument("--server-url", default="http://localhost:9999/api/v0/mcp", help="MCP server URL")
    parser.add_argument("--skip-deps-check", action="store_true", help="Skip WebRTC dependency check")
    parser.add_argument("--skip-content-add", action="store_true", help="Skip adding test content")
    parser.add_argument("--cid", help="Use existing CID instead of adding test content")
    parser.add_argument("--benchmark-only", action="store_true", help="Only run the benchmark test")
    args = parser.parse_args()
    
    # Display test header
    print("=" * 80)
    print("IPFS MCP WebRTC Test")
    print(f"Server URL: {args.server_url}")
    print("=" * 80)
    
    # Check WebRTC dependencies
    if not args.skip_deps_check and not args.benchmark_only:
        webrtc_available = check_webrtc_dependencies(args.server_url)
        if not webrtc_available:
            print("WebRTC is not available. Exiting test.")
            return
    
    # Get test content CID
    cid = args.cid
    if not cid and not args.skip_content_add and not args.benchmark_only:
        cid = add_test_content(args.server_url)
        if not cid:
            print("Failed to add test content. Exiting test.")
            return
    
    if args.benchmark_only and cid:
        # Run only the benchmark
        run_benchmark(args.server_url, cid)
        return
    elif args.benchmark_only and not cid:
        print("CID is required for benchmark-only mode. Use --cid to specify a CID.")
        return
    
    # Start WebRTC stream
    server_id = start_webrtc_stream(args.server_url, cid)
    if not server_id:
        print("Failed to start WebRTC stream. Exiting test.")
        return
    
    # Pause to allow connections to be established
    print("\nWaiting 2 seconds for connections to be established...")
    time.sleep(2)
    
    # List connections
    connection_id = list_connections(args.server_url)
    
    # Get connection statistics
    if connection_id:
        get_connection_stats(args.server_url, connection_id)
        
        # Try different quality settings
        set_connection_quality(args.server_url, connection_id, "high")
        
        # Pause to see the effect
        print("\nWaiting 2 seconds to observe quality change...")
        time.sleep(2)
        
        # Get updated statistics
        get_connection_stats(args.server_url, connection_id)
    
    # Run benchmark
    if cid:
        run_benchmark(args.server_url, cid)
    
    # Stop the stream
    stop_stream(args.server_url, server_id)
    
    # Close all connections
    close_all_connections(args.server_url)
    
    # Test complete
    print("\n" + "=" * 80)
    print("WebRTC Test Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()