#!/usr/bin/env python3
"""
Comprehensive Testing Script for ipfs_kit_py

This script runs a complete test suite for the ipfs_kit_py library while protecting
original files on disk. It follows these steps:
1. Creates backups of critical files
2. Runs comprehensive test suite
3. Analyzes test results
4. Restores original files if needed
5. Generates detailed report

Usage:
python comprehensive_test_with_backup.py [--restore-only] [--keep-backups]
"""

import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

# Configuration
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "safe_backups", 
                         datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
TEST_RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test-results",
                              datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
CRITICAL_PATHS = [
    "ipfs_kit_py/*.py",
    "ipfs_kit_py/**/*.py",
    "setup.py",
    "pyproject.toml",
    "requirements.txt",
    "pytest.ini",
]

# Report file
REPORT_FILE = os.path.join(TEST_RESULTS_DIR, "comprehensive_test_report.md")

class TestResult:
    """Class to store test result information"""
    def __init__(self, name, success, duration, message, output):
        self.name = name
        self.success = success
        self.duration = duration
        self.message = message
        self.output = output

def setup_directories():
    """Create backup and results directories"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
    print(f"Created backup directory: {BACKUP_DIR}")
    print(f"Created test results directory: {TEST_RESULTS_DIR}")

def backup_files():
    """Backup all critical files before testing"""
    print("\n=== Creating backups of critical files ===")
    files_backed_up = 0
    
    for path_pattern in CRITICAL_PATHS:
        for file_path in glob.glob(path_pattern, recursive=True):
            if os.path.isfile(file_path):
                # Create relative path structure in backup dir
                rel_path = os.path.relpath(file_path)
                backup_path = os.path.join(BACKUP_DIR, rel_path)
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                
                # Copy file with metadata
                shutil.copy2(file_path, backup_path)
                files_backed_up += 1
                print(f"  ✓ Backed up: {rel_path}")
    
    # Create a manifest of all backed up files
    with open(os.path.join(BACKUP_DIR, "backup_manifest.txt"), "w") as f:
        f.write(f"Backup created: {datetime.datetime.now().isoformat()}\n")
        f.write(f"Total files backed up: {files_backed_up}\n\n")
        for path_pattern in CRITICAL_PATHS:
            for file_path in glob.glob(path_pattern, recursive=True):
                if os.path.isfile(file_path):
                    rel_path = os.path.relpath(file_path)
                    f.write(f"{rel_path}\n")
    
    print(f"\nBackup complete: {files_backed_up} files saved to {BACKUP_DIR}")
    return files_backed_up

def restore_files(backup_dir=None):
    """Restore files from backup"""
    if backup_dir is None:
        # Find the latest backup directory
        backup_dirs = sorted(glob.glob(os.path.join(os.path.dirname(BACKUP_DIR), "*")))
        if not backup_dirs:
            print("No backup directories found.")
            return False
        backup_dir = backup_dirs[-1]
    
    if not os.path.exists(backup_dir):
        print(f"Backup directory does not exist: {backup_dir}")
        return False
    
    print(f"\n=== Restoring files from backup: {backup_dir} ===")
    
    # Read manifest if it exists
    manifest_path = os.path.join(backup_dir, "backup_manifest.txt")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            print(f.read())
    
    # Restore all files
    files_restored = 0
    for root, _, files in os.walk(backup_dir):
        for file in files:
            if file == "backup_manifest.txt":
                continue
                
            backup_path = os.path.join(root, file)
            rel_path = os.path.relpath(backup_path, backup_dir)
            original_path = rel_path
            
            # Skip if the path is backup_manifest.txt
            if rel_path == "backup_manifest.txt":
                continue
                
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(original_path), exist_ok=True)
            
            # Copy file with metadata
            shutil.copy2(backup_path, original_path)
            files_restored += 1
            print(f"  ✓ Restored: {rel_path}")
    
    print(f"\nRestore complete: {files_restored} files restored from {backup_dir}")
    return True

def find_test_files():
    """Find all test files in the repository"""
    test_files = []
    
    # Primary test directory
    for test_file in glob.glob("test/**/*.py", recursive=True):
        if os.path.basename(test_file).startswith("test_") and os.path.isfile(test_file):
            test_files.append(test_file)
    
    # Additional tests directory if it exists
    if os.path.exists("tests"):
        for test_file in glob.glob("tests/**/*.py", recursive=True):
            if os.path.basename(test_file).startswith("test_") and os.path.isfile(test_file):
                test_files.append(test_file)
    
    # Root directory tests
    for test_file in glob.glob("test_*.py"):
        if os.path.isfile(test_file):
            test_files.append(test_file)
    
    return sorted(test_files)

def run_pytest_all():
    """Run all tests using pytest"""
    result = {
        "success": False,
        "output": "",
        "message": ""
    }
    
    try:
        # Ensure we're using the virtualenv python
        cmd = [sys.executable, "-m", "pytest", "-xvs", "--color=yes"]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        result["output"] = process.stdout
        result["success"] = process.returncode == 0
        result["message"] = "All tests passed" if process.returncode == 0 else "Some tests failed"
    except Exception as e:
        result["output"] = str(e)
        result["message"] = f"Error running pytest: {str(e)}"
    
    return result

def run_single_test(test_file):
    """Run a single test file"""
    print(f"Running test: {test_file}")
    result = TestResult(
        name=test_file,
        success=False,
        duration=0,
        message="",
        output=""
    )
    
    start_time = time.time()
    try:
        # Ensure we're using the virtualenv python 
        cmd = [sys.executable, "-m", "pytest", "-xvs", test_file, "--color=yes"]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        result.output = process.stdout
        result.success = process.returncode == 0
        result.message = "Test passed" if process.returncode == 0 else "Test failed"
    except Exception as e:
        result.output = str(e)
        result.message = f"Error running test: {str(e)}"
    
    result.duration = time.time() - start_time
    return result

def run_comprehensive_tests():
    """Run a comprehensive suite of tests"""
    print("\n=== Running Comprehensive Test Suite ===")
    
    # List of all test results
    results = []
    
    # Find all test files
    test_files = find_test_files()
    print(f"Found {len(test_files)} test files")
    
    # Run each test file individually
    for test_file in test_files:
        result = run_single_test(test_file)
        results.append(result)
        
        # Save individual test output
        test_output_file = os.path.join(
            TEST_RESULTS_DIR, 
            f"test_output_{os.path.basename(test_file).replace('.py', '')}.txt"
        )
        with open(test_output_file, "w") as f:
            f.write(result.output)
        
        # Print status
        status = "✅ PASSED" if result.success else "❌ FAILED"
        print(f"  {status} {test_file} (in {result.duration:.2f}s)")
    
    # Generate summary
    success_count = sum(1 for r in results if r.success)
    print(f"\nTest Summary: {success_count} passed, {len(results) - success_count} failed")
    return results

def generate_report(results):
    """Generate a comprehensive test report"""
    print("\n=== Generating Test Report ===")
    
    success_count = sum(1 for r in results if r.success)
    failure_count = len(results) - success_count
    
    with open(REPORT_FILE, "w") as f:
        f.write(f"# Comprehensive Test Report\n\n")
        f.write(f"Generated: {datetime.datetime.now().isoformat()}\n\n")
        
        f.write(f"## Summary\n\n")
        f.write(f"- Total Tests: {len(results)}\n")
        f.write(f"- Passed: {success_count}\n")
        f.write(f"- Failed: {failure_count}\n")
        f.write(f"- Success Rate: {(success_count / len(results) * 100) if results else 0:.2f}%\n\n")
        
        f.write(f"## Test Details\n\n")
        for result in results:
            status = "✅ PASSED" if result.success else "❌ FAILED"
            f.write(f"### {status} {result.name}\n\n")
            f.write(f"- Duration: {result.duration:.2f}s\n")
            f.write(f"- Message: {result.message}\n")
            
            if not result.success:
                f.write(f"\n<details>\n<summary>Error Output</summary>\n\n")
                f.write("```\n")
                if len(result.output) > 5000:
                    f.write(result.output[:5000] + "...\n(output truncated)")
                else:
                    f.write(result.output)
                f.write("\n```\n</details>\n\n")
        
        # Generate failure summary
        if failure_count > 0:
            f.write(f"## Failed Tests Summary\n\n")
            for result in results:
                if not result.success:
                    f.write(f"- **{result.name}**: {result.message}\n")
    
    print(f"Report generated: {REPORT_FILE}")
    return REPORT_FILE

def run_module_imports_test():
    """Test if all modules can be imported correctly"""
    print("\n=== Testing Module Imports ===")
    
    module_results = []
    for module_file in glob.glob("ipfs_kit_py/**/*.py", recursive=True):
        if os.path.basename(module_file) == "__init__.py":
            continue
            
        module_path = module_file.replace("/", ".").replace(".py", "")
        
        result = TestResult(
            name=f"Import {module_path}",
            success=False,
            duration=0,
            message="",
            output=""
        )
        
        start_time = time.time()
        try:
            test_script = f"""
import sys
try:
    import {module_path}
    print(f"Successfully imported {module_path}")
    sys.exit(0)
except Exception as e:
    print(f"Error importing {module_path}: {{str(e)}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
            with tempfile.NamedTemporaryFile(suffix='.py', mode='w') as f:
                f.write(test_script)
                f.flush()
                
                process = subprocess.run(
                    [sys.executable, f.name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False
                )
                
                result.output = process.stdout
                result.success = process.returncode == 0
                result.message = f"Import successful" if process.returncode == 0 else f"Import failed"
        except Exception as e:
            result.output = str(e)
            result.message = f"Error testing import: {str(e)}"
        
        result.duration = time.time() - start_time
        module_results.append(result)
        
        # Print status
        status = "✅ PASSED" if result.success else "❌ FAILED"
        print(f"  {status} {module_path} (in {result.duration:.2f}s)")
    
    # Generate import test report
    success_count = sum(1 for r in module_results if r.success)
    print(f"\nImport Tests: {success_count} passed, {len(module_results) - success_count} failed")
    
    # Write import test results
    import_report_file = os.path.join(TEST_RESULTS_DIR, "import_test_report.md")
    with open(import_report_file, "w") as f:
        f.write("# Module Import Test Results\n\n")
        f.write(f"Generated: {datetime.datetime.now().isoformat()}\n\n")
        f.write(f"- Total Modules: {len(module_results)}\n")
        f.write(f"- Passed: {success_count}\n")
        f.write(f"- Failed: {len(module_results) - success_count}\n\n")
        
        for result in module_results:
            status = "✅ PASSED" if result.success else "❌ FAILED"
            f.write(f"## {status} {result.name}\n\n")
            
            if not result.success:
                f.write("```\n")
                f.write(result.output)
                f.write("\n```\n\n")
    
    return module_results

def check_code_quality():
    """Run code quality checks (flake8, pylint, etc.)"""
    print("\n=== Running Code Quality Checks ===")
    
    quality_results = []
    
    # Run flake8 if available
    result = TestResult(
        name="Flake8 Check",
        success=False,
        duration=0,
        message="",
        output=""
    )
    
    start_time = time.time()
    try:
        process = subprocess.run(
            [sys.executable, "-m", "flake8", "ipfs_kit_py", "--max-line-length=100"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        
        result.output = process.stdout
        result.success = process.returncode == 0
        result.message = "No code style issues" if process.returncode == 0 else "Code style issues found"
    except Exception as e:
        result.output = f"Error running flake8: {str(e)}\n{traceback.format_exc()}"
        result.message = f"Error running flake8"
    
    result.duration = time.time() - start_time
    quality_results.append(result)
    
    # Print status
    status = "✅ PASSED" if result.success else "❌ FAILED"
    print(f"  {status} {result.name} (in {result.duration:.2f}s)")
    
    # Save code quality results
    quality_report_file = os.path.join(TEST_RESULTS_DIR, "code_quality_report.md")
    with open(quality_report_file, "w") as f:
        f.write("# Code Quality Check Results\n\n")
        f.write(f"Generated: {datetime.datetime.now().isoformat()}\n\n")
        
        for result in quality_results:
            status = "PASSED" if result.success else "FAILED"
            f.write(f"## {result.name}: {status}\n\n")
            f.write(f"Duration: {result.duration:.2f}s\n\n")
            
            if result.output:
                f.write("```\n")
                f.write(result.output)
                f.write("\n```\n\n")
    
    return quality_results

def main():
    parser = argparse.ArgumentParser(description="Run comprehensive tests for ipfs_kit_py")
    parser.add_argument("--restore-only", action="store_true", help="Only restore files from backup")
    parser.add_argument("--keep-backups", action="store_true", help="Keep backup files after tests")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests (only backup)")
    
    args = parser.parse_args()
    
    if args.restore_only:
        restore_files()
        return
    
    try:
        # Create directories
        setup_directories()
        
        # Backup files
        files_backed_up = backup_files()
        
        if args.skip_tests:
            print("\nSkipping tests as requested with --skip-tests")
            return
        
        # Run comprehensive tests
        test_results = run_comprehensive_tests()
        
        # Run module import tests
        module_results = run_module_imports_test()
        
        # Check code quality
        quality_results = check_code_quality()
        
        # Generate comprehensive report
        report_file = generate_report(test_results)
        
        # Final summary
        test_success = sum(1 for r in test_results if r.success)
        module_success = sum(1 for r in module_results if r.success)
        quality_success = sum(1 for r in quality_results if r.success)
        
        print("\n=== Final Summary ===")
        print(f"Tests: {test_success}/{len(test_results)} passed")
        print(f"Module Imports: {module_success}/{len(module_results)} passed")
        print(f"Code Quality: {quality_success}/{len(quality_results)} passed")
        print(f"\nBackups created: {files_backed_up} files in {BACKUP_DIR}")
        print(f"Test report: {report_file}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        traceback.print_exc()
        print("\nAttempting to restore files from backup...")
        restore_files()
    
    # Clean up backups if not needed
    if not args.keep_backups:
        print("\nBackups no longer needed. To preserve them, use --keep-backups")
        # Uncomment to actually delete backups when tested and working properly
        # print(f"Removing backup directory: {BACKUP_DIR}")
        # shutil.rmtree(BACKUP_DIR, ignore_errors=True)

if __name__ == "__main__":
    main()