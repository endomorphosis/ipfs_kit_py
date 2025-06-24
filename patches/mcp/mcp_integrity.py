"""
Data Integrity Manager for MCP Server

This module provides data integrity verification for MCP storage backends,
ensuring that content is stored and retrieved correctly across all backends.
"""

import os
import time
import json
import hashlib
import logging
import sqlite3
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logger = logging.getLogger(__name__)

class DataIntegrityManager:
    """
    Manager for verifying data integrity across storage backends.

    This class provides functionality to:
    - Calculate and verify content hashes
    - Track content across storage backends
    - Verify content integrity periodically
    - Detect and report integrity issues
    - Recommend repair actions
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        max_workers: int = 4,
        verification_interval: int = 86400,  # 24 hours
        enable_background_verification: bool = True
    ):
        """
        Initialize the data integrity manager.

        Args:
            db_path: Path to SQLite database for tracking integrity information
            max_workers: Maximum number of worker threads for verification
            verification_interval: Interval between automatic verifications (seconds)
            enable_background_verification: Whether to enable automatic verification
        """
        # Set up database path
        if db_path is None:
            home_dir = os.path.expanduser("~")
            ipfs_kit_dir = os.path.join(home_dir, ".ipfs_kit", "integrity")
            os.makedirs(ipfs_kit_dir, exist_ok=True)
            self.db_path = os.path.join(ipfs_kit_dir, "integrity.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize configuration
        self.max_workers = max_workers
        self.verification_interval = verification_interval
        self.enable_background_verification = enable_background_verification

        # Initialize database
        self._init_database()

        # Set up thread pool for verification tasks
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # Background verification thread
        self.verification_thread = None
        self.shutdown_event = threading.Event()

        # Start background verification if enabled
        if self.enable_background_verification:
            self.start_background_verification()

    def _init_database(self) -> None:
        """Initialize the SQLite database for tracking integrity information."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create content tracking table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_integrity (
                cid TEXT PRIMARY KEY,
                original_hash TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at REAL NOT NULL,
                last_verified_at REAL,
                last_verification_success INTEGER,
                verification_count INTEGER DEFAULT 0,
                repair_count INTEGER DEFAULT 0,
                last_repair_at REAL
            )
            ''')

            # Create backend tracking table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS backend_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid TEXT NOT NULL,
                backend_name TEXT NOT NULL,
                backend_reference TEXT NOT NULL,
                stored_at REAL NOT NULL,
                last_verified_at REAL,
                last_verification_success INTEGER,
                repair_count INTEGER DEFAULT 0,
                last_repair_at REAL,
                UNIQUE(cid, backend_name),
                FOREIGN KEY(cid) REFERENCES content_integrity(cid) ON DELETE CASCADE
            )
            ''')

            # Create verification log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid TEXT NOT NULL,
                backend_name TEXT,
                verified_at REAL NOT NULL,
                success INTEGER NOT NULL,
                error_message TEXT,
                hash_mismatch INTEGER DEFAULT 0,
                size_mismatch INTEGER DEFAULT 0,
                repair_attempted INTEGER DEFAULT 0,
                repair_success INTEGER DEFAULT 0,
                FOREIGN KEY(cid) REFERENCES content_integrity(cid) ON DELETE CASCADE
            )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_last_verified ON content_integrity(last_verified_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backend_content_cid ON backend_content(cid)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backend_content_backend ON backend_content(backend_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_verification_log_cid ON verification_log(cid)')

            conn.commit()
            conn.close()
            logger.info(f"Initialized integrity database at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing integrity database: {e}")
            raise

    def start_background_verification(self) -> None:
        """Start background verification thread."""
        if self.verification_thread is not None and self.verification_thread.is_alive():
            logger.warning("Background verification already running")
            return

        self.shutdown_event.clear()
        self.verification_thread = threading.Thread(
            target=self._background_verification_loop,
            daemon=True
        )
        self.verification_thread.start()
        logger.info("Started background verification thread")

    def stop_background_verification(self) -> None:
        """Stop background verification thread."""
        if self.verification_thread is None or not self.verification_thread.is_alive():
            logger.warning("Background verification not running")
            return

        self.shutdown_event.set()
        self.verification_thread.join(timeout=5.0)
        if self.verification_thread.is_alive():
            logger.warning("Background verification thread did not terminate gracefully")
        else:
            logger.info("Stopped background verification thread")

    def _background_verification_loop(self) -> None:
        """Background thread for periodic verification."""
        while not self.shutdown_event.is_set():
            try:
                # Get content that needs verification
                content_list = self.get_content_needing_verification()

                if content_list:
                    logger.info(f"Background verification starting for {len(content_list)} items")
                    for cid in content_list:
                        if self.shutdown_event.is_set():
                            break
                        try:
                            self.verify_content_integrity(cid)
                        except Exception as e:
                            logger.error(f"Error verifying content {cid}: {e}")
                    logger.info(f"Background verification completed for {len(content_list)} items")

                # Sleep until next verification interval
                for _ in range(min(self.verification_interval, 3600)):
                    if self.shutdown_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error in background verification loop: {e}")
                # Sleep to avoid rapid retries on persistent errors
                time.sleep(60)

    def get_content_needing_verification(
        self,
        max_items: int = 100,
        max_age_hours: Optional[int] = None
    ) -> List[str]:
        """
        Get list of content IDs that need verification.

        Args:
            max_items: Maximum number of items to return
            max_age_hours: Maximum age of content to verify (hours)

        Returns:
            List of content IDs
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = '''
            SELECT cid FROM content_integrity
            WHERE (last_verified_at IS NULL) OR
                  (last_verified_at < ?)
            ORDER BY last_verified_at ASC NULLS FIRST
            LIMIT ?
            '''

            # Calculate cutoff time
            now = time.time()
            if max_age_hours is not None:
                cutoff_time = now - (max_age_hours * 3600)
            else:
                cutoff_time = now - self.verification_interval

            cursor.execute(query, (cutoff_time, max_items))
            result = [row[0] for row in cursor.fetchall()]

            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting content for verification: {e}")
            return []

    def register_content(
        self,
        cid: str,
        content_data: bytes,
        backend_name: Optional[str] = None,
        backend_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register content for integrity tracking.

        Args:
            cid: Content ID
            content_data: Content data for hash calculation
            backend_name: Optional backend name
            backend_reference: Optional backend reference

        Returns:
            Result dictionary
        """
        try:
            # Calculate hash and size
            content_hash = self._calculate_content_hash(content_data)
            content_size = len(content_data)

            # Register in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if content already exists
            cursor.execute('SELECT cid FROM content_integrity WHERE cid = ?', (cid,))
            existing = cursor.fetchone()

            now = time.time()

            if not existing:
                # Insert new content record
                cursor.execute('''
                INSERT INTO content_integrity (
                    cid, original_hash, size, created_at, last_verified_at,
                    last_verification_success, verification_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cid, content_hash, content_size, now, now, 1, 1
                ))
            else:
                # Update existing record
                cursor.execute('''
                UPDATE content_integrity SET
                    last_verified_at = ?,
                    last_verification_success = ?,
                    verification_count = verification_count + 1
                WHERE cid = ?
                ''', (
                    now, 1, cid
                ))

            # Register backend if provided
            if backend_name and backend_reference:
                # Check if backend record exists
                cursor.execute(
                    'SELECT id FROM backend_content WHERE cid = ? AND backend_name = ?',
                    (cid, backend_name)
                )
                existing_backend = cursor.fetchone()

                if not existing_backend:
                    # Insert new backend record
                    cursor.execute('''
                    INSERT INTO backend_content (
                        cid, backend_name, backend_reference, stored_at,
                        last_verified_at, last_verification_success
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        cid, backend_name, backend_reference, now, now, 1
                    ))
                else:
                    # Update existing backend record
                    cursor.execute('''
                    UPDATE backend_content SET
                        backend_reference = ?,
                        last_verified_at = ?,
                        last_verification_success = ?
                    WHERE cid = ? AND backend_name = ?
                    ''', (
                        backend_reference, now, 1, cid, backend_name
                    ))

            conn.commit()
            conn.close()

            return {
                "success": True,
                "cid": cid,
                "hash": content_hash,
                "size": content_size,
                "registered_at": now,
                "backend_name": backend_name,
                "backend_reference": backend_reference
            }
        except Exception as e:
            logger.error(f"Error registering content for integrity tracking: {e}")
            return {
                "success": False,
                "cid": cid,
                "error": str(e)
            }

    def verify_content_integrity(
        self,
        cid: str,
        content_data: Optional[bytes] = None,
        repair: bool = False
    ) -> Dict[str, Any]:
        """
        Verify content integrity.

        Args:
            cid: Content ID
            content_data: Optional content data (if not provided, will fetch from IPFS)
            repair: Whether to attempt repair if verification fails

        Returns:
            Verification result
        """
        try:
            # Get content record
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cid, original_hash, size, created_at FROM content_integrity
            WHERE cid = ?
            ''', (cid,))

            content_record = cursor.fetchone()

            if not content_record:
                conn.close()
                return {
                    "success": False,
                    "cid": cid,
                    "error": "Content not registered for integrity tracking"
                }

            original_hash = content_record['original_hash']
            original_size = content_record['size']

            # Get or fetch content data
            if content_data is None:
                content_data = self._fetch_content_from_ipfs(cid)
                if content_data is None:
                    # Log verification failure
                    now = time.time()
                    cursor.execute('''
                    INSERT INTO verification_log (
                        cid, verified_at, success, error_message
                    ) VALUES (?, ?, ?, ?)
                    ''', (
                        cid, now, 0, "Failed to fetch content from IPFS"
                    ))

                    # Update content record
                    cursor.execute('''
                    UPDATE content_integrity SET
                        last_verified_at = ?,
                        last_verification_success = ?
                    WHERE cid = ?
                    ''', (
                        now, 0, cid
                    ))

                    conn.commit()
                    conn.close()

                    return {
                        "success": False,
                        "cid": cid,
                        "error": "Failed to fetch content from IPFS"
                    }

            # Calculate current hash and size
            current_hash = self._calculate_content_hash(content_data)
            current_size = len(content_data)

            # Check integrity
            hash_match = original_hash == current_hash
            size_match = original_size == current_size

            now = time.time()
            verification_success = hash_match and size_match

            if verification_success:
                # Log successful verification
                cursor.execute('''
                INSERT INTO verification_log (
                    cid, verified_at, success
                ) VALUES (?, ?, ?)
                ''', (
                    cid, now, 1
                ))

                # Update content record
                cursor.execute('''
                UPDATE content_integrity SET
                    last_verified_at = ?,
                    last_verification_success = ?,
                    verification_count = verification_count + 1
                WHERE cid = ?
                ''', (
                    now, 1, cid
                ))

                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "cid": cid,
                    "integrity_verified": True,
                    "hash_match": True,
                    "size_match": True,
                    "verified_at": now
                }
            else:
                # Log verification failure
                cursor.execute('''
                INSERT INTO verification_log (
                    cid, verified_at, success, error_message,
                    hash_mismatch, size_mismatch
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    cid, now, 0,
                    "Content integrity verification failed",
                    0 if hash_match else 1,
                    0 if size_match else 1
                ))

                # Update content record
                cursor.execute('''
                UPDATE content_integrity SET
                    last_verified_at = ?,
                    last_verification_success = ?,
                    verification_count = verification_count + 1
                WHERE cid = ?
                ''', (
                    now, 0, cid
                ))

                conn.commit()

                failure_details = {
                    "success": False,
                    "cid": cid,
                    "integrity_verified": False,
                    "hash_match": hash_match,
                    "size_match": size_match,
                    "original_hash": original_hash,
                    "current_hash": current_hash,
                    "original_size": original_size,
                    "current_size": current_size,
                    "verified_at": now
                }

                # Attempt repair if requested
                if repair:
                    repair_result = self._repair_content(cid, content_data, cursor)
                    failure_details["repair_attempted"] = True
                    failure_details["repair_result"] = repair_result

                    if repair_result.get("success", False):
                        # Update repair counts
                        cursor.execute('''
                        UPDATE content_integrity SET
                            repair_count = repair_count + 1,
                            last_repair_at = ?
                        WHERE cid = ?
                        ''', (
                            now, cid
                        ))

                        # Update verification log
                        log_id = cursor.lastrowid
                        cursor.execute('''
                        UPDATE verification_log SET
                            repair_attempted = 1,
                            repair_success = 1
                        WHERE id = ?
                        ''', (log_id,))

                        conn.commit()
                else:
                    failure_details["repair_attempted"] = False

                conn.close()
                return failure_details
        except Exception as e:
            logger.error(f"Error verifying content integrity: {e}")
            return {
                "success": False,
                "cid": cid,
                "error": str(e)
            }

    def _fetch_content_from_ipfs(self, cid: str) -> Optional[bytes]:
        """
        Fetch content from IPFS.

        Args:
            cid: Content ID

        Returns:
            Content data or None if fetch fails
        """
        try:
            process = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True,
                timeout=60
            )

            if process.returncode != 0:
                logger.error(f"Error fetching content from IPFS: {process.stderr.decode()}")
                return None

            return process.stdout
        except Exception as e:
            logger.error(f"Error fetching content from IPFS: {e}")
            return None

    def _calculate_content_hash(self, content_data: bytes) -> str:
        """
        Calculate secure hash of content data.

        Args:
            content_data: Content data

        Returns:
            Content hash string
        """
        return hashlib.blake2b(content_data).hexdigest()

    def _repair_content(
        self,
        cid: str,
        original_content: bytes,
        cursor: sqlite3.Cursor
    ) -> Dict[str, Any]:
        """
        Attempt to repair corrupted content.

        Args:
            cid: Content ID
            original_content: Original content data
            cursor: Database cursor

        Returns:
            Repair result
        """
        try:
            # Re-add content to IPFS
            with subprocess.Popen(
                ["ipfs", "add", "-q"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ) as process:
                stdout, stderr = process.communicate(input=original_content, timeout=60)

                if process.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to repair content: {stderr.decode()}"
                    }

                repaired_cid = stdout.decode().strip()

                # Verify CID matches
                if repaired_cid != cid:
                    logger.warning(f"Repaired CID {repaired_cid} does not match original {cid}")
                    return {
                        "success": False,
                        "error": "Repaired CID does not match original"
                    }

                # Verify content was repaired
                verification = self.verify_content_integrity(cid, content_data=original_content)

                if verification.get("integrity_verified", False):
                    return {
                        "success": True,
                        "cid": cid,
                        "repaired": True
                    }
                else:
                    return {
                        "success": False,
                        "error": "Repair failed to restore content integrity"
                    }
        except Exception as e:
            logger.error(f"Error repairing content: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def register_backend_storage(
        self,
        cid: str,
        backend_name: str,
        backend_reference: str
    ) -> Dict[str, Any]:
        """
        Register content storage in a backend.

        Args:
            cid: Content ID
            backend_name: Backend name
            backend_reference: Backend reference (e.g., storage ID)

        Returns:
            Registration result
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if content exists
            cursor.execute('SELECT cid FROM content_integrity WHERE cid = ?', (cid,))
            content_exists = cursor.fetchone()

            if not content_exists:
                # Fetch content from IPFS to register
                content_data = self._fetch_content_from_ipfs(cid)
                if content_data is None:
                    conn.close()
                    return {
                        "success": False,
                        "cid": cid,
                        "error": "Content not found in IPFS and not registered"
                    }

                # Register content
                self.register_content(cid, content_data)

            # Check if backend record exists
            cursor.execute(
                'SELECT id FROM backend_content WHERE cid = ? AND backend_name = ?',
                (cid, backend_name)
            )
            existing_backend = cursor.fetchone()

            now = time.time()

            if not existing_backend:
                # Insert new backend record
                cursor.execute('''
                INSERT INTO backend_content (
                    cid, backend_name, backend_reference, stored_at,
                    last_verified_at, last_verification_success
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    cid, backend_name, backend_reference, now, now, 1
                ))
            else:
                # Update existing backend record
                cursor.execute('''
                UPDATE backend_content SET
                    backend_reference = ?,
                    last_verified_at = ?,
                    last_verification_success = ?
                WHERE cid = ? AND backend_name = ?
                ''', (
                    backend_reference, now, 1, cid, backend_name
                ))

            conn.commit()
            conn.close()

            return {
                "success": True,
                "cid": cid,
                "backend_name": backend_name,
                "backend_reference": backend_reference,
                "registered_at": now
            }
        except Exception as e:
            logger.error(f"Error registering backend storage: {e}")
            return {
                "success": False,
                "cid": cid,
                "backend_name": backend_name,
                "error": str(e)
            }

    def get_content_info(self, cid: str) -> Dict[str, Any]:
        """
        Get comprehensive information about tracked content.

        Args:
            cid: Content ID

        Returns:
            Content information
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get content record
            cursor.execute('''
            SELECT * FROM content_integrity
            WHERE cid = ?
            ''', (cid,))

            content_record = cursor.fetchone()

            if not content_record:
                conn.close()
                return {
                    "success": False,
                    "cid": cid,
                    "error": "Content not registered for integrity tracking"
                }

            # Convert to dict
            content_info = dict(content_record)

            # Get backend records
            cursor.execute('''
            SELECT backend_name, backend_reference, stored_at, last_verified_at,
                   last_verification_success, repair_count, last_repair_at
            FROM backend_content
            WHERE cid = ?
            ''', (cid,))

            backends = [dict(row) for row in cursor.fetchall()]

            # Get recent verification logs
            cursor.execute('''
            SELECT verified_at, success, error_message, hash_mismatch, size_mismatch,
                   repair_attempted, repair_success
            FROM verification_log
            WHERE cid = ?
            ORDER BY verified_at DESC
            LIMIT 10
            ''', (cid,))

            verification_logs = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return {
                "success": True,
                "content": content_info,
                "backends": backends,
                "verification_logs": verification_logs
            }
        except Exception as e:
            logger.error(f"Error getting content info: {e}")
            return {
                "success": False,
                "cid": cid,
                "error": str(e)
            }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about tracked content.

        Returns:
            Statistics dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get total content count
            cursor.execute('SELECT COUNT(*) FROM content_integrity')
            total_content = cursor.fetchone()[0]

            # Get verified content count
            cursor.execute('''
            SELECT COUNT(*) FROM content_integrity
            WHERE last_verification_success = 1
            ''')
            verified_content = cursor.fetchone()[0]

            # Get content with issues
            cursor.execute('''
            SELECT COUNT(*) FROM content_integrity
            WHERE last_verification_success = 0
            ''')
            content_with_issues = cursor.fetchone()[0]

            # Get total verification count
            cursor.execute('SELECT SUM(verification_count) FROM content_integrity')
            total_verifications = cursor.fetchone()[0] or 0

            # Get total repair count
            cursor.execute('SELECT SUM(repair_count) FROM content_integrity')
            total_repairs = cursor.fetchone()[0] or 0

            # Get backend statistics
            cursor.execute('''
            SELECT backend_name, COUNT(*) as count
            FROM backend_content
            GROUP BY backend_name
            ''')

            backend_stats = {}
            for row in cursor.fetchall():
                backend_name, count = row
                backend_stats[backend_name] = count

            conn.close()

            return {
                "success": True,
                "total_content": total_content,
                "verified_content": verified_content,
                "content_with_issues": content_with_issues,
                "integrity_percentage": (verified_content / total_content * 100) if total_content > 0 else 100,
                "total_verifications": total_verifications,
                "total_repairs": total_repairs,
                "backend_stats": backend_stats,
                "database_path": self.db_path
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def shutdown(self) -> None:
        """Clean up resources and shut down background tasks."""
        # Stop background verification
        self.stop_background_verification()

        # Shut down thread pool
        self.executor.shutdown(wait=True)
        logger.info("Data integrity manager shutdown complete")
