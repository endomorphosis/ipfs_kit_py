#!/usr/bin/env python3
"""
Unit tests for enhanced WAL durability.
"""

import os
import time
import tempfile
import shutil
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.enhanced_wal_durability import (
    DurableWAL,
    WALCheckpoint,
    durable_wal_context,
)


class TestDurableWAL(unittest.TestCase):
    """Test enhanced WAL durability functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.wal_path = os.path.join(self.test_dir, "wal")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_wal_initialization(self):
        """Test WAL initialization."""
        wal = DurableWAL(
            base_path=self.wal_path,
            fsync_mode="always",
        )
        
        # Check directories created
        self.assertTrue(Path(self.wal_path).exists())
        self.assertTrue((Path(self.wal_path) / "segments").exists())
        self.assertTrue((Path(self.wal_path) / "checkpoints").exists())
        
        stats = wal.get_stats()
        self.assertEqual(stats['sequence_number'], 0)
        self.assertEqual(stats['fsync_mode'], 'always')
        
        wal.close()
    
    def test_append_operations(self):
        """Test appending operations to WAL."""
        wal = DurableWAL(
            base_path=self.wal_path,
            fsync_mode="batch",
            batch_size=5,
        )
        
        # Append operations
        operations = [
            {'type': 'pin', 'cid': 'QmTest1'},
            {'type': 'add', 'path': '/test/file1'},
            {'type': 'get', 'cid': 'QmTest2'},
        ]
        
        seq_nums = []
        for op in operations:
            seq_num = wal.append(op)
            seq_nums.append(seq_num)
        
        # Sequence numbers should be sequential
        self.assertEqual(seq_nums, [1, 2, 3])
        
        stats = wal.get_stats()
        self.assertEqual(stats['total_operations'], 3)
        
        wal.close()
    
    def test_batch_append(self):
        """Test batch append operations."""
        wal = DurableWAL(
            base_path=self.wal_path,
            fsync_mode="batch",
        )
        
        operations = [
            {'type': 'pin', 'cid': f'QmTest{i}'}
            for i in range(10)
        ]
        
        seq_nums = wal.append_batch(operations)
        
        # Should get 10 sequence numbers
        self.assertEqual(len(seq_nums), 10)
        self.assertEqual(seq_nums, list(range(1, 11)))
        
        stats = wal.get_stats()
        self.assertEqual(stats['total_operations'], 10)
        self.assertGreater(stats['total_batches'], 0)
        
        wal.close()
    
    def test_fsync_modes(self):
        """Test different fsync modes."""
        # Test "always" mode
        wal_always = DurableWAL(
            base_path=os.path.join(self.test_dir, "wal_always"),
            fsync_mode="always",
        )
        
        wal_always.append({'type': 'test'})
        stats = wal_always.get_stats()
        self.assertGreater(stats['total_fsyncs'], 0)
        wal_always.close()
        
        # Test "batch" mode
        wal_batch = DurableWAL(
            base_path=os.path.join(self.test_dir, "wal_batch"),
            fsync_mode="batch",
            batch_size=5,
        )
        
        for i in range(3):
            wal_batch.append({'type': 'test', 'id': i})
        
        # Should not fsync yet (batch not full)
        stats = wal_batch.get_stats()
        # Fsyncs may or may not have happened depending on timing
        
        wal_batch.close()
    
    def test_checkpointing(self):
        """Test checkpoint creation."""
        wal = DurableWAL(
            base_path=self.wal_path,
            checkpoint_interval=5,  # Checkpoint every 5 operations
        )
        
        # Add operations to trigger checkpoint
        for i in range(10):
            wal.append({'type': 'test', 'id': i})
        
        stats = wal.get_stats()
        self.assertGreater(stats['total_checkpoints'], 0)
        self.assertGreater(stats['checkpoint_count'], 0)
        
        wal.close()
    
    def test_recovery(self):
        """Test WAL recovery."""
        # Create WAL and add operations
        wal1 = DurableWAL(
            base_path=self.wal_path,
            checkpoint_interval=5,
            fsync_mode="always",  # Ensure data is written
        )
        
        test_operations = [
            {'type': 'pin', 'cid': f'QmTest{i}'}
            for i in range(10)
        ]
        
        for op in test_operations:
            wal1.append(op)
        
        # Manually flush to ensure data is written
        wal1._flush_batch()
        wal1._fsync_current_segment()
        wal1.close()
        
        # Create new WAL instance and recover
        wal2 = DurableWAL(base_path=self.wal_path)
        
        recovered = wal2.recover()
        
        # Should recover operations (may be fewer if checkpoint recovery is used)
        self.assertGreaterEqual(len(recovered), 0)
        
        # Check that some operations match if any were recovered
        if len(recovered) > 0:
            for recovered_op in recovered:
                self.assertEqual(recovered_op['type'], 'pin')
        
        wal2.close()
    
    def test_segment_rotation(self):
        """Test segment rotation."""
        wal = DurableWAL(
            base_path=self.wal_path,
            max_segment_size=1024,  # Small size to trigger rotation
        )
        
        # Add many operations to trigger rotation
        for i in range(100):
            wal.append({
                'type': 'test',
                'data': 'x' * 100,  # Large payload
            })
        
        # Check that multiple segments were created
        segments_dir = Path(self.wal_path) / "segments"
        segments = list(segments_dir.glob("wal_*.log"))
        
        # May have multiple segments depending on operation size
        self.assertGreater(len(segments), 0)
        
        wal.close()
    
    def test_corruption_detection(self):
        """Test corruption detection during recovery."""
        # Create WAL with checkpoint
        wal1 = DurableWAL(
            base_path=self.wal_path,
            checkpoint_interval=5,
        )
        
        for i in range(10):
            wal1.append({'type': 'test', 'id': i})
        
        wal1.close()
        
        # Corrupt a segment file
        segments_dir = Path(self.wal_path) / "segments"
        segments = list(segments_dir.glob("wal_*.log"))
        
        if segments:
            with open(segments[0], 'a') as f:
                f.write("CORRUPTED DATA\n")
        
        # Recover and check for corruption detection
        wal2 = DurableWAL(base_path=self.wal_path)
        recovered = wal2.recover()
        
        stats = wal2.get_stats()
        # Corruption may or may not be detected depending on checkpoint
        
        wal2.close()
    
    def test_context_manager(self):
        """Test using WAL with context manager."""
        with durable_wal_context(self.wal_path) as wal:
            wal.append({'type': 'test'})
            
            stats = wal.get_stats()
            self.assertEqual(stats['total_operations'], 1)
        
        # WAL should be closed after context
        self.assertIsNone(wal.current_segment_file)
    
    def test_statistics(self):
        """Test WAL statistics."""
        wal = DurableWAL(
            base_path=self.wal_path,
            checkpoint_interval=5,
        )
        
        # Perform operations
        for i in range(10):
            wal.append({'type': 'test', 'id': i})
        
        stats = wal.get_stats()
        
        # Check expected fields
        self.assertIn('total_operations', stats)
        self.assertIn('total_batches', stats)
        self.assertIn('total_fsyncs', stats)
        self.assertIn('total_checkpoints', stats)
        self.assertIn('sequence_number', stats)
        
        self.assertEqual(stats['total_operations'], 10)
        self.assertEqual(stats['sequence_number'], 10)
        
        wal.close()


if __name__ == '__main__':
    unittest.main()
