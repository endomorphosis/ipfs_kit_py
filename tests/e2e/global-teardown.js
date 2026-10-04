const fs = require('fs');
const path = require('path');

module.exports = async function globalTeardown() {
  try {
    const pidPath = path.join(process.cwd(), 'tests', 'e2e', '.server-pid');
    if (fs.existsSync(pidPath)) {
      const pid = parseInt(String(fs.readFileSync(pidPath)), 10);
      if (!isNaN(pid)) {
        try { process.kill(pid); } catch {}
      }
      try { fs.unlinkSync(pidPath); } catch {}
    }
    // Also try to stop via CLI PID file if present
    try {
      const base = process.env.DASHBOARD_URL || 'http://127.0.0.1:8014';
      const url = new URL(base);
      const port = parseInt(url.port || '8014', 10);
      const home = process.env.HOME || process.env.USERPROFILE || '.';
      const cliPidFile = path.join(home, '.ipfs_kit', `mcp_${port}.pid`);
      if (fs.existsSync(cliPidFile)) {
        const pid = parseInt(String(fs.readFileSync(cliPidFile)), 10);
        if (!isNaN(pid)) { try { process.kill(pid); } catch {} }
        try { fs.unlinkSync(cliPidFile); } catch {}
      }
    } catch {}
  } catch {}
};
