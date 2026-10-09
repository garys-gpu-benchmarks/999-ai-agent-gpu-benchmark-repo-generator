#!/usr/bin/env python3
# File: scripts/collect_workload.py
# Description: NVIDIA CUDA stack checks. VBIOS must be a real nvidia-smi -q field.
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import subprocess
from pathlib import Path

import yaml


def pv(params, key, profile, default=""):
    raw = params.get(key, default)
    if isinstance(raw, dict):
        return raw.get(profile, raw.get("smoke", default))
    return default if raw is None else raw


def run_command(command, timeout=60):
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, f"{command[0]}: {exc}"
    return completed.returncode, (completed.stdout or "") + "\n" + (completed.stderr or "")


def package_version(name):
    completed = subprocess.run(["dpkg-query", "-W", "-f=${Version}", name], check=False, capture_output=True, text=True)
    return (completed.stdout or "").strip() if completed.returncode == 0 else ""


def count_package_mismatches(packages, *, smi_ok: bool, cuda_mismatch: int) -> int:
    """Count missing dpkg names. nvidia-smi is the command, not a package.

    cuda-toolkit is the CUDA-major check already computed for the driver.
    """
    total = 0
    for name in packages:
        normalized = name.strip().lower().replace("_", "-")
        if normalized == "nvidia-smi":
            if not smi_ok:
                total += 1
            continue
        if normalized == "cuda-toolkit":
            total += int(cuda_mismatch)
            continue
        if not package_version(name) and not package_version(name.replace("_", "-")):
            total += 1
    return total


def version_token(text):
    match = re.search(r"([0-9]+(?:\.[0-9]+)+)", text or "")
    return match.group(1) if match else ""


def version_at_least(actual: str, minimum: str) -> bool:
    try:
        actual_parts = tuple(int(part) for part in actual.split("."))
        minimum_parts = tuple(int(part) for part in minimum.split("."))
    except ValueError:
        return False
    width = max(len(actual_parts), len(minimum_parts))
    return actual_parts + (0,) * (width - len(actual_parts)) >= minimum_parts + (0,) * (width - len(minimum_parts))


def nvidia_module_version():
    proc = Path("/proc/driver/nvidia/version")
    if proc.is_file():
        try:
            token = version_token(proc.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            token = ""
        if token:
            return token
    _code, text = run_command(["modinfo", "-F", "version", "nvidia"])
    return version_token(text)


def libcuda_soname_version():
    _code, text = run_command(["ldconfig", "-p"])
    for path in re.findall(r"libcuda\.so(?:\.\d+)*\s+=>\s+(\S+)", text):
        token = version_token(os.path.realpath(path).rsplit("libcuda.so.", 1)[-1])
        if token and token != "1":
            return token
    for directory in (Path("/usr/lib/x86_64-linux-gnu"), Path("/usr/lib64"), Path("/lib/x86_64-linux-gnu")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("libcuda.so.*")):
            token = version_token(path.name.replace("libcuda.so.", "", 1))
            if token and token != "1":
                return token
    return ""


def stack_mismatch_count(module_ver, smi_ver, soname_ver):
    """How many of nvidia-smi and libcuda disagree with the loaded kernel module."""
    versions = [module_ver, smi_ver, soname_ver]
    if not module_ver:
        return float(sum(1 for item in versions if not item) or 1)
    return float(sum(1 for item in (smi_ver, soname_ver) if not item or item != module_ver))


def cuda_driver_supports(expected: str, reported: str) -> bool:
    """True when the driver CUDA major is at least the workbook major."""
    expected_match = re.search(r"(\d+)", expected or "")
    reported_match = re.search(r"(\d+)", reported or "")
    if not expected_match or not reported_match:
        return False
    return int(reported_match.group(1)) >= int(expected_match.group(1))


def write_csv(path, header, rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore", lineterminator=chr(10))
    writer.writeheader()
    rows = list(rows)
    if len(rows) == 1:
        rows.append(dict(rows[0]))
    for index, row in enumerate(rows):
        writer.writerow({"sample_index": index, **row})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(buf.getvalue(), encoding="utf-8")
    print(buf.getvalue(), end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--config", default="config/benchmark_config.yaml")
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--output-format", default="csv")
    args = parser.parse_args()
    sweep = (yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}).get("sweep") or {}
    # Read for the record; not compared yet (kernel/runtime checks live elsewhere).
    _expected_kernel = str(pv(sweep, "kernel_version", args.profile, "6.8.0"))
    expected_driver = str(pv(sweep, "nvidia_driver_version", args.profile, sweep.get("driver_version", "580")))
    expected_cuda = str(pv(sweep, "cuda_version", args.profile, "12.6"))
    packages = [item.strip() for item in str(pv(sweep, "required_packages", args.profile, "nvidia-smi")).split(",") if item.strip()]
    permissions_check = str(pv(sweep, "permissions_check", args.profile, "true")).lower() in {"1", "true", "yes"}
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    smi_code, smi = run_command(["nvidia-smi"])
    if smi_code != 0:
        raise SystemExit("[FAIL] nvidia-smi is required for NVIDIA system-config")
    smi_q = run_command(["nvidia-smi", "-q"])[1]
    nvcc = run_command(["nvcc", "--version"])[1]
    (run_dir / "nvidia-smi.txt").write_text(smi, encoding="utf-8")
    (run_dir / "nvidia-smi-q.txt").write_text(smi_q, encoding="utf-8")
    (run_dir / "nvcc.txt").write_text(nvcc, encoding="utf-8")
    driver_line = re.search(r"Driver Version\s*:\s*([0-9.]+)", smi_q) or re.search(r"Driver Version:\s*([0-9.]+)", smi)
    driver_ver = driver_line.group(1) if driver_line else ""
    module_ver = nvidia_module_version()
    soname_ver = libcuda_soname_version()
    # Compare the loaded nvidia module, nvidia-smi, and libcuda SONAME with each other.
    # A userspace 595 build against a 580 module is a mismatch even when uname contains 580.
    stack_mismatches = stack_mismatch_count(module_ver, version_token(driver_ver), soname_ver)
    driver_meets_minimum = version_at_least(version_token(driver_ver), expected_driver)
    cuda_line = re.search(r"CUDA Version\s*:\s*([0-9.]+)", smi + smi_q) or re.search(r"release\s*([0-9.]+)", nvcc)
    cuda_ver = cuda_line.group(1) if cuda_line else ""
    # nvidia-smi "CUDA Version" is the newest CUDA the driver supports.
    # A driver that reports 13.2 satisfies a workbook major of 12.
    cuda_mismatch = 0 if cuda_driver_supports(expected_cuda, cuda_ver) else 1
    package_mismatch = count_package_mismatches(packages, smi_ok=(smi_code == 0), cuda_mismatch=cuda_mismatch)
    vbios = ""
    match = re.search(r"VBIOS Version\s*:\s*(\S+)", smi_q)
    if match:
        vbios = match.group(1)
    vbios_present = 1.0 if vbios and vbios.lower() not in {"n/a", "unknown", ""} else 0.0
    # Detected VBIOS version, for information only (no expected-revision metric or gate).
    (run_dir / "vbios_version.txt").write_text((vbios or "not detected") + "\n", encoding="utf-8")
    permission_errors = 0
    if permissions_check:
        # /dev/nvidia-caps is a directory and is not writable for a normal user.
        nodes = [node for node in Path("/dev").glob("nvidia*") if node.is_char_device()]
        if not nodes:
            permission_errors += 1
        for node in nodes:
            if not os.access(node, os.R_OK | os.W_OK):
                permission_errors += 1
    compliance_checks = [
        driver_meets_minimum,
        bool(module_ver and version_token(driver_ver) == module_ver),
        bool(soname_ver and version_token(driver_ver) == soname_ver),
    ]
    driver_compliance = 100.0 * sum(compliance_checks) / len(compliance_checks)
    header = [
        "sample_index", "status",
        "cuda_package_version_mismatches_count",
        "cuda_major_version_mismatch_count",
        "nvidia_kernel_module_driver_version_mismatches_count",
        "vbios_string_present",
        "driver_compliance_percent",
        "required_library_path_device_permission_errors",
        "error_message",
    ]
    row = {
        "status": "ok" if vbios_present == 1.0 and stack_mismatches == 0 else "error",
        "cuda_package_version_mismatches_count": float(package_mismatch),
        "cuda_major_version_mismatch_count": float(cuda_mismatch),
        "nvidia_kernel_module_driver_version_mismatches_count": stack_mismatches,
        "vbios_string_present": vbios_present,
        "driver_compliance_percent": driver_compliance,
        "required_library_path_device_permission_errors": float(permission_errors),
        "error_message": "" if vbios else "VBIOS Version missing from nvidia-smi -q",
    }
    write_csv(args.raw_file, header, [row])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
