#!/usr/bin/env python3
"""Local Torch GEMM microkernel (C = A @ B)."""
from __future__ import annotations

import argparse
import time

import torch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--M", type=int, default=64)
    parser.add_argument("--N", type=int, default=64)
    parser.add_argument("--K", type=int, default=64)
    parser.add_argument("--dtype", default="fp16")
    parser.add_argument("--device-id", type=int, default=0)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--iters", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    device = torch.device(f"cuda:{args.device_id}")
    dtype = torch.float16 if "16" in args.dtype.lower() else torch.float32
    a = torch.randn(args.M, args.K, device=device, dtype=dtype)
    b = torch.randn(args.K, args.N, device=device, dtype=dtype)
    for _ in range(args.warmup):
        torch.matmul(a, b)
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(args.iters):
        c = torch.matmul(a, b)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    usec = (elapsed / args.iters) * 1e6
    flops = 2.0 * args.M * args.N * args.K
    tflops = (flops * args.iters / elapsed) / 1e12
    bytes_moved = (args.M * args.K + args.K * args.N + args.M * args.N) * a.element_size()
    gbps = (bytes_moved * args.iters / elapsed) / 1e9
    print(f"gemm_time_usec={usec:.6f}")
    print(f"gemm_tflops={tflops:.6f}")
    print(f"gemm_bandwidth_gb_s={gbps:.6f}")
    print(f"checksum={float(c.float().sum().item()):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
