"""Job tracker tool — remembers which job URLs have already been seen."""

from __future__ import annotations

import json
from pathlib import Path


class JobTrackerTool:
    """Track which job URLs have already been seen across runs."""

    @staticmethod
    def _data_path() -> Path:
        here = Path(__file__).resolve()
        return here.parent.parent.parent.parent / "data" / "seen-jobs.json"

    @staticmethod
    def read() -> str:
        path = JobTrackerTool._data_path()
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
    def read_urls() -> list[str]:
        path = JobTrackerTool._data_path()
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    @staticmethod
    def add(urls: list[str]) -> str:
        path = JobTrackerTool._data_path()
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

        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return f"Recorded {after - before} new job URL(s). Total seen: {after}."
