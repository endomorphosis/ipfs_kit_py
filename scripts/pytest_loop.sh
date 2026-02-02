#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Expected venv python at $PYTHON_BIN" >&2
  echo "Hint: run ./zero_touch_install.sh first (creates ./.venv)" >&2
  exit 2
fi

ITERATIONS=10
SLEEP_SECS=0
UNTIL_FAIL=0

usage() {
  cat <<'EOF'
Usage: ./scripts/pytest_loop.sh [--iterations N] [--sleep SECONDS] [--until-fail] [--] [pytest args...]

Defaults:
  --iterations 10
  --sleep 0

Examples:
  ./scripts/pytest_loop.sh --iterations 50 -- -q -x -rs
  ./scripts/pytest_loop.sh --until-fail -- -q -rs
EOF
}

PYTEST_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --iterations)
      ITERATIONS="${2:-}"; shift 2 ;;
    --sleep)
      SLEEP_SECS="${2:-}"; shift 2 ;;
    --until-fail)
      UNTIL_FAIL=1; shift 1 ;;
    -h|--help)
      usage; exit 0 ;;
    --)
      shift
      PYTEST_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$UNTIL_FAIL" -eq 1 ]]; then
  ITERATIONS=0
fi

run_once() {
  local i="$1"
  echo "===== pytest run #$i =====" >&2
  "$PYTHON_BIN" -m pytest "${PYTEST_ARGS[@]}"
}

i=1
while :; do
  if [[ "$ITERATIONS" -ne 0 && "$i" -gt "$ITERATIONS" ]]; then
    echo "Completed $ITERATIONS iterations." >&2
    exit 0
  fi

  if ! run_once "$i"; then
    echo "Run #$i failed." >&2
    exit 1
  fi

  if [[ "$SLEEP_SECS" != "0" ]]; then
    sleep "$SLEEP_SECS"
  fi

  i=$((i+1))
done
