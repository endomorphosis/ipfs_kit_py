#!/usr/bin/env python3
"""
MCP Tools Analyzer

This script analyzes the tools available in the MCP server and their relationship
to the IPFS Kit library and Virtual Filesystem functionality.

It helps ensure that the MCP server properly exposes all of the relevant functionality
from the underlying libraries.
"""

import argparse
import json
import os
import sys
import re
import glob
import inspect
import requests
from datetime import datetime
from collections import defaultdict


class MCPToolsAnalyzer:
    """Analyze MCP tools coverage of IPFS Kit and VFS functionality."""

    def __init__(self, server_url, output_dir):
        """Initialize the analyzer."""
        self.server_url = server_url
        self.output_dir = output_dir
        self.jsonrpc_url = f"{server_url}/jsonrpc"
        self.tools = []
        self.ipfs_methods = set()
        self.vfs_methods = set()
        self.results = {}
        self.timestamp = datetime.now().isoformat()

    def extract_ipfs_methods(self):
        """Extract methods from IPFS Kit module."""
        method_pattern = re.compile(r'^\s*def\s+([a-zA-Z][a-zA-Z0-9_]*)\s*\(', re.MULTILINE)
        
        # Locate ipfs_kit.py or similar files
        kit_files = glob.glob('ipfs_kit_py/**/ipfs_kit.py', recursive=True)
        kit_files += glob.glob('**/ipfs_kit.py', recursive=True)
        
        if not kit_files:
            print("WARNING: No IPFS Kit files found")
            return
            
        for kit_file in kit_files:
            try:
                with open(kit_file, 'r') as f:
                    content = f.read()
                
                # Find all methods
                matches = method_pattern.findall(content)
                for match in matches:
                    # Skip private methods and special methods
                    if not match.startswith('_'):
                        self.ipfs_methods.add(match)
                
                print(f"Found {len(self.ipfs_methods)} methods in {kit_file}")
            except Exception as e:
                print(f"Error reading IPFS Kit file {kit_file}: {e}")
    
    def extract_vfs_methods(self):
        """Extract methods from Virtual Filesystem modules."""
        method_pattern = re.compile(r'^\s*def\s+([a-zA-Z][a-zA-Z0-9_]*)\s*\(', re.MULTILINE)
        class_pattern = re.compile(r'^\s*class\s+([a-zA-Z][a-zA-Z0-9_]*)', re.MULTILINE)
        
        # Look for virtual filesystem implementations
        vfs_files = glob.glob('ipfs_kit_py/**/vfs.py', recursive=True)
        vfs_files += glob.glob('ipfs_kit_py/**/*_vfs.py', recursive=True)
        vfs_files += glob.glob('ipfs_kit_py/**/virtual_fs*.py', recursive=True)
        vfs_files += glob.glob('**/vfs.py', recursive=True)
        vfs_files += glob.glob('**/*_vfs.py', recursive=True)
        
        if not vfs_files:
            print("WARNING: No VFS files found")
            return
        
        for vfs_file in vfs_files:
            try:
                with open(vfs_file, 'r') as f:
                    content = f.read()
                
                # Find all methods and classes
                method_matches = method_pattern.findall(content)
                class_matches = class_pattern.findall(content)
                
                for match in method_matches:
                    # Skip private methods
                    if not match.startswith('_'):
                        self.vfs_methods.add(match)
                
                # VFS operations are often these standard names
                standard_operations = ['read', 'write', 'mkdir', 'rmdir', 'ls', 'rm', 'mv', 'cp', 'stat']
                for op in standard_operations:
                    if re.search(rf'\bdef\s+{op}\s*\(', content):
                        self.vfs_methods.add(op)
                
                print(f"Found {len(method_matches)} methods in {vfs_file}")
            except Exception as e:
                print(f"Error reading VFS file {vfs_file}: {e}")
    
    def get_mcp_tools(self):
        """Get all tools from the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": int(datetime.now().timestamp() * 1000)
        }
        
        try:
            print(f"Fetching tools from {self.jsonrpc_url}...")
            response = requests.post(self.jsonrpc_url, json=payload, timeout=10)
            data = response.json()
            
            if "result" in data and "tools" in data["result"]:
                tools = data["result"]["tools"]
                
                # Convert to consistent format
                self.tools = []
                for tool in tools:
                    if isinstance(tool, str):
                        self.tools.append({"name": tool})
                    elif isinstance(tool, dict) and "name" in tool:
                        self.tools.append(tool)
                
                print(f"Found {len(self.tools)} tools")
                return True
            else:
                print(f"Failed to get tools list: {json.dumps(data, indent=2)}")
                return False
        except Exception as e:
            print(f"Error fetching tools: {e}")
            return False
    
    def categorize_tools(self):
        """Categorize tools by their type."""
        categories = {
            "ipfs": [],
            "vfs": [],
            "core": [],
            "other": []
        }
        
        for tool in self.tools:
            name = tool["name"]
            
            if name.startswith("ipfs_"):
                categories["ipfs"].append(tool)
            elif name.startswith("vfs_"):
                categories["vfs"].append(tool)
            elif name in ["ping", "health", "list_tools", "server_info", "initialize"]:
                categories["core"].append(tool)
            else:
                categories["other"].append(tool)
        
        return categories
    
    def analyze_coverage(self):
        """Analyze the coverage of IPFS Kit and VFS in MCP tools."""
        if not self.tools:
            if not self.get_mcp_tools():
                return False
        
        # Extract methods if not already done
        if not self.ipfs_methods:
            self.extract_ipfs_methods()
        
        if not self.vfs_methods:
            self.extract_vfs_methods()
        
        # Categorize tools
        categories = self.categorize_tools()
        
        # IPFS Kit coverage
        ipfs_covered_methods = set()
        for tool in categories["ipfs"]:
            name = tool["name"]
            # Remove 'ipfs_' prefix to get the method name
            method_name = name[5:] if name.startswith("ipfs_") else name
            if method_name in self.ipfs_methods:
                ipfs_covered_methods.add(method_name)
        
        # VFS coverage
        vfs_covered_methods = set()
        for tool in categories["vfs"]:
            name = tool["name"]
            # Remove 'vfs_' prefix to get the method name
            method_name = name[4:] if name.startswith("vfs_") else name
            if method_name in self.vfs_methods:
                vfs_covered_methods.add(method_name)
        
        # Calculate coverage
        ipfs_coverage = 0 if not self.ipfs_methods else (len(ipfs_covered_methods) / len(self.ipfs_methods)) * 100
        vfs_coverage = 0 if not self.vfs_methods else (len(vfs_covered_methods) / len(self.vfs_methods)) * 100
        
        # Prepare results
        self.results = {
            "timestamp": self.timestamp,
            "server_url": self.server_url,
            "ipfs_kit": {
                "total_methods": len(self.ipfs_methods),
                "covered_methods": list(ipfs_covered_methods),
                "missing_methods": list(self.ipfs_methods - ipfs_covered_methods),
                "coverage_percentage": ipfs_coverage
            },
            "vfs": {
                "total_methods": len(self.vfs_methods),
                "covered_methods": list(vfs_covered_methods),
                "missing_methods": list(self.vfs_methods - vfs_covered_methods),
                "coverage_percentage": vfs_coverage
            },
            "tools": {
                "total": len(self.tools),
                "categories": {
                    "ipfs": len(categories["ipfs"]),
                    "vfs": len(categories["vfs"]),
                    "core": len(categories["core"]),
                    "other": len(categories["other"])
                }
            }
        }
        
        return True
    
    def save_results(self):
        """Save analysis results to file."""
        if not self.results:
            print("No results to save")
            return False
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Save JSON results
        json_file = os.path.join(self.output_dir, f"mcp_tools_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Generate markdown report
        md_file = os.path.join(self.output_dir, f"mcp_tools_coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        with open(md_file, 'w') as f:
            f.write(f"# MCP Tools Coverage Analysis\n\n")
            f.write(f"Analysis time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Server URL: {self.server_url}\n\n")
            
            f.write(f"## Summary\n\n")
            f.write(f"- Total MCP Tools: {self.results['tools']['total']}\n")
            f.write(f"  - IPFS Tools: {self.results['tools']['categories']['ipfs']}\n")
            f.write(f"  - VFS Tools: {self.results['tools']['categories']['vfs']}\n")
            f.write(f"  - Core Tools: {self.results['tools']['categories']['core']}\n")
            f.write(f"  - Other Tools: {self.results['tools']['categories']['other']}\n\n")
            
            f.write(f"## IPFS Kit Coverage\n\n")
            f.write(f"- Total IPFS Kit methods: {self.results['ipfs_kit']['total_methods']}\n")
            f.write(f"- Covered methods: {len(self.results['ipfs_kit']['covered_methods'])}\n")
            f.write(f"- Coverage percentage: {self.results['ipfs_kit']['coverage_percentage']:.2f}%\n\n")
            
            f.write(f"### Covered IPFS Methods\n\n")
            for method in sorted(self.results['ipfs_kit']['covered_methods']):
                f.write(f"- {method}\n")
            
            f.write(f"\n### Missing IPFS Methods\n\n")
            for method in sorted(self.results['ipfs_kit']['missing_methods']):
                f.write(f"- {method}\n")
            
            f.write(f"\n## VFS Coverage\n\n")
            f.write(f"- Total VFS methods: {self.results['vfs']['total_methods']}\n")
            f.write(f"- Covered methods: {len(self.results['vfs']['covered_methods'])}\n")
            f.write(f"- Coverage percentage: {self.results['vfs']['coverage_percentage']:.2f}%\n\n")
            
            f.write(f"### Covered VFS Methods\n\n")
            for method in sorted(self.results['vfs']['covered_methods']):
                f.write(f"- {method}\n")
            
            f.write(f"\n### Missing VFS Methods\n\n")
            for method in sorted(self.results['vfs']['missing_methods']):
                f.write(f"- {method}\n")
        
        print(f"Results saved to {json_file}")
        print(f"Markdown report saved to {md_file}")
        return True
    
    def run(self):
        """Run the full analysis."""
        if not self.get_mcp_tools():
            return False
        
        if not self.analyze_coverage():
            return False
        
        return self.save_results()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze MCP tools coverage.')
    parser.add_argument('--server', default='http://localhost:9996', help='MCP server URL')
    parser.add_argument('--output-dir', default='diagnostic_results', help='Output directory for reports')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    analyzer = MCPToolsAnalyzer(args.server, args.output_dir)
    if analyzer.run():
        print("Analysis completed successfully")
        sys.exit(0)
    else:
        print("Analysis failed")
        sys.exit(1)
