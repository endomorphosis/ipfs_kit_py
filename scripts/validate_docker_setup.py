#!/usr/bin/env python3
"""
Docker Multi-Architecture Validation Script

This script validates that the Docker multi-architecture support is working correctly.
It performs the following checks:

1. Docker is installed and functional
2. Dependency checker script exists and is executable
3. Docker entrypoint script exists and is executable
4. Dockerfile has proper multi-stage structure
5. Docker image can be built successfully
6. Container can run and import ipfs_kit_py
7. All documentation files are present

Usage:
    python scripts/validate_docker_setup.py [--build] [--verbose]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ValidationError(Exception):
    """Custom exception for validation failures."""
    pass


class DockerValidator:
    """Validate Docker multi-architecture setup."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.root_dir = Path(__file__).parent.parent
        self.results: List[Tuple[str, bool, str]] = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message if verbose mode is enabled."""
        if self.verbose or level in ["ERROR", "SUCCESS"]:
            prefix = {
                "INFO": "[INFO]",
                "ERROR": "[ERROR]",
                "SUCCESS": "[✓]",
                "WARNING": "[WARN]"
            }.get(level, "")
            print(f"{prefix} {message}")
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        """Record a test result."""
        self.results.append((test_name, passed, message))
        if passed:
            self.log(f"{test_name}: PASS", "SUCCESS")
        else:
            self.log(f"{test_name}: FAIL - {message}", "ERROR")
    
    def check_docker_installed(self) -> bool:
        """Check if Docker is installed and working."""
        self.log("Checking Docker installation...")
        
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            version = result.stdout.decode().strip()
            self.log(f"Found: {version}")
            self.add_result("Docker Installation", True, version)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.add_result("Docker Installation", False, "Docker not found or not responding")
            return False
    
    def check_docker_functional(self) -> bool:
        """Check if Docker can run containers."""
        self.log("Checking Docker functionality...")
        
        try:
            subprocess.run(
                ["docker", "run", "--rm", "hello-world"],
                capture_output=True,
                check=True,
                timeout=30
            )
            self.add_result("Docker Functionality", True)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            self.add_result("Docker Functionality", False, "Cannot run containers")
            return False
    
    def check_files_exist(self) -> bool:
        """Check if all required files exist."""
        self.log("Checking required files...")
        
        required_files = {
            "Dockerfile": self.root_dir / "Dockerfile",
            "docker-compose.yml": self.root_dir / "docker-compose.yml",
            "Dependency Checker": self.root_dir / "scripts" / "check_and_install_dependencies.py",
            "Docker Entrypoint": self.root_dir / "scripts" / "docker_entrypoint.sh",
            "Multi-Arch Test Script": self.root_dir / "scripts" / "test_docker_multiarch.sh",
            "Dependency Docs": self.root_dir / "DEPENDENCY_MANAGEMENT.md",
            "Docker Summary": self.root_dir / "DOCKER_MULTIARCH_SUMMARY.md",
            "Docker Quick Start": self.root_dir / "DOCKER_QUICK_START.md"
        }
        
        all_exist = True
        for name, path in required_files.items():
            exists = path.exists()
            if exists:
                self.log(f"  ✓ {name}: {path.name}")
            else:
                self.log(f"  ✗ {name}: {path.name} not found", "ERROR")
                all_exist = False
            self.add_result(f"File Exists: {name}", exists, str(path))
        
        return all_exist
    
    def check_scripts_executable(self) -> bool:
        """Check if scripts are executable."""
        self.log("Checking script permissions...")
        
        scripts = [
            self.root_dir / "scripts" / "check_and_install_dependencies.py",
            self.root_dir / "scripts" / "docker_entrypoint.sh",
            self.root_dir / "scripts" / "test_docker_multiarch.sh"
        ]
        
        all_executable = True
        for script in scripts:
            if script.exists():
                is_executable = os.access(script, os.X_OK)
                if is_executable:
                    self.log(f"  ✓ {script.name} is executable")
                else:
                    self.log(f"  ✗ {script.name} is not executable", "WARNING")
                    self.log(f"    Run: chmod +x {script}", "INFO")
                    all_executable = False
                self.add_result(f"Script Executable: {script.name}", is_executable)
        
        return all_executable
    
    def check_dockerfile_structure(self) -> bool:
        """Check if Dockerfile has proper multi-stage structure."""
        self.log("Checking Dockerfile structure...")
        
        dockerfile = self.root_dir / "Dockerfile"
        if not dockerfile.exists():
            self.add_result("Dockerfile Structure", False, "Dockerfile not found")
            return False
        
        content = dockerfile.read_text()
        
        required_stages = ["base", "builder", "production", "development", "testing"]
        missing_stages = []
        
        for stage in required_stages:
            if f"FROM base AS {stage}" in content or f"FROM python" in content and stage == "base":
                self.log(f"  ✓ Stage '{stage}' found")
            else:
                self.log(f"  ✗ Stage '{stage}' not found", "ERROR")
                missing_stages.append(stage)
        
        # Check for entrypoint
        has_entrypoint = "ENTRYPOINT" in content
        if has_entrypoint:
            self.log("  ✓ ENTRYPOINT directive found")
        else:
            self.log("  ✗ ENTRYPOINT directive not found", "WARNING")
        
        structure_ok = len(missing_stages) == 0
        self.add_result(
            "Dockerfile Structure",
            structure_ok,
            f"Missing stages: {missing_stages}" if missing_stages else "All stages present"
        )
        
        return structure_ok
    
    def check_dependency_checker(self) -> bool:
        """Test the dependency checker script."""
        self.log("Testing dependency checker...")
        
        script = self.root_dir / "scripts" / "check_and_install_dependencies.py"
        if not script.exists():
            self.add_result("Dependency Checker", False, "Script not found")
            return False
        
        try:
            result = subprocess.run(
                [sys.executable, str(script), "--dry-run"],
                capture_output=True,
                check=True,
                timeout=30,
                cwd=self.root_dir
            )
            
            output = result.stdout.decode() + result.stderr.decode()
            
            # Check for key outputs
            checks = {
                "Platform Detection": "Detected platform:" in output,
                "Python Check": "Python version" in output,
                "Summary": "Summary" in output
            }
            
            for check_name, passed in checks.items():
                self.log(f"  {check_name}: {'✓' if passed else '✗'}")
            
            all_passed = all(checks.values())
            self.add_result("Dependency Checker", all_passed)
            return all_passed
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self.add_result("Dependency Checker", False, str(e))
            return False
    
    def build_docker_image(self, tag: str = "ipfs-kit-py:validation") -> bool:
        """Build Docker image for validation."""
        self.log(f"Building Docker image: {tag}...")
        
        try:
            result = subprocess.run(
                [
                    "docker", "build",
                    "--target", "production",
                    "-t", tag,
                    "."
                ],
                capture_output=True,
                check=True,
                timeout=600,
                cwd=self.root_dir
            )
            
            self.log("Build completed successfully")
            self.add_result("Docker Build", True)
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Build failed: {e.stderr.decode()}", "ERROR")
            self.add_result("Docker Build", False, "Build failed")
            return False
        except subprocess.TimeoutExpired:
            self.log("Build timed out after 10 minutes", "ERROR")
            self.add_result("Docker Build", False, "Build timeout")
            return False
    
    def test_docker_image(self, tag: str = "ipfs-kit-py:validation") -> bool:
        """Test the built Docker image."""
        self.log(f"Testing Docker image: {tag}...")
        
        tests = [
            (
                "Import Test",
                ["python", "-c", "import ipfs_kit_py; print('OK')"]
            ),
            (
                "Platform Detection",
                ["python", "-c", "import platform; print(f'{platform.system()} {platform.machine()}')"]
            ),
            (
                "Dependency Checker",
                ["python", "/app/scripts/check_and_install_dependencies.py", "--dry-run"]
            )
        ]
        
        all_passed = True
        for test_name, command in tests:
            try:
                result = subprocess.run(
                    ["docker", "run", "--rm", tag] + command,
                    capture_output=True,
                    check=True,
                    timeout=30
                )
                
                output = result.stdout.decode() + result.stderr.decode()
                self.log(f"  ✓ {test_name}")
                if self.verbose:
                    self.log(f"    Output: {output.strip()}", "INFO")
                
                self.add_result(f"Container Test: {test_name}", True)
                
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                self.log(f"  ✗ {test_name}", "ERROR")
                self.add_result(f"Container Test: {test_name}", False, str(e))
                all_passed = False
        
        return all_passed
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for _, result, _ in self.results if result)
        total = len(self.results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {passed/total*100:.1f}%\n")
        
        if passed < total:
            print("Failed Tests:")
            for name, result, message in self.results:
                if not result:
                    print(f"  ✗ {name}")
                    if message:
                        print(f"    {message}")
        
        print("=" * 70)
        
        return passed == total
    
    def run_all_checks(self, build: bool = False) -> bool:
        """Run all validation checks."""
        print("=" * 70)
        print("Docker Multi-Architecture Validation")
        print("=" * 70)
        print()
        
        # File checks (always run)
        self.check_files_exist()
        self.check_scripts_executable()
        self.check_dockerfile_structure()
        
        # Dependency checker test (always run)
        self.check_dependency_checker()
        
        # Docker checks (optional based on Docker availability)
        docker_available = self.check_docker_installed()
        
        if docker_available:
            self.check_docker_functional()
            
            # Build and test (only if requested)
            if build:
                if self.build_docker_image():
                    self.test_docker_image()
        else:
            self.log("Skipping Docker-based tests (Docker not available)", "WARNING")
        
        # Print summary
        return self.print_summary()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Docker multi-architecture setup"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build and test Docker image (takes longer)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    validator = DockerValidator(verbose=args.verbose)
    success = validator.run_all_checks(build=args.build)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
