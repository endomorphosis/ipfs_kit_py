const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');

function waitForHttp(url, timeoutMs) {
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
  child = spawn('bash', ['-lc', 'python3 consolidated_mcp_dashboard.py'], { cwd: process.cwd(), env, stdio: 'pipe' });
  // Initially record the wrapper PID; we'll replace it with the real MCP pid when the pidFile appears
  try { fs.writeFileSync(repoPidFile, String(child.pid)); } catch {}

  process.on('exit', () => { try { child && process.kill(child.pid); } catch {} });

  // Wait for readiness with hard timeout
  await waitForHttp(`${base}/api/mcp/status`, 20_000);

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
