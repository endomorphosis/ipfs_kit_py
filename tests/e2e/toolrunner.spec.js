const { test, expect } = require('@playwright/test');

const navOpts = { timeout: 20_000 };
const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

async function openToolsView(page) {
  const toolsBtn = page.locator('.dash-nav .nav-btn', { hasText: 'Tools' });
  if (await toolsBtn.count()) {
    await toolsBtn.first().click();
  }
  await page.waitForSelector('#view-tools', { state: 'visible' });
}

async function ensureToolSelected(page, toolName) {
  // Prefer Tools view select
  const select = page.locator('#view-tools select#tool-select');
  if (await select.count() === 0) {
    await openToolsView(page);
  }
  await expect(page.locator('#view-tools select#tool-select')).toBeVisible();
  const options = await page.locator('#view-tools select#tool-select option').allTextContents();
  if (!options.some(t => t.trim() === toolName)) {
    const filter = page.locator('#view-tools input#tool-filter');
    if (await filter.count()) {
      await filter.fill(toolName);
      await page.waitForTimeout(150);
    }
  }
  const has = await page.locator('#view-tools select#tool-select option').evaluateAll((opts, name) => opts.some(o => o.value === name), toolName);
  if (has) await page.locator('#view-tools select#tool-select').selectOption(toolName);
  return has;
}

function pretty(obj) { return JSON.stringify(obj, null, 2); }

test.describe('Dynamic Tool Runner UI', () => {
  test('renders and runs a tool', async ({ page }) => {
    await page.goto(base, navOpts);
  // Wait for MCP SDK and open Tools view
  await page.waitForFunction(() => window.MCP && MCP.listTools);
  await openToolsView(page);

    // Prefer files_list; fallback to get_logs
    let tool = 'files_list';
    let ok = await ensureToolSelected(page, tool);
    if (!ok) {
      tool = 'get_logs';
      ok = await ensureToolSelected(page, tool);
    }
    expect(ok).toBeTruthy();

  const args = page.locator('#view-tools textarea#tool-args');
    if (tool === 'files_list') {
      await args.fill(pretty({ path: '.' }));
    } else {
      await args.fill(pretty({ limit: 5 }));
    }

  await page.locator('#view-tools button#btn-tool-run').click();
  const result = page.locator('#view-tools pre#tool-result');
    await expect(result).toBeVisible();
    await expect(result).toContainText('jsonrpc', { timeout: 10_000 });
  });

  test('presets save and load', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.listTools);

  await openToolsView(page);
  const ok = await ensureToolSelected(page, 'files_list');
    expect(ok).toBeTruthy();

    const argsObj = { path: 'e2e' };
    await page.getByTestId('toolrunner-args').fill(pretty(argsObj));

  // Use Tools view – no legacy preset UI here; skip if not present
  test.skip(true, 'Presets UI was part of the legacy fallback; skipped for Tools view');

    // Change args
    await page.getByTestId('toolrunner-args').fill(pretty({ path: '.' }));

    // Load saved preset and verify
  // skipped
  });

  test('filter narrows options', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.listTools);

  await openToolsView(page);
  const select = page.locator('#view-tools select#tool-select');
  await expect(select).toBeVisible();

  const allCount = await select.locator('option').count();
  await page.locator('#view-tools input#tool-filter').fill('files_');
  await page.waitForTimeout(150);
  const filteredCount = await select.locator('option').count();

    expect(filteredCount).toBeGreaterThan(0);
    expect(filteredCount).toBeLessThanOrEqual(allCount);

    // And the top option should include 'files_'
  const firstVal = await select.locator('option').first().getAttribute('value');
    expect(firstVal).toContain('files_');
  });
});
