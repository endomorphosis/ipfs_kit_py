#!/usr/bin/env python3
"""
Comprehensive test script for bucket functionality in the MCP dashboard.
Tests all CRUD operations: Create, Read, Upload, Download, Delete.
"""

import anyio
import aiohttp
import json
import tempfile
import os
from pathlib import Path

class BucketFunctionalityTester:
    def __init__(self, dashboard_url="http://127.0.0.1:8085"):
        self.dashboard_url = dashboard_url
        self.test_bucket_name = "test-bucket-functionality"
        self.test_file_content = "This is a test file for bucket functionality testing."
        
    async def test_bucket_operations(self):
        """Test all bucket operations."""
        print("🧪 Starting comprehensive bucket functionality test...")
        
        async with aiohttp.ClientSession() as session:
            # Test 1: List buckets (should work even if empty)
            await self.test_list_buckets(session)
            
            # Test 2: Create a new bucket
            await self.test_create_bucket(session)
            
            # Test 3: List buckets again (should show our new bucket)
            await self.test_list_buckets(session)
            
            # Test 4: Upload a file to the bucket
            await self.test_upload_file(session)
            
            # Test 5: List files in the bucket
            await self.test_list_bucket_files(session)
            
            # Test 6: Download the file from the bucket
            await self.test_download_file(session)
            
            # Test 7: Delete the bucket
            await self.test_delete_bucket(session)
            
            # Test 8: Verify bucket is deleted
            await self.test_list_buckets(session)
            
        print("✅ All bucket functionality tests completed!")
    
    async def test_list_buckets(self, session):
        """Test listing buckets."""
        print("\n📝 Testing bucket listing...")
        async with session.get(f"{self.dashboard_url}/api/buckets") as resp:
            if resp.status == 200:
                data = await resp.json()
                buckets = data.get('buckets', [])
                print(f"   ✅ Successfully listed {len(buckets)} buckets")
                for bucket in buckets:
                    print(f"      - {bucket.get('name', 'Unknown')}")
            else:
                print(f"   ❌ Failed to list buckets: {resp.status}")
                print(f"      Response: {await resp.text()}")
    
    async def test_create_bucket(self, session):
        """Test creating a bucket."""
        print(f"\n🔨 Testing bucket creation: {self.test_bucket_name}")
        data = {
            "name": self.test_bucket_name,
            "description": "Test bucket for functionality verification"
        }
        async with session.post(f"{self.dashboard_url}/api/buckets", json=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"   ✅ Successfully created bucket: {result}")
            else:
                print(f"   ❌ Failed to create bucket: {resp.status}")
                print(f"      Response: {await resp.text()}")
    
    async def test_upload_file(self, session):
        """Test uploading a file to the bucket."""
        print(f"\n⬆️  Testing file upload to bucket: {self.test_bucket_name}")
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(self.test_file_content)
            tmp_file_path = tmp_file.name
        
        try:
            # Upload the file
            with open(tmp_file_path, 'rb') as file:
                form_data = aiohttp.FormData()
                form_data.add_field('file', file, filename='test-file.txt')
                
                async with session.post(
                    f"{self.dashboard_url}/api/buckets/{self.test_bucket_name}/upload",
                    data=form_data
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        print(f"   ✅ Successfully uploaded file: {result}")
                    else:
                        print(f"   ❌ Failed to upload file: {resp.status}")
                        print(f"      Response: {await resp.text()}")
        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)
    
    async def test_list_bucket_files(self, session):
        """Test listing files in a bucket."""
        print(f"\n📂 Testing file listing in bucket: {self.test_bucket_name}")
        async with session.get(f"{self.dashboard_url}/api/buckets/{self.test_bucket_name}") as resp:
            if resp.status == 200:
                data = await resp.json()
                files = data.get('files', [])
                print(f"   ✅ Successfully listed {len(files)} files")
                for file_info in files:
                    print(f"      - {file_info.get('name', 'Unknown')} ({file_info.get('size', 0)} bytes)")
            else:
                print(f"   ❌ Failed to list bucket files: {resp.status}")
                print(f"      Response: {await resp.text()}")
    
    async def test_download_file(self, session):
        """Test downloading a file from the bucket."""
        print(f"\n⬇️  Testing file download from bucket: {self.test_bucket_name}")
        async with session.get(f"{self.dashboard_url}/api/buckets/{self.test_bucket_name}/download/test-file.txt") as resp:
            if resp.status == 200:
                content = await resp.read()
                downloaded_content = content.decode('utf-8')
                if downloaded_content == self.test_file_content:
                    print(f"   ✅ Successfully downloaded file with correct content")
                else:
                    print(f"   ⚠️  Downloaded file but content mismatch:")
                    print(f"      Expected: {self.test_file_content}")
                    print(f"      Got: {downloaded_content}")
            else:
                print(f"   ❌ Failed to download file: {resp.status}")
                print(f"      Response: {await resp.text()}")
    
    async def test_delete_bucket(self, session):
        """Test deleting a bucket."""
        print(f"\n🗑️  Testing bucket deletion: {self.test_bucket_name}")
        async with session.delete(f"{self.dashboard_url}/api/buckets/{self.test_bucket_name}") as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"   ✅ Successfully deleted bucket: {result}")
            else:
                print(f"   ❌ Failed to delete bucket: {resp.status}")
                print(f"      Response: {await resp.text()}")

async def main():
    """Run the comprehensive bucket functionality test."""
    tester = BucketFunctionalityTester()
    await tester.test_bucket_operations()

if __name__ == "__main__":
    anyio.run(main)
