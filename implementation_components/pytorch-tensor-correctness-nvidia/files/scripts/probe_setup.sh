#!/usr/bin/env bash
# File: scripts/probe_setup.sh
# Description: Fail setup when a tiny fp16 conv2d dies. Called by the NVIDIA
# skeleton only because this convolution component overlays the script.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
echo "[RUN] fp16 conv2d probe"
"${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/scripts/lib/probe_torch_conv2d.py"
