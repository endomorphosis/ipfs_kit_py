#!/usr/bin/env python3
"""
Fix MCP Resource Handler Logger Issue

This script patches the MCP server to ensure the logger is correctly defined
in the resource handlers, fixing the 'name logger is not defined' error.
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_mcp_package_files():
    """Find the MCP package files to patch."""
    try:
        import mcp
        mcp_dir = os.path.dirname(mcp.__file__)
        logger.info(f"Found MCP package at {mcp_dir}")
        
        # Look for server-related files
        server_files = []
        for root, dirs, files in os.walk(mcp_dir):
            for file in files:
                if file.endswith('.py') and ('server' in file or 'resource' in file):
                    full_path = os.path.join(root, file)
                    server_files.append(full_path)
        
        logger.info(f"Found {len(server_files)} MCP server files to examine")
        return server_files
    except ImportError:
        logger.error("Could not import MCP package")
        return []

def analyze_files(files):
    """Analyze the files to find where logger is used but not defined."""
    problematic_files = []
    
    for file_path in files:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Check if logger is used but not defined
        if 'logger' in content and not re.search(r'(logger\s*=|import\s+logger)', content):
            problematic_files.append({
                'path': file_path,
                'content': content,
                'has_logging_import': 'import logging' in content
            })
    
    logger.info(f"Found {len(problematic_files)} files with potential logger issues")
    return problematic_files

def fix_files(problematic_files):
    """Fix the files by adding the proper logger definition."""
    fixed_files = []
    
    for file_info in problematic_files:
        path = file_info['path']
        content = file_info['content']
        has_logging_import = file_info['has_logging_import']
        
        # Add missing imports and logger definition
        if not has_logging_import:
            # Add import logging at the top of the file
            lines = content.split('\n')
            import_line = -1
            
            # Find where imports end
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    import_line = i
            
            if import_line >= 0:
                # Add after last import line
                lines.insert(import_line + 1, 'import logging')
                modified_content = '\n'.join(lines)
            else:
                # Add at the beginning, after doc strings
                if content.startswith('"""') or content.startswith("'''"):
                    end_quote = content.find('"""', 3) if content.startswith('"""') else content.find("'''", 3)
                    if end_quote > 0:
                        modified_content = content[:end_quote+3] + '\n\nimport logging\n' + content[end_quote+3:]
                    else:
                        modified_content = 'import logging\n' + content
                else:
                    modified_content = 'import logging\n' + content
        else:
            modified_content = content
        
        # Now add logger definition if it doesn't exist
        if 'logger = ' not in modified_content:
            # Find appropriate place to add logger
            lines = modified_content.split('\n')
            
            # Check if there's a class or function definition
            class_or_func_start = -1
            for i, line in enumerate(lines):
                if line.startswith('class ') or line.startswith('def '):
                    class_or_func_start = i
                    break
            
            if class_or_func_start > 0:
                # Add before the first class or function
                lines.insert(class_or_func_start, '\n# Configure module logger')
                lines.insert(class_or_func_start + 1, 'logger = logging.getLogger(__name__)')
                lines.insert(class_or_func_start + 2, '')
            else:
                # Add after imports
                import_line = -1
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        import_line = i
                
                if import_line >= 0:
                    lines.insert(import_line + 1, '\n# Configure module logger')
                    lines.insert(import_line + 2, 'logger = logging.getLogger(__name__)')
                    lines.insert(import_line + 3, '')
                else:
                    # Add at the beginning of the file
                    lines.insert(0, '# Configure module logger')
                    lines.insert(1, 'logger = logging.getLogger(__name__)')
                    lines.insert(2, '')
            
            modified_content = '\n'.join(lines)
        
        # Write the modified content back to the file
        backup_path = path + '.bak'
        logger.info(f"Creating backup of {path} at {backup_path}")
        with open(backup_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Writing fixes to {path}")
        with open(path, 'w') as f:
            f.write(modified_content)
        
        fixed_files.append(path)
    
    return fixed_files

def fix_direct_mcp_server():
    """Fix the logger issues in direct_mcp_server.py."""
    direct_mcp_path = "direct_mcp_server.py"
    
    # Check if the file exists
    if not os.path.exists(direct_mcp_path):
        logger.error(f"Could not find {direct_mcp_path}")
        return False
    
    # Read the file content
    with open(direct_mcp_path, 'r') as f:
        content = f.read()
    
    # Create a backup
    backup_path = direct_mcp_path + '.bak.logger'
    with open(backup_path, 'w') as f:
        f.write(content)
    
    # Check if the register_all_controller_tools method is present
    if "def register_all_controller_tools(self)" in content:
        # Add logger to register_all_controller_tools method
        pattern = r'(def register_all_controller_tools\(self\):.*?""".*?""")(.*?)(\s+self\.logger\.info)'
        replacement = r'\1\2\n        from logging import getLogger\n        logger = getLogger(__name__)\3'
        modified_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        if modified_content != content:
            # Write the modified content back to the file
            with open(direct_mcp_path, 'w') as f:
                f.write(modified_content)
            
            logger.info(f"Fixed logger issue in {direct_mcp_path}")
            return True
        else:
            logger.warning(f"Could not find the exact pattern to fix in {direct_mcp_path}")
            return False
    else:
        logger.warning(f"Could not find register_all_controller_tools method in {direct_mcp_path}")
        return False

def fix_register_all_controller_tools():
    """Fix the logger issues in register_all_controller_tools.py."""
    register_path = "register_all_controller_tools.py"
    
    # Check if the file exists
    if not os.path.exists(register_path):
        logger.error(f"Could not find {register_path}")
        return False
    
    # Read the file content
    with open(register_path, 'r') as f:
        content = f.read()
    
    # Create a backup
    backup_path = register_path + '.bak'
    with open(backup_path, 'w') as f:
        f.write(content)
    
    # Ensure register_controller_methods uses logger properly
    pattern = r'def register_controller_methods\(mcp_server, module_path\):(.*?)return count'
    replacement = r'def register_controller_methods(mcp_server, module_path):\1    # Ensure logger is accessible\n    global logger\n    return count'
    
    modified_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if modified_content != content:
        # Write the modified content back to the file
        with open(register_path, 'w') as f:
            f.write(modified_content)
        
        logger.info(f"Fixed logger issue in {register_path}")
        return True
    else:
        logger.warning(f"Could not find the exact pattern to fix in {register_path}")
        return False

def main():
    """Main function to fix the MCP resource handler logger issue."""
    logger.info("Starting MCP resource handler logger fix")
    
    # Fix direct_mcp_server.py
    fix_direct_mcp_server()
    
    # Fix register_all_controller_tools.py
    fix_register_all_controller_tools()
    
    # Find and fix MCP package files
    mcp_files = find_mcp_package_files()
    problematic_files = analyze_files(mcp_files)
    fixed_files = fix_files(problematic_files)
    
    logger.info(f"Fixed {len(fixed_files)} files with logger issues")
    logger.info("MCP resource handler logger fix completed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
