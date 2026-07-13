# Iroh service lifecycle

`IrohService` supervises one named sidecar and exposes async `start`, `stop`,
`restart`, `status`, and `health_check` operations. Starts are idempotent,
serialized within a Python process and across processes, and complete only
after the local RPC readiness probe succeeds. A fixed transport port is
checked before spawning; port `0` remains OS-assigned.

## Process ownership and recovery

The private `run/sidecar.pid` file is a JSON receipt, not a bare PID. It binds
the instance and a random ownership token to the process ID, resolved
executable, and OS process birth time. Stop and restart signal a process only
when all of those values still match. A missing process makes the receipt
stale and it is safely replaced on the next start. A live process that cannot
be proven to belong to the instance is reported as `foreign` and is never
signalled.

Shutdown sends the graceful termination signal, waits the configured timeout,
then escalates to forced termination and waits again. An unexpected exit or a
startup-readiness failure atomically updates `receipts/crash.json`. Repeated
startup failures activate persistent crash-loop protection; an operator can
clear it only while the service is stopped:

```bash
python -m ipfs_kit_py.iroh.service clear-crash-loop --config /etc/ipfs-kit/iroh.json
```

`status()` reports liveness (`running`), readiness (`ready`), PID ownership,
crash count, and crash-loop state separately. This distinction lets an
orchestrator avoid routing work to a live process whose RPC endpoint is not
ready.

## Managed-child and foreground modes

Managed-child mode is intended for an IPFS Kit process that starts the sidecar
and later exits. Sidecar output is appended to the configured private log and
the PID receipt allows another `IrohService` object or process to adopt it.

Foreground mode keeps the Python supervisor attached, forwards SIGINT/SIGTERM
into the normal graceful shutdown path, and exits when the child exits. Use it
under an operating-system service manager:

```bash
python -m ipfs_kit_py.iroh.service foreground \
  --config /etc/ipfs-kit/iroh.json \
  --executable /usr/local/libexec/ipfs-kit-iroh-sidecar
```

## systemd hook

After installing the package and the verified sidecar, a minimal system unit
can delegate lifecycle supervision to foreground mode:

```ini
[Unit]
Description=IPFS Kit Iroh sidecar
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ipfs-kit
Group=ipfs-kit
ExecStart=/opt/ipfs-kit/bin/python -m ipfs_kit_py.iroh.service foreground --config /etc/ipfs-kit/iroh.json --executable /opt/ipfs-kit/bin/ipfs-kit-iroh-sidecar
Restart=on-failure
RestartSec=5
KillMode=process
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Keep systemd's `TimeoutStopSec` greater than the service's graceful and forced
shutdown timeouts combined. Do not run one instance simultaneously through
both systemd and the managed-child command.

## launchd hook

The equivalent per-machine launch daemon uses the same foreground command:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>org.ipfs-kit.iroh</string>
  <key>ProgramArguments</key><array>
    <string>/opt/ipfs-kit/bin/python</string>
    <string>-m</string><string>ipfs_kit_py.iroh.service</string>
    <string>foreground</string><string>--config</string>
    <string>/etc/ipfs-kit/iroh.json</string><string>--executable</string>
    <string>/opt/ipfs-kit/bin/ipfs-kit-iroh-sidecar</string>
  </array>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ProcessType</key><string>Background</string>
</dict></plist>
```

Load it with `launchctl bootstrap system /Library/LaunchDaemons/org.ipfs-kit.iroh.plist`.
The state root and configuration must be writable/readable by the account
selected for the daemon, while retaining the required owner-only permissions.
