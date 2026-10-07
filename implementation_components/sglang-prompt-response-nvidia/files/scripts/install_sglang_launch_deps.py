#!/usr/bin/env python3
"""Install SGLang launch_server imports without replacing the cu130 torch pin.

Do not pip-install torch/torchvision/torchaudio/transformers.
Skip outlines/outlines_core: no cp314 wheel, source build needs Rust.
"""
from __future__ import annotations

import subprocess
import sys

SKIP = {
    "torch",
    "torchvision",
    "torchaudio",
    "transformers",
    "outlines",
    "outlines_core",
    "outlines-core",
}
REMAP = {
    "PIL": "pillow",
    "cv2": "opencv-python-headless",
    "yaml": "pyyaml",
    "sgl_kernel": "sglang-kernel==0.4.6.post1",
    "flashinfer": "flashinfer-python==0.6.7.post3",
    "flashinfer_python": "flashinfer-python==0.6.7.post3",
    "xgrammar": "xgrammar==0.1.32",
}
PREINSTALL = (
    "flashinfer-python==0.6.7.post3",
    "flashinfer-cubin==0.6.7.post3",
    "xgrammar==0.1.32",
    "jsonschema",
)
SGLANG_KERNEL_INDEX = (
    "--index-url",
    "https://docs.sglang.ai/whl/cu130/",
    "--extra-index-url",
    "https://pypi.org/simple",
)


def missing_from(stderr: str) -> str | None:
    marker = "No module named "
    if marker not in stderr:
        return None
    start = stderr.rfind(marker) + len(marker)
    name = stderr[start:].strip().strip("'\"")
    name = name.split()[0].strip("'\"")
    return name.split(".")[0]


CHECKS = (
    [sys.executable, "-m", "sglang.launch_server", "--help"],
    [sys.executable, "-c", "import sglang.srt.entrypoints.http_server"],
    [
        sys.executable,
        "-c",
        "from sglang.srt.layers.sampler import create_sampler",
    ],
    [sys.executable, "-c", "import sgl_kernel"],
)


def pip_install(py: str, pkg: str) -> int:
    cmd = [py, "-m", "pip", "install", pkg, "--upgrade-strategy", "only-if-needed"]
    if "sglang-kernel" in pkg:
        # A previously-installed sglang-kernel binary can be ABI-mismatched
        # (wrong torch/CUDA build) while pip still considers it "satisfied" --
        # force a real reinstall from the pinned cu130 wheel index rather than
        # silently no-op-ing on the broken package already on disk.
        cmd = [
            py, "-m", "pip", "install", pkg,
            "--force-reinstall", "--no-deps", "--no-cache-dir",
            *SGLANG_KERNEL_INDEX,
        ]
    print(f"INSTALL {pkg}", flush=True)
    rc = subprocess.run(cmd).returncode
    if rc != 0 and "sglang-kernel" not in pkg:
        print(f"INSTALL {pkg} --no-deps", flush=True)
        rc = subprocess.run([py, "-m", "pip", "install", pkg, "--no-deps"]).returncode
    return rc


def main() -> int:
    py = sys.executable
    for pkg in PREINSTALL:
        if pip_install(py, pkg) != 0:
            return 1
    for _ in range(80):
        pending = None
        for cmd in CHECKS:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                continue
            pending = (cmd, (proc.stderr or "") + (proc.stdout or ""))
            break
        if pending is None:
            print("LAUNCH_SERVER_IMPORT_OK", flush=True)
            return 0
        cmd, err = pending
        name = missing_from(err)
        if not name and "python-multipart" in err:
            name = "python-multipart"
        if not name and ("sgl_kernel" in cmd[-1] or "[sgl_kernel]" in err or "common_ops" in err):
            # ABI-mismatch failure ("Could not load any common_ops library!",
            # "undefined symbol: ...") doesn't read as a plain ModuleNotFoundError,
            # so missing_from() can't parse a name out of it -- but the failing
            # check command names sgl_kernel directly, so treat it as that
            # package needing a forced reinstall rather than giving up.
            name = "sgl_kernel"
        if not name:
            sys.stderr.write(err[-2000:])
            return 1
        pkg = REMAP.get(name, name)
        if pkg in SKIP or name in SKIP:
            print(f"SKIP {name} -> {pkg}", flush=True)
            sys.stderr.write(err[-1500:])
            return 2
        if pip_install(py, pkg) != 0:
            return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
