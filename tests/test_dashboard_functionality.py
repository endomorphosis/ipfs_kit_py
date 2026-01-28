#!/usr/bin/env python3
"""
Test script to verify dashboard functionality
"""

import anyio
import aiohttp
import json
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardTester:
    def __init__(self, base_url="http://127.0.0.1:8004"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_dashboard_loads(self):
        """Test that the dashboard loads"""
        logger.info("Testing dashboard loads...")
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                assert response.status == 200
                html = await response.text()
                assert "IPFS Kit - Test Dashboard" in html
                logger.info("✓ Dashboard loads successfully")
                return True
        except Exception as e:
            logger.error(f"✗ Dashboard failed to load: {e}")
            return False
    
    async def test_buckets_api(self):
        """Test buckets API"""
        logger.info("Testing buckets API...")
        try:
            async with self.session.get(f"{self.base_url}/api/buckets") as response:
                assert response.status == 200
                data = await response.json()
                assert "buckets" in data
                logger.info(f"✓ Buckets API working. Found {len(data['buckets'])} buckets")
                return True
        except Exception as e:
            logger.error(f"✗ Buckets API failed: {e}")
            return False
    
    async def test_create_bucket(self):
        """Test bucket creation"""
        logger.info("Testing bucket creation...")
        try:
            bucket_data = {
                "name": "test-bucket-" + str(int(time.time())),
                "description": "Test bucket for functionality testing",
                "bucket_type": "general"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/buckets", 
                json=bucket_data
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data.get("success") == True
                logger.info(f"✓ Bucket created successfully: {bucket_data['name']}")
                return bucket_data["name"]
        except Exception as e:
            logger.error(f"✗ Bucket creation failed: {e}")
            return None
    
    async def test_bucket_files_api(self, bucket_name):
        """Test bucket files API"""
        logger.info(f"Testing bucket files API for: {bucket_name}")
        try:
            async with self.session.get(f"{self.base_url}/api/buckets/{bucket_name}/files") as response:
                assert response.status == 200
                data = await response.json()
                assert "files" in data
                logger.info(f"✓ Bucket files API working. Found {len(data['files'])} files")
                return True
        except Exception as e:
            logger.error(f"✗ Bucket files API failed: {e}")
            return False
    
    async def test_file_upload_simulation(self, bucket_name):
        """Test file upload simulation (create a test file directly)"""
        logger.info(f"Testing file upload simulation for: {bucket_name}")
        try:
            # Create a test file directly in the bucket directory
            data_dir = Path.home() / ".ipfs_kit"
            bucket_path = data_dir / "buckets" / bucket_name
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            test_file = bucket_path / "test-file.txt"
            test_content = f"Test file created at {time.time()}"
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            # Now test if the API can see it
            async with self.session.get(f"{self.base_url}/api/buckets/{bucket_name}/files") as response:
                assert response.status == 200
                data = await response.json()
                files = data.get("files", [])
                test_files = [f for f in files if f["name"] == "test-file.txt"]
                assert len(test_files) > 0
                logger.info("✓ File upload simulation successful")
                return True
        except Exception as e:
            logger.error(f"✗ File upload simulation failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting dashboard functionality tests...")
        
        results = {
            "dashboard_loads": False,
            "buckets_api": False,
            "create_bucket": None,
            "bucket_files_api": False,
            "file_upload": False
        }
        
        # Test dashboard loads
        results["dashboard_loads"] = await self.test_dashboard_loads()
        
        # Test buckets API
        results["buckets_api"] = await self.test_buckets_api()
        
        # Test bucket creation
        bucket_name = await self.test_create_bucket()
        results["create_bucket"] = bucket_name is not None
        
        if bucket_name:
            # Test bucket files API
            results["bucket_files_api"] = await self.test_bucket_files_api(bucket_name)
            
            # Test file upload simulation
            results["file_upload"] = await self.test_file_upload_simulation(bucket_name)
        
        # Print results
        logger.info("\n" + "="*50)
        logger.info("TEST RESULTS:")
        logger.info("="*50)
        for test, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{test:20}: {status}")
        
        passed = sum(1 for r in results.values() if r)
        total = len(results)
        logger.info(f"\nPassed: {passed}/{total}")
        
        return results

async def main():
    """Main test function"""
    # Wait a moment for the dashboard to be ready
    await anyio.sleep(2)
    
    async with DashboardTester() as tester:
        results = await tester.run_all_tests()
        return results

if __name__ == "__main__":
    anyio.run(main)