#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Compile src/hip_memcpy_bw.cpp with hipcc and a host-GCC pin.
# Execution: bash scripts/build.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
# shellcheck disable=SC1091
source scripts/lib/hipcc_host_gcc.sh
mkdir -p bin
hipcc -O2 src/hip_memcpy_bw.cpp -o bin/hip_memcpy_bw
echo "[PASS] compiled bin/hip_memcpy_bw"
