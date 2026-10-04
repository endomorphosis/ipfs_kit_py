#!/usr/bin/env python3
"""
Patch Management Script

This script helps to:
1. Check if patches in the patches/ directory have been applied
2. Apply patches that haven't been applied yet
3. Move applied patches to applied_patches/ directory
4. Test the system after each patch is applied

Usage:
    python3 manage_patches.py
"""

import os
import sys
import re
import subprocess
import shutil
import tempfile
import hashlib
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

# Directory paths
PATCHES_DIR = 'patches'
APPLIED_PATCHES_DIR = 'applied_patches'
BACKUP_PATCHES_DIR = 'backup_patches'

# Key target directories/files to check for patches
TARGET_FILES = {
    'ipfs_model': 'ipfs_kit_py/mcp/models/ipfs_model.py',
    'libp2p_model': 'ipfs_kit_py/mcp/models/libp2p_model.py',
    'high_level_api': 'ipfs_kit_py/high_level_api.py',
    'mcp_api': 'ipfs_kit_py/mcp/api.py',
    'mcp_server': 'ipfs_kit_py/mcp/server.py',
    'mcp_daemons': 'ipfs_kit_py/mcp/daemon_control.py',
    'mcp_form_data': 'ipfs_kit_py/mcp/form_data_handler.py',
    'mcp_storage_backends': 'ipfs_kit_py/mcp/storage_backends.py',
    'mcp_simple': 'ipfs_kit_py/mcp/simple_server.py',
    'mcp_server_combined': 'ipfs_kit_py/mcp/combined_server.py',
    'mcp_command_handlers': 'ipfs_kit_py/mcp/command_handlers.py',
    'mcp_ipfs_controller': 'ipfs_kit_py/mcp/ipfs_controller.py',
    'lotus_kit': 'ipfs_kit_py/lotus_kit.py',
}

def run_command(cmd: List[str]) -> Tuple[bool, str, str]:
    """Run a shell command and return success, stdout, stderr."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return (result.returncode == 0, result.stdout, result.stderr)
    except Exception as e:
        return (False, "", str(e))

def get_file_hash(file_path: str) -> str:
    """Generate a hash of a file's content."""
    if not os.path.exists(file_path):
        return ""
    
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def extract_targets_from_patch(patch_path: str) -> List[str]:
    """Determine the target file(s) for a patch by examining its content."""
    targets = []
    
    # First check the filename for clues
    patch_filename = os.path.basename(patch_path)
    patch_name = os.path.splitext(patch_filename)[0].lower()
    
    # Check if the filename matches any known target patterns
    for key, path in TARGET_FILES.items():
        if key in patch_name:
            targets.append(path)
    
    # If we already found targets based on filename, return them
    if targets:
        return targets
        
    # Otherwise examine the content
    with open(patch_path, 'r') as f:
        content = f.read()
    
    # Look for common patterns in patch files to identify the target
    patterns = [
        r'MODEL_FILE\s*=\s*[\'"]([^\'"]+)[\'"]',  # Python variable declaration
        r'target_file\s*=\s*[\'"]([^\'"]+)[\'"]',  # Another common pattern
        r'# Target:\s*([^\n]+)',  # Comment style
        r'"""[^"]*Target:\s*([^"]*)',  # In docstring
        r'with open\([\'"]([^\'"]+)[\'"]',  # Open file statements
        r'shutil\.copy(?:2)?\([^,]+,\s*[\'"]([^\'"]+)[\'"]',  # Copy operations
        r'os\.path\.(?:exists|isfile)\([\'"]([^\'"]+)[\'"]',  # File checks
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            target = match.strip()
            if target and target not in targets:
                targets.append(target)
    
    # If still no targets, check for MCP module patterns
    if not targets and 'mcp' in patch_name:
        mcp_dir = 'ipfs_kit_py/mcp'
        if os.path.isdir(mcp_dir):
            # Try to find likely target files based on the patch name
            for component in patch_name.split('_'):
                if component in ['api', 'server', 'daemon', 'form', 'storage', 'command']:
                    for root, dirs, files in os.walk(mcp_dir):
                        for file in files:
                            if file.endswith('.py') and component in file.lower():
                                targets.append(os.path.join(root, file))

    return targets

def is_patch_applied_to_file(patch_path: str, target_path: str) -> bool:
    """Check if a patch has already been applied to a specific target file."""
    if not os.path.exists(target_path) or os.path.isdir(target_path):
        return False
    
    # Read the patch file to understand what it changes
    with open(patch_path, 'r') as f:
        patch_content = f.read()
    
    # Look for function definitions, key pieces of code, or other identifiers in the patch
    function_pattern = r'def\s+(\w+)'
    function_matches = re.findall(function_pattern, patch_content)
    
    with open(target_path, 'r') as f:
        target_content = f.read()
    
    # If there are function matches, check if they're in the target file
    if function_matches:
        for func_name in function_matches:
            # Skip very common function names like __init__
            if func_name in ['__init__', 'main']:
                continue
            
            # Create a pattern to match the function in the target file
            func_pattern = fr'def\s+{func_name}\s*\('
            if re.search(func_pattern, target_content):
                # Found a function match, now check if the implementation is similar
                # Extract the function body from the patch
                patch_func_body = extract_function_body(patch_content, func_name)
                if patch_func_body:
                    target_func_body = extract_function_body(target_content, func_name)
                    if target_func_body:
                        # Compare the functions, ignoring whitespace
                        similarity = compare_function_bodies(patch_func_body, target_func_body)
                        if similarity > 0.7:  # 70% similarity threshold
                            print(f"Function {func_name} from patch appears to be applied ({similarity:.2f} similarity)")
                            return True
    
    # Fallback: check for unique code snippets that would only be present after patching
    unique_lines = extract_unique_lines(patch_content)
    for line in unique_lines:
        cleaned_line = re.sub(r'\s+', '', line)
        if cleaned_line and len(cleaned_line) > 30:  # Only consider substantial lines
            cleaned_target = re.sub(r'\s+', '', target_content)
            if cleaned_line in cleaned_target:
                return True
    
    # If we can't determine with confidence, assume it's not applied
    return False

def is_patch_applied(patch_path: str) -> bool:
    """Check if a patch has already been applied to any of its target files."""
    targets = extract_targets_from_patch(patch_path)
    
    if not targets:
        print(f"WARNING: Could not determine targets for patch: {patch_path}")
        # Check if this patch exists in the applied_patches directory
        patch_basename = os.path.basename(patch_path)
        if os.path.exists(os.path.join(APPLIED_PATCHES_DIR, patch_basename)):
            print(f"Found in applied_patches directory, assuming it has been applied.")
            return True
        return False
    
    # Check each target
    for target in targets:
        if os.path.exists(target):
            if os.path.isdir(target):
                # For directory targets, check if we've created backup files 
                # that would indicate the patch was applied
                backup_pattern = f"{target}/*.bak.*"
                backup_found = False
                for root, dirs, files in os.walk(target):
                    for file in files:
                        if file.endswith(".bak") or ".bak." in file:
                            backup_found = True
                            break
                
                if backup_found:
                    print(f"Found backup files in {target}, suggesting patch may have been applied.")
                    return True
            else:
                # For file targets, check the content
                if is_patch_applied_to_file(patch_path, target):
                    return True
    
    return False

def extract_function_body(content: str, func_name: str) -> str:
    """Extract the body of a function from content."""
    pattern = fr'def\s+{func_name}\s*\([^)]*\)[^:]*:(.*?)(?:\n\s*def|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

def compare_function_bodies(body1: str, body2: str) -> float:
    """Compare two function bodies and return a similarity score (0-1)."""
    # Normalize whitespace
    body1_norm = re.sub(r'\s+', ' ', body1).strip()
    body2_norm = re.sub(r'\s+', ' ', body2).strip()
    
    # Use difflib to get similarity
    return difflib.SequenceMatcher(None, body1_norm, body2_norm).ratio()

def extract_unique_lines(content: str) -> List[str]:
    """Extract lines from content that are likely to be unique identifiers."""
    lines = content.splitlines()
    unique_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip comments, empty lines, and common patterns
        if not line or line.startswith('#') or line.startswith('"""') or line.startswith('def '):
            continue
        
        # Look for lines with specific content that would be unique
        if ('=' in line and not line.strip().startswith('if ') and 
            not line.strip().startswith('for ') and not line.strip().startswith('while ')):
            unique_lines.append(line)
    
    return unique_lines

def apply_patch(patch_path: str) -> bool:
    """Apply a patch to the target file(s)."""
    print(f"Applying patch {patch_path}")
    
    # For Python-based patches, just execute the script
    if patch_path.endswith('.py'):
        success, stdout, stderr = run_command(['python3', patch_path])
        print(stdout)
        if stderr:
            print(f"Errors: {stderr}")
        
        if not success:
            print(f"Failed to apply patch: {patch_path}")
            return False
    else:
        # Traditional patch files
        targets = extract_targets_from_patch(patch_path)
        for target in targets:
            if os.path.exists(target) and not os.path.isdir(target):
                # Create a backup of the target file
                backup_path = f"{target}.bak.{int(os.path.getmtime(target))}"
                shutil.copy2(target, backup_path)
                print(f"Backup created at {backup_path}")
                
                success, stdout, stderr = run_command(['patch', target, patch_path])
                print(stdout)
                if stderr:
                    print(f"Errors: {stderr}")
                
                if not success:
                    print(f"Failed to apply patch to {target}")
                    # Restore from backup
                    shutil.copy2(backup_path, target)
                    return False
    
    return True

def test_patched_system() -> bool:
    """Run tests to verify the system still works after applying patches."""
    print("Running tests...")
    
    # Run a basic syntax check on key Python files
    for root, dirs, files in os.walk("ipfs_kit_py"):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                success, stdout, stderr = run_command(['python3', '-m', 'py_compile', file_path])
                if not success:
                    print(f"Syntax error in {file_path}:")
                    print(stderr)
                    return False
    
    # Run actual tests if available
    if os.path.exists("run_test_filecoin_model_anyio.py"):
        print("Running basic application test...")
        success, stdout, stderr = run_command(['python3', 'run_test_filecoin_model_anyio.py'])
        print(stdout)
        if stderr:
            print(f"Test errors: {stderr}")
        if not success:
            return False
    
    return True

def process_patches() -> None:
    """Process all patches in the patches directory."""
    patches = []
    
    # Collect all patches
    for root, dirs, files in os.walk(PATCHES_DIR):
        for file in files:
            if file.endswith(".py") or file.endswith(".patch"):
                patch_path = os.path.join(root, file)
                patches.append(patch_path)
    
    print(f"Found {len(patches)} patches to process")
    
    for patch_path in patches:
        print(f"\nProcessing patch: {patch_path}")
        
        # Check if the patch has already been applied
        is_applied = is_patch_applied(patch_path)
        
        if is_applied:
            print(f"Patch {patch_path} appears to be already applied")
            
            # Move the patch to applied_patches directory
            patch_basename = os.path.basename(patch_path)
            dest_path = os.path.join(APPLIED_PATCHES_DIR, patch_basename)
            
            # Check if the destination file already exists
            if os.path.exists(dest_path):
                print(f"File already exists in applied_patches: {patch_basename}")
                # Create a backup in backup_patches
                backup_path = os.path.join(BACKUP_PATCHES_DIR, patch_basename)
                print(f"Moving original to backup: {backup_path}")
                shutil.move(patch_path, backup_path)
            else:
                print(f"Moving to applied_patches: {dest_path}")
                shutil.move(patch_path, dest_path)
        else:
            print(f"Patch {patch_path} has not been applied yet")
            
            # Apply the patch
            if apply_patch(patch_path):
                print(f"Successfully applied patch: {patch_path}")
                
                # Test the system
                if test_patched_system():
                    print("Tests passed!")
                    
                    # Move the patch to applied_patches
                    patch_basename = os.path.basename(patch_path)
                    dest_path = os.path.join(APPLIED_PATCHES_DIR, patch_basename)
                    
                    if os.path.exists(dest_path):
                        print(f"File already exists in applied_patches: {patch_basename}")
                        # Create a backup in backup_patches
                        backup_path = os.path.join(BACKUP_PATCHES_DIR, patch_basename)
                        print(f"Moving original to backup: {backup_path}")
                        shutil.move(patch_path, backup_path)
                    else:
                        print(f"Moving to applied_patches: {dest_path}")
                        shutil.move(patch_path, dest_path)
                else:
                    print("Tests failed!")
                    # Restore from backups
                    revert_last_patch()
            else:
                print(f"Failed to apply patch: {patch_path}")

def revert_last_patch() -> None:
    """Revert the most recently applied patch by restoring from backups."""
    # Find the most recent .bak file
    latest_backup = None
    latest_time = 0
    
    for root, dirs, files in os.walk("ipfs_kit_py"):
        for file in files:
            if ".bak." in file:
                try:
                    backup_time = int(file.split(".bak.")[1])
                    if backup_time > latest_time:
                        latest_time = backup_time
                        latest_backup = os.path.join(root, file)
                except (ValueError, IndexError):
                    continue
    
    if latest_backup:
        target_file = latest_backup.rsplit(".bak.", 1)[0]
        print(f"Restoring {target_file} from {latest_backup}")
        shutil.copy2(latest_backup, target_file)
        return True
    
    print("No backup files found to revert.")
    return False

def main() -> None:
    """Main function."""
    # Create the necessary directories if they don't exist
    os.makedirs(APPLIED_PATCHES_DIR, exist_ok=True)
    os.makedirs(BACKUP_PATCHES_DIR, exist_ok=True)
    
    process_patches()
    
    print("\nPatch processing complete!")

if __name__ == "__main__":
    main()