#!/usr/bin/env python3
"""
MCP Blue/Green Deployment Performance Report Generator

This script analyzes the monitoring data from the blue/green deployment
and generates a comprehensive report with charts and metrics to assess
the deployment's success and performance.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("performance_report")

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    logger.warning("Plotting dependencies not available. Install with: pip install pandas matplotlib numpy")
    PLOTTING_AVAILABLE = False

class PerformanceReportGenerator:
    """Generate performance reports from blue/green deployment monitoring data."""
    
    def __init__(
        self,
        environment: str,
        monitoring_dir: str = "./monitoring_results",
        output_dir: str = "./performance_charts",
        output_file: str = "monitoring_report.md"
    ):
        """
        Initialize the report generator.
        
        Args:
            environment: Deployment environment (dev, staging, production)
            monitoring_dir: Directory containing monitoring results
            output_dir: Directory to save charts
            output_file: Output file path for the report
        """
        self.environment = environment
        self.monitoring_dir = Path(monitoring_dir)
        self.output_dir = Path(output_dir)
        self.output_file = output_file
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize data containers
        self.summary = None
        self.samples = []
        self.issues = []
        
        # Load data
        self._load_latest_data()
    
    def _load_latest_data(self) -> None:
        """Load the latest monitoring data."""
        # Find the latest summary file
        summary_files = list(self.monitoring_dir.glob(f"summary_{self.environment}_*.json"))
        if not summary_files:
            logger.error(f"No summary files found for environment: {self.environment}")
            return
        
        latest_summary_file = max(summary_files, key=os.path.getmtime)
        logger.info(f"Loading summary from: {latest_summary_file}")
        
        # Load summary
        with open(latest_summary_file, "r") as f:
            self.summary = json.load(f)
        
        # Extract timestamp from filename
        timestamp = latest_summary_file.name.split("_", 2)[2].replace(".json", "")
        
        # Load samples
        samples_file = self.monitoring_dir / f"samples_{self.environment}_{timestamp}.json"
        if samples_file.exists():
            with open(samples_file, "r") as f:
                self.samples = json.load(f)
            logger.info(f"Loaded {len(self.samples)} samples from: {samples_file}")
        
        # Load issues
        issues_file = self.monitoring_dir / f"issues_{self.environment}_{timestamp}.json"
        if issues_file.exists():
            with open(issues_file, "r") as f:
                self.issues = json.load(f)
            logger.info(f"Loaded {len(self.issues)} issues from: {issues_file}")
    
    def generate_report(self) -> bool:
        """
        Generate the performance report.
        
        Returns:
            True if the report was generated successfully, False otherwise
        """
        if not self.summary:
            logger.error("No summary data available. Cannot generate report.")
            return False
        
        # Create report sections
        sections = []
        
        # Add header
        sections.append(self._generate_header())
        
        # Add summary section
        sections.append(self._generate_summary_section())
        
        # Add traffic distribution section
        sections.append(self._generate_traffic_section())
        
        # Add performance comparison section
        sections.append(self._generate_performance_section())
        
        # Add compatibility section
        sections.append(self._generate_compatibility_section())
        
        # Add issues section
        sections.append(self._generate_issues_section())
        
        # Add recommendations section
        sections.append(self._generate_recommendations())
        
        # Generate charts if plotting is available
        if PLOTTING_AVAILABLE and self.samples:
            self._generate_charts()
            sections.append(self._generate_charts_section())
        
        # Write report
        with open(self.output_file, "w") as f:
            f.write("\n\n".join(sections))
        
        logger.info(f"Report generated: {self.output_file}")
        return True
    
    def _generate_header(self) -> str:
        """Generate the report header."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration_min = self.summary["duration"] / 60
        
        return f"""# MCP Blue/Green Deployment Performance Report

## Overview

- **Environment:** {self.environment.upper()}
- **Report Generated:** {timestamp}
- **Monitoring Duration:** {duration_min:.1f} minutes
- **Deployment Mode:** {self.samples[-1]["mode"] if self.samples else "Unknown"}
"""
    
    def _generate_summary_section(self) -> str:
        """Generate the summary section."""
        return f"""## Performance Summary

| Metric | Value |
| ------ | ----- |
| **Availability** | {self.summary["availability"]:.2f}% |
| **Issues Detected** | {self.summary["issues_detected"]} |
| **Blue Response Time** | {self.summary["avg_blue_response_time"]*1000:.2f} ms |
| **Green Response Time** | {self.summary["avg_green_response_time"]*1000:.2f} ms |
| **Compatibility Rate** | {self.summary["compatibility_rate"]:.2f}% |
| **Samples Collected** | {self.summary["total_samples"]} |

Overall Status: **{"SUCCESS" if self.summary["availability"] >= 99.0 and self.summary["issues_detected"] == 0 else "WARNING" if self.summary["availability"] >= 95.0 else "FAILURE"}**
"""
    
    def _generate_traffic_section(self) -> str:
        """Generate the traffic distribution section."""
        if not self.samples:
            return "## Traffic Distribution\n\nNo traffic data available."
        
        # Get final traffic split
        final_sample = self.samples[-1]
        blue_pct = final_sample["blue_percentage"]
        green_pct = final_sample["green_percentage"]
        
        return f"""## Traffic Distribution

Final traffic split:
- **Blue:** {blue_pct}%
- **Green:** {green_pct}%

The deployment was running in **{final_sample["mode"].upper()}** mode during the monitoring period.
"""
    
    def _generate_performance_section(self) -> str:
        """Generate the performance comparison section."""
        if not self.samples:
            return "## Performance Comparison\n\nNo performance data available."
        
        # Calculate performance comparison
        blue_times = [s["blue_response_time"]*1000 for s in self.samples]
        green_times = [s["green_response_time"]*1000 for s in self.samples]
        
        blue_avg = sum(blue_times) / len(blue_times)
        green_avg = sum(green_times) / len(green_times)
        
        blue_success_rates = [s["blue_success_rate"] for s in self.samples]
        green_success_rates = [s["green_success_rate"] for s in self.samples]
        
        blue_success_avg = sum(blue_success_rates) / len(blue_success_rates)
        green_success_avg = sum(green_success_rates) / len(green_success_rates)
        
        performance_diff = ((green_avg - blue_avg) / blue_avg) * 100 if blue_avg > 0 else 0
        performance_comparison = "faster" if performance_diff < 0 else "slower"
        
        return f"""## Performance Comparison

### Response Times

| Variant | Average | Min | Max |
| ------- | ------- | --- | --- |
| **Blue** | {blue_avg:.2f} ms | {min(blue_times):.2f} ms | {max(blue_times):.2f} ms |
| **Green** | {green_avg:.2f} ms | {min(green_times):.2f} ms | {max(green_times):.2f} ms |

The Green implementation is **{abs(performance_diff):.1f}%** {performance_comparison} than the Blue implementation.

### Success Rates

| Variant | Average Success Rate |
| ------- | -------------------- |
| **Blue** | {blue_success_avg:.2f}% |
| **Green** | {green_success_avg:.2f}% |

The difference in success rates is **{abs(green_success_avg - blue_success_avg):.2f}%** ({"favorable" if green_success_avg >= blue_success_avg else "unfavorable"} to Green).
"""
    
    def _generate_compatibility_section(self) -> str:
        """Generate the compatibility section."""
        if not self.samples:
            return "## Response Compatibility\n\nNo compatibility data available."
        
        # Calculate compatibility metrics
        compatible_rates = [s["compatible_rate"] for s in self.samples]
        critical_diff_rates = [s["critical_diff_rate"] for s in self.samples]
        
        compatible_avg = sum(compatible_rates) / len(compatible_rates)
        critical_diff_avg = sum(critical_diff_rates) / len(critical_diff_rates)
        
        compatibility_status = "HIGH" if compatible_avg >= 99 else "MEDIUM" if compatible_avg >= 95 else "LOW"
        
        return f"""## Response Compatibility

| Metric | Value | Status |
| ------ | ----- | ------ |
| **Compatible Responses** | {compatible_avg:.2f}% | {compatibility_status} |
| **Critical Differences** | {critical_diff_avg:.2f}% | {"ACCEPTABLE" if critical_diff_avg <= 1 else "CONCERNING" if critical_diff_avg <= 5 else "CRITICAL"} |

Compatibility between Blue and Green implementations is **{compatibility_status}**.
"""
    
    def _generate_issues_section(self) -> str:
        """Generate the issues section."""
        if not self.issues:
            return "## Issues Detected\n\nNo issues were detected during the monitoring period."
        
        # Count issues by type
        issue_counts = {}
        for issue in self.issues:
            issue_type = issue["type"]
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        issues_table = "\n".join(f"| **{issue_type}** | {count} |" for issue_type, count in issue_counts.items())
        
        return f"""## Issues Detected

A total of **{len(self.issues)}** issues were detected during the monitoring period.

| Issue Type | Count |
| ---------- | ----- |
{issues_table}

### Most Recent Issues

{self._format_recent_issues()}
"""
    
    def _format_recent_issues(self) -> str:
        """Format the most recent issues for the report."""
        if not self.issues:
            return "No issues detected."
        
        # Sort issues by time (newest first)
        sorted_issues = sorted(self.issues, key=lambda x: x["time"], reverse=True)
        
        # Format the 5 most recent issues
        issue_texts = []
        for i, issue in enumerate(sorted_issues[:5]):
            issue_time = datetime.fromtimestamp(issue["time"]).strftime("%Y-%m-%d %H:%M:%S")
            issue_texts.append(f"{i+1}. **[{issue_time}]** {issue['type']}: {issue['message']}")
        
        return "\n".join(issue_texts)
    
    def _generate_recommendations(self) -> str:
        """Generate recommendations based on the monitoring data."""
        if not self.samples:
            return "## Recommendations\n\nInsufficient data to make recommendations."
        
        # Determine deployment mode
        mode = self.samples[-1]["mode"]
        
        # Get final metrics
        final_sample = self.samples[-1]
        blue_healthy = final_sample["blue_healthy"]
        green_healthy = final_sample["green_healthy"]
        blue_success_rate = final_sample["blue_success_rate"]
        green_success_rate = final_sample["green_success_rate"]
        compatible_rate = final_sample["compatible_rate"]
        critical_diff_rate = final_sample["critical_diff_rate"]
        
        # Determine health status
        blue_health_status = "HEALTHY" if blue_healthy and blue_success_rate >= 99 else "DEGRADED" if blue_healthy else "UNHEALTHY"
        green_health_status = "HEALTHY" if green_healthy and green_success_rate >= 99 else "DEGRADED" if green_healthy else "UNHEALTHY"
        
        # Make recommendations based on current state
        recommendations = []
        
        if mode == "blue":
            if green_health_status == "HEALTHY" and compatible_rate >= 99 and critical_diff_rate <= 0.1:
                recommendations.append("Consider starting gradual migration to Green with a small percentage (5-10%).")
            else:
                recommendations.append("Continue running on Blue while addressing Green implementation issues.")
                
                if not green_healthy:
                    recommendations.append("- Fix health issues with Green implementation.")
                if compatible_rate < 99:
                    recommendations.append("- Improve response compatibility between implementations.")
                if critical_diff_rate > 0.1:
                    recommendations.append("- Address critical differences in responses.")
        
        elif mode == "green":
            if green_health_status != "HEALTHY":
                recommendations.append("Consider rolling back to Blue implementation due to Green health issues.")
            else:
                recommendations.append("Green implementation is performing well. Continue monitoring.")
        
        elif mode == "gradual":
            green_pct = final_sample["green_percentage"]
            
            if green_health_status == "HEALTHY" and compatible_rate >= 99 and critical_diff_rate <= 0.1:
                if green_pct < 50:
                    recommendations.append(f"Green implementation is healthy. Consider increasing traffic to 50%.")
                elif green_pct < 100:
                    recommendations.append(f"Green implementation is performing well. Consider completing migration (100%).")
                else:
                    recommendations.append("Migration complete. Consider switching to Green mode.")
            elif green_health_status != "HEALTHY":
                recommendations.append("Green implementation has health issues. Consider reducing traffic or rolling back.")
            else:
                recommendations.append("Monitor current split while addressing minor issues.")
        
        elif mode == "auto":
            recommendations.append("Auto mode is actively managing traffic. Continue monitoring for stability.")
            
            if green_health_status != "HEALTHY":
                recommendations.append("Address Green implementation health issues.")
            if blue_health_status != "HEALTHY":
                recommendations.append("Address Blue implementation health issues.")
        
        return f"""## Recommendations

Based on the current deployment state:

- Blue Implementation: **{blue_health_status}**
- Green Implementation: **{green_health_status}**

### Recommended Actions

{chr(10).join(f"- {rec}" for rec in recommendations)}
"""
    
    def _generate_charts_section(self) -> str:
        """Generate the charts section with references to the generated charts."""
        return f"""## Performance Charts

### Traffic Distribution
![Traffic Distribution](performance_charts/traffic_distribution.png)

### Response Times
![Response Times](performance_charts/response_times.png)

### Success Rates
![Success Rates](performance_charts/success_rates.png)

### Compatibility Rates
![Compatibility](performance_charts/compatibility.png)
"""
    
    def _generate_charts(self) -> None:
        """Generate performance charts from the monitoring data."""
        if not PLOTTING_AVAILABLE or not self.samples:
            logger.warning("Cannot generate charts: Plotting libraries not available or no samples.")
            return
        
        # Convert samples to pandas DataFrame for easier plotting
        data = []
        for sample in self.samples:
            data.append({
                'timestamp': datetime.fromtimestamp(sample['time']),
                'blue_percentage': sample['blue_percentage'],
                'green_percentage': sample['green_percentage'],
                'blue_response_time': sample['blue_response_time'] * 1000,  # Convert to ms
                'green_response_time': sample['green_response_time'] * 1000,
                'blue_success_rate': sample['blue_success_rate'],
                'green_success_rate': sample['green_success_rate'],
                'compatible_rate': sample['compatible_rate'],
                'critical_diff_rate': sample['critical_diff_rate']
            })
        
        df = pd.DataFrame(data)
        
        # Set style for plots
        plt.style.use('ggplot')
        
        # Create traffic distribution chart
        self._create_traffic_chart(df)
        
        # Create response times chart
        self._create_response_time_chart(df)
        
        # Create success rates chart
        self._create_success_rate_chart(df)
        
        # Create compatibility chart
        self._create_compatibility_chart(df)
    
    def _create_traffic_chart(self, df: 'pd.DataFrame') -> None:
        """Create traffic distribution chart."""
        plt.figure(figsize=(10, 6))
        plt.stackplot(df['timestamp'], df['blue_percentage'], df['green_percentage'],
                     labels=['Blue', 'Green'], colors=['#1f77b4', '#2ca02c'])
        plt.xlabel('Time')
        plt.ylabel('Traffic Percentage')
        plt.title('Traffic Distribution Over Time')
        plt.legend(loc='upper left')
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.tight_layout()
        plt.savefig(self.output_dir / 'traffic_distribution.png')
        plt.close()
    
    def _create_response_time_chart(self, df: 'pd.DataFrame') -> None:
        """Create response times chart."""
        plt.figure(figsize=(10, 6))
        plt.plot(df['timestamp'], df['blue_response_time'], 'b-', label='Blue')
        plt.plot(df['timestamp'], df['green_response_time'], 'g-', label='Green')
        plt.xlabel('Time')
        plt.ylabel('Response Time (ms)')
        plt.title('Response Times Over Time')
        plt.legend()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.tight_layout()
        plt.savefig(self.output_dir / 'response_times.png')
        plt.close()
    
    def _create_success_rate_chart(self, df: 'pd.DataFrame') -> None:
        """Create success rates chart."""
        plt.figure(figsize=(10, 6))
        plt.plot(df['timestamp'], df['blue_success_rate'], 'b-', label='Blue')
        plt.plot(df['timestamp'], df['green_success_rate'], 'g-', label='Green')
        plt.xlabel('Time')
        plt.ylabel('Success Rate (%)')
        plt.title('Success Rates Over Time')
        plt.ylim(90, 100.5)  # Focus on the important range
        plt.legend()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.tight_layout()
        plt.savefig(self.output_dir / 'success_rates.png')
        plt.close()
    
    def _create_compatibility_chart(self, df: 'pd.DataFrame') -> None:
        """Create compatibility chart."""
        plt.figure(figsize=(10, 6))
        plt.plot(df['timestamp'], df['compatible_rate'], 'b-', label='Compatible Rate')
        plt.plot(df['timestamp'], df['critical_diff_rate'], 'r-', label='Critical Diff Rate')
        plt.xlabel('Time')
        plt.ylabel('Rate (%)')
        plt.title('Response Compatibility Over Time')
        plt.legend()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.tight_layout()
        plt.savefig(self.output_dir / 'compatibility.png')
        plt.close()

def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(description="Generate MCP Blue/Green Performance Report")
    parser.add_argument("--environment", "-e", default="staging",
                      choices=["dev", "staging", "production", "local"],
                      help="Deployment environment")
    parser.add_argument("--monitoring-dir", "-m", default="./monitoring_results",
                      help="Directory containing monitoring results")
    parser.add_argument("--output-dir", "-d", default="./performance_charts",
                      help="Directory to save charts")
    parser.add_argument("--output", "-o", default="monitoring_report.md",
                      help="Output markdown report file")
    
    args = parser.parse_args()
    
    # Create report generator
    generator = PerformanceReportGenerator(
        environment=args.environment,
        monitoring_dir=args.monitoring_dir,
        output_dir=args.output_dir,
        output_file=args.output
    )
    
    # Generate report
    success = generator.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()