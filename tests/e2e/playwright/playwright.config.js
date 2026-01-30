// Note: Avoid requiring '@playwright/test' here so this config works with `npx @playwright/test` even without local node_modules.
module.exports = {
  testDir: './tests/e2e',
  testMatch: /.*\.spec\.js$/,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.DASHBOARD_URL || 'http://127.0.0.1:8014',
    browserName: 'chromium',
    headless: true,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    navigationTimeout: 10_000,
    actionTimeout: 10_000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        // Lightweight device emulation to avoid importing Playwright devices here
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  globalSetup: require.resolve('./tests/e2e/global-setup.js'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown.js'),
};
