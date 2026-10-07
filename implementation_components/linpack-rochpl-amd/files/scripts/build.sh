#!/usr/bin/env bash
# File: scripts/build.sh
# Description: Install Open MPI if needed and compile bin/rochpl with a host-GCC pin.
# Execution: bash scripts/build.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
# shellcheck disable=SC1091
source scripts/lib/hipcc_host_gcc.sh
if ! command -v mpirun >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y openmpi-bin libopenmpi-dev
fi
make
echo "[PASS] compiled bin/rochpl"
