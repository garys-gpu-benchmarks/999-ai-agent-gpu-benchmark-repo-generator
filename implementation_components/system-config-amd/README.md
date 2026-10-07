# system-config-amd

Primary collector for AMD System Config Verification (101 / 301).

## Init copies and locks

- `scripts/collect_workload.py`

## Mixins expected

- `harness-self-check` (RAG stubs)
- `rocm-tool-verify-build` (`scripts/build.sh` verifies ROCm tools)

## Agent leftover

PRD/SPEC/README, `requirements.txt`, and public docs. Do not rewrite the collector. Do not map list intent to `rvs -l`.
