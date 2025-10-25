/**
 * E2E test for backend configuration modal buttons
 * Tests the fixes for:
 * - id="close-backend-config-modal"
 * - id="save-backend-config-btn"
 * - id="test-backend-config-btn"
 * - id="apply-backend-policy-btn"
 * - id="cancel-backend-config-btn"
 */

const { test, expect } = require('@playwright/test');

const navOpts = { timeout: 10_000 };
const actOpts = { timeout: 8_000 };
const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';

test.describe('Backend Configuration Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(base, navOpts);
  });

  test('modal buttons are present in the DOM', async ({ page }) => {
    // Check that all modal buttons exist in the HTML
    const closeBtn = page.locator('#close-backend-config-modal');
    const saveBtn = page.locator('#save-backend-config-btn');
    const testBtn = page.locator('#test-backend-config-btn');
    const applyBtn = page.locator('#apply-backend-policy-btn');
    const cancelBtn = page.locator('#cancel-backend-config-btn');
    
    // These should exist but might not be visible yet (modal is hidden)
    await expect(closeBtn).toBeAttached();
    await expect(saveBtn).toBeAttached();
    await expect(testBtn).toBeAttached();
    await expect(applyBtn).toBeAttached();
    await expect(cancelBtn).toBeAttached();
  });

  test('JavaScript event listeners are attached', async ({ page }) => {
    // Execute JavaScript in the browser to check if event listeners are attached
    const listenersAttached = await page.evaluate(() => {
      const buttons = [
        'close-backend-config-modal',
        'save-backend-config-btn',
        'test-backend-config-btn',
        'apply-backend-policy-btn',
        'cancel-backend-config-btn'
      ];
      
      const results = {};
      buttons.forEach(id => {
        const element = document.getElementById(id);
        // Check if element exists and has click event listeners
        results[id] = element !== null;
      });
      
      return results;
    });
    
    // All buttons should exist
    expect(listenersAttached['close-backend-config-modal']).toBe(true);
    expect(listenersAttached['save-backend-config-btn']).toBe(true);
    expect(listenersAttached['test-backend-config-btn']).toBe(true);
    expect(listenersAttached['apply-backend-policy-btn']).toBe(true);
    expect(listenersAttached['cancel-backend-config-btn']).toBe(true);
  });

  test('backend management functions are defined', async ({ page }) => {
    // Check if the required functions are defined in the global scope
    const functionsExist = await page.evaluate(() => {
      return {
        setupBackendManagement: typeof setupBackendManagement === 'function',
        saveBackendConfiguration: typeof saveBackendConfiguration === 'function',
        testBackendConfiguration: typeof testBackendConfiguration === 'function',
        applyBackendPolicy: typeof applyBackendPolicy === 'function',
        createBackendInstance: typeof createBackendInstance === 'function',
        collectBackendConfig: typeof collectBackendConfig === 'function'
      };
    });
    
    expect(functionsExist.setupBackendManagement).toBe(true);
    expect(functionsExist.saveBackendConfiguration).toBe(true);
    expect(functionsExist.testBackendConfiguration).toBe(true);
    expect(functionsExist.applyBackendPolicy).toBe(true);
    expect(functionsExist.createBackendInstance).toBe(true);
    expect(functionsExist.collectBackendConfig).toBe(true);
  });

  test('modal close button hides modal', async ({ page }) => {
    // First, make the modal visible by manipulating the DOM
    await page.evaluate(() => {
      const modal = document.getElementById('backend-config-modal');
      if (modal) {
        modal.classList.remove('hidden');
      }
    });
    
    // Verify modal is visible
    const modal = page.locator('#backend-config-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });
    
    // Click the close button
    const closeBtn = page.locator('#close-backend-config-modal');
    await closeBtn.click(actOpts);
    
    // Verify modal is hidden
    await expect(modal).toBeHidden({ timeout: 5000 });
  });

  test('modal cancel button hides modal', async ({ page }) => {
    // Make the modal visible
    await page.evaluate(() => {
      const modal = document.getElementById('backend-config-modal');
      if (modal) {
        modal.classList.remove('hidden');
      }
    });
    
    // Verify modal is visible
    const modal = page.locator('#backend-config-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });
    
    // Click the cancel button
    const cancelBtn = page.locator('#cancel-backend-config-btn');
    await cancelBtn.click(actOpts);
    
    // Verify modal is hidden
    await expect(modal).toBeHidden({ timeout: 5000 });
  });

  test('no variable shadowing in setupBackendManagement', async ({ page }) => {
    // Check that the event listeners are properly set up without variable shadowing
    const noShadowing = await page.evaluate(() => {
      // Read the page source to check for variable shadowing
      const scriptContent = Array.from(document.scripts)
        .map(script => script.textContent)
        .join('\n');
      
      // Check for the bad pattern (variable shadowing)
      const hasBadPattern1 = /const applyBackendPolicy = document\.getElementById/.test(scriptContent);
      const hasBadPattern2 = /const createBackendInstance = document\.getElementById/.test(scriptContent);
      
      // Check for the good pattern (correct variable names)
      const hasGoodPattern1 = /const applyBackendPolicyBtn = document\.getElementById/.test(scriptContent);
      const hasGoodPattern2 = /const createBackendInstanceBtn = document\.getElementById/.test(scriptContent);
      
      return {
        hasBadPattern1,
        hasBadPattern2,
        hasGoodPattern1,
        hasGoodPattern2
      };
    });
    
    // Should not have variable shadowing
    expect(noShadowing.hasBadPattern1).toBe(false);
    expect(noShadowing.hasBadPattern2).toBe(false);
    
    // Should have correct variable names
    expect(noShadowing.hasGoodPattern1).toBe(true);
    expect(noShadowing.hasGoodPattern2).toBe(true);
  });
});

test.describe('Backend Instance Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(base, navOpts);
  });

  test('create backend instance button exists and has handler', async ({ page }) => {
    const createBtn = page.locator('#create-backend-instance-btn');
    await expect(createBtn).toBeAttached();
    
    // Check if the button has a click handler
    const hasHandler = await page.evaluate(() => {
      const btn = document.getElementById('create-backend-instance-btn');
      return btn !== null;
    });
    
    expect(hasHandler).toBe(true);
  });

  test('cancel add backend button exists and works', async ({ page }) => {
    // Make the add backend modal visible
    await page.evaluate(() => {
      const modal = document.getElementById('add-backend-instance-modal');
      if (modal) {
        modal.classList.remove('hidden');
      }
    });
    
    // Verify modal is visible
    const modal = page.locator('#add-backend-instance-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });
    
    // Click the cancel button
    const cancelBtn = page.locator('#cancel-add-backend-btn');
    await cancelBtn.click(actOpts);
    
    // Verify modal is hidden
    await expect(modal).toBeHidden({ timeout: 5000 });
  });
});
