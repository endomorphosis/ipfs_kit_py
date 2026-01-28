# ARM64 Monitoring Quick Reference

## Quick Start

### Add monitoring to your workflow:

```yaml
steps:
  # 1. Setup
  - name: Initialize monitoring
    run: |
      mkdir -p /tmp/arm64_monitor /tmp/arm64_install_logs
      python scripts/ci/monitor_arm64_installation.py

  # 2. Pre-check
  - name: Verify dependencies before installation
    run: python scripts/ci/verify_arm64_dependencies.py || true

  # 3. Install with monitoring
  - name: Install with monitoring
    run: |
      ./scripts/ci/installation_wrapper.sh my_install \
        pip install your-package

  # 4. Post-check
  - name: Verify dependencies after installation
    run: python scripts/ci/verify_arm64_dependencies.py

  # 5. Upload logs
  - name: Upload monitoring logs
    if: always()
    uses: actions/upload-artifact@v3
    with:
      name: monitoring-logs
      path: |
        /tmp/arm64_monitor/
        /tmp/arm64_install_logs/
```

## Common Commands

### Check dependencies
```bash
python scripts/ci/verify_arm64_dependencies.py
```

### Monitor installation
```bash
./scripts/ci/installation_wrapper.sh install_name your_command
```

### Generate report
```bash
python scripts/ci/monitor_arm64_installation.py
```

### Run demo
```bash
./scripts/ci/demo_monitoring.sh
```

## Log Locations

- Reports: `/tmp/arm64_monitor/`
- Installation logs: `/tmp/arm64_install_logs/`
- Metrics: `*_metrics.json`

## Status Indicators

- ✅ Success
- ❌ Error
- ⚠️ Warning
- 🔄 In Progress
- ℹ️ Info

## Troubleshooting

### Logs missing?
```bash
mkdir -p /tmp/arm64_monitor /tmp/arm64_install_logs
chmod 777 /tmp/arm64_monitor /tmp/arm64_install_logs
```

### Scripts not executable?
```bash
chmod +x scripts/ci/*.sh scripts/ci/*.py
```

### Import errors?
```bash
source venv/bin/activate  # If using venv
python scripts/ci/verify_arm64_dependencies.py
```

## GitHub Actions

View results in:
1. Workflow logs (real-time)
2. Step summary (after run)
3. Artifacts (download)

## Full Documentation

See [ARM64_MONITORING_GUIDE.md](./ARM64_MONITORING_GUIDE.md) for complete details.
