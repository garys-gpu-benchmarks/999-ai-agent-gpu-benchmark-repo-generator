#!/usr/bin/env python3
# File: scripts/collect_workload.py
# Description: AMD 119/319 harness entry point. Runs scripts/collect_torch_micro.py,
#              the same GEMM/Conv2d collector NVIDIA 219/419 use (gemm.py and conv2d.py
#              are plain PyTorch; cuda:N is the ROCm device too), and copies its
#              raw_results.csv to the harness --raw-file.
#              Before 2026-10-01 this file had its own copy that wrote 1.0 for a
#              missing value with status ok, mixed GEMM and Conv2d in one column,
#              and undercounted Conv2d FLOPs (no x2) and bytes (input only).
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--config", default="config/benchmark_config.yaml")
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--output-format", default="csv")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    helper = Path(__file__).resolve().parent / "collect_torch_micro.py"
    completed = subprocess.run(
        [sys.executable, str(helper), "--run-dir", str(run_dir), "--config", args.config, "--profile", args.profile],
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    produced = run_dir / "raw_results.csv"
    if not produced.is_file():
        raise SystemExit(f"[FAIL] {helper.name} did not write {produced}")
    raw_file = Path(args.raw_file)
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    if produced.resolve() != raw_file.resolve():
        shutil.copyfile(produced, raw_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
