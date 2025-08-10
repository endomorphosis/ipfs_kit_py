const { spawn } = require('child_process');
const http = require('http');
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
  const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';
  const url = new URL(base);
  const port = parseInt(url.port || '8014', 10);
  const host = url.hostname || '127.0.0.1';
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

  // Launch the MCP dashboard in foreground via shell.
  // Prefer ipfs-kit CLI if available; fallback to python3 -m ipfs_kit_py.cli
  const shellCmd = `(
    command -v ipfs-kit >/dev/null 2>&1 && ipfs-kit mcp start --host ${host} --port ${port} --foreground
  ) || (
    python3 -m ipfs_kit_py.cli mcp start --host ${host} --port ${port} --foreground
  )`;
  child = spawn('bash', ['-lc', shellCmd], { cwd: process.cwd(), env: process.env, stdio: 'pipe' });
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
        const payload = JSON.stringify({ jsonrpc: '2.0', method: 'tools/call', id: Date.now(), params: { name, arguments: args || {} } });
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
      { name: 'local_fs', type: 'local', config: { base_path: '.ipfs_kit_e2e_all' } },
      { name: 'parquet_meta', type: 'parquet', config: {} },
      { name: 'ipfs_local', type: 'ipfs', config: {} },
      { name: 'cluster', type: 'ipfs_cluster', config: {} },
      { name: 's3_demo', type: 's3', config: { endpoint: 'http://127.0.0.1:9000', bucket: 'demo' } },
      { name: 'github', type: 'github', config: { token: 'placeholder' } },
      { name: 'huggingface', type: 'huggingface', config: { token: 'placeholder' } },
      { name: 'gdrive', type: 'gdrive', config: { credentials_path: '~/.ipfs_kit/gdrive.json' } },
    ];
    for (const s of seeds) {
      try { await rpcCall('backend_create', s); } catch {}
    }

    // Nudge services by sending a control action (stubbed to log and return ok)
    try {
      const services = [
        'IPFS Daemon',
        'IPFS Cluster Service',
        'IPFS Cluster Follow',
        'Lassie',
        'Apache Parquet (pyarrow)'
      ];
      for (const svc of services) {
        try { await rpcCall('control_service', { service: svc, action: 'start' }); } catch {}
      }
    } catch {}

    // Poll /api/state/backends and /api/services until expected services for present types appear
    function httpJson(pathname) {
      return new Promise((resolve) => {
        const opts = { method: 'GET', hostname: url.hostname, port: url.port || (isHttps ? 443 : 80), path: pathname };
        const req = mod.request(opts, (res) => {
          let data = ''; res.on('data', c => data += String(c));
          res.on('end', () => { try { resolve(JSON.parse(data || '{}')); } catch { resolve({}); } });
        });
        req.on('error', () => resolve({}));
        req.setTimeout(4000, () => { try { req.destroy(); } catch {} resolve({}); });
        req.end();
      });
    }
    const typeToServices = {
      ipfs: ['IPFS Daemon'],
      ipfs_cluster: ['IPFS Cluster Service', 'IPFS Cluster Follow'],
      parquet: ['Apache Parquet (pyarrow)']
    };
    const deadline = Date.now() + 15_000;
    while (Date.now() < deadline) {
      try {
        const be = await httpJson('/api/state/backends');
        const presentTypes = new Set((be.backends || []).map(b => String(b.type || '').toLowerCase()));
        const expected = new Set();
        for (const t of Object.keys(typeToServices)) {
          if (presentTypes.has(t)) {
            for (const s of typeToServices[t]) expected.add(s);
          }
        }
        const svc = await httpJson('/api/services');
        const names = new Set((svc.services || []).map(s => String(s.name || '')));
        let allGood = true; for (const need of expected) { if (!names.has(need)) { allGood = false; break; } }
        if (allGood) break;
      } catch {}
      await new Promise(r => setTimeout(r, 300));
    }
  } catch {}
};
