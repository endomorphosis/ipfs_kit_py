#!/usr/bin/env python3
"""
Simple daemon test to identify startup issues.
"""

import asyncio
import sys
import time
from pathlib import Path
import subprocess
import signal
import os

# Rich for output
try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

class DaemonTester:
    """Test daemon startup and connectivity."""
    
    def __init__(self):
        self.daemon_process = None
        self.startup_logs = []
    
    def start_daemon_with_logging(self):
        """Start daemon and capture all output."""
        if console:
            console.print("🚀 Starting daemon with full logging...", style="blue")
        
        try:
            # Start daemon process
            self.daemon_process = subprocess.Popen([
                sys.executable, "-m", "mcp.ipfs_kit.daemon.multi_process_daemon",
                "--debug"
            ], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True,
            bufsize=1
            )
            
            return True
            
        except Exception as e:
            if console:
                console.print(f"❌ Failed to start daemon: {e}", style="red")
            return False
    
    def monitor_startup_logs(self, timeout=15):
        """Monitor daemon startup and capture logs."""
        if not self.daemon_process:
            return False
        
        if console:
            console.print(f"📋 Monitoring daemon startup (timeout: {timeout}s)...", style="blue")
        
        start_time = time.time()
        logs_captured = []
        
        try:
            while time.time() - start_time < timeout:
                if self.daemon_process.poll() is not None:
                    # Process ended
                    if console:
                        console.print("❌ Daemon process ended early", style="red")
                    break
                
                # Try to read a line with timeout
                try:
                    self.daemon_process.stdout.settimeout(1)
                    line = self.daemon_process.stdout.readline()
                    if line:
                        line = line.strip()
                        logs_captured.append(line)
                        
                        if console:
                            # Show important startup messages
                            if any(keyword in line.lower() for keyword in [
                                "starting", "initialized", "api server", "error", "failed"
                            ]):
                                console.print(f"📋 {line}", style="cyan")
                        
                        # Check for successful startup indicators
                        if "Starting high-performance API server" in line:
                            if console:
                                console.print("✅ API server starting!", style="green")
                        elif "Uvicorn running on" in line:
                            if console:
                                console.print("✅ Server is running!", style="green")
                            return True
                            
                except:
                    time.sleep(0.1)
                    continue
            
            # Timeout reached
            if console:
                console.print(f"⏱️ Startup monitoring timeout ({timeout}s)", style="yellow")
            
            return len(logs_captured) > 0
            
        except Exception as e:
            if console:
                console.print(f"❌ Error monitoring logs: {e}", style="red")
            return False
        finally:
            self.startup_logs = logs_captured
    
    def test_connectivity(self):
        """Test if daemon is responding."""
        if console:
            console.print("🔍 Testing daemon connectivity...", style="blue")
        
        import httpx
        
        try:
            # Quick connection test
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', 9999))
            sock.close()
            
            if result == 0:
                if console:
                    console.print("✅ Port 9999 is accepting connections", style="green")
                return True
            else:
                if console:
                    console.print("❌ Port 9999 is not accepting connections", style="red")
                return False
                
        except Exception as e:
            if console:
                console.print(f"❌ Connection test failed: {e}", style="red")
            return False
    
    def cleanup(self):
        """Clean up daemon process."""
        if self.daemon_process:
            try:
                if console:
                    console.print("🛑 Stopping daemon...", style="yellow")
                
                # Try graceful shutdown first
                self.daemon_process.terminate()
                
                # Wait up to 5 seconds for graceful shutdown
                try:
                    self.daemon_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    self.daemon_process.kill()
                    self.daemon_process.wait()
                
                if console:
                    console.print("✅ Daemon stopped", style="green")
                    
            except Exception as e:
                if console:
                    console.print(f"⚠️ Error stopping daemon: {e}", style="yellow")
    
    def display_startup_logs(self):
        """Display captured startup logs."""
        if not self.startup_logs:
            if console:
                console.print("📋 No startup logs captured", style="yellow")
            return
        
        if console:
            console.print(f"\n📋 Captured {len(self.startup_logs)} startup log lines:", style="blue")
            
            # Create table for logs
            logs_table = Table(title="🚀 Daemon Startup Logs", show_header=True)
            logs_table.add_column("Line", style="dim", width=6)
            logs_table.add_column("Log Message", style="white")
            
            for i, log in enumerate(self.startup_logs[-20:], 1):  # Show last 20 lines
                # Color code important messages
                if "error" in log.lower() or "failed" in log.lower():
                    style = "red"
                elif "warning" in log.lower():
                    style = "yellow"
                elif "starting" in log.lower() or "initialized" in log.lower():
                    style = "green"
                else:
                    style = "white"
                
                logs_table.add_row(str(i), log, style=style)
            
            console.print(logs_table)
        else:
            print("\n📋 Startup logs:")
            for i, log in enumerate(self.startup_logs, 1):
                print(f"{i:3d}: {log}")


async def main():
    """Run daemon testing."""
    tester = DaemonTester()
    
    if console:
        console.print("🧪 IPFS Kit Daemon Startup Test", style="bold blue")
        console.print("=" * 50, style="blue")
    
    try:
        # Start daemon
        if not tester.start_daemon_with_logging():
            return
        
        # Monitor startup
        startup_success = tester.monitor_startup_logs(timeout=20)
        
        # Test connectivity
        if startup_success:
            time.sleep(2)  # Give server time to fully start
            connectivity_success = tester.test_connectivity()
        else:
            connectivity_success = False
        
        # Display results
        tester.display_startup_logs()
        
        if console:
            if startup_success and connectivity_success:
                result_panel = Panel(
                    "✅ [bold green]Daemon started successfully![/bold green]\n"
                    "🌐 API server is running on http://127.0.0.1:9999\n"
                    "🔗 Port 9999 is accepting connections",
                    title="🎉 Test Results",
                    border_style="green"
                )
            elif startup_success:
                result_panel = Panel(
                    "⚠️ [bold yellow]Daemon started but connectivity failed[/bold yellow]\n"
                    "📋 Check the startup logs above for details\n"
                    "🔍 The daemon may still be initializing",
                    title="⚠️ Test Results",
                    border_style="yellow"
                )
            else:
                result_panel = Panel(
                    "❌ [bold red]Daemon startup failed[/bold red]\n"
                    "📋 Check the error logs above for details\n"
                    "🔧 Review configuration and dependencies",
                    title="❌ Test Results",
                    border_style="red"
                )
            
            console.print(result_panel)
        
        # Keep daemon running for a moment to allow manual testing
        if startup_success and connectivity_success:
            if console:
                console.print("\n⏱️ Keeping daemon running for 10 seconds for testing...", style="blue")
            await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        if console:
            console.print("\n🛑 Test interrupted by user", style="yellow")
    except Exception as e:
        if console:
            console.print(f"\n❌ Test error: {e}", style="red")
    finally:
        tester.cleanup()


if __name__ == "__main__":
    print("🧪 IPFS Kit Daemon Startup Test")
    print("=" * 40)
    
    asyncio.run(main())
