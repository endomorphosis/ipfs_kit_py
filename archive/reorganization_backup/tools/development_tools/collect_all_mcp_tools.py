#!/usr/bin/env python3
"""
Tool Collection Script for MCP Integration

This script analyzes all existing tool registries and implementations across the codebase
and produces a consolidated list of all available tools, their descriptions, schemas,
and implementation references.

The goal is to create a comprehensive inventory that can be used to expand our MCP server.
"""

import os
import sys
import json
import glob
import inspect
import importlib.util
import re
import logging
from typing import Dict, List, Any, Set, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("tool-collector")

# Storage for collected tools
all_tools = {}
tool_sources = {}
implementation_references = {}

def extract_tools_from_registry_file(file_path: str) -> Dict[str, Any]:
    """Extract tool definitions from a Python file containing registry information."""
    tools = {}
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Special handling for known registry files
        if 'ipfs_tools_registry.py' in file_path or 'direct_tool_registry.py' in file_path:
            logger.info(f"Processing known registry file: {file_path}")
            
            # Look for tool definitions in array format
            if 'ipfs_tools_registry.py' in file_path:
                search_pattern = r'IPFS_TOOLS\s*=\s*\['
            else:
                search_pattern = r'tools\s*=\s*\['
                
            # Find the start of the tools array
            match = re.search(search_pattern, content)
            if match:
                start_pos = match.end()
                # Find balanced brackets to extract the entire array
                open_brackets = 1
                end_pos = start_pos
                for i in range(start_pos, len(content)):
                    if content[i] == '[':
                        open_brackets += 1
                    elif content[i] == ']':
                        open_brackets -= 1
                        if open_brackets == 0:
                            end_pos = i
                            break
                
                # Extract the tools array content
                tools_content = content[start_pos:end_pos]
                
                # Process each tool definition (each starting with {)
                tool_starts = [m.start() for m in re.finditer(r'\s*\{', tools_content)]
                tool_starts.append(len(tools_content))  # Add end marker
                
                for i in range(len(tool_starts) - 1):
                    tool_def = tools_content[tool_starts[i]:tool_starts[i+1]]
                    # Trim trailing comma and whitespace
                    tool_def = re.sub(r',\s*$', '', tool_def)
                    
                    try:
                        # Use safer ast.literal_eval to parse the Python literal
                        import ast
                        try:
                            tool_dict = ast.literal_eval(tool_def)
                            if isinstance(tool_dict, dict) and 'name' in tool_dict:
                                tool_name = tool_dict['name']
                                tools[tool_name] = tool_dict
                                tool_sources[tool_name] = file_path
                                logger.info(f"Found tool: {tool_name} in {os.path.basename(file_path)}")
                        except (SyntaxError, ValueError) as e:
                            logger.warning(f"Failed to parse tool definition: {e}")
                    except Exception as e:
                        logger.warning(f"Error processing tool definition: {e}")
        
        # Generic pattern matching for other files
        tool_lists = re.findall(r'(?:TOOLS|IPFS_TOOLS|MCP_TOOLS|tools)\s*=\s*\[(.*?)\]', content, re.DOTALL)
        for tool_list in tool_lists:
            # Parse individual tool definitions
            tool_defs = re.split(r'\},\s*\{', tool_list)
            for tool_def in tool_defs:
                # Fix up the JSON to make it parseable
                if not tool_def.startswith('{'):
                    tool_def = '{' + tool_def
                if not tool_def.endswith('}'):
                    tool_def = tool_def + '}'
                
                try:
                    # Try to parse with ast since it's safer for Python literals
                    import ast
                    try:
                        tool_dict = ast.literal_eval(tool_def)
                        if isinstance(tool_dict, dict) and 'name' in tool_dict:
                            tool_name = tool_dict['name']
                            if tool_name not in tools:  # Only add if not already found
                                tools[tool_name] = tool_dict
                                tool_sources[tool_name] = file_path
                                logger.info(f"Found tool (generic pattern): {tool_name}")
                    except (SyntaxError, ValueError):
                        # If ast fails, just log it
                        logger.debug(f"Could not parse tool definition using ast: {tool_def[:50]}...")
                except Exception as e:
                    logger.debug(f"Error parsing tool: {e}")
                    continue
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
    
    return tools

def extract_tool_implementations(file_path: str) -> Dict[str, str]:
    """Extract tool implementation functions from a Python file."""
    implementations = {}
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Special handling for known implementation files
        if 'minimal_mcp_server.py' in file_path or 'enhanced_final_mcp_server.py' in file_path:
            logger.info(f"Processing known implementation file: {file_path}")
            
            # Look for tool handler functions
            async_handlers = re.findall(r'async\s+def\s+(handle_\w+)\s*\([^)]*\):\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', content, re.DOTALL)
            for func_name, doc_string in async_handlers:
                # Extract tool name from function name
                if func_name.startswith('handle_'):
                    tool_name = func_name[7:]  # Remove 'handle_' prefix
                    implementations[tool_name] = func_name
                    implementation_references[tool_name] = file_path
                    logger.info(f"Found tool implementation: {tool_name} -> {func_name}")
            
            # Look for regular handler functions too
            regular_handlers = re.findall(r'def\s+(handle_\w+)\s*\([^)]*\):\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', content, re.DOTALL)
            for func_name, doc_string in regular_handlers:
                # Extract tool name from function name
                if func_name.startswith('handle_'):
                    tool_name = func_name[7:]  # Remove 'handle_' prefix
                    implementations[tool_name] = func_name
                    implementation_references[tool_name] = file_path
                    logger.info(f"Found tool implementation: {tool_name} -> {func_name}")
                    
        # Look for tool functions using common decorator patterns (all files)
        tool_funcs = re.findall(r'@\w+\.tool\(.*?name=[\'"](\w+)[\'"].*?\)\s*(?:async\s+)?def\s+(\w+)', content, re.DOTALL)
        for tool_name, func_name in tool_funcs:
            implementations[tool_name] = func_name
            implementation_references[tool_name] = file_path
            logger.info(f"Found decorated tool: {tool_name} -> {func_name}")
        
        # Look for direct tool implementations
        tool_patterns = [
            # Look for ipfs_tools implementations
            (r'(?:async\s+)?def\s+(ipfs_\w+)\s*\([^)]*\):', lambda m: m.group(1)),
            # Look for vfs_tools implementations
            (r'(?:async\s+)?def\s+(vfs_\w+)\s*\([^)]*\):', lambda m: m.group(1)),
            # Look for tool_ prefix implementations
            (r'(?:async\s+)?def\s+(tool_\w+)\s*\([^)]*\):', lambda m: m.group(1)[5:]),
            # Look for functions with 'tool' in docstring
            (r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\):\s*(?:"""|\'\'\').*?(?:tool|mcp|ipfs).*?(?:"""|\'\'\')', lambda m: m.group(1))
        ]
        
        for pattern, name_extractor in tool_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                func_name = match.group(1)
                tool_name = name_extractor(match)
                implementations[tool_name] = func_name
                implementation_references[tool_name] = file_path
                logger.debug(f"Found potential tool implementation: {tool_name} -> {func_name}")
    
    except Exception as e:
        logger.warning(f"Error analyzing file {file_path}: {e}")
    
    return implementations

def scan_directory_for_tools(directory: str) -> None:
    """Scan a directory for tool registries and implementations."""
    logger.info(f"Scanning directory: {directory}")
    
    # Find all Python files in the directory and its subdirectories
    py_files = glob.glob(os.path.join(directory, "**", "*.py"), recursive=True)
    
    # List of high-priority registry and implementation files to process first
    priority_files = [
        os.path.join(directory, 'ipfs_tools_registry.py'),
        os.path.join(directory, 'direct_tool_registry.py'),
        os.path.join(directory, 'minimal_mcp_server.py'),
        os.path.join(directory, 'enhanced_final_mcp_server.py')
    ]
    
    # Process priority files first
    for file_path in priority_files:
        if os.path.exists(file_path):
            logger.info(f"Processing priority file: {file_path}")
            
            # Extract tool definitions if it's a registry file
            if 'registry.py' in file_path:
                tools = extract_tools_from_registry_file(file_path)
                for name, tool in tools.items():
                    if name not in all_tools:
                        all_tools[name] = tool
                        logger.info(f"Found tool definition in priority file: {name}")
                    else:
                        logger.info(f"Duplicate tool definition in priority file: {name}")
            
            # Extract tool implementations
            implementations = extract_tool_implementations(file_path)
            for tool_name, func_name in implementations.items():
                implementation_references[tool_name] = file_path
                if tool_name not in all_tools:
                    all_tools[tool_name] = {
                        "name": tool_name,
                        "description": f"Tool implementation found in {os.path.basename(file_path)}",
                        "implementation": func_name,
                        "auto_discovered": True
                    }
                    logger.info(f"Found undocumented tool implementation in priority file: {tool_name}")
                else:
                    # Add implementation reference to the existing tool
                    all_tools[tool_name]["implementation"] = func_name
                    all_tools[tool_name]["implementation_file"] = file_path
                    logger.info(f"Added implementation reference for tool: {tool_name}")
    
    # Scan for additional tool registry files
    registry_files = [f for f in py_files if re.search(r'registry|tools|mcp.*tools', f, re.IGNORECASE)]
    registry_files = [f for f in registry_files if f not in priority_files]  # Skip already processed files
    
    for file_path in registry_files:
        logger.info(f"Analyzing registry file: {file_path}")
        tools = extract_tools_from_registry_file(file_path)
        for name, tool in tools.items():
            if name not in all_tools:
                all_tools[name] = tool
                logger.info(f"Found tool definition: {name}")
            else:
                logger.info(f"Duplicate tool definition: {name}")
    
    # Then scan for additional implementation files
    for file_path in py_files:
        if file_path in priority_files:
            continue  # Skip already processed files
            
        if not file_path.endswith('_test.py') and not file_path.endswith('conftest.py'):
            logger.debug(f"Looking for implementations in: {file_path}")
            implementations = extract_tool_implementations(file_path)
            for tool_name, func_name in implementations.items():
                if tool_name not in all_tools:
                    all_tools[tool_name] = {
                        "name": tool_name,
                        "description": f"Auto-discovered tool from {os.path.basename(file_path)}",
                        "implementation": func_name,
                        "implementation_file": file_path,
                        "auto_discovered": True
                    }
                    logger.info(f"Found undocumented tool implementation: {tool_name}")
                elif "implementation" not in all_tools[tool_name]:
                    # Add implementation reference to the existing tool
                    all_tools[tool_name]["implementation"] = func_name
                    all_tools[tool_name]["implementation_file"] = file_path
                    logger.info(f"Found implementation for tool: {tool_name}")

def save_tools_inventory(output_file: str) -> None:
    """Save the consolidated tool inventory to a file."""
    # Enhance tool metadata with implementation status
    for tool_name, tool in all_tools.items():
        if "implementation" in tool:
            tool["has_implementation"] = True
            tool["implementation_file"] = implementation_references.get(tool_name, "unknown")
        else:
            tool["has_implementation"] = False
    
    # Add a status field to each tool
    for tool_name, tool in all_tools.items():
        if tool.get("has_implementation", False) and "schema" in tool:
            tool["status"] = "complete"
        elif tool.get("has_implementation", False):
            tool["status"] = "partial - missing schema"
        elif "schema" in tool:
            tool["status"] = "partial - missing implementation"
        else:
            tool["status"] = "incomplete"
    
    # Organize tools into categories
    categories = categorize_tools(all_tools)
    
    # Create inventory data structure
    tool_inventory = {
        "total_tools": len(all_tools),
        "complete_tools": sum(1 for t in all_tools.values() if t.get("status") == "complete"),
        "partial_tools": sum(1 for t in all_tools.values() if t.get("status").startswith("partial")),
        "incomplete_tools": sum(1 for t in all_tools.values() if t.get("status") == "incomplete"),
        "tools": all_tools,
        "tool_sources": tool_sources,
        "implementation_references": implementation_references,
        "categories": categories
    }
    
    # Save as JSON
    with open(output_file, 'w') as f:
        json.dump(tool_inventory, f, indent=2, sort_keys=True)
    
    logger.info(f"Saved {len(all_tools)} tools to {output_file}")
    
    # Generate a summary Markdown file
    with open(output_file.replace('.json', '.md'), 'w') as f:
        f.write("# MCP Tools Inventory\n\n")
        f.write(f"Total tools discovered: {len(all_tools)}\n\n")
        f.write(f"- Complete tools (schema + implementation): {tool_inventory['complete_tools']}\n")
        f.write(f"- Partial tools (missing schema or implementation): {tool_inventory['partial_tools']}\n")
        f.write(f"- Incomplete tools (missing both): {tool_inventory['incomplete_tools']}\n\n")
        
        # List tools by category
        for category, tool_names in categories.items():
            f.write(f"## {category.replace('_', ' ').title()} Tools ({len(tool_names)})\n\n")
            f.write("| Tool Name | Status | Description | Source | Implementation |\n")
            f.write("|-----------|--------|-------------|--------|----------------|\n")
            
            # Sort tools by status (complete first)
            sorted_tools = sorted(tool_names, key=lambda name: 
                                  0 if all_tools[name].get("status") == "complete" else
                                  1 if all_tools[name].get("status").startswith("partial") else 2)
            
            for tool_name in sorted_tools:
                tool = all_tools[tool_name]
                description = tool.get("description", "").split('\n')[0][:50]
                source = os.path.basename(tool_sources.get(tool_name, "unknown"))
                status = tool.get("status", "unknown")
                impl_file = os.path.basename(tool.get("implementation_file", "none"))
                
                # Set status emoji
                if status == "complete":
                    status_emoji = "✅"
                elif status.startswith("partial"):
                    status_emoji = "⚠️"
                else:
                    status_emoji = "❌"
                
                f.write(f"| `{tool_name}` | {status_emoji} | {description} | {source} | {impl_file} |\n")
            
            f.write("\n")
            
        # Add a section for MCP integration
        f.write("## MCP Integration Guide\n\n")
        f.write("### Steps to Complete Integration\n\n")
        f.write("1. Implement missing tool schemas from the registry\n")
        f.write("2. Implement missing tool handlers\n")
        f.write("3. Update the enhanced_final_mcp_server.py file to include all tools\n")
        f.write("4. Update the comprehensive_mcp_test.py to test all tools\n\n")
        
        # Add table of tools that need implementation work
        incomplete_tools = [name for name, tool in all_tools.items() if tool.get("status") != "complete"]
        if incomplete_tools:
            f.write("### Tools Requiring Implementation Work\n\n")
            f.write("| Tool Name | Missing Component | Priority |\n")
            f.write("|-----------|-------------------|----------|\n")
            
            for tool_name in incomplete_tools:
                tool = all_tools[tool_name]
                if tool.get("status") == "partial - missing schema":
                    missing = "Schema"
                    priority = "Medium"
                elif tool.get("status") == "partial - missing implementation":
                    missing = "Implementation"
                    priority = "High"
                else:
                    missing = "Both"
                    priority = "Low"
                
                f.write(f"| `{tool_name}` | {missing} | {priority} |\n")
    
    logger.info(f"Generated Markdown summary at {output_file.replace('.json', '.md')}")
    
    # Generate Python code to register all tools in enhanced_final_mcp_server.py
    with open(output_file.replace('.json', '_register.py'), 'w') as f:
        f.write("# Tool Registration Code for enhanced_final_mcp_server.py\n\n")
        f.write("# This code was auto-generated by collect_all_mcp_tools.py\n")
        f.write("# Copy the relevant sections into enhanced_final_mcp_server.py\n\n")
        
        # Generate tool registration code
        f.write("# Tool Registration\n")
        f.write("def register_all_tools():\n")
        f.write("    \"\"\"Register all tools from the consolidated inventory\"\"\"\n")
        f.write("    # Core IPFS tools\n")
        
        for category, tool_names in categories.items():
            f.write(f"\n    # {category.replace('_', ' ').title()} tools\n")
            for tool_name in tool_names:
                tool = all_tools[tool_name]
                if "schema" in tool:
                    f.write(f"    register_tool(\n")
                    f.write(f"        name=\"{tool_name}\",\n")
                    f.write(f"        handler=handle_{tool_name},\n")
                    f.write(f"        description=\"{tool.get('description', '').split(chr(10))[0]}\",\n")
                    f.write(f"        schema={json.dumps(tool['schema'], indent=8).replace(chr(10), chr(10) + '    ')}\n")
                    f.write(f"    )\n")
        
    logger.info(f"Generated tool registration code at {output_file.replace('.json', '_register.py')}")

def categorize_tools(tools: Dict[str, Any]) -> Dict[str, List[str]]:
    """Categorize tools based on their names and descriptions."""
    categories = {
        "ipfs_core": [],
        "ipfs_mfs": [],
        "vfs": [],
        "fs": [],
        "networking": [],
        "system": [],
        "utility": [],
        "other": []
    }
    
    for name, tool in tools.items():
        if name.startswith("ipfs_files_"):
            categories["ipfs_mfs"].append(name)
        elif name.startswith("ipfs_"):
            categories["ipfs_core"].append(name)
        elif name.startswith("vfs_"):
            categories["vfs"].append(name)
        elif name.startswith("fs_"):
            categories["fs"].append(name)
        elif name.startswith("net_") or "network" in name or "http" in name:
            categories["networking"].append(name)
        elif name.startswith("sys_") or "system" in name:
            categories["system"].append(name)
        elif any(keyword in name for keyword in ["ping", "health", "utility"]):
            categories["utility"].append(name)
        else:
            categories["other"].append(name)
    
    return categories

def main():
    """Main function to scan for tools and generate inventory."""
    logger.info("Starting MCP Tools collection process")
    
    # Scan the main directory and ipfs_kit_py subdirectory
    root_dir = os.path.dirname(os.path.abspath(__file__))
    logger.info(f"Scanning root directory: {root_dir}")
    scan_directory_for_tools(root_dir)
    
    ipfs_kit_dir = os.path.join(root_dir, "ipfs_kit_py")
    if os.path.exists(ipfs_kit_dir):
        logger.info(f"Scanning ipfs_kit_py directory: {ipfs_kit_dir}")
        scan_directory_for_tools(ipfs_kit_dir)
    else:
        logger.warning(f"ipfs_kit_py directory not found at {ipfs_kit_dir}")
    
    # Save the consolidated tools inventory
    output_file = os.path.join(root_dir, "consolidated_mcp_tools.json")
    logger.info(f"Saving consolidated tool inventory to {output_file}")
    save_tools_inventory(output_file)
    
    logger.info("MCP Tool collection complete!")
    logger.info(f"Total tools found: {len(all_tools)}")
    
    # Print summary statistics
    complete_tools = sum(1 for t in all_tools.values() if t.get("status") == "complete")
    partial_tools = sum(1 for t in all_tools.values() if t.get("status", "").startswith("partial"))
    incomplete_tools = sum(1 for t in all_tools.values() if t.get("status") == "incomplete")
    
    logger.info(f"Complete tools (schema + implementation): {complete_tools}")
    logger.info(f"Partial tools (missing schema or implementation): {partial_tools}")
    logger.info(f"Incomplete tools (missing both): {incomplete_tools}")
    
if __name__ == "__main__":
    main()
