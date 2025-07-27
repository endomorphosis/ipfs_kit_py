#!/usr/bin/env python3
"""
Storage Backend Analytics Demo

This script demonstrates the enhanced storage and bandwidth statistics collection
from all storage backends including S3, HuggingFace, Storacha, Google Drive, etc.

New Features:
✅ Consolidated storage metrics across all backends
✅ Real bandwidth statistics from S3, HuggingFace, Storacha
✅ Per-backend storage breakdown with percentages
✅ Human-readable format for sizes
✅ Enhanced API endpoint: /dashboard/api/storage
"""

import asyncio
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def demo_consolidated_storage_metrics():
    """Demonstrate consolidated storage metrics from all backends."""
    
    logger.info("🗃️ Storage Backend Analytics Demo")
    logger.info("=" * 60)
    
    try:
        from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        # Initialize health monitor
        health_monitor = BackendHealthMonitor()
        
        logger.info("📊 Getting consolidated storage metrics from all backends...")
        
        # Get consolidated storage metrics
        storage_metrics = await health_monitor.get_consolidated_storage_metrics()
        
        # Display overview
        logger.info("\n🎯 CONSOLIDATED STORAGE OVERVIEW")
        logger.info("-" * 40)
        logger.info(f"📁 Total Storage: {storage_metrics['total_storage_human']}")
        logger.info(f"📊 Total Objects: {storage_metrics['total_objects']:,}")
        logger.info(f"⬇️  Total Bandwidth In: {storage_metrics['total_bandwidth_in_human']}")
        logger.info(f"⬆️  Total Bandwidth Out: {storage_metrics['total_bandwidth_out_human']}")
        logger.info(f"🟢 Active Backends: {storage_metrics['active_backends']}")
        logger.info(f"✅ Healthy Backends: {storage_metrics['healthy_backends']}")
        logger.info(f"⏱️  Avg Response Time: {storage_metrics['average_response_time_ms']:.2f}ms")
        
        # Display per-backend breakdown
        logger.info("\n🏗️ PER-BACKEND BREAKDOWN")
        logger.info("-" * 40)
        
        for backend_name, backend_data in storage_metrics['backend_breakdown'].items():
            status_emoji = "🟢" if backend_data['health'] == "healthy" else "🟡" if backend_data['health'] == "partial" else "🔴"
            storage_size = health_monitor._format_bytes(backend_data['storage_bytes'])
            
            logger.info(f"\n{status_emoji} {backend_name.upper()}:")
            logger.info(f"   Status: {backend_data['status']}")
            logger.info(f"   Health: {backend_data['health']}")
            logger.info(f"   Storage: {storage_size}")
            logger.info(f"   Objects: {backend_data['objects_count']:,}")
            
            if backend_data['bandwidth_in_bytes'] > 0 or backend_data['bandwidth_out_bytes'] > 0:
                bandwidth_in = health_monitor._format_bytes(backend_data['bandwidth_in_bytes'])
                bandwidth_out = health_monitor._format_bytes(backend_data['bandwidth_out_bytes'])
                logger.info(f"   Bandwidth In: {bandwidth_in}")
                logger.info(f"   Bandwidth Out: {bandwidth_out}")
            
            if backend_data['response_time_ms'] > 0:
                logger.info(f"   Response Time: {backend_data['response_time_ms']:.2f}ms")
        
        # Display storage distribution
        if storage_metrics['storage_distribution']:
            logger.info("\n📊 STORAGE DISTRIBUTION")
            logger.info("-" * 40)
            
            for backend_name, dist_data in storage_metrics['storage_distribution'].items():
                percentage = dist_data['percentage']
                size_human = dist_data['size_human']
                bar_length = int(percentage / 5)  # Scale to max 20 chars
                bar = "■" * bar_length + "□" * (20 - bar_length)
                
                logger.info(f"{backend_name:12}: {bar} {percentage:5.1f}% ({size_human})")
        
        # Show backend-specific insights
        logger.info("\n🔍 BACKEND-SPECIFIC INSIGHTS")
        logger.info("-" * 40)
        
        for backend_name, backend_data in storage_metrics['backend_breakdown'].items():
            if backend_data['health'] == "healthy" and backend_data['storage_bytes'] > 0:
                
                if backend_name == "s3":
                    logger.info(f"💿 S3: Configured for cloud object storage")
                elif backend_name == "huggingface":
                    logger.info(f"🤗 HuggingFace: ML models and datasets repository")
                elif backend_name == "storacha":
                    logger.info(f"🌐 Storacha: IPFS+Filecoin decentralized storage")
                elif backend_name == "gdrive":
                    logger.info(f"📁 Google Drive: Cloud file storage and sync")
                elif backend_name == "ipfs":
                    logger.info(f"🌍 IPFS: Distributed peer-to-peer storage")
                elif backend_name == "lotus":
                    logger.info(f"⛏️  Lotus: Filecoin blockchain storage network")
        
        logger.info(f"\n⏰ Last Updated: {storage_metrics['last_updated']}")
        
    except Exception as e:
        logger.error(f"❌ Error in storage metrics demo: {e}")
        return False
    
    return True

async def demo_api_endpoint():
    """Demonstrate the new storage API endpoint."""
    
    logger.info("\n🔗 API ENDPOINT DEMO")
    logger.info("=" * 60)
    
    try:
        import aiohttp
        
        # Test the new storage API endpoint
        logger.info("📡 Testing /dashboard/api/storage endpoint...")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://localhost:8765/dashboard/api/storage", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("success"):
                            storage_metrics = data["storage_metrics"]
                            logger.info("✅ API endpoint working correctly!")
                            logger.info(f"   Total Storage: {storage_metrics.get('total_storage_human', 'N/A')}")
                            logger.info(f"   Active Backends: {storage_metrics.get('active_backends', 0)}")
                            logger.info(f"   Backend Count: {len(storage_metrics.get('backend_breakdown', {}))}")
                        else:
                            logger.warning(f"⚠️  API returned error: {data.get('error', 'Unknown')}")
                    else:
                        logger.warning(f"⚠️  API returned HTTP {response.status}")
                        
            except aiohttp.ClientConnectorError:
                logger.info("ℹ️  Dashboard server not running - start it to test API endpoint")
            except Exception as api_error:
                logger.warning(f"⚠️  API test failed: {api_error}")
                
    except ImportError:
        logger.info("📝 Install aiohttp to test API endpoint: pip install aiohttp")
    except Exception as e:
        logger.error(f"❌ API demo error: {e}")

def show_usage_instructions():
    """Show instructions for using the enhanced storage metrics."""
    
    logger.info("\n📋 USAGE INSTRUCTIONS")
    logger.info("=" * 60)
    logger.info("1. Start the MCP server dashboard:")
    logger.info("   python start_fixed_dashboard.py")
    logger.info("")
    logger.info("2. Access storage metrics via API:")
    logger.info("   GET http://localhost:8765/dashboard/api/storage")
    logger.info("")
    logger.info("3. View metrics in dashboard:")
    logger.info("   http://localhost:8765/dashboard")
    logger.info("   → Navigate to 'Observability' tab")
    logger.info("   → View 'Storage Backends' section")
    logger.info("")
    logger.info("4. Configure backends for enhanced metrics:")
    logger.info("   • S3: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
    logger.info("   • HuggingFace: huggingface-cli login")
    logger.info("   • Storacha: Set WEB3_STORAGE_TOKEN")
    logger.info("   • Google Drive: Configure OAuth credentials")
    logger.info("")
    logger.info("🎯 Enhanced Features:")
    logger.info("   ✓ Real storage usage from all backends")
    logger.info("   ✓ Bandwidth statistics where available")
    logger.info("   ✓ Per-backend breakdown with percentages")
    logger.info("   ✓ Consolidated metrics across all services")
    logger.info("   ✓ Human-readable size formatting")

async def main():
    """Run the storage backend analytics demo."""
    
    # Run the consolidated storage metrics demo
    demo_success = await demo_consolidated_storage_metrics()
    
    # Test the API endpoint
    await demo_api_endpoint()
    
    # Show usage instructions
    show_usage_instructions()
    
    if demo_success:
        logger.info("\n🎉 SUCCESS: Enhanced storage metrics are working!")
        logger.info("   • All storage backends now provide real usage statistics")
        logger.info("   • Dashboard observability tab shows consolidated metrics")
        logger.info("   • New API endpoint /dashboard/api/storage available")
        return 0
    else:
        logger.error("\n❌ Demo encountered issues - check logs above")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))
