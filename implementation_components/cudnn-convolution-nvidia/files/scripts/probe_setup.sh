#!/usr/bin/env bash
# File: scripts/probe_setup.sh
# Description: Fail setup unless bin/cudnn_conv (linked -lcudnn) completes
# one tiny convolution. A torch conv2d result is not a substitute.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
harness="${REPO_ROOT}/bin/cudnn_conv"
[[ -x "${harness}" ]] || { echo "[FAIL] bin/cudnn_conv missing before cuDNN harness probe" >&2; exit 1; }
echo "[RUN] cuDNN harness probe"
output="$("${harness}" \
  --dtype FP16 \
  --conv-direction all \
  --search-strategy find \
  --batch-size 1 \
  --input-channels 8 \
  --input-height 16 \
  --input-width 16 \
  --output-channels 8 \
  --kernel-height 3 \
  --kernel-width 3 \
  --warmup-iters 1 \
  --num-iterations 1)"
printf '%s\n' "${output}"
for direction in fwd bwd_data bwd_weights; do
  grep -q "RESULT direction=${direction} " <<<"${output}" || {
    echo "[FAIL] cuDNN harness probe missing RESULT direction=${direction}" >&2
    exit 1
  }
done
echo "[PASS] cuDNN harness probe"
