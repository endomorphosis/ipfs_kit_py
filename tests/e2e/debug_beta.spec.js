const { test, expect } = require('@playwright/test');

const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

test('debug beta container present and visible', async ({ page }) => {
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  await page.goto(base, { timeout: 20000 });
  // Wait a bit for app.js
  await page.waitForTimeout(500);
  const hasApp = await page.evaluate(() => !!document.getElementById('app'));
  const html = await page.evaluate(() => document.body.outerHTML.slice(0, 5000));
  const exists = await page.evaluate(() => !!document.getElementById('toolrunner-beta-container'));
  const visible = exists && await page.isVisible('#toolrunner-beta-container');
  console.log('HAS_APP', hasApp, 'EXISTS', exists, 'VISIBLE', visible);
  if (errors.length) console.log('CONSOLE_ERRORS', errors.slice(0,5));
  expect(exists).toBeTruthy();
  expect(visible).toBeTruthy();
});
