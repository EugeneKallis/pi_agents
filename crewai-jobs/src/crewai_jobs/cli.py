"""CLI dispatcher: `python -m crewai_jobs <crew-name> [args]`.

Each crew gets a subcommand. To add a new job:

1. Create ``crewai_jobs/crews/<name>/`` with a ``crew.py`` (copy
   ``news_summarizer`` as a template) and ``config/{agents,tasks}.yaml``.
2. Add an ``add_parser("<name>", ...)`` block below and a matching
   branch in ``dispatch()``.

The dispatcher owns shared concerns (LLM key check, banner, --quiet,
output writing) so individual crew ``run_*`` handlers stay tiny.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

# Load .env from the project root (two levels up from src/) before
# anything reads env vars.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Import after load_dotenv so config.py sees the env vars.
from crewai_jobs.config import (  # noqa: E402
    get_api_key,
    get_base_url,
    get_model,
    key_source,
)


# ─── shared helpers ──────────────────────────────────────────────────────────


def _check_api_key() -> bool:
    if get_api_key():
        return True
    print(
        "✗ No opencode-go API key found.\n"
        "  Set OPENCODE_API_KEY in .env, or add one to ~/.pi/agent/auth.json\n"
        "  (get a key at https://opencode.ai/zen).",
        file=sys.stderr,
    )
    return False


def _print_banner(url: str, limit: int, output: str) -> None:
    print(f"→ LLM: {get_model()}  via  {get_base_url()}  (key from: {key_source()})")
    print(f"→ Scraping {url} (limit={limit})")
    print(f"→ Summary will be written to {output}\n")


def _write_output(result, output: str) -> None:
    """Write the crew's final output to a file and return its text."""
    summary = getattr(result, "raw", str(result))
    out_path = Path(output)
    if not out_path.is_absolute():
        out_path = _PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary, encoding="utf-8")
    return summary


def _extract_json_block(text: str) -> str:
    """Pull JSON out of a crew output, trying four strategies in order:

    1. If the whole text parses as JSON, return it as-is.
    2. Find a fenced ```json ... ``` code block.
    3. Find a bare JSON object (first '{' to matching '}').
    4. Give up and return the original text.

    Returns a JSON string (no surrounding markdown). Always returns SOMETHING
    parseable-ish so the caller doesn't crash, but the caller should handle
    JSONDecodeError as a last resort.
    """
    import json as _json
    import re

    # 1. whole text is JSON
    try:
        _json.loads(text)
        return text
    except (ValueError, TypeError):
        pass

    # 2. fenced code block
    blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    for block in reversed(blocks):
        try:
            _json.loads(block)
            return block.strip()
        except ValueError:
            continue

    # 3. bare JSON object — find first '{' and walk braces to find the match
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        _json.loads(candidate)
                        return candidate
                    except ValueError:
                        break
        start = text.find("{", start + 1)

    # 4. give up
    return text


# ─── per-crew run handlers ───────────────────────────────────────────────────
# Each handler is a thin function: parse its args, build the crew, kickoff,
# then hand the result back to the dispatcher for output handling.


def run_news(args: argparse.Namespace, quiet: bool) -> int:
    from crewai_jobs.crews.news_summarizer import NewsCrew

    if not quiet:
        _print_banner(args.url, args.limit, args.output)

    inputs = {"news_url": args.url, "limit": args.limit}
    result = NewsCrew(quiet=quiet).crew().kickoff(inputs=inputs)
    summary = _write_output(result, args.output)

    if not quiet:
        print(f"\n✓ Done. Summary written to {Path(args.output)}")
        print("─" * 60)
        print(summary)
    else:
        # Quiet mode: just the summary to stdout, for n8n/SSH to capture.
        print(summary)
    return 0


def run_jobsearch(args: argparse.Namespace, quiet: bool) -> int:
    from crewai_jobs.crews.jobsearch import JobSearchCrew

    from datetime import date
    today = date.today().isoformat()

    if not quiet:
        print(f"→ LLM: {get_model()}  via  {get_base_url()}  (key from: {key_source()})")
        print(f"→ Job search: {args.role.upper()} roles (limit={args.limit})")
        print(f"→ Resume: {args.resume}")
        print(f"→ Results will be written to output/jobsearch/\n")

    inputs = {
        "role": args.role,
        "resume_path": str(Path(args.resume).resolve()),
        "limit": args.limit,
        "date": today,
    }
    # Build the real output path with role and date substituted
    output = args.output.replace("{role}", args.role).replace("{date}", today)

    result = JobSearchCrew(quiet=quiet).crew().kickoff(inputs=inputs)

    # Write the raw output to the resolved output file
    summary = _write_output(result, output)

    if not quiet:
        print(f"\n✓ Done. Results written to output/jobsearch/")
        print("─" * 60)
        print(summary)
        return 0

    # Quiet mode: print ONLY the JSON block to stdout, NOTHING else.
    # - Silence stderr (urllib3 ResourceWarnings, litellm debug logs, etc.)
    # - Silence Python warnings
    # - Extract JSON via 4-strategy fallback
    import contextlib
    import os as _os
    import sys as _sys
    import warnings

    with (
        contextlib.redirect_stderr(_os.devnull),
        warnings.catch_warnings(),
        warnings.simplefilter("ignore"),
    ):
        raw = getattr(result, "raw", str(result))
        json_block = _extract_json_block(raw)

    # Print the JSON to the REAL stdout (after the with-block exits, the
    # redirect_stderr context manager has restored stderr).
    try:
        # Pretty-print so it's human-readable AND parseable
        parsed = _sys.modules["json"].loads(json_block)
        print(_sys.modules["json"].dumps(parsed, indent=2, ensure_ascii=False))
    except Exception:
        # Last resort: dump the raw extracted block
        print(json_block)
    return 0


# ─── argument parser ─────────────────────────────────────────────────────────

# Registry: subcommand name → (description, run handler, parser-config fn)
# Adding a crew = adding one entry here + the matching branch in dispatch().
CREW_REGISTRY: dict[str, tuple[str, Callable, Callable]] = {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crewai_jobs",
        description="Multi-crew CrewAI project. Each subcommand runs one job.",
    )
    sub = parser.add_subparsers(dest="crew", required=True, metavar="<crew>")

    # Shared flags inherited by every subcommand, so `run.py news --quiet`
    # works (flag after the subcommand — the natural ergonomics).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress banners and CrewAI traces. Prints only the final "
             "output to stdout — use this when calling via SSH/n8n so the "
             "captured stdout is clean.",
    )

    # ── news ──────────────────────────────────────────────────────────────
    p_news = sub.add_parser(
        "news",
        parents=[common],
        help="Scrape a news website and summarize the top stories.",
        description="News Summarizer crew — scrape a news homepage and write a markdown brief.",
    )
    p_news.add_argument(
        "url",
        nargs="?",
        default=os.getenv("NEWS_URL", "https://www.bbc.com/news"),
        help="News site URL to scrape (default: %(default)s or $NEWS_URL)",
    )
    p_news.add_argument(
        "--limit", type=int,
        default=int(os.getenv("NEWS_LIMIT", "5")),
        help="Number of top stories to fetch (default: %(default)s or $NEWS_LIMIT)",
    )
    p_news.add_argument(
        "--output",
        default=os.getenv("OUTPUT_FILE", "output/news_summarizer/summary.md"),
        help="Output path for the final summary (default: %(default)s)",
    )
    p_news.set_defaults(handler=run_news)

    # ── jobsearch ───────────────────────────────────────────────────────
    p_js = sub.add_parser(
        "jobsearch",
        parents=[common],
        aliases=["jobs"],
        help="Search job boards for KDB+, Golang, or Python roles matching your resume.",
        description="Job Search crew — find and qualify job listings, produce JSON for n8n messaging.",
    )
    p_js.add_argument(
        "--role", choices=["kdb", "go", "python"], default="kdb",
        help="Role to search: kdb (KDB+/q), go (Golang), or python (Python) (default: kdb)",
    )
    p_js.add_argument(
        "--resume",
        default=os.getenv("JOBSEARCH_RESUME", "../agents/jobsearch/references/resume.md"),
        help="Path to resume markdown file (default: %(default)s)",
    )
    p_js.add_argument(
        "--limit", type=int,
        default=int(os.getenv("JOBSEARCH_LIMIT", "8")),
        help="Number of top results to rank (default: %(default)s)",
    )
    p_js.add_argument(
        "--output",
        default=os.getenv("JOBSEARCH_OUTPUT", "output/jobsearch/report-{role}-{date}.md"),
        help="Output path for the final report (default: %(default)s)",
    )
    p_js.set_defaults(handler=run_jobsearch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not _check_api_key():
        return 2

    # `handler` was attached via set_defaults() in the parser definition.
    return args.handler(args, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
