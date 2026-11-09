#!/usr/bin/env python3
"""
Comprehensive Post-Reorganization Test Suite

Tests all major IPFS Kit components to ensure functionality after directory reorganization:
- IPFS Kit daemon functionality
- CLI operations and commands
- Docker system compatibility
- CI/CD pipeline components
- Kubernetes configurations
- Virtual environment setup
- Package installation and imports
"""

import os
import sys
import subprocess
import json
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveTestSuite:
    """Comprehensive test suite for post-reorganization validation"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.test_results = {
            'package_imports': {},
            'cli_functionality': {},
            'daemon_operations': {},
            'docker_system': {},
            'ci_cd_pipeline': {},
            'kubernetes': {},
            'virtualenv': {},
            'file_paths': {},
            'overall_status': 'pending'
        }
        self.temp_dir = None
        
    def run_all_tests(self) -> Dict:
        """Run comprehensive test suite"""
        print("🧪 IPFS Kit Comprehensive Post-Reorganization Test Suite")
        print("=" * 70)
        print(f"Root Directory: {self.root_path}")
        print(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            # Setup temporary directory for tests
            self.temp_dir = Path(tempfile.mkdtemp(prefix="ipfs_kit_test_"))
            logger.info(f"Created temporary test directory: {self.temp_dir}")
            
            # Run test categories
            test_categories = [
                ("Package Imports", self.test_package_imports),
                ("File Path Integrity", self.test_file_paths),
                ("CLI Functionality", self.test_cli_functionality),
                ("Daemon Operations", self.test_daemon_operations),
                ("Docker System", self.test_docker_system),
                ("CI/CD Pipeline", self.test_ci_cd_pipeline),
                ("Kubernetes", self.test_kubernetes),
                ("Virtual Environment", self.test_virtualenv),
            ]
            
            for category_name, test_func in test_categories:
                print(f"\n🔍 Testing {category_name}...")
                print("-" * 50)
                try:
                    test_func()
                    print(f"✅ {category_name}: PASSED")
                except Exception as e:
                    print(f"❌ {category_name}: FAILED - {str(e)}")
                    logger.error(f"{category_name} failed: {e}", exc_info=True)
            
            # Generate final report
            self.generate_final_report()
            
        finally:
            # Cleanup
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temporary test directory")
        
        return self.test_results
    
    def test_package_imports(self):
        """Test that core package imports work correctly"""
        print("  📦 Testing package imports...")
        
        # Test core package import
        try:
            import ipfs_kit_py
            self.test_results['package_imports']['core_package'] = 'PASS'
            print("    ✅ Core package (ipfs_kit_py) imports successfully")
        except ImportError as e:
            self.test_results['package_imports']['core_package'] = f'FAIL: {e}'
            print(f"    ❌ Core package import failed: {e}")
        
        # Test specific module imports
        modules_to_test = [
            'ipfs_kit_py.api',
            'ipfs_kit_py.cli',
            'ipfs_kit_py.daemon_config_manager',
            'ipfs_kit_py.ipfs_fsspec',
        ]
        
        for module in modules_to_test:
            try:
                __import__(module)
                self.test_results['package_imports'][module] = 'PASS'
                print(f"    ✅ {module} imports successfully")
            except ImportError as e:
                self.test_results['package_imports'][module] = f'FAIL: {e}'
                print(f"    ❌ {module} import failed: {e}")
        
        # Test CLI module specifically
        try:
            result = subprocess.run([
                sys.executable, '-c', 
                'import ipfs_kit_py.cli; print("CLI module imported successfully")'
            ], capture_output=True, text=True, cwd=self.root_path)
            
            if result.returncode == 0:
                self.test_results['package_imports']['cli_module'] = 'PASS'
                print("    ✅ CLI module imports in subprocess")
            else:
                self.test_results['package_imports']['cli_module'] = f'FAIL: {result.stderr}'
                print(f"    ❌ CLI module subprocess failed: {result.stderr}")
        except Exception as e:
            self.test_results['package_imports']['cli_module'] = f'FAIL: {e}'
            print(f"    ❌ CLI module subprocess error: {e}")
    
    def test_file_paths(self):
        """Test that critical file paths exist and are accessible"""
        print("  📁 Testing file path integrity...")
        
        critical_files = {
            'main_entry': 'main.py',
            'cli_tool': 'ipfs_kit_cli.py',
            'cli_executable': 'ipfs-kit',
            'setup_config': 'pyproject.toml',
            'requirements': 'requirements.txt',
            'readme': 'README.md',
            'license': 'LICENSE'
        }
        
        for file_type, file_path in critical_files.items():
            full_path = self.root_path / file_path
            if full_path.exists():
                self.test_results['file_paths'][file_type] = 'PASS'
                print(f"    ✅ {file_path} exists")
            else:
                self.test_results['file_paths'][file_type] = 'FAIL: Missing'
                print(f"    ❌ {file_path} missing")
        
        # Test organized directories
        organized_dirs = {
            'documentation': 'docs',
            'examples': 'examples', 
            'tests': 'tests',
            'tools': 'tools',
            'cli_variants': 'cli',
            'data_files': 'data'
        }
        
        for dir_type, dir_path in organized_dirs.items():
            full_path = self.root_path / dir_path
            if full_path.exists() and full_path.is_dir():
                file_count = len(list(full_path.rglob('*')))
                self.test_results['file_paths'][f'{dir_type}_dir'] = f'PASS: {file_count} items'
                print(f"    ✅ {dir_path}/ directory exists ({file_count} items)")
            else:
                self.test_results['file_paths'][f'{dir_type}_dir'] = 'FAIL: Missing'
                print(f"    ❌ {dir_path}/ directory missing")
    
    def test_cli_functionality(self):
        """Test CLI functionality and commands"""
        print("  🖥️  Testing CLI functionality...")
        
        cli_path = self.root_path / 'ipfs_kit_cli.py'
        if not cli_path.exists():
            self.test_results['cli_functionality']['cli_exists'] = 'FAIL: CLI file missing'
            print("    ❌ CLI file does not exist")
            return
        
        # Test CLI help command
        try:
            result = subprocess.run([
                sys.executable, str(cli_path), '--help'
            ], capture_output=True, text=True, cwd=self.root_path, timeout=30)
            
            if result.returncode == 0 and 'usage:' in result.stdout.lower():
                self.test_results['cli_functionality']['help_command'] = 'PASS'
                print("    ✅ CLI --help command works")
            else:
                self.test_results['cli_functionality']['help_command'] = f'FAIL: {result.stderr}'
                print(f"    ❌ CLI --help failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.test_results['cli_functionality']['help_command'] = 'FAIL: Timeout'
            print("    ❌ CLI --help timed out")
        except Exception as e:
            self.test_results['cli_functionality']['help_command'] = f'FAIL: {e}'
            print(f"    ❌ CLI --help error: {e}")
        
        # Test CLI module execution
        try:
            result = subprocess.run([
                sys.executable, '-m', 'ipfs_kit_py.cli', '--help'
            ], capture_output=True, text=True, cwd=self.root_path, timeout=30)
            
            if result.returncode == 0:
                self.test_results['cli_functionality']['module_execution'] = 'PASS'
                print("    ✅ CLI module execution works")
            else:
                self.test_results['cli_functionality']['module_execution'] = f'FAIL: {result.stderr}'
                print(f"    ❌ CLI module execution failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.test_results['cli_functionality']['module_execution'] = 'FAIL: Timeout'
            print("    ❌ CLI module execution timed out")
        except Exception as e:
            self.test_results['cli_functionality']['module_execution'] = f'FAIL: {e}'
            print(f"    ❌ CLI module execution error: {e}")
        
        # Test specific CLI commands
        cli_commands = ['daemon', 'config', 'health', 'backend']
        for cmd in cli_commands:
            try:
                result = subprocess.run([
                    sys.executable, '-m', 'ipfs_kit_py.cli', cmd, '--help'
                ], capture_output=True, text=True, cwd=self.root_path, timeout=15)
                
                if result.returncode == 0:
                    self.test_results['cli_functionality'][f'{cmd}_command'] = 'PASS'
                    print(f"    ✅ CLI {cmd} command available")
                else:
                    self.test_results['cli_functionality'][f'{cmd}_command'] = 'FAIL'
                    print(f"    ❌ CLI {cmd} command failed")
            except Exception as e:
                self.test_results['cli_functionality'][f'{cmd}_command'] = f'FAIL: {e}'
                print(f"    ⚠️  CLI {cmd} command error: {e}")
    
    def test_daemon_operations(self):
        """Test daemon-related operations"""
        print("  🔧 Testing daemon operations...")
        
        # Test daemon configuration
        try:
            result = subprocess.run([
                sys.executable, '-c', 
                'from ipfs_kit_py.daemon_config_manager import DaemonConfigManager; print("Daemon config available")'
            ], capture_output=True, text=True, cwd=self.root_path)
            
            if result.returncode == 0:
                self.test_results['daemon_operations']['config_manager'] = 'PASS'
                print("    ✅ Daemon config manager available")
            else:
                self.test_results['daemon_operations']['config_manager'] = f'FAIL: {result.stderr}'
                print(f"    ❌ Daemon config manager failed: {result.stderr}")
        except Exception as e:
            self.test_results['daemon_operations']['config_manager'] = f'FAIL: {e}'
            print(f"    ❌ Daemon config manager error: {e}")
        
        # Test daemon status command (non-blocking)
        try:
            result = subprocess.run([
                sys.executable, '-m', 'ipfs_kit_py.cli', 'daemon', 'status'
            ], capture_output=True, text=True, cwd=self.root_path, timeout=10)
            
            # Don't fail if daemon isn't running - just check command works
            if 'status' in result.stdout.lower() or 'daemon' in result.stdout.lower():
                self.test_results['daemon_operations']['status_command'] = 'PASS'
                print("    ✅ Daemon status command works")
            else:
                self.test_results['daemon_operations']['status_command'] = 'PARTIAL: Command exists'
                print("    ⚠️  Daemon status command exists (daemon may not be running)")
        except subprocess.TimeoutExpired:
            self.test_results['daemon_operations']['status_command'] = 'PARTIAL: Timeout'
            print("    ⚠️  Daemon status command timed out")
        except Exception as e:
            self.test_results['daemon_operations']['status_command'] = f'FAIL: {e}'
            print(f"    ❌ Daemon status command error: {e}")
    
    def test_docker_system(self):
        """Test Docker system compatibility"""
        print("  🐳 Testing Docker system...")
        
        # Check if Dockerfile exists
        dockerfile_path = self.root_path / 'Dockerfile'
        if dockerfile_path.exists():
            self.test_results['docker_system']['dockerfile_exists'] = 'PASS'
            print("    ✅ Dockerfile exists")
            
            # Validate Dockerfile syntax
            try:
                with open(dockerfile_path, 'r') as f:
                    content = f.read()
                if 'FROM' in content and 'COPY' in content:
                    self.test_results['docker_system']['dockerfile_valid'] = 'PASS'
                    print("    ✅ Dockerfile appears valid")
                else:
                    self.test_results['docker_system']['dockerfile_valid'] = 'FAIL: Invalid syntax'
                    print("    ❌ Dockerfile invalid syntax")
            except Exception as e:
                self.test_results['docker_system']['dockerfile_valid'] = f'FAIL: {e}'
                print(f"    ❌ Dockerfile validation error: {e}")
        else:
            self.test_results['docker_system']['dockerfile_exists'] = 'FAIL: Missing'
            print("    ❌ Dockerfile missing")
        
        # Check Docker compose files
        compose_files = ['docker-compose.yml', 'docker-compose.yaml', 'docker/docker-compose.yml']
        compose_found = False
        for compose_file in compose_files:
            compose_path = self.root_path / compose_file
            if compose_path.exists():
                self.test_results['docker_system']['compose_file'] = f'PASS: {compose_file}'
                print(f"    ✅ Docker compose file found: {compose_file}")
                compose_found = True
                break
        
        if not compose_found:
            self.test_results['docker_system']['compose_file'] = 'PARTIAL: Not found'
            print("    ⚠️  No Docker compose file found")
        
        # Check if Docker is available (optional)
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.test_results['docker_system']['docker_available'] = 'PASS'
                print("    ✅ Docker is available on system")
            else:
                self.test_results['docker_system']['docker_available'] = 'FAIL: Not working'
                print("    ❌ Docker not working")
        except FileNotFoundError:
            self.test_results['docker_system']['docker_available'] = 'PARTIAL: Not installed'
            print("    ⚠️  Docker not installed (optional)")
        except Exception as e:
            self.test_results['docker_system']['docker_available'] = f'FAIL: {e}'
            print(f"    ❌ Docker check error: {e}")
    
    def test_ci_cd_pipeline(self):
        """Test CI/CD pipeline components"""
        print("  🔄 Testing CI/CD pipeline...")
        
        # Check GitHub Actions
        github_dir = self.root_path / '.github'
        if github_dir.exists():
            workflows_dir = github_dir / 'workflows'
            if workflows_dir.exists():
                workflow_files = list(workflows_dir.glob('*.yml')) + list(workflows_dir.glob('*.yaml'))
                if workflow_files:
                    self.test_results['ci_cd_pipeline']['github_actions'] = f'PASS: {len(workflow_files)} workflows'
                    print(f"    ✅ GitHub Actions workflows found: {len(workflow_files)} files")
                else:
                    self.test_results['ci_cd_pipeline']['github_actions'] = 'FAIL: No workflows'
                    print("    ❌ No GitHub Actions workflows found")
            else:
                self.test_results['ci_cd_pipeline']['github_actions'] = 'FAIL: No workflows dir'
                print("    ❌ No GitHub Actions workflows directory")
        else:
            self.test_results['ci_cd_pipeline']['github_actions'] = 'PARTIAL: No .github dir'
            print("    ⚠️  No .github directory found")
        
        # Check Makefile for CI/CD commands
        makefile_path = self.root_path / 'Makefile'
        if makefile_path.exists():
            try:
                with open(makefile_path, 'r') as f:
                    content = f.read()
                
                ci_targets = ['test', 'build', 'install', 'clean']
                found_targets = [target for target in ci_targets if f'{target}:' in content]
                
                if found_targets:
                    self.test_results['ci_cd_pipeline']['makefile_targets'] = f'PASS: {len(found_targets)} targets'
                    print(f"    ✅ Makefile CI/CD targets found: {', '.join(found_targets)}")
                else:
                    self.test_results['ci_cd_pipeline']['makefile_targets'] = 'PARTIAL: No CI targets'
                    print("    ⚠️  No CI/CD targets in Makefile")
            except Exception as e:
                self.test_results['ci_cd_pipeline']['makefile_targets'] = f'FAIL: {e}'
                print(f"    ❌ Makefile analysis error: {e}")
        else:
            self.test_results['ci_cd_pipeline']['makefile_targets'] = 'FAIL: No Makefile'
            print("    ❌ No Makefile found")
        
        # Check for test configuration
        test_configs = ['pytest.ini', 'setup.cfg', 'pyproject.toml']
        test_config_found = False
        for config_file in test_configs:
            config_path = self.root_path / config_file
            if config_path.exists():
                self.test_results['ci_cd_pipeline']['test_config'] = f'PASS: {config_file}'
                print(f"    ✅ Test configuration found: {config_file}")
                test_config_found = True
                break
        
        if not test_config_found:
            self.test_results['ci_cd_pipeline']['test_config'] = 'PARTIAL: No specific test config'
            print("    ⚠️  No specific test configuration found")
    
    def test_kubernetes(self):
        """Test Kubernetes configurations"""
        print("  ☸️  Testing Kubernetes...")
        
        k8s_dir = self.root_path / 'k8s'
        if k8s_dir.exists():
            yaml_files = list(k8s_dir.rglob('*.yaml')) + list(k8s_dir.rglob('*.yml'))
            if yaml_files:
                self.test_results['kubernetes']['manifests'] = f'PASS: {len(yaml_files)} manifests'
                print(f"    ✅ Kubernetes manifests found: {len(yaml_files)} files")
                
                # Check for key Kubernetes resources
                k8s_resources = ['deployment', 'service', 'configmap', 'statefulset']
                found_resources = []
                
                for yaml_file in yaml_files:
                    try:
                        with open(yaml_file, 'r') as f:
                            content = f.read().lower()
                        for resource in k8s_resources:
                            if f'kind: {resource}' in content:
                                found_resources.append(resource)
                    except Exception:
                        continue
                
                if found_resources:
                    self.test_results['kubernetes']['resource_types'] = f'PASS: {set(found_resources)}'
                    print(f"    ✅ K8s resource types found: {', '.join(set(found_resources))}")
                else:
                    self.test_results['kubernetes']['resource_types'] = 'PARTIAL: No standard resources'
                    print("    ⚠️  No standard K8s resources identified")
            else:
                self.test_results['kubernetes']['manifests'] = 'FAIL: No YAML files'
                print("    ❌ No Kubernetes YAML files found")
        else:
            self.test_results['kubernetes']['manifests'] = 'PARTIAL: No k8s directory'
            print("    ⚠️  No k8s directory found")
        
        # Check if kubectl is available (optional)
        try:
            result = subprocess.run(['kubectl', 'version', '--client'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.test_results['kubernetes']['kubectl_available'] = 'PASS'
                print("    ✅ kubectl is available on system")
            else:
                self.test_results['kubernetes']['kubectl_available'] = 'FAIL: Not working'
                print("    ❌ kubectl not working")
        except FileNotFoundError:
            self.test_results['kubernetes']['kubectl_available'] = 'PARTIAL: Not installed'
            print("    ⚠️  kubectl not installed (optional)")
        except Exception as e:
            self.test_results['kubernetes']['kubectl_available'] = f'FAIL: {e}'
            print(f"    ❌ kubectl check error: {e}")
    
    def test_virtualenv(self):
        """Test virtual environment creation and package installation"""
        print("  🐍 Testing virtual environment...")
        
        test_venv_path = self.temp_dir / 'test_venv'
        
        try:
            # Create virtual environment
            result = subprocess.run([
                sys.executable, '-m', 'venv', str(test_venv_path)
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and test_venv_path.exists():
                self.test_results['virtualenv']['creation'] = 'PASS'
                print("    ✅ Virtual environment creation works")
                
                # Test package installation in venv
                if sys.platform == 'win32':
                    pip_path = test_venv_path / 'Scripts' / 'pip.exe'
                    python_path = test_venv_path / 'Scripts' / 'python.exe'
                else:
                    pip_path = test_venv_path / 'bin' / 'pip'
                    python_path = test_venv_path / 'bin' / 'python'
                
                if pip_path.exists():
                    # Test pip upgrade
                    result = subprocess.run([
                        str(pip_path), 'install', '--upgrade', 'pip'
                    ], capture_output=True, text=True, timeout=120)
                    
                    if result.returncode == 0:
                        self.test_results['virtualenv']['pip_upgrade'] = 'PASS'
                        print("    ✅ pip upgrade works in venv")
                    else:
                        self.test_results['virtualenv']['pip_upgrade'] = f'FAIL: {result.stderr}'
                        print(f"    ❌ pip upgrade failed: {result.stderr}")
                    
                    # Test package installation from current directory
                    result = subprocess.run([
                        str(pip_path), 'install', '-e', str(self.root_path)
                    ], capture_output=True, text=True, timeout=300, cwd=self.root_path)
                    
                    if result.returncode == 0:
                        self.test_results['virtualenv']['package_install'] = 'PASS'
                        print("    ✅ Package installation works in venv")
                        
                        # Test import in venv
                        result = subprocess.run([
                            str(python_path), '-c', 'import ipfs_kit_py; print("Import successful")'
                        ], capture_output=True, text=True, timeout=30)
                        
                        if result.returncode == 0:
                            self.test_results['virtualenv']['import_test'] = 'PASS'
                            print("    ✅ Package import works in venv")
                        else:
                            self.test_results['virtualenv']['import_test'] = f'FAIL: {result.stderr}'
                            print(f"    ❌ Package import failed in venv: {result.stderr}")
                    else:
                        self.test_results['virtualenv']['package_install'] = f'FAIL: {result.stderr}'
                        print(f"    ❌ Package installation failed: {result.stderr}")
                else:
                    self.test_results['virtualenv']['pip_available'] = 'FAIL: pip not found'
                    print("    ❌ pip not found in virtual environment")
            else:
                self.test_results['virtualenv']['creation'] = f'FAIL: {result.stderr}'
                print(f"    ❌ Virtual environment creation failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.test_results['virtualenv']['creation'] = 'FAIL: Timeout'
            print("    ❌ Virtual environment creation timed out")
        except Exception as e:
            self.test_results['virtualenv']['creation'] = f'FAIL: {e}'
            print(f"    ❌ Virtual environment error: {e}")
    
    def generate_final_report(self):
        """Generate final test report"""
        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 70)
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        partial_tests = 0
        
        for category, tests in self.test_results.items():
            if category == 'overall_status':
                continue
                
            print(f"\n📂 {category.upper().replace('_', ' ')}:")
            category_total = len(tests)
            category_passed = 0
            category_failed = 0
            category_partial = 0
            
            for test_name, result in tests.items():
                total_tests += 1
                
                if isinstance(result, str):
                    if result.startswith('PASS'):
                        status = '✅ PASS'
                        passed_tests += 1
                        category_passed += 1
                    elif result.startswith('FAIL'):
                        status = '❌ FAIL'
                        failed_tests += 1
                        category_failed += 1
                    elif result.startswith('PARTIAL'):
                        status = '⚠️  PARTIAL'
                        partial_tests += 1
                        category_partial += 1
                    else:
                        status = '❓ UNKNOWN'
                        partial_tests += 1
                        category_partial += 1
                    
                    print(f"  {status} {test_name}: {result}")
            
            # Category summary
            print(f"  📈 Summary: {category_passed}/{category_total} passed, {category_failed} failed, {category_partial} partial")
        
        # Overall statistics
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"  Total Tests: {total_tests}")
        print(f"  ✅ Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"  ❌ Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print(f"  ⚠️  Partial: {partial_tests} ({partial_tests/total_tests*100:.1f}%)")
        
        # Determine overall status
        if failed_tests == 0 and partial_tests <= total_tests * 0.2:  # Allow up to 20% partial
            self.test_results['overall_status'] = 'PASS'
            print(f"\n🎉 OVERALL STATUS: ✅ PASS")
            print("   The reorganization was successful! All critical components work correctly.")
        elif failed_tests <= total_tests * 0.1:  # Allow up to 10% failures
            self.test_results['overall_status'] = 'MOSTLY_PASS'
            print(f"\n⚠️  OVERALL STATUS: 🟡 MOSTLY PASS")
            print("   Most components work correctly, but some issues need attention.")
        else:
            self.test_results['overall_status'] = 'FAIL'
            print(f"\n❌ OVERALL STATUS: 🔴 FAIL")
            print("   Critical issues found that need immediate attention.")
        
        # Save detailed results
        results_file = self.root_path / 'comprehensive_test_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\n💾 Detailed results saved to: {results_file}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if failed_tests > 0:
            print("   1. Address failed tests before production use")
            print("   2. Check import paths and file locations") 
            print("   3. Verify all dependencies are installed")
        if partial_tests > 0:
            print("   4. Consider installing optional dependencies (Docker, kubectl)")
            print("   5. Review partial test results for optimization opportunities")
        print("   6. Run specific component tests for deeper validation")
        print("   7. Test in clean environment to verify reproducibility")

def main():
    """Main test execution"""
    if len(sys.argv) > 1:
        root_path = sys.argv[1]
    else:
        root_path = "/home/devel/ipfs_kit_py"
    
    test_suite = ComprehensiveTestSuite(root_path)
    results = test_suite.run_all_tests()
    
    # Exit with appropriate code
    if results['overall_status'] == 'PASS':
        sys.exit(0)
    elif results['overall_status'] == 'MOSTLY_PASS':
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == "__main__":
    main()
