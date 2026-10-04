import { test, expect } from '@playwright/test';

// Helpers to keep timeouts explicit and prevent hangs
const navOpts = { timeout: 10_000 } as const;
const actOpts = { timeout: 8_000 } as const;
const shortWait = (ms = 200) => new Promise(r => setTimeout(r, ms));

const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

test.describe('Consolidated MCP Dashboard', () => {
  test('loads overview and shows status', async ({ page }) => {
    await page.goto(base, navOpts);
    await expect(page.locator('#panel-overview'), { timeout: 10_000 }).toBeVisible();
    await expect(page.locator('#overview'), { timeout: 10_000 }).toContainText('initialized');
  });

  test('tools list loads and can call a tool', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Tools' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh Tools' }).click(actOpts);
    const items = page.locator('#tools-list li');
    await expect(items).toHaveCountGreaterThan(0, { timeout: 10_000 } as any);
    const first = items.first();
    const name = await first.textContent({ timeout: 5_000 });
    await first.click(actOpts);
    await page.getByRole('button', { name: 'Call Tool' }).click(actOpts);
    await expect(page.locator('#tool-result')).toContainText('{', { timeout: 10_000 });
    expect(name).toBeTruthy();
  });

  test('buckets: create, list, delete (idempotent)', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Buckets' }).click(actOpts);

    // Create a local backend if missing
    await page.getByRole('button', { name: 'Backends' }).click(actOpts);
    await page.fill('#be-name', 'e2e_local', actOpts);
    await page.fill('#be-type', 'local', actOpts);
    await page.fill('#be-config', '{"base_path": ".ipfs_kit_e2e"}', actOpts);
    await page.getByRole('button', { name: 'Create' }).click(actOpts);

    await page.getByRole('button', { name: 'Buckets' }).click(actOpts);
    await page.fill('#bucket-name', 'e2e_bucket', actOpts);
    await page.fill('#bucket-backend', 'e2e_local', actOpts);
    await page.getByRole('button', { name: 'Create' }).click(actOpts);
    await page.getByRole('button', { name: 'List' }).click(actOpts);
    await expect(page.locator('#buckets-list')).toContainText('e2e_bucket', { timeout: 10_000 });

    await page.fill('#bucket-del-name', 'e2e_bucket', actOpts);
    await page.getByRole('button', { name: 'Delete' }).click(actOpts);
    await page.getByRole('button', { name: 'List' }).click(actOpts);
  });

  test('pins: create, list, delete (idempotent)', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Pins' }).click(actOpts);
    await page.fill('#pin-cid', 'bafybeigdyrzt5rjessu6', actOpts);
    await page.fill('#pin-name', 'e2e_pin', actOpts);
    await page.getByRole('button', { name: 'Create' }).click(actOpts);
    await page.getByRole('button', { name: 'List' }).click(actOpts);
    await expect(page.locator('#pins-list')).toContainText('bafy', { timeout: 10_000 });
    await page.fill('#pin-del-cid', 'bafybeigdyrzt5rjessu6', actOpts);
    await page.getByRole('button', { name: 'Delete' }).click(actOpts);
  });

  test('integrations: refresh and test by type/name', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Integrations' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts);
    await expect(page.locator('#integrations-list')).toContainText('{', { timeout: 10_000 });

    await page.fill('#intg-type', 'local', actOpts);
    await page.getByRole('button', { name: 'Test all of type' }).click(actOpts);
    await expect(page.locator('#integrations-op')).toContainText('[', { timeout: 10_000 });
  });

  test('logs: lists files and tails once', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Logs' }).click(actOpts);
    await page.getByRole('button', { name: 'List log files' }).click(actOpts);
    // Tail once may no-op if no files; still should not hang
    await page.getByRole('button', { name: 'Tail once' }).click(actOpts);
    await expect(page.locator('#log-file-tail')).toBeVisible({ timeout: 10_000 });
  });
});
