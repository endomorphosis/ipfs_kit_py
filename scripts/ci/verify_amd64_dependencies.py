#!/usr/bin/env python3
"""
AMD64 Dependency Verification Script

This script verifies that all required dependencies for AMD64 builds are properly
installed and configured. It checks binaries, Python packages, and build tools.
"""

import os
import sys
import json
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Tuple


class DependencyVerifier:
    """Verify AMD64 dependencies."""
    
    REQUIRED_BINARIES = {
        "gcc": "C compiler for building from source",
        "g++": "C++ compiler for building from source",
        "make": "Build automation tool",
        "git": "Version control for cloning repositories",
    }
    
    OPTIONAL_BINARIES = {
        "go": "Go compiler for building IPFS/Lotus from source",
        "ipfs": "IPFS daemon",
        "lotus": "Lotus daemon",
        "lassie": "Lassie retrieval client",
    }
    
    REQUIRED_PYTHON_PACKAGES = [
        "setuptools",
        "wheel",
        "pip",
    ]
    
    OPTIONAL_PYTHON_PACKAGES = [
        "ipfs_kit_py",
        "pytest",
        "requests",
    ]
    
    def __init__(self):
        self.results = {
            "system_info": self._get_system_info(),
            "binaries": {},
            "python_packages": {},
            "summary": {
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0
            }
        }
        
    def _get_system_info(self) -> Dict:
        """Get system information."""
        return {
            "architecture": platform.machine(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "is_amd64": platform.machine() in ["aarch64", "amd64"]
        }
        
    def check_binary(self, name: str, version_flag: str = "--version") -> Dict:
        """Check if a binary is installed and get version info."""
        result = {
            "name": name,
            "installed": False,
            "path": None,
            "version": None,
            "status": "missing"
        }
        
        try:
            # Check if binary exists
            which_result = subprocess.run(
                ["which", name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if which_result.returncode == 0:
                result["installed"] = True
                result["path"] = which_result.stdout.strip()
                
                # Try to get version
                try:
                    version_result = subprocess.run(
                        [name, version_flag],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if version_result.returncode == 0:
                        result["version"] = version_result.stdout.strip().split('\n')[0]
                        result["status"] = "installed"
                    else:
                        result["status"] = "installed_no_version"
                        
                except subprocess.TimeoutExpired:
                    result["status"] = "installed_version_timeout"
                    
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "error"
            
        return result
        
    def check_python_package(self, name: str) -> Dict:
        """Check if a Python package is installed."""
        result = {
            "name": name,
            "installed": False,
            "version": None,
            "status": "missing"
        }
        
        try:
            import importlib.metadata
            version = importlib.metadata.version(name)
            result["installed"] = True
            result["version"] = version
            result["status"] = "installed"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "missing"
            
        return result
        
    def verify_build_environment(self) -> bool:
        """Verify that the build environment is properly set up."""
        print("\n" + "="*70)
        print("AMD64 Build Environment Verification")
        print("="*70 + "\n")
        
        # Check system
        print("System Information:")
        for key, value in self.results["system_info"].items():
            print(f"  {key}: {value}")
        print()
        
        if not self.results["system_info"]["is_amd64"]:
            print("⚠️  WARNING: Not running on AMD64 architecture!")
            print(f"   Detected: {self.results['system_info']['architecture']}")
            print()
            
        # Check required binaries
        print("Required Build Tools:")
        all_required_ok = True
        
        for binary, description in self.REQUIRED_BINARIES.items():
            result = self.check_binary(binary)
            self.results["binaries"][binary] = result
            self.results["summary"]["total_checks"] += 1
            
            if result["installed"]:
                print(f"  ✅ {binary}: {result['version'] or result['path']}")
                self.results["summary"]["passed"] += 1
            else:
                print(f"  ❌ {binary}: NOT FOUND ({description})")
                self.results["summary"]["failed"] += 1
                all_required_ok = False
                
        print()
        
        # Check optional binaries
        print("Optional Tools:")
        for binary, description in self.OPTIONAL_BINARIES.items():
            result = self.check_binary(binary)
            self.results["binaries"][binary] = result
            self.results["summary"]["total_checks"] += 1
            
            if result["installed"]:
                print(f"  ✅ {binary}: {result['version'] or result['path']}")
                self.results["summary"]["passed"] += 1
            else:
                print(f"  ⚠️  {binary}: not found ({description})")
                self.results["summary"]["warnings"] += 1
                
        print()
        
        # Check required Python packages
        print("Required Python Packages:")
        for package in self.REQUIRED_PYTHON_PACKAGES:
            result = self.check_python_package(package)
            self.results["python_packages"][package] = result
            self.results["summary"]["total_checks"] += 1
            
            if result["installed"]:
                print(f"  ✅ {package}: {result['version']}")
                self.results["summary"]["passed"] += 1
            else:
                print(f"  ❌ {package}: NOT FOUND")
                self.results["summary"]["failed"] += 1
                all_required_ok = False
                
        print()
        
        # Check optional Python packages
        print("Optional Python Packages:")
        for package in self.OPTIONAL_PYTHON_PACKAGES:
            result = self.check_python_package(package)
            self.results["python_packages"][package] = result
            self.results["summary"]["total_checks"] += 1
            
            if result["installed"]:
                print(f"  ✅ {package}: {result['version']}")
                self.results["summary"]["passed"] += 1
            else:
                print(f"  ⚠️  {package}: not found")
                self.results["summary"]["warnings"] += 1
                
        print()
        
        # Summary
        print("="*70)
        print("Verification Summary:")
        print(f"  Total Checks: {self.results['summary']['total_checks']}")
        print(f"  ✅ Passed: {self.results['summary']['passed']}")
        print(f"  ❌ Failed: {self.results['summary']['failed']}")
        print(f"  ⚠️  Warnings: {self.results['summary']['warnings']}")
        print("="*70 + "\n")
        
        return all_required_ok
        
    def save_results(self, output_file: str = "/tmp/dependency_verification.json"):
        """Save verification results to a JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"Results saved to: {output_path}")
        
    def add_to_github_summary(self):
        """Add verification results to GitHub Actions summary."""
        if "GITHUB_STEP_SUMMARY" not in os.environ:
            return
            
        summary_file = os.environ["GITHUB_STEP_SUMMARY"]
        
        with open(summary_file, 'a') as f:
            f.write("\n## AMD64 Dependency Verification\n\n")
            
            # System info
            f.write("### System Information\n")
            for key, value in self.results["system_info"].items():
                f.write(f"- **{key}**: {value}\n")
            f.write("\n")
            
            # Required binaries
            f.write("### Required Build Tools\n")
            for binary, result in self.results["binaries"].items():
                if binary in self.REQUIRED_BINARIES:
                    status = "✅" if result["installed"] else "❌"
                    version = result.get("version", result.get("path", "N/A"))
                    f.write(f"- {status} **{binary}**: {version}\n")
            f.write("\n")
            
            # Optional binaries
            f.write("### Optional Tools\n")
            for binary, result in self.results["binaries"].items():
                if binary in self.OPTIONAL_BINARIES:
                    status = "✅" if result["installed"] else "⚠️"
                    version = result.get("version", result.get("path", "not found"))
                    f.write(f"- {status} **{binary}**: {version}\n")
            f.write("\n")
            
            # Summary
            f.write("### Summary\n")
            f.write(f"- **Total Checks**: {self.results['summary']['total_checks']}\n")
            f.write(f"- **✅ Passed**: {self.results['summary']['passed']}\n")
            f.write(f"- **❌ Failed**: {self.results['summary']['failed']}\n")
            f.write(f"- **⚠️ Warnings**: {self.results['summary']['warnings']}\n")


def main():
    """Main verification workflow."""
    verifier = DependencyVerifier()
    
    # Run verification
    success = verifier.verify_build_environment()
    
    # Save results
    verifier.save_results()
    
    # Add to GitHub Actions summary
    verifier.add_to_github_summary()
    
    # Exit with appropriate code
    if success:
        print("✅ All required dependencies are installed")
        return 0
    else:
        print("❌ Some required dependencies are missing")
        return 1


if __name__ == "__main__":
    sys.exit(main())
