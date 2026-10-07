#!/usr/bin/env python3
# File: scripts/validate_template_inputs.py
# Version: 1.0.0
# Maintainer: AI Agent GPU Benchmark Repo Generator
# Date: 2026-07-06
# Description: Validate template contracts for benchmark_specification.json and generation_manifest.json.
# Execution: python3 scripts/validate_template_inputs.py --benchmark-specification benchmark_specification.json --benchmark-schema schemas/benchmark_specification.schema.json
# Options: --benchmark-specification, --benchmark-definition, --benchmark-schema, --generation-manifest, --generation-schema, --allow-missing-benchmark-specification, --allow-missing-generation-manifest, --quiet
# Requirements: Python 3.10+
# Environment: Run from repository root in Phase 0 and before completion.
# Dependencies: Python standard library; optional jsonschema if installed
# Variables: None
# Repository: gpu-bench/sys-bench workload template
# License: Apache-2.0

"""Schema-backed contract validation for template generation inputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_BENCHMARK_FIELDS = [
    "Workload Number",
    "Workload Name",
    "Execution Domain",
    "Workload Type",
    "Workload Category",
    "Main Goal",
    "Validation Objective",
    "Metrics",
    "Framework",
    "Installation and Execution Summary",
    "Execution Description With Parameters",
    "Workload Command Line Executable",
]

ALLOWED_EXECUTION_DOMAINS = {
    "GPU Compute / ROCm",
    "GPU Compute / CUDA",
    "LLM Serving",
    "Memory / Transfer",
    "CPU / System",
    "End-to-End Pipeline",
    "Validation / Correctness",
}

ALLOWED_WORKLOAD_TYPES = {"Benchmark", "Test"}


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate machine-checkable template contracts.")
    parser.add_argument(
        "--benchmark-specification",
        "--benchmark-definition",
        dest="benchmark_definition",
        type=Path,
        help="Path to benchmark_specification.json",
    )
    parser.add_argument(
        "--benchmark-schema",
        type=Path,
        default=Path("schemas/benchmark_specification.schema.json"),
        help="Path to benchmark specification JSON schema",
    )
    parser.add_argument("--generation-manifest", type=Path, help="Path to results/generation_manifest.json")
    parser.add_argument(
        "--generation-schema",
        type=Path,
        default=Path("schemas/generation_report.schema.json"),
        help="Path to generation manifest JSON schema",
    )
    parser.add_argument("--batch-manifest", type=Path, help="Path to batch_generation_manifest.json")
    parser.add_argument(
        "--batch-schema",
        type=Path,
        default=Path("schemas/batch_generation_report.schema.json"),
        help="Path to batch generation manifest JSON schema",
    )
    parser.add_argument(
        "--allow-missing-benchmark-specification",
        "--allow-missing-benchmark-definition",
        dest="allow_missing_benchmark_definition",
        action="store_true",
        help="Do not fail if the specification path does not exist",
    )
    parser.add_argument(
        "--allow-missing-generation-manifest",
        action="store_true",
        help="Do not fail if --generation-manifest path does not exist",
    )
    parser.add_argument("--quiet", action="store_true", help="Print only failures.")
    return parser.parse_args(argv)


def _load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_schema_file_exists(path: Path, label: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append(f"{label} schema file does not exist: {path}")
        return errors
    try:
        _load_json_file(path)
    except json.JSONDecodeError as exc:
        errors.append(f"{label} schema file is not valid JSON: {path} ({exc})")
    return errors


def _try_jsonschema(instance: Any, schema: Any) -> list[str]:
    """Validate via jsonschema package if available; otherwise return no schema errors."""
    try:
        import jsonschema  # type: ignore
    except Exception:
        return []

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    rendered: list[str] = []
    for err in errors:
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        rendered.append(f"JSON Schema violation at {path}: {err.message}")
    return rendered


def _is_placeholder(value: str) -> bool:
    return value.strip() in {"", "--", "TBD"}


def _validate_benchmark_definition(payload: Any) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, list):
        return ValidationResult(["benchmark_specification.json must be a JSON array"], warnings)
    if not payload:
        return ValidationResult(["benchmark_specification.json must not be empty"], warnings)

    seen_fields: dict[str, str] = {}

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            errors.append(f"Item {idx} must be an object.")
            continue

        for required_key in ("field_name", "source_file", "value"):
            if required_key not in item:
                errors.append(f"Item {idx} missing required key '{required_key}'.")

        field_name = item.get("field_name")
        source_file = item.get("source_file")
        value = item.get("value")

        if not isinstance(field_name, str) or not field_name.strip():
            errors.append(f"Item {idx} has invalid field_name: {field_name!r}")
            continue
        if not isinstance(source_file, str) or not source_file.strip():
            errors.append(f"Item {idx} has invalid source_file for '{field_name}'.")
        if not isinstance(value, str):
            errors.append(f"Item {idx} value for '{field_name}' must be a string.")
            continue

        seen_fields[field_name] = value

    for required_field in REQUIRED_BENCHMARK_FIELDS:
        if required_field not in seen_fields:
            errors.append(f"Missing required field: '{required_field}'.")
        elif _is_placeholder(seen_fields[required_field]):
            errors.append(
                f"Required field '{required_field}' has blank or placeholder value: "
                f"{seen_fields[required_field]!r}"
            )

    domain = seen_fields.get("Execution Domain", "")
    if domain and domain not in ALLOWED_EXECUTION_DOMAINS:
        errors.append(f"Execution Domain '{domain}' is invalid.")

    workload_type = seen_fields.get("Workload Type", "")
    if workload_type and workload_type not in ALLOWED_WORKLOAD_TYPES:
        errors.append(f"Workload Type '{workload_type}' must be one of {sorted(ALLOWED_WORKLOAD_TYPES)}.")

    workload_number = seen_fields.get("Workload Number", "")
    if workload_number and not re.fullmatch(r"[0-9]+", workload_number):
        errors.append(f"Workload Number must be numeric, got: {workload_number!r}")

    if "Metrics" in seen_fields and "," not in seen_fields["Metrics"] and ";" not in seen_fields["Metrics"]:
        warnings.append("Metrics field appears to contain a single token; confirm this is expected.")

    return ValidationResult(errors, warnings)


def _is_iso8601_utc(timestamp: str) -> bool:
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _validate_generation_manifest(payload: Any) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        return ValidationResult(["generation_manifest.json must be a JSON object"], warnings)

    required_keys = [
        "schema_version",
        "source_template_commit",
        "workload_id",
        "workload_name",
        "generated_at",
        "generation_started_at",
        "generation_finished_at",
        "generation_duration_seconds",
    ]
    for key in required_keys:
        if key not in payload:
            errors.append(f"generation_manifest.json missing required key '{key}'.")

    schema_version = payload.get("schema_version")
    if schema_version != "1.0.0":
        errors.append(f"schema_version must be '1.0.0', got {schema_version!r}.")

    source_commit = payload.get("source_template_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", source_commit):
        errors.append("source_template_commit must be a 7-40 char hex commit SHA.")

    workload_id = payload.get("workload_id")
    if not isinstance(workload_id, str) or not re.fullmatch(r"[0-9]+", workload_id):
        errors.append("workload_id must be numeric string.")

    workload_name = payload.get("workload_name")
    if not isinstance(workload_name, str) or _is_placeholder(workload_name):
        errors.append("workload_name must be non-empty and not placeholder.")

    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not _is_iso8601_utc(generated_at):
        errors.append("generated_at must be valid ISO-8601 timestamp.")

    generation_started_at = payload.get("generation_started_at")
    if not isinstance(generation_started_at, str) or not _is_iso8601_utc(generation_started_at):
        errors.append("generation_started_at must be valid ISO-8601 timestamp.")

    generation_finished_at = payload.get("generation_finished_at")
    if not isinstance(generation_finished_at, str) or not _is_iso8601_utc(generation_finished_at):
        errors.append("generation_finished_at must be valid ISO-8601 timestamp.")

    generation_duration = payload.get("generation_duration_seconds")
    if not isinstance(generation_duration, int) or isinstance(generation_duration, bool) or generation_duration < 0:
        errors.append("generation_duration_seconds must be a non-negative integer.")

    generated_by = payload.get("generated_by")
    if generated_by is not None:
        if not isinstance(generated_by, dict):
            errors.append("generated_by must be an object when present.")
        else:
            agent = generated_by.get("agent")
            if not isinstance(agent, str) or not agent.strip():
                errors.append("generated_by.agent must be a non-empty string when generated_by is present.")

    return ValidationResult(errors, warnings)


def _validate_batch_manifest(payload: Any) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ValidationResult(["batch_generation_manifest.json must be a JSON object"], [])
    for key in (
        "schema_version",
        "generation_started_at",
        "generation_finished_at",
        "generation_duration_seconds",
        "requested_workloads",
        "repositories",
    ):
        if key not in payload:
            errors.append(f"batch_generation_manifest.json missing required key '{key}'.")
    workloads = payload.get("requested_workloads")
    if (
        not isinstance(workloads, list)
        or not workloads
        or any(not isinstance(item, str) or not re.fullmatch(r"[0-9]+", item) for item in workloads)
    ):
        errors.append("requested_workloads must be a non-empty list of numeric strings.")
    repositories = payload.get("repositories")
    in_progress = isinstance(workloads, list) and isinstance(repositories, list) and len(repositories) < len(workloads)
    started = payload.get("generation_started_at")
    if not isinstance(started, str) or not _is_iso8601_utc(started):
        errors.append("generation_started_at must be a valid ISO-8601 timestamp.")
    finished = payload.get("generation_finished_at")
    duration = payload.get("generation_duration_seconds")
    if in_progress:
        if finished not in {None, ""} and (not isinstance(finished, str) or not _is_iso8601_utc(finished)):
            errors.append("generation_finished_at must be null or a valid ISO-8601 timestamp while the batch is in progress.")
        if duration not in {None} and (not isinstance(duration, int) or isinstance(duration, bool) or duration < 0):
            errors.append("generation_duration_seconds must be null or a non-negative integer while the batch is in progress.")
    else:
        if not isinstance(finished, str) or not _is_iso8601_utc(finished):
            errors.append("generation_finished_at must be a valid ISO-8601 timestamp.")
        if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
            errors.append("generation_duration_seconds must be a non-negative integer.")
    if not isinstance(repositories, list):
        errors.append("repositories must be a list.")
    elif not in_progress and len(repositories) != len(workloads or []):
        errors.append("repositories must contain one result per requested workload.")
    elif isinstance(repositories, list):
        for index, repository in enumerate(repositories):
            if not isinstance(repository, dict):
                errors.append(f"repositories[{index}] must be an object.")
                continue
            for key in ("create_start_time", "create_end_time"):
                value = repository.get(key)
                if not isinstance(value, str) or not _is_iso8601_utc(value):
                    errors.append(
                        f"repositories[{index}].{key} must be a valid ISO-8601 timestamp."
                    )
            total_time = repository.get("create_total_time")
            if not isinstance(total_time, str) or not total_time.strip():
                errors.append(
                    f"repositories[{index}].create_total_time must be a non-empty string."
                )
    return ValidationResult(errors, [])


def _validate_target(
    data_path: Path | None,
    schema_path: Path,
    allow_missing: bool,
    target_name: str,
    custom_validator: callable,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_validate_schema_file_exists(schema_path, target_name))
    if errors:
        return ValidationResult(errors, warnings)

    if data_path is None:
        return ValidationResult(errors, warnings)

    if not data_path.exists():
        if allow_missing:
            warnings.append(f"{target_name} file not found (allowed): {data_path}")
            return ValidationResult(errors, warnings)
        errors.append(f"{target_name} file not found: {data_path}")
        return ValidationResult(errors, warnings)

    try:
        payload = _load_json_file(data_path)
    except json.JSONDecodeError as exc:
        errors.append(f"{target_name} is not valid JSON: {data_path} ({exc})")
        return ValidationResult(errors, warnings)

    schema = _load_json_file(schema_path)
    schema_errors = _try_jsonschema(payload, schema)
    errors.extend(schema_errors)

    semantic = custom_validator(payload)
    errors.extend(semantic.errors)
    warnings.extend(semantic.warnings)
    return ValidationResult(errors, warnings)


def _print_result(label: str, result: ValidationResult, quiet: bool) -> None:
    if result.ok:
        if not quiet:
            print(f"[PASS] {label}")
            for warning in result.warnings:
                print(f"  [WARN] {warning}")
    else:
        print(f"[FAIL] {label}")
        for err in result.errors:
            print(f"  - {err}")
        for warning in result.warnings:
            print(f"  [WARN] {warning}")


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    benchmark_result = _validate_target(
        data_path=args.benchmark_definition,
        schema_path=args.benchmark_schema,
        allow_missing=args.allow_missing_benchmark_definition,
        target_name="benchmark_definition",
        custom_validator=_validate_benchmark_definition,
    )
    manifest_result = _validate_target(
        data_path=args.generation_manifest,
        schema_path=args.generation_schema,
        allow_missing=args.allow_missing_generation_manifest,
        target_name="generation_manifest",
        custom_validator=_validate_generation_manifest,
    )
    batch_result = _validate_target(
        data_path=args.batch_manifest,
        schema_path=args.batch_schema,
        allow_missing=False,
        target_name="batch_generation_manifest",
        custom_validator=_validate_batch_manifest,
    )

    if args.benchmark_definition is not None:
        _print_result("benchmark_definition contract validation", benchmark_result, args.quiet)
    if args.generation_manifest is not None:
        _print_result("generation_manifest contract validation", manifest_result, args.quiet)
    if args.batch_manifest is not None:
        _print_result("batch_generation_manifest contract validation", batch_result, args.quiet)

    if not benchmark_result.ok or not manifest_result.ok or not batch_result.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
