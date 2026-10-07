#!/usr/bin/env python3
# File: scripts/patch_aiter_gfx1250_optional.py
# Description: Make AITER gfx1250 gluon imports optional so gfx942 SGLang can load quant.
"""AITER fused_mxfp4_quant.py imports gfx1250 gluon kernels at module import.

Those kernels need triton.experimental.gluon.amd.cdna5 / _load_shared_fp4_*.
MI300X is gfx942 and never uses those kernels, but sglang.launch_server still
imports aiter.ops.triton.quant during ServerArgs init. Wrap the gfx1250 import
so baseline/extended SGLang can start. Idempotent.
"""
from __future__ import annotations

from pathlib import Path

MARKER = "patched-by: patch_aiter_gfx1250_optional.py"
OLD_IMPORT = """from aiter.ops.triton._gluon_kernels.gfx1250.quant.fused_mxfp4_quant import (
    _gluon_fused_dynamic_mxfp4_quant_moe_sort_kernel,
    _gluon_fused_reduce_rms_mxfp4_quant_kernel,
    _gluon_fused_rms_mxfp4_quant_kernel,
)
"""
NEW_IMPORT = """try:
    from aiter.ops.triton._gluon_kernels.gfx1250.quant.fused_mxfp4_quant import (
        _gluon_fused_dynamic_mxfp4_quant_moe_sort_kernel,
        _gluon_fused_reduce_rms_mxfp4_quant_kernel,
        _gluon_fused_rms_mxfp4_quant_kernel,
    )
except (ImportError, ModuleNotFoundError):  # patched-by: patch_aiter_gfx1250_optional.py
    _gluon_fused_dynamic_mxfp4_quant_moe_sort_kernel = None
    _gluon_fused_reduce_rms_mxfp4_quant_kernel = None
    _gluon_fused_rms_mxfp4_quant_kernel = None
"""


def _candidate_files() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    roots: list[Path] = []
    try:
        import aiter  # noqa: PLC0415

        roots.append(Path(aiter.__file__).resolve().parent)
    except Exception:
        pass
    repo = Path(__file__).resolve().parents[1]
    third = repo / "third_party" / "aiter" / "aiter"
    if third.is_dir():
        roots.append(third.resolve())
    for root in roots:
        path = root / "ops" / "triton" / "quant" / "fused_mxfp4_quant.py"
        resolved = path.resolve() if path.is_file() else None
        if resolved and resolved not in seen:
            seen.add(resolved)
            files.append(resolved)
    return files


def _patch(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already"
    if OLD_IMPORT not in text:
        if "gfx1250.quant.fused_mxfp4_quant" not in text:
            return "skip"
        raise SystemExit(f"[FAIL] unexpected fused_mxfp4_quant.py import layout: {path}")
    path.write_text(text.replace(OLD_IMPORT, NEW_IMPORT, 1), encoding="utf-8")
    return "patched"


def main() -> int:
    files = _candidate_files()
    if not files:
        print("[WARN] AITER fused_mxfp4_quant.py not found; gfx1250 optional import skipped.")
        return 0
    for path in files:
        status = _patch(path)
        print(f"[INFO] {status} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
