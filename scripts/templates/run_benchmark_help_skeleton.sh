#!/usr/bin/env bash
# File: scripts/templates/run_benchmark_help_skeleton.sh
# Version: 1.0.0
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-08-14
# Description: Copy-this usage() and early --help handler for generated run_benchmark.sh.
# Execution: Not a standalone entrypoint; copy usage() and the --help loop into run_benchmark.sh.
# Options: --help, --matrix-definition
# Requirements: bash
# Environment: Local generated repository.
# Dependencies: None
# Variables: None
# Repository: gpu-bench/sys-bench template
# License: Apache-2.0
#
# Copy usage() and the early --help loop into generated run_benchmark.sh.
# Do not source this file unchanged.
# Replace the description line with this workload's header Description field.
# Use default CLI profile smoke. YAML sweep.profile stays baseline for LLM Serving.
# Immediately after sourcing common.sh, call
# capture_benchmark_run_command_submitted "$@" so the ledger records argv as
# entered. After argument parsing, call begin_benchmark_run "${profile}" so
# die() writes a ledger row on failure, including a failed ensure_setup.sh.
# After ensure_setup.sh returns, call mark_benchmark_measure_start so
# total_runtime_mm_ss starts at the benchmark. After yaml defaults are applied, call
# set_benchmark_run_command with the fully resolved
# `bash run_benchmark.sh ...` string (submitted flags plus yaml-filled
# parameters that were not on the command line). After RUN_DIR is created,
# call set_benchmark_run_dir "${RUN_DIR}" so the failure row records
# raw_run_dir.
# LLM Serving runners must call wait_for_server
# (default 600 s; HTTP 503 is not ready). Do not hardcode a 180 s wait.
# Keep the script-header Options: field as a compact comma-separated inventory.
# Document -h only if the parser accepts it.
# Include Workload options only for flags this runner actually parses.
# Include Expected environment overrides only when those flags exist.

usage() {
  cat <<'USAGE'
Usage: bash run_benchmark.sh [OPTIONS]

Run the configured benchmark and persist validated results.

Profiles:
  --profile <name>              Run profile: smoke|baseline|extended (default: smoke)
  --smoke                       Run smoke profile
  --baseline                    Run baseline profile
  --extended                    Run extended profile

Execution:
  --device <gpu|cpu>            Execution device (default: gpu)
  --phase <phaseN|N>            Run one phase (phase1|phase2|phase3|phase4, or 1-4)
  --phase1                      Collection
  --phase2                      Collection alias
  --phase3                      Parse only; requires --raw-file <path>
  --phase4                      Validation only
  --raw-file <path>             Existing raw file for --phase3
  --config <file>               Config file (default: config/benchmark_config.yaml)

Validation and logging:
  --validate                    Enable result validation (default)
  --no-validate                 Skip result validation
  --quiet                       Suppress nonessential stdout
  --log-level <level>           ERROR|WARN|INFO|DEBUG (default: INFO)
  --output-format <fmt>         Override config output_format
  --save-options-file <path>    Write resolved CLI options to PATH

Expected environment overrides:
  --kernel-version <ver>        Expected kernel version
  --driver-version <ver>        Expected GPU driver version
  --rocm-version <ver>          Expected ROCm version
  --required-packages <list>    Expected ROCm package list
  --permissions-check <value>   Expected device-permission check setting

Workload options:
  --<flag> <value>              Override a workload-specific parameter

Information:
  --specification               Print this workload's specification and exit
  --matrix-definition           Same as --specification
  --help                        Show this help and exit

Examples:
  bash run_benchmark.sh --profile smoke --validate
  bash run_benchmark.sh --baseline --device gpu
  bash run_benchmark.sh --phase3 --raw-file results/raw/<run>/raw.txt
  bash run_benchmark.sh --specification
  bash run_benchmark.sh --matrix-definition
USAGE
}

for _help_arg in "$@"; do
  case "${_help_arg}" in
    --help)
      usage
      exit 0
      ;;
    --specification|--matrix-definition)
      python3 scripts/print_benchmark_definition.py
      exit 0
      ;;
  esac
done
