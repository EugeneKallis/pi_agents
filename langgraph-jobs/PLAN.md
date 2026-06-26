# Plan: Enhance langgraph-jobs output & fix URL scraping

## Context

The job search graph has two problems:
1. **Generic URLs** — DDG search returns SEO/search pages (e.g. `linkedin.com/jobs/kdb+-developer-jobs`) instead of individual job listing URLs (e.g. `linkedin.com/jobs/view/...`)
2. **Output format** — The JSON payload includes `summary`, `html_file`, and a complex structure. User wants only 2 keys: `telegram` (a formatted message string) and `discord` (with embeds containing Title, Description, Salary, Location-type, URL).

## Approach

### 1. URL filtering in `tools/job_search.py`

Add URL classification logic so only individual job listing URLs pass through:

- **`_JOB_URL_PATTERNS`** — regex patterns that match individual job posting pages (e.g. `linkedin.com/jobs/view/`, `indeed.com/viewjob`, `glassdoor.com/job-listing/`, `dice.com/job-detail/`)
- **`_NON_JOB_URL_PATTERNS`** — regex patterns that match search/SEO/category pages (e.g. `linkedin.com/jobs/{keyword}-jobs`, `indeed.com/jobs?`, `ziprecruiter.com/jobs/search`)
- **`_is_job_listing_url(url)`** — returns `True` only if the URL hits a job pattern AND misses all non-job patterns
- Apply the filter in both `search_raw()` and `search()`

### 2. Updated graph prompts in `graphs/jobsearch/graph.py`

**`_node_analyze_rank`** prompt changes:
- Also extract salary info and location type (remote / hybrid / in-office) for each listing

**`_node_write_report`** prompt changes:
- Output ONLY `telegram` and `discord` — remove `summary` and `html_file`
- `telegram.text`: MarkdownV2 formatted, ≤4096 chars, top 3–5 jobs
- `discord.embeds[]`: each with `title`, `description`, `salary`, `location_type`, `url`
- `discord.content`: a short intro line

### 3. `run_jobsearch` quiet mode

- Already extracts JSON block from the LLM output — no structural change needed, just the prompt change above drives it

## Files to modify

| File | Change |
|------|--------|
| `src/langgraph_jobs/tools/job_search.py` | Add `_is_job_listing_url()`, apply filter in `search_raw()` and `search()` |
| `src/langgraph_jobs/graphs/jobsearch/graph.py` | Update `_node_analyze_rank` and `_node_write_report` prompts; new output schema |
| `README.md` | Update n8n Code node example for new output format |

## Reuse

- `urlparse` from stdlib — already available
- `re` from stdlib — already imported in `graph.py`, add to `job_search.py`
- `_extract_json_block()` in graph.py — keep as-is
- `JobVerifierTool`, `JobTrackerTool`, `ResumeLoaderTool` — no changes needed

## Steps

- [ ] **1. Add URL filtering to `job_search.py`**
  - Import `re`, `urlparse`
  - Add `_JOB_URL_PATTERNS` list (individual job posting patterns per site)
  - Add `_NON_JOB_URL_PATTERNS` list (search/SEO/category page patterns)
  - Add `_is_job_listing_url(url)` static method
  - Apply filter in `search_raw()` — only append results that pass `_is_job_listing_url`
  - Apply filter in `search()` after collecting results
  - Bump `max_results` fetch margin (e.g. `limit + 10`) since filter will drop entries

- [ ] **2. Update `_node_analyze_rank` prompt in `graph.py`**
  - Add instruction to extract salary and location type per listing
  - Include those fields in the per-job detail output

- [ ] **3. Rewrite `_node_write_report` prompt in `graph.py`**
  - Remove `summary` and `html_file` from the JSON schema
  - Discord embeds: `{title, description, salary, location_type, url}`
  - Telegram: keep MarkdownV2, top 3–5 jobs only
  - Still produce markdown report for the file output (optional/nice-to-have)

- [ ] **4. Update `README.md` n8n Code node snippet**
  - Reflect new 2-key JSON shape: `{telegram: string, discord: {content, embeds}}`
  - Add example expressions for downstream Telegram/Discord nodes

## Verification

- Run `uv run python run.py jobsearch --role kdb --limit 3 --quiet`
- Confirm stdout is valid JSON with ONLY `telegram` and `discord` keys
- Check that URLs in results are individual job listings (not search pages)
- Check Discord embeds have `title`, `description`, `salary`, `location_type`, `url`
- Run `uv run python run.py jobsearch --role kdb --limit 3` (non-quiet) to verify markdown report still writes
