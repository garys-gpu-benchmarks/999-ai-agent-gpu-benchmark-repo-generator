#!/usr/bin/env python3
# File: scripts/parse_results.py
# Description: Parse SDXL CSV or RESULT lines into SQLite. Converts latency_ms to seconds.
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x00")
RESULT_RE = re.compile(
    r"RESULT\s+"
    r"model_name=(\S+)\s+precision=(\S+)\s+scheduler=(\S+)\s+"
    r"prompt_source=(\S+)\s+prompt_len=(\S+)\s+image_resolution=(\S+)\s+"
    r"batch_size=(\S+)\s+num_images=(\S+)\s+num_inference_steps=(\S+)\s+"
    r"guidance_scale=(\S+)\s+seed=(\S+)\s+"
    r"per_image_latency_sec=([0-9.eE+-]+)\s+images_per_sec=([0-9.eE+-]+)\s+"
    r"peak_vram_gb=([0-9.eE+-]+)\s+status=(\w+)"
)
METRIC_COLUMNS = (
    "per_image_latency_s",
    "images_per_sec",
    "peak_gpu_memory_gb",
    "first_image_latency_s",
    "step_time_ms",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def load_fields() -> dict[str, str]:
    for name in ("benchmark_specification.json", "benchmark_definition.json"):
        path = Path(name)
        if path.is_file():
            return {
                str(item.get("field_name", "")): str(item.get("value", ""))
                for item in json.loads(path.read_text(encoding="utf-8"))
            }
    return {}


def parse_csv_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "latency_ms" in line and ("sample_index" in line or "image_index" in line):
            header = next(csv.reader([line]))
            continue
        if header is None:
            continue
        parts = next(csv.reader([line]))
        if len(parts) != len(header) or parts[0].lower() in {"sample_index", "image_index"}:
            continue
        rows.append({header[i]: parts[i].strip() for i in range(len(header))})
    return rows


def parse_result_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, match in enumerate(RESULT_RE.finditer(text)):
        latency_ms = float(match.group(12)) * 1000.0
        rows.append(
            {
                "sample_index": str(index),
                "status": match.group(16),
                "latency_ms": str(latency_ms),
                "images_per_sec": match.group(13),
                "gpu_mem_gb": match.group(14),
                "step_time_ms": str(latency_ms / max(1.0, float(match.group(9)))),
                "error_message": "",
            }
        )
    return rows


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0, "stddev": 0.0, "p95": 0.0}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "max": ordered[-1],
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "p95": ordered[min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))],
    }


def as_float(value: str, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-file", required=True, type=Path)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("BENCHMARK_DB", "results/benchmark.db")))
    parser.add_argument("--config", type=Path, default=Path("config/benchmark_config.yaml"))
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    raw_text = strip_ansi(args.raw_file.read_text(encoding="utf-8", errors="replace"))
    fields = load_fields()
    rows = parse_csv_rows(raw_text)
    if not rows:
        rows = parse_result_rows(raw_text)
    if not rows:
        raise SystemExit("[FAIL] No supported SDXL CSV or RESULT rows found.")
    first_raw = rows[0].get("first_image_latency_ms")
    if first_raw not in (None, ""):
        first_latency_s = as_float(first_raw) / 1000.0
    else:
        first_latency_s = as_float(rows[0].get("latency_ms")) / 1000.0
    samples = []
    for index, row in enumerate(rows):
        latency_ms = as_float(row.get("latency_ms"))
        sample = {
            "sample_index": int(float(row.get("sample_index", row.get("image_index", index)))),
            "status": row.get("status", "ok") or "ok",
            "error_message": row.get("error_message") or None,
            "created_at": utc_now(),
            "per_image_latency_s": latency_ms / 1000.0,
            "per_image_latency_sec": latency_ms / 1000.0,
            "images_per_sec": as_float(row.get("images_per_sec")),
            "peak_gpu_memory_gb": as_float(row.get("gpu_mem_gb", row.get("peak_gpu_memory_gb"))),
            "first_image_latency_s": first_latency_s,
            "step_time_ms": as_float(row.get("step_time_ms")),
        }
        for column in METRIC_COLUMNS:
            if sample[column] <= 0:
                raise SystemExit(f"[FAIL] missing metric {column}")
        samples.append(sample)
    started = utc_now()
    finished = utc_now()
    latencies = [float(sample["per_image_latency_s"]) for sample in samples]
    total_timed_s = sum(latencies)
    aggregates = {
        "per_image_latency_s": statistics.fmean(latencies),
        "per_image_latency_sec": statistics.fmean(latencies),
        "images_per_sec": len(samples) / total_timed_s,
        "peak_gpu_memory_gb": max(float(sample["peak_gpu_memory_gb"]) for sample in samples),
        "first_image_latency_s": float(samples[0]["first_image_latency_s"]),
        "step_time_ms": statistics.fmean(float(sample["step_time_ms"]) for sample in samples),
    }
    summary = {
        "status": "ok",
        "sample_count": len(samples),
        "profile": args.profile,
        "metrics": aggregates,
        "metric_stats": {column: stats([sample[column] for sample in samples]) for column in METRIC_COLUMNS},
        "started_at": started,
        "finished_at": finished,
    }
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        benchmark_id TEXT, benchmark_name TEXT, status TEXT, started_at TEXT, finished_at TEXT,
        host_name TEXT, os_version TEXT, kernel_version TEXT, gpu_name TEXT, rocm_version TEXT,
        framework_version TEXT, git_sha TEXT, config_path TEXT, command_line TEXT, error_message TEXT,
        per_image_latency_s REAL, images_per_sec REAL, peak_gpu_memory_gb REAL,
        first_image_latency_s REAL, step_time_ms REAL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(run_id),
        sample_index INTEGER, status TEXT, per_image_latency_s REAL, images_per_sec REAL,
        peak_gpu_memory_gb REAL, first_image_latency_s REAL, step_time_ms REAL,
        error_message TEXT, created_at TEXT)"""
    )
    cursor = conn.execute(
        """INSERT INTO runs (benchmark_id, benchmark_name, status, started_at, finished_at, host_name, os_version,
            kernel_version, gpu_name, rocm_version, framework_version, git_sha, config_path, command_line, error_message,
            per_image_latency_s, images_per_sec, peak_gpu_memory_gb, first_image_latency_s, step_time_ms)
            VALUES (?, ?, 'ok', ?, ?, ?, ?, '', '', '', 'sdxl-diffusers', '', ?, '', NULL, ?, ?, ?, ?, ?)""",
        (
            fields.get("Workload Number", "124"),
            fields.get("Workload Name", "Stable Diffusion XL Inference Baseline"),
            started,
            finished,
            os.uname().nodename if hasattr(os, "uname") else "",
            fields.get("OS Version", ""),
            str(args.config),
            aggregates["per_image_latency_s"],
            aggregates["images_per_sec"],
            aggregates["peak_gpu_memory_gb"],
            aggregates["first_image_latency_s"],
            aggregates["step_time_ms"],
        ),
    )
    run_id = int(cursor.lastrowid)
    for sample in samples:
        conn.execute(
            """INSERT INTO samples (run_id, sample_index, status, per_image_latency_s, images_per_sec,
            peak_gpu_memory_gb, first_image_latency_s, step_time_ms, error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
            (
                run_id,
                sample["sample_index"],
                sample["status"],
                sample["per_image_latency_s"],
                sample["images_per_sec"],
                sample["peak_gpu_memory_gb"],
                sample["first_image_latency_s"],
                sample["step_time_ms"],
                sample["created_at"],
            ),
        )
    conn.commit()
    conn.close()
    Path("results/summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    run_dir = args.run_dir or args.raw_file.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "samples.csv").open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(samples[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(samples)
    (run_dir / "samples.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    (run_dir / "raw_results.csv").write_text((run_dir / "samples.csv").read_text(encoding="utf-8"), encoding="utf-8")
    with (run_dir / "raw_results.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            handle.write(json.dumps(sample) + "\n")
    if not args.quiet:
        print(f"[PASS] Parsed {len(samples)} samples into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
