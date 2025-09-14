#!/usr/bin/env python3
"""
Playwright Dashboard Validation System

This creates a comprehensive testing system to:
1. Take screenshots of the current dashboard
2. Compare with expected PR #38 styling  
3. Identify broken CSS/HTML paths from PR #39 reorganization
4. Save JavaScript console logs for debugging
5. Create a full diagnostic report

Usage:
    python dashboard_validation.py [--url URL] [--output-dir DIR]
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import argparse

class DashboardValidator:
    def __init__(self, url: str = "http://127.0.0.1:8004", output_dir: str = "screenshots"):
        self.url = url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.console_logs = []
        self.network_errors = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    async def setup_page_monitoring(self, page):
        """Set up console and network monitoring"""
        # Capture console messages
        page.on("console", lambda msg: self.console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "location": msg.location
        }))
        
        # Capture network failures
        page.on("response", lambda response: 
            self.network_errors.append({
                "url": response.url,
                "status": response.status,
                "status_text": response.status_text
            }) if response.status >= 400 else None
        )
        
        # Capture failed requests
        page.on("requestfailed", lambda request:
            self.network_errors.append({
                "url": request.url,
                "failure": request.failure,
                "method": request.method
            })
        )

    async def take_dashboard_screenshot(self, page, name: str, full_page: bool = True):
        """Take a screenshot and save to output directory"""
        screenshot_path = self.output_dir / f"{self.timestamp}_{name}.png"
        await page.screenshot(path=str(screenshot_path), full_page=full_page)
        print(f"📸 Screenshot saved: {screenshot_path}")
        return screenshot_path

    async def validate_dashboard_styling(self, page):
        """Validate CSS styling and identify issues"""
        print("🔍 Validating dashboard styling...")
        
        # Check for missing CSS files
        css_checks = await page.evaluate("""
            () => {
                const results = {};
                
                // Check if stylesheets loaded
                const stylesheets = Array.from(document.styleSheets);
                results.stylesheets_count = stylesheets.length;
                results.stylesheets = stylesheets.map(sheet => ({
                    href: sheet.href,
                    disabled: sheet.disabled,
                    media: sheet.media?.mediaText
                }));
                
                // Check for common styling elements
                const header = document.querySelector('h1, .header, header');
                results.has_header = !!header;
                results.header_text = header?.textContent?.trim();
                
                // Check for navigation
                const nav = document.querySelector('nav, .nav, .navigation, .sidebar');
                results.has_navigation = !!nav;
                
                // Check for main content area
                const main = document.querySelector('main, .main, .content, .dashboard');
                results.has_main_content = !!main;
                
                // Check computed styles for body
                const body = document.body;
                const bodyStyles = window.getComputedStyle(body);
                results.body_styles = {
                    background: bodyStyles.backgroundColor,
                    color: bodyStyles.color,
                    font_family: bodyStyles.fontFamily,
                    margin: bodyStyles.margin,
                    padding: bodyStyles.padding
                };
                
                // Check for dark/light theme indicators
                results.theme_classes = Array.from(document.body.classList);
                
                return results;
            }
        """)
        
        return css_checks

    async def check_expected_elements(self, page):
        """Check for elements that should exist based on PR #38"""
        print("📋 Checking for expected dashboard elements...")
        
        elements_check = await page.evaluate("""
            () => {
                const results = {};
                
                // Expected elements from PR #38 screenshots
                const expectedSelectors = {
                    'rocket_header': '🚀', // Look for rocket emoji in header
                    'comprehensive_title': 'Comprehensive MCP Dashboard',
                    'mcp_server_active': 'MCP Server Active',
                    'overview_tab': 'Overview',
                    'services_tab': 'Services', 
                    'backends_tab': 'Backends',
                    'pin_management': 'Pin Management',
                    'peer_management': 'Peer Management',
                    'logs_tab': 'Logs',
                    'analytics_tab': 'Analytics',
                    'configuration_tab': 'Configuration'
                };
                
                for (const [key, text] of Object.entries(expectedSelectors)) {
                    // Check if text exists anywhere on page
                    results[key] = document.body.textContent.includes(text);
                }
                
                // Check for specific UI patterns from PR #38
                results.has_light_theme = !document.body.classList.contains('dark');
                results.page_title = document.title;
                
                // Look for sidebar/navigation structure
                const navItems = document.querySelectorAll('nav a, .nav a, .sidebar a, [role="navigation"] a');
                results.navigation_items = Array.from(navItems).map(item => ({
                    text: item.textContent?.trim(),
                    href: item.href,
                    active: item.classList.contains('active') || item.classList.contains('selected')
                }));
                
                return results;
            }
        """)
        
        return elements_check

    async def identify_missing_resources(self, page):
        """Identify missing CSS, JS, or other resources"""
        print("🔍 Identifying missing resources...")
        
        # Get all resource URLs that failed to load
        failed_resources = []
        
        # Check for 404s in network log
        for error in self.network_errors:
            if 'status' in error and error['status'] == 404:
                failed_resources.append({
                    'url': error['url'],
                    'type': 'http_404',
                    'status': error['status']
                })
            elif 'failure' in error:
                failed_resources.append({
                    'url': error['url'], 
                    'type': 'network_failure',
                    'failure': error['failure']
                })
        
        # Check for resources that should exist but are missing
        resource_checks = await page.evaluate("""
            () => {
                const results = {
                    missing_images: [],
                    missing_css: [],
                    missing_js: [],
                    broken_links: []
                };
                
                // Check images
                document.querySelectorAll('img').forEach(img => {
                    if (img.naturalWidth === 0) {
                        results.missing_images.push({
                            src: img.src,
                            alt: img.alt
                        });
                    }
                });
                
                // Check for inline styles that might indicate missing CSS
                const elementsWithInlineStyles = document.querySelectorAll('[style]');
                results.inline_styles_count = elementsWithInlineStyles.length;
                
                // Check for common CSS framework indicators
                results.has_bootstrap = !!document.querySelector('link[href*="bootstrap"]') || 
                                      !!document.querySelector('script[src*="bootstrap"]');
                results.has_tailwind = !!document.querySelector('link[href*="tailwind"]') || 
                                      document.body.className.match(/\\b(bg-|text-|p-|m-|flex|grid)/);
                
                return results;
            }
        """)
        
        return {
            'network_failures': failed_resources,
            'resource_analysis': resource_checks
        }

    async def create_diagnostic_report(self, validation_results):
        """Create a comprehensive diagnostic report"""
        report_path = self.output_dir / f"{self.timestamp}_dashboard_diagnostic_report.json"
        
        report = {
            "timestamp": self.timestamp,
            "dashboard_url": self.url,
            "validation_results": validation_results,
            "console_logs": self.console_logs,
            "network_errors": self.network_errors,
            "summary": {
                "console_errors": len([log for log in self.console_logs if log["type"] == "error"]),
                "network_failures": len(self.network_errors),
                "css_issues_detected": self._analyze_css_issues(validation_results),
                "missing_pr38_elements": self._identify_missing_pr38_elements(validation_results)
            }
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📊 Diagnostic report saved: {report_path}")
        return report_path

    def _analyze_css_issues(self, results):
        """Analyze CSS-specific issues from validation results"""
        issues = []
        
        styling = results.get('styling', {})
        
        # Check for missing stylesheets
        if styling.get('stylesheets_count', 0) < 2:
            issues.append("Very few stylesheets loaded - possible CSS loading issue")
        
        # Check body styles
        body_styles = styling.get('body_styles', {})
        if body_styles.get('background') in ['rgba(0, 0, 0, 0)', 'transparent']:
            issues.append("No background color set - CSS may not be loading")
            
        return issues

    def _identify_missing_pr38_elements(self, results):
        """Identify elements that should exist from PR #38 but are missing"""
        missing = []
        
        elements = results.get('elements', {})
        
        expected_elements = [
            'rocket_header', 'comprehensive_title', 'mcp_server_active',
            'overview_tab', 'services_tab', 'backends_tab'
        ]
        
        for element in expected_elements:
            if not elements.get(element, False):
                missing.append(element)
        
        return missing

    async def run_full_validation(self):
        """Run complete dashboard validation with screenshots and diagnostics"""
        print(f"🚀 Starting dashboard validation for {self.url}")
        print(f"📁 Output directory: {self.output_dir}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            await self.setup_page_monitoring(page)
            
            try:
                # Navigate to dashboard
                print(f"🌐 Navigating to {self.url}")
                await page.goto(self.url, wait_until='networkidle', timeout=30000)
                
                # Wait for page to fully load
                await page.wait_for_timeout(2000)
                
                # Take initial screenshot
                await self.take_dashboard_screenshot(page, "initial_load")
                
                # Run validation checks
                validation_results = {}
                
                # 1. CSS and styling validation
                validation_results['styling'] = await self.validate_dashboard_styling(page)
                
                # 2. Expected elements check
                validation_results['elements'] = await self.check_expected_elements(page)
                
                # 3. Missing resources identification  
                validation_results['resources'] = await self.identify_missing_resources(page)
                
                # Take screenshot of current state
                await self.take_dashboard_screenshot(page, "post_validation")
                
                # Create diagnostic report
                report_path = await self.create_diagnostic_report(validation_results)
                
                # Print summary
                await self.print_validation_summary(validation_results)
                
                return validation_results, report_path
                
            except Exception as e:
                print(f"❌ Error during validation: {e}")
                # Take error screenshot
                await self.take_dashboard_screenshot(page, "error_state")
                raise
            
            finally:
                await browser.close()

    async def print_validation_summary(self, results):
        """Print a human-readable summary of validation results"""
        print("\n" + "="*60)
        print("📊 DASHBOARD VALIDATION SUMMARY")
        print("="*60)
        
        # Styling summary
        styling = results.get('styling', {})
        print(f"🎨 CSS/Styling:")
        print(f"   - Stylesheets loaded: {styling.get('stylesheets_count', 0)}")
        print(f"   - Has header: {styling.get('has_header', False)}")
        print(f"   - Has navigation: {styling.get('has_navigation', False)}")
        print(f"   - Header text: '{styling.get('header_text', 'None')}'")
        
        # Elements summary  
        elements = results.get('elements', {})
        print(f"\n📋 Expected Elements:")
        pr38_elements = ['rocket_header', 'comprehensive_title', 'mcp_server_active']
        for elem in pr38_elements:
            status = "✅" if elements.get(elem, False) else "❌"
            print(f"   {status} {elem.replace('_', ' ').title()}")
        
        # Navigation summary
        nav_items = elements.get('navigation_items', [])
        print(f"\n🧭 Navigation ({len(nav_items)} items):")
        for item in nav_items[:8]:  # Show first 8
            active = "🔵" if item.get('active', False) else "⚪"
            print(f"   {active} {item.get('text', 'Unknown')}")
        
        # Issues summary
        print(f"\n⚠️  Issues Found:")
        print(f"   - Console errors: {len([log for log in self.console_logs if log['type'] == 'error'])}")
        print(f"   - Network failures: {len(self.network_errors)}")
        
        # Show critical errors
        for log in self.console_logs[:5]:  # Show first 5 console messages
            if log['type'] == 'error':
                print(f"   🔴 Console Error: {log['text']}")
        
        for error in self.network_errors[:3]:  # Show first 3 network errors
            print(f"   🌐 Network Error: {error.get('url', 'Unknown')} - {error.get('status', error.get('failure', 'Unknown'))}")
        
        print("="*60)

async def main():
    parser = argparse.ArgumentParser(description="Validate IPFS Kit dashboard")
    parser.add_argument("--url", default="http://127.0.0.1:8004", help="Dashboard URL")
    parser.add_argument("--output-dir", default="screenshots", help="Output directory for screenshots and reports")
    
    args = parser.parse_args()
    
    validator = DashboardValidator(args.url, args.output_dir)
    
    try:
        results, report_path = await validator.run_full_validation()
        print(f"\n✅ Validation complete! Report saved to: {report_path}")
        return 0
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))