#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Compile src/hip_stream.cpp with hipcc into bin/hip-stream.
# Execution: bash scripts/build.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
# shellcheck disable=SC1091
source scripts/lib/hipcc_host_gcc.sh
mkdir -p bin
hipcc -O2 src/hip_stream.cpp -o bin/hip-stream
echo "[PASS] compiled bin/hip-stream"
