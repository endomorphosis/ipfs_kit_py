const { test, expect } = require('@playwright/test');

const navOpts = { timeout: 10_000 };
const actOpts = { timeout: 8_000 };
const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

test.describe('Consolidated MCP Dashboard', () => {
  test('loads overview and shows status', async ({ page }) => {
    await page.goto(base, navOpts);
    await expect(page.locator('#panel-overview')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('#overview')).toContainText('initialized', { timeout: 10_000 });
  });

  test('tools list loads and can call a tool', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Tools' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh Tools' }).click(actOpts);
    const items = page.locator('#tools-list li');
    await expect(items.first()).toBeVisible({ timeout: 10_000 });
    const name = await items.first().textContent({ timeout: 5_000 });
    await items.first().click(actOpts);
    await page.getByRole('button', { name: 'Call Tool' }).click(actOpts);
    await expect(page.locator('#tool-result')).toContainText('{', { timeout: 10_000 });
    expect(name).toBeTruthy();
  });

  test('buckets: create, list, delete (idempotent)', async ({ page }) => {
    await page.goto(base, navOpts);
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
    // Should contain keys for all seeded backend types
    const list = page.locator('#integrations-list');
    await expect(list).toContainText('{', { timeout: 10_000 });
    for (const key of ['local', 'parquet', 'ipfs', 'ipfs_cluster', 's3', 'github', 'huggingface', 'gdrive']) {
      await expect(list).toContainText(key, { timeout: 10_000 });
    }
    // Exercise type tests for several types
    for (const t of ['local','parquet','ipfs','ipfs_cluster','s3','github','huggingface','gdrive']) {
      await page.fill('#intg-type', t, actOpts);
      await page.getByRole('button', { name: 'Test all of type' }).click(actOpts);
      await expect(page.locator('#integrations-op')).toBeVisible({ timeout: 10_000 });
    }

    // Exercise name-based test for a couple of seeded backends
    for (const name of ['local_fs', 's3_demo']) {
      await page.fill('#intg-name', name, actOpts);
      await page.getByRole('button', { name: 'Test backend' }).click(actOpts);
      const op = page.locator('#integrations-op');
      await expect(op).toBeVisible({ timeout: 10_000 });
      await expect(op).toContainText('"success":', { timeout: 10_000 });
    }
  });

  test('backends: seeded backends are visible in listing', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Backends' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts).catch(() => {});
    const b = page.locator('#backends');
    for (const name of ['local_fs','parquet_meta','ipfs_local','cluster','s3_demo','github','huggingface','gdrive']) {
      await expect(b).toContainText(name, { timeout: 10_000 });
    }
  // Quick probe: Show a couple of backends
  await page.fill('#be-name', 'local_fs', actOpts);
  await page.getByRole('button', { name: 'Show' }).click(actOpts);
  await expect(page.locator('#backend-op')).toContainText('local_fs', { timeout: 10_000 });
  await page.fill('#be-name', 's3_demo', actOpts);
  await page.getByRole('button', { name: 'Show' }).click(actOpts);
  await expect(page.locator('#backend-op')).toContainText('s3_demo', { timeout: 10_000 });

  // Run backend Test and expect a success field to be printed
  await page.fill('#be-name', 'local_fs', actOpts);
  await page.getByRole('button', { name: 'Test' }).click(actOpts);
  await expect(page.locator('#backend-op')).toContainText('"success":', { timeout: 10_000 });
  });

  test('logs: lists files and tails once', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Logs' }).click(actOpts);
    await page.getByRole('button', { name: 'List log files' }).click(actOpts);
    await page.getByRole('button', { name: 'Tail once' }).click(actOpts);
    await expect(page.locator('#log-file-tail')).toBeVisible({ timeout: 10_000 });
  });

  test('files: write and read content under a bucket', async ({ page }) => {
    await page.goto(base, navOpts);
    // Ensure backend and bucket exist for files test
    await page.getByRole('button', { name: 'Backends' }).click(actOpts);
    await page.fill('#be-name', 'e2e_files_local', actOpts);
    await page.fill('#be-type', 'local', actOpts);
    await page.fill('#be-config', '{"base_path": ".ipfs_kit_e2e_files"}', actOpts);
    await page.getByRole('button', { name: 'Create' }).click(actOpts);

    await page.getByRole('button', { name: 'Buckets' }).click(actOpts);
    await page.fill('#bucket-name', 'e2e_files_bucket', actOpts);
    await page.fill('#bucket-backend', 'e2e_files_local', actOpts);
    await page.getByRole('button', { name: 'Create' }).click(actOpts);

    await page.getByRole('button', { name: 'Files' }).click(actOpts);
    await page.fill('#files-bucket', 'e2e_files_bucket', actOpts);
    await page.fill('#files-path', 'hello.txt', actOpts);
    await page.fill('#files-content', 'hello world', actOpts);
    await page.getByRole('button', { name: 'Write' }).click(actOpts);
    await page.getByRole('button', { name: 'List' }).click(actOpts);
    await expect(page.locator('#files-list')).toContainText('hello.txt', { timeout: 10_000 });
    await page.getByRole('button', { name: 'Read' }).click(actOpts);
    await expect(page.locator('#files-read')).toContainText('hello world', { timeout: 10_000 });
  });

  test('cars: import, export, and remove a CAR file', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'CARs' }).click(actOpts);
    await page.fill('#car-name', 'e2e_demo', actOpts);
    await page.fill('#car-b64', 'aGVsbG8gd29ybGQ=', actOpts); // base64('hello world')
    await page.getByRole('button', { name: 'Import' }).click(actOpts);
    await page.getByRole('button', { name: 'List' }).click(actOpts);
    await expect(page.locator('#cars-list')).toContainText('e2e_demo.car', { timeout: 10_000 });
    await page.getByRole('button', { name: 'Export' }).click(actOpts);
    await expect(page.locator('#cars-export')).toContainText('content_b64', { timeout: 10_000 });
    await page.getByRole('button', { name: 'Remove' }).click(actOpts);
    await page.getByRole('button', { name: 'List' }).click(actOpts);
  });

  test('services: refresh and send a control action', async ({ page }) => {
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Services' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts);
    // Verify key services render
    const svc = page.locator('#services');
  for (const name of ['IPFS Daemon', 'IPFS Cluster Service', 'IPFS Cluster Follow', 'Lassie', 'Apache Parquet']) {
      await expect(svc).toContainText(name, { timeout: 10_000 });
    }
    await page.fill('#svc-name', 'IPFS Daemon', actOpts);
    await page.selectOption('#svc-action', 'start');
    await page.getByRole('button', { name: 'Send' }).click(actOpts);
    await expect(page.locator('#svc-op')).toContainText('"status": "ok"', { timeout: 10_000 });

  // Also try another service (stubbed action)
  await page.fill('#svc-name', 'Lassie', actOpts);
  await page.selectOption('#svc-action', 'restart');
  await page.getByRole('button', { name: 'Send' }).click(actOpts);
  await expect(page.locator('#svc-op')).toContainText('"status": "ok"', { timeout: 10_000 });
  });

  test('services: full list present and consistent with backends', async ({ page }) => {
    await page.goto(base, navOpts);
    // Backends → get types
    await page.getByRole('button', { name: 'Backends' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts).catch(() => {});
    const backendsJson = await page.locator('#backends').textContent({ timeout: 10_000 });
    const types = new Set();
    try {
      const parsed = JSON.parse(backendsJson || '{}');
      (parsed.backends || []).forEach(b => types.add(String(b.type || '').toLowerCase()));
    } catch {}

    // Services → ensure expected per types
    await page.getByRole('button', { name: 'Services' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts);
    const servicesJson = await page.locator('#services').textContent({ timeout: 10_000 });
    let names = new Set();
    try {
      const parsed = JSON.parse(servicesJson || '{}');
      (parsed.services || []).forEach(s => names.add(String(s.name || '')));
    } catch {}
    const map = {
      'ipfs': ['IPFS Daemon'],
      'ipfs_cluster': ['IPFS Cluster Service', 'IPFS Cluster Follow'],
      'parquet': ['Apache Parquet (pyarrow)']
    };
    for (const [t, expected] of Object.entries(map)) {
      if (types.has(t)) {
        for (const n of expected) {
          await expect.soft(page.locator('#services')).toContainText(n, { timeout: 10_000 });
          if (!names.has(n)) throw new Error(`Missing service '${n}' for backend type '${t}'`);
        }
      }
    }
  });

  test('services reflect backend types (connectivity check)', async ({ page }) => {
    // Gather backend types from Backends panel
    await page.goto(base, navOpts);
    await page.getByRole('button', { name: 'Backends' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts).catch(() => {});
    const backendsJson = await page.locator('#backends').textContent({ timeout: 10_000 });
    let backendTypes = new Set();
    try {
      const parsed = JSON.parse(backendsJson || '{}');
      (parsed.backends || []).forEach(b => backendTypes.add(String(b.type || '').toLowerCase()));
    } catch {}

    // Load services panel and capture services list
    await page.getByRole('button', { name: 'Services' }).click(actOpts);
    await page.getByRole('button', { name: 'Refresh' }).click(actOpts);
    const servicesJson = await page.locator('#services').textContent({ timeout: 10_000 });
    let serviceNames = new Set();
    try {
      const parsed = JSON.parse(servicesJson || '{}');
      (parsed.services || []).forEach(s => serviceNames.add(String(s.name || '')));
    } catch {}

    // Map backend types to expected service names
    const mapping = {
      'ipfs': ['IPFS Daemon'],
      'ipfs_cluster': ['IPFS Cluster Service', 'IPFS Cluster Follow'],
      'parquet': ['Apache Parquet (pyarrow)']
    };

    // For each known type present in backends, expect the corresponding services to be listed
    for (const [type, expectedServices] of Object.entries(mapping)) {
      if (backendTypes.has(type)) {
        for (const name of expectedServices) {
          await expect.soft(page.locator('#services')).toContainText(name, { timeout: 10_000 });
          // Also verify via parsed Set
          if (!serviceNames.has(name)) {
            throw new Error(`Service '${name}' not listed for backend type '${type}'`);
          }
        }
      }
    }
  });
});
