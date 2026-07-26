#!/usr/bin/env python3
"""
Comprehensive Multi-Processing IPFS Kit Testing Script.

This script will:
1. Start the multi-processing daemon
2. Test CLI tools with various operations
3. Monitor logs and performance
4. Verify everything works correctly
5. Provide detailed status reports
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import signal

# Rich for beautiful output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.live import Live
    from rich.text import Text
    from rich.columns import Columns
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# HTTP client for testing
import httpx

console = Console() if RICH_AVAILABLE else None

class IPFSKitTestSuite:
    """
    Comprehensive test suite for multi-processing IPFS Kit.
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.daemon_url = "http://127.0.0.1:9999"
        self.mcp_url = "http://127.0.0.1:8080"
        
        # Process tracking
        self.daemon_process = None
        self.mcp_process = None
        
        # Test results
        self.test_results = {}
        self.test_start_time = None
        
        # Log monitoring
        self.log_entries = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ipfs_kit_test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def print_banner(self):
        """Print test suite banner."""
        if console:
            banner = Panel(
                f"""[bold cyan]🧪 IPFS KIT MULTI-PROCESSING TEST SUITE[/bold cyan]

🔍 [bold]Test Scope[/bold]
• Multi-processing daemon startup and health
• CLI tool functionality and performance
• Batch operations and concurrent requests
• Error handling and recovery
• Log monitoring and analysis
• Performance benchmarking

📊 [bold]Testing Strategy[/bold]
• Start daemon with controlled logging
• Execute CLI operations systematically
• Monitor performance and resource usage
• Verify correct operation under load
• Check error handling and recovery

🎯 [bold]Success Criteria[/bold]
• Daemon starts successfully with workers
• CLI tools connect and operate correctly
• Batch operations complete successfully
• Performance meets expectations
• No critical errors in logs""",
                title="🚀 Multi-Processing Test Suite",
                border_style="blue",
                padding=(1, 2)
            )
            console.print(banner)
        else:
            print("=" * 80)
            print("🧪 IPFS KIT MULTI-PROCESSING TEST SUITE")
            print("=" * 80)
    
    def log_test_event(self, message: str, level: str = "info"):
        """Log test event with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_entries.append({"timestamp": timestamp, "message": message, "level": level})
        
        if console:
            if level == "success":
                console.print(f"✅ {log_entry}", style="green")
            elif level == "error":
                console.print(f"❌ {log_entry}", style="red")
            elif level == "warning":
                console.print(f"⚠️ {log_entry}", style="yellow")
            else:
                console.print(f"ℹ️ {log_entry}", style="blue")
        else:
            print(log_entry)
        
        self.logger.info(f"{level.upper()}: {message}")
    
    async def start_daemon_with_monitoring(self) -> bool:
        """Start multi-processing daemon with log monitoring."""
        self.log_test_event("Starting multi-processing daemon...")
        
        try:
            # Create a modified launcher script for testing
            launcher_script = self.base_dir / "test_daemon_launcher.py"
            
            launcher_content = f"""#!/usr/bin/env python3
import sys
import os
import asyncio
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daemon_test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("🚀 Starting test daemon...")
        
        # Import the daemon here to avoid import issues
        from mcp.ipfs_kit.daemon.multi_process_daemon import MultiProcessIPFSKitDaemon
        
        daemon = MultiProcessIPFSKitDaemon(
            host="127.0.0.1",
            port=9999,
            config_dir="/tmp/ipfs_kit_test_config",
            data_dir=str(Path.home() / ".ipfs_kit"),
            num_workers=4
        )
        
        logger.info("✅ Daemon initialized, starting server...")
        await daemon.start()
        
    except Exception as e:
        logger.error(f"❌ Daemon startup failed: {{e}}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(main())
"""
            
            with open(launcher_script, 'w') as f:
                f.write(launcher_content)
            
            launcher_script.chmod(0o755)
            
            # Start daemon process
            self.daemon_process = subprocess.Popen(
                [sys.executable, str(launcher_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.log_test_event("Daemon process started, waiting for initialization...")
            
            # Wait for daemon to start and test connectivity
            max_attempts = 30
            for attempt in range(max_attempts):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"{self.daemon_url}/health/fast", timeout=5)
                        if response.status_code == 200:
                            health_data = response.json()
                            self.log_test_event(f"Daemon started successfully! Workers: {health_data.get('workers', 'N/A')}", "success")
                            return True
                except Exception:
                    pass
                
                await asyncio.sleep(2)
                self.log_test_event(f"Waiting for daemon startup... (attempt {attempt + 1}/{max_attempts})")
            
            self.log_test_event("Daemon failed to start within timeout", "error")
            return False
            
        except Exception as e:
            self.log_test_event(f"Failed to start daemon: {e}", "error")
            return False
    
    async def test_daemon_health(self) -> Dict[str, Any]:
        """Test daemon health endpoints."""
        self.log_test_event("Testing daemon health endpoints...")
        
        results = {}
        
        try:
            async with httpx.AsyncClient() as client:
                # Test fast health check
                self.log_test_event("Testing fast health check...")
                response = await client.get(f"{self.daemon_url}/health/fast", timeout=10)
                
                if response.status_code == 200:
                    fast_health = response.json()
                    results['fast_health'] = fast_health
                    self.log_test_event(f"Fast health check: {fast_health.get('workers', 0)} workers, {fast_health.get('active_operations', 0)} active ops", "success")
                else:
                    results['fast_health'] = {"error": f"HTTP {response.status_code}"}
                    self.log_test_event(f"Fast health check failed: HTTP {response.status_code}", "error")
                
                # Test comprehensive health check
                self.log_test_event("Testing comprehensive health check...")
                response = await client.get(f"{self.daemon_url}/health", timeout=30)
                
                if response.status_code == 200:
                    full_health = response.json()
                    results['full_health'] = full_health
                    self.log_test_event("Comprehensive health check completed", "success")
                else:
                    results['full_health'] = {"error": f"HTTP {response.status_code}"}
                    self.log_test_event(f"Comprehensive health check failed: HTTP {response.status_code}", "error")
                
                # Test performance metrics
                self.log_test_event("Testing performance metrics...")
                response = await client.get(f"{self.daemon_url}/performance", timeout=10)
                
                if response.status_code == 200:
                    perf_data = response.json()
                    results['performance'] = perf_data
                    self.log_test_event(f"Performance metrics: {perf_data.get('workers', 0)} workers, {perf_data.get('total_operations', 0)} total ops", "success")
                else:
                    results['performance'] = {"error": f"HTTP {response.status_code}"}
                    self.log_test_event(f"Performance metrics failed: HTTP {response.status_code}", "error")
                
        except Exception as e:
            self.log_test_event(f"Health check error: {e}", "error")
            results['error'] = str(e)
        
        return results
    
    async def test_cli_operations(self) -> Dict[str, Any]:
        """Test CLI operations."""
        self.log_test_event("Testing CLI operations...")
        
        results = {}
        
        try:
            # Test health check via CLI simulation
            self.log_test_event("Testing CLI health check...")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.daemon_url}/health/fast", timeout=10)
                if response.status_code == 200:
                    results['cli_health'] = response.json()
                    self.log_test_event("CLI health check successful", "success")
                else:
                    results['cli_health'] = {"error": f"HTTP {response.status_code}"}
                    self.log_test_event("CLI health check failed", "error")
            
            # Test pin listing via CLI simulation
            self.log_test_event("Testing CLI pin listing...")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.daemon_url}/pins", timeout=30)
                if response.status_code == 200:
                    pin_data = response.json()
                    results['cli_pins'] = pin_data
                    self.log_test_event(f"Pin listing successful: {len(pin_data.get('pins', []))} pins found", "success")
                else:
                    results['cli_pins'] = {"error": f"HTTP {response.status_code}"}
                    self.log_test_event("Pin listing failed", "error")
            
        except Exception as e:
            self.log_test_event(f"CLI operations error: {e}", "error")
            results['error'] = str(e)
        
        return results
    
    async def test_batch_operations(self) -> Dict[str, Any]:
        """Test batch operations."""
        self.log_test_event("Testing batch operations...")
        
        results = {}
        
        try:
            # Create test batch operations
            test_operations = [
                {"operation": "add", "cid": f"QmTest{'0'*40}{i:06d}"}
                for i in range(10)  # Small batch for testing
            ]
            
            self.log_test_event(f"Testing batch of {len(test_operations)} operations...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.daemon_url}/pins/batch",
                    json=test_operations,
                    timeout=120
                )
                
                if response.status_code == 200:
                    batch_result = response.json()
                    results['batch_operations'] = batch_result
                    
                    successful = batch_result.get('successful', 0)
                    failed = batch_result.get('failed', 0)
                    total_ops = batch_result.get('total_operations', 0)
                    
                    self.log_test_event(f"Batch operations completed: {successful}/{total_ops} successful, {failed} failed", "success")
                else:
                    results['batch_operations'] = {"error": f"HTTP {response.status_code}"}
                    self.log_test_event(f"Batch operations failed: HTTP {response.status_code}", "error")
                
        except Exception as e:
            self.log_test_event(f"Batch operations error: {e}", "error")
            results['error'] = str(e)
        
        return results
    
    async def test_concurrent_requests(self) -> Dict[str, Any]:
        """Test concurrent request handling."""
        self.log_test_event("Testing concurrent request handling...")
        
        results = {}
        
        try:
            concurrency_levels = [1, 5, 10]
            
            for concurrency in concurrency_levels:
                self.log_test_event(f"Testing {concurrency} concurrent requests...")
                
                async with httpx.AsyncClient() as client:
                    start_time = time.time()
                    
                    async def make_request():
                        try:
                            response = await client.get(f"{self.daemon_url}/health/fast", timeout=10)
                            return response.status_code == 200
                        except Exception:
                            return False
                    
                    # Execute concurrent requests
                    tasks = [make_request() for _ in range(concurrency)]
                    request_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    total_time = time.time() - start_time
                    successful = sum(1 for r in request_results if r is True)
                    
                    results[f'concurrency_{concurrency}'] = {
                        'total_requests': concurrency,
                        'successful_requests': successful,
                        'total_time': total_time,
                        'success_rate': successful / concurrency * 100
                    }
                    
                    self.log_test_event(f"Concurrency {concurrency}: {successful}/{concurrency} successful ({successful/concurrency*100:.1f}%)", "success")
                
        except Exception as e:
            self.log_test_event(f"Concurrent request test error: {e}", "error")
            results['error'] = str(e)
        
        return results
    
    async def monitor_daemon_logs(self, duration: int = 30):
        """Monitor daemon logs for errors."""
        self.log_test_event(f"Monitoring daemon logs for {duration} seconds...")
        
        log_file = Path("daemon_test.log")
        if not log_file.exists():
            self.log_test_event("Daemon log file not found", "warning")
            return
        
        initial_size = log_file.stat().st_size
        
        await asyncio.sleep(duration)
        
        try:
            with open(log_file, 'r') as f:
                f.seek(initial_size)
                new_logs = f.read()
            
            if new_logs:
                lines = new_logs.strip().split('\n')
                error_count = len([line for line in lines if 'ERROR' in line.upper()])
                warning_count = len([line for line in lines if 'WARNING' in line.upper()])
                
                self.log_test_event(f"Log monitoring complete: {len(lines)} new lines, {error_count} errors, {warning_count} warnings")
                
                if error_count > 0:
                    self.log_test_event("Errors found in daemon logs", "warning")
                    # Show recent errors
                    for line in lines[-5:]:
                        if 'ERROR' in line.upper():
                            self.log_test_event(f"ERROR: {line.split('ERROR')[-1].strip()}", "error")
            else:
                self.log_test_event("No new log entries found", "info")
                
        except Exception as e:
            self.log_test_event(f"Log monitoring error: {e}", "error")
    
    def display_test_summary(self):
        """Display comprehensive test summary."""
        if console:
            console.print("\n🏆 TEST SUITE SUMMARY", style="bold green")
            
            # Create summary table
            summary_table = Table(title="📊 Test Results Summary")
            summary_table.add_column("Test Category", style="cyan")
            summary_table.add_column("Status", style="green")
            summary_table.add_column("Details", style="blue")
            
            for test_name, result in self.test_results.items():
                if isinstance(result, dict) and 'error' not in result:
                    status = "✅ PASS"
                    details = "Completed successfully"
                elif isinstance(result, dict) and 'error' in result:
                    status = "❌ FAIL"
                    details = f"Error: {result['error']}"
                else:
                    status = "✅ PASS"
                    details = "Completed"
                
                summary_table.add_row(test_name.replace('_', ' ').title(), status, details)
            
            console.print(summary_table)
            
            # Show performance summary
            if 'daemon_health' in self.test_results:
                health_data = self.test_results['daemon_health']
                if 'performance' in health_data:
                    perf = health_data['performance']
                    
                    perf_panel = Panel(
                        f"""[bold blue]📊 Performance Summary[/bold blue]

• Workers: {perf.get('workers', 'N/A')}
• Total Operations: {perf.get('total_operations', 0)}
• Active Operations: {perf.get('active_operations', 0)}
• CPU Count: {perf.get('cpu_count', 'N/A')}""",
                        border_style="blue"
                    )
                    console.print(perf_panel)
            
        else:
            print("\n🏆 TEST SUITE SUMMARY")
            print("=" * 50)
            for test_name, result in self.test_results.items():
                status = "PASS" if not (isinstance(result, dict) and 'error' in result) else "FAIL"
                print(f"  {test_name}: {status}")
    
    async def cleanup(self):
        """Clean up test processes and files."""
        self.log_test_event("Cleaning up test environment...")
        
        # Stop daemon process
        if self.daemon_process:
            try:
                self.daemon_process.terminate()
                await asyncio.sleep(2)
                if self.daemon_process.poll() is None:
                    self.daemon_process.kill()
                self.log_test_event("Daemon process stopped", "success")
            except Exception as e:
                self.log_test_event(f"Error stopping daemon: {e}", "error")
        
        # Clean up test files
        test_files = [
            "test_daemon_launcher.py",
            "daemon_test.log",
            "ipfs_kit_test.log"
        ]
        
        for file_name in test_files:
            file_path = Path(file_name)
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.log_test_event(f"Cleaned up {file_name}")
                except Exception as e:
                    self.log_test_event(f"Error cleaning {file_name}: {e}", "warning")
    
    async def run_comprehensive_test(self):
        """Run the complete test suite."""
        self.test_start_time = time.time()
        
        try:
            # Start daemon
            if not await self.start_daemon_with_monitoring():
                self.log_test_event("Cannot start daemon, aborting tests", "error")
                return False
            
            # Wait for daemon to fully initialize
            await asyncio.sleep(5)
            
            # Run health tests
            self.log_test_event("Running health tests...")
            self.test_results['daemon_health'] = await self.test_daemon_health()
            
            # Run CLI tests
            self.log_test_event("Running CLI tests...")
            self.test_results['cli_operations'] = await self.test_cli_operations()
            
            # Run batch operation tests
            self.log_test_event("Running batch operation tests...")
            self.test_results['batch_operations'] = await self.test_batch_operations()
            
            # Run concurrent request tests
            self.log_test_event("Running concurrent request tests...")
            self.test_results['concurrent_requests'] = await self.test_concurrent_requests()
            
            # Monitor logs
            await self.monitor_daemon_logs(duration=10)
            
            # Display summary
            total_time = time.time() - self.test_start_time
            self.log_test_event(f"All tests completed in {total_time:.2f} seconds", "success")
            
            self.display_test_summary()
            
            return True
            
        except KeyboardInterrupt:
            self.log_test_event("Test suite interrupted by user", "warning")
            return False
        except Exception as e:
            self.log_test_event(f"Test suite error: {e}", "error")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test execution."""
    test_suite = IPFSKitTestSuite()
    
    try:
        test_suite.print_banner()
        
        success = await test_suite.run_comprehensive_test()
        
        if success:
            if console:
                console.print("\n🎉 Test suite completed successfully!", style="bold green")
            else:
                print("\n🎉 Test suite completed successfully!")
        else:
            if console:
                console.print("\n❌ Test suite failed", style="bold red")
            else:
                print("\n❌ Test suite failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        if console:
            console.print("\n🛑 Test suite interrupted", style="yellow")
        else:
            print("\n🛑 Test suite interrupted")
    except Exception as e:
        if console:
            console.print(f"\n❌ Test suite error: {e}", style="red")
        else:
            print(f"\n❌ Test suite error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🧪 Starting IPFS Kit Multi-Processing Test Suite...")
    print("📋 This will test daemon startup, CLI operations, and monitor logs")
    print("=" * 80)
    
    asyncio.run(main())
