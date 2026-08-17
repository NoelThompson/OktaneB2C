"""The token-exchange contract.

One interface, several implementations (mock local AS, raw ID-JAG port, Okta
SDK). The agent's business logic only ever sees ``TokenExchanger``, so flipping
from a local demo to a real org changes configuration, not code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TraceEvent:
    """One step in the on-behalf-of chain, rendered in the telemetry drawer."""

    kind: str  # user_token | id_jag | access_token | mcp_call | mcp_denied | stepup | note
    label: str
    detail: str = ""
    ok: bool = True
    claims: dict[str, Any] = field(default_factory=dict)
    at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "detail": self.detail,
            "ok": self.ok,
            "claims": self.claims,
            "at": self.at,
        }


@dataclass
class ExchangeResult:
    """A scoped access token plus the trace of how it was obtained."""

    access_token: str
    audience: str
    scopes: tuple[str, ...]
    expires_at: float
    subject: str
    actor: str
    issuer: str
    trace: list[TraceEvent] = field(default_factory=list)

    @property
    def expired(self) -> bool:
        # 30s of slack so a token cannot die between the check and the call.
        return time.time() >= self.expires_at - 30


class TokenExchangeError(RuntimeError):
    """Carries Okta's ``error_description`` verbatim; the drawer shows it raw."""

    def __init__(self, stage: str, message: str, detail: str = "") -> None:
        super().__init__(f"{stage}: {message}")
        self.stage = stage
        self.error = message
        self.detail = detail


class TokenExchanger(Protocol):
    """Exchange a user's ID token for an access token scoped to one audience."""

    name: str

    async def exchange(
        self, id_token: str, audience: str, scopes: tuple[str, ...]
    ) -> ExchangeResult: ...
