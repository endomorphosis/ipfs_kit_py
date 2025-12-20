# Auto-update installation

This document explains how to enable the automated daily update for the `ipfs-kit-mcp` service.

Files added to the repository:
- `scripts/auto_update_and_restart.sh` — script that pulls `known_good`, installs requirements, installs package in editable mode, and restarts the service. Logs to `logs/auto_update.log`.
- `cron/ipfs-kit-update.cron` — sample `/etc/cron.d` file to run the script daily at 04:20.
- `ipfs-kit-mcp.service` — updated in-place to use `Restart=always` and a few safety options.

Quick install steps (run as root):

1. Copy the cron file to `/etc/cron.d`:

```bash
cp /home/barberb/ipfs_kit_py/cron/ipfs-kit-update.cron /etc/cron.d/ipfs-kit-update
chmod 644 /etc/cron.d/ipfs-kit-update
```

2. Make the script executable and ensure ownership for `barberb`:

```bash
chown barberb:barberb /home/barberb/ipfs_kit_py/scripts/auto_update_and_restart.sh
chmod +x /home/barberb/ipfs_kit_py/scripts/auto_update_and_restart.sh
```

3. (Optional) Review the cron file's PATH and SHELL. The cron file runs the job as user `barberb`.

4. Reload systemd to pick up any service file changes and restart the service now (run as root):

```bash
systemctl daemon-reload
systemctl restart ipfs-kit-mcp.service
systemctl status ipfs-kit-mcp.service --no-pager
```

Notes and safety:
- The script performs a `git pull --ff-only`. If the remote has diverged (needs merge), the job will stop and log the issue instead of performing a merge.
- The script uses the Python at `/home/barberb/miniforge3/bin/python` and `pip` via that python. Adjust the `PYTHON` variable in the script if your runtime differs.
- The cron file provided should be copied to `/etc/cron.d` by an administrator. The repository copy is only for source control and review.
- Because these operations modify code and install packages automatically, ensure you trust the `known_good` branch contents and backups are in place.
