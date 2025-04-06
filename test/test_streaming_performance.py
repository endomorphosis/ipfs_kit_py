import unittest
import asyncio
import os
import time
import tempfile
import json
import shutil
import pytest
import io
import random
from unittest.mock import patch, MagicMock, AsyncMock
from statistics import mean, median, stdev

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.tiered_cache import TieredCacheManager


class TestStreamingPerformance(unittest.TestCase):
    """Test performance metrics for streaming functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.api = IPFSSimpleAPI()
        
        # Create test files of different sizes
        self.test_dir = tempfile.mkdtemp()
        self.test_files = {}
        
        # 1KB file
        self.test_files["small"] = os.path.join(self.test_dir, "small.txt")
        with open(self.test_files["small"], "wb") as f:
            f.write(b"X" * 1024)
        
        # 1MB file
        self.test_files["medium"] = os.path.join(self.test_dir, "medium.txt")
        with open(self.test_files["medium"], "wb") as f:
            f.write(b"Y" * (1024 * 1024))
        
        # 10MB file
        self.test_files["large"] = os.path.join(self.test_dir, "large.txt")
        with open(self.test_files["large"], "wb") as f:
            f.write(b"Z" * (10 * 1024 * 1024))
        
        # Mock CIDs for testing
        self.test_cids = {
            "small": "QmSmallTestCID123",
            "medium": "QmMediumTestCID456",
            "large": "QmLargeTestCID789"
        }
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _read_file(self, path):
        """Read a file into memory."""
        with open(path, "rb") as f:
            return f.read()
    
    @patch.object(IPFSSimpleAPI, 'cat')
    def test_stream_media_performance(self, mock_cat):
        """Test performance of streaming media with different chunk sizes."""
        results = {}
        
        for file_size in ["small", "medium", "large"]:
            # Read the test file
            content = self._read_file(self.test_files[file_size])
            
            # Setup mock
            mock_cat.return_value = content
            
            size_results = {}
            
            # Test with different chunk sizes
            for chunk_size in [1024, 4096, 16384, 65536, 262144, 1048576]:
                # Skip large chunk sizes for small files
                if len(content) <= chunk_size and file_size != "small":
                    continue
                
                # Measure time for streaming
                start_time = time.time()
                chunks = list(self.api.stream_media(self.test_cids[file_size], chunk_size=chunk_size))
                end_time = time.time()
                
                # Calculate metrics
                duration = end_time - start_time
                throughput = len(content) / duration / (1024 * 1024)  # MB/s
                chunk_count = len(chunks)
                
                size_results[chunk_size] = {
                    "duration_seconds": duration,
                    "throughput_mbps": throughput,
                    "chunk_count": chunk_count
                }
            
            results[file_size] = size_results
        
        # Print performance summary
        print("\nStreaming Performance Results:")
        print("==============================")
        
        for file_size, size_results in results.items():
            print(f"\n{file_size.capitalize()} File ({os.path.getsize(self.test_files[file_size]) / 1024:.1f} KB):")
            print("-" * 50)
            print(f"{'Chunk Size':>12} | {'Duration (s)':>12} | {'Throughput (MB/s)':>18} | {'Chunk Count':>12}")
            print("-" * 50)
            
            for chunk_size, metrics in size_results.items():
                print(f"{chunk_size/1024:.1f} KB".rjust(12), " | ", 
                      f"{metrics['duration_seconds']:.6f}".rjust(12), " | ",
                      f"{metrics['throughput_mbps']:.6f}".rjust(18), " | ",
                      f"{metrics['chunk_count']}".rjust(12))
        
        # Assert that larger chunk sizes generally provide better throughput
        # for large files (but we allow for system variability)
        if "large" in results and 1048576 in results["large"] and 1024 in results["large"]:
            self.assertGreaterEqual(
                results["large"][1048576]["throughput_mbps"], 
                results["large"][1024]["throughput_mbps"] * 0.8,  # Allow 20% variance
                "Larger chunk sizes should generally provide better throughput for large files"
            )
    
    @patch.object(IPFSSimpleAPI, 'add')
    def test_stream_to_ipfs_performance(self, mock_add):
        """Test performance of streaming to IPFS with different chunk sizes."""
        results = {}
        
        for file_size in ["small", "medium", "large"]:
            # Read the test file
            content = self._read_file(self.test_files[file_size])
            
            # Setup mock
            mock_add.return_value = {"Hash": self.test_cids[file_size]}
            
            size_results = {}
            
            # Test with different chunk sizes
            for chunk_size in [1024, 4096, 16384, 65536, 262144, 1048576]:
                # Skip large chunk sizes for small files
                if len(content) <= chunk_size and file_size != "small":
                    continue
                
                # Measure time for streaming upload
                start_time = time.time()
                file_obj = io.BytesIO(content)
                result = self.api.stream_to_ipfs(file_obj, chunk_size=chunk_size)
                end_time = time.time()
                
                # Calculate metrics
                duration = end_time - start_time
                throughput = len(content) / duration / (1024 * 1024)  # MB/s
                
                size_results[chunk_size] = {
                    "duration_seconds": duration,
                    "throughput_mbps": throughput
                }
            
            results[file_size] = size_results
        
        # Print performance summary
        print("\nUpload Streaming Performance Results:")
        print("====================================")
        
        for file_size, size_results in results.items():
            print(f"\n{file_size.capitalize()} File ({os.path.getsize(self.test_files[file_size]) / 1024:.1f} KB):")
            print("-" * 50)
            print(f"{'Chunk Size':>12} | {'Duration (s)':>12} | {'Throughput (MB/s)':>18}")
            print("-" * 50)
            
            for chunk_size, metrics in size_results.items():
                print(f"{chunk_size/1024:.1f} KB".rjust(12), " | ", 
                      f"{metrics['duration_seconds']:.6f}".rjust(12), " | ",
                      f"{metrics['throughput_mbps']:.6f}".rjust(18))


@pytest.mark.asyncio
class TestAsyncStreamingPerformance:
    """Test performance of asynchronous streaming."""
    
    @pytest.fixture
    async def setup(self):
        """Set up test environment."""
        api = IPFSSimpleAPI()
        
        # Create test files of different sizes
        test_dir = tempfile.mkdtemp()
        test_files = {}
        
        # 1KB file
        test_files["small"] = os.path.join(test_dir, "small.txt")
        with open(test_files["small"], "wb") as f:
            f.write(b"X" * 1024)
        
        # 1MB file
        test_files["medium"] = os.path.join(test_dir, "medium.txt")
        with open(test_files["medium"], "wb") as f:
            f.write(b"Y" * (1024 * 1024))
        
        # 10MB file
        test_files["large"] = os.path.join(test_dir, "large.txt")
        with open(test_files["large"], "wb") as f:
            f.write(b"Z" * (10 * 1024 * 1024))
        
        # Mock CIDs for testing
        test_cids = {
            "small": "QmSmallTestCID123",
            "medium": "QmMediumTestCID456",
            "large": "QmLargeTestCID789"
        }
        
        yield api, test_files, test_cids, test_dir
        
        # Cleanup
        shutil.rmtree(test_dir)
    
    def _read_file(self, path):
        """Read a file into memory."""
        with open(path, "rb") as f:
            return f.read()
    
    @patch.object(IPFSSimpleAPI, 'cat')
    async def test_stream_media_async_performance(self, mock_cat, setup):
        """Test performance of async streaming media with different chunk sizes."""
        api, test_files, test_cids, _ = await setup
        results = {}
        
        for file_size in ["small", "medium", "large"]:
            # Read the test file
            content = self._read_file(test_files[file_size])
            
            # Setup mock
            mock_cat.return_value = content
            
            size_results = {}
            
            # Test with different chunk sizes
            for chunk_size in [1024, 4096, 16384, 65536, 262144, 1048576]:
                # Skip large chunk sizes for small files
                if len(content) <= chunk_size and file_size != "small":
                    continue
                
                # Measure time for streaming
                start_time = time.time()
                chunks = []
                async for chunk in api.stream_media_async(test_cids[file_size], chunk_size=chunk_size):
                    chunks.append(chunk)
                end_time = time.time()
                
                # Calculate metrics
                duration = end_time - start_time
                throughput = len(content) / duration / (1024 * 1024)  # MB/s
                chunk_count = len(chunks)
                
                size_results[chunk_size] = {
                    "duration_seconds": duration,
                    "throughput_mbps": throughput,
                    "chunk_count": chunk_count
                }
            
            results[file_size] = size_results
        
        # Print performance summary
        print("\nAsync Streaming Performance Results:")
        print("===================================")
        
        for file_size, size_results in results.items():
            print(f"\n{file_size.capitalize()} File ({os.path.getsize(test_files[file_size]) / 1024:.1f} KB):")
            print("-" * 50)
            print(f"{'Chunk Size':>12} | {'Duration (s)':>12} | {'Throughput (MB/s)':>18} | {'Chunk Count':>12}")
            print("-" * 50)
            
            for chunk_size, metrics in size_results.items():
                print(f"{chunk_size/1024:.1f} KB".rjust(12), " | ", 
                      f"{metrics['duration_seconds']:.6f}".rjust(12), " | ",
                      f"{metrics['throughput_mbps']:.6f}".rjust(18), " | ",
                      f"{metrics['chunk_count']}".rjust(12))


class TestCacheIntegrationWithStreaming(unittest.TestCase):
    """Test integration of streaming with the tiered cache system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a TieredCacheManager with controlled settings
        self.cache_config = {
            'memory_cache_size': 10 * 1024 * 1024,  # 10MB
            'local_cache_size': 50 * 1024 * 1024,   # 50MB
            'local_cache_path': tempfile.mkdtemp(),
            'max_item_size': 5 * 1024 * 1024,       # 5MB
            'min_access_count': 2
        }
        
        # Initialize API with this cache
        self.api = IPFSSimpleAPI()
        
        # Create test files
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "cache_test.txt")
        self.test_content = b"X" * (3 * 1024 * 1024)  # 3MB
        
        with open(self.test_file, "wb") as f:
            f.write(self.test_content)
        
        # Mock CID
        self.test_cid = "QmCacheTestCID"
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.cache_config['local_cache_path'])
    
    @patch.object(IPFSSimpleAPI, 'cat')
    @patch.object(TieredCacheManager, 'get')
    @patch.object(TieredCacheManager, 'put')
    def test_streaming_with_cache(self, mock_put, mock_get, mock_cat):
        """Test that streaming properly integrates with the cache system."""
        # First access - cache miss
        mock_get.return_value = None
        mock_cat.return_value = self.test_content
        
        # Stream the content (first time - should miss cache)
        chunks1 = list(self.api.stream_media(self.test_cid, chunk_size=1024))
        
        # Verify content and cache interaction
        received_content1 = b''.join(chunks1)
        self.assertEqual(received_content1, self.test_content)
        
        # Verify cat was called (cache miss)
        mock_cat.assert_called_once()
        
        # Verify put was called to cache the content
        mock_put.assert_called_once()
        
        # Reset mocks for second access
        mock_cat.reset_mock()
        mock_put.reset_mock()
        
        # Second access - cache hit
        mock_get.return_value = self.test_content
        
        # Stream the content again (should hit cache)
        chunks2 = list(self.api.stream_media(self.test_cid, chunk_size=1024))
        
        # Verify content
        received_content2 = b''.join(chunks2)
        self.assertEqual(received_content2, self.test_content)
        
        # Verify cat was NOT called (cache hit)
        mock_cat.assert_not_called()
        
        # Verify put was NOT called again
        mock_put.assert_not_called()
    
    @patch.object(IPFSSimpleAPI, 'cat')
    def test_streaming_with_range_requests(self, mock_cat):
        """Test that streaming properly handles range requests with caching."""
        # Setup mock
        mock_cat.return_value = self.test_content
        
        # Define range parameters
        start_byte = 1000
        end_byte = 2000
        
        # Stream a range of the content
        chunks = list(self.api.stream_media(
            self.test_cid,
            chunk_size=1024,
            start_byte=start_byte,
            end_byte=end_byte
        ))
        
        # Verify we got only the requested range
        received_content = b''.join(chunks)
        self.assertEqual(received_content, self.test_content[start_byte:end_byte+1])
        
        # Verify cat was called
        mock_cat.assert_called_once()
        
        # Verify we got the right number of chunks
        # The range is 1001 bytes, so with 1024-byte chunks, we should get 1 or 2 chunks
        self.assertLessEqual(len(chunks), 2)
    
    @patch.object(IPFSSimpleAPI, 'cat')
    def test_streaming_with_different_chunk_sizes(self, mock_cat):
        """Test the impact of different chunk sizes on streaming performance."""
        # Setup mock
        mock_cat.return_value = self.test_content
        
        results = {}
        
        # Test with different chunk sizes
        for chunk_size in [512, 1024, 4096, 16384, 65536, 262144]:
            # Measure time for streaming
            start_time = time.time()
            chunks = list(self.api.stream_media(self.test_cid, chunk_size=chunk_size))
            end_time = time.time()
            
            # Calculate metrics
            duration = end_time - start_time
            throughput = len(self.test_content) / duration / (1024 * 1024)  # MB/s
            chunk_count = len(chunks)
            
            results[chunk_size] = {
                "duration_seconds": duration,
                "throughput_mbps": throughput,
                "chunk_count": chunk_count
            }
        
        # Print performance summary
        print("\nChunk Size Performance Comparison:")
        print("=================================")
        print(f"{'Chunk Size':>12} | {'Duration (s)':>12} | {'Throughput (MB/s)':>18} | {'Chunk Count':>12}")
        print("-" * 65)
        
        for chunk_size, metrics in results.items():
            print(f"{chunk_size/1024:.1f} KB".rjust(12), " | ", 
                  f"{metrics['duration_seconds']:.6f}".rjust(12), " | ",
                  f"{metrics['throughput_mbps']:.6f}".rjust(18), " | ",
                  f"{metrics['chunk_count']}".rjust(12))
        
        # Identify optimal chunk size based on throughput
        optimal_chunk_size = max(results.items(), key=lambda x: x[1]["throughput_mbps"])[0]
        print(f"\nOptimal chunk size for this content: {optimal_chunk_size/1024:.1f} KB")


if __name__ == "__main__":
    unittest.main()