"""Anthropic wrapper with a deterministic fallback.

`available` is false when no API key is configured, and every caller has a
non-LLM path. The demo must be walkable before a key exists.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..config import settings

log = logging.getLogger("oktane.llm")

_client: Any = None


def available() -> bool:
    return bool(settings.anthropic_api_key)


def _get_client() -> Any:
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic

        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def complete(system: str, user: str, *, max_tokens: int = 400) -> str | None:
    """Returns None on any failure so callers fall back rather than error."""
    if not available():
        return None
    try:
        message = await _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        ).strip()
    except Exception as exc:  # noqa: BLE001 — never let the demo die on the LLM
        log.warning("anthropic call failed, falling back: %s", exc)
        return None


async def complete_json(system: str, user: str) -> dict[str, Any] | None:
    raw = await complete(system, user, max_tokens=300)
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
