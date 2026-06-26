"""Custom CrewAI tool that scrapes a news website and returns the top stories.

Uses plain HTTP + BeautifulSoup. Works with most traditional news sites
(BBC, Reuters, AP, Guardian, Al Jazeera, ...). Heavily JavaScript-driven
sites (some local/regional outlets) may not render — for those, swap in
Playwright or a hosted scraper.

The agent is responsible for figuring out *what* to do with the output —
this tool just returns a clean, structured text block it can read.
"""

from __future__ import annotations

from typing import Type
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class NewsScraperInput(BaseModel):
    """Input schema for NewsScraperTool."""

    url: str = Field(..., description="Absolute URL of the news website homepage to scrape")
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of stories to return (1-20)",
    )


class NewsScraperTool(BaseTool):
    """Scrapes a news website and returns the top headlines with summaries and links.

    Returns a numbered text list, one story per block:

        1. Headline text
           Short description if available.
           Link: https://...

    Designed to be called once per site — the agent reads the result and
    decides which stories are worth a closer look.
    """

    name: str = "News Scraper"
    description: str = (
        "Scrapes the homepage of a news website and returns the top headlines "
        "with short descriptions and source links. Input: url (string) and "
        "optional limit (1-20, default 5). Output: numbered text list of stories."
    )
    args_schema: Type[BaseModel] = NewsScraperInput

    # Configurable via subclass / env, but sane defaults:
    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    TIMEOUT: int = 20

    def _run(self, url: str, limit: int = 5) -> str:
        try:
            html = self._fetch(url)
        except requests.RequestException as e:
            return f"Error fetching {url}: {e}"

        soup = BeautifulSoup(html, "lxml")
        stories = self._extract_stories(soup, url, limit)

        if not stories:
            return (
                f"No stories found at {url}. "
                "The site may render content via JavaScript or use an "
                "unusual markup structure. Try a different news source."
            )

        return self._format(soup.title.string.strip() if soup.title else url, url, stories)

    # ── internals ────────────────────────────────────────────────────────────

    def _fetch(self, url: str) -> str:
        resp = requests.get(
            url,
            headers={"User-Agent": self.USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            timeout=self.TIMEOUT,
        )
        resp.raise_for_status()
        return resp.text

    def _extract_stories(self, soup: BeautifulSoup, base_url: str, limit: int) -> list[dict]:
        """Pull headlines, descriptions, and links out of the page.

        Strategy: walk the DOM, look for <h1>/<h2>/<h3> with reasonable text
        length and a nearby <a> tag. De-dupe by headline text. Capture a
        short description from the closest <p> ancestor if one exists.
        """
        seen: set[str] = set()
        stories: list[dict] = []

        for heading in soup.find_all(["h1", "h2", "h3"]):
            headline = heading.get_text(strip=True)

            # Filter noise: too short, too long, or repeated nav/UI text
            if not self._is_usable_headline(headline):
                continue
            if headline in seen:
                continue
            seen.add(headline)

            link = self._find_link(heading, base_url)
            description = self._find_description(heading)

            stories.append(
                {
                    "headline": headline,
                    "description": description,
                    "url": link,
                }
            )

            if len(stories) >= limit:
                break

        return stories

    @staticmethod
    def _is_usable_headline(text: str) -> bool:
        # Heuristics tuned for news homepages:
        #   15-300 chars (filters out nav items, filters out huge block text)
        #   no all-caps (filters out section labels like "MOST READ")
        return 15 <= len(text) <= 300 and not text.isupper()

    @staticmethod
    def _find_link(heading, base_url: str) -> str:
        # Look up the tree for an anchor (most common pattern), or
        # down into the heading for an inline link.
        anchor = heading.find_parent("a") or heading.find("a")
        if not anchor or not anchor.get("href"):
            return ""
        href = anchor["href"]
        return href if href.startswith(("http://", "https://")) else urljoin(base_url, href)

    @staticmethod
    def _find_description(heading) -> str:
        # Walk up to the nearest article/container, grab the first <p>.
        for parent in heading.parents:
            if parent.name in {"article", "section", "li", "div"}:
                p = parent.find("p")
                if p:
                    text = p.get_text(strip=True)
                    if 20 <= len(text) <= 400:
                        return text
                # Don't keep climbing forever
                if parent.name in {"article", "section"}:
                    break
        return ""

    @staticmethod
    def _format(site_name: str, source_url: str, stories: list[dict]) -> str:
        lines = [f"Top {len(stories)} stories from {site_name} ({source_url}):", ""]
        for i, s in enumerate(stories, 1):
            lines.append(f"{i}. {s['headline']}")
            if s["description"]:
                lines.append(f"   {s['description']}")
            if s["url"]:
                lines.append(f"   Link: {s['url']}")
            lines.append("")
        return "\n".join(lines)
