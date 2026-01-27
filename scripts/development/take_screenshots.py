#!/usr/bin/env python3
"""
Screenshot Tool for MCP Dashboard
Takes screenshots of the MCP services interface to verify functionality.
"""
import anyio
import time
import sys
import os
from pathlib import Path

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    print("Installing playwright...")
    os.system("pip install playwright")
    os.system("playwright install --with-deps chromium")
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True

async def take_dashboard_screenshots():
    """Take comprehensive screenshots of all dashboard tabs."""
    
    async with async_playwright() as p:
        # Launch browser with proper settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1280,720'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        # Wait for server to be ready
        dashboard_url = 'http://127.0.0.1:8004'
        
        try:
            print(f"Navigating to {dashboard_url}...")
            await page.goto(dashboard_url, wait_until='networkidle', timeout=30000)
            
            # Take overview screenshot
            print("Taking Overview tab screenshot...")
            await page.screenshot(path='overview_dashboard.png', full_page=True)
            
            # Click on Services tab if it exists
            try:
                services_tab = await page.wait_for_selector('a[href="#services"], button:has-text("Services"), .nav-item:has-text("Services")', timeout=5000)
                if services_tab:
                    await services_tab.click()
                    await page.wait_for_timeout(2000)  # Wait for content to load
                    print("Taking Services tab screenshot...")
                    await page.screenshot(path='services_dashboard.png', full_page=True)
            except Exception as e:
                print(f"Services tab not found or error: {e}")
            
            # Check for other tabs
            tab_names = ['Backends', 'Buckets', 'Pins', 'Files', 'Tools', 'IPFS', 'CARs', 'Logs']
            
            for tab_name in tab_names:
                try:
                    tab = await page.wait_for_selector(f'a:has-text("{tab_name}"), button:has-text("{tab_name}"), .nav-item:has-text("{tab_name}")', timeout=2000)
                    if tab:
                        await tab.click()
                        await page.wait_for_timeout(2000)
                        filename = f'{tab_name.lower()}_dashboard.png'
                        print(f"Taking {tab_name} tab screenshot...")
                        await page.screenshot(path=filename, full_page=True)
                except Exception as e:
                    print(f"{tab_name} tab not found: {e}")
            
            # Get console logs to check for JavaScript errors
            console_logs = []
            page.on("console", lambda msg: console_logs.append(f"{msg.type}: {msg.text}"))
            
            # Wait a bit more for any async JavaScript
            await page.wait_for_timeout(3000)
            
            # Print console logs
            if console_logs:
                print("\nJavaScript Console Output:")
                for log in console_logs[-10:]:  # Last 10 logs
                    print(f"  {log}")
            
            # Try to interact with services if they exist
            try:
                # Look for service elements
                services = await page.query_selector_all('.service-item, .service-card, tr[data-service]')
                print(f"Found {len(services)} service elements")
                
                if services:
                    print("Taking detailed services screenshot...")
                    await page.screenshot(path='services_detailed.png', full_page=True)
                    
            except Exception as e:
                print(f"Error checking services: {e}")
                
        except Exception as e:
            print(f"Error navigating to dashboard: {e}")
            # Take screenshot of error page if possible
            try:
                await page.screenshot(path='error_page.png', full_page=True)
            except:
                pass
        
        await browser.close()
        
    print("Screenshots completed!")
    print("Files generated:")
    for f in Path('.').glob('*_dashboard.png'):
        print(f"  - {f}")

if __name__ == "__main__":
    # First check if server is running
    import requests
    try:
        response = requests.get('http://127.0.0.1:8004', timeout=5)
        print(f"MCP Server is running (status: {response.status_code})")
    except:
        print("MCP Server doesn't appear to be running on port 8004")
        sys.exit(1)
    
    # Run screenshot capture
    anyio.run(take_dashboard_screenshots)