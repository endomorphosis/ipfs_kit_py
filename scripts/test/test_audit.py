#!/usr/bin/env python3
"""
Test Audit Script for Path C Phase 1.2
Runs each test file and documents status
"""
import subprocess
import sys
from pathlib import Path

def run_test_file(test_file):
    """Run a single test file and return status"""
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_file),
        "-v", "--timeout=30",
        "--tb=line",
        "-q"
    ]
    
    try:
        # Get repository root (two levels up from this script)
        repo_root = Path(__file__).resolve().parent.parent.parent
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(repo_root)
        )
        
        output = result.stdout + result.stderr
        
        # Parse output
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        skipped = output.count(" SKIPPED")
        errors = output.count(" ERROR")
        
        # Determine status
        if "ModuleNotFoundError" in output or "ImportError" in output:
            status = "IMPORT_ERROR"
            issue = "Import/Dependency"
        elif "TIMEOUT" in output:
            status = "TIMEOUT"
            issue = "Hangs/Timeout"
        elif failed > 0 or errors > 0:
            status = "FAIL"
            issue = "Test Failures"
        elif passed > 0:
            status = "PASS"
            issue = "None"
        elif skipped > 0:
            status = "SKIP"
            issue = "All Skipped"
        else:
            status = "UNKNOWN"
            issue = "Unknown"
        
        return {
            "file": test_file.name,
            "status": status,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "issue": issue,
            "output_snippet": output[:500] if status != "PASS" else ""
        }
        
    except subprocess.TimeoutExpired:
        return {
            "file": test_file.name,
            "status": "TIMEOUT",
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "issue": "Hangs/Timeout",
            "output_snippet": "Test execution timed out after 60s"
        }
    except Exception as e:
        return {
            "file": test_file.name,
            "status": "ERROR",
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 1,
            "issue": "Execution Error",
            "output_snippet": str(e)
        }

def main():
    """Run audit on all test files"""
    # Get repository root (two levels up from this script)
    repo_root = Path(__file__).resolve().parent.parent.parent
    test_dir = repo_root / "tests" / "unit"
    test_files = sorted(test_dir.glob("test_*.py"))
    
    print(f"Found {len(test_files)} test files to audit\n")
    print("=" * 80)
    
    results = []
    for i, test_file in enumerate(test_files, 1):
        print(f"\n[{i}/{len(test_files)}] Testing: {test_file.name}")
        result = run_test_file(test_file)
        results.append(result)
        
        status_emoji = {
            "PASS": "✅",
            "FAIL": "❌",
            "SKIP": "⏭️",
            "IMPORT_ERROR": "🚫",
            "TIMEOUT": "⏰",
            "ERROR": "💥",
            "UNKNOWN": "❓"
        }
        
        emoji = status_emoji.get(result["status"], "❓")
        print(f"  {emoji} {result['status']}: {result['passed']}P {result['failed']}F {result['skipped']}S - {result['issue']}")
        
        if result["status"] != "PASS" and result["output_snippet"]:
            print(f"  Issue: {result['output_snippet'][:200]}")
    
    # Summary
    print("\n" + "=" * 80)
    print("\nSUMMARY:")
    print("=" * 80)
    
    status_counts = {}
    for result in results:
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in sorted(status_counts.items()):
        print(f"{status:15s}: {count:3d} files")
    
    print(f"\n{'TOTAL':15s}: {len(results):3d} files")
    
    # Save detailed results
    output_file = repo_root / "test_audit_results.txt"
    with open(output_file, "w") as f:
        f.write("TEST AUDIT RESULTS\n")
        f.write("=" * 80 + "\n\n")
        
        for result in results:
            f.write(f"\nFile: {result['file']}\n")
            f.write(f"Status: {result['status']}\n")
            f.write(f"Tests: {result['passed']}P / {result['failed']}F / {result['skipped']}S / {result['errors']}E\n")
            f.write(f"Issue: {result['issue']}\n")
            if result["output_snippet"]:
                f.write(f"Details:\n{result['output_snippet']}\n")
            f.write("-" * 80 + "\n")
    
    print(f"\nDetailed results saved to: {output_file}")
    
    return results

if __name__ == "__main__":
    main()
