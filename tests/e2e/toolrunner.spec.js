const { test, expect } = require('@playwright/test');

const navOpts = { timeout: 20_000 };
const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

async function ensureToolSelected(page, toolName) {
  const select = page.locator('select[data-testid="toolrunner-select"]');
  await expect(select).toBeVisible();
  const options = await select.locator('option').allTextContents();
  if (!options.some(t => t.trim() === toolName)) {
    // try filtering
    const filter = page.getByTestId('toolrunner-filter');
    await filter.fill(toolName);
    await page.waitForTimeout(150);
  }
  // re-query and select if present
  const has = await select.locator('option').evaluateAll((opts, name) => opts.some(o => o.value === name), toolName);
  if (has) await select.selectOption(toolName);
  return has;
}

function pretty(obj) { return JSON.stringify(obj, null, 2); }

test.describe('Dynamic Tool Runner UI', () => {
  test('renders and runs a tool', async ({ page }) => {
    await page.goto(base, navOpts);
    // Wait for MCP SDK and Tool Runner UI
    await page.waitForFunction(() => window.MCP && MCP.listTools);
    await page.waitForSelector('select[data-testid="toolrunner-select"]');

    // Prefer files_list; fallback to get_logs
    let tool = 'files_list';
    let ok = await ensureToolSelected(page, tool);
    if (!ok) {
      tool = 'get_logs';
      ok = await ensureToolSelected(page, tool);
    }
    expect(ok).toBeTruthy();

    const args = page.getByTestId('toolrunner-args');
    if (tool === 'files_list') {
      await args.fill(pretty({ path: '.' }));
    } else {
      await args.fill(pretty({ limit: 5 }));
    }

    await page.getByTestId('toolrunner-run').click();
    const result = page.getByTestId('toolrunner-result');
    await expect(result).toBeVisible();
    await expect(result).toContainText('jsonrpc', { timeout: 10_000 });
  });

  test('presets save and load', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.listTools);

    const ok = await ensureToolSelected(page, 'files_list');
    expect(ok).toBeTruthy();

    const argsObj = { path: 'e2e' };
    await page.getByTestId('toolrunner-args').fill(pretty(argsObj));

    const presetName = `e2e_preset_${Date.now()}`;
    await page.locator('#preset-name').fill(presetName);
    await page.locator('#preset-save').click();

    // Change args
    await page.getByTestId('toolrunner-args').fill(pretty({ path: '.' }));

    // Load saved preset and verify
    await page.locator('#preset-select').selectOption(presetName);
    await page.locator('#preset-load').click();

    await expect(page.getByTestId('toolrunner-args')).toHaveValue(pretty(argsObj));
  });

  test('filter narrows options', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.listTools);

    const select = page.locator('select[data-testid="toolrunner-select"]');
    await expect(select).toBeVisible();

    // Count all options, then filter and expect fewer
    const allCount = await select.locator('option').count();
    await page.getByTestId('toolrunner-filter').fill('files_');
    await page.waitForTimeout(150);
    const filteredCount = await select.locator('option').count();

    expect(filteredCount).toBeGreaterThan(0);
    expect(filteredCount).toBeLessThanOrEqual(allCount);

    // And the top option should include 'files_'
    const firstVal = await select.locator('option').first().getAttribute('value');
    expect(firstVal).toContain('files_');
  });
});
