# GitHub publication model

Operator steps for publishing a generated workload (README, leftovers, clone-safe CI, hipcc/rocHPL, Dependabot, dry-run), four-flavor mapping, and naming: **[`GITHUB_PUBLISH_GENERATOR_OPERATIONS.md`](GITHUB_PUBLISH_GENERATOR_OPERATIONS.md)**.

The generator repository and every completed generated workload are intended to be published as **separate GitHub repositories**. Do not publish the enclosing `TEMPLATE_00_*` parent directory, live VM trees, runtime logs, result archives, or the nested `TEMPLATE_*_copy/` generation workspace.

## Generator repository

Before publishing the generator:

1. Keep root `LICENSE` and `legal/NOTICE`.
2. Keep `.gitattributes` and `.gitignore` intact.
3. Do not publish generated workload directories, `RESULTS/`, `runtime_ledger.csv`, `*.zip`, operator logs, credentials, downloaded weights, or live machine inventories.
4. Use the generator's `.github/workflows/ci.yml`; it validates generator contracts and templates, not GPU workloads.

## Generated workload repositories

`scripts/init_generated_repo.py` installs workload-specific GitHub assets rather than copying generator-specific GitHub guidance:

- `.github/CONTRIBUTING.md`
- `.github/SECURITY.md`
- `.github/CODE_OF_CONDUCT.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/`
- `.github/copilot-instructions.md`
- `.github/workflows/ci.yml`
- `.github/workflows/nightly.yml`
- `docs/GITHUB_PUBLISH_WORKLOAD_REPO.md` (workload-specific publication instructions)
- `scripts/check_github_publish_ready.sh`

The generated `ci.yml` performs host-safe checks only and does not install GPU stacks or execute the benchmark. The optional GPU workflow targets a self-hosted runner labeled `gpu` and is manual-only by default; scheduling is an explicit repository-owner opt-in.

A completed workload must pass generation-time:

```bash
bash scripts/check_github_publish_ready.sh
bash scripts/self_check_generated_repo.sh
```

Before pushing a public clone, copy the workload to a publish tree and run:

```bash
bash scripts/prepare_github_publish.sh --apply --github-owner=YOUR_GITHUB_USER
bash scripts/check_github_publish_ready.sh --published
```

`prepare_github_publish.sh` now: excludes itself from the secret scan, deletes `.claude/`, `docs/GITHUB_PUBLISH_GENERATOR_OPERATIONS.md`, and `scripts/self_check_generated_repo.sh`, strips the dead `docs/repository-template.md` README line, replaces `<org>` clone URLs, and re-runs the published-clone gate. Do not run `--apply` on the only generation copy unless you pass `--in-place`. GitHub-hosted CI must not invoke generation-time `self_check_generated_repo.sh` (it requires the nested template copy, `.venv`, and a prior smoke run).

The workload repository must contain a finalized `README.md`, root `LICENSE`, `legal/NOTICE`, `benchmark_specification.json`, setup/run scripts, configuration, schemas needed by its checks, and GitHub community/CI files. It must not depend on `TEMPLATE_*_copy/`; that local generation workspace is gitignored and must never be committed.

## Never publish

- Credentials, SSH keys, access tokens, cookies, or `.env` files
- Private hostnames/IP addresses or cloud credentials
- Downloaded model weights or licensed/proprietary datasets
- Runtime inventories containing sensitive machine identifiers
- `results/raw/*` except intended placeholders/manifest files
- `runtime_ledger.csv`, `RESULTS/`, `*.zip`, virtual environments, build products, or operator logs
