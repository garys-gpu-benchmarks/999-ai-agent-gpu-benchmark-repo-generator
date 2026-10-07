#!/usr/bin/env python3
# File: scripts/platform_policy.py
# Description: Official OS / GPU-vendor / driver policy checks.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "platform_policy.yaml"


def load_policy(path: Path | None = None) -> dict:
    target = Path(path) if path else DEFAULT_POLICY
    return yaml.safe_load(target.read_text(encoding="utf-8")) or {}


def spec_fields(spec_path: Path) -> dict[str, str]:
    data = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    return {
        str(item.get("field_name", "")): str(item.get("value", "") or "")
        for item in data
        if isinstance(item, dict)
    }


def _norm_vendor(value: str, domain: str = "") -> str:
    text = (value or "").strip().lower()
    if domain.lower().startswith("cpu") or text in {"cpu", "system"}:
        return "CPU"
    if text in {"amd", "rocm"}:
        return "AMD"
    if text in {"nvidia", "cuda"}:
        return "NVIDIA"
    return (value or "").strip().upper() or "UNKNOWN"


def _norm_os(value: str) -> str:
    text = str(value or "")
    for token in ("26.04", "24.04", "22.04"):
        if token in text:
            return token
    return text.strip()


def match_policy(fields: dict[str, str], *, os_release: str = "", policy: dict | None = None) -> dict:
    data = policy or load_policy()
    vendor = _norm_vendor(fields.get("GPU Vendor", ""), fields.get("Execution Domain", ""))
    os_id = _norm_os(os_release or fields.get("OS Version", ""))
    errors: list[str] = []
    warnings: list[str] = []
    matched = None
    for row in data.get("policies") or []:
        row_vendor = str(row.get("vendor", "")).strip().upper()
        row_os = str(row.get("os", "")).strip()
        if row_vendor != vendor:
            continue
        if row_os not in {"", "*", os_id}:
            continue
        matched = row
        break
    if matched is None:
        errors.append(f"No platform policy for vendor={vendor} os={os_id or '(unknown)'}")
        return {
            "ok": False,
            "vendor": vendor,
            "os": os_id,
            "driver": "",
            "reboots": None,
            "notes": "",
            "errors": errors,
            "warnings": warnings,
            "policy": None,
        }
    expected_os = _norm_os(fields.get("OS Version", ""))
    if expected_os and os_id and expected_os != os_id and vendor != "CPU":
        errors.append(
            f"Remote OS {os_id} does not match workload OS Version {expected_os}."
        )
    spec_vendor = _norm_vendor(fields.get("GPU Vendor", ""), fields.get("Execution Domain", ""))
    if spec_vendor != vendor:
        errors.append(f"Vendor mismatch: spec {spec_vendor} vs selected {vendor}")
    return {
        "ok": not errors,
        "vendor": vendor,
        "os": os_id,
        "driver": matched.get("driver"),
        "reboots": matched.get("reboots"),
        "notes": matched.get("notes", ""),
        "errors": errors,
        "warnings": warnings,
        "policy": matched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate official OS/vendor/driver policy")
    parser.add_argument("--spec", default="benchmark_specification.json")
    parser.add_argument("--os-release", default="")
    parser.add_argument("--policy", default="")
    args = parser.parse_args()
    fields = spec_fields(Path(args.spec)) if Path(args.spec).is_file() else {}
    policy = load_policy(Path(args.policy)) if args.policy else load_policy()
    result = match_policy(fields, os_release=args.os_release, policy=policy)
    json.dump({k: v for k, v in result.items() if k != "policy"} | {"policy_id": (result.get("policy") or {}).get("id")}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    for warning in result["warnings"]:
        print(f"[WARN] {warning}", file=sys.stderr)
    if not result["ok"]:
        for error in result["errors"]:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(f"[PASS] platform policy {result['vendor']} {result['os']} driver={result['driver']} reboots={result['reboots']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
