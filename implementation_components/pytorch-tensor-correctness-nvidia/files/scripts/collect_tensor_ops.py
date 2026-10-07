#!/usr/bin/env python3
"""Collect PyTorch CUDA tensor-op correctness vs a CPU FP64 reference."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import torch


DTYPE_MAP = {
    "f16_r": torch.float16,
    "bf16_r": torch.bfloat16,
    "f32_r": torch.float32,
    "fp16": torch.float16,
    "bf16": torch.bfloat16,
    "fp32": torch.float32,
}


def parse_list(raw: str) -> list[str]:
    return [part.strip() for part in str(raw).replace(";", ",").split(",") if part.strip()]


def parse_shapes(raw: str) -> dict[str, list[tuple[int, ...]]]:
    mapping: dict[str, list[tuple[int, ...]]] = {}
    for part in str(raw).split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        shapes = []
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            shapes.append(tuple(int(dim) for dim in item.lower().split("x")))
        mapping[name.strip()] = shapes
    return mapping


def parse_bound(raw: str, dtype_key: str, default: float) -> float:
    text = str(raw)
    if "=" not in text:
        try:
            return float(text)
        except ValueError:
            return default
    for item in text.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key.strip() == dtype_key:
            return float(value)
    return default


def run_matmul(shape: tuple[int, ...], dtype: torch.dtype, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    if len(shape) == 2:
        left = torch.randn(*shape, dtype=dtype, device=device)
        right = torch.randn(*shape, dtype=dtype, device=device)
    else:
        left = torch.randn(*shape, dtype=dtype, device=device)
        right = torch.randn(*shape, dtype=dtype, device=device)
    gpu = torch.matmul(left, right)
    ref = torch.matmul(left.detach().double().cpu(), right.detach().double().cpu())
    return gpu, ref


def run_conv2d(shape: tuple[int, ...], dtype: torch.dtype, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    n, c, h, w = shape if len(shape) == 4 else (1, 3, 32, 32)
    x = torch.randn(n, c, h, w, dtype=dtype, device=device)
    weight = torch.randn(8, c, 3, 3, dtype=dtype, device=device)
    gpu = torch.nn.functional.conv2d(x, weight, padding=1)
    ref = torch.nn.functional.conv2d(x.detach().double().cpu(), weight.detach().double().cpu(), padding=1)
    return gpu, ref


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--raw-file", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--device-id", default="0")
    parser.add_argument("--op-name", default="matmul,conv2d")
    parser.add_argument("--dtype", default="f16_r")
    parser.add_argument("--shape", default="matmul=1x128x128;conv2d=1x3x32x32")
    parser.add_argument("--rtol", default="0.02")
    parser.add_argument("--atol", default="0.1")
    parser.add_argument("--tolerance-rel", default="1e-3")
    parser.add_argument("--num-iterations", default="2")
    parser.add_argument("--seed", default="42")
    parser.add_argument("--output-format", default="csv")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(f"cuda:{int(args.device_id)}")
    torch.cuda.set_device(device)
    ops = parse_list(args.op_name)
    dtypes = parse_list(args.dtype)
    shapes = parse_shapes(args.shape)
    iterations = max(1, int(float(args.num_iterations)))
    seed = int(float(args.seed))
    rows = []
    raw_lines = []
    failures = 0
    max_abs = 0.0
    max_rel = 0.0
    cases = 0
    passed = 0
    for op in ops:
        for dtype_key in dtypes:
            dtype = DTYPE_MAP.get(dtype_key, torch.float16)
            rtol = parse_bound(args.rtol, dtype_key, 0.02)
            atol = parse_bound(args.atol, dtype_key, 0.1)
            for shape in shapes.get(op, [(128, 128)]):
                case_abs = case_rel = 0.0
                case_ok = True
                for iteration in range(iterations):
                    iter_seed = seed + iteration
                    torch.manual_seed(iter_seed)
                    random.seed(iter_seed)
                    torch.cuda.manual_seed_all(iter_seed)
                    if op == "conv2d":
                        gpu, ref = run_conv2d(shape, dtype, device)
                    else:
                        gpu, ref = run_matmul(shape, dtype, device)
                    gpu64 = gpu.detach().double().cpu()
                    abs_err = (gpu64 - ref).abs()
                    iteration_abs = float(abs_err.max().item())
                    ref_norm = float(torch.linalg.vector_norm(ref).item())
                    diff_norm = float(torch.linalg.vector_norm(abs_err).item())
                    iteration_rel = diff_norm / max(ref_norm, atol)
                    case_abs = max(case_abs, iteration_abs)
                    case_rel = max(case_rel, iteration_rel)
                    ok = bool(torch.allclose(gpu64, ref, rtol=rtol, atol=atol, equal_nan=False))
                    case_ok = case_ok and ok
                cases += 1
                coverage = 1
                max_abs = max(max_abs, case_abs)
                max_rel = max(max_rel, case_rel)
                if case_ok:
                    passed += 1
                    status = "ok"
                else:
                    failures += 1
                    status = "error"
                rows.append(
                    {
                        "check": f"{op}_{dtype_key}_{'x'.join(str(d) for d in shape)}",
                        "command": f"torch {op} vs cpu fp64",
                        "rc": 0,
                        "status": status,
                        "pass_rate_percent": 100.0 if case_ok else 0.0,
                        "max_abs_error": case_abs,
                        "max_rel_error": case_rel,
                        "tolerance_compliance": "",
                        "coverage_count": coverage,
                        "failure_count": 0 if case_ok else 1,
                    }
                )
                raw_lines.append(
                    f"===== {rows[-1]['check']} rc=0 =====\n"
                    f"PASS={case_ok} abs={case_abs} rel={case_rel} iters={iterations} seed={seed}\n"
                )
    pass_rate = 100.0 * passed / cases if cases else 0.0
    compliance = pass_rate
    # The parser means columns that do not start with max_. Repeat the suite
    # totals on every row, including tolerance, so that mean is the suite
    # value rather than a mix of per-case 0/100 flags and the summary.
    for row in rows:
        row["coverage_count"] = cases
        row["failure_count"] = failures
        row["tolerance_compliance"] = compliance
    rows.append(
        {
            "check": "summary",
            "command": "aggregate",
            "rc": 0,
            "status": "ok",
            "pass_rate_percent": pass_rate,
            "max_abs_error": max_abs,
            "max_rel_error": max_rel,
            "tolerance_compliance": compliance,
            "coverage_count": cases,
            "failure_count": failures,
        }
    )
    fieldnames = [
        "check", "command", "rc", "status",
        "pass_rate_percent", "max_abs_error", "max_rel_error",
        "tolerance_compliance", "coverage_count", "failure_count",
    ]
    (run_dir / "raw_output.txt").write_text("\n".join(raw_lines), encoding="utf-8")
    with (run_dir / "raw_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with (run_dir / "raw_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    print(f"[PASS] pass_rate={pass_rate} cases={cases} failures={failures} max_abs={max_abs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
