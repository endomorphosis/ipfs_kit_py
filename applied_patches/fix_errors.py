#!/usr/bin/env python3
"""
Script to fix common code issues in Python files.
This targets unused imports, bare excepts, and other common issues.
"""

import os
import re
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Configuration
MCP_DIR = 'ipfs_kit_py/mcp'
BACKUP_DIR = f'code_backups_{datetime.now().strftime("%Y%m%d%H%M%S")}'
LOG_FILE = 'error_fixes.log'

def setup():
    """Set up the environment for fixing errors."""
    print(f"Creating backup directory: {BACKUP_DIR}")
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Initialize log file
    with open(LOG_FILE, 'w') as f:
        f.write(f"===== Starting Error Fixes {datetime.now()} =====\n")
        f.write(f"Target MCP directory: {MCP_DIR}\n")

def log(message):
    """Log a message to both console and log file."""
    print(message)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{message}\n")

def backup_file(file_path):
    """Create a backup of a file."""
    backup_path = os.path.join(BACKUP_DIR, os.path.basename(file_path))
    shutil.copy2(file_path, backup_path)
    return backup_path

def find_files_with_issues(error_code):
    """Find files with specific error codes using ruff."""
    try:
        output = subprocess.check_output(
            ['ruff', 'check', '--select', error_code, MCP_DIR],
            stderr=subprocess.STDOUT,
            text=True
        )

        # Extract file paths from the output
        files = set()
        for line in output.splitlines():
            if MCP_DIR in line and '.py:' in line:
                file_path = line.split(':')[0]
                files.add(file_path)

        return list(files)
    except subprocess.CalledProcessError as e:
        log(f"Error running ruff for {error_code}: {e.output}")
        return []

def fix_unused_imports():
    """Fix F401 unused imports."""
    log("\n==== Fixing F401 - Unused imports ====")

    # Find files with unused imports
    files = find_files_with_issues('F401')
    if not files:
        log("No files with unused imports found.")
        return

    for file_path in files:
        log(f"Processing {file_path} for unused imports")
        backup_file(file_path)

        # Run with --output-format=json to get detailed information
        try:
            # Get unused import details
            cmd = ['ruff', 'check', '--select=F401', file_path]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)

            # Now manually parse the output to find unused imports
            # Look for patterns like: file.py:10:5: F401 'module' imported but unused
            unused_imports = []
            for line in output.splitlines():
                if "F401" in line and "imported but unused" in line:
                    # Extract the import name
                    match = re.search(r"'([^']+)'", line)
                    if match:
                        unused_imports.append(match.group(1))

            if unused_imports:
                with open(file_path, 'r') as f:
                    content = f.read()

                # Fix each unused import
                for unused_import in unused_imports:
                    log(f"  Removing unused import: {unused_import}")

                    # Try to match and remove the unused import
                    # First check for exact import statements
                    pattern1 = rf"^import\s+{re.escape(unused_import)}\s*$"
                    content = re.sub(pattern1, "", content, flags=re.MULTILINE)

                    # Check for from X import Y statements
                    for line in content.splitlines():
                        if f"from " in line and f" import {unused_import}" in line:
                            if f" import {unused_import}," in line:
                                # Part of multiple imports
                                line_new = line.replace(f"{unused_import},", "").replace(f", {unused_import}", "")
                                content = content.replace(line, line_new)
                            elif f" import {unused_import}" in line and not f" import {unused_import}" in line:
                                # Single import
                                content = content.replace(line, "")

                # Clean up any empty lines
                content = re.sub(r"\n\s*\n", "\n\n", content)

                # Write back to file
                with open(file_path, 'w') as f:
                    f.write(content)

        except subprocess.CalledProcessError as e:
            log(f"  Error processing {file_path}: {e.output}")

def fix_bare_excepts():
    """Fix E722 bare except statements."""
    log("\n==== Fixing E722 - Bare except blocks ====")

    # Find files with bare excepts
    files = find_files_with_issues('E722')
    if not files:
        log("No files with bare excepts found.")
        return

    for file_path in files:
        log(f"Processing {file_path} for bare except blocks")
        backup_file(file_path)

        with open(file_path, 'r') as f:
            content = f.read()

        # Replace bare 'except:' with 'except Exception:'
        # But be careful not to modify valid except statements like 'except ValueError:'
        fixed_content = re.sub(r'except\s*:', 'except Exception:', content)

        if fixed_content != content:
            with open(file_path, 'w') as f:
                f.write(fixed_content)
            log(f"  Fixed bare except statements in {file_path}")

def fix_late_imports():
    """Fix E402 imports not at top of file."""
    log("\n==== Fixing E402 - Imports not at top of file ====")

    # This requires careful analysis, so we'll just identify files for manual review
    files = find_files_with_issues('E402')
    if not files:
        log("No files with imports not at top found.")
        return

    with open('manual_review_late_imports.txt', 'w') as f:
        for file_path in files:
            log(f"Marked for manual review: {file_path} (imports not at top)")
            f.write(f"{file_path}\n")

def fix_import_star():
    """Fix F403 import star issues."""
    log("\n==== Fixing F403 - Import star issues ====")

    # This requires careful analysis, so we'll just identify files for manual review
    files = find_files_with_issues('F403')
    if not files:
        log("No files with import star issues found.")
        return

    with open('manual_review_import_star.txt', 'w') as f:
        for file_path in files:
            log(f"Marked for manual review: {file_path} (import star issues)")
            f.write(f"{file_path}\n")

def identify_other_issues():
    """Identify files with other issues for manual review."""
    log("\n==== Identifying files for manual review ====")

    # Track these issues separately
    issue_types = {
        'F811': 'redefined_vars',
        'F821': 'undefined_names',
        'F823': 'undefined_locals',
        'E741': 'ambiguous_vars'
    }

    for code, issue_name in issue_types.items():
        files = find_files_with_issues(code)
        if files:
            with open(f'manual_review_{issue_name}.txt', 'w') as f:
                for file_path in files:
                    log(f"Marked for manual review: {file_path} ({code} - {issue_name})")
                    f.write(f"{file_path}\n")

def generate_review_summary():
    """Generate a summary of files needing manual review."""
    log("\n==== Generating manual review summary ====")

    with open('manual_review_summary.txt', 'w') as summary:
        summary.write("===== Files Needing Manual Review =====\n")

        review_files = {
            'manual_review_late_imports.txt': 'E402 - Imports not at top of file',
            'manual_review_import_star.txt': 'F403 - Undefined locals with import star',
            'manual_review_redefined_vars.txt': 'F811 - Redefined but unused variables',
            'manual_review_undefined_names.txt': 'F821 - Undefined names',
            'manual_review_undefined_locals.txt': 'F823 - Undefined local variables',
            'manual_review_ambiguous_vars.txt': 'E741 - Ambiguous variable names'
        }

        for file_name, description in review_files.items():
            if os.path.exists(file_name):
                summary.write(f"\n== {description} ==\n")
                with open(file_name, 'r') as f:
                    content = f.read()
                    summary.write(content)

    log("Manual review summary generated: manual_review_summary.txt")

def run_final_fixes():
    """Run final passes with Ruff and Black."""
    log("\n==== Running final passes with Ruff and Black ====")

    try:
        subprocess.run(['ruff', 'check', '--fix', MCP_DIR], check=False)
        subprocess.run(['black', MCP_DIR], check=False)

        # Get statistics on remaining issues
        log("\n===== Final Error Status =====")
        log(f"Fix process completed at {datetime.now()}")

        result = subprocess.run(
            ['ruff', 'check', MCP_DIR, '--statistics'],
            capture_output=True,
            text=True,
            check=False
        )
        log(result.stdout)
        print(result.stdout)

    except Exception as e:
        log(f"Error during final fixes: {e}")

def create_targeted_fixes():
    """Create a Python script for targeted fixes of specific issues."""
    log("\n==== Creating targeted fix script for remaining issues ====")

    with open('targeted_fixes.py', 'w') as f:
        f.write("""#!/usr/bin/env python3
\"\"\"
Script for targeted fixes of specific issues in Python files.
This addresses issues that the automated script couldn't fix.
\"\"\"

import os
import re
import sys
import glob

def fix_undefined_names(file_path):
    \"\"\"Fix undefined name issues by adding imports.\"\"\"
    print(f"Fixing undefined names in {file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    # Common undefined names and their imports
    common_imports = {
        'logging': 'import logging',
        'logger': 'logger = logging.getLogger(__name__)',
        'APIRouter': 'from fastapi import APIRouter',
        'HTTPException': 'from fastapi import HTTPException',
        'Request': 'from fastapi import Request',
        'Response': 'from fastapi import Response',
        'Body': 'from fastapi import Body',
        'Query': 'from fastapi import Query',
        'Path': 'from fastapi import Path',
        'Optional': 'from typing import Optional',
        'List': 'from typing import List',
        'Dict': 'from typing import Dict',
        'Any': 'from typing import Any',
        'BaseModel': 'from pydantic import BaseModel',
        'Field': 'from pydantic import Field',
        'Enum': 'from enum import Enum',
        'json': 'import json',
        'time': 'import time',
        'os': 'import os',
        'sys': 'import sys',
        'asyncio': 'import asyncio',
        'traceback': 'import traceback',
    }

    # Add missing imports
    for name, import_stmt in common_imports.items():
        # Check if name is used but not imported
        if re.search(r'\\b' + re.escape(name) + r'\\b', content) and import_stmt not in content:
            # Add import at the top of the file
            content = import_stmt + '\\n' + content
            print(f"  Added import: {import_stmt}")

    with open(file_path, 'w') as f:
        f.write(content)

def fix_bare_excepts(file_path):
    \"\"\"Replace bare excepts with specific exception types.\"\"\"
    print(f"Fixing bare excepts in {file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    # Replace bare 'except:' with 'except Exception:'
    fixed_content = re.sub(r'except\\s*:', 'except Exception:', content)

    if fixed_content != content:
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        print(f"  Fixed bare except statements")

def main():
    \"\"\"Main function to process files.\"\"\"
    if len(sys.argv) < 2:
        print("Usage: python targeted_fixes.py <file_or_directory>")
        return

    target = sys.argv[1]

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        files = glob.glob(os.path.join(target, '**', '*.py'), recursive=True)
    else:
        print(f"Error: {target} is not a valid file or directory")
        return

    for file_path in files:
        print(f"\\nProcessing {file_path}")
        fix_undefined_names(file_path)
        fix_bare_excepts(file_path)

if __name__ == "__main__":
    main()
""")

    # Make the script executable
    os.chmod('targeted_fixes.py', 0o755)
    log("Created targeted_fixes.py for manual application to specific files")

def main():
    """Main function to run all fixes."""
    setup()
    log(f"Starting error fixes at {datetime.now()}")

    # Fix specific error types
    fix_unused_imports()
    fix_bare_excepts()
    fix_late_imports()
    fix_import_star()
    identify_other_issues()

    # Generate summary and final reports
    generate_review_summary()
    create_targeted_fixes()
    run_final_fixes()

    log("\nFixes applied. See error_fixes.log for details.")
    log("Files requiring manual review are listed in manual_review_summary.txt")
    log("Use targeted_fixes.py for further manual fixes of specific issues")

if __name__ == "__main__":
    main()
