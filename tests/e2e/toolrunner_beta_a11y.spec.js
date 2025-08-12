// Opt-in beta a11y/confirmation tests. Enable with BETA_UI=1 environment variable.
const { test, expect } = require('@playwright/test');

test.skip(!process.env.BETA_UI, 'Beta UI tests are opt-in via BETA_UI=1');

async function gotoBeta(page) {
  await page.goto('/?ui=beta', { waitUntil: 'domcontentloaded' });
}

test('beta runner exposes ARIA hooks and focuses first field', async ({ page }) => {
  await gotoBeta(page);
  await page.waitForSelector('[data-testid="toolbeta-select"]');

  // Ensure live region exists
  const roleStatus = page.locator('[role="status"][data-testid="toolbeta-result"]');
  await expect(roleStatus).toBeVisible();
  await expect(roleStatus).toHaveAttribute('aria-live', 'polite');

  // Pick a tool with arguments: files_write
  await page.selectOption('[data-testid="toolbeta-select"]', { label: 'files_write' });
  // The form should render and first field should get focus
  const pathField = page.locator('[data-testid="toolbeta-field-path"]');
  await expect(pathField).toBeVisible();
  await expect(pathField).toBeFocused();

  // Required validation should set aria-invalid on missing requireds after attempt
  await page.click('[data-testid="toolbeta-run"]');
  await expect(pathField).toHaveAttribute('aria-invalid', 'true');
});

test('confirmation dialog is shown for destructive action (files_rm)', async ({ page }) => {
  await gotoBeta(page);
  await page.waitForSelector('[data-testid="toolbeta-select"]');

  // Choose files_rm (has confirm fallback regex)
  await page.selectOption('[data-testid="toolbeta-select"]', { label: 'files_rm' });

  // Fill a safe path and set recursive false
  await page.fill('[data-testid="toolbeta-field-path"]', 'e2e/tmp');
  // Intercept the confirm and cancel the first time
  page.once('dialog', async (dialog) => {
    expect(dialog.type()).toBe('confirm');
    await dialog.dismiss();
  });
  await page.click('[data-testid="toolbeta-run"]');

  // Nothing should run, result should not change to error; it may still say Running… briefly then unchanged
  const result = page.locator('[data-testid="toolbeta-result"]');
  await expect(result).toBeVisible();

  // Now accept confirm and let it run
  page.once('dialog', async (dialog) => {
    expect(dialog.type()).toBe('confirm');
    await dialog.accept();
  });
  await page.click('[data-testid="toolbeta-run"]');

  // Should produce a JSON result object
  await expect(result).toContainText('{', { timeout: 10000 });
});
