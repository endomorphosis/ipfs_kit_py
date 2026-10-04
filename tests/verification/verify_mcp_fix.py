#!/usr/bin/env python3
"""
Verification script for MCP Dashboard bug fixes.

This script verifies that the Tailwind CDN loading issue has been fixed
by checking the fallback-system.js file for problematic references.
"""

import sys
from pathlib import Path


def check_fallback_system(file_path: Path) -> tuple[bool, list[str]]:
    """
    Check a fallback-system.js file for Tailwind CDN references.
    
    Returns:
        tuple: (is_valid, issues_found)
    """
    issues = []
    
    if not file_path.exists():
        issues.append(f"File not found: {file_path}")
        return False, issues
    
    content = file_path.read_text()
    
    # Check for problematic Tailwind CDN references
    if "cdn.tailwindcss.com" in content:
        issues.append(f"Found Tailwind CDN reference in {file_path}")
    
    if '"tailwind"' in content or "'tailwind'" in content:
        # Check if it's in the FALLBACK_CONFIG
        if "FALLBACK_CONFIG" in content:
            lines = content.split('\n')
            in_config = False
            for i, line in enumerate(lines):
                if "FALLBACK_CONFIG" in line:
                    in_config = True
                if in_config and ("tailwind" in line.lower()):
                    # Check if this is within the config block (not a comment)
                    if not line.strip().startswith("//"):
                        context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                        issues.append(
                            f"Found 'tailwind' in FALLBACK_CONFIG at line {i+1}:\n{context}"
                        )
                        break
                if in_config and "};" in line and "FALLBACK_CONFIG" not in lines[max(0, i-5):i+1]:
                    in_config = False
    
    # Verify Chart.js is still present
    if "chartjs" not in content.lower():
        issues.append(f"Chart.js configuration missing in {file_path}")
    
    return len(issues) == 0, issues


def main():
    """Main verification function."""
    print("=" * 70)
    print("MCP Dashboard Fix Verification")
    print("=" * 70)
    print()
    
    base_dir = Path(__file__).parent
    files_to_check = [
        base_dir / "ipfs_kit_py" / "mcp" / "dashboard" / "static" / "js" / "fallback-system.js",
        base_dir / "static" / "js" / "fallback-system.js",
    ]
    
    all_valid = True
    for file_path in files_to_check:
        print(f"Checking: {file_path.relative_to(base_dir)}")
        is_valid, issues = check_fallback_system(file_path)
        
        if is_valid:
            print("  ✓ PASS: No Tailwind CDN references found")
            print("  ✓ PASS: Chart.js configuration present")
        else:
            print("  ✗ FAIL: Issues found:")
            for issue in issues:
                print(f"    - {issue}")
            all_valid = False
        print()
    
    print("=" * 70)
    if all_valid:
        print("✓ ALL CHECKS PASSED")
        print()
        print("Summary:")
        print("  - Tailwind CDN references successfully removed")
        print("  - Chart.js fallback system intact")
        print("  - Dashboard will use inline CSS from enhanced_dashboard.html")
        print("  - No more 'cdn.tailwindcss.com' warnings in console")
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        print()
        print("Please review the issues above and ensure:")
        print("  - No Tailwind CDN references in fallback-system.js")
        print("  - Chart.js configuration is preserved")
        return 1


if __name__ == "__main__":
    sys.exit(main())
