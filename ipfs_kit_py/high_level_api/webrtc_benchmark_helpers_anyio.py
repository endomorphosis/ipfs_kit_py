"""
WebRTC Benchmark Helper Functions for High-Level API with AnyIO

This module provides helper functions for the IPFSSimpleAPI class to handle
WebRTC benchmarking operations through the CLI, using AnyIO for backend-agnostic
async operations.
"""

import os
import json
import logging
import time
import anyio
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import glob
import sniffio

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BENCHMARK_DIR = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "webrtc_benchmarks")

class WebRTCBenchmarkIntegrationAnyIO:
    """Integration helpers for WebRTC benchmarking with IPFSSimpleAPI using AnyIO."""
    
    @staticmethod
    async def run_benchmark(api, cid: str, **kwargs):
        """
        Run a WebRTC streaming benchmark for a specific CID.
        
        Args:
            api: IPFSSimpleAPI instance
            cid: Content identifier to benchmark
            duration: Duration in seconds
            output: Output file path
            enable_frame_stats: Whether to collect per-frame statistics
            visualize: Whether to generate visualizations
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with benchmark results
        """
        from ..webrtc_benchmark import WebRTCBenchmark, WebRTCStreamingManagerBenchmarkIntegration
        from ..webrtc_streaming import WebRTCStreamingManager, WebRTCConfig
            
        try:
            # Get parameters
            duration = kwargs.get("duration", 30)
            output_file = kwargs.get("output", None)
            enable_frame_stats = kwargs.get("enable_frame_stats", False)
            track_resource_usage = kwargs.get("track_resource_usage", True)
            visualize = kwargs.get("visualize", False)
            
            # Create benchmark directory if needed
            benchmark_dir = os.path.dirname(output_file) if output_file else DEFAULT_BENCHMARK_DIR
            os.makedirs(benchmark_dir, exist_ok=True)
            
            # Create WebRTCStreamingManager with benchmarking
            logger.info(f"Setting up WebRTC streaming for CID: {cid}")
            config = WebRTCConfig.get_optimal_config()
            manager = WebRTCStreamingManager(api, config=config)
            
            # Add benchmarking capabilities
            WebRTCStreamingManagerBenchmarkIntegration.add_benchmarking_to_manager(
                manager,
                enable_benchmarking=True,
                benchmark_reports_dir=benchmark_dir
            )
            
            # Create offer and start streaming
            logger.info(f"Creating WebRTC offer...")
            offer = await manager.create_offer(cid)
            pc_id = offer["pc_id"]
            
            logger.info(f"Connection established with ID: {pc_id}")
            logger.info(f"Running benchmark for {duration} seconds...")
            
            # Wait for the benchmark duration
            await anyio.sleep(duration)
            
            # Generate benchmark report
            logger.info("Generating benchmark report...")
            report_result = await manager.generate_benchmark_report(pc_id)
            
            # Get statistics
            stats = manager.get_benchmark_stats(pc_id)
            
            # Stop benchmark and close connection
            logger.info("Stopping benchmark...")
            manager.stop_benchmark(pc_id)
            await manager.close_peer_connection(pc_id)
            
            # Prepare result
            result = {
                "success": True,
                "pc_id": pc_id,
                "duration": duration,
                "stats": stats.get("stats", {}) if stats.get("success", False) else {},
            }
            
            # Add report information
            if report_result.get("success", False) and report_result.get("reports", []):
                report_path = report_result["reports"][0]["report_file"]
                result["report_file"] = report_path
                logger.info(f"Benchmark report saved to: {report_path}")
                
                # Generate visualizations if requested
                if visualize:
                    vis_result = await WebRTCBenchmarkIntegrationAnyIO.visualize_benchmark(api, report_path)
                    result["visualizations"] = vis_result.get("visualizations", [])
            
            # If output file is specified, save the result
            if output_file and output_file != report_path:
                try:
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    with open(output_file, 'w') as f:
                        json.dump(result, f, indent=2)
                    logger.info(f"Benchmark results saved to: {output_file}")
                except Exception as e:
                    logger.error(f"Error saving benchmark results: {e}")
                    result["output_error"] = str(e)
            
            return result
            
        except Exception as e:
            logger.error(f"Error running WebRTC benchmark: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def compare_benchmarks(api, benchmark1: str, benchmark2: str, **kwargs):
        """
        Compare two WebRTC benchmark reports.
        
        Args:
            api: IPFSSimpleAPI instance
            benchmark1: Path to first benchmark report
            benchmark2: Path to second benchmark report
            output: Optional output file path
            visualize: Whether to generate comparison visualizations
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with comparison results
        """
        from ..webrtc_benchmark import WebRTCBenchmark
            
        try:
            # Get parameters
            output_file = kwargs.get("output", None)
            visualize = kwargs.get("visualize", False)
            
            # Validate input files
            for path in [benchmark1, benchmark2]:
                if not os.path.exists(path):
                    return {
                        "success": False,
                        "error": f"Benchmark file not found: {path}"
                    }
            
            # Compare benchmarks
            logger.info(f"Comparing benchmark reports: {benchmark1} and {benchmark2}")
            comparison = await WebRTCBenchmark.compare_benchmarks(benchmark1, benchmark2)
            
            # Set success flag based on response structure
            comparison["success"] = "assessment" in comparison and "comparison" in comparison
            
            # If output file is specified, save the comparison
            if output_file:
                try:
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    with open(output_file, 'w') as f:
                        json.dump(comparison, f, indent=2)
                    logger.info(f"Comparison results saved to: {output_file}")
                except Exception as e:
                    logger.error(f"Error saving comparison results: {e}")
                    comparison["output_error"] = str(e)
            
            # Generate visualizations if requested
            if visualize:
                # Create visualizations directory
                output_dir = os.path.dirname(output_file) if output_file else DEFAULT_BENCHMARK_DIR
                vis_dir = os.path.join(output_dir, "comparisons")
                os.makedirs(vis_dir, exist_ok=True)
                
                # Create visualization file name
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                vis_prefix = f"comparison_{timestamp}"
                
                try:
                    # Check for matplotlib
                    import matplotlib.pyplot as plt
                    
                    # Load reports
                    with open(benchmark1, 'r') as f:
                        report1 = json.load(f)
                        
                    with open(benchmark2, 'r') as f:
                        report2 = json.load(f)
                    
                    # Generate comparative visualizations
                    WebRTCBenchmarkIntegrationAnyIO._generate_comparison_visualizations(
                        report1, report2, vis_dir, vis_prefix, comparison
                    )
                    
                    comparison["visualizations_dir"] = vis_dir
                    
                except ImportError:
                    logger.warning("Matplotlib not installed. Visualizations not generated.")
                    comparison["visualization_error"] = "Matplotlib not available"
                except Exception as e:
                    logger.error(f"Error generating visualizations: {e}")
                    comparison["visualization_error"] = str(e)
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing WebRTC benchmarks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def visualize_benchmark(api, report_path: str, **kwargs):
        """
        Generate visualizations for a WebRTC benchmark report.
        
        Args:
            api: IPFSSimpleAPI instance
            report_path: Path to benchmark report
            output_dir: Optional output directory
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with visualization results
        """
        try:
            # Check if report exists
            if not os.path.exists(report_path):
                return {
                    "success": False,
                    "error": f"Benchmark report not found: {report_path}"
                }
            
            # Get output directory
            output_dir = kwargs.get("output_dir", None)
            if not output_dir:
                output_dir = os.path.join(os.path.dirname(report_path), "visualizations")
            
            # Create directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Load report
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            # Check for matplotlib
            try:
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                from matplotlib.ticker import MaxNLocator
            except ImportError:
                return {
                    "success": False,
                    "error": "Matplotlib not installed. Visualizations cannot be generated."
                }
            
            # Create visualizations
            # Get base filename without extension
            base_filename = os.path.splitext(os.path.basename(report_path))[0]
            
            visualizations = []
            
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
            network_vis_path = os.path.join(output_dir, f"{base_filename}_network.png")
            plt.savefig(network_vis_path)
            visualizations.append(network_vis_path)
            
            # Create media performance visualization
            plt.figure(figsize=(12, 8))
            plt.subplot(2, 2, 1)
            plt.plot(report["time_series"]["frames_per_second"], label="FPS")
            plt.title("Frames Per Second")
            plt.legend()
            plt.grid(True)
            
            plt.subplot(2, 2, 2)
            # Plot resolution as a 2D scatter with width and height
            if "resolution_width" in report["time_series"] and "resolution_height" in report["time_series"]:
                width = report["time_series"]["resolution_width"]
                height = report["time_series"]["resolution_height"]
                plt.scatter(range(len(width)), [w * h for w, h in zip(width, height)], alpha=0.5)
                plt.title("Resolution (pixels)")
                plt.grid(True)
            
            plt.subplot(2, 2, 3)
            if "available_bitrate_kbps" in report["time_series"]:
                plt.plot(report["time_series"]["available_bitrate_kbps"], label="Available Bandwidth (kbps)")
                plt.title("Available Bandwidth")
                plt.legend()
                plt.grid(True)
            
            plt.subplot(2, 2, 4)
            if "cpu_percent" in report["time_series"]:
                plt.plot(report["time_series"]["cpu_percent"], label="CPU Usage (%)")
                plt.title("CPU Utilization")
                plt.legend()
                plt.grid(True)
            
            plt.tight_layout()
            media_vis_path = os.path.join(output_dir, f"{base_filename}_media.png")
            plt.savefig(media_vis_path)
            visualizations.append(media_vis_path)
            
            # Create summary visualization
            plt.figure(figsize=(10, 6))
            
            # Extract events with timings
            if "events" in report:
                events = report["events"]
                event_names = [e["event"] for e in events]
                event_times = [e["time_ms"] for e in events]
                
                # Plot events as a timeline
                plt.barh(event_names, [10] * len(event_names), left=event_times, height=0.5)
                plt.xlabel("Time (ms)")
                plt.title("Connection Establishment Timeline")
                plt.grid(True)
            else:
                plt.text(0.5, 0.5, "No event data available", ha='center', va='center')
            
            plt.tight_layout()
            events_vis_path = os.path.join(output_dir, f"{base_filename}_events.png")
            plt.savefig(events_vis_path)
            visualizations.append(events_vis_path)
            
            # Close all figures to free memory
            plt.close('all')
            
            logger.info(f"Visualizations saved to {output_dir}")
            
            return {
                "success": True,
                "visualizations": visualizations,
                "visualizations_dir": output_dir
            }
            
        except Exception as e:
            logger.error(f"Error visualizing WebRTC benchmark: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def list_benchmarks(api, **kwargs):
        """
        List available WebRTC benchmark reports.
        
        Args:
            api: IPFSSimpleAPI instance
            directory: Optional directory to search
            format: Output format (text or json)
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with benchmark reports
        """
        try:
            # Get parameters
            directory = kwargs.get("directory", DEFAULT_BENCHMARK_DIR)
            format = kwargs.get("format", "text")
            
            # Create directory if it doesn't exist
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                return {
                    "success": True,
                    "benchmarks": [],
                    "message": f"No benchmark reports found in {directory}"
                }
            
            # Find benchmark reports
            search_pattern = os.path.join(directory, "webrtc_benchmark_*.json")
            report_files = glob.glob(search_pattern)
            
            # Process results
            benchmarks = []
            for report_file in report_files:
                try:
                    with open(report_file, 'r') as f:
                        report = json.load(f)
                    
                    # Extract key information
                    summary = report.get("summary", {})
                    
                    benchmarks.append({
                        "file": report_file,
                        "cid": summary.get("cid", "unknown"),
                        "duration_sec": summary.get("duration_sec", 0),
                        "avg_bitrate_kbps": summary.get("avg_bitrate_kbps", 0),
                        "avg_fps": summary.get("avg_frames_per_second", 0),
                        "avg_rtt_ms": summary.get("avg_rtt_ms", 0),
                        "quality_score": summary.get("avg_quality_score", 0),
                        "timestamp": os.path.getmtime(report_file)
                    })
                    
                except Exception as e:
                    logger.warning(f"Error processing benchmark report {report_file}: {e}")
                    benchmarks.append({
                        "file": report_file,
                        "error": str(e),
                        "timestamp": os.path.getmtime(report_file)
                    })
            
            # Sort by timestamp (newest first)
            benchmarks.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return {
                "success": True,
                "benchmarks": benchmarks,
                "count": len(benchmarks),
                "directory": directory
            }
            
        except Exception as e:
            logger.error(f"Error listing WebRTC benchmarks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def _generate_comparison_visualizations(report1, report2, output_dir, prefix, comparison):
        """
        Generate comparison visualizations for two benchmark reports.
        
        Args:
            report1: First benchmark report
            report2: Second benchmark report
            output_dir: Output directory
            prefix: Filename prefix
            comparison: Comparison results
            
        Returns:
            None
        """
        import matplotlib.pyplot as plt
        
        # Create comparison visualizations
        metrics = [
            {"name": "rtt_ms", "title": "Round-Trip Time (ms)", "lower_better": True},
            {"name": "jitter_ms", "title": "Jitter (ms)", "lower_better": True},
            {"name": "packet_loss_percent", "title": "Packet Loss (%)", "lower_better": True},
            {"name": "bitrate_kbps", "title": "Bitrate (kbps)", "lower_better": False},
            {"name": "frames_per_second", "title": "Frames Per Second", "lower_better": False},
            {"name": "quality_score", "title": "Quality Score", "lower_better": False}
        ]
        
        # Create a figure for each metric
        for metric in metrics:
            if metric["name"] in report1["time_series"] and metric["name"] in report2["time_series"]:
                plt.figure(figsize=(10, 6))
                
                # Get data
                data1 = report1["time_series"][metric["name"]]
                data2 = report2["time_series"][metric["name"]]
                
                # Normalize x-axis to percentage of test duration
                x1 = [i / len(data1) * 100 for i in range(len(data1))]
                x2 = [i / len(data2) * 100 for i in range(len(data2))]
                
                # Plot
                plt.plot(x1, data1, label="Benchmark 1", alpha=0.7)
                plt.plot(x2, data2, label="Benchmark 2", alpha=0.7)
                
                # Add averages
                avg1 = sum(data1) / len(data1) if data1 else 0
                avg2 = sum(data2) / len(data2) if data2 else 0
                
                plt.axhline(y=avg1, color='b', linestyle='--', alpha=0.5)
                plt.axhline(y=avg2, color='orange', linestyle='--', alpha=0.5)
                
                # Add labels
                plt.text(98, avg1, f"{avg1:.2f}", ha='right', va='bottom')
                plt.text(98, avg2, f"{avg2:.2f}", ha='right', va='top')
                
                # Determine improvement
                better_color = 'green' if ((avg2 < avg1) == metric["lower_better"]) else 'red'
                
                # Calculate percentage change
                if avg1 != 0:
                    pct_change = ((avg2 - avg1) / avg1) * 100
                    change_text = f"{pct_change:.2f}% {'better' if ((avg2 < avg1) == metric['lower_better']) else 'worse'}"
                    
                    plt.figtext(0.5, 0.01, change_text, ha='center', color=better_color, 
                               bbox={'facecolor': 'white', 'alpha': 0.8, 'pad': 5})
                
                plt.title(f"Comparison: {metric['title']}")
                plt.xlabel("Test Duration (%)")
                plt.ylabel(metric["title"])
                plt.legend()
                plt.grid(True)
                
                # Save
                plt.tight_layout()
                vis_path = os.path.join(output_dir, f"{prefix}_{metric['name']}.png")
                plt.savefig(vis_path)
                plt.close()
        
        # Create summary visualization
        plt.figure(figsize=(12, 8))
        
        # Get summary metrics from the comparison
        metrics_to_plot = [k for k in comparison["comparison"].keys() 
                          if k in ["avg_rtt_ms", "avg_jitter_ms", "avg_packet_loss_percent", 
                                  "avg_bitrate_kbps", "avg_frames_per_second", 
                                  "throughput_mbps", "avg_quality_score"]]
        
        for i, metric in enumerate(metrics_to_plot):
            plt.subplot(3, 3, i+1)
            
            # Get values
            values = comparison["comparison"][metric]
            baseline = values["baseline"]
            current = values["current"]
            pct_change = values["percent_change"]
            is_regression = values["regression"]
            
            # Create bar chart
            bars = plt.bar([0, 1], [baseline, current], color=['blue', 'green' if not is_regression else 'red'])
            
            # Add labels
            plt.title(metric.replace("avg_", "").replace("_", " ").title())
            plt.xticks([0, 1], ["Baseline", "Current"])
            
            # Add percentage change
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.2f}', ha='center', va='bottom')
            
            # Add percentage change in the middle
            y_pos = max(baseline, current) * 1.1
            plt.text(0.5, y_pos, f"{pct_change:.2f}%", ha='center', va='bottom',
                    color='green' if not is_regression else 'red',
                    bbox={'facecolor': 'white', 'alpha': 0.8, 'pad': 2})
            
            plt.grid(True, axis='y')
        
        plt.tight_layout()
        summary_path = os.path.join(output_dir, f"{prefix}_summary.png")
        plt.savefig(summary_path)
        plt.close()
    
    # Add compatibility methods to provide backwards compatibility
    @staticmethod
    def get_backend():
        """
        Get the current async backend being used.
        
        Returns:
            String identifying the backend ('asyncio' or 'trio')
        """
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    @classmethod
    def run_sync(cls, coro, *args, **kwargs):
        """
        Run an async coroutine from a synchronous context using AnyIO.
        
        Args:
            coro: The coroutine function to run
            *args: Arguments to pass to the coroutine
            **kwargs: Keyword arguments to pass to the coroutine
            
        Returns:
            The result of the coroutine
        """
        return anyio.run(coro, *args, **kwargs)