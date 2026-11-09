#!/usr/bin/env python3
"""
WebRTC Benchmark Example

This example demonstrates how to use the WebRTC benchmarking system to measure
performance of WebRTC connections when streaming content from IPFS.

Features shown:
1. Setting up benchmarking for WebRTC connections
2. Collecting detailed performance metrics
3. Analyzing network and media performance
4. Generating benchmark reports
5. Comparing benchmark results

Requirements:
- ipfs_kit_py[webrtc] - Full installation including WebRTC dependencies
- matplotlib (optional) - For visualizing benchmark results
"""

import anyio
import argparse
import logging
import os
import json
import time
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('webrtc_benchmark_example')

# Check for ipfs_kit_py
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.webrtc_benchmark import (
        WebRTCBenchmark, 
        WebRTCFrameStat, 
        WebRTCStreamingManagerBenchmarkIntegration,
        create_frame_stat
    )
except ImportError:
    logger.error("ipfs_kit_py not found. Please install it with 'pip install ipfs_kit_py[webrtc]'")
    sys.exit(1)

# Check for optional dependencies
HAVE_MATPLOTLIB = False
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import MaxNLocator
    HAVE_MATPLOTLIB = True
except ImportError:
    logger.warning("matplotlib not found. Visualization features will be disabled.")

# Constants
DEFAULT_REPORT_DIR = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "webrtc_benchmarks")


async def setup_webrtc_server(cid, enable_benchmarking=True):
    """Set up a WebRTC server with benchmarking enabled."""
    # Initialize IPFS API
    api = IPFSSimpleAPI()
    
    # Create instance of WebRTCStreamingManager
    from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager, WebRTCConfig
    
    # Create an optimized configuration
    config = WebRTCConfig.get_optimal_config()
    
    # Create manager
    manager = WebRTCStreamingManager(api, config=config)
    
    # Add benchmarking capabilities
    if enable_benchmarking:
        WebRTCStreamingManagerBenchmarkIntegration.add_benchmarking_to_manager(
            manager, 
            enable_benchmarking=True,
            benchmark_reports_dir=DEFAULT_REPORT_DIR
        )
    
    return manager


async def run_benchmark(cid, duration=60):
    """Run a WebRTC benchmark for the specified CID."""
    logger.info(f"Running benchmark for CID: {cid}")
    logger.info(f"Duration: {duration} seconds")
    
    # Set up WebRTC server with benchmarking
    manager = await setup_webrtc_server(cid)
    
    # Create offer for WebRTC connection
    logger.info("Creating WebRTC offer...")
    offer = await manager.create_offer(cid)
    pc_id = offer["pc_id"]
    
    logger.info(f"Connection established with ID: {pc_id}")
    
    # Wait for the benchmark duration
    logger.info(f"Running benchmark for {duration} seconds...")
    await anyio.sleep(duration)
    
    # Get benchmark stats
    stats = manager.get_benchmark_stats(pc_id)
    if stats["success"]:
        logger.info("Benchmark results:")
        for key, value in stats["stats"].items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                logger.info(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")
            else:
                logger.info(f"  {key}: {value}")
    
    # Generate benchmark report
    logger.info("Generating benchmark report...")
    report_result = await manager.generate_benchmark_report(pc_id)
    
    # Stop benchmark and close connection
    logger.info("Stopping benchmark...")
    manager.stop_benchmark(pc_id)
    await manager.close_peer_connection(pc_id)
    
    # Return report path
    if report_result["success"] and report_result["reports"]:
        report_path = report_result["reports"][0]["report_file"]
        logger.info(f"Benchmark report saved to: {report_path}")
        return report_path
    else:
        logger.warning("Failed to generate benchmark report")
        return None


async def compare_benchmarks(report1, report2):
    """Compare two benchmark reports."""
    # Make sure reports exist
    if not os.path.exists(report1) or not os.path.exists(report2):
        logger.error("One or both report files do not exist")
        return
        
    # Use the benchmark comparison function
    comparison = await WebRTCBenchmark.compare_benchmarks(report1, report2)
    
    # Print comparison results
    logger.info(f"Comparison results: {comparison['assessment']}")
    
    if "regressions" in comparison:
        logger.info("Regressions:")
        for metric in comparison["regressions"]:
            change = comparison["comparison"][metric]
            logger.info(f"  {metric}: {change['baseline']:.2f} → {change['current']:.2f} " +
                       f"({change['percent_change']:.2f}%)")
    
    if "improvements" in comparison:
        logger.info("Improvements:")
        for metric in comparison["improvements"]:
            change = comparison["comparison"][metric]
            logger.info(f"  {metric}: {change['baseline']:.2f} → {change['current']:.2f} " +
                       f"({change['percent_change']:.2f}%)")
    
    return comparison


def visualize_benchmark(report_path):
    """Create visualizations for a benchmark report."""
    if not HAVE_MATPLOTLIB:
        logger.error("Matplotlib not installed. Cannot visualize benchmark.")
        return
        
    # Load report
    with open(report_path, 'r') as f:
        report = json.load(f)
        
    # Create directory for visualizations
    vis_dir = os.path.join(os.path.dirname(report_path), "visualizations")
    os.makedirs(vis_dir, exist_ok=True)
    
    # Get base filename without extension
    base_filename = os.path.splitext(os.path.basename(report_path))[0]
    
    # Create network performance visualization
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 2, 1)
    plt.plot(report["time_series"]["rtt_ms"], label="RTT (ms)")
    plt.plot(report["time_series"]["jitter_ms"], label="Jitter (ms)")
    plt.title("Network Latency")
    plt.legend()
    plt.grid(True)
    
    plt.subplot(2, 2, 2)
    plt.plot(report["time_series"]["packet_loss_percent"], label="Packet Loss (%)")
    plt.title("Packet Loss")
    plt.legend()
    plt.grid(True)
    
    plt.subplot(2, 2, 3)
    plt.plot(report["time_series"]["bitrate_kbps"], label="Bitrate (kbps)")
    plt.title("Bitrate")
    plt.legend()
    plt.grid(True)
    
    plt.subplot(2, 2, 4)
    plt.plot(report["time_series"]["quality_score"], label="Quality Score (0-100)")
    plt.title("Overall Quality Score")
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(vis_dir, f"{base_filename}_network.png"))
    
    # Create media performance visualization
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 2, 1)
    plt.plot(report["time_series"]["frames_per_second"], label="FPS")
    plt.title("Frames Per Second")
    plt.legend()
    plt.grid(True)
    
    plt.subplot(2, 2, 2)
    # Plot resolution as a 2D scatter with width and height
    width = report["time_series"]["resolution_width"]
    height = report["time_series"]["resolution_height"]
    plt.scatter(range(len(width)), [w * h for w, h in zip(width, height)], alpha=0.5)
    plt.title("Resolution (pixels)")
    plt.grid(True)
    
    plt.subplot(2, 2, 3)
    plt.plot(report["time_series"]["available_bitrate_kbps"], label="Available Bandwidth (kbps)")
    plt.title("Available Bandwidth")
    plt.legend()
    plt.grid(True)
    
    plt.subplot(2, 2, 4)
    plt.plot(report["time_series"]["cpu_percent"], label="CPU Usage (%)")
    plt.title("CPU Utilization")
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(vis_dir, f"{base_filename}_media.png"))
    
    # Create summary visualization
    plt.figure(figsize=(10, 6))
    
    # Extract events with timings
    events = report["events"]
    event_names = [e["event"] for e in events]
    event_times = [e["time_ms"] for e in events]
    
    # Plot events as a timeline
    plt.barh(event_names, [10] * len(event_names), left=event_times, height=0.5)
    plt.xlabel("Time (ms)")
    plt.title("Connection Establishment Timeline")
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(vis_dir, f"{base_filename}_events.png"))
    
    logger.info(f"Visualizations saved to {vis_dir}")
    return vis_dir


async def manual_benchmark():
    """Demonstrate manual benchmarking without WebRTCStreamingManager."""
    # Create a standalone benchmark instance
    benchmark = WebRTCBenchmark(
        connection_id="manual-test",
        cid="Qmtest",
        enable_frame_stats=True,
        report_dir=DEFAULT_REPORT_DIR
    )
    
    # Start monitoring
    await benchmark.start_monitoring()
    
    # Record connection events
    benchmark.record_connection_event("ice_gathering_start", {})
    
    # Wait a bit to simulate ICE gathering
    await anyio.sleep(0.5)
    benchmark.record_connection_event("ice_gathering_complete", {})
    
    # Record ICE connection
    benchmark.record_connection_event("ice_connection_start", {})
    await anyio.sleep(1.0)
    benchmark.record_connection_event("ice_connected", {})
    
    # Record first frame
    benchmark.record_connection_event("first_frame", {})
    
    # Record some frame stats
    for i in range(10):
        # Create frame stat
        frame_stat = create_frame_stat(
            size_bytes=1000 * (i + 1),
            codec="VP8",
            is_keyframe=(i == 0),
            encode_start_time=time.time() - 0.1,
            encode_end_time=time.time()
        )
        
        # Add more timing data
        frame_stat.send_start_time = time.time()
        frame_stat.send_end_time = time.time() + 0.01
        frame_stat.receive_time = time.time() + 0.05
        frame_stat.decode_start_time = time.time() + 0.06
        frame_stat.decode_end_time = time.time() + 0.07
        frame_stat.render_time = time.time() + 0.08
        
        # Add to benchmark
        benchmark.add_frame_stat(frame_stat)
        
        # Update stats
        benchmark.update_stats({
            "rtt": 100,
            "jitter": 20,
            "packet_loss": 0.5,
            "bitrate": 1000000,
            "bandwidth_estimate": 2000000,
            "frames_per_second": 30,
            "resolution_width": 640,
            "resolution_height": 480,
            "cpu_percent": 20,
            "bytes_sent_delta": 10000,
            "bytes_received_delta": 9000,
            "packets_sent_delta": 100,
            "packets_received_delta": 98,
            "packets_lost_delta": 2
        })
        
        await anyio.sleep(0.1)
    
    # Get summary stats
    summary = benchmark.get_summary_stats()
    logger.info("Manual benchmark summary:")
    for key, value in summary.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            logger.info(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")
        else:
            logger.info(f"  {key}: {value}")
    
    # Generate report
    report_path = await benchmark.generate_report()
    logger.info(f"Manual benchmark report saved to: {report_path}")
    
    # Stop benchmark
    await benchmark.stop()
    
    return report_path


async def main():
    parser = argparse.ArgumentParser(description='WebRTC Benchmark Example')
    parser.add_argument('--cid', help='Content ID to benchmark streaming for')
    parser.add_argument('--duration', type=int, default=30, help='Duration of benchmark in seconds')
    parser.add_argument('--compare', nargs=2, help='Compare two benchmark reports')
    parser.add_argument('--visualize', help='Visualize a benchmark report')
    parser.add_argument('--manual', action='store_true', help='Run a manual benchmark demo')
    
    args = parser.parse_args()
    
    # Create reports directory
    os.makedirs(DEFAULT_REPORT_DIR, exist_ok=True)
    
    # Run requested action
    if args.cid:
        # Run benchmark for specified CID
        report_path = await run_benchmark(args.cid, args.duration)
        
        # Visualize if matplotlib available
        if HAVE_MATPLOTLIB and report_path:
            visualize_benchmark(report_path)
            
    elif args.compare:
        # Compare two benchmark reports
        await compare_benchmarks(args.compare[0], args.compare[1])
        
    elif args.visualize:
        # Visualize a benchmark report
        visualize_benchmark(args.visualize)
        
    elif args.manual:
        # Run manual benchmark demo
        report_path = await manual_benchmark()
        
        # Visualize if matplotlib available
        if HAVE_MATPLOTLIB and report_path:
            visualize_benchmark(report_path)
            
    else:
        parser.print_help()
        

if __name__ == "__main__":
    anyio.run(main())
