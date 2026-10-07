# Publishing this workload repository to GitHub

This generated workload is designed to be published as its own independent GitHub repository.

GitHub repository name = local folder = `<Workload Number>-<Repo Name>` from `benchmark_specification.json` (for example `128-gpu-bench-amd-vllm-throughput-latency`). Keep that same leading workload number on GitHub. Do not publish the unprefixed `Repo Name` slug.

## Pre-publish check

Copy the generated workload to a publish tree (do not destroy the only generation copy), then run from that copy:

```bash
bash scripts/prepare_github_publish.sh --dry-run
bash scripts/prepare_github_publish.sh --apply --in-place --github-owner=YOUR_GITHUB_USER
bash scripts/check_github_publish_ready.sh --published
```

`prepare_github_publish.sh` removes generator leftovers (nested copies, template-only docs, generation-only scripts and schemas), converts CRLF to LF, replaces `<org>` clone URLs, and makes GitHub Actions clone-safe. It does not commit or push.

A finished workload normally no longer contains the nested `*_copy` generation workspace (it is removed once the workload passes). `--apply` refuses to run whenever a nested `*_copy` generation workspace (for example `ai-agent-gpu-benchmark-repo-generator_copy` or `TEMPLATE_00_*_copy`) is present in the current directory — copying the workload elsewhere does **not** remove it, since a plain `cp -a` copies that nested folder too. Pass `--in-place` so `--apply` can delete it. This is safe once you are standing in the publish-tree copy (that is the point of copying first); do not pass `--in-place` while standing in your only generation copy, since it permanently deletes that nested workspace there.

The `--published` readiness check verifies leftover files are gone, README relative links resolve, ignore rules are present, and host-safe syntax checks pass.

## Initialize and publish

Create the remote repository on GitHub using `<Workload Number>-<Repo Name>` (same as this folder), then run locally:

```bash
git init
git branch -M main
git add .
git status
git commit -m "Initial benchmark workload"
git remote add origin https://github.com/<OWNER>/<Workload Number>-<Repo Name>.git
git push -u origin main
```

Example: `gh repo create 128-gpu-bench-amd-vllm-throughput-latency --public --source=. --remote=origin --push`

Suggested GitHub description: `Workload <number>: <Repo Name>`. Add topics such as `amd`, `rocm`, `benchmark`, and the workload family (`perf`, `hipmemcpy`, `babelstream`, and so on).

Before committing, review `git status` carefully. The nested `TEMPLATE_*_copy/` generation workspace, runtime results, virtual environments, downloaded weights, logs, and credentials are intentionally excluded by `.gitignore` and must not be published.

## GitHub Actions

- `.github/workflows/ci.yml` performs host-safe linting, schema validation, structural validation, and publication-readiness checks on GitHub-hosted runners. It does not install GPU software or execute the benchmark.
- `.github/workflows/nightly.yml` is intended for a self-hosted runner labeled `gpu`. It is manual-only by default; add a schedule only after attaching an appropriate GPU runner and reviewing workload costs/dependencies.

## Required legal files

Keep the root `LICENSE` and `legal/NOTICE` with the repository.
