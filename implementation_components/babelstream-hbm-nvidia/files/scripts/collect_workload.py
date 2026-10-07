#!/usr/bin/env python3
"""Harness entry. run_benchmark.sh always calls scripts/collect_workload.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).with_name("collect_babelstream.py")
    sys.argv[0] = str(target)
    raise SystemExit(runpy.run_path(str(target), run_name="__main__"))
