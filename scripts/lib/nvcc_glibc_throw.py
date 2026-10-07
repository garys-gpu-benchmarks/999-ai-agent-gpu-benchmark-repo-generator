#!/usr/bin/env python3
# File: scripts/lib/nvcc_glibc_throw.py
# Description: Idempotent rsqrt exception-specifier repair for a repo-local
# copy of the CUDA crt headers. This module never writes under /usr/local/cuda.
"""Patch rsqrt declarations without touching the installed CUDA toolkit."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_UNSAFE_APPEND = re.compile(
    r'if\s+"rsqrt"\s+in\s+stripped\s+and\s+"__THROW"\s+not\s+in\s+stripped\s+and\s+stripped\.endswith\(";"\)\s*:'
)


def is_comment_line(stripped: str) -> bool:
    text = stripped.lstrip()
    return text.startswith(("//", "/*", "*"))


def has_rsqrt_specifier(stripped: str) -> bool:
    return "_NV_RSQRT_SPECIFIER" in stripped or "noexcept" in stripped


def _split_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _strip_trailing_throw(stripped: str) -> str:
    semicolon = stripped.endswith(";")
    body = stripped[:-1].rstrip() if semicolon else stripped.rstrip()
    token = "__THROW"
    if body.endswith(token):
        body = body[: -len(token)].rstrip()
    if semicolon:
        body += ";"
    return body


def patch_line(line: str, *, apply_additions: bool) -> str:
    """Repair one line. Additions run only when the caller asked for them.

    A comment that mentions rsqrt is unchanged. A line that already has
    _NV_RSQRT_SPECIFIER or noexcept loses a trailing __THROW. A declaration
    with no specifier gains one __THROW only when apply_additions is true.
    """
    body, newline = _split_newline(line)
    if "rsqrt" not in body or is_comment_line(body):
        return line
    if has_rsqrt_specifier(body) and "__THROW" in body:
        return _strip_trailing_throw(body) + newline
    if not apply_additions or has_rsqrt_specifier(body) or "__THROW" in body:
        return line
    core = body.rstrip()
    if core.endswith(";"):
        return core[:-1].rstrip() + " __THROW;" + newline
    if (
        core.startswith("__MATH_FUNCTIONS_DECL__")
        and "rsqrt(" in core
        and not core.endswith("{")
    ):
        return core + " __THROW" + newline
    return line


def patch_text(text: str, *, apply_additions: bool) -> str:
    return "".join(patch_line(line, apply_additions=apply_additions) for line in text.splitlines(keepends=True))


def broad_appender_present(text: str) -> bool:
    """True when a conditional appends __THROW to every rsqrt line that lacks it.

    The safe 00_89take2 helper also contains the words "__THROW" not in stripped
    and still checks _NV_RSQRT_SPECIFIER. This matches only the unguarded form.
    """
    for match in _UNSAFE_APPEND.finditer(text):
        window = text[match.start() : match.start() + 240]
        if "_NV_RSQRT_SPECIFIER" not in window:
            return True
    return False


def assert_repo_local(path: Path) -> None:
    resolved = path.resolve().as_posix()
    if resolved == "/usr/local/cuda" or "/usr/local/cuda/" in resolved or resolved.startswith("/usr/local/cuda"):
        raise SystemExit(f"[FAIL] refusing to write CUDA toolkit path {resolved}")


def write_patched_copy(src: Path, dest: Path, *, apply_additions: bool) -> None:
    assert_repo_local(dest)
    if src.resolve() == dest.resolve():
        raise SystemExit(f"[FAIL] refusing to edit {src} in place")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(patch_text(src.read_text(encoding="utf-8", errors="replace"), apply_additions=apply_additions), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    if len(argv) != 5 or argv[0] != "patch":
        print("usage: nvcc_glibc_throw.py patch SRC_H SRC_HPP DEST_H DEST_HPP", file=sys.stderr)
        return 2
    src_h, src_hpp, dest_h, dest_hpp = (Path(item) for item in argv[1:])
    if not src_h.is_file():
        print(f"[FAIL] missing header {src_h}", file=sys.stderr)
        return 1
    write_patched_copy(src_h, dest_h, apply_additions=True)
    if str(src_hpp) not in {"", "-"} and src_hpp.is_file():
        write_patched_copy(src_hpp, dest_hpp, apply_additions=True)
    print(f"[PASS] wrote repo-local headers {dest_h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
