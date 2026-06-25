# Coder Agent — Conventions

Loaded by pi when this agent is launched with cwd = `agents/coder/`. This file
travels with the agent — copy `agents/coder/` to another project and these
conventions come along.

## What belongs here

- **Language/toolchain defaults** specific to this agent (e.g. preferred
  formatter, test runner, package manager).
- **Code style rules** beyond what `SYSTEM.md` covers (the role/behavior).
- **Recurring commands** the agent should run after changes.
- **Anti-patterns** to avoid in this agent's domain.

## Project context (this repo)

- Repo root `AGENTS.md` is also loaded (pi walks up from cwd). Anything in
  there applies here too — don't duplicate.
- `agents/coder/SYSTEM.md` is the system prompt (role + behavior). It is
  loaded separately and is **not** a context file — keep it focused on
  identity/behavior, not conventions.

<!-- Add coder-specific conventions below. Examples: -->

<!-- - After editing Go files, run `gofmt -w <file>` and `go test ./...`. -->
<!-- - Prefer table-driven tests; never commit a test with `t.Skip()`. -->
<!-- - Use `pnpm test` before declaring a JS change done. -->
