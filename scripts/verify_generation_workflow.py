#!/usr/bin/env python3
"""Deterministic smoke checks for prompt parsing, catalog, and documentation links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from generate_workload_parameters import OUTPUT, build_catalog
from prompt_workflow import available_workloads, parse_workloads, workload_token


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_ROOTS = [ROOT, ROOT / "docs", ROOT / "templates", ROOT / ".github"]
LINK = re.compile(r"\]\(([^)#]+)(?:#[^)]+)?\)")


def check_prompt_parser() -> None:
    available = available_workloads(ROOT / "BenchmarkSpecDefinitions.xlsx")
    cases = {
        "Generate workload 101.": ["101"],
        "Generate workloads 101 and 103.": ["101", "103"],
        "Generate workloads 104 through 108.": ["104", "105", "106", "107", "108"],
        "Generate workloads ALL.": [str(value) for value in available],
    }
    for prompt, expected in cases.items():
        actual = parse_workloads(prompt, available)
        if actual != expected:
            raise AssertionError(f"Parser mismatch for {prompt!r}: {actual} != {expected}")
    if workload_token(cases["Generate workloads ALL."], available) != "ALL":
        raise AssertionError("ALL workload token was not canonicalized.")


def check_catalog() -> None:
    catalog = build_catalog()
    stored = yaml.safe_load(OUTPUT.read_text(encoding="utf-8"))
    if catalog != stored:
        raise AssertionError("workload_parameters.yaml is stale; regenerate it from the workbook.")
    if len(catalog["parameters"]) < 2:
        raise AssertionError("Shared parameter catalog unexpectedly contains fewer than two parameters.")


def check_markdown_links() -> None:
    checked: set[Path] = set()
    for directory in MARKDOWN_ROOTS:
        if not directory.exists():
            continue
        for path in directory.rglob("*.md"):
            if path in checked:
                continue
            checked.add(path)
            text = path.read_text(encoding="utf-8")
            for target in LINK.findall(text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    raise AssertionError(f"Broken Markdown link in {path}: {target}")


def main() -> int:
    check_prompt_parser()
    check_catalog()
    check_markdown_links()
    print("[PASS] Prompt, catalog, and Markdown-link checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
