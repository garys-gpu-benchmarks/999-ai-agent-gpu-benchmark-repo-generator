#!/usr/bin/env python3
# File: scripts/implementation_pack.py
# Description: Resolve component directory ids from Workload Number, GPU Vendor, and config/implementation_packs.yaml.
from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def parse_pack_field(raw: str) -> list[str]:
    return [part.strip() for part in str(raw or "").replace(";", ",").split(",") if part.strip()]


def _vendor_key(vendor: str) -> str:
    folded = vendor.strip().casefold()
    if folded == "amd":
        return "amd"
    if folded == "nvidia":
        return "nvidia"
    raise ValueError(f"GPU Vendor {vendor!r} is not AMD or NVIDIA.")


def load_pack_table(yaml_path: Path) -> dict[int, dict[str, str]]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read config/implementation_packs.yaml")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    packs = data.get("packs") or {}
    return {int(slot): dict(row) for slot, row in packs.items()}


def packs_from_table(workload: str, vendor: str, yaml_path: Path) -> list[str]:
    number = int(str(workload).strip())
    slot = ((number - 1) % 100) + 1
    if slot < 1 or slot > 32:
        return []
    family = (number - slot) // 100
    if family not in {1, 2, 3, 4}:
        return []
    table = load_pack_table(yaml_path)
    row = table.get(slot) or {}
    return parse_pack_field(str(row.get(_vendor_key(vendor), "") or ""))


def implementation_packs(fields: dict[str, str], yaml_path: Path | None = None) -> list[str]:
    workload = fields.get("Workload Number", "").strip()
    vendor = fields.get("GPU Vendor", "").strip()
    if not workload or not vendor or yaml_path is None or not yaml_path.is_file():
        return []
    return packs_from_table(workload, vendor, yaml_path)
