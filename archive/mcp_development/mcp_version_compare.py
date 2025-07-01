#!/usr/bin/env python3
"""
Version comparison tool for MCP servers.

This tool helps compare different versions of MCP servers to identify
compatibility issues, missing tools, or performance differences.
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
import subprocess
from typing import Dict, Any, List, Optional, Set
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("version_compare.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("version_compare")

class VersionComparer:
    """Tool for comparing different MCP server versions."""
    
    def __init__(self):
        """Initialize the version comparer."""
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "versions": [],
            "comparison": {
                "tools": {},
                "performance": {},
                "tests": {}
            }
        }
    
    def add_version(self, version_name: str, server_file: str, port: int, results_file: str) -> None:
        """Add a version to the comparison.
        
        Args:
            version_name: The name of the version
            server_file: The path to the server file
            port: The port to run the server on
            results_file: The path to the test results file
        """
        logger.info(f"Adding version '{version_name}' to comparison")
        
        # Start the server and run tests
        try:
            # Use the start_final_solution.sh script to run tests
            cmd = [
                "/bin/bash", 
                "start_final_solution.sh", 
                "--server-file", server_file, 
                "--port", str(port),
                "--verify"
            ]
            logger.info(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            
            # Load the test results
            with open(results_file, 'r') as f:
                results = json.load(f)
            
            self.results["versions"].append({
                "name": version_name,
                "server_file": server_file,
                "port": port,
                "results_file": results_file,
                "test_results": results
            })
            
            logger.info(f"Added version '{version_name}' to comparison")
        except Exception as e:
            logger.error(f"Error adding version '{version_name}': {e}")
            raise
    
    def compare_versions(self) -> Dict[str, Any]:
        """Compare the added versions.
        
        Returns:
            A dictionary with comparison results
        """
        if len(self.results["versions"]) < 2:
            logger.error("Need at least two versions to compare")
            return self.results
        
        logger.info("Comparing versions...")
        
        # Compare available tools
        self._compare_tools()
        
        # Compare test results
        self._compare_tests()
        
        # Compare performance
        self._compare_performance()
        
        return self.results
    
    def _compare_tools(self) -> None:
        """Compare available tools between versions."""
        all_tools: Set[str] = set()
        version_tools: Dict[str, Set[str]] = {}
        
        # Collect all tools from all versions
        for version in self.results["versions"]:
            version_name = version["name"]
            version_tools[version_name] = set()
            
            # Extract the list of tools from the test results
            if "available_tools" in version["test_results"]:
                tools = version["test_results"]["available_tools"]
                version_tools[version_name] = set(tools)
                all_tools.update(tools)
            else:
                logger.warning(f"No available_tools found in test results for version {version_name}")
        
        # Compare tool availability across versions
        for tool in sorted(all_tools):
            missing_in = []
            available_in = []
            
            for version_name, tools in version_tools.items():
                if tool in tools:
                    available_in.append(version_name)
                else:
                    missing_in.append(version_name)
            
            if missing_in:
                self.results["comparison"]["tools"][tool] = {
                    "available_in": available_in,
                    "missing_in": missing_in
                }
    
    def _compare_tests(self) -> None:
        """Compare test results between versions."""
        all_tests: Set[str] = set()
        version_tests: Dict[str, Dict[str, str]] = {}
        
        # Collect all tests from all versions
        for version in self.results["versions"]:
            version_name = version["name"]
            version_tests[version_name] = {}
            
            # Extract test results
            if "tests" in version["test_results"]:
                tests = version["test_results"]["tests"]
                for test in tests:
                    if "name" in test and "status" in test:
                        all_tests.add(test["name"])
                        version_tests[version_name][test["name"]] = test["status"]
            else:
                logger.warning(f"No tests found in test results for version {version_name}")
        
        # Compare test results across versions
        for test in sorted(all_tests):
            results = {}
            has_differences = False
            
            for version_name, tests in version_tests.items():
                results[version_name] = tests.get(test, "UNKNOWN")
            
            # Check if there are differences
            statuses = set(results.values())
            if len(statuses) > 1:
                has_differences = True
            
            if has_differences:
                self.results["comparison"]["tests"][test] = results
    
    def _compare_performance(self) -> None:
        """Compare performance metrics between versions."""
        metrics = [
            "test_duration", 
            "server_start_time", 
            "average_response_time"
        ]
        
        for metric in metrics:
            values = {}
            for version in self.results["versions"]:
                version_name = version["name"]
                
                if metric in version["test_results"]:
                    values[version_name] = version["test_results"][metric]
            
            if values:
                self.results["comparison"]["performance"][metric] = values
    
    def save_results(self, output_file: str) -> None:
        """Save the comparison results to a file.
        
        Args:
            output_file: The path to the output file
        """
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Comparison results saved to {output_file}")
    
    def generate_markdown_report(self, output_file: str) -> None:
        """Generate a markdown report from the comparison results.
        
        Args:
            output_file: The path to the output file
        """
        with open(output_file, 'w') as f:
            # Write header
            f.write("# MCP Server Version Comparison\n\n")
            f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Write version information
            f.write("## Versions\n\n")
            for version in self.results["versions"]:
                f.write(f"### {version['name']}\n")
                f.write(f"- Server file: `{version['server_file']}`\n")
                f.write(f"- Port: {version['port']}\n")
                f.write(f"- Results file: `{version['results_file']}`\n\n")
            
            # Write tool comparison
            f.write("## Tool Comparison\n\n")
            if not self.results["comparison"]["tools"]:
                f.write("No tool differences found.\n\n")
            else:
                f.write("| Tool | Available In | Missing In |\n")
                f.write("|------|--------------|------------|\n")
                
                for tool, info in self.results["comparison"]["tools"].items():
                    available_in = ", ".join(info["available_in"])
                    missing_in = ", ".join(info["missing_in"])
                    f.write(f"| `{tool}` | {available_in} | {missing_in} |\n")
                
                f.write("\n")
            
            # Write test comparison
            f.write("## Test Result Comparison\n\n")
            if not self.results["comparison"]["tests"]:
                f.write("No test result differences found.\n\n")
            else:
                # Create the header row
                header = "| Test |"
                separator = "|------|"
                
                for version in self.results["versions"]:
                    header += f" {version['name']} |"
                    separator += "----------|"
                
                f.write(header + "\n")
                f.write(separator + "\n")
                
                # Write test results
                for test, results in self.results["comparison"]["tests"].items():
                    row = f"| `{test}` |"
                    
                    for version in self.results["versions"]:
                        status = results.get(version["name"], "UNKNOWN")
                        
                        # Add color formatting based on status
                        if status == "PASS":
                            row += " ✅ PASS |"
                        elif status == "FAIL":
                            row += " ❌ FAIL |"
                        elif status == "SKIP":
                            row += " ⚠️ SKIP |"
                        else:
                            row += f" {status} |"
                    
                    f.write(row + "\n")
                
                f.write("\n")
            
            # Write performance comparison
            f.write("## Performance Comparison\n\n")
            if not self.results["comparison"]["performance"]:
                f.write("No performance metrics available for comparison.\n\n")
            else:
                # Create the header row
                header = "| Metric |"
                separator = "|--------|"
                
                for version in self.results["versions"]:
                    header += f" {version['name']} |"
                    separator += "----------|"
                
                f.write(header + "\n")
                f.write(separator + "\n")
                
                # Write performance metrics
                for metric, values in self.results["comparison"]["performance"].items():
                    row = f"| {metric} |"
                    
                    for version in self.results["versions"]:
                        value = values.get(version["name"], "N/A")
                        row += f" {value} |"
                    
                    f.write(row + "\n")
                
                f.write("\n")
            
            # Write recommendations
            f.write("## Recommendations\n\n")
            
            # Check for missing tools
            missing_tools = self.results["comparison"]["tools"]
            if missing_tools:
                f.write("### Missing Tools\n\n")
                for tool, info in missing_tools.items():
                    f.write(f"- The tool `{tool}` is available in {', '.join(info['available_in'])} ")
                    f.write(f"but missing in {', '.join(info['missing_in'])}.\n")
                f.write("\n")
            
            # Check for failing tests
            failing_tests = {}
            for test, results in self.results["comparison"]["tests"].items():
                for version, status in results.items():
                    if status == "FAIL":
                        if test not in failing_tests:
                            failing_tests[test] = []
                        failing_tests[test].append(version)
            
            if failing_tests:
                f.write("### Failing Tests\n\n")
                for test, versions in failing_tests.items():
                    f.write(f"- The test `{test}` is failing in {', '.join(versions)}.\n")
                f.write("\n")
            
            # General recommendations
            f.write("### General Recommendations\n\n")
            f.write("1. Ensure all required tools are available in all versions.\n")
            f.write("2. Fix any failing tests.\n")
            f.write("3. Ensure consistent behavior across versions.\n")
            
        logger.info(f"Markdown report generated at {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare different versions of MCP servers")
    parser.add_argument("--v1-name", required=True, help="Name of the first version")
    parser.add_argument("--v1-file", required=True, help="Server file for the first version")
    parser.add_argument("--v1-port", type=int, default=9996, help="Port for the first version")
    parser.add_argument("--v1-results", default="v1_results.json", help="Results file for the first version")
    
    parser.add_argument("--v2-name", required=True, help="Name of the second version")
    parser.add_argument("--v2-file", required=True, help="Server file for the second version")
    parser.add_argument("--v2-port", type=int, default=9997, help="Port for the second version")
    parser.add_argument("--v2-results", default="v2_results.json", help="Results file for the second version")
    
    parser.add_argument("--output-json", default="version_comparison.json", help="Output JSON file")
    parser.add_argument("--output-md", default="version_comparison.md", help="Output markdown file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create the version comparer
    comparer = VersionComparer()
    
    try:
        # Add the first version
        comparer.add_version(
            args.v1_name,
            args.v1_file,
            args.v1_port,
            args.v1_results
        )
        
        # Add the second version
        comparer.add_version(
            args.v2_name,
            args.v2_file,
            args.v2_port,
            args.v2_results
        )
        
        # Compare versions
        comparison = comparer.compare_versions()
        
        # Save results
        comparer.save_results(args.output_json)
        
        # Generate markdown report
        comparer.generate_markdown_report(args.output_md)
        
        logger.info("Comparison complete")
        return 0
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
