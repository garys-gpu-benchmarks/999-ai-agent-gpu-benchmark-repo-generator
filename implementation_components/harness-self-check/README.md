# harness-self-check

Mixin applied to every generated repository unless a primary overlay already owns the same paths.

## Provides

- `scripts/install_rag_amd.sh` (no-op)
- `scripts/install_rag_nvidia.sh` (no-op)

## Leftover work

None. Real RAG workloads (132/232/332/432) overlay the real installers; this mixin skips those destinations.
