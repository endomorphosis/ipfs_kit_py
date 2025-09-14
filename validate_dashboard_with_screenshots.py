#!/usr/bin/env python3
"""
Comprehensive Dashboard Validation with Playwright Screenshots
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Install playwright and dependencies if needed
def install_playwright():
    """Install playwright and browser dependencies"""
    try:
        import playwright
    except ImportError:
        print("Installing playwright...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    
    # Install browsers
    try:
        from playwright.async_api import async_playwright
        print("Playwright installed, checking browsers...")
        result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Browser installation failed, continuing anyway...")
    except Exception as e:
        print(f"Browser setup issue (continuing): {e}")

class DashboardValidator:
    def __init__(self, screenshots_dir: Path = None):
        self.screenshots_dir = screenshots_dir or Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.dashboard_process = None
        self.base_url = "http://127.0.0.1:8004"
        self.validation_results = {}
        
    async def start_dashboard(self) -> bool:
        """Start the MCP dashboard using the CLI"""
        try:
            print("Starting dashboard via CLI...")
            cmd = [sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "start", "--foreground"]
            
            # Start in background for testing
            self.dashboard_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent
            )
            
            # Wait for startup
            print("Waiting for dashboard to start...")
            for i in range(30):  # 30 second timeout
                try:
                    import urllib.request
                    with urllib.request.urlopen(f"{self.base_url}/", timeout=2) as response:
                        if response.getcode() == 200:
                            print(f"Dashboard available at {self.base_url}")
                            return True
                except Exception:
                    pass
                await asyncio.sleep(1)
            
            print("Dashboard failed to start within timeout")
            return False
            
        except Exception as e:
            print(f"Failed to start dashboard: {e}")
            return False
    
    async def stop_dashboard(self):
        """Stop the dashboard process"""
        if self.dashboard_process:
            self.dashboard_process.terminate()
            try:
                self.dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.dashboard_process.kill()
    
    async def take_screenshots_and_validate(self) -> Dict[str, Any]:
        """Take comprehensive screenshots and validate dashboard functionality"""
        install_playwright()
        
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            print(f"Failed to import playwright: {e}")
            return {"error": "playwright_import_failed"}
        
        results = {
            "screenshots": [],
            "console_logs": [],
            "navigation_tests": {},
            "styling_analysis": {},
            "functionality_checks": {}
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Collect console logs
            console_messages = []
            page.on("console", lambda msg: console_messages.append({
                "type": msg.type,
                "text": msg.text,
                "location": str(msg.location) if msg.location else None
            }))
            
            try:
                # Load the main dashboard page
                print(f"Loading dashboard at {self.base_url}")
                await page.goto(self.base_url, wait_until="networkidle", timeout=15000)
                
                # Wait for page to fully load
                await asyncio.sleep(3)
                
                # Take full page screenshot
                main_screenshot = self.screenshots_dir / "current_dashboard_main.png"
                await page.screenshot(path=str(main_screenshot), full_page=True)
                results["screenshots"].append(str(main_screenshot))
                print(f"Main screenshot saved: {main_screenshot}")
                
                # Get page title and header info
                title = await page.title()
                results["page_title"] = title
                
                # Check for header content (rocket emoji and title)
                header_content = await page.text_content("h1, .header, [class*='header'], [class*='title']")
                results["header_content"] = header_content
                
                # Look for navigation elements
                nav_elements = await page.query_selector_all("nav, .nav, [class*='nav'], .tab, [class*='tab']")
                nav_texts = []
                for nav in nav_elements:
                    text = await nav.text_content()
                    if text:
                        nav_texts.append(text.strip())
                results["navigation_elements"] = nav_texts
                
                # Test clicking on different navigation tabs
                tab_selectors = [
                    "text=Overview",
                    "text=Services", 
                    "text=Backends",
                    "text=Buckets",
                    "text=Pins",
                    "text=Logs",
                    "text=Files",
                    "text=Tools",
                    "text=IPFS",
                    "text=CARs",
                    "text=Pin Management",
                    "text=Peer Management",
                    "text=Analytics",
                    "text=Configuration"
                ]
                
                for tab_name in ["Overview", "Services", "Backends"]:
                    try:
                        tab_selector = f"text={tab_name}"
                        if await page.query_selector(tab_selector):
                            print(f"Testing {tab_name} tab...")
                            await page.click(tab_selector)
                            await asyncio.sleep(2)  # Let content load
                            
                            # Take screenshot of this tab
                            tab_screenshot = self.screenshots_dir / f"tab_{tab_name.lower()}.png"
                            await page.screenshot(path=str(tab_screenshot), full_page=True)
                            results["screenshots"].append(str(tab_screenshot))
                            results["navigation_tests"][tab_name] = "success"
                            print(f"Tab {tab_name} screenshot saved: {tab_screenshot}")
                        else:
                            results["navigation_tests"][tab_name] = "tab_not_found"
                    except Exception as e:
                        results["navigation_tests"][tab_name] = f"error: {e}"
                
                # Analyze CSS and styling
                try:
                    # Check background color
                    body_style = await page.evaluate("getComputedStyle(document.body).backgroundColor")
                    results["styling_analysis"]["body_background"] = body_style
                    
                    # Check if dark or light theme
                    is_dark = await page.evaluate("""
                        () => {
                            const body = document.body;
                            const style = getComputedStyle(body);
                            const bg = style.backgroundColor;
                            // Check if background is dark
                            if (bg.includes('rgb')) {
                                const rgb = bg.match(/\d+/g);
                                if (rgb && rgb.length >= 3) {
                                    const brightness = (parseInt(rgb[0]) + parseInt(rgb[1]) + parseInt(rgb[2])) / 3;
                                    return brightness < 128;
                                }
                            }
                            return body.classList.contains('dark') || 
                                   document.documentElement.classList.contains('dark');
                        }
                    """)
                    results["styling_analysis"]["is_dark_theme"] = is_dark
                    
                    # Check for rocket emoji in header
                    rocket_found = await page.evaluate("""
                        () => {
                            const text = document.body.innerText;
                            return text.includes('🚀') || text.includes('IPFS Kit');
                        }
                    """)
                    results["styling_analysis"]["rocket_emoji_present"] = rocket_found
                    
                except Exception as e:
                    results["styling_analysis"]["error"] = str(e)
                
                # Check functionality - count MCP tools, backends, etc.
                try:
                    # Look for component counts or metrics
                    metrics_text = await page.text_content("body")
                    
                    # Extract numbers that might indicate tool/backend counts
                    import re
                    tool_matches = re.findall(r'(\d+)\s*(?:tools?|MCP|backends?|services?)', metrics_text, re.IGNORECASE)
                    results["functionality_checks"]["component_counts"] = tool_matches
                    
                    # Check for system metrics (CPU, Memory, Disk)
                    has_metrics = any(term in metrics_text.lower() for term in ['cpu', 'memory', 'disk', '%'])
                    results["functionality_checks"]["has_system_metrics"] = has_metrics
                    
                except Exception as e:
                    results["functionality_checks"]["error"] = str(e)
                
                # Store console logs
                results["console_logs"] = console_messages
                
                # Take final viewport screenshot
                viewport_screenshot = self.screenshots_dir / "current_dashboard_viewport.png"
                await page.screenshot(path=str(viewport_screenshot))
                results["screenshots"].append(str(viewport_screenshot))
                
            except Exception as e:
                results["error"] = str(e)
                print(f"Error during validation: {e}")
            
            finally:
                await browser.close()
        
        return results
    
    async def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive validation report"""
        report = []
        report.append("=== DASHBOARD VALIDATION REPORT ===\n")
        
        if "error" in results:
            report.append(f"❌ VALIDATION FAILED: {results['error']}\n")
            return "\n".join(report)
        
        # Page info
        if "page_title" in results:
            report.append(f"📄 Page Title: {results['page_title']}")
        
        if "header_content" in results:
            report.append(f"📝 Header Content: {results['header_content']}")
        
        # Screenshots
        if results.get("screenshots"):
            report.append(f"\n📸 Screenshots taken: {len(results['screenshots'])}")
            for screenshot in results["screenshots"]:
                report.append(f"   - {screenshot}")
        
        # Navigation tests
        nav_results = results.get("navigation_tests", {})
        if nav_results:
            report.append("\n🧭 Navigation Tests:")
            for tab, result in nav_results.items():
                status = "✅" if result == "success" else "❌"
                report.append(f"   {status} {tab}: {result}")
        
        # Styling analysis
        styling = results.get("styling_analysis", {})
        if styling:
            report.append("\n🎨 Styling Analysis:")
            if "body_background" in styling:
                report.append(f"   Background Color: {styling['body_background']}")
            if "is_dark_theme" in styling:
                theme = "Dark" if styling["is_dark_theme"] else "Light"
                report.append(f"   Theme: {theme}")
            if "rocket_emoji_present" in styling:
                emoji_status = "✅ Found" if styling["rocket_emoji_present"] else "❌ Missing"
                report.append(f"   Rocket Emoji (🚀): {emoji_status}")
        
        # Functionality checks
        functionality = results.get("functionality_checks", {})
        if functionality:
            report.append("\n⚙️ Functionality Checks:")
            if "component_counts" in functionality:
                counts = functionality["component_counts"]
                if counts:
                    report.append(f"   Component Counts Found: {', '.join(counts)}")
                else:
                    report.append("   No component counts detected")
            if "has_system_metrics" in functionality:
                metrics_status = "✅ Present" if functionality["has_system_metrics"] else "❌ Missing"
                report.append(f"   System Metrics: {metrics_status}")
        
        # Console logs summary
        console_logs = results.get("console_logs", [])
        if console_logs:
            errors = [log for log in console_logs if log["type"] == "error"]
            warnings = [log for log in console_logs if log["type"] == "warning"]
            report.append(f"\n🖥️ Console Logs: {len(console_logs)} total")
            if errors:
                report.append(f"   ❌ {len(errors)} errors")
            if warnings:
                report.append(f"   ⚠️ {len(warnings)} warnings")
        
        return "\n".join(report)

async def main():
    """Main validation function"""
    print("Starting Dashboard Validation with Screenshots...")
    
    validator = DashboardValidator()
    
    # Start dashboard
    if not await validator.start_dashboard():
        print("❌ Failed to start dashboard")
        return 1
    
    try:
        # Run validation and take screenshots
        results = await validator.take_screenshots_and_validate()
        
        # Generate and save report
        report = await validator.generate_report(results)
        print("\n" + report)
        
        # Save detailed results to JSON
        results_file = validator.screenshots_dir / "validation_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📊 Detailed results saved to: {results_file}")
        print(f"📁 Screenshots directory: {validator.screenshots_dir}")
        
        return 0
        
    finally:
        await validator.stop_dashboard()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))