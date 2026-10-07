# .github/copilot-instructions.md

Use `AGENTS.md` as the canonical source of repository rules for all AI coding assistants.

## Priority

1. `benchmark_specification.json` (when present and schema-validated) is the single source of truth.
2. `README.md` provides the supported prompt forms; the attached
   `docs/AI_AGENT_INSTRUCTIONS.md` and `AGENTS.md` define generation workflow and coding contracts.
3. `.claude/CLAUDE.md` is agent-specific guidance and does not override `AGENTS.md`. Do not recreate a root `CLAUDE.md`.

## Copilot guidance

- Do not duplicate or reinterpret policy from this file.
- Follow protected-file and workflow constraints exactly as written in `AGENTS.md`.
- Keep changes minimal and workload-scoped.
- If any instruction appears to conflict, resolve using the document priority order in `AGENTS.md`.
