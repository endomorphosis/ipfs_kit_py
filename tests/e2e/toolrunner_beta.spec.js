const { test, expect } = require('@playwright/test');

// Disabled by default to avoid flakiness in main suite; enable with TOOLRUNNER_BETA_TEST=1
test.skip(!process.env.TOOLRUNNER_BETA_TEST, 'Beta Tool Runner tests are opt-in');

const navOpts = { timeout: 20_000 };
const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

function pretty(x){ return JSON.stringify(x, null, 2); }

// Helper: ensure a backend exists
async function ensureBackend(page, name){
  await page.waitForFunction(() => window.MCP && MCP.Backends && MCP.Backends.list);
  // Create if missing
  await page.evaluate(async (backendName) => {
    try { await MCP.Backends.create(backendName, { type: 'local' }); } catch(e) {}
  }, name);
  // Verify present
  const present = await page.evaluate(async (backendName) => {
    const r = await MCP.Backends.list();
    const items = (r && r.result && r.result.items) || [];
    return items.some(it => it.name === backendName);
  }, name);
  expect(present).toBeTruthy();
}

// Verify files_write schema enum includes 'hex'
test('files_write schema uses hex mode', async ({ page }) => {
  await page.goto(base, navOpts);
  await page.waitForFunction(() => window.MCP && MCP.listTools);
  const hasHex = await page.evaluate(async () => {
    const list = await MCP.listTools();
    const tools = (list && list.result && list.result.tools) || [];
    const tw = tools.find(t => t.name === 'files_write') || {};
    const sch = tw.inputSchema || {};
    const props = sch.properties || {};
    const mode = props.mode || {};
    const en = mode.enum || [];
    return en.includes('hex') && !en.includes('base64');
  });
  expect(hasHex).toBeTruthy();
});

// Beta Tool Runner: dynamic select options for backends
test('beta Tool Runner shows dynamic backend options', async ({ page }) => {
  await page.goto(base + '?ui=beta', navOpts);
  // Ensure beta flag is persisted in case query param is missed on reloads
  await page.evaluate(() => localStorage.setItem('toolRunner.beta', 'true'));
  // Wait for container to exist
  await page.waitForSelector('#toolrunner-beta-container');
  await ensureBackend(page, 'e2e_beta');

  // Wait for beta select and choose create_bucket
  const select = page.getByTestId('toolbeta-select');
  await expect(select).toBeVisible();
  // Filter to quickly find create_bucket if many tools
  const filter = page.getByTestId('toolbeta-filter');
  await filter.fill('create_bucket');
  await page.waitForTimeout(150);
  await select.selectOption('create_bucket');

  // Backend field should be a select with our backend as option
  const backendField = page.getByTestId('toolbeta-field-backend');
  await expect(backendField).toBeVisible();
  const tag = await backendField.evaluate(el => el.tagName.toLowerCase());
  expect(tag).toBe('select');
  const options = await backendField.locator('option').allTextContents();
  expect(options.map(s => s.trim())).toContain('e2e_beta');

  // Fill minimal required and run (name required only)
  // Provide unique bucket name to avoid conflicts
  const bucketName = 'e2e_bucket_' + Date.now();
  // There's no data-testid for name input; locate by id pattern
  const nameField = page.locator('#fld_name');
  await nameField.fill(bucketName);
  await page.getByTestId('toolbeta-run').click();
  const out = page.getByTestId('toolbeta-result');
  await expect(out).toContainText('jsonrpc');
});
