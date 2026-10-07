#!/usr/bin/env python3
"""Fail fast on generation-host gaps before Phase 0 extraction."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check generation-host prerequisites")
    parser.add_argument("--template-root", default=".")
    parser.add_argument("--ssh-target", default="", help="Optional host for ssh -o BatchMode reachability")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    if sys.version_info < (3, 10):
        errors.append(f"Python 3.10+ required, found {sys.version}")
    try:
        import yaml  # noqa: F401
    except ImportError:
        errors.append("PyYAML is not importable on this interpreter")
    if shutil.which("rg") is None:
        warnings.append("ripgrep (rg) is not on PATH; self_check will fail on the validation host")
    if os.name == "nt":
        try:
            from host_exec import resolve_host_bash

            resolve_host_bash()
        except SystemExit as exc:
            errors.append(str(exc))

    template = Path(args.template_root).resolve()
    required = [
        "AGENTS.md",
        "BenchmarkSpecDefinitions.xlsx",
        "docs/generation-workflow.md",
        "scripts/extract_benchmark_definition.py",
        "scripts/generated_repo_directory.py",
        "scripts/fill_generated_docs.py",
        "scripts/framework_registry.py",
        "scripts/platform_policy.py",
        "config/framework_registry.yaml",
        "config/platform_policy.yaml",
        "implementation_components/component.schema.json",
    ]
    for rel in required:
        if not (template / rel).exists():
            errors.append(f"missing template file: {rel}")

    if args.ssh_target:
        if shutil.which("ssh") is None:
            errors.append("ssh is not on PATH but --ssh-target was provided")
        else:
            warnings.append(f"SSH target recorded for later remote validation: {args.ssh_target}")

    print("[INFO] Write generated .sh/.py/.md/.yaml/.json/.txt as LF only, including nested *_copy/.")
    print("[INFO] Do not start a second overlapping setup.sh on the remote VM.")
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    print("[PASS] Generation-host preflight succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
