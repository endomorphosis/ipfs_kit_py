import type { FullConfig } from '@playwright/test';
import { spawn } from 'child_process';
import http from 'http';

function waitForHttp(url: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url, res => {
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 500) {
          res.resume();
          return resolve();
        }
        res.resume();
        if (Date.now() > deadline) return reject(new Error('Timeout waiting for server'));
        setTimeout(attempt, 300);
      });
      req.on('error', () => {
        if (Date.now() > deadline) return reject(new Error('Timeout waiting for server'));
        setTimeout(attempt, 300);
      });
      req.setTimeout(3000, () => { try { req.destroy(); } catch {}
      });
    };
    attempt();
  });
}

let child: ReturnType<typeof spawn> | null = null;

async function globalSetup(config: FullConfig) {
  const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';
  const url = new URL(base);
  const port = parseInt(url.port || '8014', 10);
  const host = url.hostname || '127.0.0.1';
  const env = { ...process.env };

  // Launch the MCP dashboard via CLI in background
  const args = ['-m', 'ipfs_kit_py.cli', 'mcp', 'start', '--host', host, '--port', String(port), '--foreground'];
  child = spawn(process.execPath, args, {
    cwd: process.cwd(),
    env,
    stdio: 'pipe'
  });

  // Safety: ensure the child process is killed on parent exit
  process.on('exit', () => { try { child && child.kill(); } catch {} });

  // Wait for readiness with hard timeout
  await waitForHttp(`${base}/api/mcp/status`, 20_000);
}

export default globalSetup;
