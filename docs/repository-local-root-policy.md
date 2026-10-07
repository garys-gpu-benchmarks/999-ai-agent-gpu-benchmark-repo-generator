# Repository-local root policy

Each generated workload is self-contained under its own repository directory. Setup, build, benchmark execution, source checkouts, caches, logs, and result artifacts must resolve below `REPO_ROOT`.

Recommended layout:

```text
<repo>/
  third_party/          # rocBLAS, FAISS, AITER, SGLang, and other sources
  .cache/               # pip, Hugging Face, Cargo, and build caches
  .venv/
  results/
```

Use `ROCM_SOURCE_ROOT` and workload-specific `*_SOURCE_DIR` variables rather than `${HOME}` for source checkouts. System-level ROCm packages, `/opt/rocm`, APT metadata, and systemd service files remain host-wide by design; they are infrastructure prerequisites, not repository artifacts.
