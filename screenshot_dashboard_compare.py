#!/usr/bin/env python3
"""
Screenshot Dashboard Comparison Tool

This tool takes screenshots of the current dashboard and compares it to PR #38 expectations
to identify styling issues caused by PR #39 reorganization.
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright
import time

async def take_dashboard_screenshot():
    """Take screenshot of the current dashboard and analyze styling."""
    
    # Create screenshots directory
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Enable console logging
        console_logs = []
        def log_console_message(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
        page.on("console", log_console_message)
        
        # Navigate to dashboard
        dashboard_url = "http://127.0.0.1:8004"
        print(f"Navigating to {dashboard_url}...")
        
        try:
            # Navigate and wait for load
            await page.goto(dashboard_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for dynamic content
            
            # Take full page screenshot
            screenshot_path = screenshots_dir / "current_dashboard.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved: {screenshot_path}")
            
            # Get page title and basic info
            title = await page.title()
            print(f"Page title: {title}")
            
            # Check for specific elements that should match PR #38
            header_text = await page.text_content("h1, .header, .title") or ""
            print(f"Header text: {header_text}")
            
            # Check for rocket emoji
            page_content = await page.content()
            has_rocket = "🚀" in page_content
            print(f"Has rocket emoji: {has_rocket}")
            
            # Check background color
            body_styles = await page.evaluate("""
                () => {
                    const body = document.body;
                    const styles = window.getComputedStyle(body);
                    return {
                        backgroundColor: styles.backgroundColor,
                        color: styles.color,
                        fontFamily: styles.fontFamily
                    };
                }
            """)
            print(f"Body styles: {body_styles}")
            
            # Check for navigation elements
            nav_elements = await page.query_selector_all("nav, .nav, .navigation, .tabs, .sidebar")
            print(f"Found {len(nav_elements)} navigation elements")
            
            # Get navigation text
            nav_texts = []
            for nav in nav_elements:
                text = await nav.text_content()
                if text and text.strip():
                    nav_texts.append(text.strip())
            print(f"Navigation texts: {nav_texts}")
            
            # Check for specific PR #38 elements
            pr38_elements = {
                "rocket_header": "🚀" in page_content and "IPFS Kit" in page_content,
                "light_theme": "rgb(245, 245, 245)" in str(body_styles.get('backgroundColor', '')) or "#f5f5f5" in page_content,
                "overview_tab": "Overview" in page_content,
                "services_tab": "Services" in page_content,
                "backends_tab": "Backends" in page_content,
                "pin_management": "Pin Management" in page_content or "Pins" in page_content,
                "comprehensive_subtitle": "Comprehensive" in page_content
            }
            
            print("\nPR #38 Element Check:")
            for element, found in pr38_elements.items():
                status = "✅" if found else "❌"
                print(f"{status} {element}: {found}")
            
            # Save console logs
            log_path = screenshots_dir / "console_logs.txt"
            with open(log_path, "w") as f:
                f.write(f"Dashboard Console Logs - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n")
                for log in console_logs:
                    f.write(log + "\n")
            print(f"Console logs saved: {log_path}")
            
            # Check API endpoints
            api_checks = {}
            api_endpoints = [
                "/api/metrics/system",
                "/api/buckets", 
                "/api/backends",
                "/api/pins",
                "/api/health"
            ]
            
            for endpoint in api_endpoints:
                try:
                    response = await page.request.get(f"{dashboard_url}{endpoint}")
                    api_checks[endpoint] = {
                        "status": response.status,
                        "ok": response.ok
                    }
                except Exception as e:
                    api_checks[endpoint] = {"error": str(e)}
            
            print(f"\nAPI Endpoint Checks:")
            for endpoint, result in api_checks.items():
                if "error" in result:
                    print(f"❌ {endpoint}: Error - {result['error']}")
                elif result.get("ok"):
                    print(f"✅ {endpoint}: Status {result['status']}")
                else:
                    print(f"❌ {endpoint}: Status {result['status']}")
            
            # Create analysis report
            report_path = screenshots_dir / "dashboard_analysis_current.md"
            with open(report_path, "w") as f:
                f.write(f"# Dashboard Analysis Report\n\n")
                f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"## Basic Information\n")
                f.write(f"- **URL:** {dashboard_url}\n")
                f.write(f"- **Title:** {title}\n")
                f.write(f"- **Header:** {header_text}\n\n")
                f.write(f"## Styling Analysis\n")
                f.write(f"- **Background Color:** {body_styles.get('backgroundColor', 'N/A')}\n")
                f.write(f"- **Text Color:** {body_styles.get('color', 'N/A')}\n")
                f.write(f"- **Font Family:** {body_styles.get('fontFamily', 'N/A')}\n\n")
                f.write(f"## PR #38 Compatibility\n")
                for element, found in pr38_elements.items():
                    status = "✅ Pass" if found else "❌ Fail"
                    f.write(f"- **{element.replace('_', ' ').title()}:** {status}\n")
                f.write(f"\n## Navigation Elements\n")
                for i, text in enumerate(nav_texts, 1):
                    f.write(f"{i}. {text}\n")
                f.write(f"\n## API Endpoints\n")
                for endpoint, result in api_checks.items():
                    if "error" in result:
                        f.write(f"- **{endpoint}:** ❌ Error - {result['error']}\n")
                    elif result.get("ok"):
                        f.write(f"- **{endpoint}:** ✅ Status {result['status']}\n") 
                    else:
                        f.write(f"- **{endpoint}:** ❌ Status {result['status']}\n")
            
            print(f"Analysis report saved: {report_path}")
            
            compatibility_score = sum(pr38_elements.values()) / len(pr38_elements) * 100
            print(f"\n📊 PR #38 Compatibility Score: {compatibility_score:.1f}%")
            
            if compatibility_score < 80:
                print("⚠️  Dashboard styling does NOT match PR #38 expectations")
                print("🔍 Issues likely caused by PR #39 reorganization")
            else:
                print("✅ Dashboard styling matches PR #38 expectations")
                
        except Exception as e:
            print(f"Error during screenshot: {e}")
            # Take a screenshot anyway for debugging
            error_screenshot = screenshots_dir / "error_dashboard.png"
            try:
                await page.screenshot(path=error_screenshot, full_page=True)
                print(f"Error screenshot saved: {error_screenshot}")
            except:
                pass
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(take_dashboard_screenshot())