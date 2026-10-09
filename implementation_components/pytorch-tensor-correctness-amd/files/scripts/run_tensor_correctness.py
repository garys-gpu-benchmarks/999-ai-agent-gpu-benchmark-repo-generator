#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import torch
import yaml

DTYPE_MAP = {
    "f16_r": torch.float16, "fp16": torch.float16, "float16": torch.float16,
    "bf16_r": torch.bfloat16, "bf16": torch.bfloat16, "bfloat16": torch.bfloat16,
    "f32_r": torch.float32, "fp32": torch.float32, "float32": torch.float32,
}


def parse_list(value):
    return [part.strip() for part in str(value or "").replace(";", ",").split(",") if part.strip()]


def parse_shapes(value):
    mapping = {}
    for chunk in str(value or "").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            name, rest = chunk.split("=", 1)
            mapping[name.strip()] = parse_list(rest)
        else:
            mapping.setdefault("*", []).extend(parse_list(chunk))
    return mapping


def parse_dim(text):
    return tuple(int(part) for part in text.lower().replace("x", " ").replace(",", " ").split() if part)


def scalar_map(value, keys, default):
    if isinstance(value, (int, float)):
        return {key: float(value) for key in keys}
    text = str(value or "")
    if "=" not in text:
        number = float(text or default)
        return {key: number for key in keys}
    out = {key: default for key in keys}
    for chunk in parse_list(text):
        if "=" in chunk:
            key, raw = chunk.split("=", 1)
            out[key.strip()] = float(raw)
    return out


def run_case(op_name, dtype_name, shape_text, iterations, seed, device, atol, rtol):
    torch.manual_seed(seed)
    dtype = DTYPE_MAP[dtype_name]
    dims = parse_dim(shape_text)
    max_abs = max_rel = 0.0
    failures = 0
    for _ in range(max(1, iterations)):
        if op_name == "conv2d":
            n, c, h, w = dims if len(dims) == 4 else (1, 3, 32, 32)
            inp = torch.randn(n, c, h, w, device=device, dtype=dtype)
            weight = torch.randn(c, c, 3, 3, device=device, dtype=dtype)
            gpu = torch.nn.functional.conv2d(inp, weight, padding=1)
            ref = torch.nn.functional.conv2d(inp.float().cpu(), weight.float().cpu(), padding=1)
        else:
            if len(dims) >= 3:
                b, m, k = dims[0], dims[1], dims[2]
                n = dims[2]
                a = torch.randn(b, m, k, device=device, dtype=dtype)
                b_t = torch.randn(b, k, n, device=device, dtype=dtype)
            else:
                m, k = (dims + (128, 128))[:2]
                a = torch.randn(m, k, device=device, dtype=dtype)
                b_t = torch.randn(k, k, device=device, dtype=dtype)
            gpu = torch.matmul(a, b_t)
            ref = torch.matmul(a.float().cpu(), b_t.float().cpu())
        diff = (gpu.float().cpu() - ref).abs()
        # A whole-tensor norm avoids a near-zero reference element dominating
        # the headline relative error. Compliance itself remains the standard
        # elementwise |difference| <= atol + rtol * |reference| criterion.
        ref_norm = float(torch.linalg.vector_norm(ref).item())
        diff_norm = float(torch.linalg.vector_norm(diff).item())
        case_abs = float(diff.max().item())
        case_rel = diff_norm / max(ref_norm, float(atol))
        max_abs = max(max_abs, case_abs)
        max_rel = max(max_rel, case_rel)
        compliant = torch.all(diff <= float(atol) + float(rtol) * ref.abs())
        if not bool(compliant.item()):
            failures += 1
    return {
        "op_name": op_name, "dtype": dtype_name, "shape": shape_text,
        "max_abs_error": max_abs, "max_rel_error": max_rel,
        "tolerance_compliance": "",
        "coverage_count": "",
        "failure_count": float(failures),
        "status": "ok" if failures == 0 else "error", "error_message": "",
    }


def collect(profile, config_path):
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    params = cfg.get("sweep") or {}

    def value_of(key, default):
        raw = params.get(key, default)
        if isinstance(raw, dict):
            return raw.get(profile, raw.get("smoke", default))
        return raw

    ops = parse_list(value_of("op_name", "matmul,conv2d"))
    dtypes = parse_list(value_of("dtype", "f16_r"))
    shapes = parse_shapes(value_of("shape", "matmul=1x128x128;conv2d=1x3x32x32"))
    iterations = int(float(value_of("num_iterations", 2)))
    seed = int(float(value_of("seed", 42)))
    device_id = int(float(value_of("device_id", 0)))
    atol_map = scalar_map(value_of("atol", 0.1), dtypes, 0.1)
    rtol_map = scalar_map(value_of("rtol", 0.02), dtypes, 0.02)
    if not torch.cuda.is_available():
        raise SystemExit("[FAIL] no ROCm GPU")
    device = torch.device(f"cuda:{device_id}")
    rows = []
    for op_name in ops:
        op_shapes = shapes.get(op_name) or shapes.get("*") or (["1x3x32x32"] if op_name == "conv2d" else ["1x128x128"])
        for dtype_name in dtypes:
            for shape_text in op_shapes:
                rows.append(run_case(op_name, dtype_name, shape_text, iterations, seed, device, atol_map.get(dtype_name, 0.1), rtol_map.get(dtype_name, 0.02)))
    case_count = float(len(rows))
    failed_cases = sum(1 for row in rows if row["failure_count"])
    compliance = 100.0 * (case_count - failed_cases) / case_count if case_count else 0.0
    for row in rows:
        row["coverage_count"] = case_count
        row["tolerance_compliance"] = compliance
        # This contract metric is a suite-level failed-case count, not the
        # mean number of failed iterations. Repeat it so generic aggregation
        # preserves the integer total.
        row["failure_count"] = float(failed_cases)
    return rows
