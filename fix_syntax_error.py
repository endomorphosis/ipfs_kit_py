#!/usr/bin/env python3
"""
Script to fix syntax errors in high_level_api.py
"""

def fix_syntax_error():
    """Fix syntax errors in high_level_api.py"""
    input_file = "ipfs_kit_py/high_level_api.py"
    output_file = "ipfs_kit_py/high_level_api.py.fixed"
    
    with open(input_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Store fixed lines
    fixed_lines = []
    
    # Keep track of try blocks
    in_try_block = False
    has_except = False
    
    # Process lines one by one
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for method definitions to handle duplicates
        if line.strip().startswith("def ai_update_deployment("):
            # Skip this duplicate method definition
            # Count indentation level
            indent = len(line) - len(line.lstrip())
            
            # Skip until we find a line with lesser or equal indentation
            skip_count = 0
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip() and len(next_line) - len(next_line.lstrip()) <= indent:
                    break
                skip_count += 1
                j += 1
            
            # Skip this duplicate method
            i += skip_count + 1
            continue
        
        # Handle try blocks
        if line.strip() == 'try:':
            in_try_block = True
            has_except = False
        elif line.strip().startswith('except '):
            has_except = True
        elif in_try_block and line.strip() and not has_except:
            # Check if this line starts a new method or ends the try block
            if (line.strip().startswith('def ') or 
                line.strip().startswith('class ') or 
                line.strip() == '# Create a singleton instance for easy import'):
                # Add an except block before this line
                indent = len(lines[i-1]) - len(lines[i-1].lstrip())
                fixed_lines.append(' ' * indent + 'except Exception as e:\n')
                fixed_lines.append(' ' * indent + '    return {"success": False, "error": str(e)}\n')
                in_try_block = False
                has_except = False
        
        # Add the current line
        fixed_lines.append(line)
        i += 1
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as file:
        file.writelines(fixed_lines)
    
    print(f"Fixed content written to {output_file}")
    return True

if __name__ == "__main__":
    fix_syntax_error()