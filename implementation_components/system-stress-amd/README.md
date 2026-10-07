# system-stress-amd

Primary collector for AMD CPU + System Stress (103 / 303).

## Init copies and locks

- `scripts/collect_workload.py` (stress-ng + amd-smi / sysfs telemetry)

## Mixins expected

- `harness-self-check`
- `rocblas-clients-build` (protected `rocm_compile_rocblas_bench`, staging PATH)

## Does not provide

A GEMM sweep. Framework still requires install+verify of `rocblas-bench`. Smoke-check must not apply `transa` / `command_status` GEMM runner rules.

## Agent leftover

Docs and `requirements.txt`. Do not rewrite the collector. Troubleshooting must name the staging binary path.
