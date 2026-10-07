#!/usr/bin/env bash
# File: scripts/probe_setup.sh
# Description: Fail setup unless bin/gpu_stress runs cuBLAS GEMMs on the GPU.
# Two seconds at 50%: GPU_LOAD_DONE must report gemms > 0.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
harness="${REPO_ROOT}/bin/gpu_stress"
[[ -x "${harness}" ]] || { echo "[FAIL] bin/gpu_stress missing before GPU load probe" >&2; exit 1; }
echo "[RUN] GPU load probe: bin/gpu_stress 2 50"
output="$("${harness}" 2 50)"
printf '%s\n' "${output}"
gemms="$(sed -n 's/^GPU_LOAD_DONE .*gemms=\([0-9][0-9]*\).*/\1/p' <<<"${output}" | tail -n 1)"
if [[ -z "${gemms}" || "${gemms}" -eq 0 ]]; then
  echo "[FAIL] GPU load probe ran no GEMMs" >&2
  exit 1
fi
echo "[PASS] GPU load probe: ${gemms} GEMMs"
