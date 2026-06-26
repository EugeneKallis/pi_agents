"""Shared runtime config: opencode-go API key, model, base URL.

Resolution order for the API key:

1. ``OPENCODE_API_KEY`` env var (or whatever ``.env`` sets)
2. ``~/.pi/agent/auth.json`` — the pi-coding-agent auth file. This means
   pi_agents users can run any crew without extra setup; their existing
   opencode-go key is picked up automatically.
3. ``None`` — caller is expected to error out with a clear message.

This module is shared across all crews — every crew's ``build_llm()``
calls into ``get_api_key()`` here.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4-flash"
_PI_AUTH_PATH = Path.home() / ".pi" / "agent" / "auth.json"


def get_api_key() -> str | None:
    """Return the opencode-go API key, or None if not found."""
    key = os.getenv("OPENCODE_API_KEY")
    if key:
        return key

    if not _PI_AUTH_PATH.exists():
        return None

    try:
        data = json.loads(_PI_AUTH_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    entry = data.get("opencode-go") or {}
    return entry.get("key") or None


def get_model() -> str:
    return os.getenv("MODEL", DEFAULT_MODEL)


def get_base_url() -> str:
    # Strip trailing slash — openai-compat clients care about this.
    return os.getenv("OPENCODE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@lru_cache(maxsize=1)
def key_source() -> str:
    """Where the API key came from: 'env', 'pi-auth', or 'missing'."""
    if os.getenv("OPENCODE_API_KEY"):
        return "env"
    if get_api_key() is not None:
        return "pi-auth"
    return "missing"
