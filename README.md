[![Template CI](https://github.com/garymichaelbass/ai-agent-gpu-benchmark-repo-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/garymichaelbass/ai-agent-gpu-benchmark-repo-generator/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

# AI Coding Agent Spec-Driven GPU Benchmark Repo Generator

A template-driven generation framework that enables AI coding agents to autonomously build, validate, and document GPU benchmark repositories. It converts single-row workload definitions into complete, standardized, execution-ready codebases with zero manual scaffolding required. Included workload domains span GPU compute, LLM serving, memory and data transfer, CPU and system performance, end-to-end pipelines, and validation/correctness testing.

Instead of manually assembling setup scripts, SPEC files, PRDs, CI workflows, and parsing logic for each workload, the agent consumes this template and executes a strict multi‑phase workflow defined in [`AGENTS.md`](AGENTS.md) and [`docs/generation-workflow.md`](docs/generation-workflow.md). The result is a repository that installs the runtime stack, validates the environment, and executes a smoke test, producing reliable, reproducible benchmark repos at scale. This transforms benchmark creation from a manual, error‑prone process into a scalable, automated pipeline.

### AI-Agent GPU Benchmark Repository Generator — High-Level Capabilities

#### Repository Generation & Scale

- **Single Excel Row → Full Repository Generation** — Generates an entire benchmark repo from one spreadsheet row plus one AI agent prompt.
- **Optimized for AI Coding Agents** — Designed for Claude Code, Copilot, Cursor, and similar agents to ensure consistent output.
- **Starter Benchmark Library** — `BenchmarkSpecDefinitions.xlsx` defines 32 AMD Ubuntu 24.04, 32 NVIDIA Ubuntu 24.04, 32 AMD Ubuntu 26.04, and 32 NVIDIA Ubuntu 26.04 workloads ready to generate. Workloads 101–132 and 201–232 describe the `TEMPLATE_00_72` collectors. `implementation_components/` supplies reusable implementation assets selected from `config/implementation_packs.yaml` by Workload Number and GPU Vendor; users do not select components in the workbook. Generated repositories are created as siblings of this generator, not as pre-built folders in this tree.
- **Scales to Hundreds of Benchmarks** — A user can add rows to Excel and generate dozens or hundreds of repositories without manual coding.
- **Batch Mode Generation** — Supports lists and ranges (e.g., "101 through 110") to generate multiple repositories from one prompt.
- **Six Execution Domains** — GPU Compute, LLM Serving, Memory/Transfer, CPU/System, End-to-End Pipeline, Validation/Correctness.

#### Setup & Execution

- **Quick Start Guide Included** — Provides a streamlined "Generate Your First Benchmark Repository in Ten Minutes" document.
- **Ready-to-Run Local Repositories** — Delivers every file and directory necessary to run the benchmark end-to-end on the target machine.
- **Effortless Setup & Execution** — Install with `bash setup.sh --assume-yes`. A bare `bash run_benchmark.sh` is smoke. Pass `--baseline` or `--extended` for the longer profiles.
- **Reboot-Resilient Install** — A single end-to-end install command that saves state and resumes across reboots.
- **Safe, Idempotent Setup Scripts** — Setup scripts can be rerun without corrupting state.
- **Flexible Benchmark Profiles** — Supports smoke, baseline, and extended runs via CLI flags.
- **Supports Local + Remote Development** — Supports integrating a remote Linux VM which can be used for code development and validation.
- **Isolated Python Environments** — Each generated repo uses its own Python venv.

#### Repository Structure & AI-Agent Guidance

- **Rich Template Library** — Includes templates for PRD, README, SPEC, scripts, scaffolding, CI workflows, and GitHub files.
- **Detailed Reference Materials** — Generates README, PRD, SPEC, ARCHITECTURE documents customized per benchmark.
- **Consistent Repository Structure** — Every generated repo includes `src/`, `config/`, `scripts/`, `schemas/`, `tests/`, and `results/`.
- **Local Template Copy During Generation** — `create_generated_repo.py` materializes a nested `ai-agent-gpu-benchmark-repo-generator_copy/` while a workload is generated. `create_one_workload.py` removes it once the workload passes (`--keep-template-copy` keeps it); for other paths run `python3 scripts/remove_template_copy.py --repo-root <repo>`. Finished repositories therefore do not carry the copy, whose deep paths exceed the Windows 260-character limit. While it exists, the tree is gitignored and must not be published to GitHub.

#### Results & Observability

- **Rich CLI Details Mode** — Displays workload name, execution summary, framework, metrics, runtime language, and execution domain.
- **Timestamped Run Output Directory** — Saves results, commands, metrics, system info, and exit status per run.
- **Environment Logging** — Creates a log of installed software components and versions.
- **Excel-sourced HW/SW Inventory Capture** — Executes a post-run HW/SW inventory collection script generated from Excel command definitions.
- **Runtime Ledger** — Generates a per‑run one-line CSV ledger entry summarizing workload identity, runtime, metrics, and parameters.
- **SQLite Result Storage** — Stores parsed benchmark results in a portable database.
- **Replayable Command Log** — Records all executed benchmark commands for audit and reproducibility.

#### Validation & Quality Gates

- **Self-Validation via GitHub Actions** — Lints scripts, validates schemas, and verifies generator structure on every change.
- **Generated Repos Include CI Workflows** — Each repo includes `ci.yml.example` and `nightly.yml.example`.
- **Meets GitHub Community Standards** — LICENSE, CODE_OF_CONDUCT.md, CONTRIBUTING.md, SECURITY.md, issue templates, PR template.
- **Strict Submission Checklist** — Implements `SUBMISSION_CHECKLIST.md` as a completion gate.
- **Agent-Executed Completion Verification** — Requires passing every checklist item before declaring a repo complete.

## Requirements

- An AI coding agent capable of following multi-file, multi-phase written instructions (agent-agnostics rules defined in `AGENTS.md`).
- Python 3.12+ locally, for the extraction/validation scripts. From this directory: `pip install -e "config[dev]"` (or `pip install jsonschema openpyxl PyYAML`).
- `BenchmarkSpecDefinitions.xlsx` populated with your workload matrix (a starter copy is included). Author smoke/baseline/extended values on the `Parameters_SmokeBaselineExtend` sheet; `Workload_Definitions` command columns are generated from that sheet. Do not extract historical `_1_0` / `_1_1` copies; those belong in `archive/` only.
- A local or remote Ubuntu 24.04 or Ubuntu 26.04 target with an MI300X or an H100 GPU, for workloads that need real hardware to install/run against.

## Generate Your First Benchmark Repository in Ten Minutes

If you are starting from scratch and need an AMD Developer Cloud account and GPU droplet, first follow the [`AMD Developer Cloud Getting Started Guide`](docs/amd-developer-cloud-getting-started.md).

Steps to generate your first benchmark repository:

1. **Prerequisites**:
   - Git
   - An AI Coding Agent
   - An Ubuntu target for benchmark execution
   - Optional remote Ubuntu validation VM

2. **Set up your project root**:

   ```text
   mkdir my_project_root && cd my_project_root
   ```

3. **Clone the repository generator into project root directory**:

   ```text
   git clone https://github.com/garymichaelbass/ai-agent-gpu-benchmark-repo-generator.git
   cd ai-agent-gpu-benchmark-repo-generator
   ```

4. **(OPTIONAL) Create a remote VM when the prompt includes an IP address**: On a VM provider (e.g., DigitalOcean, RunPod, AWS, Azure, or GCP), create a freshly installed Ubuntu server, configure access, and include its IPv4 address in the SSH command in the prompt. An IPv4 address makes remote validation mandatory: the AI Coding Agent must load every generated repository onto that VM, install it there, and run its self-check and smoke benchmark there before completion. This VM is not used by the generated repository at runtime.

5. **Choose workloads and submit a prompt**: Open `BenchmarkSpecDefinitions.xlsx`, select one or more workload numbers, attach `ai-agent-gpu-benchmark-repo-generator/docs/AI_AGENT_INSTRUCTIONS.md` to your AI Coding Agent, and submit one of the supported prompt forms below.

   ```text
   @ai-agent-gpu-benchmark-repo-generator/docs/AI_AGENT_INSTRUCTIONS.md
   Generate workload <WORKLOAD_NUMBER>.
   Remotely access Ubuntu VM with `ssh -i /path/to/.ssh/<amd_ssh_key> root@<REMOTE_HOST_IP>`
   ```

  Example 1: one workload with mandatory remote validation:

   ```text
   @ai-agent-gpu-benchmark-repo-generator/docs/AI_AGENT_INSTRUCTIONS.md
   Generate workload 101.
   Remotely access Ubuntu VM with `ssh -i /path/to/.ssh/<amd_ssh_key> root@<REMOTE_HOST_IP>`
   ```

   Example 2: one workload without remote validation:

   ```text
   @ai-agent-gpu-benchmark-repo-generator/docs/AI_AGENT_INSTRUCTIONS.md
   Generate workload 101.
   ```

   Example 3: multiple workloads:

   ```text
   @ai-agent-gpu-benchmark-repo-generator/docs/AI_AGENT_INSTRUCTIONS.md
   Generate workloads 121, 122.
   ```

   Example 4: inclusive workload range:

   ```text
   @ai-agent-gpu-benchmark-repo-generator/docs/AI_AGENT_INSTRUCTIONS.md
   Generate workloads 101 through 104.
   ```

   Workload lists may also use `and`, hyphen ranges, `to` ranges, or `ALL`. The agent validates the requested workloads against the workbook before generation.

6. **Agent records the submitted prompt and generates repositories sequentially**: The agent validates the selected workloads, creates one `AI_AGENT_PROMPT_SUBMITTED_<WORKLOADS>_<UTC_TIMESTAMP>.md` in `my_project_root/`, then creates and fully finishes each sibling repository one at a time with `create_generated_repo.py --workload <N>` before creating the next directory. If the supplied SSH command contains an IPv4 address, "fully finishes" includes loading the repository onto that VM, installing it there, and running its self-check and smoke benchmark there. 

7. **Execute the output**: Once completed, copy the repository (ie, `101_sys-bench-rocm-stack-validation/`) to the Ubuntu target for benchmark execution. Enter the generated repository and run:

    ```bash
    bash setup.sh
    bash run_benchmark.sh --help
    bash run_benchmark.sh --profile smoke --validate
    ```

See [`docs/AI_AGENT_INSTRUCTIONS.md`](docs/AI_AGENT_INSTRUCTIONS.md) for the authoritative agent instructions and [`docs/generation-workflow.md`](docs/generation-workflow.md) for what the agent does at each phase.

The shared parameter catalog at `config/workload_parameters.yaml` is generated from `BenchmarkSpecDefinitions.xlsx`; run `python3 scripts/generate_workload_parameters.py --check` to validate active parameter names and `python3 scripts/verify_generation_workflow.py` for the deterministic workflow checks.

## Why this exists

Generating benchmark repos by hand doesn't scale past a handful of workloads, and letting an agent freelance the structure produces inconsistent repos that are hard to CI, diff, or maintain. This template fixes both problems by giving the agent:

- a single source of truth (`benchmark_specification.json`, extracted from `BenchmarkSpecDefinitions.xlsx`) that wins over every other file on conflict,
- a strict document read-order (see [`AGENTS.md`](AGENTS.md)) so agents from different vendors behave consistently,
- machine-checkable contracts (JSON Schemas under [`schemas/`](schemas)) instead of prose-only conventions,
- a reboot-safe ROCm install pattern for workloads that require a kernel driver install and reboot mid-setup, and
- a submission checklist the agent runs before declaring a generated repo complete.

## What this repository generates

For each selected workload, the agent creates a sibling repository under `my_project_root` using the workload number and exact repository name from the validated benchmark definition:

```text
my_project_root/
├── ai-agent-gpu-benchmark-repo-generator/
├── AI_AGENT_PROMPT_SUBMITTED_101_20260805_080015.md
└── 101_sys-bench-rocm-stack-validation/
    ├── benchmark_specification.json
    ├── PRD.md
    ├── SPEC.md
    ├── README.md
    ├── setup.sh
    ├── run_benchmark.sh
    ├── scripts/
    ├── config/
    ├── results/
    └── ai-agent-gpu-benchmark-repo-generator_copy/   # during generation only; removed once the workload passes
```

## Limitations and prerequisites

- An AI Coding Agent capable of following multi-file, multi-phase instructions.
- Python 3.12 or newer for local extraction and validation tooling.
- A populated `BenchmarkSpecDefinitions.xlsx` workload matrix.
- Ubuntu 24.04 (workloads 101–232) or Ubuntu 26.04 (workloads 301–332) for benchmark installation and execution.
- AMD Instinct MI300X hardware and a compatible ROCm installation for GPU workloads.
- A local or cloud-hosted validation machine; cloud providers may charge for compute, storage, networking, and related services.
- The generated repositories are local-runtime repositories. When the prompt contains an IPv4 address, the specified remote VM is mandatory for generation-time loading, installation, self-check, and smoke-test validation.

## Security

Keep private keys, passwords, API tokens, SSH commands containing secrets, and other credentials outside this repository and outside submitted-prompt artifacts. Use placeholders in prompt files and provide credentials only through the secure mechanism supported by the AI Coding Agent or validation environment. Never commit credentials to Git.

## Repository layout

| Path | Purpose |
|---|---|
| `AGENTS.md`, `.claude/CLAUDE.md`, `.github/copilot-instructions.md` | Cross-agent and agent-specific operating rules, in priority order |
| `.github/CODE_OF_CONDUCT.md`, `.github/CONTRIBUTING.md` | Community standards and contribution guidelines |
| `docs/AI_AGENT_INSTRUCTIONS.md` | Detailed generation workflow and agent operating instructions |
| `templates/PRD_TEMPLATE.md`, `templates/SPEC_TEMPLATE.md`, `templates/README_TEMPLATE.md` | Source templates copied to the generated repo root |
| `docs/` | Phase-by-phase generation workflow and machine-checkable contracts |
| `schemas/` | JSON Schemas that generated artifacts must validate against |
| `scripts/` | Generation, validation, and smoke-check tooling |
| `config/` | The benchmark matrix workbook, machine definitions, hardware profiles |
| `implementation_components/` | Reusable capability-oriented implementation components automatically discovered from the benchmark specification |
| `docs/SUBMISSION_CHECKLIST.md` | Completion gate the agent runs before reporting a generated repo done |

For the full documentation map, see [`ARCHITECTURE.md`](docs/ARCHITECTURE.md). For dated release notes, see [`docs/CHANGELOG.md`](docs/CHANGELOG.md). For template-maintainer notes, see [`TEMPLATE_README.md`](docs/TEMPLATE_README.md).

## Contributing

See [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## License

The Apache 2.0 license is in root `LICENSE`; project notices are in `legal/NOTICE`.


Apache License 2.0 — see [`LICENSE`](LICENSE).
