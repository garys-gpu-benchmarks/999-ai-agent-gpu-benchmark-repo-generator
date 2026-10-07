#!/usr/bin/env python3
# File: tests/test_remove_template_copy.py
# Description: Fixture tests for scripts/remove_template_copy.py (post-generation removal of the nested *_copy/).
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from remove_template_copy import remove_template_copy  # noqa: E402

COPY = "ai-agent-gpu-benchmark-repo-generator_copy"


def _make_repo(root: Path, *, with_copy: bool = True) -> Path:
    repo = root / "101-sys-bench-amd-rocm-stack-validation-ubu2404"
    (repo / "results").mkdir(parents=True)
    (repo / "setup.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / "benchmark_specification.json").write_text("[]\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0",
        "workload_id": "101",
        "template_copy_path": COPY,
        "template_copy_sha256": "0" * 64,
        "implementation_components_discovered": ["system-config-amd"],
    }
    (repo / "results" / "generation_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (repo / "results" / "overlay_lock.json").write_text(
        json.dumps({"scripts/collect_workload.py": {"component_id": "rocm-health-amd", "sha256": "x"}}),
        encoding="utf-8",
    )
    if with_copy:
        copy = repo / COPY
        (copy / "scripts").mkdir(parents=True)
        (copy / "AGENTS.md").write_text("x\n", encoding="utf-8")
        (copy / "scripts" / "create_generated_repo.py").write_text("x\n", encoding="utf-8")
        gate_dir = copy / "implementation_components" / "rocm-health-amd"
        gate_dir.mkdir(parents=True)
        (gate_dir / "gate.json").write_text(json.dumps({"forbidden_cli": ["--bad"]}), encoding="utf-8")
        deep = copy / "implementation_components" / "sglang-prompt-response-nvidia" / "files" / "scripts" / "lib"
        deep.mkdir(parents=True)
        (deep / "sglang_nvidia_libs.sh").write_text("x\n", encoding="utf-8")
    return repo


def _run(repo: Path, **kwargs) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return remove_template_copy(repo, **kwargs)


class RemoveTemplateCopyTests(unittest.TestCase):
    def test_removes_copy_snapshots_gates_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            self.assertEqual(_run(repo), 0)
            self.assertFalse((repo / COPY).exists())
            gates = json.loads((repo / "results" / "component_gates.json").read_text(encoding="utf-8"))
            self.assertEqual(gates, {"rocm-health-amd": {"forbidden_cli": ["--bad"]}})
            manifest = json.loads((repo / "results" / "generation_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["template_copy_removed_at"].endswith("Z"))
            self.assertEqual(manifest["template_copy_path"], COPY)  # provenance kept
            self.assertEqual(manifest["template_copy_sha256"], "0" * 64)
            self.assertTrue((repo / "setup.sh").is_file())  # generated files untouched

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            self.assertEqual(_run(repo), 0)
            first = json.loads((repo / "results" / "generation_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(_run(repo), 0)
            second = json.loads((repo / "results" / "generation_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(first, second)

    def test_dry_run_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            self.assertEqual(_run(repo, dry_run=True), 0)
            self.assertTrue((repo / COPY).is_dir())
            manifest = json.loads((repo / "results" / "generation_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("template_copy_removed_at", manifest)

    def test_refuses_non_generated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_run(Path(tmp)), 1)

    def test_ignores_unrelated_copy_named_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp), with_copy=False)
            unrelated = repo / "data_copy"
            unrelated.mkdir()
            self.assertEqual(_run(repo), 0)
            self.assertTrue(unrelated.is_dir())

    def test_refuses_when_cwd_is_inside_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            old = os.getcwd()
            os.chdir(repo / COPY)
            try:
                self.assertEqual(_run(repo), 1)
            finally:
                os.chdir(old)
            self.assertTrue((repo / COPY).is_dir())

    def test_removes_read_only_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            locked = repo / COPY / "AGENTS.md"
            os.chmod(locked, 0o444)
            self.assertEqual(_run(repo), 0)
            self.assertFalse((repo / COPY).exists())


if __name__ == "__main__":
    unittest.main()
