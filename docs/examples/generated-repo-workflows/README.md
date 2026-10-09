# Generated-Repo Workflows (moved)

Workflow files for generated workload repositories are no longer copied from
this folder. Since TEMPLATE_00_103 they are rendered:

- `templates/workload/.github/workflows/ci.yml` and `gpu-smoke.yml` — the two
  thin callers that `scripts/init_generated_repo.py` renders into every
  workload, using `config/ci_contract.yaml` and the workload's
  `benchmark_specification.json` (vendor, OS label).
- `templates/shared-workflows/` — the reusable workflows those callers run,
  emitted once by `scripts/emit_shared_workflows.py` into the persistent
  `shared-workflows` repository and released with tags (`v1.0.0`, `v1`).

`ci.yml.example` and `nightly.yml.example` were removed. See the README section
"Continuous Integration" and `templates/shared-workflows/README.md`.
