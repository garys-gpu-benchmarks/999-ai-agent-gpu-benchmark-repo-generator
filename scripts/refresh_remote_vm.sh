#!/usr/bin/env bash
# File: scripts/refresh_remote_vm.sh
# Version: 1.0.0
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-07-24
# Description: Rebuilds a DigitalOcean validation VM from the Ubuntu 24.04 image.
# Execution: bash scripts/refresh_remote_vm.sh <REMOTE_IPV4> --confirm
# Options: REMOTE_IPV4, --confirm
# Requirements: Bash, doctl, an authenticated doctl context.
# Environment: Local generation host; never run from a generated repository.
# Dependencies: DigitalOcean doctl authentication.
# Variables: IMAGE_SLUG, REMOTE_IPV4.
# Repository: gpu-bench/sys-bench template
# License: Apache-2.0

set -euo pipefail

REMOTE_IPV4="${1:-}"
CONFIRMATION="${2:-}"
IMAGE_SLUG="ubuntu-24-04-x64"

[[ "${REMOTE_IPV4}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || {
  printf '[FAIL] Invalid remote IPv4 address: %s\n' "${REMOTE_IPV4}" >&2
  exit 2
}
[[ "${CONFIRMATION}" == "--confirm" ]] || {
  printf '[FAIL] Rebuilding the remote VM is destructive; pass --confirm explicitly.\n' >&2
  exit 2
}
DOCTL="$(command -v doctl.exe 2>/dev/null || command -v doctl 2>/dev/null || true)"
[[ -n "${DOCTL}" ]] || {
  printf '[FAIL] doctl is required to refresh remote validation VM.\n' >&2
  exit 2
}

printf '[INFO] Looking up DigitalOcean droplet for %s.\n' "${REMOTE_IPV4}"
DROPLET_ID="$(
  "${DOCTL}" compute droplet list --format ID,PublicIPv4 --no-header |
    awk -v ip="${REMOTE_IPV4}" '$2 == ip { print $1; exit }'
)"
[[ -n "${DROPLET_ID}" ]] || {
  printf '[FAIL] No DigitalOcean droplet found for %s.\n' "${REMOTE_IPV4}" >&2
  exit 1
}

"${DOCTL}" compute droplet get "${DROPLET_ID}" --format ID,Name,PublicIPv4,Status
printf '[INFO] Rebuilding droplet %s with %s; existing remote data will be lost.\n' \
  "${DROPLET_ID}" "${IMAGE_SLUG}"
"${DOCTL}" compute droplet-action rebuild "${DROPLET_ID}" --image "${IMAGE_SLUG}"
printf '[PASS] Remote VM rebuild submitted for %s.\n' "${REMOTE_IPV4}"
