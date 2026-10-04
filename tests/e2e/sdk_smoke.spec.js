const { test, expect } = require('@playwright/test');

const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';
const navOpts = { timeout: 15_000 };

// Lightweight smoke test to verify the MCP JS SDK is available and functional
// without depending on any specific dashboard DOM structure.
test.describe('MCP JS SDK (window.MCP)', () => {
  test('exposes core and namespaces', async ({ page }) => {
    await page.goto(base, navOpts);
    // Wait for SDK to load
    await page.waitForFunction(() => typeof window.MCP === 'object' && typeof window.MCP.listTools === 'function', null, { timeout: 15000 });

    const shape = await page.evaluate(() => ({
      core: {
        listTools: typeof MCP.listTools,
        callTool: typeof MCP.callTool,
        status: typeof MCP.status,
      },
      namespaces: Object.keys(MCP).filter(k => !['listTools','callTool','status'].includes(k)).sort(),
    }));

    expect(shape.core.listTools).toBe('function');
    expect(shape.core.callTool).toBe('function');
    expect(shape.core.status).toBe('function');
    for (const ns of ['Services','Backends','Buckets','Pins','Files','IPFS','CARs','State','Logs','Server']) {
      expect(shape.namespaces).toContain(ns);
    }
  });

  test('can list tools via SDK and call a simple file op', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.waitForFunction(() => typeof window.MCP === 'object' && typeof window.MCP.listTools === 'function', null, { timeout: 15000 });

    const toolCount = await page.evaluate(async () => {
      const t = await MCP.listTools();
      return (t && t.result && Array.isArray(t.result.tools)) ? t.result.tools.length : 0;
    });
    expect(toolCount).toBeGreaterThan(0);

    const filesOk = await page.evaluate(async () => {
      try {
        const r = await MCP.Files.list('.');
        return !!(r && (r.result || r.error));
      } catch { return false; }
    });
    expect(filesOk).toBeTruthy();
  });
});
