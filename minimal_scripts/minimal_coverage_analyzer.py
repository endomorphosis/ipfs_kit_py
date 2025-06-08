#!/usr/bin/env python3
"""
Minimal IPFS Kit Coverage Analyzer

A minimal version of the coverage analyzer that checks which IPFS Kit functions 
are exposed as MCP tools.
"""

import requests
import json
import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("minimal_coverage_analyzer")

# Constants
MCP_PORT_DEFAULT = 9996
REPORT_FILE = "minimal_ipfs_coverage_report.json"
IPFS_TOOLS = [
    "ipfs_add",
    "ipfs_cat",
    "ipfs_version",
    "ipfs_pin_add",
    "ipfs_pin_rm",
    "ipfs_pin_ls",
    "ipfs_files_mkdir",
    "ipfs_files_write",
    "ipfs_files_read",
    "ipfs_files_ls",
    "ipfs_files_rm"
]

def main():
    """Main entry point"""
    logger.info("Starting minimal IPFS Kit coverage analysis")
    
    # Fetch tools from MCP server
    logger.info(f"Fetching tools from MCP server on port {MCP_PORT_DEFAULT}")
    
    url = f"http://localhost:{MCP_PORT_DEFAULT}/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "list_tools",
        "params": {}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        
        if 'result' not in result or 'tools' not in result['result']:
            logger.error(f"Unexpected response format: {result}")
            return 1
        
        tools = result['result']['tools']
        logger.info(f"Found {len(tools)} tools")
        
        # Extract tool names
        tool_names = []
        for tool in tools:
            if isinstance(tool, str):
                tool_names.append(tool)
            elif isinstance(tool, dict) and 'name' in tool:
                tool_names.append(tool['name'])
        
        # Check for expected IPFS tools
        found_tools = []
        missing_tools = []
        
        for tool_name in IPFS_TOOLS:
            if tool_name in tool_names:
                found_tools.append(tool_name)
            else:
                missing_tools.append(tool_name)
        
        # Calculate coverage
        total_ipfs_tools = len(IPFS_TOOLS)
        found_count = len(found_tools)
        coverage_pct = (found_count / total_ipfs_tools) * 100 if total_ipfs_tools > 0 else 0
        
        # Generate report
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_ipfs_tools": total_ipfs_tools,
            "found_tools": found_count,
            "missing_tools": len(missing_tools),
            "coverage_percentage": coverage_pct,
            "found_tools_list": found_tools,
            "missing_tools_list": missing_tools
        }
        
        # Print summary
        logger.info("\n--- COVERAGE SUMMARY ---")
        logger.info(f"Total expected IPFS tools: {total_ipfs_tools}")
        logger.info(f"Found IPFS tools: {found_count}")
        logger.info(f"Missing IPFS tools: {len(missing_tools)}")
        logger.info(f"Coverage percentage: {coverage_pct:.1f}%")
        
        logger.info("\nFound IPFS tools:")
        for tool in found_tools:
            logger.info(f"- {tool}")
        
        if missing_tools:
            logger.info("\nMissing IPFS tools:")
            for tool in missing_tools:
                logger.info(f"- {tool}")
        
        # Save report to file
        with open(REPORT_FILE, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nReport saved to {REPORT_FILE}")
        return 0
    
    except Exception as e:
        logger.error(f"Error analyzing coverage: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
