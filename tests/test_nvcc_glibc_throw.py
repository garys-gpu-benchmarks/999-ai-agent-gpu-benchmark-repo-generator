#!/usr/bin/env python3
"""Fixtures for the repo-local rsqrt header repair."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "scripts" / "lib"
sys.path.insert(0, str(LIB))

import nvcc_glibc_throw as repair  # noqa: E402


SAMPLE = "\n".join(
    [
        "extern double rsqrt(double x);",
        "extern double rsqrt(double x) _NV_RSQRT_SPECIFIER;",
        "extern double rsqrt(double x) _NV_RSQRT_SPECIFIER __THROW;",
        " * rsqrt is mentioned in this comment",
        "__MATH_FUNCTIONS_DECL__ float rsqrt(const float a)",
        "__MATH_FUNCTIONS_DECL__ float rsqrt(const float a) __THROW",
        "__MATH_FUNCTIONS_DECL__ float rsqrt(const float a) _NV_RSQRT_SPECIFIER",
        "",
    ]
)


class RsqrtRepairTest(unittest.TestCase):
    def test_bare_declaration_is_unchanged_until_a_repair_is_required(self) -> None:
        text = "extern double rsqrt(double x);\n"
        self.assertEqual(repair.patch_text(text, apply_additions=False), text)

    def test_bare_declaration_gains_one_throw_when_additions_are_required(self) -> None:
        text = repair.patch_text(SAMPLE, apply_additions=True)
        self.assertIn("extern double rsqrt(double x) __THROW;", text)

    def test_specifier_without_throw_is_left_alone(self) -> None:
        text = repair.patch_text(SAMPLE, apply_additions=True)
        self.assertIn("extern double rsqrt(double x) _NV_RSQRT_SPECIFIER;", text)
        self.assertNotIn("extern double rsqrt(double x) _NV_RSQRT_SPECIFIER __THROW;", text)

    def test_doubled_specifier_is_repaired(self) -> None:
        once = repair.patch_text(SAMPLE, apply_additions=True)
        self.assertNotIn("_NV_RSQRT_SPECIFIER __THROW", once)

    def test_comment_is_unchanged(self) -> None:
        once = repair.patch_text(SAMPLE, apply_additions=True)
        self.assertIn(" * rsqrt is mentioned in this comment", once)

    def test_host_definition_gains_one_throw_only_without_a_specifier(self) -> None:
        once = repair.patch_text(SAMPLE, apply_additions=True)
        self.assertIn("__MATH_FUNCTIONS_DECL__ float rsqrt(const float a) __THROW", once)
        self.assertIn("__MATH_FUNCTIONS_DECL__ float rsqrt(const float a) _NV_RSQRT_SPECIFIER\n", once)
        self.assertNotIn("_NV_RSQRT_SPECIFIER __THROW", once)

    def test_second_run_matches_the_first(self) -> None:
        once = repair.patch_text(SAMPLE, apply_additions=True)
        twice = repair.patch_text(once, apply_additions=True)
        self.assertEqual(twice, once)

    def test_broad_appender_is_detected_and_the_shipped_helper_is_not_one(self) -> None:
        unsafe = 'if "rsqrt" in stripped and "__THROW" not in stripped and stripped.endswith(";"):\n'
        self.assertTrue(repair.broad_appender_present(unsafe))
        guarded = (
            'if "rsqrt" in stripped and "__THROW" not in stripped and "_NV_RSQRT_SPECIFIER" not in stripped '
            'and stripped.endswith(";"):\n'
        )
        self.assertFalse(repair.broad_appender_present(guarded))
        for name in ("nvcc_glibc_throw.py", "nvcc_glibc_throw.sh"):
            text = (LIB / name).read_text(encoding="utf-8")
            self.assertFalse(repair.broad_appender_present(text), name)

    def test_patch_refuses_the_installed_toolkit(self) -> None:
        with self.assertRaises(SystemExit):
            repair.assert_repo_local(Path("/usr/local/cuda/include/crt/math_functions.h"))


if __name__ == "__main__":
    unittest.main()
