const { test, expect } = require('@playwright/test');

test.describe('MCP Server Dashboard', () => {
  const BASE_URL = 'http://127.0.0.1:8765';

  // Increase default timeout for all tests in this describe block
  test.setTimeout(90000); // 90 seconds

  test.beforeEach(async ({ page }) => {
    // Listen for all console messages from the browser
    page.on('console', msg => {
      console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
    });

    // Listen for all request failures
    page.on('requestfailed', request => {
      console.error(`[Request Failed] URL: ${request.url()}, Error: ${request.failure().errorText}`);
    });

    // Listen for all network requests
    page.on('request', request => {
      console.log(`[Network Request] ${request.method()} ${request.url()}`);
    });

    // Listen for all network responses
    page.on('response', async response => {
      console.log(`[Network Response] ${response.status()} ${response.url()}`);
      if (response.status() >= 400) {
        console.error(`[Network Response Error] ${response.status()} ${response.url()} - ${await response.text()}`);
      }
    });
  });

  test('should load the dashboard and display system status and backend summary', async ({ page }) => {
    // Navigate to the dashboard
    await page.goto(`${BASE_URL}/`);
    console.log(`Navigated to: ${page.url()}`);

    // Wait for the system status element to no longer contain "Loading..."
    const systemStatus = page.locator('#systemStatus');
    await expect(systemStatus).not.toContainText('Loading...', { timeout: 30000 });

    // Check if the system status section is populated with expected text
    await expect(systemStatus).toContainText('Status: running', { timeout: 15000 });
    await expect(systemStatus).toContainText('Uptime:', { timeout: 15000 });
    await expect(systemStatus).toContainText('Backends:', { timeout: 15000 });

    // Wait for the backend summary element to no longer contain "Loading..."
    const backendSummary = page.locator('#backendSummary');
    await expect(backendSummary).not.toContainText('Loading...', { timeout: 15000 });
    // Check if the Backend Summary section is populated with expected text
    await expect(backendSummary).toContainText('Backends Healthy', { timeout: 15000 });
    await expect(backendSummary).toContainText('Health Score:', { timeout: 15000 });

    // Wait for the performance metrics element to no longer contain "Loading..."
    const performanceMetrics = page.locator('#performanceMetrics');
    await expect(performanceMetrics).not.toContainText('Loading...', { timeout: 15000 });
    // Check if the Performance section is populated with expected text
    await expect(performanceMetrics).toContainText('Memory:', { timeout: 15000 });
    await expect(performanceMetrics).toContainText('CPU:', { timeout: 15000 });
    await expect(performanceMetrics).toContainText('Healthy Backends', { timeout: 15000 });

    console.log('Dashboard loaded and key overview sections are populated.');
  });

  test('should switch to Monitoring tab and display backend grid', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    // Wait for initial overview data to load before switching tabs
    await expect(page.locator('#systemStatus')).not.toContainText('Loading...', { timeout: 30000 });

    // Click on the Monitoring tab button
    await page.locator('button.tab-button', { hasText: 'Monitoring' }).click();

    // Ensure the Monitoring tab content is active
    const monitoringTabContent = page.locator('#monitoring');
    await expect(monitoringTabContent).toHaveClass(/active/);

    // Wait for at least one backend card to appear in the grid and contain expected text
    const backendCards = page.locator('#backendGrid .backend-card');
    await expect(backendCards.first()).toBeVisible({ timeout: 15000 });
    await expect(backendCards.first()).toContainText('Status:', { timeout: 15000 }); // Check for common text in a backend card

    console.log('Monitoring tab loaded and backend grid is populated.');
  });

  test('should switch to Logs tab and display system logs', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    // Wait for initial overview data to load before switching tabs
    await expect(page.locator('#systemStatus')).not.toContainText('Loading...', { timeout: 30000 });

    // Click on the Logs tab button
    await page.locator('button.tab-button', { hasText: 'Logs' }).click();

    // Ensure the Logs tab content is active
    const logsTabContent = page.locator('#logs');
    await expect(logsTabContent).toHaveClass(/active/);

    // Wait for the log viewer to be populated and contain expected text
    const logViewer = page.locator('#logViewer');
    await expect(logViewer).not.toContainText('Loading logs...', { timeout: 15000 });
    await expect(logViewer).not.toBeEmpty({ timeout: 15000 });
    await expect(logViewer).toContainText('Modular Enhanced MCP Server started', { timeout: 15000 }); // Check for a known log entry

    console.log('Logs tab loaded and log viewer is populated.');
  });
});