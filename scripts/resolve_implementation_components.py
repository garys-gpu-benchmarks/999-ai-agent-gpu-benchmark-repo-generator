#!/usr/bin/env python3
"""Resolve reusable implementation components from benchmark specification fields."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from implementation_pack import implementation_packs

NULL_VALUES = {"", "none", "n/a", "—", "-"}
VALID_OPERATORS = {"equals", "contains", "in", "prefix"}
VALID_ROLES = {"collector", "parser", "runner", "source", "build", "mixin"}


def definition_fields(spec_path: Path) -> dict[str, str]:
    if not spec_path.is_file():
        return {}
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    return {
        str(item.get("field_name", "")).strip(): str(item.get("value", "")).strip()
        for item in data
        if isinstance(item, dict) and str(item.get("field_name", "")).strip()
    }


def infer_defaults(data: dict[str, object]) -> dict[str, object]:
    overlay = [str(item) for item in (data.get("overlay") or [])]
    if not data.get("role"):
        if any(path == "scripts/collect_workload.py" for path in overlay):
            data["role"] = "collector"
        elif any(path.startswith("src/") for path in overlay):
            data["role"] = "source"
        elif any(path == "scripts/build.sh" for path in overlay):
            data["role"] = "build"
        else:
            data["role"] = "collector"
    if data["role"] not in VALID_ROLES:
        raise ValueError(f"Invalid role {data['role']!r} for {data.get('component_id')}")
    if not data.get("completeness"):
        has_collect = "scripts/collect_workload.py" in overlay
        has_build = "scripts/build.sh" in overlay
        data["completeness"] = "closed" if has_collect and has_build else "thin"
    data.setdefault("provides", list(overlay))
    data.setdefault("does_not_provide", [])
    data.setdefault("verifies", [])
    data.setdefault("contracts", {})
    data.setdefault("also_applies_to", [])
    data.setdefault("apply_when", {})
    data.setdefault("selectors", [])
    if not data.get("entry_point"):
        named = [
            path for path in overlay
            if path.startswith("scripts/collect_") and path.endswith(".py") and path != "scripts/collect_workload.py"
        ]
        if "scripts/collect_workload.py" in overlay:
            data["entry_point"] = "scripts/collect_workload.py"
        elif named:
            data["entry_point"] = named[0]
        elif "scripts/infer_sdxl.py" in overlay:
            data["entry_point"] = "scripts/infer_sdxl.py"
        elif "run_benchmark.sh" in overlay:
            data["entry_point"] = "run_benchmark.sh"
    return data


def load_component(component_root: Path) -> dict[str, object]:
    component_id = component_root.name
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", component_id):
        raise ValueError(f"Invalid implementation component id: {component_id!r}")
    manifest = component_root / "component.json"
    if not manifest.is_file():
        raise ValueError(f"Missing component manifest: {manifest}")
    data = infer_defaults(json.loads(manifest.read_text(encoding="utf-8")))
    if data.get("component_id") != component_id:
        raise ValueError(f"component_id mismatch in {manifest}")
    selectors = data.get("selectors")
    overlay = data.get("overlay")
    if not isinstance(overlay, list) or not overlay:
        raise ValueError(f"Component must declare at least one overlay path: {manifest}")
    role = str(data.get("role"))
    if role == "mixin":
        if not data.get("apply_when"):
            raise ValueError(f"Mixin {component_id} must declare apply_when")
    elif selectors and not isinstance(selectors, list):
        raise ValueError(f"Component selectors must be a list: {manifest}")
    for clause in selectors or []:
        if not isinstance(clause, dict):
            raise ValueError(f"Invalid selector in {manifest}: {clause!r}")
        field = str(clause.get("field", "")).strip()
        operator = str(clause.get("operator", "")).strip()
        value = str(clause.get("value", "")).strip()
        if not field or operator not in VALID_OPERATORS:
            raise ValueError(f"Invalid selector in {manifest}: {clause!r}")
        if operator != "prefix" and not value:
            raise ValueError(f"Invalid selector in {manifest}: {clause!r}")
    for rel in overlay:
        rel_path = Path(str(rel))
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError(f"Unsafe overlay path in {manifest}: {rel!r}")
        src = component_root / "files" / rel_path
        if not src.is_file():
            raise ValueError(f"Implementation component file is missing: {src}")
    return data


def _fold_hyphens(text: str) -> str:
    for mark in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(mark, "-")
    return text


def selector_matches(actual: str, operator: str, expected: str) -> bool:
    a = _fold_hyphens(actual.strip()).casefold()
    e = _fold_hyphens(expected.strip()).casefold()
    if operator == "equals":
        return a == e
    if operator == "contains":
        return e in a
    if operator == "in":
        options = [part.strip().casefold() for part in expected.split(",") if part.strip()]
        return a in options
    if operator == "prefix":
        return a.startswith(e)
    return False


def component_matches(fields: dict[str, str], component: dict[str, object]) -> tuple[bool, list[str]]:
    if str(component.get("role")) == "mixin":
        return False, []
    reasons: list[str] = []
    for clause in component["selectors"]:  # type: ignore[index]
        field = str(clause["field"])
        operator = str(clause["operator"])
        expected = str(clause["value"])
        actual = fields.get(field, "")
        if not selector_matches(actual, operator, expected):
            return False, []
        reasons.append(f"{field} {operator} {expected!r}")
    also = [str(item) for item in (component.get("also_applies_to") or [])]
    workload_number = fields.get("Workload Number", "").strip()
    if also and workload_number and workload_number not in also:
        reasons.append(
            f"WARNING Workload Number {workload_number!r} is not in also_applies_to {also}"
        )
    return True, reasons


def merged_contracts(resolved: Iterable[dict[str, object]]) -> dict[str, object]:
    contracts: dict[str, object] = {}
    for item in resolved:
        component = item["component"]
        raw = component.get("contracts") or {}
        if isinstance(raw, dict):
            contracts.update(raw)
    return contracts


def mixin_should_apply(
    mixin: dict[str, object],
    fields: dict[str, str],
    primaries: list[dict[str, object]],
    provided_paths: set[str],
) -> bool:
    apply_when = mixin.get("apply_when") or {}
    if not isinstance(apply_when, dict) or not apply_when:
        return False
    if apply_when.get("always") is True:
        return True
    contracts = merged_contracts(primaries)
    if "compile_rocblas_bench" in apply_when:
        wanted = bool(apply_when["compile_rocblas_bench"])
        if bool(contracts.get("compile_rocblas_bench")) != wanted:
            return False
    if apply_when.get("build_policy"):
        if str(contracts.get("build_policy") or "") != str(apply_when["build_policy"]):
            return False
    missing = apply_when.get("missing_overlay")
    if missing and str(missing) in provided_paths:
        return False
    vendor = str(apply_when.get("gpu_vendor") or "").strip()
    if vendor and vendor.casefold() not in fields.get("GPU Vendor", "").casefold():
        return False
    return True


def validate_component_vs_spec(
    fields: dict[str, str],
    resolved: list[dict[str, object]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    framework = fields.get("Framework", "")
    fw = framework.casefold()
    for item in resolved:
        cid = str(item["component_id"])
        component = item["component"]
        if str(component.get("role")) == "mixin":
            continue
        contracts = component.get("contracts") or {}
        verifies = [str(value).casefold() for value in (component.get("verifies") or [])]
        does_not = [str(value).casefold() for value in (component.get("does_not_provide") or [])]
        lists_rvs = "rvs" in fw or "validation & diagnostics suite" in fw
        if lists_rvs and contracts.get("skip_rvs_default") == 1:
            errors.append(f"{cid}: skip_rvs_default is 1 but Framework lists RVS")
        lists_rocblas = "rocblas-bench" in fw or "rocblas (gemm)" in fw
        verifies_rocblas = any("rocblas-bench" in value for value in verifies)
        if lists_rocblas and not verifies_rocblas and not contracts.get("compile_rocblas_bench"):
            if "rocblas-bench invocation" in does_not:
                warnings.append(
                    f"{cid}: Framework lists rocblas-bench; overlay does not run it (install/verify only)"
                )
            else:
                warnings.append(
                    f"{cid}: Framework lists rocblas-bench but component does not verify or compile it"
                )
    return errors, warnings


def resolve_primaries(spec_path: Path, components_root: Path) -> list[dict[str, object]]:
    fields = definition_fields(spec_path)
    if not fields or not components_root.is_dir():
        return []
    yaml_path = components_root.parent / "config" / "implementation_packs.yaml"
    packs = implementation_packs(fields, yaml_path if yaml_path.is_file() else None)
    resolved: list[dict[str, object]] = []
    if packs:
        seen: set[str] = set()
        for pack in packs:
            if pack in seen:
                continue
            seen.add(pack)
            component_root = components_root / pack
            if not (component_root / "component.json").is_file():
                raise ValueError(f"implementation_packs.yaml id {pack!r} is not a component directory")
            component = load_component(component_root)
            if str(component.get("role")) == "mixin":
                raise ValueError(f"implementation_packs.yaml id {pack!r} is a mixin; list only primary packs")
            resolved.append(
                {
                    "component_id": component["component_id"],
                    "component_root": component_root,
                    "component": component,
                    "reasons": [f"config/implementation_packs.yaml maps to {pack!r}"],
                }
            )
        return resolved
    raise ValueError(
        "No component ids could be derived from "
        "Workload Number + GPU Vendor + config/implementation_packs.yaml"
    )


def resolve_mixins(
    fields: dict[str, str],
    components_root: Path,
    primaries: list[dict[str, object]],
) -> list[dict[str, object]]:
    provided_paths = {
        str(rel)
        for item in primaries
        for rel in item["component"].get("overlay") or []
    }
    mixins: list[dict[str, object]] = []
    if not components_root.is_dir():
        return mixins
    for component_root in sorted(path for path in components_root.iterdir() if path.is_dir()):
        if not (component_root / "component.json").is_file():
            continue
        component = load_component(component_root)
        if str(component.get("role")) != "mixin":
            continue
        if not mixin_should_apply(component, fields, primaries, provided_paths):
            continue
        overlay = [str(rel) for rel in component["overlay"] if str(rel) not in provided_paths]
        if not overlay:
            continue
        filtered = dict(component)
        filtered["overlay"] = overlay
        mixins.append(
            {
                "component_id": component["component_id"],
                "component_root": component_root,
                "component": filtered,
                "reasons": [f"mixin apply_when {component.get('apply_when')}"],
            }
        )
        provided_paths.update(overlay)
    return mixins


def resolve_components(spec_path: Path, components_root: Path) -> list[dict[str, object]]:
    fields = definition_fields(spec_path)
    primaries = resolve_primaries(spec_path, components_root)
    mixins = resolve_mixins(fields, components_root, primaries)
    return primaries + mixins


def validate_overlay_conflicts(resolved: Iterable[dict[str, object]]) -> None:
    destinations: dict[str, tuple[str, bytes]] = {}
    for item in resolved:
        cid = str(item["component_id"])
        root = Path(item["component_root"])
        component = item["component"]
        for rel in component["overlay"]:  # type: ignore[index]
            rel_s = str(rel)
            payload = (root / "files" / rel_s).read_bytes()
            prior = destinations.get(rel_s)
            if prior and prior[1] != payload:
                raise ValueError(
                    f"Conflicting implementation components target {rel_s!r}: {prior[0]} and {cid}"
                )
            destinations[rel_s] = (cid, payload)


def validate_all(components_root: Path) -> int:
    count = 0
    for component_root in sorted(path for path in components_root.iterdir() if path.is_dir()):
        if (component_root / "component.json").is_file():
            load_component(component_root)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Automatically resolve implementation components")
    parser.add_argument("--spec", default="benchmark_specification.json")
    parser.add_argument("--components-root", default="implementation_components")
    parser.add_argument("--json", action="store_true", help="Print machine-readable resolution details")
    parser.add_argument("--validate-manifests", action="store_true")
    args = parser.parse_args()
    components_root = Path(args.components_root).resolve()
    if args.validate_manifests:
        count = validate_all(components_root)
        print(f"[PASS] Validated {count} implementation component manifest(s)")
        return 0
    spec_path = Path(args.spec).resolve()
    resolved = resolve_components(spec_path, components_root)
    validate_overlay_conflicts(resolved)
    errors, warnings = validate_component_vs_spec(definition_fields(spec_path), resolved)
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    payload = [
        {
            "component_id": item["component_id"],
            "role": item["component"].get("role"),
            "completeness": item["component"].get("completeness"),
            "reasons": item["reasons"],
            "overlay": item["component"].get("overlay"),
        }
        for item in resolved
    ]
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif payload:
        for item in payload:
            print(f"{item['component_id']}: " + "; ".join(str(reason) for reason in item["reasons"]))
    else:
        print("No compatible implementation components discovered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
