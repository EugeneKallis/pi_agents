# Job Search Agent — Conventions

Loaded by pi when this agent is launched with cwd = `agents/jobsearch/`. This
file travels with the agent — copy `agents/jobsearch/` to another project and
these conventions come along.

## What belongs here

- **Resume locations** the agent should read for context (e.g.
  `references/resume.md`, `references/resume-go.md`).
- **Job-board list** the agent should hit (and which to deprioritize).
- **Filtering rules** (location constraints, exclusion lists, etc.).
- **Output format** expectations (table columns, HTML report, etc.).

## Project context (this repo)

- Repo root `AGENTS.md` is also loaded (pi walks up from cwd). Anything in
  there applies here too — don't duplicate.
- `agents/jobsearch/SYSTEM.md` is the system prompt (role + behavior). It is
  loaded separately and is **not** a context file — keep it focused on
  identity/behavior, not conventions.

## Hard rules for this agent

- **US-based roles only** — exclude any non-US job, no exceptions.
- **Verify each posting is still accepting applicants** before listing.
- **Deliverables**: ranked table in chat **and** a styled HTML file at
  `search-results/<role>-<date>.html`, then `open` it.

## Reference files

- `references/resume.md` — KDB+ / q resume (used by `just jobsearch-kdb`)
- `references/resume-go.md` — Golang resume (used by `just jobsearch-go`)

<!-- Add more jobsearch-specific conventions below as needed. -->
