"""Job search tool — searches job boards via DuckDuckGo (ddgs).

Same logic as the crewai version, minus the BaseTool wrapper.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse


class JobSearchTool:
    """Search job boards using DuckDuckGo and return structured listings."""

    # ── URL classifiers ──────────────────────────────────────────────────

    # Patterns that indicate an INDIVIDUAL job posting (not a search/SEO page)
    _JOB_URL_PATTERNS: list[re.Pattern] = [
        # LinkedIn individual job postings
        re.compile(r"linkedin\.com/jobs/view/", re.I),
        # Indeed viewjob pages
        re.compile(r"indeed\.com/(viewjob|.*/jobs/[^/]+/)", re.I),
        re.compile(r"indeed\.com/rc/clk\?jk=", re.I),
        # ZipRecruiter specific job pages
        re.compile(r"ziprecruiter\.com/jobs/[^/]+/[a-f0-9\-]+$", re.I),
        re.compile(r"ziprecruiter\.com/job/", re.I),
        # Glassdoor job listing pages
        re.compile(r"glassdoor\.com/job-listing/", re.I),
        re.compile(r"glassdoor\.com/partner/jobListing", re.I),
        # Dice job detail pages
        re.compile(r"dice\.com/job-detail/", re.I),
        re.compile(r"dice\.com/jobs/detail/", re.I),
    ]

    # Patterns that indicate a search/SEO/aggregate page (NOT an individual job)
    _NON_JOB_URL_PATTERNS: list[re.Pattern] = [
        re.compile(r"linkedin\.com/jobs/(search|collections|companies)", re.I),
        # LinkedIn SEO pages: /jobs/{keyword}-jobs-{location}
        re.compile(r"linkedin\.com/jobs/[^/]+-jobs", re.I),
        re.compile(r"linkedin\.com/jobs/[^/]+-developer", re.I),
        re.compile(r"linkedin\.com/jobs/[^/]+-engineer", re.I),
        re.compile(r"indeed\.com/(jobs\?|q-)", re.I),
        re.compile(r"indeed\.com/career/", re.I),
        re.compile(r"ziprecruiter\.com/(jobs/search|jobs\?|candidate/search)", re.I),
        re.compile(r"glassdoor\.com/Job/[^/]+-jobs", re.I),
        re.compile(r"glassdoor\.com/Search/", re.I),
        re.compile(r"glassdoor\.com/Explore/", re.I),
        re.compile(r"dice\.com/jobs\?", re.I),
        re.compile(r"dice\.com/jobs/[^/]+-jobs", re.I),
    ]

    @staticmethod
    def _is_job_listing_url(url: str) -> bool:
        """Return True if the URL looks like an individual job listing."""
        if not url:
            return False
        parsed = urlparse(url)
        # Check against host+path+query (some patterns span query params)
        full = f"{parsed.netloc}{parsed.path}{'?' if parsed.query else ''}{parsed.query}"
        # Must match at least one "this is a job" pattern
        if not any(p.search(full) for p in JobSearchTool._JOB_URL_PATTERNS):
            return False
        # Must NOT match any "this is a search page" pattern
        if any(p.search(full) for p in JobSearchTool._NON_JOB_URL_PATTERNS):
            return False
        return True

    # ── role filters ─────────────────────────────────────────────────────

    @staticmethod
    def _filters_for_role(role: str) -> str:
        base = "job salary US"
        if role == "kdb":
            return f"{base} KDB+ q remote"
        elif role == "go":
            return f"{base} Golang Go backend engineer remote"
        elif role == "python":
            return f"{base} Python backend engineer remote"
        return base

    @staticmethod
    def search(query: str, role: str = "kdb", limit: int = 10) -> str:
        try:
            from ddgs import DDGS
        except ImportError:
            return "Error: ddgs not installed. Run `uv sync` first."

        filters = JobSearchTool._filters_for_role(role)
        full_query = f"{query} {filters}"

        results: list[dict] = []
        seen: set[str] = set()
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(full_query, max_results=limit + 10):
                    url = r.get("href", "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": url,
                    })
                    if len(results) >= limit:
                        break
        except Exception as e:
            return f"Search error: {e}"

        # Filter to individual job listings only
        results = [r for r in results if JobSearchTool._is_job_listing_url(r["url"])]

        if not results:
            return f"No job listings found for query: {full_query}"

        lines = [f"Search results for: {full_query}", f"Found {len(results)} listings:\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['snippet'][:200]}")
            lines.append(f"   URL: {r['url']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def search_raw(query: str, role: str = "kdb", limit: int = 10) -> list[dict]:
        """Return raw list of dicts (title, snippet, url) — for programmatic use.

        Only returns URLs classified as individual job listings (not search pages).
        """
        try:
            from ddgs import DDGS
        except ImportError:
            return []

        filters = JobSearchTool._filters_for_role(role)
        full_query = f"{query} {filters}"

        results: list[dict] = []
        seen: set[str] = set()
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(full_query, max_results=limit + 10):
                    url = r.get("href", "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    # Only collect URLs that look like individual job postings
                    if not JobSearchTool._is_job_listing_url(url):
                        continue
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": url,
                    })
                    if len(results) >= limit:
                        break
        except Exception:
            pass
        return results
