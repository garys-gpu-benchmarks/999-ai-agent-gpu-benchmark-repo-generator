# Publishing generated workloads to GitHub

This is the operator note for the five publish steps (complete README, strip leftovers, clone-safe CI, vendor compile fixes, Dependabot) and the dry-run. Read this file next week if you need the same instructions.

Companion files:

- Per-workload copy (installed into each generated repo as `docs/GITHUB_PUBLISH_WORKLOAD_REPO.md`): [`examples/generated-repo-github/GITHUB_PUBLISH_WORKLOAD_REPO.md`](examples/generated-repo-github/GITHUB_PUBLISH_WORKLOAD_REPO.md)
- Generator-vs-workload split: [`GITHUB_PUBLISH_WORKLOAD_REPO.md`](GITHUB_PUBLISH_WORKLOAD_REPO.md)
- Script: [`../scripts/prepare_github_publish.sh`](../scripts/prepare_github_publish.sh)
- History: [`CHANGELOG.md`](CHANGELOG.md) (2026-08-28 GitHub publish prep)

## Naming

Keep the existing local-directory convention and use that **same** name on GitHub. Do **not** rename to `WL-315-…` or drop the workload number from either the folder or the GitHub slug.

| What | Rule | Example |
|---|---|---|
| Local generation directory | `<Workload Number>-<Repo Name>` | `315-gpu-bench-amd-babelstream-hbm-bandwidth-ubu2604` |
| GitHub repository name | same as the local directory | `315-gpu-bench-amd-babelstream-hbm-bandwidth-ubu2604` |
| 101–132 / 201–232 | no `-ubu2604` suffix | `128_gpu-bench-amd-vllm-throughput-latency` |
| 301–332 / 401–432 | `Repo Name` ends with `-ubu2604` | `315_…-ubu2604`, `415_…-ubu2604` |

The workbook `Repo Name` field stays unprefixed (`gpu-bench-amd-vllm-throughput-latency`). The published GitHub name always adds the leading workload number.

## Four flavors

Each task exists as AMD/NVIDIA × Ubuntu 24.04/26.04. One generator (`init_generated_repo.py`, `common.sh`, README template, CI example, `prepare_github_publish.sh`) serves all four. Not every *runtime* pin applies to every flavor.

| Upgrade | AMD 24.04 (101–132) | NVIDIA 24.04 (201–232) | AMD 26.04 (301–332) | NVIDIA 26.04 (401–432) |
|---|---|---|---|---|
| 1. Complete README + Prerequisites + mermaid | yes | yes | yes | yes |
| 2. Do not copy `AGENTS.md` / `*TEMPLATE.md` onto the workload root | yes | yes | yes | yes |
| 3. Clone-safe GitHub Actions (no generation-time `self_check`) | yes | yes | yes | yes |
| 4a. `scripts/lib/hipcc_host_gcc.sh` sourced from `common.sh` | yes (no-op or GCC 13/14 pin if `hipcc` is used) | harmless (no `hipcc`; flags unused) | **required** for HIP `build.sh` (Clang 23 / GCC 16 misses `<cstdlib>`) | harmless |
| 4b. rocHPL `linpack-rochpl-amd` overlay (`size_t nn` + clamp N>=65536 to 32768, 16 repeats) | yes (120) | no (NVIDIA Linpack is a different tree) | yes (320) | no |
| 5. Dependabot (Actions weekly, pip monthly) | yes | yes | yes | yes |
| `prepare_github_publish.sh --dry-run` / `--apply` | yes | yes | yes | yes |

NVIDIA compile uses `nvcc` / CUDA, not `hipcc`. The hipcc helper is still copied into NVIDIA repos because `scripts/lib/` is shared; it does not change CUDA setup.

Ubuntu 26.04 README Prerequisites must name ROCm 7.14 (AMD) or CUDA 13.3 (NVIDIA). Ubuntu 24.04 README Prerequisites must name ROCm 7.2.1 or CUDA 12.8. The README template pulls those from the workbook fields; do not hard-code one OS into all four flavors.

## The five steps, then dry-run

### 1. Complete README

Every generated `README.md` must include Overview, Hardware Requirements, Installation, Running, and License — not a 26-line Quick Start stub. Include OS/GPU/runtime Prerequisites and a mermaid setup → run → parse diagram. `scripts/check_github_publish_ready.sh` fails stubs.

### 2. Strip generator leftovers

Do not publish `AGENTS.md`, `README_TEMPLATE.md`, `PRD_TEMPLATE.md`, `SPEC_TEMPLATE.md`, `.claude/`, `docs/GITHUB_PUBLISH_GENERATOR_OPERATIONS.md`, `scripts/self_check_generated_repo.sh`, `benchmark_actual.csv`, `benchmark_actual_excel.csv`, nested `*_copy/`, generator `docs/`, generation schemas, or generator scripts (`create_generated_repo.py`, and so on). `init_generated_repo.py` no longer copies the templates onto the root. `prepare_github_publish.sh --apply` deletes leftovers that are still present and warns if a surviving file still names a deleted path. Public README/SPEC kernel defaults and `PRD.md` Workload Number must match `config/benchmark_config.yaml` and `benchmark_specification.json`.

### 3. Clone-safe CI

Public `.github/workflows/ci.yml` must not run generation-time `scripts/self_check_generated_repo.sh` (that needs `*_copy`, `.venv`, and a prior smoke run). Host-safe lint, schema validate, and `check_github_publish_ready.sh` stay.

### 4. Vendor compile correctness

- AMD + `hipcc`: source `scripts/lib/hipcc_host_gcc.sh` or pass `--gcc-install-dir`. Required on Ubuntu 26.04.
- AMD rocHPL 120/320: keep the overlay; never `host_a(n * n)`.
- NVIDIA: leave CUDA / `nvcc` paths as they are.

### 5. Dependabot

`.github/dependabot.yml` is installed with the other generated GitHub files.

### Dry-run, then apply, on a **copy**

Do not `--apply` on the only generation tree (it deletes `*_copy/`).

```bash
# Preview one workload (safe)
cd <Workload Number>-<Repo Name>
bash scripts/prepare_github_publish.sh --dry-run

# Publish tree
mkdir -p /tmp/publish
cp -a <Workload Number>-<Repo Name> /tmp/publish/
cd /tmp/publish/<Workload Number>-<Repo Name>
bash scripts/prepare_github_publish.sh --apply --github-owner=YOUR_GITHUB_USER
bash scripts/check_github_publish_ready.sh --published
# then git init / add / status / commit / push to github.com/<owner>/<Workload Number>-<Repo Name>
# example: gh repo create 128_gpu-bench-amd-vllm-throughput-latency --public --source=. --remote=origin --push
```

`prepare_github_publish.sh` stages: prune leftovers → sanitize secrets/paths → normalize LF/gitignore/CI → validate (`check_github_publish_ready.sh --published`) → optional `git init`. The secret scan excludes its own source so a clean repo no longer fails on the script's grep patterns.

On the current 00_64 301–332 batch only, preview every repo without writing:

```bash
bash _generation_work/prepare_all_github_publish.sh
```

That wrapper lives in the 00_64 project (`TEMPLATE_00_64/_generation_work/`), not inside 00_65. For 101–132 / 201–232 / 401–432, run `prepare_github_publish.sh --dry-run` per repo.

`--apply --in-place` destroys the nested generation workspace. Use it only when you have another copy.

## In a week, start here

1. Open this file: `ai-agent-gpu-benchmark-repo-generator/docs/GITHUB_PUBLISH_GENERATOR_OPERATIONS.md`
2. Open [`CHANGELOG.md`](CHANGELOG.md) if you need the date of the change
3. The script header (`scripts/prepare_github_publish.sh --help`) repeats the flags
4. Each generated repo’s `docs/GITHUB_PUBLISH_WORKLOAD_REPO.md` repeats dry-run / apply / check
