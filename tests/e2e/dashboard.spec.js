const { test, expect } = require('@playwright/test');

const navOpts = { timeout: 15_000 };
const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

test.describe('Consolidated MCP Dashboard (SDK-first)', () => {
  test('status via SDK', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => typeof window.MCP === 'object' && typeof window.MCP.status === 'function');
    const status = await page.evaluate(() => MCP.status());
    expect(status).toBeTruthy();
    expect(status.initialized).toBeTruthy();
    expect(Array.isArray(status.tools)).toBeTruthy();
  });

  test('tools list and simple call via SDK', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.listTools);
    const tools = await page.evaluate(() => MCP.listTools());
    const count = (tools && tools.result && Array.isArray(tools.result.tools)) ? tools.result.tools.length : 0;
    expect(count).toBeGreaterThan(0);
    const res = await page.evaluate(() => MCP.callTool('get_logs', { limit: 5 }));
    expect(res).toBeTruthy();
  });

  test('backends and buckets via SDK', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.Backends && MCP.Buckets);
    // Create backend
    await page.evaluate(() => MCP.Backends.create('e2e_local', { type: 'local', base_path: '.ipfs_kit_e2e' }));
    // Create bucket
    await page.evaluate(() => MCP.Buckets.create('e2e_bucket', 'e2e_local'));
    // List buckets and expect our bucket there
    const list = await page.evaluate(() => MCP.Buckets.list());
    const names = (list && list.result && Array.isArray(list.result.items)) ? list.result.items.map(b => b.name) : [];
    expect(names).toContain('e2e_bucket');
    // Delete bucket
    await page.evaluate(() => MCP.Buckets.delete('e2e_bucket'));
  });

  test('pins via SDK (idempotent)', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.Pins);
    await page.evaluate(() => MCP.Pins.create('bafybeigdyrzt5rjessu6', 'e2e_pin'));
    const pins = await page.evaluate(() => MCP.Pins.list());
    const text = JSON.stringify(pins || {});
    expect(text).toContain('bafy');
    await page.evaluate(() => MCP.Pins.delete('bafybeigdyrzt5rjessu6'));
  });

  test('files via SDK (write/read)', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.Files);
    await page.evaluate(() => MCP.Files.write('e2e/hello.txt', 'hello world', 'text'));
    const list = await page.evaluate(() => MCP.Files.list('e2e'));
    const items = JSON.stringify(list || {});
    expect(items).toContain('hello.txt');
    const read = await page.evaluate(() => MCP.Files.read('e2e/hello.txt'));
    const readStr = JSON.stringify(read || {});
    expect(readStr).toContain('hello world');
  });

  test('services basic probe via SDK', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.Services);
    const st = await page.evaluate(() => MCP.Services.status('ipfs'));
    expect(st).toBeTruthy();
    // Do not start/stop daemons in CI; just assert structure
    const txt = JSON.stringify(st || {});
    expect(txt).toMatch(/bin|api_port_open/);
  });

  test('logs via SDK', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.Logs);
    const logs = await page.evaluate(() => MCP.Logs.get(10));
    expect(logs).toBeTruthy();
  });

  test('CARs are optional (skip if IPFS unavailable)', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => window.MCP && MCP.IPFS && MCP.CARs);
    const hasIpfs = await page.evaluate(async () => {
      try { const v = await MCP.IPFS.version(); return !!(v && (v.result || {}).ok); } catch { return false; }
    });
    test.skip(!hasIpfs, 'IPFS not available');
    // If IPFS present, list cars (may be empty)
    const cars = await page.evaluate(() => MCP.CARs.list());
    expect(cars).toBeTruthy();
  });
});
