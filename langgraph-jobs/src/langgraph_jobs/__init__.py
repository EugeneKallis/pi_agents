"""langgraph-jobs — a multi-graph LangGraph project.

Each job lives under ``langgraph_jobs.graphs.<name>`` and is dispatched
from the CLI (``langgraph_jobs.cli``) via a subcommand:

    uv run run.py jobsearch --role python --limit 8
    uv run run.py news --limit 5

Add a new job by creating a new graph folder under ``graphs/`` and
registering a subcommand in ``cli.py``.
"""

__version__ = "0.1.0"
