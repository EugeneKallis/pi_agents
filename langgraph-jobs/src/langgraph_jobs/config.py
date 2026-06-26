"""Shared runtime config: opencode-go API key, model, base URL.

Same resolution order as crewai-jobs: env var → pi auth file → None.
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
    return os.getenv("OPENCODE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@lru_cache(maxsize=1)
def key_source() -> str:
    if os.getenv("OPENCODE_API_KEY"):
        return "env"
    if get_api_key() is not None:
        return "pi-auth"
    return "missing"
