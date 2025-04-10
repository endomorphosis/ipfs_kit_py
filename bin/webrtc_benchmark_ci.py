#!/usr/bin/env python3
"""
WebRTC Benchmark CI Integration

This script integrates WebRTC benchmarking into CI/CD pipelines, enabling:
1. Automated benchmark runs on PR and regular intervals
2. Performance baseline tracking and maintenance
3. Regression detection with configurable thresholds
4. Integration with CI systems (GitHub Actions, GitLab CI, Jenkins)
5. Result reporting and visualization

Usage:
    python webrtc_benchmark_ci.py run --cid=<test_cid> --duration=30 --save-baseline
    python webrtc_benchmark_ci.py compare --baseline=<baseline_path> --current=<current_path>
    python webrtc_benchmark_ci.py validate --report=<report_path> --thresholds=thresholds.json
"""

import os
import sys
import json
import time
import argparse
import logging
import anyio
import datetime
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("webrtc_benchmark_ci")

# Constants
DEFAULT_BASELINE_DIR = os.path.join(
    os.path.expanduser("~"), ".ipfs_kit", "webrtc_benchmarks", "baselines"
)
DEFAULT_CI_REPORT_DIR = os.path.join(
    os.path.expanduser("~"), ".ipfs_kit", "webrtc_benchmarks", "ci_reports"
)
DEFAULT_THRESHOLDS = {
    "critical": {
        "avg_rtt_ms": 20,  # 20% increase is critical
        "avg_jitter_ms": 30,
        "avg_packet_loss_percent": 30,
        "p95_latency_ms": 25,
        "avg_bitrate_kbps": -15,  # 15% decrease is critical
        "avg_frames_per_second": -15,
        "quality_score": -10
    },
    "warning": {
        "avg_rtt_ms": 10,  # 10% increase is warning
        "avg_jitter_ms": 15,
        "avg_packet_loss_percent": 15,
        "p95_latency_ms": 15,
        "avg_bitrate_kbps": -7.5,
        "avg_frames_per_second": -7.5,
        "quality_score": -5
    }
}


def check_dependencies() -> bool:
    """Check if required dependencies are available."""
    try:
        import ipfs_kit_py.webrtc_benchmark
        import ipfs_kit_py.high_level_api
        return True
    except ImportError as e:
        logger.error(f"Failed to import required dependencies: {e}")
        logger.error("Please install ipfs_kit_py with WebRTC support: pip install ipfs_kit_py[webrtc]")
        return False


class BenchmarkCI:
    """CI integration for WebRTC benchmarks."""

    def __init__(self, 
                 baseline_dir: str = DEFAULT_BASELINE_DIR,
                 report_dir: str = DEFAULT_CI_REPORT_DIR,
                 thresholds: Dict[str, Dict[str, float]] = None):
        """
        Initialize the benchmark CI system.
        
        Args:
            baseline_dir: Directory to store baseline benchmark reports
            report_dir: Directory to store CI benchmark reports
            thresholds: Regression thresholds configuration
        """
        # Ensure directories exist
        self.baseline_dir = baseline_dir
        os.makedirs(self.baseline_dir, exist_ok=True)
        
        self.report_dir = report_dir
        os.makedirs(self.report_dir, exist_ok=True)
        
        # Set thresholds
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        
        # Create timestamp for this run
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Import modules
        from ipfs_kit_py.webrtc_benchmark import WebRTCBenchmark
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        
        self.WebRTCBenchmark = WebRTCBenchmark
        self.api = IPFSSimpleAPI()

    async def run_benchmark(self, cid: str, duration: int = 30) -> Optional[str]:
        """
        Run a WebRTC benchmark for the specified CID.
        
        Args:
            cid: Content ID to benchmark
            duration: Duration of the benchmark in seconds
            
        Returns:
            Path to the generated report file
        """
        logger.info(f"Running WebRTC benchmark for CID: {cid} (Duration: {duration}s)")
        
        try:
            # Set up WebRTC server with benchmark capabilities
            from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager, WebRTCConfig
            from ipfs_kit_py.webrtc_benchmark import WebRTCStreamingManagerBenchmarkIntegration
            
            # Create optimized config
            config = WebRTCConfig.get_optimal_config()
            
            # Create the streaming manager
            manager = WebRTCStreamingManager(self.api, config=config)
            
            # Add benchmarking capabilities
            WebRTCStreamingManagerBenchmarkIntegration.add_benchmarking_to_manager(
                manager,
                enable_benchmarking=True,
                benchmark_reports_dir=self.report_dir
            )
            
            # Create offer
            logger.info("Creating WebRTC offer...")
            offer = await manager.create_offer(cid)
            
            if not offer or "pc_id" not in offer:
                logger.error("Failed to create WebRTC offer")
                return None
                
            pc_id = offer["pc_id"]
            logger.info(f"WebRTC connection established with ID: {pc_id}")
            
            # Run benchmark for the specified duration
            logger.info(f"Running benchmark for {duration} seconds...")
            await asyncio.sleep(duration)
            
            # Generate report
            logger.info("Generating benchmark report...")
            report_result = await manager.generate_benchmark_report(pc_id)
            
            # Stop the benchmark and close connection
            logger.info("Stopping benchmark...")
            manager.stop_benchmark(pc_id)
            await manager.close_peer_connection(pc_id)
            
            # Return report path if successful
            if report_result.get("success", False) and report_result.get("reports"):
                report_path = report_result["reports"][0]["report_file"]
                logger.info(f"Benchmark report saved to: {report_path}")
                return report_path
            else:
                logger.error("Failed to generate benchmark report")
                return None
                
        except Exception as e:
            logger.error(f"Error running benchmark: {e}", exc_info=True)
            return None

    def save_as_baseline(self, report_path: str, name: str = None) -> Optional[str]:
        """
        Save a benchmark report as a baseline for future comparisons.
        
        Args:
            report_path: Path to the benchmark report
            name: Optional name for the baseline
            
        Returns:
            Path to the saved baseline file
        """
        try:
            # Load the report
            with open(report_path, 'r') as f:
                report = json.load(f)
                
            # Determine baseline name
            if not name:
                # Extract CID from report
                cid = report.get("summary", {}).get("cid", "unknown")
                name = f"baseline_{cid}"
                
            # Create timestamped filename
            baseline_filename = f"{name}_{self.timestamp}.json"
            baseline_path = os.path.join(self.baseline_dir, baseline_filename)
            
            # Also create a "latest" symlink
            latest_path = os.path.join(self.baseline_dir, f"{name}_latest.json")
            
            # Save the baseline
            with open(baseline_path, 'w') as f:
                json.dump(report, f, indent=2)
                
            # Update the "latest" link
            if os.path.exists(latest_path):
                os.remove(latest_path)
                
            # On Windows, symlinks require extra privileges, so use file copy instead
            if sys.platform == "win32":
                import shutil
                shutil.copy2(baseline_path, latest_path)
            else:
                os.symlink(baseline_path, latest_path)
                
            logger.info(f"Saved benchmark report as baseline: {baseline_path}")
            return baseline_path
            
        except Exception as e:
            logger.error(f"Error saving baseline: {e}", exc_info=True)
            return None

    async def compare_with_baseline(self, report_path: str, baseline_path: str = None, 
                             baseline_name: str = None) -> Dict[str, Any]:
        """
        Compare a benchmark report with a baseline.
        
        Args:
            report_path: Path to the benchmark report
            baseline_path: Path to baseline report (overrides baseline_name)
            baseline_name: Name of the baseline to use
            
        Returns:
            Comparison results
        """
        # Determine baseline path
        if not baseline_path and baseline_name:
            # Try to locate the "latest" baseline with this name
            baseline_path = os.path.join(self.baseline_dir, f"{baseline_name}_latest.json")
            
        if not baseline_path or not os.path.exists(baseline_path):
            logger.error(f"Baseline not found: {baseline_path}")
            return {
                "success": False,
                "error": "Baseline not found",
                "baseline_path": baseline_path
            }
            
        # Check report path
        if not os.path.exists(report_path):
            logger.error(f"Report not found: {report_path}")
            return {
                "success": False,
                "error": "Report not found",
                "report_path": report_path
            }
            
        # Perform comparison
        try:
            comparison = await self.WebRTCBenchmark.compare_benchmarks(baseline_path, report_path)
            comparison["success"] = True
            comparison["baseline_path"] = baseline_path
            comparison["report_path"] = report_path
            
            return comparison
        except Exception as e:
            logger.error(f"Error comparing benchmarks: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "baseline_path": baseline_path,
                "report_path": report_path
            }

    def validate_against_thresholds(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate benchmark comparison against defined thresholds.
        
        Args:
            comparison: Benchmark comparison results
            
        Returns:
            Validation results
        """
        if not comparison.get("success", False):
            return {
                "success": False,
                "error": comparison.get("error", "Invalid comparison"),
                "passed": False
            }
            
        # Extract comparison data
        comp_data = comparison.get("comparison", {})
        
        # Initialize results
        validation = {
            "success": True,
            "passed": True,
            "critical_regressions": [],
            "warning_regressions": [],
            "improvements": [],
            "details": {}
        }
        
        # Validate each metric against thresholds
        for metric, data in comp_data.items():
            if not isinstance(data, dict) or "percent_change" not in data:
                continue
                
            percent_change = data["percent_change"]
            validation["details"][metric] = {
                "baseline": data["baseline"],
                "current": data["current"],
                "percent_change": percent_change,
                "status": "unchanged"
            }
            
            # Check against critical thresholds
            critical_threshold = self.thresholds.get("critical", {}).get(metric)
            if critical_threshold is not None:
                if (critical_threshold > 0 and percent_change > critical_threshold) or \
                   (critical_threshold < 0 and percent_change < critical_threshold):
                    validation["critical_regressions"].append(metric)
                    validation["details"][metric]["status"] = "critical_regression"
                    validation["passed"] = False
                    continue
            
            # Check against warning thresholds
            warning_threshold = self.thresholds.get("warning", {}).get(metric)
            if warning_threshold is not None:
                if (warning_threshold > 0 and percent_change > warning_threshold) or \
                   (warning_threshold < 0 and percent_change < warning_threshold):
                    validation["warning_regressions"].append(metric)
                    validation["details"][metric]["status"] = "warning_regression"
                    continue
            
            # Check for improvements
            if data.get("regression", False) == False and abs(percent_change) >= 5:
                validation["improvements"].append(metric)
                validation["details"][metric]["status"] = "improvement"
                
        # Add summary
        validation["has_critical_regressions"] = len(validation["critical_regressions"]) > 0
        validation["has_warning_regressions"] = len(validation["warning_regressions"]) > 0
        validation["has_improvements"] = len(validation["improvements"]) > 0
        
        return validation

    def generate_report(self, validation: Dict[str, Any], comparison: Dict[str, Any]) -> str:
        """
        Generate a CI report with validation results.
        
        Args:
            validation: Validation results
            comparison: Benchmark comparison results
            
        Returns:
            Path to the generated report
        """
        try:
            # Create report data
            report = {
                "timestamp": self.timestamp,
                "validation": validation,
                "comparison": comparison.get("comparison", {}),
                "thresholds": self.thresholds
            }
            
            # Save the report
            report_path = os.path.join(
                self.report_dir, 
                f"ci_validation_{self.timestamp}.json"
            )
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
                
            # Generate text summary
            summary_path = os.path.join(
                self.report_dir,
                f"ci_summary_{self.timestamp}.txt"
            )
            
            with open(summary_path, 'w') as f:
                f.write(f"WebRTC Benchmark CI Report ({self.timestamp})\n")
                f.write("=" * 80 + "\n\n")
                
                # Overall status
                if validation["passed"]:
                    f.write("OVERALL STATUS: PASSED ✅\n\n")
                else:
                    f.write("OVERALL STATUS: FAILED ❌\n\n")
                
                # Critical regressions
                if validation["critical_regressions"]:
                    f.write("CRITICAL REGRESSIONS:\n")
                    for metric in validation["critical_regressions"]:
                        details = validation["details"][metric]
                        f.write(f"  {metric}: {details['baseline']:.2f} → {details['current']:.2f} ({details['percent_change']:.2f}%)\n")
                    f.write("\n")
                
                # Warning regressions
                if validation["warning_regressions"]:
                    f.write("WARNING REGRESSIONS:\n")
                    for metric in validation["warning_regressions"]:
                        details = validation["details"][metric]
                        f.write(f"  {metric}: {details['baseline']:.2f} → {details['current']:.2f} ({details['percent_change']:.2f}%)\n")
                    f.write("\n")
                
                # Improvements
                if validation["improvements"]:
                    f.write("IMPROVEMENTS:\n")
                    for metric in validation["improvements"]:
                        details = validation["details"][metric]
                        f.write(f"  {metric}: {details['baseline']:.2f} → {details['current']:.2f} ({details['percent_change']:.2f}%)\n")
                    f.write("\n")
                    
                # Add thresholds used
                f.write("THRESHOLDS:\n")
                f.write("  Critical:\n")
                for metric, threshold in self.thresholds["critical"].items():
                    f.write(f"    {metric}: {threshold}%\n")
                f.write("  Warning:\n")
                for metric, threshold in self.thresholds["warning"].items():
                    f.write(f"    {metric}: {threshold}%\n")
                    
            logger.info(f"CI validation report saved to: {report_path}")
            logger.info(f"CI summary saved to: {summary_path}")
            
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating CI report: {e}", exc_info=True)
            return ""

    def print_summary(self, validation: Dict[str, Any]) -> None:
        """Print a summary of validation results to console."""
        if not validation.get("success", False):
            logger.error(f"Validation failed: {validation.get('error', 'Unknown error')}")
            return
            
        print("\n" + "=" * 80)
        print(" WebRTC Benchmark CI Validation Results ".center(80, "="))
        print("=" * 80 + "\n")
        
        # Overall status
        if validation["passed"]:
            print("OVERALL STATUS: PASSED ✅\n")
        else:
            print("OVERALL STATUS: FAILED ❌\n")
        
        # Critical regressions
        if validation["critical_regressions"]:
            print("CRITICAL REGRESSIONS:")
            for metric in validation["critical_regressions"]:
                details = validation["details"][metric]
                print(f"  {metric}: {details['baseline']:.2f} → {details['current']:.2f} ({details['percent_change']:.2f}%)")
            print("")
        
        # Warning regressions
        if validation["warning_regressions"]:
            print("WARNING REGRESSIONS:")
            for metric in validation["warning_regressions"]:
                details = validation["details"][metric]
                print(f"  {metric}: {details['baseline']:.2f} → {details['current']:.2f} ({details['percent_change']:.2f}%)")
            print("")
        
        # Improvements
        if validation["improvements"]:
            print("IMPROVEMENTS:")
            for metric in validation["improvements"]:
                details = validation["details"][metric]
                print(f"  {metric}: {details['baseline']:.2f} → {details['current']:.2f} ({details['percent_change']:.2f}%)")
            print("")
            
        print("=" * 80 + "\n")


async def run_command(args: argparse.Namespace) -> int:
    """Run a WebRTC benchmark and optionally save as baseline."""
    if not check_dependencies():
        return 1
        
    # Load threshold configuration
    thresholds = DEFAULT_THRESHOLDS
    if args.thresholds and os.path.exists(args.thresholds):
        try:
            with open(args.thresholds, 'r') as f:
                thresholds = json.load(f)
        except Exception as e:
            logger.error(f"Error loading thresholds: {e}")
    
    # Initialize CI system
    ci = BenchmarkCI(
        baseline_dir=args.baseline_dir or DEFAULT_BASELINE_DIR,
        report_dir=args.report_dir or DEFAULT_CI_REPORT_DIR,
        thresholds=thresholds
    )
    
    # Run benchmark
    report_path = await ci.run_benchmark(args.cid, args.duration)
    if not report_path:
        return 1
        
    # Save as baseline if requested
    if args.save_baseline:
        baseline_path = ci.save_as_baseline(report_path, args.baseline_name)
        if not baseline_path:
            return 1
            
    # Compare with baseline if requested
    if args.compare_baseline:
        baseline_path = args.baseline_path
        if not baseline_path:
            # Try to use name to find baseline
            baseline_name = args.baseline_name or f"baseline_{args.cid}"
            baseline_path = os.path.join(ci.baseline_dir, f"{baseline_name}_latest.json")
            
        if not os.path.exists(baseline_path):
            logger.error(f"Baseline not found for comparison: {baseline_path}")
            return 1
            
        # Run comparison
        comparison = await ci.compare_with_baseline(report_path, baseline_path)
        if not comparison.get("success", False):
            logger.error(f"Comparison failed: {comparison.get('error', 'Unknown error')}")
            return 1
            
        # Validate against thresholds
        validation = ci.validate_against_thresholds(comparison)
        
        # Generate report
        ci.generate_report(validation, comparison)
        
        # Print summary
        ci.print_summary(validation)
        
        # Return status code
        return 0 if validation["passed"] else 1
        
    return 0


async def compare_command(args: argparse.Namespace) -> int:
    """Compare two benchmark reports."""
    if not check_dependencies():
        return 1
        
    # Load threshold configuration
    thresholds = DEFAULT_THRESHOLDS
    if args.thresholds and os.path.exists(args.thresholds):
        try:
            with open(args.thresholds, 'r') as f:
                thresholds = json.load(f)
        except Exception as e:
            logger.error(f"Error loading thresholds: {e}")
    
    # Initialize CI system
    ci = BenchmarkCI(
        report_dir=args.report_dir or DEFAULT_CI_REPORT_DIR,
        thresholds=thresholds
    )
    
    # Run comparison
    comparison = await ci.compare_with_baseline(args.current, args.baseline)
    if not comparison.get("success", False):
        logger.error(f"Comparison failed: {comparison.get('error', 'Unknown error')}")
        return 1
        
    # Validate against thresholds
    validation = ci.validate_against_thresholds(comparison)
    
    # Generate report
    ci.generate_report(validation, comparison)
    
    # Print summary
    ci.print_summary(validation)
    
    # Return status code
    return 0 if validation["passed"] else 1


async def validate_command(args: argparse.Namespace) -> int:
    """Validate a benchmark report against thresholds."""
    if not check_dependencies():
        return 1
        
    # Load threshold configuration
    thresholds = DEFAULT_THRESHOLDS
    if args.thresholds and os.path.exists(args.thresholds):
        try:
            with open(args.thresholds, 'r') as f:
                thresholds = json.load(f)
        except Exception as e:
            logger.error(f"Error loading thresholds: {e}")
            
    # Load comparison report
    if not os.path.exists(args.report):
        logger.error(f"Report not found: {args.report}")
        return 1
        
    try:
        with open(args.report, 'r') as f:
            comparison = json.load(f)
    except Exception as e:
        logger.error(f"Error loading report: {e}")
        return 1
        
    # Initialize CI system
    ci = BenchmarkCI(
        report_dir=args.report_dir or DEFAULT_CI_REPORT_DIR,
        thresholds=thresholds
    )
    
    # Validate against thresholds
    validation = ci.validate_against_thresholds(comparison)
    
    # Generate report
    ci.generate_report(validation, comparison)
    
    # Print summary
    ci.print_summary(validation)
    
    # Return status code
    return 0 if validation["passed"] else 1


def save_baseline_command(args: argparse.Namespace) -> int:
    """Save a benchmark report as a baseline."""
    if not check_dependencies():
        return 1
        
    # Check if report exists
    if not os.path.exists(args.report):
        logger.error(f"Report not found: {args.report}")
        return 1
        
    # Initialize CI system
    ci = BenchmarkCI(
        baseline_dir=args.baseline_dir or DEFAULT_BASELINE_DIR
    )
    
    # Save as baseline
    baseline_path = ci.save_as_baseline(args.report, args.name)
    if not baseline_path:
        logger.error("Failed to save baseline")
        return 1
        
    logger.info(f"Successfully saved baseline to {baseline_path}")
    return 0


def main() -> int:
    """Main entry point with command parser."""
    parser = argparse.ArgumentParser(description='WebRTC Benchmark CI Integration')
    subparsers = parser.add_subparsers(dest='command')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a WebRTC benchmark')
    run_parser.add_argument('--cid', required=True, help='Content ID to benchmark')
    run_parser.add_argument('--duration', type=int, default=30, help='Duration of benchmark in seconds')
    run_parser.add_argument('--baseline-dir', help='Directory for baseline reports')
    run_parser.add_argument('--report-dir', help='Directory for CI reports')
    run_parser.add_argument('--save-baseline', action='store_true', help='Save as baseline')
    run_parser.add_argument('--baseline-name', help='Name for baseline')
    run_parser.add_argument('--compare-baseline', action='store_true', help='Compare with baseline')
    run_parser.add_argument('--baseline-path', help='Path to baseline for comparison')
    run_parser.add_argument('--thresholds', help='Path to thresholds configuration')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two benchmark reports')
    compare_parser.add_argument('--baseline', required=True, help='Path to baseline report')
    compare_parser.add_argument('--current', required=True, help='Path to current report')
    compare_parser.add_argument('--report-dir', help='Directory for CI reports')
    compare_parser.add_argument('--thresholds', help='Path to thresholds configuration')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a report against thresholds')
    validate_parser.add_argument('--report', required=True, help='Path to comparison report')
    validate_parser.add_argument('--report-dir', help='Directory for CI reports')
    validate_parser.add_argument('--thresholds', help='Path to thresholds configuration')
    
    # Save baseline command
    save_baseline_parser = subparsers.add_parser('save-baseline', help='Save a benchmark report as a baseline')
    save_baseline_parser.add_argument('--report', required=True, help='Path to benchmark report')
    save_baseline_parser.add_argument('--name', help='Name for the baseline')
    save_baseline_parser.add_argument('--baseline-dir', help='Directory for baseline reports')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
        
    try:
        # Run appropriate command
        if args.command == 'run':
            return asyncio.run(run_command(args))
        elif args.command == 'compare':
            return asyncio.run(compare_command(args))
        elif args.command == 'validate':
            return asyncio.run(validate_command(args))
        elif args.command == 'save-baseline':
            return save_baseline_command(args)
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
