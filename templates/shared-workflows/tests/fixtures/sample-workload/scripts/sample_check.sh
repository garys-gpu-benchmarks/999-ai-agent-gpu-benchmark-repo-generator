#!/usr/bin/env bash
# Fixture helper so shellcheck and bash -n have a scripts/*.sh file to check.
set -euo pipefail
profile="${1:-smoke}"
python3 "$(dirname "${BASH_SOURCE[0]}")/parse_sample.py" "${profile}"
