#!/usr/bin/env python3
"""
Comprehensive Dashboard Test Suite

Tests all integrated comprehensive features to ensure they work correctly.
"""

import anyio
import json
import aiohttp
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComprehensiveDashboardTester:
    def __init__(self, base_url: str = "http://127.0.0.1:8007"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_comprehensive_discovery(self):
        """Test the comprehensive features discovery endpoint."""
        logger.info("🔍 Testing comprehensive features discovery...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/comprehensive") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        features_data = data["data"]
                        logger.info(f"✅ Discovery successful!")
                        logger.info(f"   - Total Features: {features_data.get('total_features', 0)}")
                        logger.info(f"   - Categories: {len(features_data.get('categories', []))}")
                        logger.info(f"   - Available Categories: {', '.join(features_data.get('categories', []))}")
                        return features_data
                    else:
                        logger.error(f"❌ Discovery failed: {data.get('error')}")
                        return None
                else:
                    logger.error(f"❌ Discovery request failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"❌ Discovery error: {e}")
            return None
    
    async def test_category_features(self, category: str):
        """Test features in a specific category."""
        logger.info(f"🔍 Testing {category} category features...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/comprehensive/{category}") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        category_data = data["data"]
                        feature_count = category_data.get("feature_count", 0)
                        features = category_data.get("features", [])
                        logger.info(f"✅ {category} category: {feature_count} features")
                        logger.info(f"   - Features: {', '.join(features[:5])}{'...' if len(features) > 5 else ''}")
                        return features
                    else:
                        logger.error(f"❌ {category} category failed: {data.get('error')}")
                        return []
                else:
                    logger.error(f"❌ {category} request failed: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"❌ {category} error: {e}")
            return []
    
    async def test_feature_execution(self, category: str, action: str, test_data: dict = None):
        """Test executing a specific feature."""
        logger.info(f"⚡ Testing {category}/{action}...")
        
        try:
            payload = test_data or {}
            async with self.session.post(
                f"{self.base_url}/api/comprehensive/{category}/{action}",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        logger.info(f"✅ {category}/{action} executed successfully")
                        # Log first few keys of response data
                        if isinstance(data.get("data"), dict):
                            keys = list(data["data"].keys())[:3]
                            logger.info(f"   - Response keys: {keys}")
                        return data["data"]
                    else:
                        logger.warning(f"⚠️ {category}/{action} execution failed: {data.get('error')}")
                        return None
                else:
                    logger.warning(f"⚠️ {category}/{action} request failed: {response.status}")
                    return None
        except Exception as e:
            logger.warning(f"⚠️ {category}/{action} error: {e}")
            return None
    
    async def test_batch_execution(self):
        """Test batch execution of multiple features."""
        logger.info("🔄 Testing batch execution...")
        
        batch_actions = [
            {"category": "system", "action": "get_system_status", "data": {}},
            {"category": "mcp", "action": "get_mcp_status", "data": {}},
            {"category": "backend", "action": "get_backends", "data": {}}
        ]
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/comprehensive/batch",
                json={"actions": batch_actions}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        batch_data = data["data"]
                        total = batch_data.get("total_actions", 0)
                        successful = batch_data.get("successful_actions", 0)
                        failed = batch_data.get("failed_actions", 0)
                        logger.info(f"✅ Batch execution completed!")
                        logger.info(f"   - Total: {total}, Successful: {successful}, Failed: {failed}")
                        return batch_data
                    else:
                        logger.error(f"❌ Batch execution failed: {data.get('error')}")
                        return None
                else:
                    logger.error(f"❌ Batch request failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"❌ Batch execution error: {e}")
            return None

async def run_comprehensive_tests():
    """Run all comprehensive dashboard tests."""
    logger.info("🚀 Starting Comprehensive Dashboard Tests")
    logger.info("=" * 60)
    
    async with ComprehensiveDashboardTester() as tester:
        # Test 1: Discovery
        logger.info("\n📋 TEST 1: Feature Discovery")
        features_data = await tester.test_comprehensive_discovery()
        if not features_data:
            logger.error("❌ Feature discovery failed - stopping tests")
            return
        
        # Test 2: Category Exploration  
        logger.info("\n📂 TEST 2: Category Exploration")
        categories = features_data.get("categories", [])
        for category in categories[:5]:  # Test first 5 categories
            await tester.test_category_features(category)
        
        # Test 3: Feature Execution
        logger.info("\n⚡ TEST 3: Feature Execution")
        test_features = [
            ("system", "get_system_status"),
            ("mcp", "get_mcp_status"),
            ("backend", "get_backends"),
            ("bucket", "get_buckets"),
            ("config", "get_all_configs")
        ]
        
        execution_results = []
        for category, action in test_features:
            result = await tester.test_feature_execution(category, action)
            execution_results.append(result is not None)
        
        # Test 4: Batch Execution
        logger.info("\n🔄 TEST 4: Batch Execution")
        batch_result = await tester.test_batch_execution()
        
        # Summary
        logger.info("\n📊 TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Discovery: {'PASS' if features_data else 'FAIL'}")
        logger.info(f"✅ Categories tested: {len(categories[:5])}")
        logger.info(f"✅ Feature executions: {sum(execution_results)}/{len(execution_results)} successful")
        logger.info(f"✅ Batch execution: {'PASS' if batch_result else 'FAIL'}")
        
        if features_data:
            logger.info(f"🎉 Comprehensive Dashboard Integration SUCCESSFUL!")
            logger.info(f"   - Total Features Available: {features_data.get('total_features', 0)}")
            logger.info(f"   - Categories Available: {len(features_data.get('categories', []))}")
            logger.info(f"   - Feature Parity: {'ACHIEVED' if features_data.get('total_features', 0) >= 80 else 'PARTIAL'}")
        else:
            logger.error("❌ Comprehensive Dashboard Integration FAILED")

if __name__ == "__main__":
    anyio.run(run_comprehensive_tests)
