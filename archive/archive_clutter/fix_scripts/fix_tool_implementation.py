#!/usr/bin/env python3
"""
Fix for tool implementation in the MCP server.
This script adds the necessary 'use' method to Tool objects.
"""

import os
import sys
import logging
import inspect
import shutil
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak.toolimplement"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_tool_class():
    """Fix the Tool class implementation."""
    direct_mcp_file = Path("direct_mcp_server.py")
    
    # Create a backup
    backup_file(direct_mcp_file)
    
    with open(direct_mcp_file, 'r') as f:
        content = f.read()
    
    # Look for the Tool class definition
    lines = content.split('\n')
    tool_class_start = None
    tool_class_end = None
    indentation = 4  # Default indentation
    
    for i, line in enumerate(lines):
        if "class Tool:" in line or "class Tool(object):" in line:
            tool_class_start = i
            indentation = len(line) - len(line.lstrip())
            
            # Find where the class ends
            for j in range(i + 1, len(lines)):
                # Next class or function at the same indentation level marks the end
                if lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) <= indentation:
                    if lines[j].lstrip().startswith(('class ', 'def ', '@')):
                        tool_class_end = j
                        break
            
            # If we didn't find the end, it goes to the end of the file
            if tool_class_end is None:
                tool_class_end = len(lines)
            
            break
    
    if tool_class_start is None:
        logger.error("Could not find the Tool class definition in the file.")
        return False
    
    # Check if the 'use' method already exists
    use_method_exists = False
    for i in range(tool_class_start, tool_class_end):
        if "def use(" in lines[i]:
            use_method_exists = True
            break
    
    if use_method_exists:
        logger.info("The 'use' method already exists in the Tool class.")
        
        # We need to fix the implementation
        modified_lines = lines.copy()
        for i in range(tool_class_start, tool_class_end):
            if "def use(" in lines[i]:
                # Find the method body
                method_start = i
                method_body_indentation = len(lines[i + 1]) - len(lines[i + 1].lstrip()) if i + 1 < len(lines) else indentation + 4
                method_end = method_start + 1
                
                for j in range(method_start + 1, tool_class_end):
                    if lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) < method_body_indentation:
                        method_end = j
                        break
                
                # Replace with our implementation
                new_method = [
                    f"{' ' * indentation}async def use(self, arguments):",
                    f"{' ' * (indentation + 4)}\"\"\"Use the tool with the given arguments.\"\"\"",
                    f"{' ' * (indentation + 4)}if hasattr(self, 'handler') and callable(self.handler):",
                    f"{' ' * (indentation + 8)}try:",
                    f"{' ' * (indentation + 12)}# Check if it's an async function",
                    f"{' ' * (indentation + 12)}if inspect.iscoroutinefunction(self.handler):",
                    f"{' ' * (indentation + 16)}return await self.handler(**arguments)",
                    f"{' ' * (indentation + 12)}else:",
                    f"{' ' * (indentation + 16)}return self.handler(**arguments)",
                    f"{' ' * (indentation + 8)}except Exception as e:",
                    f"{' ' * (indentation + 12)}logger.error(f\"Error executing tool {{self.name}}: {{e}}\")",
                    f"{' ' * (indentation + 12)}raise",
                    f"{' ' * (indentation + 4)}else:",
                    f"{' ' * (indentation + 8)}raise ValueError(f\"Tool {{self.name}} has no handler method.\")",
                ]
                
                modified_lines[method_start:method_end] = new_method
                break
        
        # Update the content with our modified lines
        modified_content = '\n'.join(modified_lines)
        
        # Add import for inspect if not already there
        if "import inspect" not in modified_content:
            import_line = "import inspect"
            import_section_end = 0
            
            # Find a good place to insert the import
            for i, line in enumerate(modified_lines):
                if line.startswith('import ') or line.startswith('from '):
                    import_section_end = i + 1
            
            modified_lines.insert(import_section_end, import_line)
            modified_content = '\n'.join(modified_lines)
        
        # Write the modified content
        with open(direct_mcp_file, 'w') as f:
            f.write(modified_content)
        
        logger.info("Successfully updated the 'use' method in the Tool class")
        return True
    else:
        # Add the 'use' method to the Tool class
        tool_class_lines = lines[tool_class_start:tool_class_end]
        last_method_line = tool_class_start
        
        # Find the last method in the class to insert after it
        for i, line in enumerate(tool_class_lines):
            if line.strip().startswith('def '):
                last_method_line = tool_class_start + i
        
        # Create the 'use' method
        use_method = [
            "",  # Empty line before the method
            f"{' ' * indentation}async def use(self, arguments):",
            f"{' ' * (indentation + 4)}\"\"\"Use the tool with the given arguments.\"\"\"",
            f"{' ' * (indentation + 4)}if hasattr(self, 'handler') and callable(self.handler):",
            f"{' ' * (indentation + 8)}try:",
            f"{' ' * (indentation + 12)}# Check if it's an async function",
            f"{' ' * (indentation + 12)}if inspect.iscoroutinefunction(self.handler):",
            f"{' ' * (indentation + 16)}return await self.handler(**arguments)",
            f"{' ' * (indentation + 12)}else:",
            f"{' ' * (indentation + 16)}return self.handler(**arguments)",
            f"{' ' * (indentation + 8)}except Exception as e:",
            f"{' ' * (indentation + 12)}logger.error(f\"Error executing tool {{self.name}}: {{e}}\")",
            f"{' ' * (indentation + 12)}raise",
            f"{' ' * (indentation + 4)}else:",
            f"{' ' * (indentation + 8)}raise ValueError(f\"Tool {{self.name}} has no handler method.\")",
        ]
        
        # Insert the method into the class
        modified_lines = lines[:last_method_line + 1] + use_method + lines[last_method_line + 1:]
        
        # Update the content
        modified_content = '\n'.join(modified_lines)
        
        # Add import for inspect if not already there
        if "import inspect" not in modified_content:
            import_line = "import inspect"
            import_section_end = 0
            
            # Find a good place to insert the import
            for i, line in enumerate(modified_lines):
                if line.startswith('import ') or line.startswith('from '):
                    import_section_end = i + 1
            
            modified_lines.insert(import_section_end, import_line)
            modified_content = '\n'.join(modified_lines)
        
        # Write the modified content
        with open(direct_mcp_file, 'w') as f:
            f.write(modified_content)
        
        logger.info("Successfully added the 'use' method to the Tool class")
        return True

def main():
    """Main function."""
    logger.info("Fixing Tool class implementation...")
    
    if fix_tool_class():
        logger.info("\n✅ Tool class implementation fixed")
        logger.info("The MCP server should now be able to use tools through JSON-RPC")
        logger.info("Restart the MCP server to apply the changes:")
        logger.info("  1. Stop the current server")
        logger.info("  2. Start the server again")
        return 0
    else:
        logger.error("Failed to fix the Tool class implementation")
        return 1

if __name__ == "__main__":
    sys.exit(main())
