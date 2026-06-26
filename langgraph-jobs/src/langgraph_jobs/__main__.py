"""Allow `python -m langgraph_jobs` to run the CLI."""

from langgraph_jobs.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
