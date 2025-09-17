const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');

function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let delay = 300;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url, res => {
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 500) {
          res.resume();
          return resolve();
        }
        // Fallback probe to /healthz before retrying
        res.resume();
        const u = new URL(url);
        const healthz = `${u.origin}/healthz`;
        const r2 = http.get(healthz, r => {
          if (r.statusCode && r.statusCode >= 200 && r.statusCode < 500) {
            r.resume();
            return resolve();
          }
          r.resume();
          if (Date.now() > deadline) return reject(new Error('Timeout waiting for server'));
          delay = Math.min(delay * 1.5, 1200);
          setTimeout(attempt, delay);
        });
        r2.on('error', () => {
          if (Date.now() > deadline) return reject(new Error('Timeout waiting for server'));
          delay = Math.min(delay * 1.5, 1200);
          setTimeout(attempt, delay);
        });
        r2.setTimeout(5000, () => { try { r2.destroy(); } catch {} });
      });
      req.on('error', () => {
        // On error, also try /healthz before retrying
        const u = new URL(url);
        const healthz = `${u.origin}/healthz`;
        const r2 = http.get(healthz, r => {
          if (r.statusCode && r.statusCode >= 200 && r.statusCode < 500) {
            r.resume();
            return resolve();
          }
          r.resume();
          if (Date.now() > deadline) return reject(new Error('Timeout waiting for server'));
          delay = Math.min(delay * 1.5, 1200);
          setTimeout(attempt, delay);
        });
        r2.on('error', () => {
          if (Date.now() > deadline) return reject(new Error('Timeout waiting for server'));
          delay = Math.min(delay * 1.5, 1200);
          setTimeout(attempt, delay);
        });
        r2.setTimeout(5000, () => { try { r2.destroy(); } catch {} });
      });
      req.setTimeout(5000, () => { try { req.destroy(); } catch {} });
    };
    setTimeout(attempt, 800);
  });
}

let child = null;
let pidFile = null; // CLI PID in ~/.ipfs_kit
const repoPidFile = path.join(process.cwd(), 'tests', 'e2e', '.server-pid');

module.exports = async function globalSetup() {
  // Use a fixed port to align with tests' default fallback, and export for clarity
  const host = '127.0.0.1';
  const port = 8014;
  const base = `http://${host}:${port}`;
  process.env.DASHBOARD_URL = base;
  const home = process.env.HOME || process.env.USERPROFILE || '.';
  pidFile = path.join(home, '.ipfs_kit', `mcp_${port}.pid`);

  // Attempt to stop any previous instance on the same port by pid file
  try {
    if (fs.existsSync(pidFile)) {
      const pid = parseInt(String(fs.readFileSync(pidFile)), 10);
      if (!isNaN(pid)) {
        try { process.kill(pid); } catch {}
      }
    }
  } catch {}

  // Best-effort: free up the port and kill stale consolidated servers
  try {
    // Kill anything on the port (Linux fuser). Ignore errors.
    await new Promise((r) => {
      const k = spawn('bash', ['-lc', `fuser -k -n tcp ${port} >/dev/null 2>&1 || true`], { stdio: 'ignore' });
      k.on('exit', () => r(undefined));
    });
  } catch {}
  try {
    await new Promise((r) => {
      const k = spawn('bash', ['-lc', `pkill -f consolidated_mcp_dashboard.py >/dev/null 2>&1 || true`], { stdio: 'ignore' });
      k.on('exit', () => r(undefined));
    });
  } catch {}

  // Launch the consolidated MCP dashboard directly to ensure JSON-RPC shapes and UI match tests
  const env = { ...process.env, MCP_HOST: String(host), MCP_PORT: String(port) };
  const logPath = path.join(process.cwd(), 'dashboard_test.log');
  try { fs.writeFileSync(logPath, ''); } catch {}
  const cmd = `python3 consolidated_mcp_dashboard.py >> ${logPath} 2>&1`;
  child = spawn('bash', ['-lc', cmd], { cwd: process.cwd(), env, stdio: 'ignore' });
  // Initially record the wrapper PID; we'll replace it with the real MCP pid when the pidFile appears
  try { fs.writeFileSync(repoPidFile, String(child.pid)); } catch {}

  process.on('exit', () => { try { child && process.kill(child.pid); } catch {} });

  // Wait for readiness with hard timeout; fail early if child exits unexpectedly
  const exitEarly = new Promise((_, reject) => {
    child.once('exit', (code, signal) => {
      let tail = '';
      try {
        const content = fs.readFileSync(logPath, 'utf8');
        tail = content.slice(-4000);
      } catch {}
      reject(new Error(`Server exited early (code=${code} signal=${signal})\n${tail}`));
    });
  });
  await Promise.race([
    waitForHttp(`${base}/api/mcp/status`, 45_000),
    exitEarly,
  ]);

  // Debug: fetch index HTML and log a small snippet to verify SDK script presence
  try {
    await new Promise((resolve) => setTimeout(resolve, 150));
    const url = new URL(base);
    const isHttps = url.protocol === 'https:';
    const mod = isHttps ? require('https') : require('http');
    await new Promise((resolve) => {
      const req = mod.request({ method: 'GET', hostname: url.hostname, port: url.port || (isHttps ? 443 : 80), path: '/' }, (res) => {
        let buf = '';
        res.on('data', (c) => (buf += String(c||'')));
        res.on('end', () => {
          const head = buf.slice(0, 400).replace(/\s+/g, ' ').trim();
          const hasMcp = buf.includes('window.MCP');
          console.log('[global-setup] INDEX HEAD:', head);
          console.log('[global-setup] INDEX has window.MCP literal:', hasMcp);
          resolve();
        });
      });
      req.on('error', () => resolve());
      req.end();
    });
  } catch {}

  // If the CLI wrote a PID file, prefer that PID for teardown
  try {
    if (fs.existsSync(pidFile)) {
      const realPid = parseInt(String(fs.readFileSync(pidFile)), 10);
      if (!isNaN(realPid)) {
        fs.writeFileSync(repoPidFile, String(realPid));
      }
    }
  } catch {}

  // Seed a set of backends so Integrations and Backends panels show all types
  // Use JSON-RPC tools/call endpoint for idempotent creation
  try {
    await new Promise((resolve) => setTimeout(resolve, 250));
    const url = new URL(base);
    const isHttps = url.protocol === 'https:';
    const mod = isHttps ? require('https') : require('http');
    function rpcCall(name, args) {
      return new Promise((resolve, reject) => {
        const payload = JSON.stringify({ name, args: args || {} });
        const opts = {
          method: 'POST',
          hostname: url.hostname,
          port: url.port || (isHttps ? 443 : 80),
          path: '/mcp/tools/call',
          headers: { 'content-type': 'application/json', 'content-length': Buffer.byteLength(payload) },
        };
        const req = mod.request(opts, (res) => {
          let data = '';
          res.on('data', (c) => (data += String(c)));
          res.on('end', () => {
            try {
              const j = JSON.parse(data || '{}');
              resolve(j.result || j);
            } catch (e) {
              resolve({});
            }
          });
        });
        req.on('error', (e) => resolve({ error: String(e) }));
        req.setTimeout(5000, () => { try { req.destroy(); } catch {} resolve({ timeout: true }); });
        req.write(payload);
        req.end();
      });
    }

    const seeds = [
      { name: 'local_fs', config: { type: 'local', base_path: '.ipfs_kit_e2e_all' } },
      { name: 'parquet_meta', config: { type: 'parquet' } },
      { name: 'ipfs_local', config: { type: 'ipfs' } },
      { name: 'cluster', config: { type: 'ipfs_cluster' } },
      { name: 's3_demo', config: { type: 's3', endpoint: 'http://127.0.0.1:9000', bucket: 'demo' } },
      { name: 'github', config: { type: 'github', token: 'placeholder' } },
      { name: 'huggingface', config: { type: 'huggingface', token: 'placeholder' } },
      { name: 'gdrive', config: { type: 'gdrive', credentials_path: '~/.ipfs_kit/gdrive.json' } },
    ];
    for (const s of seeds) {
      try { await rpcCall('create_backend', s); } catch {}
    }
  } catch {}
};
