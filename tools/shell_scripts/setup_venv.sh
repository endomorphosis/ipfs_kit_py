#!/usr/bin/env bash

# Compatibility wrapper: prefer the repository zero-touch installer.
# This script exists because some docs/automation expect tools/shell_scripts/setup_venv.sh.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

exec ./zero_touch_install.sh --profile dev --node no --playwright no "$@"
