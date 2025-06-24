#!/usr/bin/env python3

"""
Script to check for syntax errors in high_level_api.py
"""

import os
import sys
import tokenize
from io import BytesIO

def check_syntax(file_path):
    """Check for syntax errors in the file by tokenizing it."""
    try:
        with open(file_path, 'rb') as f:
            tokens = list(tokenize.tokenize(f.readline))
        print(f"Successfully tokenized the file - no syntax errors!")
        return True
    except tokenize.TokenError as e:
        print(f"Tokenize error at line {e.args[1][0]}: {e.args[0]}")
        return False
    except SyntaxError as e:
        print(f"Syntax error at line {e.lineno}: {e.text}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def check_content(file_path):
    """Check for specific patterns that might cause syntax errors."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for common escape sequence issues
        if '"""\\"""' in content:
            print(f"Found problematic triple quote pattern: '\"\"\"\\\"\"\"'")

        # Check for unterminated triple quotes
        triple_quotes = content.count('"""')
        if triple_quotes % 2 != 0:
            print(f"Odd number of triple quotes: {triple_quotes} (should be even)")

        # Check if we can split the content into lines without error
        try:
            lines = content.splitlines()
            print(f"File has {len(lines)} lines")

            # Check line 4958 specifically where the error was reported
            if len(lines) >= 4958:
                print(f"Line 4958: {repr(lines[4957])}")

                # Check surrounding lines for context
                for i in range(max(4957-3, 0), min(4957+4, len(lines))):
                    print(f"Line {i+1}: {repr(lines[i])}")
        except Exception as e:
            print(f"Error splitting content into lines: {e}")

        return True
    except Exception as e:
        print(f"Error checking content: {e}")
        return False

if __name__ == "__main__":
    file_path = 'ipfs_kit_py/high_level_api.py'
    print(f"Checking syntax in {file_path}...")
    check_syntax(file_path)
    print("\nChecking content patterns...")
    check_content(file_path)
