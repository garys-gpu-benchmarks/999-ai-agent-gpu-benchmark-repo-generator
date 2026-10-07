#!/usr/bin/env python3
# File: run.py
# Description: Compatibility entry that forwards to scripts/infer_sdxl.py.
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    script = Path(__file__).resolve().parent / "scripts" / "infer_sdxl.py"
    return subprocess.call([sys.executable, str(script), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
