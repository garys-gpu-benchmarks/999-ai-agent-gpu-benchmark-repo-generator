#!/usr/bin/env python3
# File: scripts/lib/flashinfer_warmup.py
# Description: Compile one real FlashInfer kernel during setup so a broken
# CUDA header fails before .setup_state is written.
"""Trigger one FlashInfer JIT compile: sampling for vLLM, prefill for SGLang."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# FlashInfer JIT runs `ninja` from PATH. Setup calls this script by the venv
# python's full path without activating the venv, so put the venv bin first.
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")


def _fail(message: str) -> int:
    print(f"[FAIL] {message}", file=sys.stderr)
    return 1


def _sampling() -> None:
    import torch
    import flashinfer

    probs = torch.rand((4, 32), device="cuda", dtype=torch.float32)
    probs = probs / probs.sum(dim=-1, keepdim=True)
    top_p = torch.full((4,), 0.9, device="cuda", dtype=torch.float32)
    sampler = getattr(flashinfer, "sampling", None)
    func = getattr(sampler, "top_p_sampling_from_probs", None) if sampler is not None else None
    if func is None:
        func = getattr(flashinfer, "top_p_sampling_from_probs", None)
    if func is None:
        raise RuntimeError("flashinfer has no top_p_sampling_from_probs")
    try:
        func(probs, top_p)
    except TypeError:
        func(probs, top_p, deterministic=True)


def _prefill() -> None:
    import torch
    import flashinfer

    q = torch.randn((1, 1, 64), device="cuda", dtype=torch.float16)
    k = torch.randn((4, 1, 64), device="cuda", dtype=torch.float16)
    v = torch.randn((4, 1, 64), device="cuda", dtype=torch.float16)
    func = getattr(flashinfer, "single_prefill_with_kv_cache", None)
    if func is None:
        prefill = getattr(flashinfer, "prefill", None)
        func = getattr(prefill, "single_prefill_with_kv_cache", None) if prefill is not None else None
    if func is None:
        raise RuntimeError("flashinfer has no single_prefill_with_kv_cache")
    func(q, k, v)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in {"sampling", "prefill"}:
        return _fail("usage: flashinfer_warmup.py sampling|prefill")
    try:
        import torch
    except ImportError as exc:
        return _fail(f"torch is required for the FlashInfer warmup: {exc}")
    if not torch.cuda.is_available():
        return _fail("FlashInfer warmup requires torch.cuda.is_available()")
    try:
        import flashinfer  # noqa: F401
    except ImportError as exc:
        return _fail(f"flashinfer is required for the {argv[0]} warmup: {exc}")
    try:
        if argv[0] == "sampling":
            _sampling()
        else:
            _prefill()
        torch.cuda.synchronize()
    except Exception as exc:  # noqa: BLE001 — setup must see the compiler error
        return _fail(f"FlashInfer {argv[0]} compile failed: {exc}")
    print(f"[PASS] FlashInfer {argv[0]} kernel compiled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
