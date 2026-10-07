#!/usr/bin/env bash
# File: scripts/lib/align_nvidia_userspace.sh
# Description: Pin libcuda/NVML to the loaded kernel module when nvidia-smi
# fails. Move a system cuDNN tensor_ir library off the default path only when
# its version differs from the virtualenv cuDNN. Wrap this repo's bin/cudnn_conv
# only. No-op for the pin when nvidia-smi already works.
# shellcheck shell=bash

_nvidia_host_note() {
  if declare -F log_status >/dev/null 2>&1; then
    log_status "$1"
  else
    printf '%s\n' "[PASS] $1"
  fi
}

align_nvidia_userspace() {
  # Ubuntu 24.04 images whose userspace already matches the module return here.
  if nvidia-smi >/dev/null 2>&1; then
    return 0
  fi
  local ver libdir hold base
  ver="$(awk '/NVRM version:/{print $8; exit}' /proc/driver/nvidia/version 2>/dev/null || true)"
  libdir="/usr/lib/x86_64-linux-gnu"
  if [[ -z "${ver}" || ! -e "${libdir}/libcuda.so.${ver}" || ! -e "${libdir}/libnvidia-ml.so.${ver}" ]]; then
    echo "[FAIL] nvidia-smi failed and libcuda/libnvidia-ml for the loaded module were not found." >&2
    exit 1
  fi
  hold="/var/lib/nvidia-userspace-mismatch-held"
  mkdir -p "${hold}"
  shopt -s nullglob
  for base in "${libdir}"/libcuda.so.[0-9]* "${libdir}"/libnvidia-ml.so.[0-9]*; do
    [[ -e "${base}" ]] || continue
    case "$(basename "${base}")" in
      "libcuda.so.${ver}"|"libnvidia-ml.so.${ver}"|"libcuda.so.1"|"libnvidia-ml.so.1") continue ;;
    esac
    mv "${base}" "${hold}/"
  done
  shopt -u nullglob
  ln -sfn "libcuda.so.${ver}" "${libdir}/libcuda.so.1"
  ln -sfn "libnvidia-ml.so.${ver}" "${libdir}/libnvidia-ml.so.1"
  ldconfig
  if ! nvidia-smi >/dev/null 2>&1; then
    echo "[FAIL] nvidia-smi still fails after pinning userspace to kernel module ${ver}." >&2
    exit 1
  fi
  _nvidia_host_note "PASS|SETUP pinned libcuda and NVML to ${ver}"
}

_cudnn_triplet() {
  local raw="$1" a b c
  IFS=. read -r a b c _ <<<"${raw}"
  [[ -n "${a:-}" && -n "${b:-}" && -n "${c:-}" ]] || return 1
  printf '%s.%s.%s\n' "${a}" "${b}" "${c}"
}

_venv_cudnn_triplet() {
  local py="${REPO_ROOT}/.venv/bin/python" ver
  [[ -x "${py}" ]] || return 1
  ver="$("${py}" - <<'PY'
import importlib.metadata
for name in ("nvidia-cudnn-cu13", "nvidia-cudnn-cu12"):
    try:
        print(importlib.metadata.version(name))
        raise SystemExit(0)
    except importlib.metadata.PackageNotFoundError:
        continue
raise SystemExit(1)
PY
)" || return 1
  _cudnn_triplet "${ver}"
}

_system_tensor_ir_triplet() {
  local path base ver resolved
  shopt -s nullglob
  for path in /usr/lib/x86_64-linux-gnu/libcudnn_engines_tensor_ir.so.*; do
    [[ -e "${path}" ]] || continue
    resolved="$(readlink -f "${path}" 2>/dev/null || printf '%s' "${path}")"
    base="$(basename "${resolved}")"
    ver="${base#libcudnn_engines_tensor_ir.so.}"
    if _cudnn_triplet "${ver}" >/dev/null 2>&1; then
      _cudnn_triplet "${ver}"
      shopt -u nullglob
      return 0
    fi
  done
  shopt -u nullglob
  return 1
}

isolate_mismatched_cudnn_tensor_ir() {
  # Presence of a system tensor_ir file is not a mismatch. Move it only when
  # its version differs from the virtualenv nvidia-cudnn package. The wheel's
  # libcudnn.so version is the comparison target, because some wheels omit
  # libcudnn_engines_tensor_ir.so.9 entirely.
  local venv_cudnn="" candidate venv_ver sys_ver
  shopt -s nullglob
  for candidate in "${REPO_ROOT}/.venv"/lib/python*/site-packages/nvidia/cudnn/lib; do
    if [[ -d "${candidate}" ]]; then
      venv_cudnn="${candidate}"
    fi
  done
  shopt -u nullglob
  [[ -n "${venv_cudnn}" ]] || return 0
  venv_ver="$(_venv_cudnn_triplet || true)"
  sys_ver="$(_system_tensor_ir_triplet || true)"
  if [[ -z "${sys_ver}" ]]; then
    return 0
  fi
  if [[ -n "${venv_ver}" && "${venv_ver}" == "${sys_ver}" ]]; then
    return 0
  fi
  if [[ -z "${venv_ver}" ]]; then
    _nvidia_host_note "WARN|SETUP system tensor_ir ${sys_ver} left in place; virtualenv cuDNN version is unknown"
    return 0
  fi
  shopt -s nullglob
  local files=(/usr/lib/x86_64-linux-gnu/libcudnn_engines_tensor_ir.so*)
  shopt -u nullglob
  [[ ${#files[@]} -gt 0 ]] || return 0
  local dest="/opt/cudnn-host-extra"
  mkdir -p "${dest}"
  mv "${files[@]}" "${dest}/"
  local versioned
  versioned="$(ls "${dest}"/libcudnn_engines_tensor_ir.so.[0-9]*.[0-9]* 2>/dev/null | head -n 1 || true)"
  if [[ -n "${versioned}" ]]; then
    ln -sfn "$(basename "${versioned}")" "${dest}/libcudnn_engines_tensor_ir.so.9"
    ln -sfn libcudnn_engines_tensor_ir.so.9 "${dest}/libcudnn_engines_tensor_ir.so"
  fi
  ldconfig
  _nvidia_host_note "PASS|SETUP moved cuDNN tensor_ir ${sys_ver} (venv ${venv_ver}) off the default linker path"
  wrap_cudnn_conv
}

_wrap_one_cudnn_conv() {
  local bin="$1"
  [[ -f "${bin}" ]] || return 0
  if head -n 5 "${bin}" 2>/dev/null | grep -q "cudnn-host-extra"; then
    return 0
  fi
  mv "${bin}" "${bin}.real"
  cat > "${bin}" << 'WRAP'
#!/usr/bin/env bash
# cudnn-host-extra: load the system tensor_ir that was moved off the default path
export LD_LIBRARY_PATH="/opt/cudnn-host-extra${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$(dirname "$0")/cudnn_conv.real" "$@"
WRAP
  chmod 755 "${bin}"
  _nvidia_host_note "PASS|SETUP wrapped ${bin} for host cuDNN tensor_ir"
}

wrap_cudnn_conv() {
  # Only this repo's harness. A later setup must not rewrite another repo's
  # bin/cudnn_conv. Skip the wrap when the virtualenv already ships tensor_ir;
  # pointing the binary at the moved system copy would mix two cuDNN builds.
  local dest="/opt/cudnn-host-extra" candidate venv_cudnn=""
  [[ -e "${dest}/libcudnn_engines_tensor_ir.so.9" || -e "${dest}/libcudnn_engines_tensor_ir.so" ]] || return 0
  [[ -n "${REPO_ROOT:-}" ]] || return 0
  shopt -s nullglob
  for candidate in "${REPO_ROOT}/.venv"/lib/python*/site-packages/nvidia/cudnn/lib; do
    if [[ -e "${candidate}/libcudnn_engines_tensor_ir.so.9" ]]; then
      venv_cudnn="${candidate}"
    fi
  done
  shopt -u nullglob
  [[ -z "${venv_cudnn}" ]] || return 0
  _wrap_one_cudnn_conv "${REPO_ROOT}/bin/cudnn_conv"
}

restore_triton_nvidia_bin_exec() {
  # A preserved .venv can arrive with Triton's bundled ptxas mode 644.
  # import triton still succeeds; the JIT exec fails with EACCES.
  local dir found=0 bin
  shopt -s nullglob
  for dir in "${REPO_ROOT}/.venv"/lib/python*/site-packages/triton/backends/nvidia/bin; do
    [[ -d "${dir}" ]] || continue
    found=1
    for bin in "${dir}"/*; do
      [[ -f "${bin}" ]] || continue
      chmod 755 "${bin}"
    done
    if [[ ! -x "${dir}/ptxas" ]]; then
      echo "[FAIL] Triton ptxas is not executable: ${dir}/ptxas" >&2
      exit 1
    fi
    _nvidia_host_note "PASS|SETUP Triton ptxas is executable"
  done
  shopt -u nullglob
  if [[ "${found}" -eq 0 ]]; then
    echo "[FAIL] Triton NVIDIA bin directory was not found under ${REPO_ROOT}/.venv" >&2
    exit 1
  fi
}
