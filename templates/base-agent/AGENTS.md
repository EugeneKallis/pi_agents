# {{NAME}} Agent — Conventions

Loaded by pi when this agent is launched with cwd = `agents/{{NAME}}/`. This
file travels with the agent — copy `agents/{{NAME}}/` to another project and
these conventions come along.

## What belongs here

- Toolchain, commands, and style rules specific to this agent's domain.
- Anti-patterns to avoid in this agent's work.
- Reference files the agent should read (e.g. `references/...`).

## Layering (don't duplicate)

- This file = **conventions** (how to work in this domain).
- `SYSTEM.md` = **system prompt** (role + behavior). Loaded separately by pi
  via `systemPromptFile` in `agent.yaml`. Keep it focused on identity.
- `agent.yaml` = **identity & permissions** (id, name, model, allowed paths).

## Project context

- The repo-root `AGENTS.md` is also loaded when running inside this repo
  (pi walks up from cwd). Anything there applies here too.
- If this agent is copied to another project, the repo-root file won't be
  found — keep this per-agent file self-sufficient.

<!-- Replace this section with conventions specific to {{NAME}}. -->
