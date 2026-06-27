"""Web search tool for LLM agents — wraps DuckDuckGo search.

The search_web tool is designed to be consumed by a LangChain agent
(create_react_agent). The LLM drives the query strategy naturally.
"""

from __future__ import annotations


def search_web(query: str, limit: int = 10) -> str:
    """Search the web for job listings. Returns structured results.

    Args:
        query: Natural language search query (no special syntax needed).
        limit: Max results to return.

    Returns:
        Formatted text with Title, Snippet, URL per result.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return "Error: ddgs not installed."

    results: list[str] = []
    seen: set[str] = set()
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit + 5):
                url = r.get("href", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                results.append(
                    f"Title: {r.get('title', '')}\n"
                    f"Snippet: {r.get('body', '')}\n"
                    f"URL: {url}"
                )
                if len(results) >= limit:
                    break
    except Exception as e:
        return f"Search error: {e}"

    if not results:
        return f"No results found for: {query}"

    return "\n---\n".join(results)
