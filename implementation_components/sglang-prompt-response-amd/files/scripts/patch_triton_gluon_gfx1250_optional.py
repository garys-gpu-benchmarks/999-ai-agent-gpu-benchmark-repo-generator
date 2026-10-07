#!/usr/bin/env python3
# File: scripts/patch_triton_gluon_gfx1250_optional.py
# Description: Make Triton's own gluon.amd.gfx1250 import optional so gfx942
# SGLang can survive its first real prefill.
"""triton.experimental.gluon.amd.__init__ unconditionally does
`from . import gfx1250` at package-import time, even though gfx1250 is a
different AMD architecture than gfx942 (MI300X) and is never used by it.

On this ROCm 7.2 / Triton 3.6.0 wheel, that gfx1250 submodule itself imports
`triton.experimental.gluon.amd.cdna5`, which references
`_load_shared_fp4_repacked` -- a symbol this wheel's
`triton.experimental.gluon.language.amd._ops` does not export. The import
raises ImportError, and since SGLang's Triton JIT reaches
`triton.experimental.gluon` while compiling `write_req_to_token_pool_triton`
for the very first prefill batch, that ImportError kills the scheduler
process outright (SIGQUIT).

Wrapping only amd/__init__.py is not enough: Triton's JIT binder imports
`triton.experimental.gluon.amd.gfx1250` directly. The gfx1250/ package
directory shadows sibling gfx1250.py (which already defines
TensorDescriptor without the broken cdna5 ops). An empty except-pass
then fails with AttributeError: no attribute TensorDescriptor.

This patch wraps amd/__init__.py and rewrites gfx1250/__init__.py so a
failed cdna5 import falls back to loading TensorDescriptor from
gfx1250.py by file path. Idempotent; upgrades the earlier empty-except
wrap.
"""
from __future__ import annotations

from pathlib import Path

MARKER = "patched-by: patch_triton_gluon_gfx1250_optional.py"
FALLBACK_MARKER = "_gfx1250_td_fallback"

AMD_INIT_OLD = "from . import gfx1250\n"
AMD_INIT_NEW = (
    "try:\n"
    "    from . import gfx1250\n"
    f"except (ImportError, ModuleNotFoundError):  # {MARKER}\n"
    "    gfx1250 = None\n"
)

GFX1250_INIT = f"""try:
    from ..cdna5 import *  # noqa: F403
    from ..cdna5 import __all__ as __all__
except (ImportError, ModuleNotFoundError):  # {MARKER}
    import importlib.util
    from pathlib import Path

    sibling = Path(__file__).resolve().parent.parent / "gfx1250.py"
    spec = importlib.util.spec_from_file_location(
        "triton.experimental.gluon.amd.{FALLBACK_MARKER}",
        sibling,
    )
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)
    TensorDescriptor = _mod.TensorDescriptor
    __all__ = ["TensorDescriptor"]
"""


def _amd_root() -> Path | None:
    try:
        import triton  # noqa: PLC0415

        root = Path(triton.__file__).resolve().parent
    except Exception:
        return None
    path = root / "experimental" / "gluon" / "amd"
    return path if path.is_dir() else None


def _drop_pycache(path: Path) -> None:
    cache = path.parent / "__pycache__"
    if not cache.is_dir():
        return
    stem = path.stem
    for item in cache.glob(f"{stem}.*"):
        item.unlink(missing_ok=True)


def _patch_amd_init(path: Path) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already"
    if AMD_INIT_OLD not in text:
        return "unrecognized"
    path.write_text(text.replace(AMD_INIT_OLD, AMD_INIT_NEW, 1), encoding="utf-8")
    _drop_pycache(path)
    return "patched"


def _patch_gfx1250_init(path: Path) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8")
    if FALLBACK_MARKER in text:
        return "already"
    path.write_text(GFX1250_INIT if GFX1250_INIT.endswith("\n") else GFX1250_INIT + "\n", encoding="utf-8")
    _drop_pycache(path)
    return "upgraded" if MARKER in text else "patched"


def main() -> int:
    amd_root = _amd_root()
    if amd_root is None:
        print("[WARN] triton.experimental.gluon.amd not found; gfx1250 optional import skipped.")
        return 0
    status = _patch_amd_init((amd_root / "__init__.py").resolve())
    print(f"[INFO] {status} {(amd_root / '__init__.py').resolve()}")
    status = _patch_gfx1250_init((amd_root / "gfx1250" / "__init__.py").resolve())
    print(f"[INFO] {status} {(amd_root / 'gfx1250' / '__init__.py').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
