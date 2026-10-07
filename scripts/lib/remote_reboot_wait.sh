#!/usr/bin/env bash
# File: scripts/lib/remote_reboot_wait.sh
# Version: 1.0.2
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-07-07
# Description: Helper functions for remote reboot/reconnect polling over SSH.
# Execution: source scripts/lib/remote_reboot_wait.sh
# Options: None
# Requirements: bash, ssh
# Environment: Local controller machine issuing SSH commands to remote host.
# Dependencies: ssh, sleep
# Variables: None
# Repository: gpu-bench/sys-bench template
# License: Apache-2.0

set -euo pipefail

# wait_for_remote_reboot <ssh_opts> <remote_user_host> [down_timeout_s] [up_timeout_s] [settle_s]
# Example:
#   wait_for_remote_reboot "-o ConnectTimeout=10 -i /path/to/.ssh/<ssh_key>" "root@<REMOTE_HOST_IP>" 180 420 10
wait_for_remote_reboot() {
    local ssh_opts="$1"
    local remote="$2"
    local down_timeout="${3:-180}"
    local up_timeout="${4:-420}"
    local settle="${5:-10}"
    local elapsed=0

    echo "[INFO] Waiting for remote host to go offline: ${remote}"
    sleep 3
    while ssh ${ssh_opts} "${remote}" "exit" >/dev/null 2>&1; do
        sleep 3
        elapsed=$((elapsed + 3))
        if [[ "${elapsed}" -ge "${down_timeout}" ]]; then
            echo "[ERROR] Timeout waiting for remote host to go offline: ${remote}" >&2
            return 1
        fi
    done
    echo "[PASS] Remote host is offline."

    echo "[INFO] Waiting for remote host to come online: ${remote}"
    elapsed=0
    while ! ssh ${ssh_opts} "${remote}" "exit" >/dev/null 2>&1; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [[ "${elapsed}" -ge "${up_timeout}" ]]; then
            echo "[ERROR] Timeout waiting for remote host to come online: ${remote}" >&2
            return 1
        fi
    done
    echo "[PASS] Remote host is online."
    echo "[INFO] Settling for ${settle}s..."
    sleep "${settle}"
}
