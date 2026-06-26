"""Job search tool — searches job boards via DuckDuckGo.

Uses the ``duckduckgo_search`` library (free, no API key). Searches with
site-specific queries across LinkedIn, Indeed, ZipRecruiter, etc., and
returns structured results the agent can consume.
"""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class JobSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="Search query for job listings. Use site-specific queries "
        "like 'site:linkedin.com/jobs KDB developer remote' for targeted results.",
    )
    role: str = Field(
        default="kdb",
        description="Role key: 'kdb', 'go', or 'python'. Used to pick search strategy.",
    )
    limit: int = Field(
        default=10,
        ge=3,
        le=25,
        description="Number of search results to return (3-25, default 10).",
    )


class JobSearchTool(BaseTool):
    """Search job boards using DuckDuckGo and return structured listings."""

    name: str = "Job Search"
    description: str = (
        "Searches for job listings across the web using site-specific queries. "
        "Input: query (string like 'site:linkedin.com/jobs KDB developer remote'), "
        "role ('kdb', 'go', or 'python'), and optional limit (3-25). "
        "Output: numbered list of job listings with title, snippet, and URL."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, query: str, role: str = "kdb", limit: int = 10) -> str:
        try:
            from ddgs import DDGS
        except ImportError:
            return (
                "Error: ddgs not installed. "
                "Run `uv sync` first."
            )

        filters = self._filters_for_role(role)
        full_query = f"{query} {filters}"

        results: list[dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(full_query, max_results=limit + 5):
                    url = r.get("href", "")
                    if not url or any(prev.get("url") == url for prev in results):
                        continue
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "url": url,
                        }
                    )
                    if len(results) >= limit:
                        break
        except Exception as e:
            return f"Search error: {e}"

        if not results:
            return f"No job listings found for query: {full_query}"

        return self._format(full_query, results)

    @staticmethod
    def _filters_for_role(role: str) -> str:
        """Append role-specific job and location filters."""
        base = "job salary US"
        if role == "kdb":
            return f"{base} KDB+ q remote"
        elif role == "go":
            return f"{base} Golang Go backend engineer remote"
        elif role == "python":
            return f"{base} Python backend engineer remote"
        return base

    @staticmethod
    def _format(query: str, results: list[dict]) -> str:
        lines = [
            f"Search results for: {query}",
            f"Found {len(results)} listings:\n",
        ]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['snippet'][:200]}")
            lines.append(f"   URL: {r['url']}")
            lines.append("")
        return "\n".join(lines)
