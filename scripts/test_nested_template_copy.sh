#!/usr/bin/env bash
# File: scripts/test_nested_template_copy.sh
# Version: 1.0.0
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-07-18
# Description: Regression test for the prompt-driven nested template-copy workflow.
# Execution: bash scripts/test_nested_template_copy.sh
# Options: None
# Requirements: Bash, Python 3.10+, cp, mktemp, test
# Environment: Run from the template repository; no external virtual environment is required.
# Dependencies: scripts/create_generated_repo.py and the workload matrix workbook
# Variables: WORKLOAD_NUMBER and REPO_NAME identify the regression workload.
# Repository: gpu-bench/sys-bench template
# License: Apache-2.0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKLOAD_NUMBER="${WORKLOAD_NUMBER:-103}"
REPO_NAME="${REPO_NAME:-sys-bench-system-stress-stability}"
PROJECT_ROOT="$(mktemp -d)"
trap 'rm -rf "${PROJECT_ROOT}"' EXIT

cp -a "${SOURCE_ROOT}" "${PROJECT_ROOT}/TEMPLATE_00_32"
SOURCE_COPY="${PROJECT_ROOT}/TEMPLATE_00_32"
TARGET_ROOT="${PROJECT_ROOT}/${WORKLOAD_NUMBER}-${REPO_NAME}"
PROMPT_FILE="${PROJECT_ROOT}/AI_AGENT_PROMPT_SUBMITTED_${WORKLOAD_NUMBER}_20260805_000000.md"
cat > "${PROMPT_FILE}" <<EOF
@docs/AI_AGENT_INSTRUCTIONS.md
Generate workload ${WORKLOAD_NUMBER}.
Legacy: NONE
EOF

echo "[RUN] Creating workload ${WORKLOAD_NUMBER} from the submitted prompt"
python3 "${SOURCE_COPY}/scripts/create_generated_repo.py" \
    --repo-name "${REPO_NAME}" \
    --template-root "${SOURCE_COPY}" \
    --project-root "${PROJECT_ROOT}" \
    --prompt-file "${PROMPT_FILE}"

ACTIVE_COPY="${TARGET_ROOT}/TEMPLATE_00_32_copy"
test -d "${TARGET_ROOT}"
test -d "${ACTIVE_COPY}"
test -f "${ACTIVE_COPY}/BenchmarkSpecDefinitions.xlsx"
test -f "${ACTIVE_COPY}/benchmark_specification.json"
test -f "${TARGET_ROOT}/benchmark_specification.json"
test -f "${TARGET_ROOT}/results/generation_manifest.json"
test ! -d "${ACTIVE_COPY}/TEMPLATE_00_32_copy"

echo "[RUN] Confirming non-forced rerun refuses to overwrite the repository"
set +e
python3 "${SOURCE_COPY}/scripts/create_generated_repo.py" \
    --repo-name "${REPO_NAME}" \
    --template-root "${SOURCE_COPY}" \
    --project-root "${PROJECT_ROOT}" \
    --prompt-file "${PROMPT_FILE}" >/dev/null 2>&1
rerun_status=$?
set -e
test "${rerun_status}" -ne 0

echo "[RUN] Confirming forced rerun remains idempotent"
python3 "${SOURCE_COPY}/scripts/create_generated_repo.py" \
    --repo-name "${REPO_NAME}" \
    --template-root "${SOURCE_COPY}" \
    --project-root "${PROJECT_ROOT}" \
    --prompt-file "${PROMPT_FILE}" \
    --force >/dev/null
test -d "${TARGET_ROOT}/TEMPLATE_00_32_copy"
test ! -d "${TARGET_ROOT}/TEMPLATE_00_32_copy/TEMPLATE_00_32_copy"

echo "[RUN] Confirming the nested template copy is removed after generation"
python3 "${SOURCE_COPY}/scripts/remove_template_copy.py" --repo-root "${TARGET_ROOT}"
test ! -d "${TARGET_ROOT}/TEMPLATE_00_32_copy"
test -f "${TARGET_ROOT}/results/component_gates.json"
python3 - "${TARGET_ROOT}/results/generation_manifest.json" <<'PY'
import json
import sys

manifest = json.loads(open(sys.argv[1], encoding="utf-8").read())
assert manifest.get("template_copy_removed_at"), "template_copy_removed_at not recorded"
assert manifest.get("template_copy_path") == "TEMPLATE_00_32_copy", "provenance record lost"
PY
python3 "${SOURCE_COPY}/scripts/remove_template_copy.py" --repo-root "${TARGET_ROOT}" >/dev/null

echo "[PASS] Nested template-copy regression checks succeeded."
