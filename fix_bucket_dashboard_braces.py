#!/usr/bin/env python3
"""
Fix unescaped curly braces in bucket_dashboard.py f-string.
"""

def fix_bucket_dashboard_braces():
    """Fix all unescaped curly braces in the f-string."""
    
    with open('/home/devel/ipfs_kit_py/ipfs_kit_py/bucket_dashboard.py', 'r') as f:
        content = f.read()
    
    # Find the f-string boundaries
    start_marker = 'return f"""'
    end_marker = '"""'
    
    start_pos = content.find(start_marker)
    if start_pos == -1:
        print("Could not find f-string start")
        return False
    
    start_pos += len(start_marker)
    end_pos = content.find(end_marker, start_pos)
    if end_pos == -1:
        print("Could not find f-string end")
        return False
    
    # Get the f-string content
    before_fstring = content[:start_pos]
    fstring_content = content[start_pos:end_pos]
    after_fstring = content[end_pos:]
    
    print(f"F-string content length: {len(fstring_content)} characters")
    
    # Fix the f-string content
    # We need to escape single braces that are not already escaped
    # But preserve template literals and other intentional braces
    
    fixed_content = fstring_content
    
    # Patterns to fix systematically
    replacements = [
        # JavaScript function/control structures
        ('async function refreshBuckets() {', 'async function refreshBuckets() {{'),
        ('} else {', '}} else {{'),
        ('} catch (error) {', '}} catch (error) {{'),
        ('try {', 'try {{'),
        ('if (', 'if ('),  # Don't change this, just the closing braces
        ('function (', 'function ('),  # Don't change this
        
        # Common JavaScript patterns that need escaping
        (') {', ') {{'),
        ('} ', '}} '),
        
        # But preserve template literals with ${...}
        # These are already handled correctly in the original
    ]
    
    # More systematic approach: escape all single braces except in template literals
    import re
    
    # First, protect template literals and already escaped braces
    protected_parts = []
    temp_content = fixed_content
    
    # Find and temporarily replace protected patterns
    # 1. Template literals: ${...}
    template_literal_pattern = r'\\$\\{[^}]*\\}'
    protected_parts.extend(re.findall(template_literal_pattern, temp_content))
    for i, part in enumerate(protected_parts):
        temp_content = temp_content.replace(part, f'__PROTECTED_{i}__', 1)
    
    # 2. Already escaped braces: {{ and }}
    escaped_open_pattern = r'\\{\\{'
    escaped_close_pattern = r'\\}\\}'
    escaped_opens = re.findall(escaped_open_pattern, temp_content)
    escaped_closes = re.findall(escaped_close_pattern, temp_content)
    
    for i, part in enumerate(escaped_opens):
        temp_content = temp_content.replace(part, f'__ESCAPED_OPEN_{i}__', 1)
        protected_parts.append(part)
    
    for i, part in enumerate(escaped_closes):
        temp_content = temp_content.replace(part, f'__ESCAPED_CLOSE_{i}__', 1)
        protected_parts.append(part)
    
    # Now escape all remaining single braces
    temp_content = temp_content.replace('{', '{{')
    temp_content = temp_content.replace('}', '}}')
    
    # Restore protected parts
    for i, part in enumerate(protected_parts):
        if part.startswith('{{'):
            temp_content = temp_content.replace(f'__ESCAPED_OPEN_{i}__', part, 1)
        elif part.startswith('}}'):
            temp_content = temp_content.replace(f'__ESCAPED_CLOSE_{i}__', part, 1)
        else:
            temp_content = temp_content.replace(f'__PROTECTED_{i}__', part, 1)
    
    fixed_content = temp_content
    
    # Reconstruct the file
    new_content = before_fstring + fixed_content + after_fstring
    
    # Write the fixed content
    with open('/home/devel/ipfs_kit_py/ipfs_kit_py/bucket_dashboard.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Fixed bucket_dashboard.py f-string braces")
    return True


if __name__ == "__main__":
    fix_bucket_dashboard_braces()
