"""Approvals: polling, step-up, and the guarded release of an order.

The route order matters for the demo's credibility. Nothing here can place an
order without a step-up that this process verified itself, and the order call
uses a token derived from that fresh authentication.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .. import mcp_client
from ..approvals import stepup
from ..approvals.store import ApprovalConflict, store
from ..config import settings
from ..telemetry import record
from ..tokens.base import TraceEvent

log = logging.getLogger("oktane.approvals")
router = APIRouter(tags=["approvals"])


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@router.get("/approvals/{approval_id}")
def poll(approval_id: str) -> dict[str, Any]:
    """The CIBA-shaped poll the chat panel uses while it waits for the shopper."""
    approval = store.get(approval_id)
    if approval is None:
        raise HTTPException(404, "unknown approval")

    intent = store.get_intent(approval.intent_id)
    return {
        "approval": approval.public(),
        "intent": intent.public() if intent else None,
    }


@router.get("/auth/stepup/start")
def stepup_start(approval_id: str, code: str) -> RedirectResponse:
    """Consume the resume code and bounce the shopper into a forced re-auth."""
    try:
        url = stepup.start(approval_id, code)
    except stepup.StepUpError as exc:
        record(
            approval_id,
            TraceEvent(
                kind="stepup",
                label="Step-up refused",
                detail=f"{exc.code}: {exc.detail}",
                ok=False,
            ),
        )
        return RedirectResponse(
            f"{settings.web_base}/approve/{approval_id}?"
            + urlencode({"error": exc.code, "detail": exc.detail}),
            status_code=302,
        )

    record(
        approval_id,
        TraceEvent(
            kind="stepup",
            label="Step-up requested",
            detail=f"acr_values={settings.required_acr} max_age=0 prompt=login",
            claims={"pkce": "S256", "resume_code": "consumed"},
        ),
    )
    return RedirectResponse(url, status_code=302)


@router.get("/auth/stepup/callback")
async def stepup_callback(
    state: str = "",
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Verify the round trip, then hand the browser a one-time decision token."""
    try:
        approval, verified = await stepup.complete(state, code, error, error_description)
    except stepup.StepUpError as exc:
        log.warning("step-up failed: %s", exc)
        params = {"error": exc.code, "detail": exc.detail}
        if exc.approval_id:
            record(
                exc.approval_id,
                TraceEvent(
                    kind="stepup",
                    label="Step-up rejected",
                    detail=f"{exc.code}: {exc.detail}",
                    ok=False,
                ),
            )
            # A failed factor is a retry, not a dead end.
            try:
                params["retry"] = store.reissue_code(exc.approval_id)
            except ApprovalConflict as conflict:
                log.info("no retry offered for %s: %s", exc.approval_id, conflict)
        return RedirectResponse(
            f"{settings.web_base}/approve/{exc.approval_id or 'unknown'}?"
            + urlencode(params),
            status_code=302,
        )

    decision_token = secrets.token_urlsafe(32)
    approval.decision_token_hash = _hash(decision_token)
    approval.stepup_id_token = verified.id_token

    record(
        approval.approval_id,
        TraceEvent(
            kind="stepup",
            label="Step-up verified",
            detail=f"acr={verified.acr} auth_time fresh",
            claims={
                "sub": verified.subject,
                "acr": verified.acr,
                "auth_time": verified.auth_time,
                "checks": [
                    "pkce",
                    "state_bound",
                    "sub_matches_approval",
                    "nonce",
                    "acr_required",
                    "auth_time_fresh",
                    "resume_code_single_use",
                ],
            },
        ),
    )

    return RedirectResponse(
        f"{settings.web_base}/approve/{approval.approval_id}?"
        + urlencode({"dt": decision_token}),
        status_code=302,
    )


class Decision(BaseModel):
    decision: str
    decision_token: str


@router.post("/approvals/{approval_id}/decision")
async def decide(approval_id: str, body: Decision) -> dict[str, Any]:
    """Release or refuse the order. POST-only, and only with the one-time token.

    A GET approve link would be prefetchable by a mail scanner, which would let
    a link previewer buy a basketball.
    """
    approval = store.get(approval_id)
    if approval is None:
        raise HTTPException(404, "unknown approval")
    if approval.decision_token_hash is None or not secrets.compare_digest(
        approval.decision_token_hash, _hash(body.decision_token)
    ):
        raise HTTPException(403, "decision token invalid — complete step-up first")

    if body.decision == "deny":
        try:
            store.transition(approval_id, "STEPUP_VERIFIED", "DENIED")
        except ApprovalConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        approval.decision_token_hash = None
        approval.stepup_id_token = None
        record(
            approval_id,
            TraceEvent(kind="note", label="Shopper denied the purchase", ok=False),
        )
        return {"approval": approval.public()}

    if body.decision != "approve":
        raise HTTPException(400, "decision must be approve or deny")

    intent = store.get_intent(approval.intent_id)
    if intent is None:
        raise HTTPException(500, "approval has no intent")

    # Burn the token before doing any work: a double-click must not reach
    # orders.create twice, and the guarded transition below is the second line
    # of defence.
    approval.decision_token_hash = None
    id_token = approval.stepup_id_token
    approval.stepup_id_token = None
    if id_token is None:
        raise HTTPException(409, "step-up token already used")

    try:
        store.transition(approval_id, "STEPUP_VERIFIED", "APPROVED")
        store.transition(approval_id, "APPROVED", "EXECUTING")
    except ApprovalConflict as exc:
        raise HTTPException(409, str(exc)) from exc

    trace: list[TraceEvent] = []
    try:
        result = await mcp_client.call_tool(
            "orders.create",
            {
                "variant_sku": intent.variant_sku,
                "qty": intent.qty,
                "max_total_cents": intent.max_total_cents,
                "approval_id": approval_id,
                # Keyed on the approval, so any retry of this exact approval is
                # a no-op rather than a second basketball.
                "idempotency_key": f"approval:{approval_id}",
            },
            id_token=id_token,
            subject=approval.subject,
            trace=trace,
        )
    except mcp_client.McpError as exc:
        for event in trace:
            record(approval_id, event)
        store.transition(approval_id, "EXECUTING", "FAILED", failure=str(exc))
        record(
            approval_id,
            TraceEvent(kind="note", label="Order refused", detail=str(exc), ok=False),
        )
        raise HTTPException(409, str(exc)) from exc

    order = result.get("order", {})
    approval.order_id = order.get("order_id")
    store.transition(approval_id, "EXECUTING", "COMPLETED", order_id=approval.order_id)

    for event in trace:
        record(approval_id, event)
    record(
        approval_id,
        TraceEvent(
            kind="note",
            label="Order placed on the shopper's behalf",
            detail=f"{order.get('order_id')} {intent.variant_label} "
            f"${int(order.get('total_cents', 0)) / 100:.2f}",
            claims={
                "sub": order.get("subject"),
                "placed_by_agent": order.get("placed_by_agent"),
                "idempotent_replay": result.get("idempotent_replay"),
            },
        ),
    )

    refreshed = store.get(approval_id)
    return {
        "approval": refreshed.public() if refreshed else approval.public(),
        "order": order,
        "trace": [event.public() for event in trace],
    }
