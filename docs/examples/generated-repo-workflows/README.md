# Generated-Repo Workflow Examples

These workflow sources are installed into every generated workload repository by `scripts/init_generated_repo.py`. They are not active in the generator repository because GitHub Actions only runs workflow files directly under `.github/workflows/`.

- `ci.yml.example` becomes `.github/workflows/ci.yml`. It runs host-safe lint/schema/syntax checks and `scripts/check_github_publish_ready.sh` on `ubuntu-latest`. It does not install GPU stacks, run generation-time `self_check_generated_repo.sh`, or execute the benchmark.
- `nightly.yml.example` becomes `.github/workflows/nightly.yml`. It targets a self-hosted runner labeled `gpu` and runs the smoke profile. Attach and review an appropriate GPU runner before enabling scheduled execution.
