#!/usr/bin/env python3
"""
Simple dashboard screenshot capture using Chrome headless.
Takes a screenshot of the current dashboard and saves it to screenshots/ directory.
"""
import asyncio
import subprocess
import time
from pathlib import Path
from datetime import datetime

async def take_dashboard_screenshot():
    """Take a screenshot of the current dashboard using Chrome headless."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = Path("screenshots") / f"current_dashboard_{timestamp}.png"
    
    # Ensure screenshots directory exists
    screenshot_path.parent.mkdir(exist_ok=True)
    
    try:
        # Wait for dashboard to be ready
        await asyncio.sleep(2)
        
        # Test if dashboard is accessible
        test_cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:8004"]
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
        if result.stdout.strip() != "200":
            print(f"Dashboard not accessible (HTTP {result.stdout.strip()})")
            return None
            
        print(f"Dashboard is accessible, taking screenshot...")
        
        # Take screenshot using Chrome headless
        chrome_cmd = [
            "google-chrome",
            "--headless",
            "--no-sandbox", 
            "--disable-gpu",
            "--window-size=1920,1080",
            f"--screenshot={screenshot_path.absolute()}",
            "--incognito",
            "--noerrdialogs",
            "--no-first-run",
            f"--user-data-dir=/tmp/.com.google.Chrome.{timestamp}",
            "--ozone-platform=headless",
            "--ozone-override-screen-size=800,600",
            "--use-angle=swiftshader-webgl",
            "http://127.0.0.1:8004"
        ]
        
        result = subprocess.run(chrome_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and screenshot_path.exists():
            size = screenshot_path.stat().st_size
            print(f"Screenshot saved: {screenshot_path} ({size:,} bytes)")
            return screenshot_path
        else:
            print(f"Screenshot failed: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Screenshot error: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(take_dashboard_screenshot())