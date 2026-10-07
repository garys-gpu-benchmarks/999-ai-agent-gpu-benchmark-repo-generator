#!/usr/bin/env python3
"""Collect Torch GEMM and Conv2d microkernel samples (AMD 119/319 and NVIDIA 219/419)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path

import yaml

# Six metrics, GEMM and Conv2d kept apart (119/219/319/419 share this list).
# The old mean_minimum_traffic_gb_s averaged GEMM and Conv2d bandwidth into one
# number, and gemm_throughput_tflops duplicated gemm_tflops.
METRIC_FIELDS = [
    "gemm_time_usec",
    "gemm_tflops",
    "gemm_bandwidth_gb_s",
    "conv_time_usec",
    "conv_tflops",
    "conv_bandwidth_gb_s",
]
PARAM_FIELDS = ["check", "device_id", "dtype", "kernel_type", "status"]
KV_RE = re.compile(r"^([A-Za-z0-9_]+)=([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE)


def pick(sweep: dict, key: str, profile: str, default: str = "") -> str:
    value = sweep.get(key, default)
    if isinstance(value, dict):
        value = value.get(profile, value.get("smoke", default))
    return "" if value is None else str(value).strip()


def parse_kv(text: str) -> dict[str, float]:
    return {m.group(1): float(m.group(2)) for m in KV_RE.finditer(text)}


def run(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return completed.returncode, completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--config", default="config/benchmark_config.yaml")
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--device-id", default="")
    parser.add_argument("--kernel-type", default="")
    parser.add_argument("--dtype", default="")
    parser.add_argument("--input-shape", default="")
    parser.add_argument("--M", dest="M", default="")
    parser.add_argument("--N", dest="N", default="")
    parser.add_argument("--K", dest="K", default="")
    parser.add_argument("--batch-size", default="")
    parser.add_argument("--warmup-iters", default="")
    parser.add_argument("--num-iterations", default="")
    parser.add_argument("--seed", default="")
    parser.add_argument("--output-format", default="csv")
    args = parser.parse_args()
    sweep = (yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}).get("sweep", {})
    profile = args.profile
    device = args.device_id or pick(sweep, "device_id", profile, "0")
    dtype = args.dtype or pick(sweep, "dtype", profile, "fp16")
    shape = args.input_shape or pick(sweep, "input_shape", profile, "1,3,32,32")
    m_dim = args.M or pick(sweep, "M", profile, "64")
    n_dim = args.N or pick(sweep, "N", profile, "64")
    k_dim = args.K or pick(sweep, "K", profile, "64")
    warmup = args.warmup_iters or pick(sweep, "warmup_iters", profile, "2")
    iters = args.num_iterations or pick(sweep, "num_iterations", profile, "5")
    seed = args.seed or pick(sweep, "seed", profile, "42")
    repo = Path(__file__).resolve().parents[1]
    python = repo / ".venv" / "bin" / "python"
    if not python.is_file():
        python = Path("python3")
    gemm_cmd = [str(python), str(repo / "scripts" / "gemm.py"), "--M", str(m_dim), "--N", str(n_dim), "--K", str(k_dim), "--dtype", dtype, "--device-id", str(device), "--warmup", str(warmup), "--iters", str(iters), "--seed", str(seed)]
    conv_cmd = [str(python), str(repo / "scripts" / "conv2d.py"), "--shape", shape, "--dtype", dtype, "--device-id", str(device), "--warmup", str(warmup), "--iters", str(iters), "--seed", str(seed)]
    print("[RUN] " + " ".join(gemm_cmd))
    gcode, gtext = run(gemm_cmd)
    print(gtext.rstrip())
    print("[RUN] " + " ".join(conv_cmd))
    ccode, ctext = run(conv_cmd)
    print(ctext.rstrip())
    if gcode != 0 or ccode != 0:
        raise SystemExit("[FAIL] gemm.py or conv2d.py failed.")
    values = {**parse_kv(gtext), **parse_kv(ctext)}
    missing = [name for name in METRIC_FIELDS if name not in values]
    if missing:
        raise SystemExit(f"[FAIL] gemm.py/conv2d.py did not print {', '.join(missing)}; no default is substituted.")
    latest = {name: values[name] for name in METRIC_FIELDS}
    if any(latest[name] <= 0 for name in METRIC_FIELDS):
        raise SystemExit(f"[FAIL] non-positive torch micro metrics: {latest}")
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for check in ("gemm", "conv2d"):
        row = {"check": check, "device_id": device, "dtype": dtype, "kernel_type": "all", "status": "ok"}
        for name in METRIC_FIELDS:
            row[name] = f"{latest[name]:.6f}"
        rows.append(row)
    summary = {"check": "summary", "device_id": device, "dtype": dtype, "kernel_type": "all", "status": "ok"}
    for name in METRIC_FIELDS:
        summary[name] = f"{latest[name]:.6f}"
    rows.append(summary)
    fields = [*PARAM_FIELDS, *METRIC_FIELDS]
    with (run_dir / "raw_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "raw_results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    (run_dir / "raw_output.txt").write_text(f"===== gemm rc={gcode} =====\n{gtext}\n===== conv2d rc={ccode} =====\n{ctext}", encoding="utf-8")
    print("# METRICS_CSV")
    print((run_dir / "raw_results.csv").read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
