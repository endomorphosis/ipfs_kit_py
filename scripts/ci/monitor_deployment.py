#!/usr/bin/env python3
"""
MCP Blue/Green Deployment Monitoring Script

This script monitors the health of a blue/green deployment, collecting metrics
and validating that the deployment meets specified criteria. It can be used
in CI/CD pipelines to verify deployment success and prevent bad deployments
from proceeding.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("deployment_monitor")

class DeploymentMonitor:
    """Monitor blue/green deployment health and performance."""

    def __init__(
        self,
        environment: str,
        host: str = None,
        port: int = 8090,
        api_path: str = "/api/health",
        output_dir: str = "./monitoring_results",
        poll_interval: int = 10
    ):
        """
        Initialize the deployment monitor.

        Args:
            environment: Deployment environment (dev, staging, production)
            host: Host address for the proxy service
            port: Port for the proxy API
            api_path: API endpoint path for health checks
            output_dir: Directory to save monitoring results
            poll_interval: Time between health checks in seconds
        """
        self.environment = environment
        self.port = port
        self.api_path = api_path
        self.output_dir = Path(output_dir)
        self.poll_interval = poll_interval

        # Determine host based on environment if not provided
        if host:
            self.host = host
        else:
            if environment == "local":
                self.host = "localhost"
            else:
                # In Kubernetes, use port-forwarding or service DNS
                self.host = f"mcp-proxy.mcp-{environment}"

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Initialize monitoring state
        self.start_time = time.time()
        self.samples = []
        self.issues = []
        self.summary = {
            "environment": environment,
            "start_time": self.start_time,
            "end_time": None,
            "duration": 0,
            "total_samples": 0,
            "successful_samples": 0,
            "failures": 0,
            "availability": 100.0,
            "avg_blue_response_time": 0,
            "avg_green_response_time": 0,
            "compatibility_rate": 0,
            "issues_detected": 0
        }

    def check_health(self) -> Optional[Dict[str, Any]]:
        """
        Perform a health check and return the results.

        Returns:
            Dict containing health data, or None if check failed
        """
        url = f"http://{self.host}:{self.port}{self.api_path}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logger.warning(f"Health check failed with status code: {response.status_code}")
                self.issues.append({
                    "time": time.time(),
                    "type": "http_error",
                    "message": f"HTTP status code {response.status_code}"
                })
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error connecting to health endpoint: {e}")
            self.issues.append({
                "time": time.time(),
                "type": "connection_error",
                "message": str(e)
            })
            return None

    def analyze_health_data(self, data: Dict[str, Any]) -> None:
        """
        Analyze health data and update monitoring state.

        Args:
            data: Health data from API
        """
        # Extract key metrics
        deployment_mode = data.get("mode", "unknown")
        status = data.get("status", "unknown")

        # Get traffic split if available
        traffic_split = data.get("traffic_split", {})
        blue_percentage = traffic_split.get("blue_percentage", 0)
        green_percentage = traffic_split.get("green_percentage", 0)

        # Get server health
        components = data.get("components", {})
        blue_healthy = components.get("blue", {}).get("success", False)
        green_healthy = components.get("green", {}).get("success", False)

        # Get performance metrics
        metrics = data.get("metrics", {})
        blue_metrics = metrics.get("blue", {})
        green_metrics = metrics.get("green", {})

        blue_success_rate = blue_metrics.get("success_rate", 0)
        green_success_rate = green_metrics.get("success_rate", 0)

        blue_response_time = blue_metrics.get("avg_response_time", 0)
        green_response_time = green_metrics.get("avg_response_time", 0)

        # Get validation stats
        validation = data.get("validation", {})
        compatible_rate = validation.get("compatible_rate", 0)
        critical_diff_rate = validation.get("critical_difference_rate", 0)

        # Record sample
        sample = {
            "time": time.time(),
            "mode": deployment_mode,
            "status": status,
            "blue_percentage": blue_percentage,
            "green_percentage": green_percentage,
            "blue_healthy": blue_healthy,
            "green_healthy": green_healthy,
            "blue_success_rate": blue_success_rate,
            "green_success_rate": green_success_rate,
            "blue_response_time": blue_response_time,
            "green_response_time": green_response_time,
            "compatible_rate": compatible_rate,
            "critical_diff_rate": critical_diff_rate
        }

        self.samples.append(sample)

        # Check for issues
        if status != "healthy":
            self.issues.append({
                "time": time.time(),
                "type": "unhealthy_status",
                "message": f"Deployment status is {status}"
            })

        if not blue_healthy and deployment_mode in ["blue", "gradual", "auto"]:
            self.issues.append({
                "time": time.time(),
                "type": "blue_unhealthy",
                "message": "Blue server is unhealthy but is part of active deployment"
            })

        if not green_healthy and deployment_mode in ["green", "gradual", "auto"]:
            self.issues.append({
                "time": time.time(),
                "type": "green_unhealthy",
                "message": "Green server is unhealthy but is part of active deployment"
            })

        if blue_success_rate < 99 and deployment_mode in ["blue", "gradual", "auto"]:
            self.issues.append({
                "time": time.time(),
                "type": "low_blue_success_rate",
                "message": f"Blue success rate is {blue_success_rate}%, below 99%"
            })

        if green_success_rate < 99 and deployment_mode in ["green", "gradual", "auto"]:
            self.issues.append({
                "time": time.time(),
                "type": "low_green_success_rate",
                "message": f"Green success rate is {green_success_rate}%, below 99%"
            })

        if critical_diff_rate > 1:
            self.issues.append({
                "time": time.time(),
                "type": "high_critical_diff_rate",
                "message": f"Critical difference rate is {critical_diff_rate}%, above 1%"
            })

    def run_monitoring(self, duration: int, threshold: float = 99.0) -> bool:
        """
        Run monitoring for the specified duration.

        Args:
            duration: Monitoring duration in minutes
            threshold: Success threshold percentage

        Returns:
            True if deployment meets success criteria, False otherwise
        """
        end_time = time.time() + (duration * 60)
        logger.info(f"Starting monitoring for {duration} minutes")

        while time.time() < end_time:
            # Check health
            data = self.check_health()

            if data:
                self.analyze_health_data(data)
                logger.info(f"Health check successful: {data.get('status', 'unknown')} mode={data.get('mode', 'unknown')}")
            else:
                logger.warning("Health check failed")

            # Sleep until next check
            if time.time() < end_time:
                time.sleep(self.poll_interval)

        # Generate summary
        success = self.generate_summary()

        # Determine if deployment meets success criteria
        if self.summary["availability"] < threshold:
            logger.error(f"Deployment failed: availability {self.summary['availability']}% below threshold {threshold}%")
            return False

        if self.summary["issues_detected"] > 0:
            logger.warning(f"Deployment has {self.summary['issues_detected']} issues")
            # Don't fail the build for warnings, but log them

        logger.info(f"Deployment monitoring complete: availability {self.summary['availability']}%")
        return success

    def generate_summary(self) -> bool:
        """
        Generate summary statistics from collected samples.

        Returns:
            True if the deployment is considered successful, False otherwise
        """
        self.summary["end_time"] = time.time()
        self.summary["duration"] = self.summary["end_time"] - self.summary["start_time"]
        self.summary["total_samples"] = len(self.samples)
        self.summary["successful_samples"] = sum(1 for s in self.samples if s["status"] == "healthy")
        self.summary["failures"] = self.summary["total_samples"] - self.summary["successful_samples"]

        if self.summary["total_samples"] > 0:
            self.summary["availability"] = (self.summary["successful_samples"] / self.summary["total_samples"]) * 100

            # Calculate average metrics
            self.summary["avg_blue_response_time"] = sum(s["blue_response_time"] for s in self.samples) / self.summary["total_samples"]
            self.summary["avg_green_response_time"] = sum(s["green_response_time"] for s in self.samples) / self.summary["total_samples"]
            self.summary["compatibility_rate"] = sum(s["compatible_rate"] for s in self.samples) / self.summary["total_samples"]

        self.summary["issues_detected"] = len(self.issues)

        # Save results
        self.save_results()

        # Print summary
        self._print_summary()

        # Return success/failure
        return self.summary["availability"] >= 99.0 and self.summary["issues_detected"] == 0

    def save_results(self) -> None:
        """Save monitoring results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save summary
        summary_file = self.output_dir / f"summary_{self.environment}_{timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(self.summary, f, indent=2)

        # Save samples
        samples_file = self.output_dir / f"samples_{self.environment}_{timestamp}.json"
        with open(samples_file, "w") as f:
            json.dump(self.samples, f, indent=2)

        # Save issues
        if self.issues:
            issues_file = self.output_dir / f"issues_{self.environment}_{timestamp}.json"
            with open(issues_file, "w") as f:
                json.dump(self.issues, f, indent=2)

        logger.info(f"Results saved to {self.output_dir}")

    def _print_summary(self) -> None:
        """Print summary information to console."""
        duration_min = self.summary["duration"] / 60

        print("\n" + "=" * 50)
        print(f"DEPLOYMENT MONITORING SUMMARY: {self.environment.upper()}")
        print("=" * 50)
        print(f"Duration: {duration_min:.1f} minutes")
        print(f"Total Samples: {self.summary['total_samples']}")
        print(f"Availability: {self.summary['availability']:.2f}%")
        print(f"Issues Detected: {self.summary['issues_detected']}")
        print(f"Blue Avg Response Time: {self.summary['avg_blue_response_time']*1000:.2f} ms")
        print(f"Green Avg Response Time: {self.summary['avg_green_response_time']*1000:.2f} ms")
        print(f"Compatibility Rate: {self.summary['compatibility_rate']:.2f}%")
        print("=" * 50)

        if self.issues:
            print("\nISSUES DETECTED:")
            for i, issue in enumerate(self.issues[:5]):  # Show first 5 issues
                issue_time = datetime.fromtimestamp(issue["time"]).strftime("%H:%M:%S")
                print(f"  {i+1}. [{issue_time}] {issue['type']}: {issue['message']}")

            if len(self.issues) > 5:
                print(f"  ... and {len(self.issues) - 5} more issues")

        print("\n")

def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(description="Monitor MCP Blue/Green Deployment")
    parser.add_argument("--environment", "-e", default="staging",
                      choices=["dev", "staging", "production", "local"],
                      help="Deployment environment")
    parser.add_argument("--host", help="Host address for proxy service")
    parser.add_argument("--port", type=int, default=8090, help="Port for proxy API")
    parser.add_argument("--duration", "-d", type=int, default=15,
                      help="Monitoring duration in minutes")
    parser.add_argument("--interval", "-i", type=int, default=10,
                      help="Polling interval in seconds")
    parser.add_argument("--output-dir", "-o", default="./monitoring_results",
                      help="Output directory for results")
    parser.add_argument("--threshold", "-t", type=float, default=99.0,
                      help="Success threshold percentage")

    args = parser.parse_args()

    # Create monitor
    monitor = DeploymentMonitor(
        environment=args.environment,
        host=args.host,
        port=args.port,
        output_dir=args.output_dir,
        poll_interval=args.interval
    )

    # Run monitoring
    success = monitor.run_monitoring(
        duration=args.duration,
        threshold=args.threshold
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
