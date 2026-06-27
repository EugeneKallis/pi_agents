"""Job Search graph — LangGraph + LLM-powered job listing analysis.

Flow: load_resume → search_jobs → analyze_and_report

The search node runs efficient DDG searches and passes raw results to
the LLM (analyze_and_report) which evaluates quality, extracts details,
ranks by fit, and formats for n8n — all in one LLM call.

Key design: search is fast (no LLM round-trips), quality evaluation is
LLM-powered (adapts to results). One LLM call instead of two.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from langgraph_jobs.config import get_api_key, get_base_url, get_model
from langgraph_jobs.tools import (
    JobTrackerTool,
    ResumeLoaderTool,
    search_web,
)

# ── State ────────────────────────────────────────────────────────────────────


class JobSearchState(TypedDict, total=False):
    """State carried through the job search graph."""

    # Inputs
    role: str
    resume_path: str
    limit: int
    date: str
    quiet: bool
    output: str

    # Intermediate
    resume_text: str
    seen_urls: list[str]
    raw_listings_json: str   # JSON array of raw listings from DDG
    final_report: str        # full output (JSON for n8n + markdown)


# ── LLM helpers ──────────────────────────────────────────────────────────────


def _build_llm(**kwargs) -> ChatOpenAI:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "No opencode-go API key found. Set OPENCODE_API_KEY in .env "
            "or add one to ~/.pi/agent/auth.json."
        )
    params = {
        "model": get_model(),
        "base_url": get_base_url(),
        "api_key": api_key,
        "temperature": 0.7,
    }
    params.update(kwargs)
    return ChatOpenAI(**params)


# ── Search ───────────────────────────────────────────────────────────────────


def _search_listings(role: str, limit: int) -> list[dict]:
    """Run targeted DDG searches and return raw results.

    Uses natural language queries. Returns all results without URL filtering;
    the LLM evaluates quality in the analysis node.
    """
    queries = [
        f"{role.upper()} developer job remote US",
        f"{role.upper()} developer job salary",
        f"{role.upper()} developer job New York",
        f"job {role.upper()} developer remote",
    ]

    all_results: list[dict] = []
    seen: set[str] = set()

    for q in queries:
        raw = search_web(q, limit=limit + 5)
        if raw.startswith("Error") or raw.startswith("No results"):
            continue
        # Parse the formatted text back into dicts
        for block in raw.split("\n---\n"):
            lines = block.strip().split("\n")
            item: dict = {}
            for line in lines:
                if line.startswith("Title: "):
                    item["title"] = line[7:]
                elif line.startswith("Snippet: "):
                    item["snippet"] = line[9:]
                elif line.startswith("URL: "):
                    item["url"] = line[5:]
            if item.get("url") and item["url"] not in seen:
                seen.add(item["url"])
                all_results.append(item)

    return all_results[: limit * 3]


# ── Nodes ────────────────────────────────────────────────────────────────────


def _node_load_resume(state: JobSearchState) -> dict:
    """Load the resume, extract role-specific sections, and get seen URLs."""
    role = state["role"]
    resume_path = state["resume_path"]

    resume_text = ResumeLoaderTool.load(path=resume_path, role=role)
    seen_urls = JobTrackerTool.read_urls()

    return {
        "resume_text": resume_text,
        "seen_urls": seen_urls,
    }


def _node_search_jobs(state: JobSearchState) -> dict:
    """Run DDG searches, return raw listings as JSON for the LLM to evaluate."""
    import json as _json

    role = state["role"]
    limit = state.get("limit", 8)
    seen = set(state.get("seen_urls", []))

    raw_listings = _search_listings(role, limit)

    # Filter out already-seen URLs
    raw_listings = [r for r in raw_listings if r.get("url") not in seen]

    list_json = _json.dumps(raw_listings, indent=2, ensure_ascii=False)

    return {
        "raw_listings_json": list_json,
    }


def _node_analyze_and_report(state: JobSearchState) -> dict:
    """Single LLM call: filter, analyze, rank, and format.

    Combines filtering + ranking + n8n JSON output in one call to
    avoid the slow double-LLM pattern.
    """
    llm = _build_llm(temperature=0.7)
    role = state["role"]
    limit = state.get("limit", 8)
    date_str = state.get("date", date.today().isoformat())
    resume_text = state.get("resume_text", "")
    list_json = state.get("raw_listings_json", "[]")
    output_path = state.get("output", "output/jobsearch/report-{role}-{date}.md")

    listings = json.loads(list_json) if list_json and list_json != "[]" else []

    if not listings:
        empty_json = '{"job_count": 0, "telegram": "", "discord": {"content": "No matching jobs found.", "embeds": []}}'
        report = f"# Job Search Results — {role.upper()}\n\nNo job listings found.\n\n```json\n{empty_json}\n```"
        _write_report_file(report, role, date_str, output_path)
        return {"final_report": report}

    # Build compact listing text from raw DDG results
    listings_text = ""
    for i, r in enumerate(listings[: limit * 2], 1):
        listings_text += (
            f"{i}. {r.get('title', 'N/A')}\n"
            f"   Snippet: {r.get('snippet', '')[:300]}\n"
            f"   URL: {r.get('url', '')}\n\n"
        )

    prompt = f"""You are a senior technical recruiter analyzing job listings for a {role.upper()} role.

RESUME (key skills and experience):
{resume_text[:2500]}

RAW SEARCH RESULTS — these are from web search and may include job board search pages, individual listings, or aggregators. Evaluate each one:
{listings_text}

YOUR TASKS (do all in one response):

1. FILTER: Skip anything that is clearly not a job listing (news articles, blog posts, ads, etc.).
2. EXTRACT: For each valid listing, infer: title, company, location, salary, location_type (Remote/Hybrid/In-office/Unknown). Use the snippet text — most of the info is there.
3. ANALYZE: Compare against the resume. Rate fit: Excellent / Strong / Moderate / Weak. Reference specific resume skills.
4. RANK: Top {limit} by fit quality.
5. FORMAT: Produce a JSON block (```json) with EXACTLY these keys:

{{
  "job_count": <number>,
  "telegram": "<Markdown-formatted message. Use **bold** for job titles, - for bullet lists. Include top 3-5 jobs with title, company, location, salary. ≤4096 chars. If 0 jobs, empty string>",
  "discord": {{
    "content": "<short intro line, ≤2000 chars>",
    "embeds": [
      {{
        "title": "Job Title",
        "description": "2-3 sentence summary of the role and why it fits the resume",
        "salary": "$100k-$150k" or "Not listed",
        "location_type": "Remote" | "Hybrid" | "In-office" | "Unknown",
        "url": "https://direct-job-url"
      }}
    ]
  }}
}}

RULES:
- job_count: integer (0 if nothing found).
- Telegram: be concise, scannable. If 0 jobs, "".
- Discord embeds: one per ranked job, up to {limit}. Each embed MUST have all 5 fields. If 0 jobs, embeds: [], content: "No matching jobs found."
- url: use the URL from the search result. Even if it's a search/aggregate page, include it as-is — user can navigate from there.
- location_type: exactly "Remote" | "Hybrid" | "In-office" | "Unknown"
- SKIP jobs outside the US or requiring visa sponsorship.
- SKIP Jersey City, NJ locations.
- ONLY three top-level keys: job_count, telegram, discord.

After the JSON block, add a brief markdown section with a ranked table and per-job details for the output file.
"""

    response = llm.invoke(prompt)
    report = response.content

    # Write to output file
    _write_report_file(report, role, date_str, output_path)

    return {"final_report": report}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_report_file(report: str, role: str, date_str: str, output: str) -> None:
    """Write the report to the output file."""
    out_path = output.replace("{role}", role).replace("{date}", date_str)
    path = Path(out_path)
    if not path.is_absolute():
        here = Path(__file__).resolve()
        project_root = here.parent.parent.parent.parent.parent
        path = (project_root / out_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


# ── Graph ────────────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and return the compiled JobSearch LangGraph graph."""
    graph = StateGraph(JobSearchState)

    graph.add_node("load_resume", _node_load_resume)
    graph.add_node("search_jobs", _node_search_jobs)
    graph.add_node("analyze_and_report", _node_analyze_and_report)

    graph.set_entry_point("load_resume")
    graph.add_edge("load_resume", "search_jobs")
    graph.add_edge("search_jobs", "analyze_and_report")
    graph.add_edge("analyze_and_report", END)

    return graph.compile()


def run_jobsearch(
    role: str = "kdb",
    resume_path: str = "../agents/jobsearch/references/resume.md",
    limit: int = 8,
    quiet: bool = False,
    output: str = "output/jobsearch/report-{role}-{date}.md",
) -> str:
    """Run the job search graph and return the final report text."""
    today = date.today().isoformat()

    initial_state: JobSearchState = {
        "role": role,
        "resume_path": str(Path(resume_path).resolve()),
        "limit": limit,
        "date": today,
        "quiet": quiet,
        "output": output,
    }

    app = build_graph()
    result = app.invoke(initial_state)

    if quiet:
        raw = result.get("final_report", "")
        json_block = _extract_json_block(raw)
        try:
            parsed = json.loads(json_block)
        except Exception:
            return json_block

        clean: dict = {}
        clean["job_count"] = int(parsed.get("job_count", 0))
        if "telegram" in parsed:
            clean["telegram"] = parsed["telegram"]
        if "discord" in parsed:
            clean["discord"] = parsed["discord"]

        if isinstance(clean.get("discord"), dict):
            clean["discord"].setdefault("content", "")
            clean["discord"].setdefault("embeds", [])

        return json.dumps(clean, indent=2, ensure_ascii=False)

    return result.get("final_report", "")


def _extract_json_block(text: str) -> str:
    """Pull JSON out of text, trying multiple strategies."""
    # 1. whole text is JSON
    try:
        json.loads(text)
        return text
    except (ValueError, TypeError):
        pass

    # 2. fenced code block
    blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    for block in reversed(blocks):
        try:
            json.loads(block)
            return block.strip()
        except ValueError:
            continue

    # 3. bare JSON object
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except ValueError:
                        break
        start = text.find("{", start + 1)

    return text
