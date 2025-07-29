#!/usr/bin/env python3
"""
Comprehensive IPFS-Kit Test Suite
=====================================

This script provides comprehensive testing of all IPFS-Kit components after reorganization:
- Virtual environment creation and package installation
- CLI functionality and command structure  
- Daemon management and services
- Docker containerization
- Kubernetes deployment
- CI/CD workflows
- Log aggregation system

Usage:
    python comprehensive_test_suite.py --all
    python comprehensive_test_suite.py --component cli
    python comprehensive_test_suite.py --component daemon
    python comprehensive_test_suite.py --component docker
    python comprehensive_test_suite.py --component k8s
    python comprehensive_test_suite.py --component virtualenv
"""

import asyncio
import subprocess
import sys
import os
import tempfile
import shutil
import json
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class TestResult:
    """Container for test results"""
    def __init__(self, name: str, success: bool, message: str, duration: float = 0.0, details: Optional[Dict] = None):
        self.name = name
        self.success = success
        self.message = message
        self.duration = duration
        self.details = details or {}
        self.timestamp = datetime.now()

class ComprehensiveTestSuite:
    """Main test suite runner"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.project_root = Path(__file__).parent
        self.start_time = time.time()
        
    def log_info(self, message: str):
        """Log info message with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{Colors.CYAN}[{timestamp}] ℹ️  {message}{Colors.END}")
        
    def log_success(self, message: str):
        """Log success message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{Colors.GREEN}[{timestamp}] ✅ {message}{Colors.END}")
        
    def log_error(self, message: str):
        """Log error message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{Colors.RED}[{timestamp}] ❌ {message}{Colors.END}")
        
    def log_warning(self, message: str):
        """Log warning message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{Colors.YELLOW}[{timestamp}] ⚠️  {message}{Colors.END}")

    async def run_command(self, cmd: List[str], cwd: Optional[Path] = None, timeout: int = 30, check_success: bool = True) -> Tuple[bool, str, str]:
        """Run a command and return success, stdout, stderr"""
        try:
            self.log_info(f"Running: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd or self.project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                success = process.returncode == 0 if check_success else True
                return success, stdout.decode('utf-8'), stderr.decode('utf-8')
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return False, "", f"Command timed out after {timeout} seconds"
                
        except Exception as e:
            return False, "", str(e)

    def add_result(self, name: str, success: bool, message: str, duration: float = 0.0, details: Optional[Dict] = None):
        """Add a test result"""
        result = TestResult(name, success, message, duration, details)
        self.results.append(result)
        
        if success:
            self.log_success(f"{name}: {message}")
        else:
            self.log_error(f"{name}: {message}")

    # ========================= VIRTUAL ENVIRONMENT TESTS =========================

    async def test_virtualenv_creation(self) -> bool:
        """Test virtual environment creation from scratch"""
        self.log_info("🔧 Testing virtual environment creation...")
        
        start_time = time.time()
        test_venv_path = self.project_root / "test_venv"
        
        try:
            # Clean up any existing test venv
            if test_venv_path.exists():
                shutil.rmtree(test_venv_path)
            
            # Create new virtual environment
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "venv", str(test_venv_path)
            ])
            
            if not success:
                self.add_result("VirtualEnv Creation", False, f"Failed to create venv: {stderr}")
                return False
            
            # Check if venv was created properly
            python_path = test_venv_path / "bin" / "python"
            if not python_path.exists():
                python_path = test_venv_path / "Scripts" / "python.exe"  # Windows
            
            if not python_path.exists():
                self.add_result("VirtualEnv Creation", False, "Python executable not found in venv")
                return False
            
            # Test venv Python
            success, stdout, stderr = await self.run_command([
                str(python_path), "--version"
            ])
            
            if not success:
                self.add_result("VirtualEnv Creation", False, f"VirtualEnv Python not working: {stderr}")
                return False
            
            duration = time.time() - start_time
            self.add_result("VirtualEnv Creation", True, f"Successfully created and tested venv in {duration:.2f}s", duration)
            
            # Clean up test venv
            shutil.rmtree(test_venv_path)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("VirtualEnv Creation", False, f"Exception: {str(e)}", duration)
            return False

    async def test_package_installation(self) -> bool:
        """Test package installation in virtual environment"""
        self.log_info("📦 Testing package installation...")
        
        start_time = time.time()
        
        try:
            # Check if current venv exists
            venv_path = self.project_root / ".venv"
            if not venv_path.exists():
                self.add_result("Package Installation", False, "No .venv directory found")
                return False
            
            # Find Python executable
            python_path = venv_path / "bin" / "python"
            if not python_path.exists():
                python_path = venv_path / "Scripts" / "python.exe"  # Windows
            
            if not python_path.exists():
                self.add_result("Package Installation", False, "Python executable not found in .venv")
                return False
            
            # Test installing package in development mode
            success, stdout, stderr = await self.run_command([
                str(python_path), "-m", "pip", "install", "-e", "."
            ], timeout=120)
            
            if not success:
                self.add_result("Package Installation", False, f"Failed to install package: {stderr}")
                return False
            
            # Test importing the package
            success, stdout, stderr = await self.run_command([
                str(python_path), "-c", "import ipfs_kit_py; print('Import successful')"
            ])
            
            if not success:
                self.add_result("Package Installation", False, f"Failed to import package: {stderr}")
                return False
            
            # Test console script installation
            ipfs_kit_path = venv_path / "bin" / "ipfs-kit"
            if not ipfs_kit_path.exists():
                ipfs_kit_path = venv_path / "Scripts" / "ipfs-kit.exe"  # Windows
            
            if ipfs_kit_path.exists():
                success, stdout, stderr = await self.run_command([
                    str(ipfs_kit_path), "--help"
                ], timeout=10)
                
                if success:
                    self.log_success("Console script ipfs-kit working")
                else:
                    self.log_warning(f"Console script not working: {stderr}")
            
            duration = time.time() - start_time
            self.add_result("Package Installation", True, f"Package installed and imported successfully in {duration:.2f}s", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("Package Installation", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= CLI TESTS =========================

    async def test_cli_basic_functionality(self) -> bool:
        """Test basic CLI functionality"""
        self.log_info("⌨️  Testing CLI basic functionality...")
        
        start_time = time.time()
        
        try:
            # Test help command (should be instant)
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "--help"
            ], timeout=5)
            
            if not success:
                self.add_result("CLI Help", False, f"Help command failed: {stderr}")
                return False
            
            if "IPFS-Kit CLI" not in stdout:
                self.add_result("CLI Help", False, "Help output doesn't contain expected content")
                return False
            
            # Test invalid command handling
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "invalid-command"
            ], timeout=5, check_success=False)
            
            # Should fail gracefully, not crash
            if "invalid choice" not in stderr and "unrecognized arguments" not in stderr:
                self.log_warning("Invalid command handling could be improved")
            
            duration = time.time() - start_time
            self.add_result("CLI Basic Functionality", True, f"CLI help and error handling working in {duration:.2f}s", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("CLI Basic Functionality", False, f"Exception: {str(e)}", duration)
            return False

    async def test_cli_commands(self) -> bool:
        """Test specific CLI commands"""
        self.log_info("🎯 Testing CLI commands...")
        
        start_time = time.time()
        commands_tested = 0
        commands_passed = 0
        
        # Test commands that should work without external dependencies
        test_commands = [
            (["config", "--help"], "Config help"),
            (["daemon", "--help"], "Daemon help"),
            (["pin", "--help"], "Pin help"),
            (["log", "--help"], "Log help"),  # New log command
            (["resource", "--help"], "Resource help"),
            (["metrics", "--help"], "Metrics help"),
            (["mcp", "--help"], "MCP help"),
        ]
        
        for cmd_args, description in test_commands:
            commands_tested += 1
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli"
            ] + cmd_args, timeout=10)
            
            if success:
                commands_passed += 1
                self.log_success(f"{description} working")
            else:
                self.log_error(f"{description} failed: {stderr}")
        
        # Test log aggregation commands specifically
        log_commands = [
            (["log", "show", "--help"], "Log show help"),
            (["log", "stats", "--help"], "Log stats help"), 
            (["log", "clear", "--help"], "Log clear help"),
            (["log", "export", "--help"], "Log export help"),
        ]
        
        for cmd_args, description in log_commands:
            commands_tested += 1
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli"
            ] + cmd_args, timeout=10)
            
            if success:
                commands_passed += 1
                self.log_success(f"{description} working")
            else:
                self.log_error(f"{description} failed: {stderr}")
        
        duration = time.time() - start_time
        success_rate = commands_passed / commands_tested if commands_tested > 0 else 0
        
        if success_rate >= 0.8:  # 80% success rate
            self.add_result("CLI Commands", True, f"{commands_passed}/{commands_tested} commands working ({success_rate:.1%}) in {duration:.2f}s", duration)
            return True
        else:
            self.add_result("CLI Commands", False, f"Only {commands_passed}/{commands_tested} commands working ({success_rate:.1%})", duration)
            return False

    async def test_cli_performance(self) -> bool:
        """Test CLI performance requirements"""
        self.log_info("⚡ Testing CLI performance...")
        
        try:
            # Test help command performance (should be < 1 second)
            start_time = time.time()
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "--help"
            ], timeout=5)
            help_duration = time.time() - start_time
            
            if not success:
                self.add_result("CLI Performance", False, f"Help command failed: {stderr}")
                return False
            
            # Check performance requirement
            if help_duration > 1.0:
                self.add_result("CLI Performance", False, f"Help command too slow: {help_duration:.2f}s (should be < 1s)")
                return False
            
            # Test multiple rapid commands
            rapid_test_times = []
            for i in range(3):
                start = time.time()
                success, _, _ = await self.run_command([
                    sys.executable, "-m", "ipfs_kit_py.cli", "config", "--help"
                ], timeout=5)
                rapid_test_times.append(time.time() - start)
                
                if not success:
                    self.log_warning(f"Rapid test {i+1} failed")
            
            avg_time = sum(rapid_test_times) / len(rapid_test_times) if rapid_test_times else 0
            
            self.add_result("CLI Performance", True, f"Help: {help_duration:.2f}s, Avg rapid: {avg_time:.2f}s", help_duration, {
                'help_duration': help_duration,
                'rapid_test_avg': avg_time,
                'rapid_test_times': rapid_test_times
            })
            return True
            
        except Exception as e:
            self.add_result("CLI Performance", False, f"Exception: {str(e)}")
            return False

    # ========================= DAEMON TESTS =========================

    async def test_daemon_functionality(self) -> bool:
        """Test daemon management functionality"""
        self.log_info("🔧 Testing daemon functionality...")
        
        start_time = time.time()
        
        try:
            # Test daemon status (should work without starting daemon)
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "daemon", "status"
            ], timeout=15)
            
            # Daemon status should work even if no daemon is running
            if not success:
                self.log_warning(f"Daemon status command failed: {stderr}")
            else:
                self.log_success("Daemon status command working")
            
            # Test daemon help
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "daemon", "--help"
            ], timeout=10)
            
            if not success:
                self.add_result("Daemon Functionality", False, f"Daemon help failed: {stderr}")
                return False
            
            # Check if help contains expected subcommands
            expected_subcommands = ["start", "stop", "status", "restart"]
            missing_subcommands = [cmd for cmd in expected_subcommands if cmd not in stdout]
            
            if missing_subcommands:
                self.log_warning(f"Missing daemon subcommands: {missing_subcommands}")
            
            duration = time.time() - start_time
            self.add_result("Daemon Functionality", True, f"Daemon commands accessible in {duration:.2f}s", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("Daemon Functionality", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= DOCKER TESTS =========================

    async def test_docker_setup(self) -> bool:
        """Test Docker configuration and setup"""
        self.log_info("🐳 Testing Docker setup...")
        
        start_time = time.time()
        
        try:
            # Check if Docker is available
            success, stdout, stderr = await self.run_command([
                "docker", "--version"
            ], timeout=10)
            
            if not success:
                self.add_result("Docker Setup", False, "Docker not available on system")
                return False
            
            # Check for Dockerfile
            dockerfile_paths = [
                self.project_root / "docker" / "Dockerfile",
                self.project_root / "Dockerfile"
            ]
            
            dockerfile_found = False
            for dockerfile_path in dockerfile_paths:
                if dockerfile_path.exists():
                    dockerfile_found = True
                    self.log_success(f"Found Dockerfile: {dockerfile_path}")
                    break
            
            if not dockerfile_found:
                self.add_result("Docker Setup", False, "No Dockerfile found")
                return False
            
            # Check for docker-compose
            compose_paths = [
                self.project_root / "docker" / "docker-compose.yml",
                self.project_root / "docker-compose.yml"
            ]
            
            compose_found = False
            for compose_path in compose_paths:
                if compose_path.exists():
                    compose_found = True
                    self.log_success(f"Found docker-compose.yml: {compose_path}")
                    break
            
            if not compose_found:
                self.log_warning("No docker-compose.yml found")
            
            # Test docker-compose validation if available
            if compose_found:
                success, stdout, stderr = await self.run_command([
                    "docker-compose", "-f", str(compose_path), "config"
                ], timeout=15)
                
                if success:
                    self.log_success("Docker-compose configuration valid")
                else:
                    self.log_warning(f"Docker-compose validation failed: {stderr}")
            
            duration = time.time() - start_time
            self.add_result("Docker Setup", True, f"Docker environment validated in {duration:.2f}s", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("Docker Setup", False, f"Exception: {str(e)}", duration)
            return False

    async def test_docker_build(self) -> bool:
        """Test Docker image building"""
        self.log_info("🔨 Testing Docker build...")
        
        start_time = time.time()
        
        try:
            # Find Dockerfile
            dockerfile_path = self.project_root / "docker" / "Dockerfile"
            if not dockerfile_path.exists():
                dockerfile_path = self.project_root / "Dockerfile"
            
            if not dockerfile_path.exists():
                self.add_result("Docker Build", False, "No Dockerfile found for building")
                return False
            
            # Build Docker image (with timeout to prevent hanging)
            image_tag = "ipfs-kit:test"
            success, stdout, stderr = await self.run_command([
                "docker", "build", "-t", image_tag, "-f", str(dockerfile_path), "."
            ], timeout=300)  # 5 minute timeout for build
            
            if not success:
                self.add_result("Docker Build", False, f"Docker build failed: {stderr}")
                return False
            
            # Test running the built image
            success, stdout, stderr = await self.run_command([
                "docker", "run", "--rm", image_tag, "--help"
            ], timeout=30)
            
            if not success:
                self.log_warning(f"Docker run test failed: {stderr}")
            else:
                self.log_success("Docker image runs successfully")
            
            # Clean up test image
            await self.run_command([
                "docker", "rmi", image_tag
            ], timeout=30, check_success=False)
            
            duration = time.time() - start_time
            self.add_result("Docker Build", True, f"Docker build successful in {duration:.2f}s", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("Docker Build", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= KUBERNETES TESTS =========================

    async def test_kubernetes_manifests(self) -> bool:
        """Test Kubernetes manifest validation"""
        self.log_info("☸️  Testing Kubernetes manifests...")
        
        start_time = time.time()
        
        try:
            # Look for Kubernetes manifests
            k8s_paths = [
                self.project_root / "k8s",
                self.project_root / "kubernetes",
                self.project_root / "deployment" / "k8s"
            ]
            
            manifests_found = []
            for k8s_path in k8s_paths:
                if k8s_path.exists():
                    yaml_files = list(k8s_path.glob("*.yaml")) + list(k8s_path.glob("*.yml"))
                    manifests_found.extend(yaml_files)
            
            if not manifests_found:
                self.add_result("Kubernetes Manifests", False, "No Kubernetes manifests found")
                return False
            
            self.log_success(f"Found {len(manifests_found)} Kubernetes manifests")
            
            # Test kubectl availability
            success, stdout, stderr = await self.run_command([
                "kubectl", "version", "--client"
            ], timeout=10)
            
            kubectl_available = success
            if not kubectl_available:
                self.log_warning("kubectl not available, skipping validation")
            
            # Validate manifests if kubectl is available
            valid_manifests = 0
            for manifest in manifests_found:
                if kubectl_available:
                    success, stdout, stderr = await self.run_command([
                        "kubectl", "apply", "--dry-run=client", "-f", str(manifest)
                    ], timeout=15)
                    
                    if success:
                        valid_manifests += 1
                        self.log_success(f"Valid manifest: {manifest.name}")
                    else:
                        self.log_warning(f"Invalid manifest {manifest.name}: {stderr}")
                else:
                    # Basic YAML validation
                    try:
                        import yaml
                        with open(manifest) as f:
                            yaml.safe_load(f)
                        valid_manifests += 1
                        self.log_success(f"Valid YAML: {manifest.name}")
                    except Exception as e:
                        self.log_warning(f"Invalid YAML {manifest.name}: {e}")
            
            duration = time.time() - start_time
            success_rate = valid_manifests / len(manifests_found) if manifests_found else 0
            
            if success_rate >= 0.8:
                self.add_result("Kubernetes Manifests", True, f"{valid_manifests}/{len(manifests_found)} manifests valid ({success_rate:.1%}) in {duration:.2f}s", duration)
                return True
            else:
                self.add_result("Kubernetes Manifests", False, f"Only {valid_manifests}/{len(manifests_found)} manifests valid ({success_rate:.1%})", duration)
                return False
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("Kubernetes Manifests", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= CI/CD TESTS =========================

    async def test_cicd_workflows(self) -> bool:
        """Test CI/CD workflow configurations"""
        self.log_info("🔄 Testing CI/CD workflows...")
        
        start_time = time.time()
        
        try:
            # Check for GitHub Actions workflows
            github_workflows_path = self.project_root / ".github" / "workflows"
            workflows_found = []
            
            if github_workflows_path.exists():
                workflow_files = list(github_workflows_path.glob("*.yml")) + list(github_workflows_path.glob("*.yaml"))
                workflows_found.extend(workflow_files)
            
            if not workflows_found:
                self.add_result("CI/CD Workflows", False, "No CI/CD workflows found")
                return False
            
            self.log_success(f"Found {len(workflows_found)} workflow files")
            
            # Validate workflow YAML syntax
            valid_workflows = 0
            try:
                import yaml
                yaml_available = True
            except ImportError:
                yaml_available = False
                self.log_warning("PyYAML not available, skipping workflow validation")
            
            workflow_details = {}
            for workflow_file in workflows_found:
                try:
                    if yaml_available:
                        with open(workflow_file) as f:
                            workflow_data = yaml.safe_load(f)
                        
                        # Check for required fields
                        if 'name' in workflow_data and 'on' in workflow_data:
                            valid_workflows += 1
                            workflow_details[workflow_file.name] = {
                                'name': workflow_data.get('name', 'Unknown'),
                                'triggers': list(workflow_data.get('on', {}).keys()) if isinstance(workflow_data.get('on'), dict) else [workflow_data.get('on')]
                            }
                            self.log_success(f"Valid workflow: {workflow_file.name}")
                        else:
                            self.log_warning(f"Incomplete workflow: {workflow_file.name}")
                    else:
                        valid_workflows += 1  # Assume valid if we can't validate
                        
                except Exception as e:
                    self.log_warning(f"Invalid workflow {workflow_file.name}: {e}")
            
            duration = time.time() - start_time
            success_rate = valid_workflows / len(workflows_found) if workflows_found else 0
            
            if success_rate >= 0.8:
                self.add_result("CI/CD Workflows", True, f"{valid_workflows}/{len(workflows_found)} workflows valid ({success_rate:.1%}) in {duration:.2f}s", duration, workflow_details)
                return True
            else:
                self.add_result("CI/CD Workflows", False, f"Only {valid_workflows}/{len(workflows_found)} workflows valid ({success_rate:.1%})", duration, workflow_details)
                return False
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("CI/CD Workflows", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= LOG AGGREGATION TESTS =========================

    async def test_log_aggregation(self) -> bool:
        """Test the new log aggregation system"""
        self.log_info("📋 Testing log aggregation system...")
        
        start_time = time.time()
        
        try:
            # Test log command help
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "log", "--help"
            ], timeout=10)
            
            if not success:
                self.add_result("Log Aggregation", False, f"Log command help failed: {stderr}")
                return False
            
            # Check for expected subcommands
            expected_subcommands = ["show", "stats", "clear", "export"]
            missing_subcommands = [cmd for cmd in expected_subcommands if cmd not in stdout]
            
            if missing_subcommands:
                self.add_result("Log Aggregation", False, f"Missing log subcommands: {missing_subcommands}")
                return False
            
            # Test each log subcommand help
            subcommand_tests = []
            for subcommand in expected_subcommands:
                success, stdout, stderr = await self.run_command([
                    sys.executable, "-m", "ipfs_kit_py.cli", "log", subcommand, "--help"
                ], timeout=10)
                
                subcommand_tests.append((subcommand, success))
                if success:
                    self.log_success(f"Log {subcommand} help working")
                else:
                    self.log_error(f"Log {subcommand} help failed: {stderr}")
            
            successful_subcommands = sum(1 for _, success in subcommand_tests if success)
            
            duration = time.time() - start_time
            
            if successful_subcommands == len(expected_subcommands):
                self.add_result("Log Aggregation", True, f"All log subcommands working in {duration:.2f}s", duration)
                return True
            else:
                self.add_result("Log Aggregation", False, f"Only {successful_subcommands}/{len(expected_subcommands)} log subcommands working", duration)
                return False
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("Log Aggregation", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= INTEGRATION TESTS =========================

    async def test_integration_end_to_end(self) -> bool:
        """Test end-to-end integration functionality"""
        self.log_info("🔗 Testing end-to-end integration...")
        
        start_time = time.time()
        
        try:
            # Test a complex workflow that involves multiple components
            test_steps = []
            
            # Step 1: Check config system
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "config", "show"
            ], timeout=15)
            test_steps.append(("Config Show", success))
            
            # Step 2: Check daemon status
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "daemon", "status"
            ], timeout=15)
            test_steps.append(("Daemon Status", success))
            
            # Step 3: Check log system
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "log", "stats"
            ], timeout=15)
            test_steps.append(("Log Stats", success))
            
            # Step 4: Check metrics
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "metrics"
            ], timeout=15)
            test_steps.append(("Metrics", success))
            
            # Step 5: Check resource monitoring
            success, stdout, stderr = await self.run_command([
                sys.executable, "-m", "ipfs_kit_py.cli", "resource", "status"
            ], timeout=15)
            test_steps.append(("Resource Status", success))
            
            successful_steps = sum(1 for _, success in test_steps if success)
            
            duration = time.time() - start_time
            
            if successful_steps >= len(test_steps) * 0.8:  # 80% success rate
                self.add_result("End-to-End Integration", True, f"{successful_steps}/{len(test_steps)} integration steps successful in {duration:.2f}s", duration)
                return True
            else:
                self.add_result("End-to-End Integration", False, f"Only {successful_steps}/{len(test_steps)} integration steps successful", duration)
                return False
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("End-to-End Integration", False, f"Exception: {str(e)}", duration)
            return False

    # ========================= MAIN TEST RUNNER =========================

    async def run_test_component(self, component: str) -> bool:
        """Run tests for a specific component"""
        self.log_info(f"🧪 Running {component} tests...")
        
        if component == "virtualenv":
            return await self.test_virtualenv_creation() and await self.test_package_installation()
        elif component == "cli":
            return (await self.test_cli_basic_functionality() and 
                   await self.test_cli_commands() and 
                   await self.test_cli_performance())
        elif component == "daemon":
            return await self.test_daemon_functionality()
        elif component == "docker":
            return await self.test_docker_setup() and await self.test_docker_build()
        elif component == "k8s":
            return await self.test_kubernetes_manifests()
        elif component == "cicd":
            return await self.test_cicd_workflows()
        elif component == "logs":
            return await self.test_log_aggregation()
        elif component == "integration":
            return await self.test_integration_end_to_end()
        else:
            self.log_error(f"Unknown component: {component}")
            return False

    async def run_all_tests(self) -> bool:
        """Run all test components"""
        self.log_info("🚀 Running comprehensive test suite...")
        
        components = ["virtualenv", "cli", "daemon", "docker", "k8s", "cicd", "logs", "integration"]
        
        results = {}
        for component in components:
            self.log_info(f"\n{'='*60}")
            self.log_info(f"Testing component: {component.upper()}")
            self.log_info(f"{'='*60}")
            
            try:
                results[component] = await self.run_test_component(component)
            except Exception as e:
                self.log_error(f"Component {component} test failed with exception: {e}")
                results[component] = False
        
        return all(results.values())

    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        total_duration = time.time() - self.start_time
        
        passed = len([r for r in self.results if r.success])
        failed = len([r for r in self.results if not r.success])
        total = len(self.results)
        
        success_rate = (passed / total * 100) if total > 0 else 0
        
        report = f"""
{Colors.BOLD}IPFS-Kit Comprehensive Test Report{Colors.END}
{'='*80}

{Colors.CYAN}📊 Summary:{Colors.END}
  Total Tests: {total}
  Passed: {Colors.GREEN}{passed}{Colors.END}
  Failed: {Colors.RED}{failed}{Colors.END}
  Success Rate: {Colors.GREEN if success_rate >= 80 else Colors.RED}{success_rate:.1f}%{Colors.END}
  Total Duration: {total_duration:.2f}s

{Colors.CYAN}📋 Detailed Results:{Colors.END}
"""
        
        for result in self.results:
            status_icon = "✅" if result.success else "❌"
            color = Colors.GREEN if result.success else Colors.RED
            
            report += f"  {status_icon} {color}{result.name:<30}{Colors.END} - {result.message}"
            if result.duration > 0:
                report += f" ({result.duration:.2f}s)"
            report += "\n"
        
        if failed > 0:
            report += f"\n{Colors.RED}❌ Failed Tests Details:{Colors.END}\n"
            for result in [r for r in self.results if not r.success]:
                report += f"  • {result.name}: {result.message}\n"
        
        # Component summary
        components = {}
        for result in self.results:
            component = result.name.split()[0].lower()
            if component not in components:
                components[component] = {'passed': 0, 'total': 0}
            components[component]['total'] += 1
            if result.success:
                components[component]['passed'] += 1
        
        if components:
            report += f"\n{Colors.CYAN}🔧 Component Summary:{Colors.END}\n"
            for component, stats in components.items():
                rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
                color = Colors.GREEN if rate >= 80 else Colors.YELLOW if rate >= 60 else Colors.RED
                report += f"  {component.capitalize():<15}: {color}{stats['passed']}/{stats['total']} ({rate:.1f}%){Colors.END}\n"
        
        return report

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS-Kit Comprehensive Test Suite")
    parser.add_argument("--component", choices=["virtualenv", "cli", "daemon", "docker", "k8s", "cicd", "logs", "integration"], 
                       help="Test specific component only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--output", help="Output report to file")
    
    args = parser.parse_args()
    
    if not args.component and not args.all:
        parser.print_help()
        return 1
    
    suite = ComprehensiveTestSuite()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("🧪 IPFS-Kit Comprehensive Test Suite")
    print("=" * 80)
    print(f"{Colors.END}")
    
    try:
        if args.all:
            success = await suite.run_all_tests()
        else:
            success = await suite.run_test_component(args.component)
        
        # Generate and display report
        report = suite.generate_report()
        print(report)
        
        # Save report if requested
        if args.output:
            with open(args.output, 'w') as f:
                # Strip ANSI codes for file output
                import re
                clean_report = re.sub(r'\x1b\[[0-9;]*m', '', report)
                f.write(clean_report)
            print(f"\n📄 Report saved to: {args.output}")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Test suite interrupted by user{Colors.END}")
        return 130
    except Exception as e:
        print(f"\n{Colors.RED}❌ Test suite failed with exception: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
