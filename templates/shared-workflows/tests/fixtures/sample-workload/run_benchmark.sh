#!/usr/bin/env bash
# Fixture run_benchmark.sh: supports --help like every generated workload.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash run_benchmark.sh [--profile smoke|baseline|extended] [--validate] [--help]
USAGE
}

PROFILE="smoke"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --profile) PROFILE="${2:?--profile needs a value}"; shift 2 ;;
    --validate) shift ;;
    *) echo "[FAIL] unknown option: $1" >&2; exit 1 ;;
  esac
done
bash scripts/sample_check.sh "${PROFILE}"
