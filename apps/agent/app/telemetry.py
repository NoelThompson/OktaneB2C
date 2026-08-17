"""Per-approval trace buffer.

The telemetry drawer is how a technical audience sees that the authorization
chain is real rather than narrated, so events raised outside a chat turn (the
restock, the step-up, the order) are collected here and polled alongside the
approval state.

Only claim values are recorded. Tokens are never stored or logged.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque

from .tokens.base import TraceEvent

_MAX = 60
_lock = threading.Lock()
_by_approval: dict[str, deque[TraceEvent]] = defaultdict(lambda: deque(maxlen=_MAX))
_global: deque[TraceEvent] = deque(maxlen=_MAX)


def record(approval_id: str, event: TraceEvent) -> None:
    with _lock:
        _by_approval[approval_id].append(event)
        _global.append(event)


def for_approval(approval_id: str) -> list[dict[str, object]]:
    with _lock:
        return [event.public() for event in _by_approval.get(approval_id, ())]


def recent() -> list[dict[str, object]]:
    with _lock:
        return [event.public() for event in _global]
