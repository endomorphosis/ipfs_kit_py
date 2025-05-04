#!/usr/bin/env python3
"""
Filesystem Journal Tools

This module provides filesystem journaling functionality for tracking changes to files
and directories. It maintains a journal of operations (create, modify, delete, etc.)
and can sync with the filesystem to identify changes.
"""

import os
import sys
import json
import time
import logging
import hashlib
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DB_PATH = os.path.expanduser("~/.ipfs_fs_journal.db")

def _initialize_db():
    """Initialize the journal database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            recursive BOOLEAN,
            added_at TIMESTAMP,
            notes TEXT,
            last_sync TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            operation TEXT,
            timestamp TIMESTAMP,
            details TEXT,
            checksum TEXT,
            size INTEGER,
            ipfs_cid TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_state (
            path TEXT PRIMARY KEY,
            exists BOOLEAN,
            is_dir BOOLEAN,
            size INTEGER,
            last_modified TIMESTAMP,
            checksum TEXT,
            last_operation TEXT,
            last_operation_time TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error initializing journal database: {e}")
        return False

def _get_file_checksum(path: str) -> Optional[str]:
    """Calculate the MD5 checksum of a file"""
    try:
        if not os.path.isfile(path):
            return None
            
        hash_md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating checksum for {path}: {e}")
        return None

def _add_journal_entry(path: str, operation: str, details: str = "", 
                      checksum: Optional[str] = None, size: Optional[int] = None,
                      ipfs_cid: Optional[str] = None):
    """Add an entry to the journal"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.datetime.now().isoformat()
        
        cursor.execute('''
        INSERT INTO journal_entries 
        (path, operation, timestamp, details, checksum, size, ipfs_cid)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (path, operation, timestamp, details, checksum, size, ipfs_cid))
        
        # Update file state
        if operation != "DELETE":
            exists = os.path.exists(path)
            is_dir = os.path.isdir(path) if exists else False
            size = os.path.getsize(path) if exists and not is_dir else None
            last_modified = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat() if exists else None
            
            cursor.execute('''
            INSERT OR REPLACE INTO file_state
            (path, exists, is_dir, size, last_modified, checksum, last_operation, last_operation_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (path, exists, is_dir, size, last_modified, checksum, operation, timestamp))
        else:
            # File was deleted
            cursor.execute('''
            UPDATE file_state
            SET exists = 0, last_operation = ?, last_operation_time = ?
            WHERE path = ?
            ''', (operation, timestamp, path))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding journal entry for {path}: {e}")
        return False

def register_tools(server) -> bool:
    """Register filesystem journal tools with the MCP server"""
    logger.info("Registering filesystem journal tools...")
    
    # Initialize the database
    if not _initialize_db():
        logger.error("Failed to initialize journal database")
        return False
    
    # Tool: Track a file or directory for changes
    async def fs_journal_track(path: str, recursive: bool = True, notes: str = ""):
        """Start tracking a file or directory for changes"""
        try:
            # Make sure the path exists
            if not os.path.exists(path):
                return {"success": False, "error": f"Path not found: {path}"}
            
            # Get absolute path
            abs_path = os.path.abspath(path)
            
            # Add to tracked paths
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            timestamp = datetime.datetime.now().isoformat()
            
            try:
                cursor.execute('''
                INSERT INTO tracked_paths (path, recursive, added_at, notes, last_sync)
                VALUES (?, ?, ?, ?, ?)
                ''', (abs_path, recursive, timestamp, notes, timestamp))
                conn.commit()
            except sqlite3.IntegrityError:
                # Already tracking this path, update instead
                cursor.execute('''
                UPDATE tracked_paths 
                SET recursive = ?, notes = ?, last_sync = ?
                WHERE path = ?
                ''', (recursive, notes, timestamp, abs_path))
                conn.commit()
                conn.close()
                return {
                    "success": True,
                    "path": abs_path,
                    "recursive": recursive,
                    "status": "updated",
                    "message": f"Updated tracking for {abs_path}"
                }
            
            # Initial scan to populate journal with current state
            files_tracked = 0
            dirs_tracked = 0
            
            if os.path.isdir(abs_path):
                # Track the directory itself
                _add_journal_entry(abs_path, "TRACK", "Directory tracking started", None, None)
                dirs_tracked += 1
                
                # Track contents if recursive
                if recursive:
                    for root, dirs, files in os.walk(abs_path):
                        for d in dirs:
                            dir_path = os.path.join(root, d)
                            _add_journal_entry(dir_path, "TRACK", "Directory tracking started", None, None)
                            dirs_tracked += 1
                        
                        for f in files:
                            file_path = os.path.join(root, f)
                            checksum = _get_file_checksum(file_path)
                            size = os.path.getsize(file_path)
                            _add_journal_entry(file_path, "TRACK", "File tracking started", checksum, size)
                            files_tracked += 1
            else:
                # Single file
                checksum = _get_file_checksum(abs_path)
                size = os.path.getsize(abs_path)
                _add_journal_entry(abs_path, "TRACK", "File tracking started", checksum, size)
                files_tracked += 1
            
            conn.close()
            
            return {
                "success": True,
                "path": abs_path,
                "recursive": recursive,
                "status": "added",
                "files_tracked": files_tracked,
                "directories_tracked": dirs_tracked,
                "total_tracked": files_tracked + dirs_tracked
            }
            
        except Exception as e:
            logger.error(f"Error tracking path {path}: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Stop tracking a file or directory
    async def fs_journal_untrack(path: str):
        """Stop tracking a file or directory for changes"""
        try:
            # Get absolute path
            abs_path = os.path.abspath(path)
            
            # Remove from tracked paths
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # First check if we're tracking this path
            cursor.execute("SELECT recursive FROM tracked_paths WHERE path = ?", (abs_path,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return {
                    "success": False,
                    "error": f"Path not being tracked: {abs_path}"
                }
            
            recursive = bool(result[0])
            
            # Remove from tracked paths
            cursor.execute("DELETE FROM tracked_paths WHERE path = ?", (abs_path,))
            conn.commit()
            
            # Add untrack journal entry
            _add_journal_entry(abs_path, "UNTRACK", "Tracking stopped", None, None)
            
            # Remove from file_state if desired
            if recursive and os.path.isdir(abs_path):
                cursor.execute("DELETE FROM file_state WHERE path LIKE ?", (abs_path + "/%",))
                
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "path": abs_path,
                "status": "untracked",
                "message": f"Stopped tracking {abs_path}"
            }
            
        except Exception as e:
            logger.error(f"Error untracking path {path}: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: List all tracked files and directories
    async def fs_journal_list_tracked():
        """List all files and directories being tracked"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT path, recursive, added_at, notes, last_sync 
            FROM tracked_paths
            ORDER BY added_at
            ''')
            
            rows = cursor.fetchall()
            
            tracked_paths = []
            for row in rows:
                # Get stats for this tracked path
                path = row['path']
                recursive = bool(row['recursive'])
                
                if recursive and os.path.isdir(path):
                    cursor.execute('''
                    SELECT COUNT(*) FROM file_state 
                    WHERE path LIKE ? AND exists = 1 AND is_dir = 0
                    ''', (path + "/%",))
                    file_count = cursor.fetchone()[0]
                    
                    cursor.execute('''
                    SELECT COUNT(*) FROM file_state 
                    WHERE path LIKE ? AND exists = 1 AND is_dir = 1
                    ''', (path + "/%",))
                    dir_count = cursor.fetchone()[0]
                else:
                    file_count = 1 if os.path.isfile(path) else 0
                    dir_count = 1 if os.path.isdir(path) else 0
                
                tracked_paths.append({
                    "path": path,
                    "recursive": recursive,
                    "added_at": row['added_at'],
                    "notes": row['notes'],
                    "last_sync": row['last_sync'],
                    "file_count": file_count,
                    "directory_count": dir_count
                })
            
            conn.close()
            
            return {
                "success": True,
                "tracked_paths": tracked_paths,
                "count": len(tracked_paths)
            }
            
        except Exception as e:
            logger.error(f"Error listing tracked paths: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Get history of operations for a path
    async def fs_journal_get_history(path: str, limit: int = 50, operation_filter: Optional[str] = None):
        """Get the history of operations for a specific path"""
        try:
            # Get absolute path
            abs_path = os.path.abspath(path)
            
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if operation_filter:
                cursor.execute('''
                SELECT * FROM journal_entries 
                WHERE path = ? AND operation = ?
                ORDER BY timestamp DESC LIMIT ?
                ''', (abs_path, operation_filter, limit))
            else:
                cursor.execute('''
                SELECT * FROM journal_entries 
                WHERE path = ?
                ORDER BY timestamp DESC LIMIT ?
                ''', (abs_path, limit))
            
            rows = cursor.fetchall()
            
            entries = []
            for row in rows:
                details = row['details']
                if details and details.startswith('{'):
                    try:
                        details = json.loads(details)
                    except:
                        pass
                
                entries.append({
                    "path": row['path'],
                    "operation": row['operation'],
                    "timestamp": row['timestamp'],
                    "details": details,
                    "checksum": row['checksum'],
                    "size": row['size'],
                    "ipfs_cid": row['ipfs_cid']
                })
            
            # Get current state
            cursor.execute("SELECT * FROM file_state WHERE path = ?", (abs_path,))
            state_row = cursor.fetchone()
            
            current_state = None
            if state_row:
                current_state = {
                    "exists": bool(state_row['exists']),
                    "is_dir": bool(state_row['is_dir']),
                    "size": state_row['size'],
                    "last_modified": state_row['last_modified'],
                    "checksum": state_row['checksum'],
                    "last_operation": state_row['last_operation'],
                    "last_operation_time": state_row['last_operation_time']
                }
            
            conn.close()
            
            return {
                "success": True,
                "path": abs_path,
                "entries": entries,
                "count": len(entries),
                "current_state": current_state
            }
            
        except Exception as e:
            logger.error(f"Error getting history for {path}: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Sync the journal with the filesystem
    async def fs_journal_sync(path: Optional[str] = None, report_only: bool = False):
        """Sync the journal with the current state of the filesystem"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get tracked paths
            if path:
                abs_path = os.path.abspath(path)
                cursor.execute("SELECT * FROM tracked_paths WHERE path = ?", (abs_path,))
            else:
                cursor.execute("SELECT * FROM tracked_paths")
            
            tracked_paths = cursor.fetchall()
            
            if not tracked_paths:
                conn.close()
                if path:
                    return {
                        "success": False,
                        "error": f"Path not being tracked: {path}"
                    }
                else:
                    return {
                        "success": True,
                        "message": "No paths being tracked",
                        "changes": []
                    }
            
            all_changes = []
            
            for tracked in tracked_paths:
                tracked_path = tracked['path']
                recursive = bool(tracked['recursive'])
                
                # Get current file state records
                if recursive and os.path.isdir(tracked_path):
                    cursor.execute('''
                    SELECT * FROM file_state 
                    WHERE path = ? OR path LIKE ?
                    ''', (tracked_path, tracked_path + "/%"))
                else:
                    cursor.execute("SELECT * FROM file_state WHERE path = ?", (tracked_path,))
                
                file_states = {row['path']: row for row in cursor.fetchall()}
                
                # Scan filesystem for current state
                paths_checked = set()
                
                if os.path.exists(tracked_path):
                    if os.path.isdir(tracked_path):
                        # Directory
                        paths_checked.add(tracked_path)
                        
                        if not tracked_path in file_states:
                            # New directory
                            change = {
                                "path": tracked_path,
                                "type": "directory",
                                "change": "created"
                            }
                            all_changes.append(change)
                            
                            if not report_only:
                                _add_journal_entry(tracked_path, "CREATE", "Directory created", None, None)
                        
                        if recursive:
                            # Walk the directory
                            for root, dirs, files in os.walk(tracked_path):
                                for d in dirs:
                                    dir_path = os.path.join(root, d)
                                    paths_checked.add(dir_path)
                                    
                                    if not dir_path in file_states:
                                        # New directory
                                        change = {
                                            "path": dir_path,
                                            "type": "directory",
                                            "change": "created"
                                        }
                                        all_changes.append(change)
                                        
                                        if not report_only:
                                            _add_journal_entry(dir_path, "CREATE", "Directory created", None, None)
                                
                                for f in files:
                                    file_path = os.path.join(root, f)
                                    paths_checked.add(file_path)
                                    
                                    checksum = _get_file_checksum(file_path)
                                    size = os.path.getsize(file_path)
                                    
                                    if not file_path in file_states:
                                        # New file
                                        change = {
                                            "path": file_path,
                                            "type": "file",
                                            "change": "created",
                                            "size": size,
                                            "checksum": checksum
                                        }
                                        all_changes.append(change)
                                        
                                        if not report_only:
                                            _add_journal_entry(file_path, "CREATE", "File created", checksum, size)
                                    else:
                                        # Existing file, check for changes
                                        state = file_states[file_path]
                                        if state['checksum'] != checksum:
                                            # File modified
                                            change = {
                                                "path": file_path,
                                                "type": "file",
                                                "change": "modified",
                                                "old_size": state['size'],
                                                "new_size": size,
                                                "old_checksum": state['checksum'],
                                                "new_checksum": checksum
                                            }
                                            all_changes.append(change)
                                            
                                            if not report_only:
                                                _add_journal_entry(file_path, "MODIFY", "File modified", checksum, size)
                    else:
                        # Single file
                        paths_checked.add(tracked_path)
                        
                        checksum = _get_file_checksum(tracked_path)
                        size = os.path.getsize(tracked_path)
                        
                        if not tracked_path in file_states:
                            # New file
                            change = {
                                "path": tracked_path,
                                "type": "file",
                                "change": "created",
                                "size": size,
                                "checksum": checksum
                            }
                            all_changes.append(change)
                            
                            if not report_only:
                                _add_journal_entry(tracked_path, "CREATE", "File created", checksum, size)
                        else:
                            # Existing file, check for changes
                            state = file_states[tracked_path]
                            if state['checksum'] != checksum:
                                # File modified
                                change = {
                                    "path": tracked_path,
                                    "type": "file",
                                    "change": "modified",
                                    "old_size": state['size'],
                                    "new_size": size,
                                    "old_checksum": state['checksum'],
                                    "new_checksum": checksum
                                }
                                all_changes.append(change)
                                
                                if not report_only:
                                    _add_journal_entry(tracked_path, "MODIFY", "File modified", checksum, size)
                
                # Check for deleted files
                for path, state in file_states.items():
                    if path not in paths_checked and bool(state['exists']):
                        # File or directory no longer exists
                        change = {
                            "path": path,
                            "type": "file" if not bool(state['is_dir']) else "directory",
                            "change": "deleted"
                        }
                        all_changes.append(change)
                        
                        if not report_only:
                            _add_journal_entry(path, "DELETE", "File or directory deleted", None, None)
                
                # Update last_sync
                if not report_only:
                    timestamp = datetime.datetime.now().isoformat()
                    cursor.execute('''
                    UPDATE tracked_paths SET last_sync = ? WHERE path = ?
                    ''', (timestamp, tracked_path))
            
            if not report_only:
                conn.commit()
            
            conn.close()
            
            return {
                "success": True,
                "paths_checked": len(tracked_paths),
                "changes": all_changes,
                "count": len(all_changes),
                "report_only": report_only
            }
            
        except Exception as e:
            logger.error(f"Error syncing journal: {e}")
            return {"success": False, "error": str(e)}
    
    # Register all tools with the MCP server
    try:
        server.register_tool("fs_journal_track", fs_journal_track)
        server.register_tool("fs_journal_untrack", fs_journal_untrack)
        server.register_tool("fs_journal_list_tracked", fs_journal_list_tracked)
        server.register_tool("fs_journal_get_history", fs_journal_get_history)
        server.register_tool("fs_journal_sync", fs_journal_sync)
        
        logger.info("✅ Filesystem journal tools registered successfully")
        return True
    except Exception as e:
        logger.error(f"Error registering filesystem journal tools: {e}")
        return False

if __name__ == "__main__":
    logger.info("This module should be imported, not run directly.")
    logger.info("To use these tools, import and register them with an MCP server.")
