#!/usr/bin/env python3
# File: scripts/host_exec.py
# Description: Official Windows host shell is Git Bash + OpenSSH, never WSL bash.
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


def resolve_host_bash() -> str:
    if os.name != "nt":
        return shutil.which("bash") or "bash"
    env = os.environ.get("GIT_BASH") or ""
    candidates = [
        env,
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        str(Path.home() / "AppData/Local/Programs/Git/bin/bash.exe"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        lowered = str(path).lower().replace("\\", "/")
        if "windowsapps" in lowered or "system32" in lowered or "wsl" in lowered:
            continue
        if path.is_file() and ("git" in lowered or env):
            return str(path)
    found = shutil.which("bash") or ""
    lowered = found.lower().replace("\\", "/")
    if found and "git" in lowered and "windowsapps" not in lowered and "wsl" not in lowered:
        return found
    raise SystemExit(
        "[FAIL] Git Bash not found. The official Windows driver requires "
        "Git for Windows bash.exe, not WSL bash. Set GIT_BASH to the Git bash.exe path."
    )


def to_git_bash_path(path: str) -> str:
    text = str(path or "").strip().strip('"').strip("'")
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", text)
    if match:
        return f"/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}"
    return text.replace("\\", "/")


def normalize_ssh_command(ssh: str) -> str:
    """Rewrite Windows drive-letter key paths so Git Bash OpenSSH can read -i."""
    parts = re.split(r"(\s+)", ssh.strip())
    out: list[str] = []
    take_path = False
    for part in parts:
        if take_path and part.strip():
            out.append(to_git_bash_path(part))
            take_path = False
            continue
        out.append(part)
        if part.strip() == "-i":
            take_path = True
    return "".join(out)


def run_host_bash(
    command: str,
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    bash = resolve_host_bash()
    env = os.environ.copy()
    # Git Bash rewrites /opt/... into C:/Program Files/Git/opt/... before ssh.
    if os.name == "nt":
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"
    return subprocess.run(
        [bash, "-lc", command],
        cwd=str(cwd) if cwd else None,
        check=check,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def ssh_argv(ssh: str) -> list[str]:
    import shlex

    return shlex.split(normalize_ssh_command(ssh))
