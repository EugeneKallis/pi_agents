"""Job verifier tool — checks if a job posting is still accepting applicants."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup


class JobVerifierTool:
    """Fetch a job posting URL and determine if it's still accepting applicants."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    TIMEOUT = 8

    ACTIVE_SIGNALS: list[str] = [
        "apply now", "apply today", "apply for this job",
        "submit your application", "click to apply", "easy apply",
        "posted", "days ago", "hours ago", "just posted",
        "urgently hiring", "actively hiring", "hiring now", "quick apply",
    ]

    CLOSED_SIGNALS: list[str] = [
        "position has been filled", "no longer accepting",
        "this position has been closed", "job closed",
        "position filled", "role filled", "hiring complete",
        "not accepting applications", "expired", "archived",
        "no longer available",
    ]

    @staticmethod
    def verify(url: str) -> str:
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": JobVerifierTool.USER_AGENT},
                timeout=JobVerifierTool.TIMEOUT,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            return f"UNCERTAIN | Could not fetch {url}: {e}"

        text = soup.get_text(" ", strip=True).lower()
        active_hits = [s for s in JobVerifierTool.ACTIVE_SIGNALS if s in text]
        closed_hits = [s for s in JobVerifierTool.CLOSED_SIGNALS if s in text]

        if closed_hits:
            return f"CLOSED | Found: {', '.join(closed_hits[:3])}"
        if active_hits:
            return f"ACTIVE | Found: {', '.join(active_hits[:3])}"
        return "UNCERTAIN | No clear active/closed signals in page text."
