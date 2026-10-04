#!/usr/bin/env python3
"""
MCP Roadmap Synchronization Script

This script ensures that both copies of the MCP roadmap file
remain in sync, with the root version being the source of truth.
"""

import sys
import os
import shutil
import re
from pathlib import Path
import logging
import argparse
import difflib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("roadmap_sync")

def add_warning_header(file_path, is_canonical=True):
    """Add appropriate warning header to the file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define the warning based on whether this is the canonical version
    if is_canonical:
        warning = "> **IMPORTANT**: This is the canonical roadmap file. There is another copy in `/docs/mcp_roadmap.md` that should be kept in sync with this file.\n\n"
    else:
        warning = "> **IMPORTANT**: This is a copy of the roadmap file. The canonical version is at the root directory (`/mcp_roadmap.md`). This file should be kept in sync with the canonical version.\n\n"
    
    # Check if a warning already exists
    if '> **IMPORTANT**' in content:
        # Replace existing warning
        content = re.sub(r'> \*\*IMPORTANT\*\*.*?\n\n', warning, content, flags=re.DOTALL)
    else:
        # Insert warning after first heading
        content = re.sub(r'(# .*?\n\n)', r'\1' + warning, content, count=1)
    
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(content)
    
    return content

def sync_roadmap_files(args):
    """Synchronize the roadmap files."""
    project_root = Path(__file__).resolve().parent.parent
    canonical_path = project_root / "mcp_roadmap.md"
    docs_path = project_root / "docs" / "mcp_roadmap.md"
    
    if not canonical_path.exists():
        logger.error(f"Canonical roadmap file not found at: {canonical_path}")
        return False
    
    # Create backup of docs version if it exists
    if docs_path.exists() and not args.no_backup:
        backup_path = docs_path.with_suffix('.md.bak')
        shutil.copy2(docs_path, backup_path)
        logger.info(f"Created backup of docs roadmap at: {backup_path}")
    
    # Update the canonical version warning
    canonical_content = add_warning_header(canonical_path, is_canonical=True)
    
    if args.check_only:
        # Just compare the files and report differences
        if docs_path.exists():
            with open(docs_path, 'r') as f:
                docs_content = f.read()
            
            # Compare content (ignoring warning headers)
            canonical_cleaned = re.sub(r'> \*\*IMPORTANT\*\*.*?\n\n', '', canonical_content, flags=re.DOTALL)
            docs_cleaned = re.sub(r'> \*\*IMPORTANT\*\*.*?\n\n', '', docs_content, flags=re.DOTALL)
            
            if canonical_cleaned != docs_cleaned:
                logger.warning("Files are different!")
                diff = difflib.unified_diff(
                    docs_cleaned.splitlines(True),
                    canonical_cleaned.splitlines(True),
                    fromfile=str(docs_path),
                    tofile=str(canonical_path)
                )
                sys.stdout.writelines(diff)
                return False
            else:
                logger.info("Files are synchronized (ignoring warning headers)")
                return True
        else:
            logger.warning(f"Docs roadmap does not exist at: {docs_path}")
            return False
    else:
        # Create docs directory if it doesn't exist
        docs_path.parent.mkdir(exist_ok=True)
        
        # Copy canonical to docs (overwriting existing)
        shutil.copy2(canonical_path, docs_path)
        logger.info(f"Copied canonical roadmap to: {docs_path}")
        
        # Update the docs version warning
        add_warning_header(docs_path, is_canonical=False)
        logger.info("Updated warning headers in both files")
        
        return True

def main():
    """Parse arguments and execute sync."""
    parser = argparse.ArgumentParser(description='Synchronize MCP roadmap files')
    parser.add_argument('--check-only', action='store_true', help='Only check if files are in sync')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup of docs version')
    parser.add_argument('--force', action='store_true', help='Force sync even if files are already in sync')
    
    args = parser.parse_args()
    
    logger.info("Starting roadmap synchronization")
    result = sync_roadmap_files(args)
    
    if result:
        logger.info("Roadmap synchronization completed successfully")
        return 0
    else:
        if args.check_only:
            logger.warning("Roadmap files are not in sync")
        else:
            logger.error("Roadmap synchronization failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())