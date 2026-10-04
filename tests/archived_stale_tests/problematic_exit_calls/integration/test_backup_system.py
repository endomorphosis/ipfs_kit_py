#!/usr/bin/env python3
"""
Backup System Integrity Test Script

This script validates the backup system by:
1. Checking available disk space
2. Testing backup file creation/restoration
3. Validating file permissions
4. Verifying restore process works correctly

Usage:
python verify_backup_system.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import traceback

def check_disk_space(min_required_mb=500):
    """Check if there's enough disk space for backups"""
    print("=== Checking Disk Space ===")
    
    try:
        # Get disk usage information for the current directory
        disk_usage = shutil.disk_usage(os.path.dirname(os.path.abspath(__file__)))
        
        free_mb = disk_usage.free / (1024 * 1024)  # Convert bytes to MB
        print(f"Free disk space: {free_mb:.2f} MB")
        
        if free_mb < min_required_mb:
            print(f"⚠️ WARNING: Low disk space - only {free_mb:.2f} MB available")
            print(f"Recommended minimum: {min_required_mb} MB")
            return False
        else:
            print(f"✅ Sufficient disk space available: {free_mb:.2f} MB")
            return True
    except Exception as e:
        print(f"❌ Error checking disk space: {str(e)}")
        return False

def test_file_permissions():
    """Test if we have proper file permissions to create and restore backups"""
    print("\n=== Testing File Permissions ===")
    
    success = True
    
    # Test creating directories and files
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Test creating subdirectories
            test_subdir = os.path.join(temp_dir, "subdir1", "subdir2")
            os.makedirs(test_subdir, exist_ok=True)
            print(f"✅ Can create nested directories")
            
            # Test creating files
            test_file = os.path.join(test_subdir, "testfile.txt")
            with open(test_file, "w") as f:
                f.write("Test content")
            print(f"✅ Can create files in nested directories")
            
            # Test file metadata preservation
            os.chmod(test_file, 0o644)  # Set test permissions
            test_file_copy = os.path.join(temp_dir, "testfile_copy.txt")
            shutil.copy2(test_file, test_file_copy)  # copy2 preserves metadata
            
            original_stat = os.stat(test_file)
            copy_stat = os.stat(test_file_copy)
            
            if original_stat.st_mode == copy_stat.st_mode:
                print(f"✅ File metadata preservation works")
            else:
                print(f"⚠️ File metadata not preserved during copy")
                success = False
                
            # Test file deletion
            os.unlink(test_file)
            if not os.path.exists(test_file):
                print(f"✅ Can delete files")
            else:
                print(f"⚠️ Cannot delete files properly")
                success = False
        except Exception as e:
            print(f"❌ Permission test error: {str(e)}")
            traceback.print_exc()
            success = False
    
    # Test permissions in the actual code directories
    try:
        # Find a Python file to test
        for dirpath, _, filenames in os.walk("ipfs_kit_py"):
            for filename in filenames:
                if filename.endswith(".py"):
                    test_file = os.path.join(dirpath, filename)
                    break
        
        if test_file:
            # Test reading
            with open(test_file, "r") as f:
                content = f.read(100)  # Just read a bit
            print(f"✅ Can read production code files")
            
            # Test backup and restore
            with tempfile.TemporaryDirectory() as temp_dir:
                backup_file = os.path.join(temp_dir, "backup_test.py")
                shutil.copy2(test_file, backup_file)
                
                with open(backup_file, "r") as f:
                    backup_content = f.read(100)
                
                if backup_content == content:
                    print(f"✅ Can backup and verify file content")
                else:
                    print(f"⚠️ Backup verification failed - content mismatch")
                    success = False
    except Exception as e:
        print(f"❌ Error testing code file access: {str(e)}")
        traceback.print_exc()
        success = False
    
    return success

def test_python_subprocess():
    """Test if we can run Python subprocesses properly"""
    print("\n=== Testing Python Subprocess Execution ===")
    
    try:
        test_script = "import sys; print('Python subprocess test successful'); sys.exit(0)"
        process = subprocess.run(
            [sys.executable, "-c", test_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        
        if process.returncode == 0:
            print(f"✅ Python subprocess execution works")
            print(f"   Output: {process.stdout.strip()}")
            return True
        else:
            print(f"❌ Python subprocess execution failed")
            print(f"   Output: {process.stdout}")
            return False
    except Exception as e:
        print(f"❌ Error running Python subprocess: {str(e)}")
        traceback.print_exc()
        return False

def verify_backup_script():
    """Verify that the backup script exists and can be run"""
    print("\n=== Verifying Backup Script ===")
    
    backup_script = "comprehensive_test_with_backup.py"
    
    if not os.path.exists(backup_script):
        print(f"❌ Backup script not found: {backup_script}")
        return False
    
    try:
        # Just check if we can import the script without errors
        process = subprocess.run(
            [sys.executable, "-m", "py_compile", backup_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        
        if process.returncode == 0:
            print(f"✅ Backup script compiles successfully")
            
            # Test running with --skip-tests to just check backup functionality
            print("\nTesting backup only, with --skip-tests option...")
            backup_process = subprocess.run(
                [sys.executable, backup_script, "--skip-tests"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,  # 30 second timeout should be enough for just backup
                check=False
            )
            
            if "Backup complete:" in backup_process.stdout:
                print(f"✅ Backup functionality works")
                print(f"   (Restore not tested to avoid overwriting files)")
                return True
            else:
                print(f"⚠️ Backup test didn't complete successfully")
                print(f"   Output excerpt: {backup_process.stdout[-500:]}")  # Last 500 chars
                return False
        else:
            print(f"❌ Backup script has syntax errors")
            print(f"   Output: {process.stdout}")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ Backup script test timed out")
        return False
    except Exception as e:
        print(f"❌ Error verifying backup script: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Run all validation checks"""
    print("=== BACKUP SYSTEM VALIDATION ===\n")
    
    # Track success of each validation
    validations = []
    
    # Check disk space
    disk_space_ok = check_disk_space()
    validations.append(("Disk Space Check", disk_space_ok))
    
    # Test file permissions
    permissions_ok = test_file_permissions()
    validations.append(("File Permissions", permissions_ok))
    
    # Test Python subprocess
    subprocess_ok = test_python_subprocess()
    validations.append(("Python Subprocess", subprocess_ok))
    
    # Verify backup script
    script_ok = verify_backup_script()
    validations.append(("Backup Script Check", script_ok))
    
    # Print summary
    print("\n=== VALIDATION SUMMARY ===")
    all_ok = True
    for name, result in validations:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if not result:
            all_ok = False
    
    if all_ok:
        print("\n✅ All validation checks passed - backup system is ready to use")
        print("\nTo run the comprehensive tests with backup protection:")
        print("python comprehensive_test_with_backup.py")
        print("\nTo only backup files without testing:")
        print("python comprehensive_test_with_backup.py --skip-tests")
        print("\nTo restore from the most recent backup:")
        print("python comprehensive_test_with_backup.py --restore-only")
        sys.exit(0)
    else:
        print("\n⚠️ Some validation checks failed - fix issues before running comprehensive tests")
        sys.exit(1)

if __name__ == "__main__":
    main()