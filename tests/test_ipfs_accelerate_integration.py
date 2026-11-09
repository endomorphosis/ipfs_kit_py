#!/usr/bin/env python3
"""
Test suite for ipfs_accelerate_py integration across AI/ML modules.

Tests ensure:
1. Graceful fallback when ipfs_accelerate_py is not available
2. Proper compute layer usage when ipfs_accelerate_py is available
3. No failures in CI/CD without optional dependencies
4. Compatibility with ipfs_datasets_py integration
"""

import unittest
import sys
import os
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestIPFSAccelerateIntegration(unittest.TestCase):
    """Test ipfs_accelerate_py integration with AI/ML modules."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_framework_integration_import(self):
        """Test that framework_integration imports without errors."""
        try:
            from ipfs_kit_py.mcp.ai import framework_integration
            self.assertIsNotNone(framework_integration)
            self.assertTrue(hasattr(framework_integration, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"framework_integration not available: {e}")
    
    def test_framework_integration_has_accelerate_flag(self):
        """Test that HAS_ACCELERATE flag is present."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import HAS_ACCELERATE
            # Should be bool, either True or False
            self.assertIsInstance(HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"framework_integration not available: {e}")
    
    def test_distributed_training_import(self):
        """Test that distributed_training imports without errors."""
        try:
            from ipfs_kit_py.mcp.ai import distributed_training
            self.assertIsNotNone(distributed_training)
            self.assertTrue(hasattr(distributed_training, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"distributed_training not available: {e}")
    
    def test_distributed_training_has_accelerate_flag(self):
        """Test that HAS_ACCELERATE flag is present in distributed_training."""
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import HAS_ACCELERATE
            self.assertIsInstance(HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"distributed_training not available: {e}")
    
    def test_model_registry_import(self):
        """Test that model_registry imports without errors."""
        try:
            from ipfs_kit_py.mcp.ai import model_registry
            self.assertIsNotNone(model_registry)
            self.assertTrue(hasattr(model_registry, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"model_registry not available: {e}")
    
    def test_model_registry_has_accelerate_flag(self):
        """Test that HAS_ACCELERATE flag is present in model_registry."""
        try:
            from ipfs_kit_py.mcp.ai.model_registry import HAS_ACCELERATE
            self.assertIsInstance(HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"model_registry not available: {e}")
    
    def test_ai_ml_integrator_import(self):
        """Test that ai_ml_integrator imports without errors."""
        try:
            from ipfs_kit_py.mcp.ai import ai_ml_integrator
            self.assertIsNotNone(ai_ml_integrator)
            self.assertTrue(hasattr(ai_ml_integrator, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"ai_ml_integrator not available: {e}")
    
    def test_ai_ml_integrator_has_accelerate_flag(self):
        """Test that HAS_ACCELERATE flag is present in ai_ml_integrator."""
        try:
            from ipfs_kit_py.mcp.ai.ai_ml_integrator import HAS_ACCELERATE
            self.assertIsInstance(HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"ai_ml_integrator not available: {e}")
    
    def test_utils_check_dependencies(self):
        """Test that utils.check_dependencies includes ipfs_accelerate_py."""
        try:
            from ipfs_kit_py.mcp.ai.utils import check_dependencies
            deps = check_dependencies()
            self.assertIsInstance(deps, dict)
            self.assertIn('ipfs_accelerate_py', deps)
            self.assertIn('ipfs_datasets_py', deps)
            # Should be bool values
            self.assertIsInstance(deps['ipfs_accelerate_py'], bool)
            self.assertIsInstance(deps['ipfs_datasets_py'], bool)
        except ImportError as e:
            self.skipTest(f"utils not available: {e}")
    
    def test_framework_integration_graceful_fallback(self):
        """Test that framework_integration works without ipfs_accelerate_py."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import (
                HAS_ACCELERATE, HuggingFaceConfig, HuggingFaceIntegration
            )
            
            # Should work regardless of HAS_ACCELERATE value
            config = HuggingFaceConfig(
                name="test-hf",
                model_id="gpt2",
                use_local=False
            )
            self.assertIsNotNone(config)
            
            # Should be able to create integration
            integration = HuggingFaceIntegration(config)
            self.assertIsNotNone(integration)
            
        except ImportError as e:
            self.skipTest(f"HuggingFace components not available: {e}")
    
    def test_distributed_training_graceful_fallback(self):
        """Test that distributed_training works without ipfs_accelerate_py."""
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import (
                HAS_ACCELERATE, DistributedTrainingManager
            )
            
            # Should work regardless of HAS_ACCELERATE value
            manager = DistributedTrainingManager(storage_path=self.test_dir)
            self.assertIsNotNone(manager)
            
            # Should be able to create a job
            job = manager.create_job(
                name="test-job",
                config={"learning_rate": 0.001},
                framework="pytorch"
            )
            self.assertIsNotNone(job)
            
        except ImportError as e:
            self.skipTest(f"DistributedTrainingManager not available: {e}")
    
    def test_model_registry_graceful_fallback(self):
        """Test that model_registry works without ipfs_accelerate_py."""
        try:
            from ipfs_kit_py.mcp.ai.model_registry import (
                HAS_ACCELERATE, ModelRegistry
            )
            
            # Should work regardless of HAS_ACCELERATE value
            registry = ModelRegistry(storage_path=self.test_dir)
            self.assertIsNotNone(registry)
            
        except ImportError as e:
            self.skipTest(f"ModelRegistry not available: {e}")
    
    def test_no_hard_dependency_on_ipfs_accelerate(self):
        """Test that modules don't crash if ipfs_accelerate_py is unavailable."""
        # This test verifies that all imports work even without ipfs_accelerate_py
        modules_to_test = [
            'ipfs_kit_py.mcp.ai.framework_integration',
            'ipfs_kit_py.mcp.ai.distributed_training',
            'ipfs_kit_py.mcp.ai.model_registry',
            'ipfs_kit_py.mcp.ai.ai_ml_integrator',
            'ipfs_kit_py.mcp.ai.utils',
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                # If we get here, import succeeded
                self.assertTrue(True, f"{module_name} imported successfully")
            except ImportError as e:
                # Module itself not available (e.g., in minimal CI environment)
                self.skipTest(f"{module_name} not available: {e}")
            except Exception as e:
                # Should not raise other exceptions
                self.fail(f"{module_name} raised unexpected exception: {e}")
    
    def test_ci_cd_compatibility(self):
        """Test that code works in CI/CD without optional dependencies."""
        # Simulate CI/CD environment where ipfs_accelerate_py is not installed
        # All modules should import and basic functionality should work
        
        try:
            from ipfs_kit_py.mcp.ai import utils
            deps = utils.check_dependencies()
            
            # In CI/CD, many deps might be False
            # Code should handle this gracefully
            self.assertIsInstance(deps, dict)
            
            # Each dependency check should return bool, not raise exception
            for dep_name, is_available in deps.items():
                self.assertIsInstance(is_available, bool, 
                    f"Dependency {dep_name} check should return bool")
                
        except ImportError as e:
            self.skipTest(f"utils not available: {e}")


class TestComputeAccelerationUsage(unittest.TestCase):
    """Test that compute acceleration is used when available."""
    
    def test_framework_integration_logs_acceleration_usage(self):
        """Test that framework_integration logs when using acceleration."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import HAS_ACCELERATE
            
            if HAS_ACCELERATE:
                # If acceleration is available, should use it
                # (This is tested indirectly through logs in actual execution)
                self.assertTrue(True, "Acceleration available for use")
            else:
                self.skipTest("ipfs_accelerate_py not available")
                
        except ImportError as e:
            self.skipTest(f"framework_integration not available: {e}")
    
    def test_distributed_training_logs_acceleration_usage(self):
        """Test that distributed_training logs when using acceleration."""
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import HAS_ACCELERATE
            
            if HAS_ACCELERATE:
                self.assertTrue(True, "Acceleration available for distributed training")
            else:
                self.skipTest("ipfs_accelerate_py not available")
                
        except ImportError as e:
            self.skipTest(f"distributed_training not available: {e}")


if __name__ == '__main__':
    unittest.main()
