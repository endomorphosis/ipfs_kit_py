#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import os
from datetime import datetime

async def take_dashboard_screenshot():
    """Take a screenshot of the dashboard and save it to the screenshots directory"""
    
    # Create screenshots directory if it doesn't exist
    screenshots_dir = "/home/runner/work/ipfs_kit_py/ipfs_kit_py/screenshots"
    os.makedirs(screenshots_dir, exist_ok=True)
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Set viewport size
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Navigate to the dashboard
            dashboard_url = "http://127.0.0.1:8004"
            print(f"Navigating to {dashboard_url}...")
            
            # Navigate with timeout
            await page.goto(dashboard_url, wait_until="networkidle", timeout=30000)
            
            # Wait a bit for dynamic content to load
            await page.wait_for_timeout(3000)
            
            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(screenshots_dir, f"current_dashboard_{timestamp}.png")
            
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")
            
            # Get page title and some basic info
            title = await page.title()
            url = page.url
            print(f"Page title: {title}")
            print(f"Current URL: {url}")
            
            # Check for any console errors
            console_messages = []
            
            def handle_console(msg):
                console_messages.append(f"{msg.type}: {msg.text}")
            
            page.on("console", handle_console)
            
            # Wait a bit more to capture any console messages
            await page.wait_for_timeout(2000)
            
            if console_messages:
                print("Console messages:")
                for msg in console_messages:
                    print(f"  {msg}")
            else:
                print("No console messages captured")
                
            return screenshot_path
            
        except Exception as e:
            print(f"Error taking screenshot: {str(e)}")
            return None
        finally:
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(take_dashboard_screenshot())
    if result:
        print(f"\nScreenshot successfully saved: {result}")
        # Also print file size
        file_size = os.path.getsize(result)
        print(f"File size: {file_size:,} bytes")
    else:
        print("Failed to take screenshot")