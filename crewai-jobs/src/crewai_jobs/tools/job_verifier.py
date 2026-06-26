"""Job verifier tool — checks if a job posting is still accepting applicants.

Fetches a job posting URL with ``requests`` and inspects the page for
signs the position is still open: "Apply now", "Posted X days ago", etc.
Returns a structured verdict: ACTIVE, UNCERTAIN, or CLOSED + evidence.
"""

from __future__ import annotations

from typing import Type

import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class JobVerifierInput(BaseModel):
    url: str = Field(..., description="Absolute URL of the job posting to verify")


class JobVerifierTool(BaseTool):
    """Fetch a job posting URL and determine if it's still accepting applicants."""

    name: str = "Job Verifier"
    description: str = (
        "Fetches a job posting URL and checks if the position is still accepting "
        "applicants. Returns ACTIVE, UNCERTAIN, or CLOSED + a short evidence snippet. "
        "Input: url (string). Use this before presenting any job to the user."
    )
    args_schema: Type[BaseModel] = JobVerifierInput

    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    TIMEOUT: int = 15

    # ── signals ────────────────────────────────────────────────────────────

    ACTIVE_SIGNALS: list[str] = [
        "apply now", "apply today", "apply for this job",
        "submit your application", "click to apply", "easy apply",
        "posted", "days ago", "hours ago", "just posted",
        "urgently hiring", "actively hiring", "hiring now",
        "quick apply",
    ]

    CLOSED_SIGNALS: list[str] = [
        "position has been filled", "no longer accepting",
        "this position has been closed", "job closed",
        "position filled", "role filled", "hiring complete",
        "not accepting applications", "expired", "archived",
        "no longer available",
    ]

    def _run(self, url: str) -> str:
        try:
            with requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            return f"UNCERTAIN | Could not fetch {url}: {e}"

        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True).lower()

        active_hits = [s for s in self.ACTIVE_SIGNALS if s in text]
        closed_hits = [s for s in self.CLOSED_SIGNALS if s in text]

        if closed_hits:
            return f"CLOSED | Found: {', '.join(closed_hits[:3])}"
        if active_hits:
            return f"ACTIVE | Found: {', '.join(active_hits[:3])}"
        return "UNCERTAIN | No clear active/closed signals in page text."
