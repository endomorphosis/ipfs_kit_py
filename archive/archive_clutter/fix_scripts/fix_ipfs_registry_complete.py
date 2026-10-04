#!/usr/bin/env python3
"""
Fix the IPFS tools registry completely by rewriting it from scratch
"""

import json
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_registry():
    """Fix the IPFS tools registry by rebuilding it from scratch"""
    registry_path = "ipfs_tools_registry.py"
    
    try:
        # Read the current registry
        with open(registry_path, 'r') as f:
            content = f.read()
        
        # Define a regex pattern to extract each tool definition
        pattern = r'\{\s*"name":\s*"([^"]+)",\s*"description":\s*"([^"]+)",\s*"schema":\s*(\{[^{]*(?:\{[^{]*(?:\{[^{]*\}[^{]*)*\}[^{]*)*\})'
        
        # Find all matches
        matches = re.finditer(pattern, content, re.DOTALL)
        
        # Extract all tool definitions
        tools = []
        for match in matches:
            name = match.group(1)
            description = match.group(2)
            schema_str = match.group(3).strip()
            
            # Fix any Python literals in the schema (True/False)
            schema_str = schema_str.replace("True", "true").replace("False", "false")
            
            try:
                # Convert schema string to JSON object
                schema = json.loads(schema_str)
                
                # Add the tool to our list
                tools.append({
                    "name": name,
                    "description": description,
                    "schema": schema
                })
                logger.info(f"Extracted tool: {name}")
            except json.JSONDecodeError as e:
                logger.warning(f"Error parsing schema for tool {name}: {e}")
        
        # Generate new registry file
        new_content = """\"\"\"IPFS MCP Tools Registry - Completely rebuilt\"\"\"

IPFS_TOOLS = [
"""
        
        # Add each tool
        for i, tool in enumerate(tools):
            tool_json = json.dumps(tool, indent=4)
            
            # Fix boolean literals for Python
            tool_json = tool_json.replace('"true"', 'True').replace('"false"', 'False')
            
            new_content += f"{tool_json}"
            if i < len(tools) - 1:
                new_content += ","
            new_content += "\n"
        
        # Close the list and add the function
        new_content += """]

def get_ipfs_tools():
    \"\"\"Get all IPFS tool definitions\"\"\"
    return IPFS_TOOLS
"""
        
        # Write the fixed file
        with open(registry_path, 'w') as f:
            f.write(new_content)
            
        logger.info(f"✅ Successfully rebuilt IPFS tools registry with {len(tools)} tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error rebuilding registry: {e}")
        return False

if __name__ == "__main__":
    fix_registry()
