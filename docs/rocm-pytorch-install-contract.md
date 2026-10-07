# ROCm PyTorch Installation Contract

This contract applies to GPU workloads whose `Framework`, installation summary, or implementation requires PyTorch on an AMD ROCm host.

## Required behavior

1. `setup.sh` must not install unconstrained `torch` or `torchvision` from the default PyPI index for a ROCm workload.
2. Parser-only dependencies may remain in `requirements.txt`; accelerator frameworks must be installed explicitly from the official ROCm wheel index.
3. The wheel index and package versions must be configurable through environment variables and documented in `README.md`, for example:

### Agent safeguard: verify pins before generating setup

AI coding agents must not copy version pins from an unrelated template example or assume that a version exists on the selected ROCm index. Before committing defaults in a generated `setup.sh`, query the exact index for both packages and select a compatible pair:

# For non-vLLM ROCm/PyTorch workloads:
```bash
torch_versions="$(python3 -m pip index versions torch \
  --index-url "${PYTORCH_ROCM_INDEX_URL}" 2>&1)"
torchvision_versions="$(python3 -m pip index versions torchvision \
  --index-url "${PYTORCH_ROCM_INDEX_URL}" 2>&1)"
grep -Fq "${PYTORCH_VERSION}" <<< "${torch_versions}"
grep -Fq "${TORCHVISION_VERSION}" <<< "${torchvision_versions}"
```

Do not pipe `pip index` directly into `grep -q` while `set -o pipefail` is active: `grep` can close the pipe after a match and make pip report a `BrokenPipeError`, producing a false "version unavailable" failure.

The generated setup must fail early with an actionable message if either requested version is unavailable. Record the verified pair in the generated README and keep both versions overrideable through environment variables. Never leave an example pin in production setup code without checking that the index actually publishes it.

Ubuntu 24.04 / ROCm 7.2:

```bash
PYTORCH_ROCM_INDEX_URL="${PYTORCH_ROCM_INDEX_URL:-https://download.pytorch.org/whl/rocm7.2}"
PYTORCH_VERSION="${PYTORCH_VERSION:-2.11.0+rocm7.2}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.26.0+rocm7.2}"
python -m pip install \
  "torch==${PYTORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" \
  --index-url "${PYTORCH_ROCM_INDEX_URL}"
```

Ubuntu 26.04 / ROCm 7.14: `https://download.pytorch.org/whl/rocm7.14` is empty. Use the AMD multi-arch index plus the gfx942 device package. Do not install `torch[device-all]`.

```bash
PYTORCH_ROCM_INDEX_URL="${PYTORCH_ROCM_INDEX_URL:-https://repo.amd.com/rocm/whl-multi-arch/}"
PYTORCH_VERSION="${PYTORCH_VERSION:-2.12.0+rocm7.14.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.27.0+rocm7.14.0}"
python -m pip install \
  "torch==${PYTORCH_VERSION}" \
  "amd-torch-device-gfx942==${PYTORCH_VERSION}" \
  --index-url "${PYTORCH_ROCM_INDEX_URL}" \
  --extra-index-url https://pypi.org/simple
```

vLLM on Ubuntu 26.04 / Python 3.14 pairs with `torch==2.11.0+rocm7.14.0`, matching `amd-torch-device-gfx942`, and `torchvision==0.26.0+rocm7.14.0`. Official `wheels.vllm.ai/rocm/` remains a prefix check only (still cp312 / rocm723). After that check, install the AMD cp314 vLLM wheel and the matching flash-attn wheel. Extra-deps pip is non-fatal because `amd-quark>=0.8.99` is unpublished; always install `uvloop`, `fastapi`, and `aiohttp>=3.13.3` so `vllm.entrypoints.openai.api_server` can start.

## Ubuntu 26.04 / ROCm 7.14 extras (AMD 301–332)

Do not rewrite `scripts/lib/rocm_install_24_04.sh` or `scripts/lib/rocm_install_26_04.sh`. `scripts/lib/rocm_install.sh` is a dispatcher only.

- Kernel pin: 7.0.0. Python pin: 3.14.4. ROCm pin: 7.14 (TheRock at `/opt/rocm`).
- TheRock layout: `amdrocm` / `amdrocm-blas7.14-gfx942`. There is no `/opt/rocm/rocblas` directory. OpenMPI is `HPL_MPI_DIR=/usr/lib/x86_64-linux-gnu/openmpi`.
- `amd-smi metric` crashes on this stack; `amd-smi static` and `rocm-smi` work.
- AITER wheel: `https://rocm.frameworks.amd.com/whl-multi-arch/vllm-cdna/amd-aiter/`. Import name is `aiter`, not `amd_aiter`. Prefer the wheel; do not clone `third_party/aiter` by default.
- SGLang has no proven ROCm 7.14 / cp314 wheel. Smoke uses `scripts/tiny_sglang_server.py`. Setup that sees Framework `sglang` must default `BENCHMARK_COMPILE_SGLANG=1` and die if `import sglang` still fails. Pin `SGLANG_REPO_REF=v0.5.13.post1`. Also install `xgrammar`, `timm`, `compressed-tensors`, `orjson`, `pybase64`, `starlette`, `pyzmq`, and ROCm `torchvision`. Skip `outlines` (needs cargo). After install, patch `qwen3_asr` `AutoConfig.register(..., exist_ok=True)` and require `python -m sglang.launch_server --help` on both the compile and already-importable paths.
- multichase (109 / 309) must chase through `void * volatile`. A `(void)p;` sink is not enough: gcc `-O2` deletes the loop and baseline `1.33e9` iters validate as `latency_ns=0`.
- vLLM 128/129/328/329: `max_model_len` is `input_len + output_len + 64` (BOS/tokenizer slack), capped at 32768. Do not set `max_model_len=$((INPUT_LEN + OUTPUT_LEN))`.
- JAX: plugin first from the AMD index (`jax_rocm7_plugin==0.10.0+rocm7.14.0` and `jax_rocm7_pjrt==0.10.0+rocm7.14.0`), then PyPI `jax==0.10.0` and `jaxlib==0.10.0`. `jax.devices()` should show `RocmDevice`.
- hipcc (Clang 23) prefers GCC 16. That tree does not expose `<cstdlib>` / `<cmath>` to `__clang_hip_runtime_wrapper.h`, so hipMemcpy / BabelStream / RCCL `scripts/build.sh` dies in about one second with `'cstdlib' file not found`. Every hipcc compile must source `scripts/lib/hipcc_host_gcc.sh` or pass `--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/15`. Setup installs `g++-15`. Always export `LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64` so HIP binaries find `libamdhip64.so.7`.
- rocHPL (120 / 320) host allocations must use 64-bit sizes. Do not run extended `N=65536` (228 min hang, then `hipErrorIllegalAddress`). Keep the `linpack-rochpl-amd` overlay. Clamp `N>=65536` to 32768 and allow up to 16 timed repeats at `N=32768` (~12 min). Missing `help-prun.txt` under pmix2/prrte3 is a secondary Open MPI 5 help-text miss after the child already crashed.
- AMD RAG (132 / 332) must use the `rag-faiss-end2end-amd` overlay. Setup calls `scripts/install_rag_amd.sh` after ROCm torch exists. Do not install a CUDA wheel and do not leave the `torch.nn.Linear` stub.

ROCm wheels may still expose `torch.version.cuda` as an API compatibility shim. Verification must require `torch.version.hip is not None` and a visible GPU; do not treat a non-None CUDA version string as a CUDA wheel.

For vLLM workloads, install the official vLLM ROCm wheel instead; it supplies the compatible PyTorch-family build set and compiled vLLM extensions.

4. Installation must verify all of the following before writing the successful setup marker:

```python
import torch
assert torch.version.hip is not None
assert torch.cuda.is_available()
assert torch.cuda.device_count() >= 1
```

5. The verification must print the PyTorch version, HIP version, and GPU name, and must allocate a tensor on `cuda`. A CUDA wheel such as `torch+cu130`, a CPU wheel, or `torch.version.hip is None` is a setup failure. Some MI300X VF / TheRock wheels report `torch.cuda.device_count() == 0` while `is_available()` and `cuda:0` compute still work; do not treat a zero count as a CUDA-wheel failure when a `cuda` allocation succeeds.
6. The setup failure must prevent benchmark execution and must identify the ROCm wheel index and GPU visibility checks needed for remediation.

The ROCm runtime and GPU device must be installed and visible through `rocminfo`/`amd-smi` before the PyTorch verification is expected to pass.

For LLM-serving workloads, install the verified ROCm Torch pair before installing framework packages. Do not allow a generic CUDA `sgl_kernel` wheel to replace the ROCm build. Build SGLang's `sgl-kernel` from its source tree with `setup_rocm.py` and the target `PYTORCH_ROCM_ARCH`, install the SGLang Python package without dependency replacement, and install AMD AITER from the official ROCm repository with recursive submodules.

vLLM ROCm platform detection also requires the Python `amdsmi` package; generated vLLM repositories must install and import-check it before launching the server. The vLLM serving package must come from the official ROCm wheel index `https://wheels.vllm.ai/rocm/`, not only the default PyPI package, so compiled ROCm extensions such as `vllm._C` are present. For vLLM workloads, the official wheel is authoritative for its compatible PyTorch, torchvision, torchaudio, Triton, and ROCm extension builds; verify those resolved versions after vLLM installation rather than reinstalling a standalone PyTorch pair afterward. If the selected ROCm wheel's V1 engine imports CUDA-only FlashInfer components, generated runners should use a documented ROCm compatibility shim to skip the incompatible warmup, while retaining an explicit opt-out for wheels that fix it.
