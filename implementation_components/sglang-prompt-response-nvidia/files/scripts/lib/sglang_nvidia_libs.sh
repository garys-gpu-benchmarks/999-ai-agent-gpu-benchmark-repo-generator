#!/usr/bin/env bash
# Prepend venv NVIDIA CUDA wheel lib dirs to LD_LIBRARY_PATH.
# sglang/deep_gemm need libnvrtc.so.13 from nvidia/cu13/lib; the dynamic
# linker does not search site-packages unless this path is exported.
prepend_venv_nvidia_libs() {
  local python_bin="${1:-${PYTHON_BIN:-python3}}"
  local extra
  extra="$("${python_bin}" - <<'PY'
from pathlib import Path
import sysconfig
root = Path(sysconfig.get_path("purelib")) / "nvidia"
print(":".join(str(path) for path in sorted(root.glob("*/lib")) if path.is_dir()))
PY
)"
  if [[ -n "${extra}" ]]; then
    export LD_LIBRARY_PATH="${extra}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  fi
}
