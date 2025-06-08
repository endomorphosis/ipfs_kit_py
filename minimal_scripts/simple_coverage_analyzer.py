#!/usr/bin/env python3
"""
IPFS Kit Coverage Analyzer

This script analyzes the coverage of IPFS Kit functionality in the MCP tools:
1. Fetches available MCP tools from the server
2. Identifies which IPFS kit functions are exposed as MCP tools
3. Generates a report on coverage

Usage:
  python3 ipfs_kit_coverage_analyzer.py --server-url http://localhost:9996 [--verbose]
"""

import argparse
import json
import os
import sys
import time
import requests
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ipfs_kit_coverage_analyzer")

# Constants
MCP_PORT_DEFAULT = 9996
REPORT_FILE = "ipfs_coverage_report.json"

class IPFSKitCoverageAnalyzer:
    """Analyzer for IPFS Kit coverage in MCP tools."""
    
    def __init__(self, server_url: str, verbose: bool = False):
        """Initialize the analyzer.
        
        Args:
            server_url: The base URL of the MCP server
            verbose: Whether to output verbose logs
        """
        self.server_url = server_url
        self.verbose = verbose
        self.mcp_tools = {}
        
        # Set up logging
        if verbose:
            logger.setLevel(logging.DEBUG)
        
    def fetch_mcp_tools(self) -> None:
        """Fetch all MCP tools from the server."""
        logger.info("Fetching MCP tools from server...")
        port = MCP_PORT_DEFAULT
        
        try:
            # Use the list_tools method to get available tools
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "list_tools",
                "params": {}
            }
            
            # Make the request
            response = requests.post(f"{self.server_url}/jsonrpc", json=list_tools_request)
            response.raise_for_status()
            
            result = response.json()
            if 'result' in result and 'tools' in result['result']:
                tools = result['result']['tools']
                logger.info(f"Found {len(tools)} tools from list_tools method")
                
                for tool in tools:
                    if isinstance(tool, dict):
                        tool_name = tool.get("name", "")
                        self.mcp_tools[tool_name] = {
                            "name": tool_name,
                            "description": tool.get("description", ""),
                            "schema": tool.get("schema", {})
                        }
                    elif isinstance(tool, str):
                        self.mcp_tools[tool] = {
                            "name": tool,
                            "description": f"Tool: {tool}"
                        }
                
                logger.info(f"Fetched {len(self.mcp_tools)} MCP tools successfully")
            else:
                logger.warning("No tools found in response")
                
        except Exception as e:
            logger.error(f"Failed to fetch MCP tools: {str(e)}")
    
    def categorize_tools(self) -> Dict[str, List[str]]:
        """Categorize tools by their type.
        
        Returns:
            A dictionary of tool categories and their tools
        """
        categories = {
            "core": [],
            "vfs": [],
            "ipfs": [],
            "mfs": [],
            "other": []
        }
        
        for tool_name in self.mcp_tools:
            if tool_name.startswith("vfs_"):
                categories["vfs"].append(tool_name)
            elif tool_name.startswith("ipfs_files_"):
                categories["mfs"].append(tool_name)
            elif tool_name.startswith("ipfs_"):
                categories["ipfs"].append(tool_name)
            elif tool_name in ["ping", "health", "list_tools", "server_info", "initialize"]:
                categories["core"].append(tool_name)
            else:
                categories["other"].append(tool_name)
        
        return categories
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a coverage report.
        
        Returns:
            A dictionary with the coverage report
        """
        categories = self.categorize_tools()
        
        # Calculate category coverage
        ipfs_expected = ["ipfs_version", "ipfs_add", "ipfs_cat", "ipfs_pin_add", "ipfs_pin_rm", "ipfs_pin_ls"]
        vfs_expected = ["vfs_ls", "vfs_mkdir", "vfs_rmdir", "vfs_read", "vfs_write", "vfs_rm"]
        mfs_expected = ["ipfs_files_mkdir", "ipfs_files_write", "ipfs_files_read", "ipfs_files_ls", "ipfs_files_rm"]
        
        ipfs_covered = [t for t in ipfs_expected if t in categories["ipfs"]]
        vfs_covered = [t for t in vfs_expected if t in categories["vfs"]]
        mfs_covered = [t for t in mfs_expected if t in categories["mfs"]]
        
        ipfs_coverage = len(ipfs_covered) / len(ipfs_expected) * 100 if ipfs_expected else 0
        vfs_coverage = len(vfs_covered) / len(vfs_expected) * 100 if vfs_expected else 0
        mfs_coverage = len(mfs_covered) / len(mfs_expected) * 100 if mfs_expected else 0
        
        total_expected = len(ipfs_expected) + len(vfs_expected) + len(mfs_expected)
        total_covered = len(ipfs_covered) + len(vfs_covered) + len(mfs_covered)
        total_coverage = total_covered / total_expected * 100 if total_expected else 0
        
        # Create the report
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "server_url": self.server_url,
            "total_tools": len(self.mcp_tools),
            "categories": {
                "core": {
                    "count": len(categories["core"]),
                    "tools": categories["core"]
                },
                "ipfs": {
                    "count": len(categories["ipfs"]),
                    "expected": len(ipfs_expected),
                    "coverage": f"{ipfs_coverage:.1f}%",
                    "covered": ipfs_covered,
                    "missing": list(set(ipfs_expected) - set(categories["ipfs"]))
                },
                "vfs": {
                    "count": len(categories["vfs"]),
                    "expected": len(vfs_expected),
                    "coverage": f"{vfs_coverage:.1f}%",
                    "covered": vfs_covered,
                    "missing": list(set(vfs_expected) - set(categories["vfs"]))
                },
                "mfs": {
                    "count": len(categories["mfs"]),
                    "expected": len(mfs_expected),
                    "coverage": f"{mfs_coverage:.1f}%",
                    "covered": mfs_covered,
                    "missing": list(set(mfs_expected) - set(categories["mfs"]))
                },
                "other": {
                    "count": len(categories["other"]),
                    "tools": categories["other"]
                }
            },
            "summary": {
                "total_expected_tools": total_expected,
                "total_covered_tools": total_covered,
                "total_coverage": f"{total_coverage:.1f}%"
            }
        }
        
        return report
    
    def run_analysis(self) -> Dict[str, Any]:
        """Run the full analysis.
        
        Returns:
            The coverage report
        """
        logger.info(f"Starting IPFS Kit coverage analysis on {self.server_url}")
        
        # Fetch MCP tools
        self.fetch_mcp_tools()
        logger.info(f"Found {len(self.mcp_tools)} MCP tools")
        
        # Generate the coverage report
        report = self.generate_report()
        logger.info(f"Generated coverage report")
        
        # Print summary
        logger.info(f"===== IPFS Kit Coverage Analysis Summary =====")
        logger.info(f"Total MCP tools: {report['total_tools']}")
        logger.info(f"IPFS Tool Coverage: {report['categories']['ipfs']['coverage']}")
        logger.info(f"VFS Tool Coverage: {report['categories']['vfs']['coverage']}")
        logger.info(f"MFS Tool Coverage: {report['categories']['mfs']['coverage']}")
        logger.info(f"Overall Coverage: {report['summary']['total_coverage']}")
        
        # Missing tools
        for category in ["ipfs", "vfs", "mfs"]:
            missing = report["categories"][category]["missing"]
            if missing:
                logger.warning(f"Missing {category.upper()} tools: {', '.join(missing)}")
        
        return report
    
def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Analyze IPFS Kit coverage in MCP tools")
    parser.add_argument("--server-url", default=f"http://localhost:{MCP_PORT_DEFAULT}", 
                        help=f"URL of the MCP server (default: http://localhost:{MCP_PORT_DEFAULT})")
    parser.add_argument("--port", type=int, default=MCP_PORT_DEFAULT,
                        help=f"Port of the MCP server (default: {MCP_PORT_DEFAULT})")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--output-file", default=REPORT_FILE, help=f"Output JSON report file (default: {REPORT_FILE})")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # If port is specified, override server_url
    if args.port != MCP_PORT_DEFAULT:
        args.server_url = f"http://localhost:{args.port}"
    
    # Create and run the analyzer
    analyzer = IPFSKitCoverageAnalyzer(args.server_url, args.verbose)
    report = analyzer.run_analysis()
    
    # Save the report to a file
    with open(args.output_file, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Report written to {args.output_file}")
    
    # Return success if all expected tools are covered
    missing_tools = (
        len(report["categories"]["ipfs"]["missing"]) +
        len(report["categories"]["vfs"]["missing"]) +
        len(report["categories"]["mfs"]["missing"])
    )
    
    return 0 if missing_tools == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
