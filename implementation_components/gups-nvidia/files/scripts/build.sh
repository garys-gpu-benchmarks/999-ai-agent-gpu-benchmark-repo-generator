#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Compile overlay src/gups.c with OpenMP into bin/gups.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
command -v gcc >/dev/null || { echo "[FAIL] gcc missing" >&2; exit 1; }
mkdir -p bin
echo "[RUN] gcc -O2 -fopenmp -o bin/gups src/gups.c"
gcc -O2 -fopenmp -o bin/gups src/gups.c
[[ -x bin/gups ]] || { echo "[FAIL] bin/gups missing" >&2; exit 1; }
echo "[PASS] build.sh compiled bin/gups"
