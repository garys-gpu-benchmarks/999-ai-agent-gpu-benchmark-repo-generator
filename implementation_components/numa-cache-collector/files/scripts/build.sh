#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Compile src/numa_sweep.cpp into bin/numa_sweep.
# Vendor-neutral. Do not require nvcc.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
mkdir -p bin build
echo "[RUN] g++ -O2 -std=c++17 -pthread -o bin/numa_sweep src/numa_sweep.cpp"
g++ -O2 -std=c++17 -pthread -o bin/numa_sweep src/numa_sweep.cpp
[[ -x bin/numa_sweep ]] || { echo "[FAIL] bin/numa_sweep missing" >&2; exit 1; }
echo "[PASS] build.sh compiled bin/numa_sweep"
