#!/usr/bin/env python3
"""
Screenshot Validation System using Playwright
Creates actual PNG screenshots saved to disk for dashboard validation.
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
import json

def install_playwright():
    """Install playwright if not available"""
    try:
        from playwright.async_api import async_playwright
        return True
    except ImportError:
        print("Installing playwright...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False

async def start_dashboard():
    """Start the MCP dashboard and return process"""
    print("Starting dashboard...")
    proc = subprocess.Popen([
        sys.executable, "-c", """
import sys
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')
from ipfs_kit_py.cli import main
import asyncio
asyncio.run(main())
""", "mcp", "start", "--foreground"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Give dashboard time to start
    await asyncio.sleep(3)
    return proc

def is_dashboard_running(port=8004):
    """Check if dashboard is running on port"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False

async def capture_screenshots():
    """Capture screenshots using Playwright"""
    if not install_playwright():
        print("Failed to install playwright")
        return None
        
    from playwright.async_api import async_playwright
    
    # Check if dashboard is running
    if not is_dashboard_running():
        proc = await start_dashboard()
        time.sleep(5)  # Give more time for startup
        if not is_dashboard_running():
            print("Dashboard failed to start")
            return None
    
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        try:
            # Navigate to dashboard
            await page.goto('http://127.0.0.1:8004', timeout=30000)
            
            # Wait for page to load
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            # Capture full page screenshot
            screenshot_path = screenshots_dir / f"dashboard_full_{timestamp}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"Full screenshot saved: {screenshot_path}")
            
            # Capture viewport screenshot
            viewport_path = screenshots_dir / f"dashboard_viewport_{timestamp}.png"
            await page.screenshot(path=str(viewport_path))
            print(f"Viewport screenshot saved: {viewport_path}")
            
            # Get page title and content
            title = await page.title()
            print(f"Page title: {title}")
            
            # Get console messages
            console_messages = []
            def handle_console(msg):
                console_messages.append({
                    'type': msg.type,
                    'text': msg.text
                })
            page.on('console', handle_console)
            
            # Wait a bit more to capture any console messages
            await asyncio.sleep(2)
            
            # Get page source
            source = await page.content()
            source_path = screenshots_dir / f"dashboard_source_{timestamp}.html"
            with open(source_path, 'w') as f:
                f.write(source)
            print(f"Source saved: {source_path}")
            
            # Check for specific elements
            elements_check = {}
            
            # Check for rocket emoji in title
            elements_check['rocket_emoji'] = '🚀' in title or '🚀' in source
            
            # Check for IPFS Kit text
            elements_check['ipfs_kit_text'] = 'IPFS Kit' in source
            
            # Check for navigation elements
            try:
                nav_elements = await page.query_selector_all('nav, .nav, [role="navigation"]')
                elements_check['navigation_present'] = len(nav_elements) > 0
            except:
                elements_check['navigation_present'] = False
            
            # Create diagnostic report
            diagnostic = {
                'timestamp': timestamp,
                'url': 'http://127.0.0.1:8004',
                'title': title,
                'screenshots': {
                    'full_page': str(screenshot_path),
                    'viewport': str(viewport_path)
                },
                'source_file': str(source_path),
                'elements_check': elements_check,
                'console_messages': console_messages,
                'page_loaded': True
            }
            
            # Save diagnostic report
            report_path = screenshots_dir / f"diagnostic_report_{timestamp}.json"
            with open(report_path, 'w') as f:
                json.dump(diagnostic, f, indent=2)
            print(f"Diagnostic report saved: {report_path}")
            
            return diagnostic
            
        except Exception as e:
            print(f"Error capturing screenshots: {e}")
            return None
            
        finally:
            await browser.close()

async def main():
    """Main function to run screenshot validation"""
    print("=== Dashboard Screenshot Validation ===")
    
    result = await capture_screenshots()
    
    if result:
        print("\n=== Validation Results ===")
        print(f"Dashboard URL: {result['url']}")
        print(f"Page Title: {result['title']}")
        print(f"Rocket Emoji Present: {result['elements_check']['rocket_emoji']}")
        print(f"IPFS Kit Text Present: {result['elements_check']['ipfs_kit_text']}")
        print(f"Navigation Present: {result['elements_check']['navigation_present']}")
        print(f"Screenshots saved in: screenshots/")
        
        # List all files created
        screenshots_dir = Path("screenshots")
        print("\nFiles created:")
        for file in sorted(screenshots_dir.glob(f"*{result['timestamp']}*")):
            size = file.stat().st_size
            print(f"  {file.name} ({size:,} bytes)")
        
        return True
    else:
        print("Failed to capture screenshots")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)