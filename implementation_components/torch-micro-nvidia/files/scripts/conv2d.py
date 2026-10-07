#!/usr/bin/env python3
"""Local Torch Conv2d microkernel."""
from __future__ import annotations

import argparse
import time

import torch
import torch.nn.functional as F


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shape", default="1,3,32,32")
    parser.add_argument("--dtype", default="fp16")
    parser.add_argument("--device-id", type=int, default=0)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--iters", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    n, c, h, w = [int(x) for x in args.shape.split(",")]
    device = torch.device(f"cuda:{args.device_id}")
    dtype = torch.float16 if "16" in args.dtype.lower() else torch.float32
    x = torch.randn(n, c, h, w, device=device, dtype=dtype)
    weight = torch.randn(8, c, 3, 3, device=device, dtype=dtype)
    for _ in range(args.warmup):
        F.conv2d(x, weight, padding=1)
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(args.iters):
        y = F.conv2d(x, weight, padding=1)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    usec = (elapsed / args.iters) * 1e6
    flops = 2.0 * n * 8 * h * w * c * 9
    tflops = (flops * args.iters / elapsed) / 1e12
    bytes_moved = (x.numel() + weight.numel() + y.numel()) * x.element_size()
    gbps = (bytes_moved * args.iters / elapsed) / 1e9
    print(f"conv_time_usec={usec:.6f}")
    print(f"conv_tflops={tflops:.6f}")
    print(f"conv_bandwidth_gb_s={gbps:.6f}")
    print(f"checksum={float(y.float().sum().item()):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
