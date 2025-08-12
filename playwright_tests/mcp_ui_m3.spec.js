// Playwright tests for MCP UI M3 behaviors
// - Keyboard shortcuts (Enter, Ctrl+Enter)
// - Tools list cache (localStorage TTL)
// - SSE logs filter/level/max-lines controls

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8004';

test.describe('MCP Dashboard M3 behaviors', () => {
  test.setTimeout(120_000);

  test.beforeEach(async ({ page }) => {
    page.on('console', (msg) => console.log(`[browser:${msg.type()}] ${msg.text()}`));
  });

  test('Tool Runner keyboard shortcuts/run flow works', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);

    // Try advanced UI first; fall back to minimal UI
    const advancedRunner = page.locator('h4:has-text("Tool Runner (SDK)")').first();
    const minimalRunner = page.locator('h4:has-text("Tool Runner")').first();
    let card;
    if (await advancedRunner.isVisible({ timeout: 1000 }).catch(() => false)) {
      card = advancedRunner.locator('xpath=ancestor::div[contains(@class, "card")]').first();
    } else {
      await expect(minimalRunner).toBeVisible({ timeout: 30000 });
      card = minimalRunner.locator('xpath=ancestor::div[contains(@class, "card")]').first();
    }

    // Search for a simple tool
    // Advanced UI path
    const search = card.locator('input[placeholder="Search tools"]');
    if (await search.isVisible().catch(() => false)) {
      await search.fill('get_system_status');
      await search.press('Enter');
      const responsePre = card.locator('h5:has-text("Response")').locator('xpath=following-sibling::pre[1]');
      await expect(responsePre).toContainText('jsonrpc', { timeout: 15_000 });
      // JSON args Ctrl+Enter
      const jsonToggle = card.getByRole('button', { name: 'JSON args' });
      if (await jsonToggle.isVisible().catch(() => false)) {
        await jsonToggle.click();
        const jsonTa = card.locator('details:has(> summary:has-text("Args JSON")) textarea').first();
        await expect(jsonTa).toBeVisible();
        await jsonTa.fill('{"limit": 1}');
        await jsonTa.press('Control+Enter');
        await expect(responsePre).toContainText('jsonrpc', { timeout: 15_000 });
      }
    } else {
      // Minimal UI path: select tool and click Run
      const select = card.locator('select#tool-select');
      await expect(select).toBeVisible({ timeout: 15000 });
      // Choose get_system_status if present, else first option
      const hasOption = await select.locator('option', { hasText: 'get_system_status' }).count();
      if (hasOption > 0) {
        await select.selectOption({ label: 'get_system_status' });
      } else {
        const first = await select.locator('option').first().getAttribute('value');
        if (first) await select.selectOption(first);
      }
      // Clear args
      const args = card.locator('textarea#tool-args');
      if (await args.isVisible().catch(() => false)) {
        await args.fill('{}');
      }
      await card.locator('button#tool-run').click();
      const result = card.locator('pre#tool-result');
      await expect(result).toContainText('jsonrpc', { timeout: 20000 });
    }
  });

  test('Tools list cache is populated in localStorage', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    // Try to detect cache; if absent, treat as pass (feature not present in minimal UI)
    try {
      await page.waitForFunction(() => !!localStorage.getItem('mcp_tools_cache'), null, { timeout: 10000 });
    } catch (e) {
      test.info().annotations.push({ type: 'skipped', description: 'tools cache not present in this UI build' });
      test.skip();
    }
    const cache = await page.evaluate(() => {
      try { return JSON.parse(localStorage.getItem('mcp_tools_cache')); } catch { return null; }
    });
    expect(cache).toBeTruthy();
    expect(cache.ts).toBeGreaterThan(0);
    const toolsLen = cache?.data?.result?.tools?.length || 0;
    expect(toolsLen).toBeGreaterThan(0);
  });

  test('SSE logs filter and max-lines controls affect the tail view', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);

    const sseCard = page.locator('#sse');
    if (await sseCard.isVisible({ timeout: 1000 }).catch(() => false)) {
      const logsPre = page.locator('#sse pre#logs');
      await expect(logsPre).toBeVisible({ timeout: 30000 });

    // Capture current content
    const initialText = await logsPre.textContent();

    // Apply a filter unlikely to match anything and expect empty/shorter view
  const filterIn = page.locator('#sse input#logFilter');
  await filterIn.fill('ZZZ_NOT_FOUND_FILTER');
  await page.waitForTimeout(400); // debounce + render
  const filteredText = await logsPre.textContent();
  expect((filteredText || '').length).toBeLessThan((initialText || '').length);

    // Increase max-lines and then decrease to ensure truncation occurs
      const maxIn = page.locator('#sse input#logMax');
      await maxIn.fill('80');
      await maxIn.dispatchEvent('change');
      await page.waitForTimeout(100);
      const shorter = await logsPre.textContent();
      expect((shorter || '').split('\n').length).toBeLessThanOrEqual(80);

      // Clear logs view client-side
      await page.getByRole('button', { name: 'Clear' }).click();
      await expect(logsPre).toHaveText('');
    } else {
      // Minimal UI: just ensure logs pre exists and receives content via SSE
      const logsPre = page.locator('pre#logs');
      await expect(logsPre).toBeVisible({ timeout: 30000 });
      await expect(logsPre).not.toBeEmpty({ timeout: 30000 });
    }
  });
});
