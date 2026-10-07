#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-$PWD}"
PYTHON="${REPO_ROOT}/.venv/bin/python"

value_or_not_found() {
  local value="${1:-}"
  [[ -n "${value}" ]] && printf '%s\n' "${value}" || printf '%s\n' "NOT FOUND"
}

ubuntu_version="$(
  . /etc/os-release 2>/dev/null
  printf '%s' "${PRETTY_NAME:-}"
)"
python_version="NOT FOUND"
if [[ -x "${PYTHON}" ]]; then
  python_version="$("${PYTHON}" --version 2>&1 || true)"
fi
[[ -n "${python_version}" ]] || python_version="NOT FOUND"

rocblas_version="$(dpkg-query -W -f='${Version}' rocblas 2>/dev/null || true)"
rocm_version="$(dpkg-query -W -f='${Version}' rocm-core 2>/dev/null || true)"
system_family="$(
  dmidecode -t system 2>/dev/null |
    awk -F: '/^[[:space:]]*Family:/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}'
)"

printf '[INFO] %-31s %s\n' "Repository:" "${REPO_ROOT}"
printf '[INFO] %-31s %s\n' "Ubuntu Version:" "$(value_or_not_found "${ubuntu_version}")"
printf '[INFO] %-31s %s\n' "Python Version:" "${python_version}"
printf '[INFO] %-31s %s\n' "rocBLAS Version:" "$(value_or_not_found "${rocblas_version}")"
printf '[INFO] %-31s %s\n' "ROCm Version:" "$(value_or_not_found "${rocm_version}")"
printf '[INFO] %-31s %s\n' "System:" "$(value_or_not_found "${system_family}")"
printf '[INFO]\n'
