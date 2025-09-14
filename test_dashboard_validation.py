#!/usr/bin/env python3
"""
Playwright Screen Capture System for Dashboard Validation
=========================================================

This system provides automated screenshot capture and validation
to ensure the dashboard works correctly after reorganization changes.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

class DashboardValidator:
    def __init__(self, dashboard_url="http://127.0.0.1:8004", screenshot_dir="screenshots"):
        self.dashboard_url = dashboard_url
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        
    async def capture_dashboard_state(self):
        """Capture comprehensive screenshots of the dashboard."""
        results = {}
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            try:
                # Navigate to dashboard
                print(f"Navigating to {self.dashboard_url}...")
                await page.goto(self.dashboard_url, wait_until="domcontentloaded", timeout=10000)
                await page.wait_for_timeout(3000)  # Wait for JS to load
                
                # Take main dashboard screenshot
                main_screenshot = self.screenshot_dir / "main_dashboard.png"
                await page.screenshot(path=main_screenshot, full_page=True)
                results["main_dashboard"] = str(main_screenshot)
                print(f"✅ Main dashboard screenshot saved: {main_screenshot}")
                
                # Check header and navigation
                header_text = await page.text_content("h1") if await page.query_selector("h1") else "No h1 found"
                results["header_text"] = header_text
                print(f"📝 Header text: {header_text}")
                
                # Check navigation tabs
                nav_buttons = await page.query_selector_all(".nav-btn")
                nav_text = []
                for button in nav_buttons:
                    text = await button.text_content()
                    if text:
                        nav_text.append(text.strip())
                results["navigation"] = nav_text
                print(f"📋 Navigation tabs: {nav_text}")
                
                # Check for styling elements
                await page.wait_for_selector("body", timeout=5000)
                background_color = await page.evaluate("""
                    () => window.getComputedStyle(document.body).backgroundColor
                """)
                results["body_background"] = background_color
                print(f"🎨 Body background color: {background_color}")
                
                # Capture console logs
                console_logs = []
                page.on("console", lambda msg: console_logs.append({
                    "type": msg.type,
                    "text": msg.text,
                    "location": msg.location
                }))
                
                # Wait a bit more for any console messages
                await page.wait_for_timeout(2000)
                results["console_logs"] = console_logs[-10:]  # Last 10 logs
                
                # Check if specific elements from PR #38 are present
                elements_to_check = [
                    ("🚀 IPFS Kit header", "h1:has-text('🚀 IPFS Kit')"),
                    ("Overview tab", ".nav-btn[data-view='overview']"),
                    ("Services tab", ".nav-btn[data-view='services']"),
                    ("Backends tab", ".nav-btn[data-view='backends']"),
                    ("Buckets tab", ".nav-btn[data-view='buckets']")
                ]
                
                element_status = {}
                for name, selector in elements_to_check:
                    try:
                        element = await page.query_selector(selector)
                        element_status[name] = element is not None
                        if element:
                            print(f"✅ Found: {name}")
                        else:
                            print(f"❌ Missing: {name}")
                    except Exception as e:
                        element_status[name] = f"Error: {str(e)}"
                        print(f"⚠️ Error checking {name}: {e}")
                
                results["elements_found"] = element_status
                
                # Try clicking different tabs to test functionality
                tab_screenshots = {}
                tabs_to_test = ["services", "backends", "buckets"]
                
                for tab in tabs_to_test:
                    try:
                        tab_button = await page.query_selector(f".nav-btn[data-view='{tab}']")
                        if tab_button:
                            await tab_button.click()
                            await page.wait_for_timeout(1000)  # Wait for tab to load
                            
                            tab_screenshot = self.screenshot_dir / f"tab_{tab}.png"
                            await page.screenshot(path=tab_screenshot, full_page=True)
                            tab_screenshots[tab] = str(tab_screenshot)
                            print(f"📸 Tab screenshot captured: {tab}")
                        else:
                            print(f"❌ Could not find tab button for: {tab}")
                    except Exception as e:
                        print(f"⚠️ Error testing tab {tab}: {e}")
                
                results["tab_screenshots"] = tab_screenshots
                
            except TimeoutError:
                results["error"] = "Timeout - Dashboard not accessible"
                print("❌ Timeout - Dashboard not accessible")
            except Exception as e:
                results["error"] = f"Error: {str(e)}"
                print(f"❌ Error: {e}")
            finally:
                await browser.close()
        
        return results
    
    async def validate_pr38_functionality(self):
        """Validate that PR #38 functionality is present."""
        print("\n🔍 Validating PR #38 Dashboard Functionality...")
        
        results = await self.capture_dashboard_state()
        
        # Analysis
        print("\n📊 VALIDATION RESULTS:")
        print("=" * 50)
        
        # Check header
        if "🚀 IPFS Kit" in results.get("header_text", ""):
            print("✅ HEADER: Correct '🚀 IPFS Kit' header found")
        else:
            print(f"❌ HEADER: Wrong header - found: {results.get('header_text')}")
        
        # Check navigation
        expected_nav = ["Overview", "Services", "Backends", "Buckets", "Pins", "Logs", "Files", "Tools", "IPFS", "CARs"]
        found_nav = results.get("navigation", [])
        nav_match = all(item in found_nav for item in expected_nav[:4])  # Check first 4 critical tabs
        
        if nav_match:
            print("✅ NAVIGATION: Correct navigation tabs found")
        else:
            print(f"❌ NAVIGATION: Wrong navigation - found: {found_nav}")
            print(f"   Expected: {expected_nav}")
        
        # Check styling
        background = results.get("body_background", "")
        if "rgb(245, 245, 245)" in background or "#f5f5f5" in background or "245" in background:
            print("✅ STYLING: Light theme background detected")
        else:
            print(f"⚠️ STYLING: Background color: {background}")
        
        # Check console errors
        console_logs = results.get("console_logs", [])
        error_count = len([log for log in console_logs if log.get("type") == "error"])
        if error_count == 0:
            print("✅ CONSOLE: No JavaScript errors detected")
        else:
            print(f"⚠️ CONSOLE: {error_count} JavaScript errors found")
            for log in console_logs:
                if log.get("type") == "error":
                    print(f"   Error: {log.get('text')}")
        
        # Overall assessment
        print("\n🎯 OVERALL ASSESSMENT:")
        issues = []
        
        if "🚀 IPFS Kit" not in results.get("header_text", ""):
            issues.append("Wrong header text")
        
        if not nav_match:
            issues.append("Navigation structure incorrect")
        
        if error_count > 0:
            issues.append(f"{error_count} JavaScript errors")
        
        if not results.get("elements_found", {}).get("🚀 IPFS Kit header", False):
            issues.append("Missing header element")
        
        if issues:
            print(f"❌ ISSUES FOUND: {len(issues)} problems detected")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ SUCCESS: Dashboard matches PR #38 specifications!")
        
        # Save detailed results
        results_file = self.screenshot_dir / "validation_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n📝 Detailed results saved to: {results_file}")
        
        return results, issues

async def main():
    """Main validation function."""
    print("🚀 Dashboard Validation System")
    print("=" * 50)
    
    validator = DashboardValidator()
    results, issues = await validator.validate_pr38_functionality()
    
    if issues:
        print(f"\n❌ Validation failed with {len(issues)} issues")
        return 1
    else:
        print("\n✅ Validation successful - Dashboard working correctly!")
        return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)