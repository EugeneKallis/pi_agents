"""crewai-jobs — a multi-crew CrewAI project.

Each crew lives under ``crewai_jobs.crews.<name>`` and is dispatched from
the CLI (``crewai_jobs.cli``) via a subcommand:

    uv run run.py news --limit 5      # → crews.news_summarizer

Add a new job by creating a new crew folder under ``crews/`` and
registering a subcommand in ``cli.py``. See README "Adding a new crew".
"""

__version__ = "0.2.0"
