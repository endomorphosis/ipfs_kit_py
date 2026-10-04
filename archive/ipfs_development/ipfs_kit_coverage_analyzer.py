#!/usr/bin/env python3
"""
IPFS Kit Coverage Analyzer

This script analyzes the coverage of IPFS Kit functionality in the MCP tools:
1. Inspects the IPFS Kit Python module to identify all functions and classes
2. Checks which IPFS functions are exposed as MCP tools
3. Identifies missing functionality that should be exposed
4. Generates a comprehensive coverage report

Usage:
  python3 ipfs_kit_coverage_analyzer.py --server-file final_mcp_server.py --port 9996 [--open-report]
"""

import argparse
import json
import os
import sys
import time
import inspect
import importlib
import requests
import webbrowser
import datetime
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import urljoin
import pkgutil
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ipfs_kit_coverage_analyzer")

# Constants
REPORT_DIR = "coverage_reports"
SUMMARY_FILE = os.path.join(REPORT_DIR, "ipfs_coverage_summary.json")
DETAILED_REPORT_FILE = os.path.join(REPORT_DIR, "ipfs_coverage_report.md")
HTML_REPORT_FILE = os.path.join(REPORT_DIR, "ipfs_coverage_report.html")

# IPFS module to analyze
IPFS_MODULE = "ipfs_kit_py"

class IPFSCoverageAnalyzer:
    """Analyzer for IPFS Kit coverage in MCP tools."""

    def __init__(self, url: str, verbose: bool = False):
        """Initialize the analyzer.
        
        Args:
            url: The base URL of the MCP server
            verbose: Whether to print verbose output
        """
        self.base_url = url
        self.rpc_url = urljoin(url, "/jsonrpc")
        self.verbose = verbose
        self.ipfs_tools = []
        self.ipfs_functions = {}
        self.mfs_functions = {}
        self.vfs_functions = {}
        self.coverage_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "server_url": url,
            "coverage_summary": {},
            "ipfs_functions": {},
            "mfs_functions": {},
            "vfs_functions": {},
            "missing_functions": [],
            "tool_to_function_map": {}
        }
        
        # Set up detailed logging if verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
            logger.debug(f"Verbose logging enabled")

    def log(self, message: str, level: str = "info"):
        """Log a message.
        
        Args:
            message: The message to log
            level: The log level
        """
        if level == "debug" and self.verbose:
            logger.debug(message)
        elif level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        elif level == "success":
            logger.info(f"SUCCESS: {message}")

    def get_mcp_tools(self) -> bool:
        """Get all available MCP tools.
        
        Returns:
            True if successful, False otherwise.
        """
        self.log("Getting available MCP tools...")
        
        try:
            # Get all methods
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "system.listMethods"
            }
            response = requests.post(self.rpc_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    all_methods = data["result"]
                    
                    # Filter IPFS related tools
                    self.ipfs_tools = [m for m in all_methods if m.startswith("ipfs.")]
                    vfs_tools = [m for m in all_methods if m.startswith("vfs.")]
                    mfs_tools = [m for m in all_methods if m.startswith("mfs.")]
                    
                    self.log(f"Found {len(self.ipfs_tools)} IPFS tools")
                    self.log(f"Found {len(vfs_tools)} VFS tools")
                    self.log(f"Found {len(mfs_tools)} MFS tools")
                    
                    # Store in coverage data
                    self.coverage_data["ipfs_tools"] = self.ipfs_tools
                    self.coverage_data["vfs_tools"] = vfs_tools
                    self.coverage_data["mfs_tools"] = mfs_tools
                    
                    return True
                else:
                    self.log(f"Error getting MCP tools: {data.get('error', 'Unknown error')}", "error")
                    return False
            else:
                self.log(f"Error getting MCP tools: HTTP {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"Error getting MCP tools: {e}", "error")
            return False

    def get_tools_schema(self) -> bool:
        """Get the schema for all available tools.
        
        Returns:
            True if successful, False otherwise.
        """
        self.log("Getting tools schema...")
        
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "get_tools_schema"
            }
            response = requests.post(self.rpc_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    tools_schema = data["result"]
                    
                    # Filter schemas by category
                    ipfs_schemas = {k: v for k, v in tools_schema.items() if k.startswith("ipfs.")}
                    vfs_schemas = {k: v for k, v in tools_schema.items() if k.startswith("vfs.")}
                    mfs_schemas = {k: v for k, v in tools_schema.items() if k.startswith("mfs.")}
                    
                    self.log(f"Got schema for {len(ipfs_schemas)} IPFS tools")
                    self.log(f"Got schema for {len(vfs_schemas)} VFS tools")
                    self.log(f"Got schema for {len(mfs_schemas)} MFS tools")
                    
                    # Store in coverage data
                    self.coverage_data["ipfs_tool_schemas"] = ipfs_schemas
                    self.coverage_data["vfs_tool_schemas"] = vfs_schemas
                    self.coverage_data["mfs_tool_schemas"] = mfs_schemas
                    
                    return True
                else:
                    self.log(f"Error getting tools schema: {data.get('error', 'Unknown error')}", "error")
                    return False
            else:
                self.log(f"Error getting tools schema: HTTP {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"Error getting tools schema: {e}", "error")
            return False

    def analyze_ipfs_module(self) -> bool:
        """Analyze the IPFS Kit Python module.
        
        Returns:
            True if successful, False otherwise.
        """
        self.log(f"Analyzing IPFS Kit module: {IPFS_MODULE}")
        
        try:
            # Try to import the module
            try:
                ipfs_module = importlib.import_module(IPFS_MODULE)
            except ImportError:
                self.log(f"Module {IPFS_MODULE} not found, using inspection approach", "warning")
                # If we can't import it directly, we'll inspect the files
                module_path = os.path.join(os.getcwd(), IPFS_MODULE)
                if not os.path.exists(module_path):
                    self.log(f"Module path not found: {module_path}", "error")
                    return False
                
                ipfs_functions = self._inspect_module_files(module_path)
                self.ipfs_functions = ipfs_functions.get("ipfs", {})
                self.mfs_functions = ipfs_functions.get("mfs", {})
                self.vfs_functions = ipfs_functions.get("vfs", {})
            else:
                # If module imported successfully
                self._analyze_imported_module(ipfs_module)
            
            # Store in coverage data
            self.coverage_data["ipfs_functions"] = {
                name: {"docstring": doc, "signature": sig}
                for name, (doc, sig) in self.ipfs_functions.items()
            }
            self.coverage_data["mfs_functions"] = {
                name: {"docstring": doc, "signature": sig}
                for name, (doc, sig) in self.mfs_functions.items()
            }
            self.coverage_data["vfs_functions"] = {
                name: {"docstring": doc, "signature": sig}
                for name, (doc, sig) in self.vfs_functions.items()
            }
            
            self.log(f"Found {len(self.ipfs_functions)} IPFS functions/methods")
            self.log(f"Found {len(self.mfs_functions)} MFS functions/methods")
            self.log(f"Found {len(self.vfs_functions)} VFS functions/methods")
            
            return True
        except Exception as e:
            self.log(f"Error analyzing IPFS module: {e}", "error")
            return False

    def _analyze_imported_module(self, module) -> None:
        """Analyze an imported module to extract functions and methods.
        
        Args:
            module: The imported module
        """
        # Extract functions directly from the module
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith('_'):
                self.ipfs_functions[name] = (inspect.getdoc(obj), str(inspect.signature(obj)))
            
            # Look for submodules
            elif inspect.ismodule(obj) and obj.__name__.startswith(module.__name__):
                submodule_name = obj.__name__.split('.')[-1]
                
                # Process different submodules
                if submodule_name == "ipfs":
                    self._process_submodule(obj, self.ipfs_functions)
                elif submodule_name == "mfs":
                    self._process_submodule(obj, self.mfs_functions)
                elif submodule_name == "vfs":
                    self._process_submodule(obj, self.vfs_functions)
        
        # Try to find classes from the module
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and not name.startswith('_'):
                class_name = obj.__name__
                
                # Process IPFS related classes
                if "IPFS" in class_name or "ipfs" in class_name.lower():
                    self._process_class(obj, self.ipfs_functions, class_name)
                # Process MFS related classes
                elif "MFS" in class_name or "mfs" in class_name.lower():
                    self._process_class(obj, self.mfs_functions, class_name)
                # Process VFS related classes
                elif "VFS" in class_name or "vfs" in class_name.lower():
                    self._process_class(obj, self.vfs_functions, class_name)

    def _process_submodule(self, submodule, function_dict: Dict) -> None:
        """Process a submodule to extract functions.
        
        Args:
            submodule: The submodule to process
            function_dict: The dictionary to store functions in
        """
        for name, obj in inspect.getmembers(submodule):
            if inspect.isfunction(obj) and not name.startswith('_'):
                function_dict[name] = (inspect.getdoc(obj), str(inspect.signature(obj)))

    def _process_class(self, cls, function_dict: Dict, class_prefix: str) -> None:
        """Process a class to extract methods.
        
        Args:
            cls: The class to process
            function_dict: The dictionary to store methods in
            class_prefix: The prefix to add to method names
        """
        for name, obj in inspect.getmembers(cls):
            if inspect.isfunction(obj) and not name.startswith('_'):
                function_dict[f"{class_prefix}.{name}"] = (inspect.getdoc(obj), str(inspect.signature(obj)))

    def _inspect_module_files(self, module_path: str) -> Dict[str, Dict[str, Tuple[str, str]]]:
        """Inspect module files to extract function and method information.
        
        Args:
            module_path: Path to the module
            
        Returns:
            Dictionary of function categories with function info
        """
        result = {
            "ipfs": {},
            "mfs": {},
            "vfs": {}
        }
        
        # Function pattern with capture groups for name, args, and docstring
        func_pattern = r"def\s+([a-zA-Z0-9_]+)\s*\((.*?)\).*?:(.*?)(?=\s*def|\s*class|$)"
        
        # Walk through the module directory
        for root, dirs, files in os.walk(module_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, module_path)
                    
                    # Determine the category based on file path
                    category = "ipfs"
                    if "mfs" in relative_path.lower():
                        category = "mfs"
                    elif "vfs" in relative_path.lower():
                        category = "vfs"
                    
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            
                            # Find all function definitions
                            matches = re.finditer(func_pattern, content, re.DOTALL)
                            for match in matches:
                                name = match.group(1)
                                args = match.group(2)
                                docstring_block = match.group(3).strip()
                                
                                # Skip internal functions
                                if name.startswith('_'):
                                    continue
                                
                                # Extract docstring if it exists
                                docstring = ""
                                docstring_pattern = r'[\'"].*?[\'"]'
reate 
[Response interrupted by a tool use result. Only one tool may be used at a time and should be placed at the end of the message.]
