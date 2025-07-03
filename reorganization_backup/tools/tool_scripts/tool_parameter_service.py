#!/usr/bin/env python3
"""
Tool Parameter Adapter Service Script

This script will check for common parameter mismatches between tool implementations
and client calls, and create mappings to fix them. It analyzes the test logs to
identify common patterns of parameter mismatches.
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("param-adapter-service")

# Default test log pattern
DEFAULT_LOG_PATTERN = "test_*.log"

def extract_parameter_errors(log_file: str) -> List[Dict[str, Any]]:
    """Extract parameter errors from a test log file"""
    error_patterns = [
        r"got an unexpected keyword argument '([^']+)'",
        r"missing a required argument: '([^']+)'",
        r"Parameter '([^']+)' not found"
    ]
    
    errors = []
    
    with open(log_file, 'r') as f:
        content = f.read()
        
        # Find JSON-RPC calls with errors
        rpc_pattern = r'("method": "([^"]+)".*?"params": ({[^}]+}).*?"error")'
        for match in re.finditer(rpc_pattern, content, re.DOTALL):
            method = match.group(2)
            params_str = match.group(3)
            
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError:
                continue
            
            # Look for parameter errors
            for error_pattern in error_patterns:
                for match in re.finditer(error_pattern, content):
                    param_name = match.group(1)
                    errors.append({
                        "method": method,
                        "params": params,
                        "error_param": param_name
                    })
    
    return errors

def analyze_parameters(errors: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    """Analyze parameter errors to create mappings"""
    mappings = {}
    
    for error in errors:
        method = error["method"]
        params = error["params"]
        error_param = error["error_param"]
        
        if method not in mappings:
            mappings[method] = {
                "required": [],
                "optional": [],
                "mappings": {}
            }
        
        # Add to required parameters
        if error_param not in mappings[method]["required"]:
            mappings[method]["required"].append(error_param)
        
        # Create potential mappings
        for param_name in params.keys():
            if param_name != error_param and param_name not in mappings[method]["mappings"].get(error_param, []):
                if error_param not in mappings[method]["mappings"]:
                    mappings[method]["mappings"][error_param] = []
                mappings[method]["mappings"][error_param].append(param_name)
    
    return mappings

def generate_adapter_code(mappings: Dict[str, Dict[str, List[str]]]) -> str:
    """Generate adapter code from mappings"""
    code = """
# Generated Parameter Adapter Mappings
# This file contains parameter mappings for tools based on error analysis

TOOL_PARAMETER_MAPPINGS = {
"""
    
    for method, mapping in mappings.items():
        code += f"    '{method}': {{\n"
        
        # Add required parameters
        code += f"        'required': {mapping['required']},\n"
        
        # Add optional parameters
        code += f"        'optional': {mapping['optional']},\n"
        
        # Add parameter mappings
        code += "        'mappings': {\n"
        for param, alternatives in mapping.get("mappings", {}).items():
            code += f"            '{param}': {alternatives},\n"
        code += "        }\n"
        
        code += "    },\n"
    
    code += "}\n"
    return code

def main():
    """Main function"""
    # Find test logs
    log_files = list(Path(".").glob(DEFAULT_LOG_PATTERN))
    if not log_files:
        logger.error(f"No log files found matching pattern: {DEFAULT_LOG_PATTERN}")
        return
    
    # Extract and analyze errors
    all_errors = []
    for log_file in log_files:
        logger.info(f"Analyzing log file: {log_file}")
        errors = extract_parameter_errors(str(log_file))
        all_errors.extend(errors)
    
    # Generate mappings
    mappings = analyze_parameters(all_errors)
    
    # Generate code
    code = generate_adapter_code(mappings)
    
    # Write to file
    output_file = "generated_parameter_mappings.py"
    with open(output_file, "w") as f:
        f.write(code)
    
    logger.info(f"Generated parameter mappings written to: {output_file}")

if __name__ == "__main__":
    main()