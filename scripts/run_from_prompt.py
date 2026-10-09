#!/usr/bin/env python3
# File: scripts/run_from_prompt.py
# Description: Chatbox entry point. Parse a short operator prompt and run the sequential driver.
# The template root is the directory that contains this scripts/ folder.
# Repositories are written in that directory's parent. Do not pass --remote-root.
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from prompt_workflow import available_workloads, parse_workloads


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def remote_ip(text: str) -> str:
    matches = re.findall(
        r"\bssh\b[^\n]*@((?:\d{1,3}\.){3}\d{1,3})\b",
        text,
        flags=re.IGNORECASE,
    )
    unique = sorted(set(matches))
    if len(unique) > 1:
        raise SystemExit("[FAIL] Prompt must contain at most one SSH remote IPv4 address.")
    return unique[0] if unique else ""


def ensure_batch_manifest(project_root: Path, prompt: Path, workloads: list[str], ip: str) -> None:
    path = project_root / "batch_generation_manifest.json"
    batch: dict = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            batch = loaded
    batch.setdefault("schema_version", "1.0.0")
    batch.setdefault("generation_started_at", utc_now())
    batch["generation_finished_at"] = None
    batch["generation_duration_seconds"] = None
    batch["prompt_file"] = str(prompt)
    batch["submitted_prompt_artifact"] = str(prompt)
    batch["requested_workloads"] = workloads
    batch["remote_validation_ip"] = ip or None
    batch["remote_refresh_requested"] = False
    batch["remote_refresh_confirmed"] = False
    batch["remote_refresh_status"] = "not_requested"
    batch.setdefault("repositories", [])
    path.write_text(json.dumps(batch, indent=2) + "\n", encoding="utf-8", newline="\n")


def stamp_batch_finish(project_root: Path, workloads: list[str]) -> None:
    path = project_root / "batch_generation_manifest.json"
    if not path.is_file():
        return
    batch = json.loads(path.read_text(encoding="utf-8"))
    recorded = {str(row.get("workload")) for row in batch.get("repositories", []) if isinstance(row, dict)}
    if any(workload not in recorded for workload in workloads):
        return
    finished = utc_now()
    started = str(batch.get("generation_started_at") or finished)
    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    batch["generation_finished_at"] = finished
    batch["generation_duration_seconds"] = max(0, int((end_dt - start_dt).total_seconds()))
    path.write_text(json.dumps(batch, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate every workload named in a short operator prompt")
    parser.add_argument("--prompt-file", required=True)
    args = parser.parse_args(argv)
    template_root = Path(__file__).resolve().parents[1]
    project_root = template_root.parent
    prompt = Path(args.prompt_file).resolve()
    if not prompt.is_file():
        raise SystemExit(f"[FAIL] Prompt file is missing: {prompt}")
    text = prompt.read_text(encoding="utf-8")
    if re.search(r"(?im)^\s*legacy\s*:", text):
        print(
            "[INFO] Legacy: line ignored. This command uses only the current template "
            "and does not read other TEMPLATE_* directories.",
            flush=True,
        )
    workloads = parse_workloads(text, available_workloads(template_root / "BenchmarkSpecDefinitions.xlsx"))
    ip = remote_ip(text)
    print(f"[INFO] Template root: {template_root}", flush=True)
    print(f"[INFO] Project root: {project_root}", flush=True)
    print(f"[INFO] Workloads: {', '.join(workloads)}", flush=True)
    print(f"[INFO] Remote validation: {ip or 'NONE'}", flush=True)
    ensure_batch_manifest(project_root, prompt, workloads, ip)
    command = [
        sys.executable,
        str(template_root / "scripts" / "create_one_workload.py"),
        "--prompt-file",
        str(prompt),
        "--template-root",
        str(template_root),
        "--project-root",
        str(project_root),
        "--skip-remote-refresh",
    ]
    for workload in workloads:
        command.extend(["--workload", workload])
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    env["MSYS2_ARG_CONV_EXCL"] = "*"
    env["PYTHONUNBUFFERED"] = "1"
    completed = subprocess.run(command, cwd=str(template_root), env=env, check=False)
    stamp_batch_finish(project_root, workloads)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
