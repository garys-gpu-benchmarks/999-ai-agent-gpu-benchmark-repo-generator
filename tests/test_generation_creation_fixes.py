# File: tests/test_generation_creation_fixes.py
# Description: Regression checks for the creation failures from workloads 101-432.
# Execution: python -m unittest tests.test_generation_creation_fixes

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GenerationCreationFixes(unittest.TestCase):
    def test_folded_workload_command_survives_pyyaml(self) -> None:
        text = """
sweep:
  workload_commands:
    smoke: >-
      stress-ng --cpu 1 --timeout 2s --metrics-brief,stress-ng
      --cache 1 --timeout 2s --metrics-brief
"""
        raw = yaml.safe_load(text)["sweep"]["workload_commands"]["smoke"]
        self.assertIn("stress-ng --cpu", raw)
        self.assertIn("--cache", raw)
        harness = (ROOT / "scripts" / "materialize_generated_harness.py").read_text(encoding="utf-8")
        self.assertIn("import yaml", harness)

    def test_prerequisites_are_not_a_hardware_table(self) -> None:
        docs = _load(ROOT / "scripts" / "fill_generated_docs.py", "fill_docs_creation")
        rendered = docs.expand_generate(
            "[[GENERATE: Prerequisites and a mermaid diagram. Mention hardware config and GPU.]]",
            {"OS Version": "Ubuntu 24.04", "GPU Vendor": "AMD", "Python Version": "3.12", "Framework": "ROCm"},
        )
        self.assertIn("Prerequisites:", rendered)
        self.assertIn("Python 3.12;", rendered)
        self.assertNotIn("Python Python", rendered)
        self.assertIn("```mermaid", rendered)
        self.assertNotIn("| GPU Count |", rendered)
        labeled = docs.expand_generate(
            "[[GENERATE: Prerequisites and a mermaid diagram.]]",
            {"OS Version": "Ubuntu 24.04", "GPU Vendor": "AMD", "Python Version": "Python 3.12.3", "Framework": "ROCm"},
        )
        self.assertIn("Python 3.12.3;", labeled)
        self.assertNotIn("Python Python", labeled)

    def test_profile_kernel_replaces_workbook_kernel(self) -> None:
        docs = _load(ROOT / "scripts" / "fill_generated_docs.py", "fill_docs_kernel")
        rendered = docs.render_template(
            "Kernel {{Kernel Version}}",
            {
                "Kernel Version": "kernel 7.0.0",
                "Profile Parameter Values": json.dumps({"kernel_version": {"smoke": "6.8.0"}}),
            },
        )
        self.assertIn("kernel 6.8.0", rendered)
        self.assertNotIn("7.0.0", rendered)

    def test_doc_fields_are_synthesized(self) -> None:
        extract = _load(ROOT / "scripts" / "extract_benchmark_definition.py", "extract_creation")
        entries = extract._to_definition(
            type("Extraction", (), {
                "sheet_name": "Workload_Definitions",
                "header": ["Workload Number", "GPU Vendor", "Execution Description With Parameters"],
                "values": ["101", "AMD", "Run the smoke profile."],
            })(),
            Path("BenchmarkSpecDefinitions.xlsx"),
        )
        names = {item["field_name"] for item in entries}
        self.assertIn("Execution Summary (Run and Measure)", names)
        self.assertIn("nVidia Porting Instructions (Reference Only)", names)
        self.assertIn("Model Context Protocols", names)

    def test_locked_numeric_sweep_is_left_unchanged(self) -> None:
        config = _load(ROOT / "scripts" / "generate_benchmark_config.py", "bench_config_creation")
        existing = {"sweep": {"atol": 0.1, "rtol": "0.001"}}
        sweep = {"atol": "0.1", "rtol": 0.001}
        self.assertTrue(config._sweep_already_matches(existing, sweep))
        self.assertFalse(config._sweep_already_matches(existing, {"atol": "0.2"}))

    def test_newer_driver_cuda_is_not_a_mismatch(self) -> None:
        nvidia = _load(
            ROOT / "implementation_components" / "system-config-nvidia" / "files" / "scripts" / "collect_workload.py",
            "system_config_nvidia_creation",
        )
        self.assertTrue(nvidia.cuda_driver_supports("12.6", "13.2"))
        self.assertFalse(nvidia.cuda_driver_supports("13", "12.2"))

    def test_batch_row_uses_schema_fields(self) -> None:
        driver = _load(ROOT / "scripts" / "create_one_workload.py", "create_one_creation")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver.record(root, "101", "unknown", "failed", "2026-10-03T00:00:00Z", "2026-10-03T00:00:01Z", "doc tokens", return_code=1)
            row = json.loads((root / "batch_generation_manifest.json").read_text(encoding="utf-8"))["repositories"][0]
        self.assertEqual(row["return_code"], 1)
        self.assertEqual(row["reason"], "doc tokens")
        self.assertNotIn("notes", row)

    def test_runtime_clock_starts_after_setup(self) -> None:
        common = (ROOT / "scripts" / "lib" / "common.sh").read_text(encoding="utf-8")
        self.assertIn("mark_benchmark_measure_start()", common)
        self.assertIn('BENCHMARK_START_DATETIME="$(iso_utc_now)"', common)
        harness = (ROOT / "scripts" / "materialize_generated_harness.py").read_text(encoding="utf-8")
        setup_at = harness.index("bash scripts/ensure_setup.sh")
        mark_at = harness.index("mark_benchmark_measure_start", setup_at)
        begin_at = harness.rindex("begin_benchmark_run", 0, setup_at)
        self.assertLess(begin_at, setup_at)
        self.assertLess(setup_at, mark_at)
        runners = list((ROOT / "implementation_components").glob("*/files/run_benchmark.sh"))
        self.assertGreaterEqual(len(runners), 12)
        for path in runners:
            text = path.read_text(encoding="utf-8")
            if "scripts/ensure_setup.sh" not in text:
                continue
            setup_at = text.index("scripts/ensure_setup.sh")
            self.assertLess(text.rindex("begin_benchmark_run", 0, setup_at), setup_at, path.name)
            self.assertLess(setup_at, text.index("mark_benchmark_measure_start", setup_at), path.name)


if __name__ == "__main__":
    unittest.main()
