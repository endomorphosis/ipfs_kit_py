#!/usr/bin/env python3
"""
IPFS-Kit Continuous Validation Script
=====================================

This script can be run regularly to ensure IPFS-Kit remains functional
after any changes or updates. It performs essential health checks.

Usage:
    python continuous_validation.py           # Quick health check
    python continuous_validation.py --full    # Full validation
    python continuous_validation.py --ci      # CI-friendly output
"""

import anyio
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime

class HealthChecker:
    def __init__(self, ci_mode=False):
        self.ci_mode = ci_mode
        self.results = []
        
    def log(self, message, level="info"):
        if not self.ci_mode:
            timestamp = datetime.now().strftime('%H:%M:%S')
            icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
            icon = icons.get(level, "ℹ️")
            print(f"[{timestamp}] {icon} {message}")
    
    async def run_cmd(self, cmd, timeout=10):
        try:
            process = await anyio.open_process(
                cmd,
                stdout=anyio.subprocess.PIPE,
                stderr=anyio.subprocess.PIPE
            )
            with anyio.fail_after(timeout):
                stdout, stderr = await process.communicate()
            return process.returncode == 0, stdout.decode(), stderr.decode()
        except Exception as e:
            return False, "", str(e)
    
    def add_result(self, test_name, success, message="", duration=0.0):
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        
        if self.ci_mode:
            status = "PASS" if success else "FAIL"
            print(f"{test_name}: {status}")
        else:
            level = "success" if success else "error"
            self.log(f"{test_name}: {message}", level)
    
    async def test_cli_basic(self):
        """Test basic CLI functionality"""
        self.log("Testing CLI basic functionality...")
        
        start_time = time.time()
        success, stdout, stderr = await self.run_cmd([
            sys.executable, "-m", "ipfs_kit_py.cli", "--help"
        ])
        duration = time.time() - start_time
        
        if success and duration < 2.0:
            self.add_result("CLI_BASIC", True, f"Working in {duration:.2f}s", duration)
        else:
            self.add_result("CLI_BASIC", False, f"Failed or slow: {stderr}", duration)
    
    async def test_log_system(self):
        """Test log aggregation system"""
        self.log("Testing log aggregation system...")
        
        tests = [
            (["log", "--help"], "Log main command"),
            (["log", "show", "--help"], "Log show"),
            (["log", "stats", "--help"], "Log stats"),
            (["log", "clear", "--help"], "Log clear"),
            (["log", "export", "--help"], "Log export")
        ]
        
        passed = 0
        for cmd, name in tests:
            success, _, stderr = await self.run_cmd([
                sys.executable, "-m", "ipfs_kit_py.cli"
            ] + cmd)
            
            if success:
                passed += 1
        
        success_rate = passed / len(tests) if tests else 0
        if success_rate >= 0.8:
            self.add_result("LOG_SYSTEM", True, f"{passed}/{len(tests)} log commands working")
        else:
            self.add_result("LOG_SYSTEM", False, f"Only {passed}/{len(tests)} log commands working")
    
    async def test_core_commands(self):
        """Test core CLI commands"""
        self.log("Testing core commands...")
        
        commands = ["daemon", "config", "pin", "resource", "metrics", "mcp"]
        passed = 0
        
        for cmd in commands:
            success, _, _ = await self.run_cmd([
                sys.executable, "-m", "ipfs_kit_py.cli", cmd, "--help"
            ])
            if success:
                passed += 1
        
        success_rate = passed / len(commands) if commands else 0
        if success_rate >= 0.8:
            self.add_result("CORE_COMMANDS", True, f"{passed}/{len(commands)} commands working")
        else:
            self.add_result("CORE_COMMANDS", False, f"Only {passed}/{len(commands)} commands working")
    
    async def test_package_health(self):
        """Test package installation health"""
        self.log("Testing package health...")
        
        # Test import
        success, stdout, stderr = await self.run_cmd([
            sys.executable, "-c", "import ipfs_kit_py; print('OK')"
        ])
        
        if success:
            self.add_result("PACKAGE_IMPORT", True, "Package imports successfully")
        else:
            self.add_result("PACKAGE_IMPORT", False, f"Import failed: {stderr}")
    
    async def test_performance(self):
        """Test performance requirements"""
        self.log("Testing performance...")
        
        # Test help command speed (should be < 1 second)
        times = []
        for i in range(3):
            start_time = time.time()
            success, _, _ = await self.run_cmd([
                sys.executable, "-m", "ipfs_kit_py.cli", "--help"
            ])
            duration = time.time() - start_time
            times.append(duration)
        
        avg_time = sum(times) / len(times) if times else 0
        
        if avg_time < 1.0:
            self.add_result("PERFORMANCE", True, f"Average help time: {avg_time:.2f}s")
        else:
            self.add_result("PERFORMANCE", False, f"Too slow: {avg_time:.2f}s")
    
    async def run_quick_validation(self):
        """Run quick health checks"""
        if not self.ci_mode:
            self.log("Running quick validation checks...")
        
        await self.test_cli_basic()
        await self.test_log_system()
        await self.test_package_health()
        await self.test_performance()
    
    async def run_full_validation(self):
        """Run comprehensive validation"""
        if not self.ci_mode:
            self.log("Running full validation checks...")
        
        await self.test_cli_basic()
        await self.test_log_system()
        await self.test_core_commands()
        await self.test_package_health()
        await self.test_performance()
    
    def generate_report(self):
        """Generate validation report"""
        passed = len([r for r in self.results if r["success"]])
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        if self.ci_mode:
            # CI-friendly JSON output
            report = {
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": total - passed,
                    "success_rate": success_rate,
                    "status": "PASS" if success_rate >= 80 else "FAIL"
                },
                "tests": self.results,
                "timestamp": datetime.now().isoformat()
            }
            print(json.dumps(report, indent=2))
        else:
            # Human-readable output
            print("\n" + "="*60)
            print("IPFS-Kit Validation Report")
            print("="*60)
            print(f"Total Tests: {total}")
            print(f"Passed: {passed}")
            print(f"Failed: {total - passed}")
            print(f"Success Rate: {success_rate:.1f}%")
            
            if success_rate >= 90:
                print("🎉 Status: EXCELLENT")
            elif success_rate >= 80:
                print("✅ Status: GOOD") 
            elif success_rate >= 70:
                print("⚠️ Status: FAIR")
            else:
                print("❌ Status: POOR")
            
            # Show failed tests
            failed_tests = [r for r in self.results if not r["success"]]
            if failed_tests:
                print("\nFailed Tests:")
                for test in failed_tests:
                    print(f"  ❌ {test['test']}: {test['message']}")
        
        return success_rate >= 80

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS-Kit Continuous Validation")
    parser.add_argument("--full", action="store_true", help="Run full validation")
    parser.add_argument("--ci", action="store_true", help="CI-friendly output")
    
    args = parser.parse_args()
    
    checker = HealthChecker(ci_mode=args.ci)
    
    try:
        if args.full:
            await checker.run_full_validation()
        else:
            await checker.run_quick_validation()
        
        success = checker.generate_report()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        if not args.ci:
            print("\n⚠️ Validation interrupted by user")
        return 130
    except Exception as e:
        if args.ci:
            print(json.dumps({"error": str(e), "status": "ERROR"}))
        else:
            print(f"❌ Validation failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)
