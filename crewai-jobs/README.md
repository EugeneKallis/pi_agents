# crewai-jobs — Multi-Crew CrewAI Project

A home for **scheduled, headless AI jobs** — pipelines that run without a
human in the chair. Each job is a CrewAI *crew*; this project holds them
all in one place with shared tooling, one venv, and a single CLI
dispatcher that [n8n](https://n8n.io) (or cron, or launchd) calls via SSH.

```
n8n (schedule + notify)  ──SSH──▶  uv run run.py <crew> [args]
                                         │
                              ┌──────────┴──────────┐
                              ▼                      ▼
                        crews/news_summarizer   crews/<next job>
                              │
                   researcher → summarizer → output/news_summarizer/summary.md
```

This sits next to (not inside) the repo's `agents/` folder. `agents/`
holds your *interactive* pi assistants; `crewai-jobs/` holds your
*automated* pipelines. Different tools, different shapes, same repo.

## What's here so far

- **`news`** — scrapes a news website (BBC by default) and writes a
  polished markdown brief. The reference crew; copy it to make more.

## Requirements

- **[uv](https://docs.astral.sh/uv/)** — `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.
- **An opencode-go API key** — get one at [opencode.ai/zen](https://opencode.ai/zen).
  - *pi_agents users:* if `~/.pi/agent/auth.json` already has an
    `opencode-go` entry, every crew picks it up automatically — skip the
    `.env` step.
- **Python 3.10–3.13** — uv picks the version from `.python-version` and
  downloads it if needed.

## Setup

```bash
cd crewai-jobs
uv sync                       # creates .venv, installs everything
cp .env.example .env          # optional if you have ~/.pi/agent/auth.json
# Edit .env and set OPENCODE_API_KEY=sk-ocg-... (only if no auth.json)
```

## Running a job

```bash
# interactive — full CrewAI traces, banner, summary printed
uv run run.py news
uv run run.py news https://apnews.com --limit 8

# quiet — ONLY the final summary goes to stdout
# (this is what n8n's SSH node should capture)
uv run run.py news --quiet
uv run run.py news --quiet --limit 3 > brief.md

# job search — KDB+, Golang, or Python roles
uv run run.py jobsearch --role kdb --limit 5         # verbose
uv run run.py jobsearch --role python --limit 8 --quiet  # n8n-friendly (JSON stdout)
uv run run.py jobs --role go                        # alias `jobs` works too
```

Other invocation shapes that all work after `uv sync`:

```bash
uv run python -m crewai_jobs news          # module form
uv run python -m crewai_jobs jobsearch     # module form
uv run crewai-jobs news                    # installed console script
uv run crewai-jobs jobsearch --role kdb    # installed console script
.venv/bin/python run.py news               # after `source .venv/bin/activate`
.venv/bin/python run.py jobsearch --role go # after activate
```

## Calling it from n8n

### News summarizer

Add an **SSH node** that runs:

```bash
cd /Users/ponzi/dev/pi_agents/crewai-jobs && .venv/bin/python run.py news --quiet --limit 5
```

The SSH node's stdout will be exactly the markdown brief — pipe that

### Job search

Add an **SSH node** that runs:

```bash
cd /Users/ponzi/dev/pi_agents/crewai-jobs && .venv/bin/python run.py jobsearch --role kdb --limit 5 --quiet
```

The SSH node's stdout is a JSON object with keys `telegram`, `discord`,
`summary`, and `html_file`. n8n's **JSON Parse** node feeds directly
into native **Telegram** and **Discord** nodes — no bot tokens needed
in crewai. The JSON is scoped per platform so each message looks best on
its own channel.

For the Telegram node, use `{{json.telegram.text}}` as the message
and `{{json.telegram.parse_mode}}` for formatting. For Discord, use
`{{json.discord.content}}` and map `{{json.discord.embeds}}` to embeds.
into whatever downstream node you like (Telegram, Slack, email, Notion,
a DB). `--quiet` is the important flag: it suppresses CrewAI's traces
and banners so the captured stdout is clean.

No secrets need to live in n8n — the script reads the opencode-go key
from `~/.pi/agent/auth.json` on the Mac it runs on. Set the SSH node
timeout to ~5 minutes so a slow LLM response doesn't get killed.

## Project layout

```
crewai-jobs/
├── README.md
├── pyproject.toml                 # deps + uv config + console script
├── uv.lock                        # commit this — reproducible installs
├── .python-version                # pins Python 3.11 for uv
├── .env.example
├── .gitignore
├── run.py                         # launcher → crewai_jobs.cli dispatcher
├── output/                        # generated files (gitignored)
│   └── news_summarizer/
│       ├── research.md            # raw story list from the researcher
│       └── summary.md             # final polished brief
├── logs/                          # if you wire up file logging later
└── src/crewai_jobs/
    ├── __init__.py
    ├── __main__.py                # makes `python -m crewai_jobs` work
    ├── cli.py                     # subcommand dispatcher (--quiet lives here)
    ├── config.py                  # shared: opencode-go key/model/base_url
    ├── crews/
    │   ├── __init__.py
    │   ├── news_summarizer/       # ← one folder per job
    │   │   ├── __init__.py        #   exports NewsCrew
    │   ├── jobsearch/
    │   │   ├── __init__.py        #   exports JobSearchCrew
    │       ├── crew.py            #   @CrewBase assembly + build_llm()
    │       └── config/
    │           ├── agents.yaml    #   role/goal/backstory per agent
    │           └── tasks.yaml     #   description/expected_output per task
    └── tools/
        ├── __init__.py
        └── news_scraper.py        # NewsScraperTool (BaseTool subclass)
```

## How the pieces fit

### The dispatcher — `cli.py`

One CLI, one subcommand per crew. `uv run run.py news` → calls
`run_news()` which builds `NewsCrew`, kicks it off, and writes the
output. Shared concerns (API key check, banner, `--quiet`, output
writing) live in the dispatcher so each crew's handler stays tiny.

### A crew — `crews/<name>/`

A crew is a team of agents + a list of tasks + a process. The
`@CrewBase` decorator loads `config/agents.yaml` and `config/tasks.yaml`
(resolved relative to `crew.py`) and the `@agent` / `@task` methods wire
them up. `Process.sequential` means the researcher runs to completion,
then the summarizer runs with the research output piped in as context.

### The LLM — `config.py` + each crew's `build_llm()`

All crews share one opencode-go LLM config. `config.py` resolves the
API key (env first, then `~/.pi/agent/auth.json`), the model, and the
base URL. Each crew's `build_llm()` constructs a `crewai.LLM`:

```python
LLM(model=f"openai/{get_model()}",   # "openai/" prefix → OpenAI-compat mode
    base_url=get_base_url(),         # opencode.ai/zen/go/v1, not api.openai.com
    api_key=get_api_key())
```

The `openai/` prefix tells LiteLLM (CrewAI delegates to it) to use the
OpenAI request shape; `base_url` reroutes the call to opencode-go.

### The tools — `tools/`

Shared across all crews. `NewsScraperTool` is a `crewai.tools.BaseTool`
subclass with a Pydantic `args_schema` — the agent sees its name +
description + arg schema, decides to call it, and CrewAI handles the
tool-calling protocol automatically. You write *what* the tool does;
CrewAI handles *when and how* it's called.

## Adding a new crew (a new job)

1. **Copy the template:**
   ```bash
   cp -r src/crewai_jobs/crews/news_summarizer src/crewai_jobs/crews/pr_reviewer
   ```
2. **Edit the crew:**
   - `crew.py` — rename `NewsCrew` → `PrReviewerCrew`, swap the tool,
     adjust the agents/tasks.
   - `config/agents.yaml` — new roles (e.g. `code_reader`, `reviewer`).
   - `config/tasks.yaml` — new tasks, new `output_file` paths under
     `output/pr_reviewer/`.
3. **Register a subcommand** in `cli.py`:
   ```python
   from crewai_jobs.crews.pr_reviewer import PrReviewerCrew

   def run_pr_review(args, quiet):
       ...
       result = PrReviewerCrew(quiet=quiet).crew().kickoff(inputs={...})
       ...

   # in _build_parser():
   p_pr = sub.add_parser("pr-review", parents=[common], help="Review a PR.")
   p_pr.add_argument("--pr", type=int, required=True)
   p_pr.set_defaults(handler=run_pr_review)
   ```
4. **Ship the YAML** — add one line to `pyproject.toml`:
   ```toml
   [tool.setuptools.package-data]
   "crewai_jobs.crews.pr_reviewer" = ["config/*.yaml"]
   ```
5. **Make the output dir:** `mkdir -p output/pr_reviewer`
6. **Re-sync & run:** `uv sync && uv run run.py pr-review --pr 123`

That's the whole pattern. Each crew is self-contained in its folder;
the dispatcher is the only shared wiring.

## Configuration reference

All in `.env` (copy from `.env.example`):

| Variable            | Default                          | Purpose                                              |
| ------------------- | -------------------------------- | --------------------------------------------------- |
| `OPENCODE_API_KEY`  | — *(falls back to pi auth.json)* | **Required.** opencode-go API key.                   |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/go/v1`  | API endpoint.                                        |
| `MODEL`             | `deepseek-v4-flash`              | Any opencode-go model id. See `.env.example` for the full list. |
| `NEWS_URL`          | `https://www.bbc.com/news`       | Homepage to scrape (news crew only).                |
| `NEWS_LIMIT`        | `5`                              | Top N stories (news crew only).                     |
| `OUTPUT_FILE`       | `output/news_summarizer/summary.md` | Where the brief is written.                     |

CLI flags override env vars for that run only. `--quiet` works on every
subcommand.

## Composing crews into a pipeline (Flows)

When you have 2+ crews and want to chain them ("research these 3 sites,
*then* write one combined digest"), that's a CrewAI **Flow** — an
orchestrator that sits above crews with state, branching, and parallel
execution. Add a `flows/` package when you get there. The crews don't
need to change; a Flow just calls `crew_a.kickoff()` then
`crew_b.kickoff()` with the first one's output. See the CrewAI Flows
docs when you're ready.

## Known limits

- Pure HTML scraping — JS-rendered sites return empty results. Swap
  `requests` for Playwright in `news_scraper.py` for those.
- No rate limiting — don't hammer a site. Add caching or per-domain
  delays for heavy use.
- A `deepseek-v4-flash` news run costs well under a cent; `deepseek-v4-pro`
  is ~12× more.
