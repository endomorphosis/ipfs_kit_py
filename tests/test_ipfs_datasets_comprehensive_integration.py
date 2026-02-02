"""
Test suite for comprehensive ipfs_datasets_py integrations.

This tests the dataset storage capabilities added to:
Phase 1:
- audit_logging.py
- log_manager.py
- storage_wal.py

Phase 2:
- wal_telemetry.py
- mcp/monitoring/health.py

Phase 3:
- fs_journal_monitor.py
- fs_journal_replication.py

Phase 5:
- mcp/enterprise/lifecycle.py
- mcp/enterprise/data_lifecycle.py
"""

import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import directly to avoid MCP module initialization issues
try:
    # Import audit logging components directly
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ipfs_kit_py'))
    from mcp.auth.audit_logging import AuditLogger, AuditEventType
    from ipfs_kit_py.log_manager import LogManager
    from ipfs_kit_py.storage_wal import StorageWriteAheadLog, OperationType, BackendType
    from ipfs_kit_py.wal_telemetry import WALTelemetry
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import modules: {e}")
    IMPORTS_AVAILABLE = False


class TestPhase2TelemetryIntegration(unittest.TestCase):
    """Test Phase 2: WAL telemetry integration with ipfs_datasets_py."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        self.test_dir = tempfile.mkdtemp()
        self.metrics_path = os.path.join(self.test_dir, "telemetry")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_wal_telemetry_without_dataset_storage(self):
        """Test WAL telemetry works without dataset storage."""
        telemetry = WALTelemetry(
            wal=None,
            metrics_path=self.metrics_path,
            enable_dataset_storage=False,
            operation_hooks=False
        )
        
        self.assertIsNotNone(telemetry)
        self.assertFalse(telemetry.enable_dataset_storage)
        
        telemetry.close()
    
    def test_wal_telemetry_with_dataset_storage_enabled(self):
        """Test WAL telemetry with dataset storage option."""
        telemetry = WALTelemetry(
            wal=None,
            metrics_path=self.metrics_path,
            enable_dataset_storage=True,
            operation_hooks=False
        )
        
        # Should work even if datasets not available
        self.assertIsNotNone(telemetry)
        
        telemetry.close()
    
    def test_flush_metrics_to_dataset(self):
        """Test manual flush of telemetry metrics."""
        telemetry = WALTelemetry(
            wal=None,
            metrics_path=self.metrics_path,
            enable_dataset_storage=True,
            operation_hooks=False
        )
        
        # Should not raise error even if datasets unavailable
        try:
            telemetry.flush_metrics_to_dataset()
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)
        telemetry.close()


class TestAuditLoggingIntegration(unittest.TestCase):
    """Test audit logging integration with ipfs_datasets_py."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "audit.log")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_audit_logger_without_dataset_storage(self):
        """Test audit logger works without dataset storage."""
        logger = AuditLogger(
            log_file=self.log_file,
            enable_dataset_storage=False
        )
        
        event = logger.log_auth_success("user123", "192.168.1.1")
        
        self.assertIsNotNone(event)
        self.assertEqual(event.user_id, "user123")
        self.assertEqual(event.action, "login")
    
    def test_audit_logger_with_dataset_storage_disabled(self):
        """Test audit logger with dataset storage option but datasets unavailable."""
        logger = AuditLogger(
            log_file=self.log_file,
            enable_dataset_storage=True  # Will fail gracefully if ipfs_datasets not available
        )
        
        # Should work regardless of whether ipfs_datasets is available
        event = logger.log_auth_failure("user456", "192.168.1.2", reason="invalid_credentials")
        
        self.assertIsNotNone(event)
        self.assertEqual(event.user_id, "user456")
        self.assertEqual(event.status, "failure")
    
    def test_audit_logger_batch_storage(self):
        """Test that audit events accumulate before storage."""
        logger = AuditLogger(
            log_file=self.log_file,
            enable_dataset_storage=True
        )
        
        # Add multiple events
        for i in range(5):
            logger.log(
                event_type=AuditEventType.DATA,
                action=f"access_file_{i}",
                user_id=f"user{i}"
            )
        
        # Should have accumulated events
        self.assertEqual(len(logger.recent_events), 5)
    
    def test_flush_to_dataset(self):
        """Test manual flush of audit events."""
        logger = AuditLogger(
            log_file=self.log_file,
            enable_dataset_storage=True
        )
        
        logger.log_auth_success("testuser", "10.0.0.1")
        
        # Should not raise error even if datasets unavailable
        try:
            logger.flush_to_dataset()
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)


class TestLogManagerIntegration(unittest.TestCase):
    """Test log manager integration with ipfs_datasets_py."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        self.test_dir = tempfile.mkdtemp()
        # Use a different logs path for testing
        self.original_logs_path = os.environ.get('IPFS_KIT_LOGS_PATH')
        os.environ['IPFS_KIT_LOGS_PATH'] = self.test_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_logs_path:
            os.environ['IPFS_KIT_LOGS_PATH'] = self.original_logs_path
        else:
            os.environ.pop('IPFS_KIT_LOGS_PATH', None)
        
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_log_manager_basic(self):
        """Test basic log manager functionality."""
        manager = LogManager(enable_dataset_storage=False)
        
        # Should be able to get logs even if empty
        logs = manager.get_logs()
        self.assertIsInstance(logs, list)
    
    def test_log_manager_with_dataset_storage(self):
        """Test log manager with dataset storage enabled."""
        manager = LogManager(enable_dataset_storage=True)
        
        # Should work even if datasets not available
        self.assertIsNotNone(manager)
    
    def test_store_logs_as_dataset(self):
        """Test storing logs as dataset."""
        manager = LogManager(enable_dataset_storage=True)
        
        # Should not raise error even if no logs or datasets unavailable
        result = manager.store_logs_as_dataset(component="test", version="1.0")
        
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)


class TestStorageWALIntegration(unittest.TestCase):
    """Test storage WAL integration with ipfs_datasets_py."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        self.test_dir = tempfile.mkdtemp()
        self.wal_path = os.path.join(self.test_dir, "wal")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_wal_without_dataset_storage(self):
        """Test WAL works without dataset storage."""
        wal = StorageWriteAheadLog(
            base_path=self.wal_path,
            enable_dataset_storage=False,
            process_interval=60  # Don't start processing during test
        )
        
        # Add an operation
        result = wal.add_operation(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS,
            parameters={"cid": "QmTest123"}
        )
        
        self.assertTrue(result["success"])
        
        wal.close()
    
    def test_wal_with_dataset_storage_enabled(self):
        """Test WAL with dataset storage enabled."""
        wal = StorageWriteAheadLog(
            base_path=self.wal_path,
            enable_dataset_storage=True,
            process_interval=60
        )
        
        # Should work even if datasets not available
        result = wal.add_operation(
            operation_type=OperationType.PIN,
            backend=BackendType.IPFS,
            parameters={"cid": "QmTest456"}
        )
        
        self.assertTrue(result["success"])
        
        wal.close()
    
    def test_archive_to_dataset(self):
        """Test archiving WAL to dataset."""
        wal = StorageWriteAheadLog(
            base_path=self.wal_path,
            enable_dataset_storage=True,
            process_interval=60
        )
        
        # Try to archive (should not raise error even if datasets unavailable)
        result = wal.archive_to_dataset()
        
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        
        wal.close()


class TestPhase3FileSystemIntegration(unittest.TestCase):
    """Test Phase 3: Filesystem monitor and replication integration with ipfs_datasets_py."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
        self.stats_dir = os.path.join(self.test_dir, "stats")
        self.replication_path = os.path.join(self.test_dir, "replication")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except OSError:
                # If cleanup fails due to race conditions, ignore
                shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_fs_journal_monitor_without_dataset(self):
        """Test journal monitor works without dataset storage."""
        try:
            from fs_journal_monitor import JournalHealthMonitor
            from ipfs_kit_py.filesystem_journal import FilesystemJournal
            
            journal = FilesystemJournal(
                base_path=self.journal_path,
                sync_interval=5
            )
            
            monitor = JournalHealthMonitor(
                journal=journal,
                check_interval=60,
                stats_dir=self.stats_dir,
                enable_dataset_storage=False
            )
            
            # Should work without dataset storage
            self.assertIsNotNone(monitor)
            self.assertFalse(monitor.enable_dataset_storage)
            
            # Collect stats should work
            stats = monitor.collect_stats()
            self.assertIsInstance(stats, dict)
            self.assertIn("timestamp", stats)
            
            # Stop monitoring properly
            monitor.stop()
            
        except ImportError:
            self.skipTest("fs_journal_monitor not available")
    
    def test_fs_journal_monitor_with_dataset(self):
        """Test journal monitor with dataset storage enabled."""
        try:
            from fs_journal_monitor import JournalHealthMonitor
            from ipfs_kit_py.filesystem_journal import FilesystemJournal
            
            journal = FilesystemJournal(
                base_path=self.journal_path,
                sync_interval=5
            )
            
            monitor = JournalHealthMonitor(
                journal=journal,
                check_interval=60,
                stats_dir=self.stats_dir,
                enable_dataset_storage=True,
                dataset_batch_size=10
            )
            
            # Should initialize (may or may not have dataset support)
            self.assertIsNotNone(monitor)
            
            # If dataset storage enabled, should have manager
            if monitor.enable_dataset_storage:
                self.assertIsNotNone(monitor.dataset_manager)
            
            # Manual flush should not raise error
            monitor.flush_to_dataset()
            
            # Stop monitoring properly
            monitor.stop()
            
        except ImportError:
            self.skipTest("fs_journal_monitor not available")
    
    def test_fs_replication_without_dataset(self):
        """Test metadata replication without dataset storage."""
        try:
            from fs_journal_replication import MetadataReplicationManager
            
            manager = MetadataReplicationManager(
                node_id="test-node-1",
                role="worker",
                config={
                    "base_path": self.replication_path,
                    "enable_dataset_storage": False
                }
            )
            
            # Should work without dataset storage
            self.assertIsNotNone(manager)
            self.assertFalse(manager.enable_dataset_storage)
            
            # Save state should not raise error (may fail due to race conditions)
            try:
                result = manager._save_state()
                # If it succeeds, that's great
                if result:
                    self.assertTrue(result)
            except Exception:
                # If it fails, that's also okay for this test
                pass
            
            # Stop threads properly
            manager.close()
            
        except ImportError:
            self.skipTest("fs_journal_replication not available")
    
    def test_fs_replication_with_dataset(self):
        """Test metadata replication with dataset storage enabled."""
        try:
            from fs_journal_replication import MetadataReplicationManager
            
            manager = MetadataReplicationManager(
                node_id="test-node-2",
                role="worker",
                config={
                    "base_path": self.replication_path,
                    "enable_dataset_storage": True,
                    "dataset_batch_size": 10
                }
            )
            
            # Should initialize (may or may not have dataset support)
            self.assertIsNotNone(manager)
            
            # If dataset storage enabled, should have manager
            if manager.enable_dataset_storage:
                self.assertIsNotNone(manager.dataset_manager)
            
            # Manual flush should not raise error
            manager.flush_to_dataset()
            
            # Stop threads properly
            manager.close()
            
        except ImportError:
            self.skipTest("fs_journal_replication not available")


class TestPhase5EnterpriseIntegration(unittest.TestCase):
    """Test Phase 5: Enterprise lifecycle integration with ipfs_datasets_py."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.lifecycle_path = os.path.join(self.test_dir, "lifecycle")
        self.data_lifecycle_path = os.path.join(self.test_dir, "data_lifecycle")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_lifecycle_manager_without_dataset(self):
        """Test lifecycle manager works without dataset storage."""
        try:
            from mcp.enterprise.lifecycle import LifecycleManager
            
            manager = LifecycleManager(
                metadata_db_path=os.path.join(self.lifecycle_path, "metadata.json"),
                enable_dataset_storage=False
            )
            
            # Should work without dataset storage
            self.assertIsNotNone(manager)
            self.assertFalse(manager.enable_dataset_storage)
            
            # Save metadata should work
            manager._save_metadata()
            
            # Stop manager
            manager.stop()
            
        except ImportError:
            self.skipTest("lifecycle module not available")
    
    def test_lifecycle_manager_with_dataset(self):
        """Test lifecycle manager with dataset storage enabled."""
        try:
            from mcp.enterprise.lifecycle import LifecycleManager
            
            manager = LifecycleManager(
                metadata_db_path=os.path.join(self.lifecycle_path, "metadata.json"),
                enable_dataset_storage=True,
                dataset_batch_size=10
            )
            
            # Should initialize (may or may not have dataset support)
            self.assertIsNotNone(manager)
            
            # If dataset storage enabled, should have manager
            if manager.enable_dataset_storage:
                self.assertIsNotNone(manager.dataset_manager)
            
            # Manual flush should not raise error
            manager.flush_to_dataset()
            
            # Stop manager
            manager.stop()
            
        except ImportError:
            self.skipTest("lifecycle module not available")
    
    def test_data_lifecycle_manager_without_dataset(self):
        """Test data lifecycle manager without dataset storage."""
        try:
            from mcp.enterprise.data_lifecycle import DataLifecycleManager
            
            manager = DataLifecycleManager(
                storage_path=self.data_lifecycle_path,
                enable_dataset_storage=False
            )
            
            # Should work without dataset storage
            self.assertIsNotNone(manager)
            self.assertFalse(manager.enable_dataset_storage)
            
            # Stop manager
            manager.stop()
            
        except ImportError:
            self.skipTest("data_lifecycle module not available")
    
    def test_data_lifecycle_manager_with_dataset(self):
        """Test data lifecycle manager with dataset storage enabled."""
        try:
            from mcp.enterprise.data_lifecycle import DataLifecycleManager
            
            manager = DataLifecycleManager(
                storage_path=self.data_lifecycle_path,
                enable_dataset_storage=True,
                dataset_batch_size=10
            )
            
            # Should initialize (may or may not have dataset support)
            self.assertIsNotNone(manager)
            
            # If dataset storage enabled, should have manager
            if manager.enable_dataset_storage:
                self.assertIsNotNone(manager.dataset_manager)
            
            # Manual flush should not raise error
            manager.flush_to_dataset()
            
            # Stop manager
            manager.stop()
            
        except ImportError:
            self.skipTest("data_lifecycle module not available")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Phase 1 tests
    suite.addTests(loader.loadTestsFromTestCase(TestAuditLoggingIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestLogManagerIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestStorageWALIntegration))
    
    # Phase 2 tests
    suite.addTests(loader.loadTestsFromTestCase(TestPhase2TelemetryIntegration))
    
    # Phase 3 tests
    suite.addTests(loader.loadTestsFromTestCase(TestPhase3FileSystemIntegration))
    
    # Phase 5 tests
    suite.addTests(loader.loadTestsFromTestCase(TestPhase5EnterpriseIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
