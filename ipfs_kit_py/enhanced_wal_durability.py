#!/usr/bin/env python3
"""
Enhanced Write-Ahead Log with Durability Guarantees

Provides improved durability for WAL operations through:
- Fsync guarantees for critical operations
- Checkpointing for faster recovery
- Batch writes for performance
- Enhanced recovery mechanisms
"""

import os
import time
import json
import logging
import threading
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class WALCheckpoint:
    """Represents a WAL checkpoint for recovery."""
    checkpoint_id: str
    timestamp: float
    sequence_number: int
    operations_count: int
    file_path: str
    checksum: str


class DurableWAL:
    """
    Enhanced Write-Ahead Log with durability guarantees.
    
    Features:
    - Atomic writes with fsync
    - Batch operation support
    - Checkpointing for fast recovery
    - Integrity verification with checksums
    - Automatic corruption detection and recovery
    """
    
    def __init__(
        self,
        base_path: str,
        fsync_mode: str = "always",  # "always", "batch", "periodic"
        batch_size: int = 100,
        batch_timeout: float = 5.0,
        checkpoint_interval: int = 1000,
        max_segment_size: int = 100 * 1024 * 1024,  # 100MB
    ):
        """
        Initialize the durable WAL.
        
        Args:
            base_path: Base directory for WAL files
            fsync_mode: When to fsync - "always", "batch", or "periodic"
            batch_size: Number of operations to batch before write
            batch_timeout: Maximum time to wait for batch (seconds)
            checkpoint_interval: Operations between checkpoints
            max_segment_size: Maximum size for a single segment file
        """
        self.base_path = Path(base_path).expanduser()
        self.fsync_mode = fsync_mode
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.checkpoint_interval = checkpoint_interval
        self.max_segment_size = max_segment_size
        
        # Create directories
        self.segments_dir = self.base_path / "segments"
        self.checkpoints_dir = self.base_path / "checkpoints"
        self.segments_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        
        # WAL state
        self.current_segment = None
        self.current_segment_file = None
        self.sequence_number = 0
        self.operations_since_checkpoint = 0
        
        # Batch buffer
        self.batch_buffer: List[Dict[str, Any]] = []
        self.batch_lock = threading.RLock()
        self.last_batch_flush = time.time()
        
        # Checkpoints
        self.checkpoints: List[WALCheckpoint] = []
        self.checkpoint_lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'total_operations': 0,
            'total_batches': 0,
            'total_fsyncs': 0,
            'total_checkpoints': 0,
            'corruption_detections': 0,
            'recovery_operations': 0,
        }
        
        # Initialize WAL
        self._initialize_wal()
        
        # Start batch flush thread if using batch mode
        if self.fsync_mode == "batch":
            self._start_batch_flush_thread()
        
        logger.info(
            f"Initialized durable WAL at {base_path} "
            f"(fsync_mode={fsync_mode}, batch_size={batch_size})"
        )
    
    def _initialize_wal(self):
        """Initialize or recover existing WAL."""
        # Load existing checkpoints
        self._load_checkpoints()
        
        # Find latest segment or create new one
        existing_segments = sorted(self.segments_dir.glob("wal_*.log"))
        
        if existing_segments:
            # Recover from latest segment
            latest_segment = existing_segments[-1]
            self.sequence_number = self._recover_sequence_number(latest_segment)
            logger.info(f"Recovered WAL from {latest_segment} (seq={self.sequence_number})")
        
        # Open new segment for writing
        self._rotate_segment()
    
    def _load_checkpoints(self):
        """Load existing checkpoints."""
        with self.checkpoint_lock:
            checkpoint_files = sorted(self.checkpoints_dir.glob("checkpoint_*.json"))
            
            for checkpoint_file in checkpoint_files:
                try:
                    with open(checkpoint_file, 'r') as f:
                        data = json.load(f)
                        checkpoint = WALCheckpoint(**data)
                        self.checkpoints.append(checkpoint)
                except Exception as e:
                    logger.error(f"Failed to load checkpoint {checkpoint_file}: {e}")
            
            if self.checkpoints:
                logger.info(f"Loaded {len(self.checkpoints)} checkpoints")
    
    def _recover_sequence_number(self, segment_path: Path) -> int:
        """Recover the last sequence number from a segment."""
        try:
            with open(segment_path, 'r') as f:
                last_seq = 0
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        seq = entry.get('sequence_number', 0)
                        if seq > last_seq:
                            last_seq = seq
                    except json.JSONDecodeError:
                        continue
                return last_seq
        except Exception as e:
            logger.error(f"Failed to recover sequence number: {e}")
            return 0
    
    def _rotate_segment(self):
        """Rotate to a new segment file."""
        # Close current segment if open
        if self.current_segment_file:
            self._fsync_current_segment()
            self.current_segment_file.close()
        
        # Create new segment
        timestamp = int(time.time() * 1000)
        segment_name = f"wal_{timestamp}_{self.sequence_number:010d}.log"
        self.current_segment = self.segments_dir / segment_name
        self.current_segment_file = open(self.current_segment, 'a', buffering=1)
        
        logger.info(f"Rotated to new segment: {segment_name}")
    
    def append(self, operation: Dict[str, Any]) -> int:
        """
        Append an operation to the WAL.
        
        Args:
            operation: Operation dictionary to append
            
        Returns:
            Sequence number assigned to this operation
        """
        with self.batch_lock:
            # Assign sequence number
            self.sequence_number += 1
            seq_num = self.sequence_number
            
            # Add metadata
            operation_with_meta = {
                'sequence_number': seq_num,
                'timestamp': time.time(),
                'operation': operation,
            }
            
            # Add to batch buffer
            self.batch_buffer.append(operation_with_meta)
            self.stats['total_operations'] += 1
            
            # Flush based on mode
            if self.fsync_mode == "always":
                self._flush_batch()
            elif len(self.batch_buffer) >= self.batch_size:
                self._flush_batch()
            
            # Check for checkpoint
            self.operations_since_checkpoint += 1
            if self.operations_since_checkpoint >= self.checkpoint_interval:
                self._create_checkpoint()
            
            # Check for segment rotation
            if self.current_segment.stat().st_size >= self.max_segment_size:
                self._rotate_segment()
            
            return seq_num
    
    def append_batch(self, operations: List[Dict[str, Any]]) -> List[int]:
        """
        Append multiple operations as a batch.
        
        Args:
            operations: List of operations to append
            
        Returns:
            List of sequence numbers assigned
        """
        sequence_numbers = []
        
        with self.batch_lock:
            for operation in operations:
                self.sequence_number += 1
                seq_num = self.sequence_number
                sequence_numbers.append(seq_num)
                
                operation_with_meta = {
                    'sequence_number': seq_num,
                    'timestamp': time.time(),
                    'operation': operation,
                }
                
                self.batch_buffer.append(operation_with_meta)
                self.stats['total_operations'] += 1
            
            # Always flush after batch append
            self._flush_batch()
            
            # Check for checkpoint
            self.operations_since_checkpoint += len(operations)
            if self.operations_since_checkpoint >= self.checkpoint_interval:
                self._create_checkpoint()
        
        return sequence_numbers
    
    def _flush_batch(self):
        """Flush the batch buffer to disk."""
        if not self.batch_buffer:
            return
        
        try:
            # Write all operations in buffer
            for operation in self.batch_buffer:
                line = json.dumps(operation) + '\n'
                self.current_segment_file.write(line)
            
            # Fsync based on mode
            if self.fsync_mode in ("always", "batch"):
                self._fsync_current_segment()
            
            self.stats['total_batches'] += 1
            batch_size = len(self.batch_buffer)
            self.batch_buffer.clear()
            self.last_batch_flush = time.time()
            
            logger.debug(f"Flushed batch of {batch_size} operations")
            
        except Exception as e:
            logger.error(f"Failed to flush batch: {e}")
            raise
    
    def _fsync_current_segment(self):
        """Fsync the current segment file."""
        if self.current_segment_file:
            try:
                self.current_segment_file.flush()
                os.fsync(self.current_segment_file.fileno())
                self.stats['total_fsyncs'] += 1
            except Exception as e:
                logger.error(f"Failed to fsync segment: {e}")
                raise
    
    def _create_checkpoint(self):
        """Create a checkpoint for faster recovery."""
        with self.checkpoint_lock:
            # Flush any pending operations first
            self._flush_batch()
            self._fsync_current_segment()
            
            # Calculate checksum of current segment
            checksum = self._calculate_file_checksum(self.current_segment)
            
            # Create checkpoint metadata
            checkpoint = WALCheckpoint(
                checkpoint_id=hashlib.sha256(
                    f"{self.sequence_number}_{time.time()}".encode()
                ).hexdigest()[:16],
                timestamp=time.time(),
                sequence_number=self.sequence_number,
                operations_count=self.operations_since_checkpoint,
                file_path=str(self.current_segment),
                checksum=checksum,
            )
            
            # Save checkpoint
            checkpoint_file = (
                self.checkpoints_dir / 
                f"checkpoint_{checkpoint.timestamp:.0f}_{checkpoint.sequence_number:010d}.json"
            )
            
            with open(checkpoint_file, 'w') as f:
                json.dump(asdict(checkpoint), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            self.checkpoints.append(checkpoint)
            self.operations_since_checkpoint = 0
            self.stats['total_checkpoints'] += 1
            
            logger.info(
                f"Created checkpoint at sequence {checkpoint.sequence_number} "
                f"({checkpoint.operations_count} operations)"
            )
            
            # Clean up old checkpoints (keep last 10)
            self._cleanup_old_checkpoints()
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _cleanup_old_checkpoints(self, keep_count: int = 10):
        """Remove old checkpoint files, keeping only the most recent."""
        if len(self.checkpoints) <= keep_count:
            return
        
        # Sort by timestamp
        self.checkpoints.sort(key=lambda c: c.timestamp)
        
        # Remove old checkpoints
        to_remove = self.checkpoints[:-keep_count]
        for checkpoint in to_remove:
            try:
                checkpoint_file = (
                    self.checkpoints_dir / 
                    f"checkpoint_{checkpoint.timestamp:.0f}_{checkpoint.sequence_number:010d}.json"
                )
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
            except Exception as e:
                logger.error(f"Failed to remove old checkpoint: {e}")
        
        # Update checkpoint list
        self.checkpoints = self.checkpoints[-keep_count:]
    
    def _start_batch_flush_thread(self):
        """Start background thread for periodic batch flushing."""
        def flush_loop():
            while True:
                time.sleep(self.batch_timeout)
                
                with self.batch_lock:
                    if self.batch_buffer and \
                       time.time() - self.last_batch_flush >= self.batch_timeout:
                        try:
                            self._flush_batch()
                        except Exception as e:
                            logger.error(f"Error in batch flush thread: {e}")
        
        thread = threading.Thread(target=flush_loop, daemon=True)
        thread.start()
        logger.info("Started batch flush thread")
    
    def recover(self, from_checkpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Recover operations from WAL.
        
        Args:
            from_checkpoint: Optional checkpoint ID to recover from
            
        Returns:
            List of recovered operations
        """
        recovered_operations = []
        
        try:
            # Find checkpoint to start from
            start_sequence = 0
            if from_checkpoint:
                checkpoint = next(
                    (c for c in self.checkpoints if c.checkpoint_id == from_checkpoint),
                    None
                )
                if checkpoint:
                    start_sequence = checkpoint.sequence_number
                    logger.info(f"Starting recovery from checkpoint {from_checkpoint}")
            elif self.checkpoints:
                # Use latest checkpoint
                latest_checkpoint = max(self.checkpoints, key=lambda c: c.timestamp)
                start_sequence = latest_checkpoint.sequence_number
                logger.info(f"Starting recovery from latest checkpoint")
            
            # Read all segments
            segments = sorted(self.segments_dir.glob("wal_*.log"))
            
            for segment in segments:
                # Verify segment integrity if we have a checkpoint for it
                checkpoint = next(
                    (c for c in self.checkpoints if c.file_path == str(segment)),
                    None
                )
                
                if checkpoint:
                    checksum = self._calculate_file_checksum(segment)
                    if checksum != checkpoint.checksum:
                        logger.error(
                            f"Checksum mismatch for {segment} - "
                            f"possible corruption detected"
                        )
                        self.stats['corruption_detections'] += 1
                        continue
                
                # Read operations from segment
                with open(segment, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            seq_num = entry.get('sequence_number', 0)
                            
                            if seq_num > start_sequence:
                                recovered_operations.append(entry['operation'])
                                self.stats['recovery_operations'] += 1
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse WAL entry: {e}")
                            self.stats['corruption_detections'] += 1
                            continue
            
            logger.info(f"Recovered {len(recovered_operations)} operations from WAL")
            
        except Exception as e:
            logger.error(f"Error during WAL recovery: {e}")
            raise
        
        return recovered_operations
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WAL statistics."""
        return {
            **self.stats,
            'sequence_number': self.sequence_number,
            'batch_buffer_size': len(self.batch_buffer),
            'operations_since_checkpoint': self.operations_since_checkpoint,
            'checkpoint_count': len(self.checkpoints),
            'fsync_mode': self.fsync_mode,
        }
    
    def close(self):
        """Close the WAL and flush any pending operations."""
        with self.batch_lock:
            # Flush pending operations
            if self.batch_buffer:
                self._flush_batch()
            
            # Create final checkpoint
            if self.operations_since_checkpoint > 0:
                self._create_checkpoint()
            
            # Close segment file
            if self.current_segment_file:
                self._fsync_current_segment()
                self.current_segment_file.close()
                self.current_segment_file = None
        
        logger.info("Durable WAL closed")


@contextmanager
def durable_wal_context(base_path: str, **kwargs):
    """
    Context manager for using DurableWAL.
    
    Example:
        with durable_wal_context("~/.ipfs_kit/wal") as wal:
            wal.append({'operation': 'pin', 'cid': 'QmXxx...'})
    """
    wal = DurableWAL(base_path, **kwargs)
    try:
        yield wal
    finally:
        wal.close()
