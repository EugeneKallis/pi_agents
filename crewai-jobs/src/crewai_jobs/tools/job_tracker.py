"""Job tracker tool — remembers which job URLs have already been seen.

Reads/writes a JSON file (``data/seen-jobs.json``) so the same job
never appears in search results twice. Separate file from the pi
agent's ``references/seen-jobs.json`` to avoid cross-contamination.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class JobTrackerInput(BaseModel):
    action: str = Field(
        ...,
        description="'read' to get previously seen URLs, or 'add' to record new ones.",
    )
    urls: list[str] = Field(
        default_factory=list,
        description="List of job URLs to record. Required when action='add'.",
    )


class JobTrackerTool(BaseTool):
    """Track which job URLs have already been seen across runs."""

    name: str = "Job Tracker"
    description: str = (
        "Reads or writes the list of previously seen job URLs. "
        "Input: action ('read' or 'add') and urls (list of URLs, for 'add'). "
        "Use 'read' before searching to get seen URLs; use 'add' after presenting "
        "results to record new URLs so they never appear again."
    )
    args_schema: Type[BaseModel] = JobTrackerInput

    # Resolved relative to the project root (crewai-jobs/)
    _DATA_PATH: Path | None = None

    @property
    def data_path(self) -> Path:
        if self._DATA_PATH is None:
            # crew.py runs from src/crewai_jobs/crews/jobsearch/,
            # tools live in src/crewai_jobs/tools/ — walk up to project root.
            here = Path(__file__).resolve()
            # .../crewai-jobs/src/crewai_jobs/tools/job_tracker.py
            self._DATA_PATH = here.parent.parent.parent.parent / "data" / "seen-jobs.json"
        return self._DATA_PATH

    def _run(self, action: str, urls: list[str] | None = None) -> str:
        if urls is None:
            urls = []
        path = self.data_path

        if action == "read":
            return self._read(path)
        elif action == "add":
            return self._add(path, urls)
        else:
            return f"Unknown action '{action}'. Use 'read' or 'add'."

    @staticmethod
    def _read(path: Path) -> str:
        if not path.exists():
            return "No previously seen jobs (tracker file does not exist yet)."
        try:
            seen = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return "No previously seen jobs (tracker file is empty or corrupt)."
        if not seen:
            return "No previously seen jobs (tracker file is empty)."
        urls = "\n".join(f"  - {u}" for u in seen)
        return f"Previously seen job URLs ({len(seen)}):\n{urls}"

    @staticmethod
    def _add(path: Path, urls: list[str]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[str] = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = []

        before = len(existing)
        for url in urls:
            if url not in existing:
                existing.append(url)
        after = len(existing)
        new_count = after - before

        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return f"Recorded {new_count} new job URL(s). Total seen: {after}."
