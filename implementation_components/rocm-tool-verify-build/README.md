# rocm-tool-verify-build

Mixin applied when a primary component sets `contracts.build_policy=verify_tools` and does not already overlay `scripts/build.sh`.

## Provides

- verify-only `scripts/build.sh` for `rocminfo`, `rocm-smi`, `amd-smi`, `hipcc`

Used by 101 / 102 style inventory workloads.
