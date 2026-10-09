#!/usr/bin/env python3
"""Fixture helper so ruff and compileall have a scripts/*.py file to check."""

import json
import sys


def main() -> int:
    profile = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    print(json.dumps({"profile": profile, "sample_check_count": 1}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
