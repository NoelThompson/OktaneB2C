"""Standing intents and the approval state machine.

The agent may *want* to buy something, but it cannot spend money unattended.
An intent is a durable "buy this when you can" record; releasing it into an
actual order requires a fresh, step-up-authenticated human decision.

Every transition is guarded on the expected current state, so a double-clicked
approval, a replayed resume link, and a concurrent poll cannot between them
produce two orders.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from ..config import settings

ApprovalState = Literal[
    "PENDING_STOCK",
    "REQUESTED",
    "NOTIFIED",
    "STEPUP_STARTED",
    "STEPUP_VERIFIED",
    "APPROVED",
    "EXECUTING",
    "COMPLETED",
    "STEPUP_FAILED",
    "DENIED",
    "EXPIRED",
    "FAILED",
]

TERMINAL: frozenset[str] = frozenset({"COMPLETED", "DENIED", "EXPIRED", "FAILED"})

_ALLOWED: dict[str, set[str]] = {
    "PENDING_STOCK": {"REQUESTED", "EXPIRED", "DENIED"},
    "REQUESTED": {"NOTIFIED", "FAILED", "EXPIRED"},
    "NOTIFIED": {"STEPUP_STARTED", "DENIED", "EXPIRED"},
    "STEPUP_STARTED": {"STEPUP_VERIFIED", "STEPUP_FAILED", "EXPIRED"},
    # A failed step-up is retryable: back to NOTIFIED, not to a dead end.
    "STEPUP_FAILED": {"NOTIFIED", "STEPUP_STARTED", "DENIED", "EXPIRED"},
    "STEPUP_VERIFIED": {"APPROVED", "DENIED", "EXPIRED"},
    "APPROVED": {"EXECUTING", "FAILED", "EXPIRED"},
    "EXECUTING": {"COMPLETED", "FAILED"},
}


class ApprovalConflict(RuntimeError):
    """Raised when a transition does not match the record's current state."""


@dataclass
class Intent:
    """A standing purchase intent, created at demo beat 5."""

    intent_id: str
    subject: str
    subject_email: str
    variant_sku: str
    product_name: str
    variant_label: str
    qty: int
    unit_cents: int
    max_total_cents: int
    state: str = "PENDING_STOCK"
    approval_id: str | None = None
    order_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    history: list[dict[str, Any]] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "variant_sku": self.variant_sku,
            "product_name": self.product_name,
            "variant_label": self.variant_label,
            "qty": self.qty,
            "unit_cents": self.unit_cents,
            "max_total_cents": self.max_total_cents,
            "state": self.state,
            "approval_id": self.approval_id,
            "order_id": self.order_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "history": self.history,
        }


@dataclass
class Approval:
    """An approval request. Also the thing the resume link points at."""

    approval_id: str
    intent_id: str
    subject: str
    subject_email: str
    state: str = "REQUESTED"
    # SHA-256 of the single-use resume code. The plaintext is handed out once
    # and never stored, so a leaked store cannot be replayed into an order.
    code_hash: str | None = None
    code_consumed: bool = False
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(
        default_factory=lambda: time.time() + settings.approval_ttl_seconds
    )
    updated_at: float = field(default_factory=time.time)
    # Set only after a verified step-up round trip.
    verified_acr: str | None = None
    verified_auth_time: int | None = None
    # The stepped-up ID token, used to obtain the orders:write access token so
    # the purchase is authorized by the *fresh* authentication, not the old
    # session. Held in memory only and never serialised to a response or log.
    stepup_id_token: str | None = None
    # One-time token returned to the approve page and required on the decision
    # POST. Doubles as CSRF protection and as proof the decision came from the
    # browser that completed step-up.
    decision_token_hash: str | None = None
    failure: str | None = None
    order_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at and self.state not in TERMINAL

    def public(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "intent_id": self.intent_id,
            "state": "EXPIRED" if self.expired else self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "updated_at": self.updated_at,
            "seconds_remaining": max(0, int(self.expires_at - time.time())),
            "verified_acr": self.verified_acr,
            "verified_auth_time": self.verified_auth_time,
            "failure": self.failure,
            "order_id": self.order_id,
            "history": self.history,
        }


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class ApprovalStore:
    """In-memory store with a lock. One process, one demo — but the guards are real."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._intents: dict[str, Intent] = {}
        self._approvals: dict[str, Approval] = {}
        # state token -> approval_id, so a step-up callback cannot be pointed at
        # a different approval than the one that started it.
        self._states: dict[str, tuple[str, str, str, float]] = {}

    # ---- intents ----------------------------------------------------------

    def create_intent(self, **kwargs: Any) -> Intent:
        with self._lock:
            intent = Intent(intent_id=f"int_{uuid.uuid4().hex[:12]}", **kwargs)
            intent.history.append({"at": time.time(), "state": intent.state})
            self._intents[intent.intent_id] = intent
            return intent

    def get_intent(self, intent_id: str) -> Intent | None:
        return self._intents.get(intent_id)

    def intents_for(self, subject: str) -> list[Intent]:
        return [i for i in self._intents.values() if i.subject == subject]

    def pending_for_sku(self, variant_sku: str) -> list[Intent]:
        with self._lock:
            return [
                i
                for i in self._intents.values()
                if i.variant_sku == variant_sku and i.state == "PENDING_STOCK"
            ]

    # ---- approvals --------------------------------------------------------

    def raise_approval(self, intent: Intent) -> tuple[Approval, str]:
        """Move an intent to REQUESTED and mint its single-use resume code."""
        with self._lock:
            self._transition_intent(intent, "PENDING_STOCK", "REQUESTED")
            code = secrets.token_urlsafe(32)
            approval = Approval(
                approval_id=f"apr_{uuid.uuid4().hex[:12]}",
                intent_id=intent.intent_id,
                subject=intent.subject,
                subject_email=intent.subject_email,
                code_hash=hash_code(code),
            )
            approval.history.append({"at": time.time(), "state": "REQUESTED"})
            self._approvals[approval.approval_id] = approval
            intent.approval_id = approval.approval_id
            return approval, code

    def get(self, approval_id: str) -> Approval | None:
        approval = self._approvals.get(approval_id)
        if approval and approval.expired and approval.state not in TERMINAL:
            with self._lock:
                self._set(approval, "EXPIRED")
        return approval

    def transition(
        self, approval_id: str, expected: str | set[str], to: str, **fields: Any
    ) -> Approval:
        """Guarded transition. Raises rather than silently overwriting."""
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                raise ApprovalConflict(f"unknown approval {approval_id}")
            if approval.expired and to != "EXPIRED":
                self._set(approval, "EXPIRED")
                raise ApprovalConflict(f"{approval_id} expired")

            wanted = {expected} if isinstance(expected, str) else expected
            if approval.state not in wanted:
                raise ApprovalConflict(
                    f"{approval_id} is {approval.state}, expected {sorted(wanted)}"
                )
            allowed = _ALLOWED.get(approval.state, set())
            if to not in allowed:
                raise ApprovalConflict(f"{approval.state} -> {to} is not a legal move")

            for key, value in fields.items():
                setattr(approval, key, value)
            self._set(approval, to)
            return approval

    def consume_code(self, approval_id: str, code: str) -> Approval:
        """Single-use check. Marks consumed inside the same locked section."""
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                raise ApprovalConflict("unknown approval")
            if approval.expired:
                self._set(approval, "EXPIRED")
                raise ApprovalConflict("approval expired")
            if approval.code_consumed:
                raise ApprovalConflict("resume code already used")
            if approval.code_hash is None or not secrets.compare_digest(
                approval.code_hash, hash_code(code)
            ):
                raise ApprovalConflict("resume code invalid")
            approval.code_consumed = True
            return approval

    def reissue_code(self, approval_id: str) -> str:
        """Mint a replacement resume code after a failed step-up.

        The emailed link stays strictly single-use; this new code is handed only
        to the browser that just failed, so a shopper who mistypes a second
        factor can retry without the original link becoming replayable.
        """
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                raise ApprovalConflict(f"unknown approval {approval_id}")
            if approval.state != "STEPUP_FAILED":
                raise ApprovalConflict(
                    f"{approval_id} is {approval.state}, cannot reissue a resume code"
                )
            if approval.expired:
                self._set(approval, "EXPIRED")
                raise ApprovalConflict("approval expired")

            code = secrets.token_urlsafe(32)
            approval.code_hash = hash_code(code)
            approval.code_consumed = False
            self._set(approval, "NOTIFIED")
            return code

    # ---- step-up state binding -------------------------------------------

    def bind_state(
        self, state: str, approval_id: str, verifier: str, nonce: str
    ) -> None:
        with self._lock:
            self._states[state] = (approval_id, verifier, nonce, time.time() + 600)

    def take_state(self, state: str) -> tuple[str, str, str] | None:
        """One-shot lookup: a `state` value cannot be replayed."""
        with self._lock:
            entry = self._states.pop(state, None)
        if entry is None or entry[3] < time.time():
            return None
        return entry[0], entry[1], entry[2]

    # ---- internals --------------------------------------------------------

    def _set(self, approval: Approval, to: str) -> None:
        approval.state = to
        approval.updated_at = time.time()
        approval.history.append({"at": approval.updated_at, "state": to})
        intent = self._intents.get(approval.intent_id)
        if intent is not None:
            intent.state = to
            intent.updated_at = approval.updated_at
            intent.order_id = approval.order_id
            intent.history.append({"at": approval.updated_at, "state": to})

    def _transition_intent(self, intent: Intent, expected: str, to: str) -> None:
        if intent.state != expected:
            raise ApprovalConflict(f"{intent.intent_id} is {intent.state}, expected {expected}")
        intent.state = to
        intent.updated_at = time.time()
        intent.history.append({"at": intent.updated_at, "state": to})


store = ApprovalStore()
