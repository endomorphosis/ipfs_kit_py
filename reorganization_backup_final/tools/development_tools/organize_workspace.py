#!/usr/bin/env python3
"""
Workspace Organization Script for IPFS Kit

This script analyzes the files in the workspace and classifies them as:
1. Keep - Files that are part of the final solution
2. Archive - Files that are useful for reference but not part of the final solution
3. Delete - Files that can be safely deleted

It then helps the user organize the workspace according to this classification.
"""

import os
import re
import sys
import json
import logging
import argparse
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("workspace-organizer")

# Define constants
ARCHIVE_DIR = "mcp_archive"
KEY_FILES = {
    "final_mcp_server.py": "Final MCP server implementation",
    "unified_ipfs_tools.py": "Unified IPFS tools registration",
    "run_final_solution.sh": "Script to run the final solution",
    "test_ipfs_mcp_tools.py": "Comprehensive test suite for IPFS MCP tools",
    "organize_workspace.py": "This script for workspace organization",
    "README.md": "Project documentation",
}

class FileClassifier:
    """Classify files in the workspace"""
    
    def __init__(self, workspace_dir: str):
        """Initialize the classifier"""
        self.workspace_dir = workspace_dir
        self.keep_files = set()
        self.archive_files = set()
        self.delete_files = set()
        self.file_stats = {}
        
    def classify_files(self) -> Dict[str, Set[str]]:
        """Classify all files in the workspace"""
        logger.info(f"Analyzing files in {self.workspace_dir}...")
        
        # Collect file stats
        self._collect_file_stats()
        
        # Classify each file
        for file_path in self.file_stats.keys():
            if os.path.basename(file_path) in KEY_FILES:
                self.keep_files.add(file_path)
            elif self._is_important_file(file_path):
                self.keep_files.add(file_path)
            elif self._is_reference_file(file_path):
                self.archive_files.add(file_path)
            else:
                self.delete_files.add(file_path)
        
        # Always keep previously created test files
        test_file_pattern = re.compile(r'^test_.+\.py$')
        for file_path in self.file_stats.keys():
            if test_file_pattern.match(os.path.basename(file_path)):
                self.keep_files.add(file_path)
                if file_path in self.archive_files:
                    self.archive_files.remove(file_path)
                if file_path in self.delete_files:
                    self.delete_files.remove(file_path)
        
        # Return the classification
        return {
            "keep": self.keep_files,
            "archive": self.archive_files,
            "delete": self.delete_files
        }
    
    def _collect_file_stats(self):
        """Collect statistics for all files in the workspace"""
        for root, dirs, files in os.walk(self.workspace_dir):
            # Skip the archive directory and hidden directories
            if ARCHIVE_DIR in root or any(part.startswith('.') for part in root.split(os.sep)):
                continue
                
            for filename in files:
                # Skip hidden files
                if filename.startswith('.'):
                    continue
                
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, self.workspace_dir)
                
                try:
                    stat = os.stat(file_path)
                    self.file_stats[rel_path] = {
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "extension": os.path.splitext(filename)[1].lower(),
                        "is_backup": self._is_backup_file(filename),
                        "is_log": self._is_log_file(filename),
                        "is_test": self._is_test_file(filename),
                    }
                except Exception as e:
                    logger.warning(f"Error collecting stats for {rel_path}: {e}")
    
    def _is_important_file(self, file_path: str) -> bool:
        """Check if a file is important and should be kept"""
        filename = os.path.basename(file_path)
        
        # Key implementation files
        if filename.startswith('final_') and filename.endswith('.py'):
            return True
        
        # Python source files that are actively maintained
        if (filename.endswith('.py') 
            and not self._is_backup_file(filename) 
            and self._is_recently_modified(file_path)):
            with open(os.path.join(self.workspace_dir, file_path), 'r', encoding='utf-8', errors='ignore') as f:
                try:
                    content = f.read(4096)  # Read the first 4KB
                    # Check if this is an active implementation file
                    if ('register_ipfs_tools' in content 
                        or 'register_fs_journal_tools' in content
                        or 'register_vfs_tools' in content):
                        return True
                except Exception:
                    pass
        
        # Important non-Python files
        important_extensions = ['.md', '.json', '.sh']
        if os.path.splitext(filename)[1] in important_extensions:
            if not self._is_backup_file(filename) and not self._is_log_file(filename):
                return True
        
        return False
    
    def _is_reference_file(self, file_path: str) -> bool:
        """Check if a file should be archived for reference"""
        filename = os.path.basename(file_path)
        
        # Backup files should be archived
        if self._is_backup_file(filename):
            return True
        
        # Old server implementations should be archived
        if filename.endswith('_server.py') and not filename.startswith('final_'):
            return True
        
        # Older test files should be archived
        if self._is_test_file(filename) and not filename == 'test_ipfs_mcp_tools.py':
            return True
        
        # Logs should be archived
        if self._is_log_file(filename):
            return True
        
        # Older tools implementations
        older_tools_pattern = re.compile(r'(ipfs|mfs|vfs|fs)_tools[^/]*\.py$')
        if older_tools_pattern.search(filename) and not filename == 'unified_ipfs_tools.py':
            return True
        
        return False
    
    def _is_backup_file(self, filename: str) -> bool:
        """Check if a file is a backup file"""
        backup_patterns = [
            r'\.bak(\.\w+)?$',
            r'\.backup(_\d+)?$',
            r'\.\d{10}$',
            r'\.old$',
            r'\.prev$',
            r'_old$',
            r'_backup$',
            r'_bak$',
        ]
        
        return any(re.search(pattern, filename) for pattern in backup_patterns)
    
    def _is_log_file(self, filename: str) -> bool:
        """Check if a file is a log file"""
        return filename.endswith('.log') or '_log' in filename.lower()
    
    def _is_test_file(self, filename: str) -> bool:
        """Check if a file is a test file"""
        return filename.startswith('test_') and filename.endswith('.py')
    
    def _is_recently_modified(self, file_path: str) -> bool:
        """Check if a file was modified recently"""
        # Consider files modified in the last day as recent
        stats = self.file_stats.get(file_path, {})
        if not stats:
            return False
        
        # Last day (86400 seconds)
        file_time = stats.get('mtime', 0)
        current_time = datetime.now().timestamp()
        return (current_time - file_time) < 86400

class WorkspaceOrganizer:
    """Organize the workspace based on file classification"""
    
    def __init__(self, workspace_dir: str):
        """Initialize the organizer"""
        self.workspace_dir = workspace_dir
        self.classifier = FileClassifier(workspace_dir)
        self.classification = None
        
    def analyze(self) -> Dict[str, Set[str]]:
        """Analyze the workspace and classify files"""
        self.classification = self.classifier.classify_files()
        return self.classification
    
    def organize(self, mode: str = 'dry-run') -> bool:
        """Organize the workspace according to the classification"""
        if self.classification is None:
            self.analyze()
        
        if mode == 'dry-run':
            logger.info("Dry run mode - no changes will be made")
            self._display_summary()
            return True
            
        elif mode == 'archive':
            # Create archive directory if it doesn't exist
            archive_dir = os.path.join(self.workspace_dir, ARCHIVE_DIR)
            os.makedirs(archive_dir, exist_ok=True)
            
            # Archive files
            success = self._archive_files(archive_dir)
            if success:
                logger.info(f"Successfully archived files to {ARCHIVE_DIR}")
            else:
                logger.error("Failed to archive some files")
                
            return success
            
        elif mode == 'delete':
            # Delete files marked for deletion
            success = self._delete_files()
            if success:
                logger.info("Successfully deleted files")
            else:
                logger.error("Failed to delete some files")
                
            return success
        
        else:
            logger.error(f"Unknown mode: {mode}")
            return False
    
    def _display_summary(self):
        """Display a summary of the classification"""
        keep_count = len(self.classification["keep"])
        archive_count = len(self.classification["archive"])
        delete_count = len(self.classification["delete"])
        total_count = keep_count + archive_count + delete_count
        
        logger.info(f"Workspace Analysis Summary:")
        logger.info(f"  Total files: {total_count}")
        logger.info(f"  Files to keep: {keep_count} ({keep_count/total_count*100:.1f}%)")
        logger.info(f"  Files to archive: {archive_count} ({archive_count/total_count*100:.1f}%)")
        logger.info(f"  Files to delete: {delete_count} ({delete_count/total_count*100:.1f}%)")
        
        # Display key files
        logger.info("\nKey files to keep:")
        for file_path in sorted(self.classification["keep"]):
            if os.path.basename(file_path) in KEY_FILES:
                logger.info(f"  {file_path}: {KEY_FILES[os.path.basename(file_path)]}")
    
    def _archive_files(self, archive_dir: str) -> bool:
        """Archive files to the archive directory"""
        success = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for file_path in self.classification["archive"]:
            src = os.path.join(self.workspace_dir, file_path)
            
            # Create a timestamped name for the archived file
            basename = os.path.basename(file_path)
            archived_name = f"{os.path.splitext(basename)[0]}.{timestamp}{os.path.splitext(basename)[1]}"
            dst = os.path.join(archive_dir, archived_name)
            
            try:
                # Create parent directories if they don't exist
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                
                # Copy the file
                shutil.copy2(src, dst)
                logger.debug(f"Archived {file_path} to {dst}")
            except Exception as e:
                logger.error(f"Failed to archive {file_path}: {e}")
                success = False
        
        return success
    
    def _delete_files(self) -> bool:
        """Delete files marked for deletion"""
        success = True
        
        for file_path in self.classification["delete"]:
            path = os.path.join(self.workspace_dir, file_path)
            
            try:
                os.unlink(path)
                logger.debug(f"Deleted {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                success = False
        
        return success

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Organize the IPFS Kit workspace")
    parser.add_argument("--mode", choices=['dry-run', 'archive', 'delete'], 
                      default='dry-run',
                      help="Operation mode: dry-run (default), archive, delete")
    parser.add_argument("--workspace", default=".",
                      help="Workspace directory (default: current directory)")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger("workspace-organizer").setLevel(logging.DEBUG)
    
    # Get absolute path to workspace directory
    workspace_dir = os.path.abspath(args.workspace)
    
    # Create and run the organizer
    organizer = WorkspaceOrganizer(workspace_dir)
    organizer.analyze()
    success = organizer.organize(mode=args.mode)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())