#!/usr/bin/env python3
# File: scripts/framework_registry.py
# Description: Resolve Framework text to official setup flags. No ad-hoc grep in skeletons.
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # system python, before the benchmark virtualenv exists
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "config" / "framework_registry.yaml"


def _parse_scalar(raw: str):
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",")]
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _load_simple_yaml(text: str) -> dict:
    """Registry subset: nested mappings, inline lists, and dash lists. No PyYAML."""
    rows: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        rows.append((len(raw_line) - len(raw_line.lstrip(" ")), raw_line.strip()))
    root: dict = {}
    stack: list[tuple[int, object]] = [(-1, root)]
    for index, (indent, line) in enumerate(rows):
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(container, list):
                raise ValueError(f"YAML list item without a list: {line}")
            container.append(_parse_scalar(line[2:]))
            continue
        if ":" not in line or not isinstance(container, dict):
            raise ValueError(f"YAML mapping expected: {line}")
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest != "":
            container[key] = _parse_scalar(rest)
            continue
        nxt = rows[index + 1] if index + 1 < len(rows) else None
        child: object = [] if nxt and nxt[0] > indent and nxt[1].startswith("- ") else {}
        container[key] = child
        stack.append((indent, child))
    return root


def load_registry(path: Path | None = None) -> dict:
    target = Path(path) if path else DEFAULT_REGISTRY
    text = target.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _load_simple_yaml(text) or {}


def spec_fields(spec_path: Path) -> dict[str, str]:
    data = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    return {
        str(item.get("field_name", "")): str(item.get("value", "") or "")
        for item in data
        if isinstance(item, dict)
    }


def _match_any(text: str, needles: list[str]) -> bool:
    blob = text.lower()
    for needle in needles or []:
        token = str(needle).strip().lower()
        if not token:
            continue
        if re.search(rf"(^|[,;:\s/]){re.escape(token)}([,;:\s/]|$)", blob) or token in blob:
            return True
    return False


def resolve_flags(
    framework: str,
    *,
    vendor: str,
    workload_name: str = "",
    registry: dict | None = None,
) -> dict[str, int]:
    data = registry or load_registry()
    vendor_key = str(vendor or "").strip().lower()
    if vendor_key in {"cpu", "system", "cpu / system"}:
        vendor_key = "cpu"
    elif vendor_key in {"amd", "rocm"}:
        vendor_key = "amd"
    elif vendor_key in {"nvidia", "cuda"}:
        vendor_key = "nvidia"
    vendor_block = ((data.get("vendors") or {}).get(vendor_key) or {})
    flags_spec = vendor_block.get("flags") or {}
    haystack = f"{framework} {workload_name}"
    flags: dict[str, int] = {name: 0 for name in flags_spec}
    for name, rule in flags_spec.items():
        include = rule.get("include") or []
        exclude = rule.get("exclude") or []
        extra = rule.get("or_workload_name") or []
        hit = _match_any(framework, include) or _match_any(workload_name, extra)
        blocked = _match_any(framework, exclude)
        if hit and not blocked:
            flags[name] = 1
    for name, rule in flags_spec.items():
        if flags.get(name) != 1:
            continue
        for implied in rule.get("implies") or []:
            if implied in flags:
                flags[implied] = 1
    return flags


def format_env(flags: dict[str, int]) -> str:
    return "\n".join(f"export {key}={value}" for key, value in flags.items())


def main() -> int:
    parser = argparse.ArgumentParser(description="Print official Framework setup flags")
    parser.add_argument("--spec", default="benchmark_specification.json")
    parser.add_argument("--vendor", default="")
    parser.add_argument("--framework", default="")
    parser.add_argument("--workload-name", default="")
    parser.add_argument("--registry", default="")
    parser.add_argument("--format", choices=("env", "json"), default="env")
    args = parser.parse_args()
    fields: dict[str, str] = {}
    spec = Path(args.spec)
    if spec.is_file():
        fields = spec_fields(spec)
    framework = args.framework or fields.get("Framework") or fields.get("Software Framework", "")
    workload_name = args.workload_name or fields.get("Workload Name", "")
    vendor = args.vendor or fields.get("GPU Vendor") or fields.get("Execution Domain", "")
    if str(fields.get("Execution Domain", "")).startswith("CPU"):
        vendor = "cpu"
    registry = load_registry(Path(args.registry)) if args.registry else load_registry()
    flags = resolve_flags(framework, vendor=vendor, workload_name=workload_name, registry=registry)
    if args.format == "json":
        json.dump(flags, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_env(flags) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
