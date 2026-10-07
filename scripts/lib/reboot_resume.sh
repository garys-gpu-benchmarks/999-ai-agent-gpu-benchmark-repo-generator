#!/usr/bin/env bash
# File: scripts/lib/reboot_resume.sh
# Version: 1.0.2
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-07-07
# Description: Helper functions for local reboot request + resume after user login.
# Execution: source scripts/lib/reboot_resume.sh
# Options: None
# Requirements: bash, sudo
# Environment: Runs on target system where reboot is requested.
# Dependencies: date, reboot
# Variables: RESUME_STATE_FILE
# Repository: gpu-bench/sys-bench template
# License: Apache-2.0

set -euo pipefail

RESUME_STATE_FILE="${RESUME_STATE_FILE:-.resume_state.env}"

save_resume_state() {
    local phase="$1"
    local step="$2"
    local script_path="$3"
    {
        echo "RESUME_PHASE=${phase}"
        echo "RESUME_STEP=${step}"
        echo "RESUME_SCRIPT=${script_path}"
        echo "RESUME_SAVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${RESUME_STATE_FILE}"
    echo "[INFO] Resume state written to ${RESUME_STATE_FILE}"
}

clear_resume_state() {
    if [[ -f "${RESUME_STATE_FILE}" ]]; then
        rm -f "${RESUME_STATE_FILE}"
        echo "[INFO] Resume state cleared: ${RESUME_STATE_FILE}"
    fi
}

resume_detect_and_prompt() {
    if [[ ! -f "${RESUME_STATE_FILE}" ]]; then
        return 0
    fi

    # shellcheck disable=SC1090
    source "${RESUME_STATE_FILE}"
    echo "[WARN] Found previous reboot-resume state:"
    echo "       phase=${RESUME_PHASE:-unknown} step=${RESUME_STEP:-unknown} saved_at=${RESUME_SAVED_AT:-unknown}"

    read -r -p "Resume from saved state? [Y/n]: " _resume_choice
    _resume_choice="${_resume_choice:-Y}"
    if [[ "${_resume_choice}" =~ ^[Yy]$ ]]; then
        export RESUME_PHASE="${RESUME_PHASE:-}"
        export RESUME_STEP="${RESUME_STEP:-}"
        export RESUME_SCRIPT="${RESUME_SCRIPT:-}"
        echo "[INFO] Continuing from resume state."
    else
        clear_resume_state
        unset RESUME_PHASE RESUME_STEP RESUME_SCRIPT
        echo "[INFO] Starting fresh run."
    fi
}

request_reboot_and_exit() {
    local reason="$1"
    echo "[WARN] Reboot requested: ${reason}"
    echo "[WARN] After login, re-run this script to continue from saved state."
    sudo reboot
    exit 0
}
