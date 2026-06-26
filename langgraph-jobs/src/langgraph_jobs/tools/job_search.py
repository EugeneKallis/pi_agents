"""Job search tool — searches job boards via DuckDuckGo (ddgs).

Same logic as the crewai version, minus the BaseTool wrapper.
"""

from __future__ import annotations


class JobSearchTool:
    """Search job boards using DuckDuckGo and return structured listings."""

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
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(full_query, max_results=limit + 5):
                    url = r.get("href", "")
                    if not url or any(prev.get("url") == url for prev in results):
                        continue
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": url,
                    })
                    if len(results) >= limit:
                        break
        except Exception as e:
            return f"Search error: {e}"

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
        """Return raw list of dicts (title, snippet, url) — for programmatic use."""
        try:
            from ddgs import DDGS
        except ImportError:
            return []

        filters = JobSearchTool._filters_for_role(role)
        full_query = f"{query} {filters}"

        results: list[dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(full_query, max_results=limit + 5):
                    url = r.get("href", "")
                    if not url:
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
