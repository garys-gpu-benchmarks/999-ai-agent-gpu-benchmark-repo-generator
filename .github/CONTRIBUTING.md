# Contributing

Thanks for considering a contribution to this template. It's a source template, not an application — most changes are to the rules an AI coding agent follows during generation, not to application code, so please read this before opening a PR.

## Before you start

1. Read [`AGENTS.md`](../AGENTS.md) — it defines the document priority order, coding conventions, and repository structure this template enforces on every generated repo. Changes here ripple into every workload repo generated afterward, so they should be deliberate.
2. Read [`TEMPLATE_README.md`](../docs/TEMPLATE_README.md) for the current version and recent change history.
3. Check [`ARCHITECTURE.md`](../docs/ARCHITECTURE.md) if you're not sure which file governs the behavior you want to change.

## Protected files

Some files are intentionally not meant to change casually:

- `scripts/lib/rocm_install.sh` — protected dispatcher. It sources `rocm_install_24_04.sh` or `rocm_install_26_04.sh`. Only change version pins or add installation tasks in the versioned files; don't restructure them without discussion first.
- `benchmark_specification.json` (in generated repos), `README.md`, `docs/AI_AGENT_INSTRUCTIONS.md`, and `*_TEMPLATE.md` files — these define the machine-checkable contract between the template and generated repos. Changing their structure means updating the matching JSON Schema in `schemas/` and the agent instructions embedded in the template.

## Making a change

1. Fork and branch from `main`.
2. Keep the change scoped — one concern per PR (a doc-contract change and a script fix should be separate PRs).
3. If you change a schema, update the corresponding `*_TEMPLATE.md` / `AGENTS.md` guidance in the same PR so they stay in sync.
4. Run the checks locally before opening the PR:
   ```bash
   shellcheck scripts/*.sh scripts/lib/*.sh
   ruff check --config config/pyproject.toml scripts/*.py
   python3 scripts/validate_template_inputs.py \
     --benchmark-specification benchmark_specification.json \
     --benchmark-schema schemas/benchmark_specification.schema.json \
     --allow-missing-benchmark-definition
   ```
5. Fill out the PR template — it includes a checklist matching what CI verifies.
6. Never commit real credentials, SSH key paths, hostnames, or IP addresses — use placeholders (`<REMOTE_HOST_IP>`, `<ssh_key>`, etc.) in any example command.

## Reporting issues

Use the issue templates under `.github/ISSUE_TEMPLATE/`. For anything security-sensitive (for example a credential or internal hostname), do not open a public issue. Follow [SECURITY.md](SECURITY.md).
