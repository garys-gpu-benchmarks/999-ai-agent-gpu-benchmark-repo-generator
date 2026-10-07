#!/usr/bin/env python3
# File: scripts/lib/probe_torch_conv2d.py
# Description: Setup gate for NVIDIA convolution components. Runs one tiny
# fp16 conv2d after PyTorch is installed. A signal 11 here fails setup.
# Not used by vLLM, SGLang, DistilBERT, BERT, or RAG.

from __future__ import annotations

import sys

import torch
import torch.nn.functional as F


def main() -> int:
    if not torch.cuda.is_available():
        print("[FAIL] fp16 conv2d probe requires CUDA", file=sys.stderr)
        return 1
    x = torch.randn(1, 3, 8, 8, device="cuda", dtype=torch.float16)
    w = torch.randn(8, 3, 3, 3, device="cuda", dtype=torch.float16)
    y = F.conv2d(x, w, padding=1)
    torch.cuda.synchronize()
    if not torch.isfinite(y.float()).all():
        print("[FAIL] fp16 conv2d probe produced non-finite values", file=sys.stderr)
        return 1
    print("[PASS] fp16 conv2d probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
