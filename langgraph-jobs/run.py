#!/usr/bin/env python3
"""Convenience launcher — runs the langgraph_jobs CLI from the project root.

    python run.py jobsearch --role python --limit 8
    python run.py jobsearch --role go --quiet

Works whether or not the package is installed.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from langgraph_jobs.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
