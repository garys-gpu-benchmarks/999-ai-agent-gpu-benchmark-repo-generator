#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Compile repository-local rocblas-bench and put the staging directory on PATH.
# Execution: bash scripts/build.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
export ROCM_SOURCE_ROOT="${REPO_ROOT}/third_party"
export ROCBLAS_SOURCE_DIR="${ROCM_SOURCE_ROOT}/rocBLAS"
export PATH="/opt/rocm/bin:${PATH}"
export LD_LIBRARY_PATH="/opt/rocm/lib:/opt/rocm/lib64:${LD_LIBRARY_PATH:-}"
# shellcheck disable=SC1091
source scripts/lib/rocm_install.sh
rocm_compile_rocblas_bench
STAGING="${ROCBLAS_SOURCE_DIR}/build/release/clients/staging"
export PATH="${STAGING}:${PATH}"
if ! command -v rocblas-bench >/dev/null 2>&1; then
  echo "[FAIL] rocblas-bench not on PATH after compile; expected ${STAGING}/rocblas-bench" >&2
  exit 1
fi
rocblas-bench -h >/dev/null
echo "[PASS] rocblas-bench is present at ${STAGING}/rocblas-bench"
