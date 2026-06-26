# PLAN — Job Search Crew (CrewAI)

Mirror the `agents/jobsearch/` pi agent as a CrewAI crew under
`crewai-jobs/src/crewai_jobs/crews/jobsearch/`, adding Telegram/Discord
notification.

## Context

The existing pi jobsearch agent at `agents/jobsearch/` is a single
interactive agent that:

1. Reads a resume (`references/resume.md`) — KDB+, Golang, and Python profiles
2. Searches 5+ job boards via `web_search` with site-specific queries
3. Deduplicates against `seen-jobs.json` via a `track_jobs` tool
4. Verifies postings are still accepting applicants via `fetch_content`
5. Presents a ranked table with: Title, Company, Location, Salary, Fit, Link
6. Saves results to `search-results/<role>-<date>.md` and `.html`, opens browser
7. Tracks seen jobs so they never repeat

We want the **same workflow** running headless in CrewAI, callable from
n8n via SSH, with results delivered via Telegram (or Discord webhook
fallback) instead of opening a browser.

## Approach

### Architecture: 2-agent sequential crew

```
┌─────────────────┐    raw listings    ┌──────────────────┐
│  Researcher     │ ──fit-analysis──▶  │ Report Writer     │
│  + search tool  │                    │  (no tools needed)│
│  + verifier     │                    │                   │
│  + tracker      │                    │  formats md + html│
│  + resume loader│                    │  + JSON for n8n   │
└─────────────────┘                    └────────┬──────────┘
                                                 │
                                      ┌──────────▼──────────┐
                                      │  n8n SSH node parses│
                                      │  JSON → Telegram /  │
                                      │  Discord native nodes│
                                      └─────────────────────┘
```

- **Researcher agent** — searches boards, verifies posts, checks fit,
  deduplicates, produces a ranked table with analysis. Owns 4 tools.
- **Report Writer agent** — formats the table as markdown + HTML, saves
  files, and appends a JSON block with separate `telegram` and `discord`
  messages (platform-appropriate formatting). **No tools** — just writes.

**Why no NotifierTool:** n8n already has native Telegram and Discord
nodes. The crew's job is to produce the *content*; n8n's job is to
*deliver* it. The report writer outputs a structured JSON block that
n8n's SSH node captures, parses, and routes to the right channels — no
bot tokens needed in crewai's .env.

### Resume handling

Pass `--resume` CLI arg (default: `../agents/jobsearch/references/resume.md`).
A `ResumeLoaderTool` reads the file and returns relevant sections for the
given role (`kdb`, `go`, or `python`). The researcher calls it at the start
of every run.

### Seen jobs tracking

`JobTrackerTool` reads/writes `crewai-jobs/data/seen-jobs.json` — a
simple JSON array of URLs. Separate file from the pi agent's
`references/seen-jobs.json` (avoids cross-contamination between pi and
crewai runs).

### Search backend

Use the `duckduckgo-search` Python library (free, no API key) to perform
site-specific queries across job boards. The researcher agent calls
`JobSearchTool` once per board, or combines queries into a single call
with broad filters.

### JSON output for n8n messaging

Instead of a NotifierTool, the report writer produces a **JSON block** at
the end of its output. The block has separate messages formatted for each
platform — Telegrams's 4096-char limit with MarkdownV2, Discord's 2000-char
limit with optional embeds.

```json
{
  "telegram": {
    "text": "🔥 *3 new KDB+ roles found*\n\n1. Senior KDB Developer @ Acme Corp…",
    "parse_mode": "MarkdownV2"
  },
  "discord": {
    "content": "## 3 new KDB+ roles found\n\n…",
    "embeds": [
      {"title": "Senior KDB Developer @ Acme Corp", "description": "…", "url": "…"}
    ]
  },
  "summary": "3 new KDB+ roles: Acme Corp, FinTech Inc, DataStream LLC",
  "html_file": "output/jobsearch/report-kdb-2026-06-25.html"
}
```

- **`--quiet` mode** prints *only* this JSON block to stdout — so n8n's
  SSH node can `JSON.parse()` it and route to Telegram/Discord nodes.
- **Verbose mode** prints the full markdown report, then the JSON block.
- The `telegram` field uses MarkdownV2 (escape `*_[]()~>#+-=|{}.!` ).
- The `discord` field has a plain `content` string + up to 10 embed objects
  for rich cards.
- No bot tokens or webhook URLs live in crewai — n8n owns all credentials.
  This is cleaner and safer.

## Files to create / modify

### New files

| File | Purpose |
|------|---------|
| `crewai-jobs/src/crewai_jobs/tools/job_search.py` | `JobSearchTool` — DuckDuckGo job board search |
| `crewai-jobs/src/crewai_jobs/tools/job_verifier.py` | `JobVerifierTool` — fetch URL, check if post is still active |
| `crewai-jobs/src/crewai_jobs/tools/job_tracker.py` | `JobTrackerTool` — read/write seen jobs JSON |
| `crewai-jobs/src/crewai_jobs/tools/resume_loader.py` | `ResumeLoaderTool` — read resume.md, return role-specific section |

| `crewai-jobs/src/crewai_jobs/crews/jobsearch/__init__.py` | Exports `JobSearchCrew` |
| `crewai-jobs/src/crewai_jobs/crews/jobsearch/crew.py` | `@CrewBase` assembly + `build_llm()` |
| `crewai-jobs/src/crewai_jobs/crews/jobsearch/config/agents.yaml` | Researcher + Report Writer agent defs |
| `crewai-jobs/src/crewai_jobs/crews/jobsearch/config/tasks.yaml` | Research + Write tasks (w/ JSON output spec) |
| `crewai-jobs/data/.gitkeep` | Placeholder for seen-jobs.json |

### Modified files

| File | Change |
|------|--------|
| `crewai-jobs/src/crewai_jobs/cli.py` | Register `jobsearch` subcommand |
| `crewai-jobs/src/crewai_jobs/tools/__init__.py` | Export new tools |
| `crewai-jobs/pyproject.toml` | Add `duckduckgo-search` dep + package-data for jobsearch crew yamls |
| `crewai-jobs/README.md` | Add jobsearch section to "What's here" + model table |


## Tool designs

### JobSearchTool
- **BaseTool** with Pydantic `args_schema`
- `_run(query, role="kdb", limit=10)` → uses `duckduckgo_search.DDGS().text()`
- Role is one of `kdb`, `go`, `python` — appends role-specific filters (US, remote, salary)
- Returns numbered text list: title, snippet, URL
- De-duplicates by URL

### JobVerifierTool
- `_run(url)` → fetches the page with `requests`, checks for signs the
  posting is still active: "apply now", "posted X days ago", no "filled"
  or "no longer accepting" language
- Returns a structured verdict: "ACTIVE", "UNCERTAIN", or "CLOSED" +
  evidence snippet

### JobTrackerTool
- `_run(action="read" | "add", urls=[])` → reads/writes
  `data/seen-jobs.json`
- Returns list of previously seen URLs on read; confirms write on add

### ResumeLoaderTool
- `_run(path, role="kdb")` → reads the resume file, returns the relevant
  profile section (KDB+, Golang, or Python) + the "Quick Reference for Agent"
  section (search keywords, experience level, preferences)

## Agent definitions (config/agents.yaml)

### researcher
- **role:** Senior Job Market Researcher
- **goal:** Find the best matching job listings for the given role,
  verify they are still accepting applicants, analyze fit against the
  resume, and rank the top candidates
- **tools:** ResumeLoaderTool, JobSearchTool, JobTrackerTool, JobVerifierTool
- **backstory:** veteran technical recruiter with deep knowledge of
  KDB+/q and Golang markets. Knows which boards have genuine listings
  and how to filter out ghost posts

### report_writer
- **role:** Job Search Report Writer
- **goal:** Take the researcher's ranked job list, format it as a
  professional markdown report with an HTML counterpart, and append a
  JSON block with separate Telegram and Discord messages ready for n8n
- **tools:** (none — writes markdown + HTML + JSON)
- **backstory:** precise technical writer who formats job search
  results into clean, scannable reports. Knows which details matter
  (salary, location fit, resume alignment), always includes clickable
  apply links, and appends a structured JSON block with platform-tailored
  messages for n8n's native Telegram and Discord nodes

## Task definitions (config/tasks.yaml)

### research_task
- **agent:** researcher
- **description:** Load the resume for {role}, search 5+ job boards
  with site-specific queries, deduplicate against seen jobs, verify
  each promising posting is still active, analyze fit against resume
  skills, produce a ranked top-{limit} list
- **expected_output:** Ranked table with columns: Title, Company,
  Location, Salary, Fit, Apply Link. Each entry gets a 2-3 line fit
  analysis referencing specific resume skills
- **output_file:** output/jobsearch/research.md

### write_report_task
- **agent:** report_writer
- **description:** Read the researcher's ranked list, create a
  polished markdown report with a header, the ranked table, detailed
  sections per job, and a summary. Create a self-contained HTML
  version. End with a JSON block containing separate `telegram` and
  `discord` messages formatted for n8n's native messaging nodes —
  Telegram uses MarkdownV2 (≤4096 chars), Discord has `content` +
  optional `embeds` for rich cards
- **expected_output:** Two files (markdown + HTML) AND a JSON block
  with keys `telegram` (object with `text` + `parse_mode`), `discord`
  (object with `content` + `embeds`), `summary` (one-liner string),
  and `html_file` (path)
- **context:** [research_task]
- **output_file:** output/jobsearch/report-{role}-{date}.md

## CLI registration (cli.py changes)

Add a `jobsearch` subcommand:

```python
p_js = sub.add_parser("jobsearch", parents=[common], help="Search job boards for KDB+, Golang, or Python roles")
p_js.add_argument("--role", choices=["kdb", "go", "python"], default="kdb")
p_js.add_argument("--resume", default="../agents/jobsearch/references/resume.md")
p_js.add_argument("--limit", type=int, default=8)
p_js.set_defaults(handler=run_jobsearch)
```

Handler `run_jobsearch(args, quiet)` → builds `JobSearchCrew`, kickoff
with inputs `{role: args.role, resume_path: args.resume, limit: args.limit}`,
writes output.

Invocation:
```bash
uv run run.py jobsearch --role kdb --limit 8          # verbose
uv run run.py jobsearch --role python --limit 5 --quiet  # n8n-friendly
uv run run.py jobsearch --role go --limit 5 --quiet    # n8n-friendly
```

## Reuse

| From | What |
|------|------|
| `crewai_jobs.config` | `get_api_key()`, `get_model()`, `get_base_url()` — same opencode-go LLM |
| `crewai_jobs.cli` | parent parser (`common`) with `--quiet`, banner/check helpers |
| `crewai_jobs.crews.news_summarizer.crew` | `build_llm()` pattern — copy into jobsearch's crew.py |
| `agents/jobsearch/references/resume.md` | Same resume — loaded via ResumeLoaderTool (reads the file; no copy needed) |

## Steps

- [ ] 1. Add `duckduckgo-search` to pyproject.toml dependencies
- [ ] 2. Create `tools/job_search.py` (JobSearchTool)
- [ ] 3. Create `tools/job_verifier.py` (JobVerifierTool)
- [ ] 4. Create `tools/job_tracker.py` (JobTrackerTool)
- [ ] 5. Create `tools/resume_loader.py` (ResumeLoaderTool)
- [ ] 6. Update `tools/__init__.py` to export all new tools
- [ ] 7. Create `crews/jobsearch/config/agents.yaml`
- [ ] 8. Create `crews/jobsearch/config/tasks.yaml`
- [ ] 9. Create `crews/jobsearch/crew.py` (JobSearchCrew with 2 agents)
- [ ] 10. Create `crews/jobsearch/__init__.py`
- [ ] 11. Register `jobsearch` subcommand in `cli.py`
- [ ] 12. Update `pyproject.toml` package-data for jobsearch YAMLs
- [ ] 13. Update `README.md` — add jobsearch to "What's here" + model table
- [ ] 14. `uv sync` to install duckduckgo-search
- [ ] 15. Smoke test: `uv run run.py jobsearch --help`
- [ ] 16. End-to-end test: real job search with modest limit
- [ ] 17. Quiet-mode test: verify stdout is only the JSON block
- [ ] 18. Integration test: n8n SSH node captures JSON, routes to Telegram

## Verification

1. `uv run run.py jobsearch --help` — shows subcommand with --role (kdb/go/python), --resume, --limit
2. `uv run run.py jobsearch --role kdb --limit 3` — researcher finds jobs, writer creates markdown + HTML, JSON appended at end
3. `uv run run.py jobsearch --role python --quiet` — stdout is ONLY the JSON block (parseable by n8n), no banners
4. `data/seen-jobs.json` exists after first run and grows on subsequent runs
5. Any duplicate URLs from a prior run are excluded
6. JSON block validates: `telegram.text` ≤ 4096 chars, `discord.embeds` ≤ 10 entries
