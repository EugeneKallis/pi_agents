"""Page fetching tool for LLM agents — fetches URLs and returns text content.

The fetch_page tool gives an LLM agent the ability to read actual
job listing pages, extract full descriptions, and find real apply URLs.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
_TIMEOUT = 15
_MAX_CHARS = 8000


def fetch_page(url: str, max_chars: int = _MAX_CHARS) -> str:
    """Fetch a web page and return its text content.

    Args:
        url: The full URL to fetch.
        max_chars: Max characters to return (prevents token overflow).

    Returns:
        Clean text content of the page, or an error message.
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return f"Error: Request to {url} timed out after {_TIMEOUT}s."
    except requests.exceptions.RequestException as e:
        return f"Error fetching {url}: {e}"

    # Parse and clean
    try:
        soup = BeautifulSoup(response.text, "lxml")
    except Exception:
        soup = BeautifulSoup(response.text, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse repeated blank lines
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... content truncated at character limit ...]"

    return text
