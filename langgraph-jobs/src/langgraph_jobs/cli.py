"""CLI dispatcher: `python -m langgraph_jobs <job-name> [args]`.

Each job gets a subcommand. To add a new job:

1. Create ``langgraph_jobs/graphs/<name>/graph.py`` with a ``run_<name>()`` fn.
2. Add a subparser below + a handler in ``dispatch()``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from langgraph_jobs.config import get_api_key, get_base_url, get_model, key_source  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────


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


def _run_jobsearch(args: argparse.Namespace, quiet: bool) -> int:
    from langgraph_jobs.graphs.jobsearch import run_jobsearch
    from datetime import date

    today = date.today().isoformat()

    if not quiet:
        print(f"→ LLM: {get_model()}  via  {get_base_url()}  (key from: {key_source()})")
        print(f"→ Job search: {args.role.upper()} roles (limit={args.limit})")
        print(f"→ Resume: {args.resume}")
        print(f"→ Results will be written to output/jobsearch/\n")

    output = args.output.replace("{role}", args.role).replace("{date}", today)
    result = run_jobsearch(
        role=args.role,
        resume_path=str(Path(args.resume).resolve()),
        limit=args.limit,
        quiet=quiet,
        output=output,
    )

    if quiet:
        print(result)
    else:
        print(f"\n✓ Done. Results written to output/jobsearch/")
        print("─" * 60)
        print(result)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="langgraph_jobs",
        description="Multi-graph LangGraph project. Each subcommand runs one job.",
    )
    sub = parser.add_subparsers(dest="job", required=True, metavar="<job>")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress banners. Prints only the final output to stdout.",
    )

    # ── jobsearch ────────────────────────────────────────────────────────
    p_js = sub.add_parser(
        "jobsearch",
        parents=[common],
        aliases=["jobs"],
        help="Search job boards for KDB+, Golang, or Python roles.",
        description="Job Search graph — find and qualify job listings, produce JSON for n8n messaging.",
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not _check_api_key():
        return 2

    import contextlib
    import io as _io
    import warnings

    ctx = contextlib.redirect_stderr(_io.StringIO()) if args.quiet else contextlib.nullcontext()
    with ctx, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _run_jobsearch(args, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
