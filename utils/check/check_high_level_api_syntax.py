"""
Syntax Check Utility for high_level_api module.

This utility script verifies the syntax of the high_level_api.py module
without executing it or importing dependencies. It's used primarily during
development to check for syntax errors in the high-level API implementation.

Note: This is not a test file, but a utility script. The actual tests for
high_level_api.py are in the test/test_high_level_api.py file.
"""

import ast
import sys

def check_file_syntax(file_path):
    """Check syntax of a Python file."""
    print(f"Checking syntax in {file_path}...")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Check syntax by parsing the source file
        ast.parse(source)
        print("Syntax check passed!")
        return True
    except SyntaxError as e:
        print(f"Syntax error at line {e.lineno}, column {e.offset}: {e.msg}")
        if e.text:
            print(f"Line content: {e.text.strip()}")
        print(f"Error details: {e}")
        return False
    except Exception as e:
        print(f"Error checking syntax: {e}")
        return False

if __name__ == "__main__":
    # Path to the module
    module_path = "./ipfs_kit_py/high_level_api.py"

    # Check syntax
    result = check_file_syntax(module_path)

    # Exit with status code
    sys.exit(0 if result else 1)
