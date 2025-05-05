#!/usr/bin/env python3
"""
Workspace Organization Script

This script analyzes the ipfs_kit_py workspace and identifies which files
should be kept, archived, or removed to reduce code debt and maintain
a clean, well-organized workspace.
"""

import os
import sys
import re
import shutil
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("organize_workspace.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("organize-workspace")

# Define categories for files
CATEGORIES = {
    "keep": {
        "description": "Files that should be kept in the workspace",
        "files": set()
    },
    "archive": {
        "description": "Files that should be archived (still useful but not needed in the root directory)",
        "files": set()
    },
    "delete": {
        "description": "Files that can be safely deleted (redundant, temporary, or obsolete)",
        "files": set()
    },
    "unknown": {
        "description": "Files that need manual review",
        "files": set()
    }
}

# Define key files that must be kept
KEY_FILES = {
    # Core server files
    "final_mcp_server.py",
    "unified_ipfs_tools.py",
    "enhance_vfs_mcp_integration.py",
    "ipfs_mcp_fs_integration.py",
    
    # Test files
    "test_ipfs_mcp_tools.py",
    "test_final_mcp_server.py",
    
    # Config files
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    
    # Documentation files
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "CONTRIBUTING.md",
    
    # Scripts
    "restart_enhanced_mcp_server.sh",
    "start_final_mcp_server.sh",
    "stop_ipfs_mcp_server.sh",
    "organize_workspace.py"
}

# Define patterns for backup files and temporary files
BACKUP_PATTERNS = [
    r".*\.bak$",
    r".*\.bak\.[a-z0-9_]+$",
    r".*\.backup$",
    r".*_backup$",
    r".*\.py\.\d+$",
    r".*\.orig$",
    r".*~$",
    r".*_old$"
]

# Define patterns for log files
LOG_PATTERNS = [
    r".*\.log$",
    r".*_log$",
    r".*\.log\.\d+$"
]

# Define patterns for files that should be archived
ARCHIVE_PATTERNS = [
    r"direct_mcp_server\.py$",  # The direct MCP server should be archived but kept
    r"fix_.*\.py$",             # Fix scripts should be archived
    r"enhance_.*\.py$",         # Enhancement scripts should be archived
    r"register_.*\.py$"         # Registration scripts should be archived
]

def categorize_files(workspace_dir: str) -> Dict[str, Set[str]]:
    """
    Categorize files in the workspace directory.
    
    Args:
        workspace_dir: The workspace directory to analyze
        
    Returns:
        Dict of file paths categorized by "keep", "archive", or "delete"
    """
    categorized: Dict[str, Set[str]] = {
        "keep": set(),
        "archive": set(),
        "delete": set(),
        "unknown": set()
    }
    
    # Get all files in workspace_dir
    all_files = []
    for root, _, files in os.walk(workspace_dir):
        for file in files:
            # Skip files in subdirectories like .git, __pycache__, etc.
            if any(part.startswith('.') for part in Path(root).parts):
                continue
            if "__pycache__" in root:
                continue
                
            file_path = os.path.relpath(os.path.join(root, file), workspace_dir)
            all_files.append(file_path)
    
    logger.info(f"Found {len(all_files)} files in the workspace")
    
    # First, identify key files to keep
    for file in all_files:
        filename = os.path.basename(file)
        
        # Keep key files
        if filename in KEY_FILES or file in KEY_FILES:
            categorized["keep"].add(file)
            continue
        
        # Categorize backup files for deletion
        if any(re.match(pattern, filename) for pattern in BACKUP_PATTERNS):
            categorized["delete"].add(file)
            continue
            
        # Categorize log files for deletion
        if any(re.match(pattern, filename) for pattern in LOG_PATTERNS):
            categorized["delete"].add(file)
            continue
        
        # Categorize files that should be archived
        if any(re.match(pattern, filename) for pattern in ARCHIVE_PATTERNS):
            categorized["archive"].add(file)
            continue
            
        # Check if it's a Python file
        if filename.endswith('.py'):
            # If it's not a core file and not already categorized,
            # put it in the archive category
            if not is_core_python_file(file, workspace_dir):
                categorized["archive"].add(file)
                continue
            else:
                categorized["keep"].add(file)
                continue
        
        # Check if it's a shell script
        if filename.endswith('.sh'):
            if is_important_shell_script(file, workspace_dir):
                categorized["keep"].add(file)
            else:
                categorized["archive"].add(file)
            continue
            
        # For any other files, mark them as unknown for manual review
        categorized["unknown"].add(file)
    
    return categorized

def is_core_python_file(file: str, workspace_dir: str) -> bool:
    """
    Check if a Python file is a core file that should be kept.
    
    Args:
        file: The file path relative to workspace_dir
        workspace_dir: The workspace directory
        
    Returns:
        True if the file is a core Python file, False otherwise
    """
    # Check if it's in the KEY_FILES list
    if os.path.basename(file) in KEY_FILES or file in KEY_FILES:
        return True
    
    # Read the file and check its content
    try:
        with open(os.path.join(workspace_dir, file), 'r') as f:
            content = f.read()
            
        # If the file has "mcp" or "ipfs" in its name and defines actual functionality
        if "mcp" in file.lower() or "ipfs" in file.lower():
            # Check if it defines classes or functions
            if re.search(r'class\s+\w+\s*\(', content) or re.search(r'def\s+\w+\s*\(', content):
                # Check if it's not just a fix or enhancement script
                if not re.search(r'(fix|enhance|update|register)_', file.lower()):
                    return True
        
        # Check for files used by imports in core files
        for key_file in KEY_FILES:
            if key_file.endswith('.py'):
                key_file_path = os.path.join(workspace_dir, key_file)
                if os.path.exists(key_file_path):
                    with open(key_file_path, 'r') as kf:
                        key_content = kf.read()
                        module_name = os.path.splitext(os.path.basename(file))[0]
                        if f"import {module_name}" in key_content or f"from {module_name} import" in key_content:
                            return True
    except Exception as e:
        logger.warning(f"Error reading file {file}: {e}")
    
    return False

def is_important_shell_script(file: str, workspace_dir: str) -> bool:
    """
    Check if a shell script is important and should be kept.
    
    Args:
        file: The file path relative to workspace_dir
        workspace_dir: The workspace directory
        
    Returns:
        True if the script is important, False otherwise
    """
    # Check if it's in the KEY_FILES list
    if os.path.basename(file) in KEY_FILES or file in KEY_FILES:
        return True
    
    # Check if it's related to the final MCP server
    filename = os.path.basename(file)
    if "final_mcp" in filename or "fixed_mcp" in filename:
        return True
    
    # Check if it's referenced by other important files
    try:
        with open(os.path.join(workspace_dir, file), 'r') as f:
            content = f.read()
            
        # If it's a substantial script with useful functionality
        if len(content.strip().split('\n')) > 20:  # More than 20 non-empty lines
            # Check if it's not just a temporary or test script
            if not any(pattern in filename for pattern in ["test_", "temp_", "tmp_", "example_"]):
                return True
    except Exception as e:
        logger.warning(f"Error reading file {file}: {e}")
    
    return False

def create_organization_plan(categorized_files: Dict[str, Set[str]]) -> Dict[str, Any]:
    """
    Create a detailed organization plan based on categorized files.
    
    Args:
        categorized_files: Dict of files categorized by "keep", "archive", or "delete"
        
    Returns:
        Dict with the organization plan
    """
    plan = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_files": sum(len(files) for files in categorized_files.values()),
            "keep": len(categorized_files["keep"]),
            "archive": len(categorized_files["archive"]),
            "delete": len(categorized_files["delete"]),
            "unknown": len(categorized_files["unknown"])
        },
        "categories": {
            "keep": {
                "description": CATEGORIES["keep"]["description"],
                "files": sorted(list(categorized_files["keep"]))
            },
            "archive": {
                "description": CATEGORIES["archive"]["description"],
                "files": sorted(list(categorized_files["archive"]))
            },
            "delete": {
                "description": CATEGORIES["delete"]["description"],
                "files": sorted(list(categorized_files["delete"]))
            },
            "unknown": {
                "description": CATEGORIES["unknown"]["description"],
                "files": sorted(list(categorized_files["unknown"]))
            }
        },
        "recommendations": {
            "general": [
                "Keep the core MCP server files in the root directory",
                "Archive fix scripts, enhancement scripts, and registration scripts",
                "Delete backup files and logs",
                "Review unknown files manually"
            ],
            "specific": []
        }
    }
    
    # Add specific recommendations based on patterns observed
    if len(categorized_files["archive"]) > 20:
        plan["recommendations"]["specific"].append(
            "Consider creating subdirectories for archived files (e.g., ./archive/fixes, ./archive/enhancements)"
        )
    
    if len(categorized_files["delete"]) > 10:
        plan["recommendations"]["specific"].append(
            "Large number of backup/temp files detected. Consider adding them to .gitignore"
        )
    
    if any("README" in file for file in categorized_files["keep"]):
        plan["recommendations"]["specific"].append(
            "Update README.md to reflect the new workspace structure and document the final_mcp_server.py"
        )
    
    if any("requirements" in file for file in categorized_files["keep"]):
        plan["recommendations"]["specific"].append(
            "Ensure requirements.txt is up-to-date with all needed dependencies"
        )
    
    return plan

def execute_organization_plan(plan: Dict[str, Any], workspace_dir: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Execute the organization plan by moving files to appropriate directories.
    
    Args:
        plan: The organization plan
        workspace_dir: The workspace directory
        dry_run: If True, don't actually move files, just simulate
        
    Returns:
        Dict with execution results
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "actions": [],
        "errors": []
    }
    
    # Create necessary directories if they don't exist
    archive_dir = os.path.join(workspace_dir, "archive")
    trash_dir = os.path.join(workspace_dir, "trash")
    
    try:
        if not dry_run:
            os.makedirs(archive_dir, exist_ok=True)
            os.makedirs(trash_dir, exist_ok=True)
    except Exception as e:
        results["errors"].append(f"Failed to create directories: {e}")
        return results
    
    # Keep files stay in place
    for file in plan["categories"]["keep"]["files"]:
        results["actions"].append({
            "file": file,
            "action": "keep",
            "details": "File remains in place"
        })
    
    # Move archived files to archive directory
    for file in plan["categories"]["archive"]["files"]:
        source = os.path.join(workspace_dir, file)
        
        # Create subdirectory based on file type
        subdir = "misc"
        if "fix" in file:
            subdir = "fixes"
        elif "enhance" in file:
            subdir = "enhancements"
        elif "test" in file:
            subdir = "tests"
        elif "register" in file or "tool" in file:
            subdir = "tools"
        elif file.endswith('.sh'):
            subdir = "scripts"
            
        target_dir = os.path.join(archive_dir, subdir)
        target = os.path.join(target_dir, os.path.basename(file))
        
        try:
            if not dry_run:
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(source, target)
            
            results["actions"].append({
                "file": file,
                "action": "archive",
                "destination": os.path.join("archive", subdir, os.path.basename(file)),
                "details": f"Moved to {target}"
            })
        except Exception as e:
            results["errors"].append(f"Failed to archive {file}: {e}")
    
    # Move files to delete to the trash directory
    for file in plan["categories"]["delete"]["files"]:
        source = os.path.join(workspace_dir, file)
        target = os.path.join(trash_dir, os.path.basename(file))
        
        try:
            if not dry_run:
                shutil.move(source, target)
            
            results["actions"].append({
                "file": file,
                "action": "delete",
                "destination": os.path.join("trash", os.path.basename(file)),
                "details": f"Moved to {target}"
            })
        except Exception as e:
            results["errors"].append(f"Failed to delete {file}: {e}")
    
    # Report on unknown files
    for file in plan["categories"]["unknown"]["files"]:
        results["actions"].append({
            "file": file,
            "action": "unknown",
            "details": "Requires manual review"
        })
    
    return results

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Organize IPFS Kit Workspace")
    parser.add_argument("--workspace", type=str, default=".", help="Workspace directory (default: current directory)")
    parser.add_argument("--output", type=str, help="Output file for organization plan")
    parser.add_argument("--execute", action="store_true", help="Execute the organization plan")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without moving files")
    
    args = parser.parse_args()
    
    workspace_dir = os.path.abspath(args.workspace)
    logger.info(f"Analyzing workspace: {workspace_dir}")
    
    # Categorize files
    categorized_files = categorize_files(workspace_dir)
    
    # Create organization plan
    plan = create_organization_plan(categorized_files)
    
    # Output plan
    if args.output:
        with open(args.output, "w") as f:
            json.dump(plan, f, indent=2)
        logger.info(f"Organization plan written to {args.output}")
    
    # Print summary
    print("\nWorkspace Organization Summary:")
    print("=============================")
    print(f"Total files: {plan['summary']['total_files']}")
    print(f"Files to keep: {plan['summary']['keep']}")
    print(f"Files to archive: {plan['summary']['archive']}")
    print(f"Files to delete: {plan['summary']['delete']}")
    print(f"Files requiring manual review: {plan['summary']['unknown']}")
    
    # Execute plan
    if args.execute or args.dry_run:
        logger.info(f"Executing organization plan (dry run: {args.dry_run})")
        results = execute_organization_plan(plan, workspace_dir, dry_run=args.dry_run or not args.execute)
        
        # Output results
        if args.output:
            results_file = args.output.replace(".json", "_results.json")
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Execution results written to {results_file}")
        
        # Print execution summary
        print("\nExecution Summary:")
        if args.dry_run and not args.execute:
            print("(Dry run mode - no files were actually moved)")
        
        action_counts = {}
        for action in results["actions"]:
            action_type = action["action"]
            action_counts[action_type] = action_counts.get(action_type, 0) + 1
        
        for action_type, count in action_counts.items():
            print(f"{action_type.capitalize()}: {count} files")
        
        if results["errors"]:
            print(f"\nEncountered {len(results['errors'])} errors:")
            for error in results["errors"][:5]:  # Show only the first 5 errors
                print(f"- {error}")
            if len(results["errors"]) > 5:
                print(f"  (and {len(results['errors']) - 5} more)")
    
    # Print recommendations
    print("\nRecommendations:")
    for rec in plan["recommendations"]["general"]:
        print(f"- {rec}")
    
    for rec in plan["recommendations"]["specific"]:
        print(f"- {rec}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())