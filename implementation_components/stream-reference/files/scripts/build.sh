#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Compile official overlay src/stream.c with GCC OpenMP.
# Vendor-neutral. Do not require nvcc. Do not compile cuda_stack_probe.cu first.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
ARRAY_SIZE="${STREAM_ARRAY_SIZE:-10000000}"
NTIMES="${NTIMES:-2}"
mkdir -p build bin
echo "[RUN] gcc -O3 -fopenmp -DSTREAM_ARRAY_SIZE=${ARRAY_SIZE} -DNTIMES=${NTIMES} src/stream.c -o build/stream -lm"
gcc -O3 -fopenmp -DSTREAM_ARRAY_SIZE="${ARRAY_SIZE}" -DNTIMES="${NTIMES}" src/stream.c -o build/stream -lm
cp -f build/stream bin/stream
# An existing bin/stream keeps its mode across cp. Restore the execute bit.
chmod +x build/stream bin/stream
[[ -x build/stream && -x bin/stream ]] || { echo "[FAIL] STREAM binary missing" >&2; exit 1; }
echo "[PASS] built build/stream and bin/stream"
