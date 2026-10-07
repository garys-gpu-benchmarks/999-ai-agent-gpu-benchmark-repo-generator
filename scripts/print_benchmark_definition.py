#!/usr/bin/env python3
# File: scripts/print_benchmark_definition.py
# Version: 1.0.0
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-08-14
# Description: Print this workload's benchmark_specification.json fields as a two-column table.
# Execution: python3 scripts/print_benchmark_definition.py
# Options: None
# Requirements: Python 3.10+; benchmark_specification.json at repository root
# Environment: Run from a generated repository root.
# Dependencies: None
# Variables: None
# Repository: gpu-bench/sys-bench template
# License: Apache-2.0

"""Print the extracted matrix row for the current workload.

The generated repository stores that row as benchmark_specification.json.
This command does not read the Excel workbook at runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def main() -> int:
    _configure_stdout()
    path = Path("benchmark_specification.json")
    if not path.is_file():
        print("[ERROR] benchmark_specification.json is missing; run from the repository root.", file=sys.stderr)
        return 2
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Cannot read benchmark_specification.json: {exc}", file=sys.stderr)
        return 2
    if not isinstance(rows, list):
        print("[ERROR] benchmark_specification.json must be a list of field objects.", file=sys.stderr)
        return 2

    names: list[str] = []
    values: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("field_name", "")).strip()
        if not name:
            continue
        value = item.get("value", "")
        if value is None:
            value = ""
        names.append(name)
        values.append(str(value).replace("\r\n", "\n").replace("\r", "\n"))

    width = max((len(name) for name in names), default=0)
    for name, value in zip(names, values):
        lines = value.split("\n") or [""]
        print(f"{name:<{width}}  {lines[0]}")
        for extra in lines[1:]:
            print(f"{'':<{width}}  {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
