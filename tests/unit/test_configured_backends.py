#!/usr/bin/env python3
"""
Test S3 and HuggingFace Backend Integration

This script specifically tests the S3 and HuggingFace backends with your configured credentials.
"""

import anyio
import pytest
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.anyio

async def test_s3_backend():
    """Test S3 backend with configured credentials."""
    logger.info("🗄️ Testing S3 Backend Integration...")
    
    try:
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        health_monitor = BackendHealthMonitor()
        
        # Test S3 backend specifically
        s3_health = await health_monitor.check_backend_health("s3")
        
        if s3_health:
            logger.info("✅ S3 Backend Results:")
            logger.info(f"   Status: {s3_health.get('status', 'unknown')}")
            logger.info(f"   Health: {s3_health.get('health', 'unknown')}")
            
            metrics = s3_health.get('metrics', {})
            logger.info(f"   Boto3 Available: {metrics.get('boto3_available', False)}")
            logger.info(f"   Credentials Available: {metrics.get('credentials_available', False)}")
            logger.info(f"   Client Creation: {metrics.get('client_creation', 'unknown')}")
            
            if 'total_storage_bytes' in metrics:
                storage_gb = metrics['total_storage_bytes'] / (1024**3)
                logger.info(f"   Total Storage: {storage_gb:.2f} GB")
                logger.info(f"   Total Objects: {metrics.get('total_objects', 0)}")
                logger.info(f"   Bucket Count: {metrics.get('bucket_count', 0)}")
        else:
            logger.warning("⚠️ No S3 health data returned")
            
    except Exception as e:
        logger.error(f"❌ S3 backend test failed: {e}")

async def test_huggingface_backend():
    """Test HuggingFace backend with configured credentials."""
    logger.info("🤗 Testing HuggingFace Backend Integration...")
    
    try:
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        health_monitor = BackendHealthMonitor()
        
        # Test HuggingFace backend specifically
        hf_health = await health_monitor.check_backend_health("huggingface")
        
        if hf_health:
            logger.info("✅ HuggingFace Backend Results:")
            logger.info(f"   Status: {hf_health.get('status', 'unknown')}")
            logger.info(f"   Health: {hf_health.get('health', 'unknown')}")
            
            metrics = hf_health.get('metrics', {})
            logger.info(f"   HF Hub Available: {metrics.get('huggingface_hub_available', False)}")
            logger.info(f"   Authenticated: {metrics.get('authenticated', False)}")
            logger.info(f"   Username: {metrics.get('username', 'unknown')}")
            
            if 'total_data_stored_bytes' in metrics:
                storage_mb = metrics['total_data_stored_bytes'] / (1024**2)
                logger.info(f"   Total Storage: {storage_mb:.2f} MB")
                logger.info(f"   Total Models: {metrics.get('total_models', 0)}")
                logger.info(f"   Total Datasets: {metrics.get('total_datasets', 0)}")
        else:
            logger.warning("⚠️ No HuggingFace health data returned")
            
    except Exception as e:
        logger.error(f"❌ HuggingFace backend test failed: {e}")

async def test_consolidated_with_real_backends():
    """Test consolidated storage metrics with real S3 and HuggingFace data."""
    logger.info("📊 Testing Consolidated Storage with Real Backend Data...")
    
    try:
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        health_monitor = BackendHealthMonitor()
        
        # First, run health checks on the backends we've configured
        logger.info("🔍 Running health checks on S3 and HuggingFace...")
        await health_monitor.check_backend_health("s3")
        await health_monitor.check_backend_health("huggingface")
        
        # Now get consolidated metrics
        consolidated = await health_monitor.get_consolidated_storage_metrics()
        
        logger.info("📈 Consolidated Results:")
        logger.info(f"   Total Storage: {consolidated['total_storage_human']}")
        logger.info(f"   Active Backends: {consolidated['active_backends']}")
        logger.info(f"   Healthy Backends: {consolidated['healthy_backends']}")
        
        # Show breakdown for configured backends
        for backend_name in ['s3', 'huggingface']:
            if backend_name in consolidated['backend_breakdown']:
                data = consolidated['backend_breakdown'][backend_name]
                logger.info(f"   {backend_name.upper()}:")
                logger.info(f"     Status: {data['status']}")
                logger.info(f"     Health: {data['health']}")
                logger.info(f"     Storage: {health_monitor._format_bytes(data['storage_bytes'])}")
                
    except Exception as e:
        logger.error(f"❌ Consolidated test failed: {e}")

async def main():
    """Run all backend integration tests."""
    logger.info("🚀 Testing S3 and HuggingFace Backend Integration")
    logger.info("=" * 60)
    
    # Test individual backends
    await test_s3_backend()
    logger.info("")
    await test_huggingface_backend()
    logger.info("")
    
    # Test consolidated metrics
    await test_consolidated_with_real_backends()
    
    logger.info("\n✅ Backend integration tests completed!")
    logger.info("🎯 Next: Start the dashboard to see real metrics")
    logger.info("   python start_fixed_dashboard.py")

if __name__ == "__main__":
    anyio.run(main)
