#!/usr/bin/env python3
"""Convenience launcher — runs the crewai_jobs CLI from the project root.

    python run.py news                      # news crew, .env defaults
    python run.py news https://apnews.com   # different site
    python run.py news --limit 10           # more stories
    python run.py news --quiet              # clean stdout (for n8n/SSH)

Works whether or not the package is installed (falls back to adding
./src to sys.path).
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from crewai_jobs.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
