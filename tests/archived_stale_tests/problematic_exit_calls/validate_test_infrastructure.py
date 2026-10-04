#!/usr/bin/env python3
"""
Test Infrastructure Validation
=============================

Quick validation script to ensure the test infrastructure is properly set up.
"""

import os
import sys
import subprocess
from pathlib import Path


def validate_test_files():
    """Validate that test files exist and are importable"""
    print("🔍 Validating test files...")
    
    test_files = [
        "tests/test_cluster_services.py",
        "tests/test_vfs_integration.py", 
        "tests/test_http_api_integration.py"
    ]
    
    project_root = Path(__file__).parent
    
    for test_file in test_files:
        file_path = project_root / test_file
        if not file_path.exists():
            print(f"❌ Missing test file: {test_file}")
            return False
        
        # Check if the file is importable
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import sys; sys.path.insert(0, '.'); exec(open('{file_path}').read())"],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            if result.returncode != 0:
                print(f"❌ Test file has syntax errors: {test_file}")
                print(f"   Error: {result.stderr}")
                return False
            else:
                print(f"✅ Test file valid: {test_file}")
                
        except Exception as e:
            print(f"❌ Error validating {test_file}: {e}")
            return False
    
    return True


def validate_test_discovery():
    """Validate that pytest can discover the tests"""
    print("\n🔍 Validating test discovery...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            test_count = 0
            for line in lines:
                if 'test session starts' in line.lower() or 'collected' in line.lower():
                    continue
                if '::' in line and 'test_' in line:
                    test_count += 1
            
            print(f"✅ Test discovery successful: {test_count} tests found")
            return True
        else:
            print(f"❌ Test discovery failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Test discovery timed out")
        return False
    except Exception as e:
        print(f"❌ Error during test discovery: {e}")
        return False


def validate_dependencies():
    """Validate that required dependencies are available"""
    print("\n🔍 Validating dependencies...")
    
    required_deps = [
        "pytest",
        ("pytest-" "async" "io"),
        "enhanced_daemon_manager_with_cluster",
        "ipfs_fsspec"
    ]
    
    for dep in required_deps:
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {dep}"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ Dependency available: {dep}")
            else:
                print(f"❌ Dependency not available: {dep}")
                return False
        except Exception as e:
            print(f"❌ Error checking dependency {dep}: {e}")
            return False
    
    return True


def validate_ci_workflow():
    """Validate that CI workflow files are properly configured"""
    print("\n🔍 Validating CI workflow files...")
    
    workflow_files = [
        ".github/workflows/run-tests.yml",
        ".github/workflows/cluster-tests.yml"
    ]
    
    project_root = Path(__file__).parent
    
    for workflow_file in workflow_files:
        file_path = project_root / workflow_file
        if not file_path.exists():
            print(f"❌ Missing workflow file: {workflow_file}")
            return False
        
        # Basic syntax validation
        try:
            import yaml
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            print(f"✅ Workflow file valid: {workflow_file}")
        except Exception as e:
            print(f"❌ Workflow file has errors: {workflow_file}")
            print(f"   Error: {e}")
            return False
    
    return True


def run_sample_tests():
    """Run a small sample of tests to verify functionality"""
    print("\n🔍 Running sample tests...")
    
    sample_tests = [
        "tests/test_cluster_services.py::TestNodeRole::test_role_values",
        "tests/test_vfs_integration.py::TestIPFSFileSystemIntegration::test_fs_initialization"
    ]
    
    for test in sample_tests:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test, "-v"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✅ Sample test passed: {test}")
            else:
                print(f"❌ Sample test failed: {test}")
                print(f"   Output: {result.stdout}")
                print(f"   Error: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"❌ Sample test timed out: {test}")
            return False
        except Exception as e:
            print(f"❌ Error running sample test {test}: {e}")
            return False
    
    return True


def main():
    """Main validation function"""
    print("=" * 60)
    print("TEST INFRASTRUCTURE VALIDATION")
    print("=" * 60)
    
    validations = [
        ("Test Files", validate_test_files),
        ("Test Discovery", validate_test_discovery),
        ("Dependencies", validate_dependencies),
        ("CI Workflows", validate_ci_workflow),
        ("Sample Tests", run_sample_tests)
    ]
    
    all_passed = True
    
    for name, validation_func in validations:
        try:
            if not validation_func():
                all_passed = False
        except Exception as e:
            print(f"❌ Validation '{name}' failed with exception: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    if all_passed:
        print("✅ All validations passed!")
        print("🚀 Test infrastructure is ready for use.")
        print("\nNext steps:")
        print("1. Run comprehensive tests: python run_comprehensive_tests.py")
        print("2. Run specific test suites: python -m pytest tests/test_cluster_services.py -v")
        print("3. Check CI/CD integration in GitHub Actions")
        sys.exit(0)
    else:
        print("❌ Some validations failed!")
        print("🔧 Please fix the issues above before running tests.")
        sys.exit(1)


if __name__ == "__main__":
    main()
