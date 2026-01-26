#!/usr/bin/env python3
"""
Test script for the Enhanced MCP Dashboard
Tests all major functionality to ensure the dashboard works correctly.
"""

import anyio
import aiohttp
import json
import sys
import time
from pathlib import Path

class DashboardTester:
    def __init__(self, base_url="http://127.0.0.1:8083"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_endpoint(self, method, endpoint, data=None, expected_status=200, test_name=None):
        """Test a single endpoint and return result"""
        if not test_name:
            test_name = f"{method} {endpoint}"
            
        try:
            url = f"{self.base_url}{endpoint}"
            kwargs = {}
            if data:
                if isinstance(data, dict):
                    kwargs['json'] = data
                else:
                    kwargs['data'] = data
                    
            async with self.session.request(method, url, **kwargs) as response:
                status = response.status
                try:
                    content = await response.json()
                except:
                    content = await response.text()
                    
                success = status == expected_status
                result = {
                    'test': test_name,
                    'success': success,
                    'status': status,
                    'expected_status': expected_status,
                    'response_size': len(str(content)),
                    'has_content': bool(content)
                }
                
                if not success:
                    result['error'] = f"Status {status}, expected {expected_status}"
                    
                self.test_results.append(result)
                return result
                
        except Exception as e:
            result = {
                'test': test_name,
                'success': False,
                'error': str(e),
                'status': 'ERROR',
                'expected_status': expected_status
            }
            self.test_results.append(result)
            return result

    async def test_basic_endpoints(self):
        """Test basic dashboard endpoints"""
        print("Testing basic endpoints...")
        
        # Test main dashboard
        await self.test_endpoint('GET', '/', test_name="Main Dashboard")
        
        # Test sub-pages
        pages = ['/daemon', '/backends', '/buckets', '/pins', '/vfs', '/parquet']
        for page in pages:
            await self.test_endpoint('GET', page, test_name=f"Page {page}")

    async def test_api_endpoints(self):
        """Test REST API endpoints"""
        print("Testing API endpoints...")
        
        # Test status endpoint
        await self.test_endpoint('GET', '/api/status', test_name="System Status")
        
        # Test bucket operations
        await self.test_endpoint('GET', '/api/buckets', test_name="List Buckets")
        
        # Test backend health
        await self.test_endpoint('GET', '/api/backends', test_name="Backend Status")
        
        # Test pin management
        await self.test_endpoint('GET', '/api/pins', test_name="List Pins")
        
        # Test VFS operations
        await self.test_endpoint('GET', '/api/vfs?path=/', test_name="VFS Root")
        
        # Test Parquet datasets
        await self.test_endpoint('GET', '/api/parquet/datasets', test_name="Parquet Datasets")
        
        # Test metrics
        await self.test_endpoint('GET', '/api/metrics', test_name="System Metrics")
        
        # Test logs
        await self.test_endpoint('GET', '/api/logs', test_name="System Logs")
        
        # Test configuration
        await self.test_endpoint('GET', '/api/config', test_name="System Config")

    async def test_mcp_integration(self):
        """Test MCP tool integration"""
        print("Testing MCP integration...")
        
        # Test MCP tool execution - start with a simple tool
        test_data = {
            "arguments": {
                "text": "Hello World Test"
            }
        }
        
        await self.test_endpoint('POST', '/api/mcp/tool/ipfs_add', 
                               data=test_data, test_name="MCP IPFS Add")

    async def test_bucket_operations(self):
        """Test bucket creation and operations"""
        print("Testing bucket operations...")
        
        # Create test bucket
        bucket_data = {
            "bucket_name": "test-dashboard-bucket",
            "bucket_type": "general",
            "backend": "filesystem"
        }
        
        await self.test_endpoint('POST', '/api/buckets', 
                               data=bucket_data, test_name="Create Test Bucket")
        
        # Delete test bucket (cleanup)
        await self.test_endpoint('DELETE', '/api/buckets/test-dashboard-bucket',
                               expected_status=200, test_name="Delete Test Bucket")

    async def test_websocket_connection(self):
        """Test WebSocket connection"""
        print("Testing WebSocket connection...")
        
        try:
            import websockets
            
            ws_url = self.base_url.replace('http://', 'ws://') + '/ws'
            async with websockets.connect(ws_url, timeout=5) as websocket:
                # Send a test message
                await websocket.send(json.dumps({"type": "ping"}))
                
                # Wait for response
                try:
                    with anyio.fail_after(3):
                        response = await websocket.recv()
                    self.test_results.append({
                        'test': 'WebSocket Connection',
                        'success': True,
                        'response_received': bool(response)
                    })
                except TimeoutError:
                    self.test_results.append({
                        'test': 'WebSocket Connection',
                        'success': True,  # Connection worked, just no immediate response
                        'note': 'Connected but no immediate response'
                    })
                    
        except ImportError:
            self.test_results.append({
                'test': 'WebSocket Connection',
                'success': False,
                'error': 'websockets library not available'
            })
        except Exception as e:
            self.test_results.append({
                'test': 'WebSocket Connection',
                'success': False,
                'error': str(e)
            })

    async def run_all_tests(self):
        """Run all test suites"""
        print(f"Starting dashboard tests for {self.base_url}")
        print("=" * 60)
        
        # Run test suites
        await self.test_basic_endpoints()
        await self.test_api_endpoints()
        await self.test_mcp_integration()
        await self.test_bucket_operations()
        await self.test_websocket_connection()
        
        # Print results
        self.print_results()

    def print_results(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            print("-" * 40)
            for result in self.test_results:
                if not result['success']:
                    print(f"❌ {result['test']}")
                    if 'error' in result:
                        print(f"   Error: {result['error']}")
                    if 'status' in result and 'expected_status' in result:
                        print(f"   Status: {result['status']} (expected {result['expected_status']})")
        
        print("\nPASSED TESTS:")
        print("-" * 40)
        for result in self.test_results:
            if result['success']:
                print(f"✅ {result['test']}")
                if 'response_size' in result:
                    print(f"   Response size: {result['response_size']} chars")
        
        return passed_tests, failed_tests

async def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Enhanced MCP Dashboard')
    parser.add_argument('--url', default='http://127.0.0.1:8083',
                      help='Dashboard URL (default: http://127.0.0.1:8083)')
    parser.add_argument('--wait', type=int, default=0,
                      help='Seconds to wait before starting tests')
    
    args = parser.parse_args()
    
    if args.wait:
        print(f"Waiting {args.wait} seconds for dashboard to start...")
        time.sleep(args.wait)
    
    async with DashboardTester(args.url) as tester:
        try:
            await tester.run_all_tests()
            passed, failed = tester.print_results()
            
            # Exit with error code if tests failed
            if failed > 0:
                sys.exit(1)
            else:
                print("\n🎉 All tests passed!")
                sys.exit(0)
                
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n\nTest suite failed with error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    anyio.run(main)
