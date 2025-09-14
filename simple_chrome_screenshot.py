#!/usr/bin/env python3
"""
Simple Chrome Screenshot Tool

Uses Chrome headless to capture dashboard screenshots and analyze CSS issues.
"""

import subprocess
import time
import json
import os
from pathlib import Path

def take_chrome_screenshot():
    """Take screenshot using Chrome headless and analyze the dashboard."""
    
    # Create screenshots directory
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    
    dashboard_url = "http://127.0.0.1:8004"
    screenshot_path = screenshots_dir / "current_dashboard_chrome.png"
    
    print(f"Taking screenshot of {dashboard_url}...")
    
    # Chrome headless command
    chrome_cmd = [
        "google-chrome", 
        "--headless", 
        "--no-sandbox", 
        "--disable-gpu",
        "--window-size=1920,1080",
        f"--screenshot={screenshot_path}",
        "--virtual-time-budget=5000",  # Wait 5 seconds for page load
        dashboard_url
    ]
    
    try:
        result = subprocess.run(chrome_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ Screenshot saved: {screenshot_path}")
            file_size = screenshot_path.stat().st_size
            print(f"📏 File size: {file_size:,} bytes")
        else:
            print(f"❌ Chrome error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Chrome screenshot timed out")
        return False
    except FileNotFoundError:
        print("❌ Google Chrome not found, trying chromium...")
        # Try with chromium
        chrome_cmd[0] = "chromium-browser"
        try:
            result = subprocess.run(chrome_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✅ Screenshot saved: {screenshot_path}")
                file_size = screenshot_path.stat().st_size
                print(f"📏 File size: {file_size:,} bytes")
            else:
                print(f"❌ Chromium error: {result.stderr}")
                return False
        except FileNotFoundError:
            print("❌ Neither Chrome nor Chromium found")
            return False
    
    # Also get page source for analysis
    source_cmd = [
        "google-chrome",
        "--headless", 
        "--no-sandbox",
        "--disable-gpu",
        "--dump-dom",
        "--virtual-time-budget=5000",
        dashboard_url
    ]
    
    try:
        source_result = subprocess.run(source_cmd, capture_output=True, text=True, timeout=30)
        if source_result.returncode == 0:
            source_path = screenshots_dir / "dashboard_source.html"
            with open(source_path, "w") as f:
                f.write(source_result.stdout)
            print(f"📄 Page source saved: {source_path}")
            
            # Analyze the source for PR #38 elements
            source = source_result.stdout
            
            print("\n🔍 Analyzing dashboard for PR #38 compatibility...")
            
            pr38_checks = {
                "🚀 Rocket Emoji": "🚀" in source,
                "IPFS Kit Title": "IPFS Kit" in source,
                "Light Theme Background": "#f5f5f5" in source or "rgb(245, 245, 245)" in source,
                "Overview Tab": "Overview" in source,
                "Services Tab": "Services" in source,
                "Backends Tab": "Backends" in source,
                "Pin Management": "Pin Management" in source or "Pins" in source,
                "Comprehensive Subtitle": "Comprehensive" in source,
                "MCP Server Active": "MCP Server" in source or "mcp" in source.lower(),
            }
            
            print("\nPR #38 Compatibility Check:")
            passed = 0
            for check, result in pr38_checks.items():
                status = "✅" if result else "❌"
                print(f"{status} {check}")
                if result:
                    passed += 1
            
            score = (passed / len(pr38_checks)) * 100
            print(f"\n📊 Compatibility Score: {passed}/{len(pr38_checks)} ({score:.1f}%)")
            
            # Check for dark theme indicators (problematic)
            dark_indicators = [
                "background-color: #1a1a1a",
                "background-color: rgb(26, 26, 26)", 
                "background: #1a1a1a",
                "bg-gray-900",
                "dark-theme",
                "background-color: black",
                "background-color: #000"
            ]
            
            dark_theme_detected = any(indicator in source for indicator in dark_indicators)
            if dark_theme_detected:
                print("⚠️  DARK THEME DETECTED - This does NOT match PR #38!")
                for indicator in dark_indicators:
                    if indicator in source:
                        print(f"   Found: {indicator}")
            else:
                print("✅ No dark theme indicators found")
            
            # Save analysis
            analysis_path = screenshots_dir / "pr38_compatibility_analysis.md"
            with open(analysis_path, "w") as f:
                f.write(f"# PR #38 Compatibility Analysis\n\n")
                f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"## Compatibility Results\n")
                f.write(f"**Score:** {score:.1f}% ({passed}/{len(pr38_checks)})\n\n")
                for check, result in pr38_checks.items():
                    status = "✅ PASS" if result else "❌ FAIL"
                    f.write(f"- **{check}:** {status}\n")
                f.write(f"\n## Dark Theme Detection\n")
                if dark_theme_detected:
                    f.write("❌ **DARK THEME DETECTED** - Does NOT match PR #38\n")
                    f.write("### Found indicators:\n")
                    for indicator in dark_indicators:
                        if indicator in source:
                            f.write(f"- `{indicator}`\n")
                else:
                    f.write("✅ **No dark theme indicators** - Matches PR #38 light theme\n")
            
            print(f"📋 Analysis report saved: {analysis_path}")
            
            if score < 70:
                print(f"\n🚨 CRITICAL: Dashboard does NOT match PR #38 ({score:.1f}% compatibility)")
                print("   This confirms PR #39 reorganization caused styling issues")
                return False
            elif score < 90:
                print(f"\n⚠️  WARNING: Dashboard partially matches PR #38 ({score:.1f}% compatibility)")
                print("   Some elements may need fixing")
                return True
            else:
                print(f"\n✅ SUCCESS: Dashboard matches PR #38 expectations ({score:.1f}% compatibility)")
                return True
        else:
            print(f"❌ Failed to get page source: {source_result.stderr}")
            
    except Exception as e:
        print(f"❌ Error analyzing page source: {e}")
    
    return True

if __name__ == "__main__":
    success = take_chrome_screenshot()
    if success:
        print("\n✅ Screenshot capture completed successfully")
    else:
        print("\n❌ Screenshot capture failed or revealed issues")