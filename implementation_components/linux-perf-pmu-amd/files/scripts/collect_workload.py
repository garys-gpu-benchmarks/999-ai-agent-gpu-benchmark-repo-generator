#!/usr/bin/env python3
# File: scripts/collect_workload.py
# Description: Linux perf PMU Analysis Harness collector, shared by AMD 111/311
#   and NVIDIA 211/411 (one file, identical in linux-perf-pmu-amd and
#   linux-perf-pmu-nvidia). Runs each yaml workload_commands entry (stress-ng)
#   under "perf stat -x," and publishes the same five metrics on every vendor:
#   IPC, branch misprediction %, cache misses per 1,000 instructions, pipeline
#   stall %, and context switches/s. A counter perf cannot read on this host
#   is reported as "na (<reason>)", never as an invented number.
# Execution: python3 scripts/collect_workload.py --run-dir <dir> --raw-file <csv> [--profile smoke]
# Requirements: python3, PyYAML, stress-ng, Linux perf (linux-tools-$(uname -r))
# Environment: BENCHMARK_PMU_STALL_EVENT (stall event override), BENCHMARK_PERF_BIN
#   (perf binary override; "none" runs without perf, for tests)
# License: Apache-2.0
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import resource
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import yaml

# Events every metric needs. context-switches is a software event, so it is
# still counted when the hardware PMU is not exposed (common in VMs).
REQUIRED_EVENTS = ("cycles", "instructions", "branches", "branch-misses", "cache-misses", "context-switches")
# "Cycles in which execution was stalled", picked by CPU vendor. The generic
# stalled-cycles-* events are not implemented on Intel, and Intel's
# cycle_activity.stalls_total does not exist on AMD. BENCHMARK_PMU_STALL_EVENT overrides.
STALL_EVENT_CANDIDATES = {
    "GenuineIntel": ("cycle_activity.stalls_total",),
    "AuthenticAMD": ("stalled-cycles-backend",),
}
DEFAULT_STALL_CANDIDATES = ("stalled-cycles-backend",)
DEFAULT_EVENT_LIST = ",".join(REQUIRED_EVENTS)

METRIC_KEYS = (
    "instructions_per_cycle_ipc",
    "branch_misprediction_rate",
    "cache_misses_per_1000_instructions",
    "pipeline_stall_pct",
    "context_switches_during_workload_switches_s",
)
HEADER = [
    "sample_index", "status", "workload_command", "duration_sec", "elapsed_sec",
    *METRIC_KEYS,
    "cycles", "instructions", "branches", "branch_misses", "cache_misses", "stall_cycles",
    "pipeline_stall_event", "pmu_counter_running_pct", "context_switches",
    "cpu_time_sec", "cpu_utilization_percent", "stress_ng_bogo_ops_s",
    "pmu_source", "error_message",
]

# stress-ng --metrics-brief row: "[pid] <stressor> <bogo ops> <real s> <usr s> <sys s> <bogo ops/s real> ..."
STRESS_ROW_RE = re.compile(
    r"\]\s+([A-Za-z][\w-]*)\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s+"
    r"([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)"
)


def pv(params: dict, key: str, profile: str, default=""):
    raw = params.get(key, default)
    if isinstance(raw, dict):
        return raw.get(profile, raw.get("smoke", default))
    return default if raw is None else raw


def duration_seconds(raw, default: float = 2.0) -> float:
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return default
    return number / 1000.0 if number >= 10000 else number


def resolve_perf() -> str | None:
    """Prefer the kernel-versioned binary; /usr/bin/perf is often a wrapper
    that only prints "WARNING: perf not found for kernel ..."."""
    override = os.environ.get("BENCHMARK_PERF_BIN", "").strip()
    if override:
        return None if override == "none" else override
    kernel = os.uname().release
    candidates = [Path(f"/usr/lib/linux-tools/{kernel}/perf"), Path(f"/usr/lib/linux-tools-{kernel}/perf")]
    candidates += sorted(Path("/usr/lib").glob("linux-tools-*/perf"), reverse=True)
    candidates += sorted(Path("/usr/lib/linux-tools").glob("*/perf"), reverse=True)
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 10000:
                return str(path)
        except OSError:
            continue
    found = shutil.which("perf")
    if not found:
        return None
    try:
        probe = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return found if probe.returncode == 0 and "not found" not in (probe.stdout + probe.stderr).lower() else None


def cpu_vendor() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("vendor_id"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def perf_paranoid() -> str:
    try:
        return Path("/proc/sys/kernel/perf_event_paranoid").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def normalize_event(name: str) -> str:
    """cpu_core/cycles/ -> cycles, cycles:u -> cycles (hybrid CPUs and
    perf_event_paranoid user-only counting change the printed name)."""
    name = name.strip()
    match = re.fullmatch(r"[\w.-]+/([^/]+)/[\w]*", name)
    if match:
        name = match.group(1)
    return re.sub(r":[ukhGHp]+$", "", name).lower()


def parse_perf_csv(text: str) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    """Parse "perf stat -x," output. Returns (counts, percent running, status)
    where status is "counted", "not supported", or "not counted"."""
    counts: dict[str, float] = {}
    running: dict[str, float] = {}
    status: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) < 3:
            continue
        value, event = fields[0].strip(), normalize_event(fields[2])
        if not event:
            continue
        if value.startswith("<"):
            status.setdefault(event, value.strip("<>"))
            continue
        try:
            number = float(value)
        except ValueError:
            continue
        counts[event] = counts.get(event, 0.0) + number  # hybrid CPUs print one line per core type
        status[event] = "counted"
        if len(fields) > 4:
            try:
                pct = float(fields[4])
                running[event] = min(running.get(event, pct), pct)
            except ValueError:
                pass
    return counts, running, status


def probe_event(perf: str, event: str) -> tuple[bool, bool]:
    """(perf knows the event name, perf counted a value for it). A probe that
    fails for lack of permission still counts as a known name, so a denied PMU
    is reported as denied rather than as unknown events."""
    try:
        done = subprocess.run(
            [perf, "stat", "-x,", "-e", event, "--", "true"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, False
    if done.returncode != 0:
        lowered = done.stderr.lower()
        unknown = "event syntax error" in lowered or "unknown" in lowered or "parser error" in lowered
        return (not unknown), False
    counts, _, _ = parse_perf_csv(done.stderr)
    return True, normalize_event(event) in counts


def pick_stall_event(perf: str | None, vendor: str) -> tuple[str | None, str]:
    override = os.environ.get("BENCHMARK_PMU_STALL_EVENT", "").strip()
    candidates = (override,) if override else STALL_EVENT_CANDIDATES.get(vendor, DEFAULT_STALL_CANDIDATES)
    if perf is None:
        return None, "perf not installed"
    for event in candidates:
        _, counted = probe_event(perf, event)
        if counted:
            return event, ""
    return None, f"no stall-cycle event counted on this CPU ({vendor}; tried {', '.join(candidates)})"


def pmu_unavailable_reason(perf: str | None, transcript: str) -> str:
    if perf is None:
        return f"na (perf not installed for kernel {os.uname().release})"
    lowered = transcript.lower()
    if any(token in lowered for token in ("no permission", "not permitted", "access to performance monitoring")):
        return f"na (PMU access denied: perf_event_paranoid={perf_paranoid()})"
    return "na (hardware PMU counters not available on this host)"


def stress_ng_bogo_ops_s(text: str) -> float | None:
    total = None
    for line in text.splitlines():
        lowered = line.lower()
        if "stress-ng" not in lowered or "(secs)" in lowered or "bogo ops" in lowered:
            continue
        match = STRESS_ROW_RE.search(line)
        if match:
            total = (total or 0.0) + float(match.group(6))
    return total


def run_timed(command: list[str], timeout: int) -> tuple[int, str, float, float, float]:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    try:
        done = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"[FAIL] workload timed out after {timeout} s: {' '.join(command)}") from exc
    elapsed = max(time.perf_counter() - started, 1e-6)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = max((after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime), 0.0)
    switches = max(float((after.ru_nvcsw - before.ru_nvcsw) + (after.ru_nivcsw - before.ru_nivcsw)), 0.0)
    return done.returncode, (done.stdout or "") + "\n" + (done.stderr or ""), elapsed, cpu, switches


def ratio(counts: dict[str, float], num: str, den: str, scale: float, na: str):
    if num in counts and counts.get(den, 0.0) > 0:
        return scale * counts[num] / counts[den]
    return na


def split_commands(raw: str, cpus: str, seconds: int) -> list[list[str]]:
    commands = []
    for part in re.split(r",(?=\s*stress-ng)", raw or ""):
        text = part.strip().replace("{num_cpus}", cpus).replace("{duration}", str(seconds))
        if text:
            commands.append(shlex.split(text))
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description="Linux perf PMU collector (111/211/311/411).")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--config", default="config/benchmark_config.yaml")
    parser.add_argument("--device", default="cpu", help="accepted for harness compatibility; CPU workload")
    parser.add_argument("--output-format", default="csv")
    parser.add_argument("--num-cpus", default=None, help="stress-ng worker count ({num_cpus})")
    parser.add_argument("--workload-commands", default=None, help="comma-separated stress-ng commands")
    parser.add_argument("--event-list", default=None, help="extra perf events counted with the metric events")
    parser.add_argument("--duration", default=None, help="seconds per workload command ({duration})")
    args = parser.parse_args()

    config_path = Path(args.config)
    params = {}
    if config_path.is_file():
        params = (yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}).get("sweep") or {}
    seconds = max(1, int(duration_seconds(args.duration if args.duration not in (None, "") else pv(params, "duration", args.profile, 2), 2)))
    cpus = str(args.num_cpus if args.num_cpus not in (None, "") else pv(params, "num_cpus", args.profile, 1) or 1)
    raw_cmds = args.workload_commands if args.workload_commands not in (None, "") else str(pv(params, "workload_commands", args.profile, "") or "")
    event_list = args.event_list if args.event_list not in (None, "") else str(pv(params, "event_list", args.profile, "") or "")
    commands = split_commands(raw_cmds, cpus, seconds) or [
        ["stress-ng", "--cpu", cpus, "--timeout", f"{seconds}s", "--metrics-brief"],
    ]
    if any(cmd and Path(cmd[0]).name == "stress-ng" for cmd in commands) and shutil.which("stress-ng") is None:
        raise SystemExit("[FAIL] stress-ng is not installed (setup installs it); refusing to profile an idle host")

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    perf = resolve_perf()
    vendor = cpu_vendor()
    stall_event, stall_reason = pick_stall_event(perf, vendor)

    events: list[str] = list(REQUIRED_EVENTS) + ([stall_event] if stall_event else [])
    dropped: list[str] = []
    for name in [item.strip() for item in event_list.split(",") if item.strip()]:
        if name in events:
            continue
        if perf is not None and probe_event(perf, name)[0]:
            events.append(name)
        else:
            dropped.append(name)
    (run_dir / "pmu_events.txt").write_text(
        "\n".join([
            f"perf={perf or 'not found'}",
            f"cpu_vendor={vendor}",
            f"perf_event_paranoid={perf_paranoid()}",
            f"pipeline_stall_event={stall_event or 'none'}" + (f" ({stall_reason})" if stall_reason else ""),
            f"events_requested={','.join(events)}",
            f"events_dropped_unknown_to_perf={','.join(dropped) or 'none'}",
        ]) + "\n",
        encoding="utf-8",
    )

    timeout = seconds + 60
    cpu_count = max(float(cpus), 1.0)
    rows = []
    for index, workload in enumerate(commands):
        counts: dict[str, float] = {}
        running: dict[str, float] = {}
        perf_text = ""
        transcript = ""
        rc = 1
        if perf is not None:
            perf_out = run_dir / f"perf_{index}.csv"
            rc, transcript, elapsed, cpu_time, switches = run_timed(
                [perf, "stat", "-x,", "-o", str(perf_out), "-e", ",".join(events), "--", *workload], timeout
            )
            perf_text = perf_out.read_text(encoding="utf-8", errors="replace") if perf_out.is_file() else ""
            counts, running, _ = parse_perf_csv(perf_text)
        bogo = stress_ng_bogo_ops_s(transcript)
        workload_ran = bogo is not None or "successful run completed" in transcript.lower()
        if perf is None or (not counts and not workload_ran):
            # perf missing, or perf could not open its events and never started
            # the workload: run it bare so CPU time and bogo-ops are still real.
            transcript = (transcript + "\n" + perf_text).strip() + "\n--- workload run without perf ---\n"
            rc, bare_text, elapsed, cpu_time, switches = run_timed(workload, timeout)
            transcript += bare_text
            bogo = stress_ng_bogo_ops_s(bare_text)
        (run_dir / f"perf_{index}.txt").write_text(transcript + ("\n" + perf_text if perf_text else ""), encoding="utf-8")
        if rc != 0:
            raise SystemExit(f"[FAIL] workload exited {rc}: {' '.join(workload)} (see {run_dir / f'perf_{index}.txt'})")

        pmu_ok = counts.get("cycles", 0.0) > 0 and counts.get("instructions", 0.0) > 0
        if pmu_ok:
            source = "perf"
            na = lambda event: f"na ({event} not counted on this host)"  # noqa: E731
            ipc = counts["instructions"] / counts["cycles"]
            mispredict = ratio(counts, "branch-misses", "branches", 100.0, na("branch-misses"))
            cache = ratio(counts, "cache-misses", "instructions", 1000.0, na("cache-misses"))
            if stall_event and normalize_event(stall_event) in counts:
                stall = 100.0 * counts[normalize_event(stall_event)] / counts["cycles"]
            else:
                stall = f"na ({stall_reason or (str(stall_event) + ' not counted on this host')})"
            hw = [running[e] for e in ("cycles", "instructions", "branches", "branch-misses", "cache-misses") if e in running]
            running_pct = min(hw) if hw else ""
        else:
            reason = pmu_unavailable_reason(perf, perf_text + transcript)
            source = "unavailable" if perf is not None else "perf_missing"
            ipc = mispredict = cache = stall = reason
            running_pct = ""
        if "context-switches" in counts:
            ctx = counts["context-switches"]
        else:
            ctx = switches  # getrusage of the reaped workload processes
        rows.append({
            "status": "ok",
            "workload_command": " ".join(workload),
            "duration_sec": seconds,
            "elapsed_sec": round(elapsed, 6),
            "instructions_per_cycle_ipc": ipc,
            "branch_misprediction_rate": mispredict,
            "cache_misses_per_1000_instructions": cache,
            "pipeline_stall_pct": stall,
            "context_switches_during_workload_switches_s": ctx / elapsed,
            "cycles": counts.get("cycles", ""),
            "instructions": counts.get("instructions", ""),
            "branches": counts.get("branches", ""),
            "branch_misses": counts.get("branch-misses", ""),
            "cache_misses": counts.get("cache-misses", ""),
            "stall_cycles": counts.get(normalize_event(stall_event), "") if stall_event else "",
            "pipeline_stall_event": stall_event or "none",
            "pmu_counter_running_pct": running_pct,
            "context_switches": ctx,
            "cpu_time_sec": round(cpu_time, 6),
            "cpu_utilization_percent": 100.0 * cpu_time / (elapsed * cpu_count),
            "stress_ng_bogo_ops_s": bogo if bogo is not None else "",
            "pmu_source": source,
            "error_message": "",
        })

    if len(rows) == 1:
        rows.append(dict(rows[0]))  # the harness requires at least two sample rows
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=HEADER, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for index, row in enumerate(rows):
        writer.writerow({"sample_index": index, **row})
    Path(args.raw_file).parent.mkdir(parents=True, exist_ok=True)
    Path(args.raw_file).write_text(buf.getvalue(), encoding="utf-8")
    print(buf.getvalue(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
