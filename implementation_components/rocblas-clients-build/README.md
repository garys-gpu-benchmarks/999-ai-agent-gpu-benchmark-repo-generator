# rocblas-clients-build

Mixin applied when a primary component sets `contracts.compile_rocblas_bench` and does not already overlay `scripts/build.sh`.

## Provides

- `scripts/build.sh` calling `rocm_compile_rocblas_bench`
- PATH to `<repo>/third_party/rocBLAS/build/release/clients/staging`

This mixin does **not** make the workload a GEMM sweep. `gemm_per_point` stays on the primary (`rocblas-gemm-amd` yes, `system-stress-amd` no).
