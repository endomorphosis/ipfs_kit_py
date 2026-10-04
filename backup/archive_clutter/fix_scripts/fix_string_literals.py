#!/usr/bin/env python3
"""
Quick fix for unterminated string literals in mcp_test_runner.py
"""

import re

def fix_all_strings():
    """Fix all unterminated string literals in the test runner"""
    try:
        with open('mcp_test_runner.py', 'r') as f:
            content = f.read()
        
        # Make a backup
        with open('mcp_test_runner.py.string_bak', 'w') as f:
            f.write(content)
            print("Created backup at mcp_test_runner.py.string_bak")
        
        # Find all lines with summary.append(" at the end of the line
        pattern = r'(^\s*summary\.append\(")(\s*)$'
        content = re.sub(pattern, r'\1\\n" +', content, flags=re.MULTILINE)
        
        # Fix any other potential issues
        content = content.replace('summary.append("\n', 'summary.append("\\n')
        
        with open('mcp_test_runner.py', 'w') as f:
            f.write(content)
        
        print("Fixed all unterminated string literals in mcp_test_runner.py")
        return True
    except Exception as e:
        print(f"Error fixing string literals: {e}")
        return False

if __name__ == "__main__":
    fix_all_strings()
