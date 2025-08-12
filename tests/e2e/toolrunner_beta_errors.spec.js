// Opt-in beta error summary tests. Enable with BETA_UI=1 environment variable.
const { test, expect } = require('@playwright/test');

test.skip(!process.env.BETA_UI, 'Beta UI tests are opt-in via BETA_UI=1');

async function gotoBeta(page) {
  await page.goto('/?ui=beta', { waitUntil: 'domcontentloaded' });
}

test('error summary announces invalid inputs and focuses summary', async ({ page }) => {
  await gotoBeta(page);
  await page.waitForSelector('[data-testid="toolbeta-select"]');

  await page.selectOption('[data-testid="toolbeta-select"]', { label: 'files_write' });

  // Don't fill required path; trigger run
  const result = page.locator('[data-testid="toolbeta-result"]');
  const summary = page.locator('#toolbeta-errors[role="alert"]');
  await page.click('[data-testid="toolbeta-run"]');

  await expect(summary).toBeVisible();
  await expect(summary).toContainText('Please fix the following:');
  await expect(summary).toBeFocused();
  await expect(result).toContainText('Invalid input');
});
