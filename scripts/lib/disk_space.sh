#!/usr/bin/env bash
# File: scripts/lib/disk_space.sh
# Description: Free-space checks and reuse of an already completed install.
# Execution: source scripts/lib/disk_space.sh
# A second virtual environment, a full SDXL snapshot, or an nvcc JIT into a
# full filesystem fails with "No space left on device" after a partial write.
# Callers check the destination first, or link a finished copy of this repo.

require_free_kib() {
  local path="$1"
  local need_kib="$2"
  local why="$3"
  local avail_kib
  mkdir -p "${path}"
  avail_kib="$(df -Pk "${path}" | awk 'NR==2 {print $4}')"
  if [[ -z "${avail_kib}" || ! "${avail_kib}" =~ ^[0-9]+$ || "${avail_kib}" -lt "${need_kib}" ]]; then
    printf '[FAIL] %s\n' "${why}" >&2
    printf '[FAIL] path=%s free_kib=%s need_kib=%s\n' "${path}" "${avail_kib:-unknown}" "${need_kib}" >&2
    return 1
  fi
  printf '[PASS] free_kib=%s need_kib=%s path=%s (%s)\n' "${avail_kib}" "${need_kib}" "${path}" "${why}"
}

reuse_completed_venv() {
  local name here root candidate cand_real seen=" "
  local roots=()
  name="$(basename "${REPO_ROOT}")"
  here="$(readlink -f "${REPO_ROOT}")"
  if [[ -n "${BENCHMARK_INSTALL_ROOTS:-}" ]]; then
    IFS=':' read -r -a roots <<< "${BENCHMARK_INSTALL_ROOTS}"
  fi
  roots+=("$(dirname "${REPO_ROOT}")" /root /opt/workloads)
  for root in "${roots[@]}"; do
    [[ -n "${root}" && -d "${root}" ]] || continue
    case "${seen}" in
      *" ${root} "*) continue ;;
    esac
    seen+=" ${root} "
    candidate="${root%/}/${name}"
    [[ -d "${candidate}" ]] || continue
    cand_real="$(readlink -f "${candidate}")"
    [[ "${cand_real}" == "${here}" ]] && continue
    [[ -f "${candidate}/.setup_state" && -x "${candidate}/.venv/bin/python" ]] || continue
    if [[ -e "${REPO_ROOT}/.venv" && ! -L "${REPO_ROOT}/.venv" ]]; then
      printf '[INFO] %s already has a .venv; not linking %s\n' "${REPO_ROOT}" "${candidate}"
      return 1
    fi
    printf '[INFO] Reusing completed install at %s\n' "${candidate}"
    ln -sfn "${candidate}/.venv" "${REPO_ROOT}/.venv"
    cp -f "${candidate}/.setup_state" "${REPO_ROOT}/.setup_state"
    if [[ -f "${candidate}/results/nvcc_toolkit.env" ]]; then
      mkdir -p "${REPO_ROOT}/results"
      cp -f "${candidate}/results/nvcc_toolkit.env" "${REPO_ROOT}/results/nvcc_toolkit.env"
    fi
    return 0
  done
  return 1
}

sglang_server_disk_failure() {
  local log="${1:-}"
  [[ -f "${log}" ]] || return 1
  if grep -q "No space left on device" "${log}"; then
    printf '[FAIL] SGLang server log reports No space left on device while nvcc wrote JIT files.\n' >&2
    grep -F "No space left on device" "${log}" | tail -n 3 >&2 || true
    return 0
  fi
  return 1
}
