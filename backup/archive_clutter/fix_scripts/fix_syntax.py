#!/usr/bin/env python3
"""
This script fixes common syntax errors in the Python codebase.
"""

import os
import re
import sys
from pathlib import Path

# Directory to process
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def fix_trailing_commas(content):
    """Fix trailing commas in import statements and function definitions."""
    # Fix import statements with trailing commas
    content = re.sub(r'from\s+[\w\.]+\s+import\s+[\w\,\s]+,\s*\n', lambda m: m.group(0).rstrip(',\n') + '\n', content)

    # Fix function parameters with trailing commas
    return content


def fix_missing_commas_in_parameters(content):
    """Fix missing commas in method parameter lists."""
    # Fix method definitions missing commas after self
    content = re.sub(r'def\s+\w+\s*\(\s*self\s+', r'def \1(\1, ', content)

    return content


def fix_unterminated_strings(content):
    """Attempt to fix unterminated string literals."""
    # Look for obvious unterminated strings in error messages
    pattern = r'message_override="([^"]*?)\n'
    content = re.sub(pattern, r'message_override="\1"\n', content)

    return content


def fix_bracket_mismatches(content):
    """Fix common bracket mismatches."""
    # Fix specific pattern in HTTP exception raising
    content = re.sub(
        r'message_override=({[^}]+?}),\s+endpoint="([^"]+)",\s+doc_category="([^"]+)"\s+\),',
        r'message_override=\1, endpoint="\2", doc_category="\3"),',
        content
    )
    return content


def fix_parameterized_strings(content):
    """Fix parameter issues in string formatting."""
    # Fix common string formatting errors with result.get(
    content = re.sub(
        r'result\.get\(\,',
        r'result.get("error", "Unknown error"),',
        content
    )
    return content


def process_file(filepath):
    """Process a single file and fix syntax errors."""
    print(f"Processing {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply fixers
        original_content = content
        content = fix_trailing_commas(content)
        content = fix_missing_commas_in_parameters(content)
        content = fix_unterminated_strings(content)
        content = fix_bracket_mismatches(content)
        content = fix_parameterized_strings(content)

        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed issues in {filepath}")
        else:
            print(f"No changes needed for {filepath}")

    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")


def fix_specific_files():
    """Fix specific files known to have syntax errors."""
    known_files = [
        # Files identified from pytest output
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/storage/filecoin_controller.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/distributed_controller_anyio.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/fs_journal_controller.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/credential_controller_anyio.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller_anyio.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/peer_websocket_controller_anyio.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/storage/s3_controller_anyio.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_dashboard_controller_anyio.py",
    ]

    for filepath in known_files:
        if os.path.exists(filepath):
            process_file(filepath)
        else:
            print(f"File not found: {filepath}")


def fix_specific_errors():
    """Fix specific known errors manually."""

    # Fix filecoin_controller.py error with result.get(
    fc_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/storage/filecoin_controller.py"
    if os.path.exists(fc_path):
        with open(fc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the problematic line
        content = content.replace('"error": result.get(,', '"error": result.get("error", "Unknown error"),')

        with open(fc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed specific error in {fc_path}")

    # Fix distributed_controller_anyio.py list_nodes method
    dc_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/distributed_controller_anyio.py"
    if os.path.exists(dc_path):
        with open(dc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the problematic method definition
        content = content.replace(
            "async def list_nodes(\n        self\n        include_metrics:",
            "async def list_nodes(\n        self,\n        include_metrics:"
        )

        with open(dc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed list_nodes method in {dc_path}")

    # Fix webrtc_controller.py connections list
    wc_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller.py"
    if os.path.exists(wc_path):
        with open(wc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Fix any "connections": [, syntax
        content = content.replace('"connections": [,', '"connections": [')

        with open(wc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed connections list in {wc_path}")


if __name__ == "__main__":
    print("Starting syntax error fixing script...")

    # Fix specific known errors first
    fix_specific_errors()

    # Process specific files with known errors
    fix_specific_files()

    print("Script completed.")
