# langgraph-jobs

Multi-graph LangGraph project running scheduled AI jobs — currently a **job search agent** that finds, verifies, and ranks job listings for KDB+/q, Golang, or Python roles.

Designed to be called from **n8n** (via SSH) or run manually from the terminal.

## Prerequisites

- **Python 3.10 – 3.13**
- **uv** (fast Python package manager) — install via `curl -LsSf https://astral.sh/uv/install.sh | sh`
- An **OpenCode API key** — get one at [opencode.ai/zen](https://opencode.ai/zen)

## Setup

```bash
cd langgraph-jobs

# Create a virtual env and install dependencies
uv sync

# Create a .env with your API key
echo "OPENCODE_API_KEY=sk-..." > .env

# Optionally override the model or base URL:
# echo "MODEL=deepseek-v4-flash" >> .env
# echo "OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1" >> .env
```

The API key is also resolved from `~/.pi/agent/auth.json` if no `.env` is present (looks for an `opencode-go` key entry).

## How to Run

All commands should be run from the `langgraph-jobs/` directory.

### Via the convenience launcher (easiest)

```bash
# Search for Python roles
uv run python run.py jobsearch --role python

# Search for Golang roles, top 5 results
uv run python run.py jobsearch --role go --limit 5

# KDB+/q roles, quiet mode (outputs JSON for n8n)
uv run python run.py jobsearch --role kdb --quiet

# All options
uv run python run.py jobsearch --help
```

### Via the installed package

```bash
uv run langgraph-jobs jobsearch --role python
```

### Via `python -m`

```bash
uv run python -m langgraph_jobs jobsearch --role golang --limit 10
```

## CLI Options

| Option              | Description                                 | Default                                        |
|---------------------|---------------------------------------------|------------------------------------------------|
| `--role`            | Role to search: `kdb`, `go`, or `python`    | `kdb`                                          |
| `--limit`           | Number of top results to rank               | `8` (or `$JOBSEARCH_LIMIT`)                    |
| `--resume`          | Path to resume markdown file                | `$JOBSEARCH_RESUME` or `../agents/jobsearch/references/resume.md` |
| `--output`          | Output path for the markdown report         | `$JOBSEARCH_OUTPUT` or `output/jobsearch/report-{role}-{date}.md` |
| `-q` / `--quiet`    | Suppress banners; print JSON to stdout      | off                                             |

## Configuration

| Env Variable         | Purpose                                 | Default                                         |
|----------------------|-----------------------------------------|-------------------------------------------------|
| `OPENCODE_API_KEY`   | API key for the LLM provider            | — (required)                                    |
| `OPENCODE_BASE_URL`  | LLM API base URL                        | `https://opencode.ai/zen/go/v1`                 |
| `MODEL`              | Model name                              | `deepseek-v4-flash`                             |
| `JOBSEARCH_LIMIT`    | Default `--limit` value                 | `8`                                             |
| `JOBSEARCH_RESUME`   | Default `--resume` path                 | `../agents/jobsearch/references/resume.md`      |
| `JOBSEARCH_OUTPUT`   | Default `--output` pattern              | `output/jobsearch/report-{role}-{date}.md`      |

## Output

Reports are written to `output/jobsearch/report-{role}-{date}.md`. Each report contains:

- A ranked markdown table of job listings with fit analysis
- Per-job details (why fit, description, salary, location type, apply link)
- A JSON block with the n8n payload

### Quiet mode JSON shape

In **quiet mode** (`--quiet`), only the JSON payload is printed to stdout — ideal for piping into n8n:

```json
{
  "telegram": "Top KDB+ Job Matches\n\n**Quantitative/Software Engineer (KDB+/Q)**...",
  "discord": {
    "content": "Top KDB+ developer job matches from the latest search.",
    "embeds": [
      {
        "title": "Quantitative/Software Engineer (KDB+/Q)",
        "description": "Build high-performance trading systems at a top-tier hedge fund. Strong fit — your kdb+ experience in tick architecture matches their stack.",
        "salary": "Up to $350k + Bonus",
        "location_type": "Hybrid",
        "url": "https://www.linkedin.com/jobs/view/123456789"
      }
    ]
  }
}
```

## n8n Integration

### SSH Node → Code Node → Telegram / Discord

```
[Cron Trigger]
       ↓
[SSH / Execute Command]
  command: cd /path/to/langgraph-jobs && uv run python run.py jobsearch --role kdb --quiet
       ↓
[Code Node]   ← snippet below
       ↓
[Telegram Send] / [Discord Send]
```

### Code node snippet

```javascript
// ── Parse stdout from SSH node and create items for Telegram + Discord ──
// Input:  [{ code, signal, stdout, stderr }]
// Output: items with json.telegram (for Telegram node) and json.* (for Discord embeds)

const items = [];

for (const row of $input.all()) {
  const raw = row.json.stdout || '';
  if (!raw) continue;

  let payload;
  try {
    payload = JSON.parse(raw.trim());
  } catch (e) {
    throw new Error(`Failed to parse stdout: ${e.message}`);
  }

  // 1. Telegram message as a separate item (nice for Telegram node)
  if (payload.telegram) {
    items.push({
      json: {
        action: 'send_telegram',
        text: payload.telegram,
      }
    });
  }

  // 2. Discord embeds — one item per embed (loop in Switch/IF node)
  if (payload.discord?.content) {
    items.push({
      json: {
        action: 'send_discord',
        content: payload.discord.content,
        embeds: payload.discord.embeds || [],
        // also expose each field individually for Discord node expressions
        embed_count: (payload.discord.embeds || []).length,
      }
    });
  }

  // 3. Individual Discord embed items (for fan-out)
  for (const embed of (payload.discord?.embeds || [])) {
    items.push({
      json: {
        action: 'send_discord_embed',
        title: embed.title,
        description: embed.description,
        salary: embed.salary,
        location_type: embed.location_type,
        url: embed.url,
      }
    });
  }
}

return items;
```

### Downstream node expressions

| Node | Expression |
|------|-----------|
| **Telegram** text | `{{ $json.text }}` |
| **Discord** content | `{{ $json.content }}` |
| **Discord** embed title | `{{ $json.title }}` |

> Use an **IF node** to split on `{{ $json.action }}` (e.g. `send_telegram` → Telegram node, `send_discord` → first Discord node, `send_discord_embed` → loop over embeds).

## Architecture

```
langgraph-jobs/
├── run.py                          # Convenience launcher (just works from project root)
├── pyproject.toml                  # Package metadata, dependencies, CLI entrypoint
├── uv.lock                         # Locked dependency versions
├── .env                            # API key (gitignored)
├── output/jobsearch/               # Generated reports
└── src/langgraph_jobs/
    ├── cli.py                      # CLI dispatcher (subcommands: jobsearch, …)
    ├── config.py                   # API key, model, base URL resolution
    ├── graphs/
    │   ├── __init__.py
    │   └── jobsearch/              # Job search LangGraph
    │       ├── __init__.py
    │       └── graph.py            # StateGraph nodes: load_resume → search → verify → rank → report
    └── tools/
        ├── job_search.py           # DuckDuckGo search for job listings
        ├── job_verifier.py         # HTTP fetch + signal check (active/closed)
        ├── job_tracker.py          # Persists seen URLs to data/seen-jobs.json
        └── resume_loader.py        # Reads resume.md, extracts role-specific sections
```

### Graph Flow

```
load_resume  →  search_jobs  →  verify_jobs  →  analyze_rank  →  write_report  →  END
```

1. **load_resume** — Reads the resume file and extracts role-relevant sections (KDB+, Go, or All Skills + Experience)
2. **search_jobs** — Searches LinkedIn, Indeed, Glassdoor, ZipRecruiter, and Dice via DuckDuckGo
3. **verify_jobs** — Fetches each promising URL and checks for active/closed signals
4. **analyze_rank** — Sends verified listings + resume to the LLM for fit analysis and ranking
5. **write_report** — Generates a markdown report + n8n-compatible JSON block

## Adding a New Job Graph

1. Create `src/langgraph_jobs/graphs/<name>/graph.py` with a `run_<name>()` function
2. Add a subcommand in `cli.py` — copy the `jobsearch` parser pattern
3. Register the handler in `dispatch()`

## Dependencies

| Package           | Purpose                        |
|-------------------|--------------------------------|
| langgraph         | State-based graph execution    |
| langchain-openai  | OpenAI-compatible LLM calls    |
| ddgs              | DuckDuckGo search (no API key) |
| requests          | HTTP fetches                   |
| beautifulsoup4    | HTML parsing                   |
| lxml              | Fast XML/HTML parser           |
| pyyaml            | YAML support                   |
| python-dotenv     | .env file loading              |

## License

MIT
