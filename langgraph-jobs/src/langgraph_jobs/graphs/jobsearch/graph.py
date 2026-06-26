"""Job Search graph — LangGraph replacement for the CrewAI jobsearch crew.

Flow: load_resume → search_jobs → verify_jobs → analyze_rank → write_report

State carries: role, resume_path, limit, date, plus intermediate results.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_jobs.config import get_api_key, get_base_url, get_model
from langgraph_jobs.tools import (
    JobSearchTool,
    JobTrackerTool,
    JobVerifierTool,
    ResumeLoaderTool,
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
    search_results: str          # human-readable search output
    raw_listings: list[dict]     # structured {title, snippet, url}
    verified_listings: list[dict]  # listings with verification results
    ranked_markdown: str         # ranked table output
    final_report: str            # full markdown + JSON report


# ── LLM ──────────────────────────────────────────────────────────────────────


def _build_llm() -> ChatOpenAI:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "No opencode-go API key found. Set OPENCODE_API_KEY in .env "
            "or add one to ~/.pi/agent/auth.json."
        )
    return ChatOpenAI(
        model=get_model(),
        base_url=get_base_url(),
        api_key=api_key,
        temperature=0.7,
    )


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
    """Search multiple job boards for the role."""
    role = state["role"]
    limit = state.get("limit", 8)
    seen = set(state.get("seen_urls", []))

    queries = [
        f"site:linkedin.com/jobs {role} developer",
        f"site:indeed.com {role} developer salary",
        f"site:ziprecruiter.com {role} developer",
        f"site:glassdoor.com/jobs {role} developer",
        f"site:dice.com/jobs {role} developer",
    ]

    all_listings: list[dict] = []
    seen_urls_set: set[str] = set()

    for q in queries:
        results = JobSearchTool.search_raw(query=q, role=role, limit=limit + 5)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen and url not in seen_urls_set:
                seen_urls_set.add(url)
                all_listings.append(r)

    # Build human-readable search output
    search_text = f"Search results for {role.upper()} roles:\nFound {len(all_listings)} unique listings across {len(queries)} boards.\n"
    for i, r in enumerate(all_listings[:limit * 2], 1):
        search_text += f"\n{i}. {r['title']}\n   {r['snippet'][:200]}\n   URL: {r['url']}\n"

    return {
        "search_results": search_text,
        "raw_listings": all_listings,
    }


def _node_verify_jobs(state: JobSearchState) -> dict:
    """Verify promising listings are still active (with short timeout)."""
    listings = state.get("raw_listings", [])
    limit = state.get("limit", 8)

    verified: list[dict] = []
    to_check = listings[:min(limit * 2, 12)]  # cap at 12 to avoid excessive fetches

    for r in to_check:
        url = r.get("url", "")
        verdict = JobVerifierTool.verify(url)  # uses 8s timeout internally
        r["verdict"] = verdict
        if verdict.startswith("ACTIVE") or verdict.startswith("UNCERTAIN"):
            verified.append(r)
        if len(verified) >= limit * 2:
            break

    # If verification didn't find enough, fall back to raw listings
    if len(verified) < limit:
        for r in listings[len(to_check):]:
            r["verdict"] = "NOT_VERIFIED (fast path)"
            verified.append(r)
            if len(verified) >= limit * 2:
                break

    return {"verified_listings": verified}


def _node_analyze_rank(state: JobSearchState) -> dict:
    """Use LLM to analyze fit against resume and produce a ranked table."""
    llm = _build_llm()
    role = state["role"]
    limit = state.get("limit", 8)
    resume_text = state.get("resume_text", "")
    verified = state.get("verified_listings", [])

    if not verified:
        return {"ranked_markdown": f"No verified active job listings found for {role.upper()} roles."}

    # Build a compact listing for the LLM
    listings_text = ""
    for i, r in enumerate(verified[:limit * 2], 1):
        listings_text += (
            f"{i}. {r['title']}\n"
            f"   Snippet: {r['snippet'][:250]}\n"
            f"   URL: {r['url']}\n"
            f"   Verdict: {r.get('verdict', 'unknown')}\n\n"
        )

    prompt = f"""You are a senior technical recruiter analyzing job listings for a {role.upper()} role.

RESUME:
{resume_text[:3000]}

JOB LISTINGS:
{listings_text}

TASK: Analyze each listing against the resume. For each job, write a 2-3 line fit analysis referencing specific resume skills. Flag salary transparency, location fit (remote=best, NYC-hybrid=ok, Jersey City=NO, non-US=NO). Then rank the top {limit} by fit quality.

Output format — a markdown table followed by per-job details:

| # | Title | Company | Location | Salary | Fit | Link |
|---|-------|---------|----------|--------|-----|------|

Below each row, a **Details** section with:
- **Why fit:** 2-3 lines referencing specific resume skills
- **Description:** 1-2 sentence summary
- **Salary:** Listed or "Not listed"
- **Apply:** Clickable URL

End with: total found, total verified active, total ranked.
"""

    response = llm.invoke(prompt)
    return {"ranked_markdown": response.content}


def _node_write_report(state: JobSearchState) -> dict:
    """Format final report with markdown + JSON block for n8n."""
    llm = _build_llm()
    role = state["role"]
    date_str = state.get("date", date.today().isoformat())
    ranked = state.get("ranked_markdown", "")
    output = state.get("output", f"output/jobsearch/report-{{role}}-{{date}}.md")

    prompt = f"""Read the ranked job list below and produce the final deliverables.

RANKED JOB LIST:
{ranked}

TASK:
1. Write a JSON block (as ```json) with n8n-compatible messages:

{{
  "telegram": {{
    "text": "<MarkdownV2-formatted, ≤4096 chars. Escape: * _ [ ] ( ) ~ ` > # + - = | {{ }} . ! with \\\\>",
    "parse_mode": "MarkdownV2"
  }},
  "discord": {{
    "content": "<plain text, ≤2000 chars>",
    "embeds": [
      {{"title": "Job Title", "description": "Company | Location | Salary | Fit summary", "url": "https://apply.link"}}
    ]
  }},
  "summary": "<one-line summary: found N results for ROLE>",
  "html_file": "output/jobsearch/report-{role}-{date_str}.html"
}}

Telegram rules: MarkdownV2, ≤4096 chars, escape special chars. Top 3-5 jobs only.
Discord rules: ≤2000 chars content, ≤10 embeds.

2. THEN produce a polished markdown report with:
   - Header: role, date, stats
   - The ranked table + per-job details
   - "Key Takeaways" section

Save both the markdown report and the JSON block.
"""

    response = llm.invoke(prompt)
    report = response.content

    # Write to output file
    out_path = output.replace("{role}", role).replace("{date}", date_str)
    path = Path(out_path)
    if not path.is_absolute():
        # graph.py → jobsearch/ → graphs/ → langgraph_jobs/ → src/ → langgraph-jobs/
        here = Path(__file__).resolve()
        project_root = here.parent.parent.parent.parent.parent
        path = (project_root / out_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")

    return {"final_report": report}


# ── Graph ────────────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and return the compiled JobSearch LangGraph graph."""
    graph = StateGraph(JobSearchState)

    graph.add_node("load_resume", _node_load_resume)
    graph.add_node("search_jobs", _node_search_jobs)
    graph.add_node("verify_jobs", _node_verify_jobs)
    graph.add_node("analyze_rank", _node_analyze_rank)
    graph.add_node("write_report", _node_write_report)

    graph.set_entry_point("load_resume")
    graph.add_edge("load_resume", "search_jobs")
    graph.add_edge("search_jobs", "verify_jobs")
    graph.add_edge("verify_jobs", "analyze_rank")
    graph.add_edge("analyze_rank", "write_report")
    graph.add_edge("write_report", END)

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
        # Extract JSON block for clean n8n output
        raw = result.get("final_report", "")
        json_block = _extract_json_block(raw)
        try:
            parsed = json.loads(json_block)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            return json_block

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
