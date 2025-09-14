#!/usr/bin/env python3

import subprocess
import time
import os
from datetime import datetime
import json

def take_chrome_screenshot():
    """Take a screenshot using Chrome headless"""
    
    # Create screenshots directory
    screenshots_dir = "/home/runner/work/ipfs_kit_py/ipfs_kit_py/screenshots"
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Dashboard URL
    dashboard_url = "http://127.0.0.1:8004"
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(screenshots_dir, f"dashboard_screenshot_{timestamp}.png")
    
    try:
        print(f"Taking screenshot of {dashboard_url}...")
        
        # Use Chrome headless to take screenshot
        cmd = [
            "google-chrome",
            "--headless",
            "--no-sandbox", 
            "--disable-gpu",
            "--window-size=1920,1080",
            f"--screenshot={screenshot_path}",
            dashboard_url
        ]
        
        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            if os.path.exists(screenshot_path):
                file_size = os.path.getsize(screenshot_path)
                print(f"Screenshot saved successfully: {screenshot_path}")
                print(f"File size: {file_size:,} bytes")
                
                # Also test if the dashboard is accessible
                test_cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", dashboard_url]
                curl_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                print(f"Dashboard HTTP status: {curl_result.stdout}")
                
                return screenshot_path
            else:
                print(f"Screenshot file was not created at {screenshot_path}")
                return None
        else:
            print(f"Chrome command failed with return code {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("Chrome command timed out")
        return None
    except Exception as e:
        print(f"Error taking screenshot: {str(e)}")
        return None

def check_dashboard_status():
    """Check if dashboard is running and accessible"""
    try:
        # Check if the dashboard port is listening
        netstat_cmd = ["netstat", "-tlnp", "2>/dev/null", "|", "grep", ":8004"]
        result = subprocess.run(" ".join(netstat_cmd), shell=True, capture_output=True, text=True)
        
        if "8004" in result.stdout:
            print("✅ Dashboard port 8004 is listening")
        else:
            print("❌ Dashboard port 8004 is not listening")
            return False
            
        # Test HTTP response
        curl_cmd = ["curl", "-s", "-I", "http://127.0.0.1:8004"]
        curl_result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
        
        if "200 OK" in curl_result.stdout or "HTTP" in curl_result.stdout:
            print("✅ Dashboard responds to HTTP requests")
            return True
        else:
            print("❌ Dashboard not responding to HTTP requests")
            print(f"Curl output: {curl_result.stdout}")
            return False
            
    except Exception as e:
        print(f"Error checking dashboard status: {e}")
        return False

if __name__ == "__main__":
    print("=== Dashboard Screenshot Capture ===")
    
    # First check if dashboard is running
    if check_dashboard_status():
        # Take screenshot
        screenshot_path = take_chrome_screenshot()
        
        if screenshot_path:
            print(f"\n✅ SUCCESS: Screenshot saved to {screenshot_path}")
        else:
            print("\n❌ FAILED: Could not take screenshot")
    else:
        print("\n❌ Dashboard is not accessible. Please start it first with 'ipfs-kit mcp start'")