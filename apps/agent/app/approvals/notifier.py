"""Out-of-band notification for an approval request.

Deliberately one small interface. The shape is CIBA's: raise a request, notify
the human out of band, then poll for a decision. Swapping in real CIBA (or push)
means writing one class here — the state machine does not change.

Email is the default channel because it is the one a shopper would actually
receive, and because it makes the out-of-band hop visible on stage: the approval
leaves the browser entirely and comes back through a second device.
"""

from __future__ import annotations

import logging
import smtplib
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Protocol

import httpx

from ..config import settings
from .store import Approval

log = logging.getLogger("oktane.notify")


@dataclass(frozen=True)
class Delivery:
    """What actually happened when we tried to notify the human.

    Returned rather than raised so the caller can record a truthful trace: a
    demo that prints "Notification sent" when the send failed is worse than one
    that admits it, because the next five minutes of the script depend on the
    shopper receiving something.
    """

    channel: str
    ok: bool
    recipient: str = ""
    detail: str = ""
    message_id: str = ""
    sender: str = ""
    subject: str = ""

    def claims(self) -> dict[str, Any]:
        out: dict[str, Any] = {"channel": self.channel, "delivered": self.ok}
        if self.recipient:
            out["to"] = self.recipient
        if self.sender:
            out["from"] = self.sender
        if self.subject:
            out["subject"] = self.subject
        if self.message_id:
            out["message_id"] = self.message_id
        if self.detail:
            out["detail"] = self.detail
        return out


class Notifier(Protocol):
    name: str

    def notify(self, approval: Approval, resume_url: str, summary: str) -> Delivery: ...


# ---- the demo outbox -------------------------------------------------------

@dataclass
class SentMail:
    """A copy of one notification, kept so the demo can show what was sent."""

    to: str
    subject: str
    body: str
    resume_url: str
    approval_id: str
    delivered: bool
    detail: str = ""
    at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {
            "to": self.to,
            "subject": self.subject,
            "body": self.body,
            "resume_url": self.resume_url,
            "approval_id": self.approval_id,
            "delivered": self.delivered,
            "detail": self.detail,
            "at": self.at,
        }


_outbox: deque[SentMail] = deque(maxlen=20)
_outbox_lock = threading.Lock()


def _remember(mail: SentMail) -> None:
    with _outbox_lock:
        _outbox.append(mail)


def outbox() -> list[dict[str, Any]]:
    """Most recent first, so the demo UI can show the newest mail without work."""
    with _outbox_lock:
        return [mail.public() for mail in reversed(_outbox)]


def latest_for(approval_id: str) -> dict[str, Any] | None:
    with _outbox_lock:
        for mail in reversed(_outbox):
            if mail.approval_id == approval_id:
                return mail.public()
    return None


# ---- message composition ---------------------------------------------------

def _compose(approval: Approval, resume_url: str, summary: str) -> tuple[str, str, str]:
    """Subject, plain-text body, HTML body — all from the same three inputs.

    Two parts so they cannot drift. The text part is the fallback every client
    can render and carries no tracking pixels: the link is the only actionable
    thing in the message. The HTML part is what the shopper actually sees.
    """
    subject, text = _compose_text(approval, resume_url, summary)
    return subject, text, _compose_html(resume_url, summary)


def _compose_html(resume_url: str, summary: str) -> str:
    """Table layout and inline styles only.

    Gmail strips ``<style>``, and remote images are blocked by default — which on
    stage would leave a broken frame in the middle of the demo. So: no images, no
    stylesheet, one button.
    """
    minutes = max(1, settings.approval_ttl_seconds // 60)
    return f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center">
<table role="presentation" width="480" cellpadding="0" cellspacing="0" border="0" style="width:480px;max-width:100%;background:#171a23;border:1px solid #262a36;border-radius:12px;">
  <tr><td style="padding:24px 28px 0 28px;">
    <div style="font-size:13px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#ff7a45;">CourtEdge</div>
    <h1 style="margin:14px 0 0 0;font-size:20px;line-height:1.3;color:#f5f6fa;font-weight:600;">Your item is back in stock</h1>
  </td></tr>
  <tr><td style="padding:18px 28px 0 28px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0f1117;border:1px solid #262a36;border-radius:8px;">
      <tr><td style="padding:14px 16px;font-size:15px;color:#f5f6fa;font-weight:600;">{summary}</td></tr>
    </table>
  </td></tr>
  <tr><td style="padding:18px 28px 0 28px;font-size:14px;line-height:1.6;color:#a8adbd;">
    Your shopping assistant found it and is holding the order. It cannot spend
    your money on its own, so <strong style="color:#f5f6fa;">nothing has been bought yet</strong>.
  </td></tr>
  <tr><td style="padding:22px 28px 0 28px;">
    <a href="{resume_url}" style="display:inline-block;background:#0057d8;color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:13px 24px;border-radius:8px;">Verify and approve</a>
  </td></tr>
  <tr><td style="padding:14px 28px 0 28px;font-size:12px;line-height:1.6;color:#6d7387;">
    A second factor is required &middot; this link works once &middot; expires in about {minutes} minutes.
    That step is what authorizes the purchase — the link on its own cannot buy anything.
  </td></tr>
  <tr><td style="padding:18px 28px 24px 28px;border-top:1px solid #262a36;font-size:11px;line-height:1.6;color:#565b6e;">
    If you did not ask for this, ignore this message and nothing will happen.
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def _compose_text(approval: Approval, resume_url: str, summary: str) -> tuple[str, str]:
    """Subject and plain-text body."""
    minutes = max(1, settings.approval_ttl_seconds // 60)
    subject = f"Approve your CourtEdge order — {summary}"
    body = f"""Your item is back in stock.

  {summary}

Your shopping assistant found it and is holding the order. It cannot spend your
money on its own, so nothing has been bought yet.

To approve this purchase, verify it is really you:

  {resume_url}

You will be asked for a second factor. That step is what authorizes the
purchase — this link on its own cannot buy anything, and it works only once.

This request expires in about {minutes} minutes. If you did not ask for this,
ignore this message and nothing will happen.

— CourtEdge
"""
    return subject, body


# ---- notifiers -------------------------------------------------------------

class EmailNotifier:
    """Sends the approval request as a real email over SMTP.

    Falls back to the outbox rather than raising when SMTP is unconfigured or
    unreachable. A demo that cannot reach a mail server should still be able to
    show the message it would have sent and carry on to step-up; losing the
    narrative to a network failure on stage is the worse outcome, and the
    returned ``Delivery`` still reports the truth.
    """

    name = "email"

    def notify(self, approval: Approval, resume_url: str, summary: str) -> Delivery:
        to = settings.notify_email_to or approval.subject_email
        subject, body, html = _compose(approval, resume_url, summary)

        if not settings.smtp_configured:
            log.info(
                "EMAIL (not sent — SMTP unconfigured) to %s\n  %s\n  resume: %s",
                to,
                subject,
                resume_url,
            )
            _remember(
                SentMail(
                    to=to,
                    subject=subject,
                    body=body,
                    resume_url=resume_url,
                    approval_id=approval.approval_id,
                    delivered=False,
                    detail="SMTP not configured; message captured in the demo outbox",
                )
            )
            return Delivery(
                channel="email",
                ok=False,
                recipient=to,
                detail="SMTP not configured — captured in the demo outbox",
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from))
        message["To"] = to
        message["Message-ID"] = make_msgid(domain="courtedge.demo")
        # A mail scanner that prefetches links must not be able to approve a
        # purchase. The decision is POST-only behind step-up, so this is defence
        # in depth rather than the control itself.
        message["X-Auto-Response-Suppress"] = "All"
        message["Auto-Submitted"] = "auto-generated"
        message.set_content(body)
        message.add_alternative(html, subtype="html")

        try:
            self._send(message)
        except Exception as exc:  # noqa: BLE001 - one failure path, reported not raised
            detail = f"{type(exc).__name__}: {exc}"
            log.warning("email to %s failed: %s", to, detail)
            _remember(
                SentMail(
                    to=to,
                    subject=subject,
                    body=body,
                    resume_url=resume_url,
                    approval_id=approval.approval_id,
                    delivered=False,
                    detail=detail,
                )
            )
            return Delivery(channel="email", ok=False, recipient=to, detail=detail)

        log.info("emailed approval %s to %s", approval.approval_id, to)
        _remember(
            SentMail(
                to=to,
                subject=subject,
                body=body,
                resume_url=resume_url,
                approval_id=approval.approval_id,
                delivered=True,
            )
        )
        return Delivery(
            channel="email",
            ok=True,
            recipient=to,
            message_id=str(message["Message-ID"]),
        )

    @staticmethod
    def _send(message: EmailMessage) -> None:
        timeout = settings.smtp_timeout_seconds
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout
            ) as smtp:
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
            smtp.ehlo()
            if settings.smtp_use_starttls:
                smtp.starttls()
                smtp.ehlo()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)


class ResendNotifier:
    """The approval request as a real email, over Resend's HTTPS API.

    The same message ``EmailNotifier`` sends — ``_compose`` is shared — over a
    different transport. HTTPS rather than SMTP because the agent runs on Render's
    free tier, which blocks outbound 25/465/587; :443 is not blocked.

    Like ``EmailNotifier``, reports failure through ``Delivery`` rather than
    raising, and captures the message in the outbox either way.
    """

    name = "resend"
    endpoint = "https://api.resend.com/emails"

    def notify(self, approval: Approval, resume_url: str, summary: str) -> Delivery:
        to = settings.notify_email_to or approval.subject_email
        subject, body, html = _compose(approval, resume_url, summary)
        sender = formataddr((settings.resend_from_name, settings.resend_from))

        if not settings.resend_configured:
            log.info(
                "EMAIL (not sent — RESEND_API_KEY unset) to %s\n  %s\n  resume: %s",
                to,
                subject,
                resume_url,
            )
            _remember(
                SentMail(
                    to=to,
                    subject=subject,
                    body=body,
                    resume_url=resume_url,
                    approval_id=approval.approval_id,
                    delivered=False,
                    detail="RESEND_API_KEY not set; message captured in the demo outbox",
                )
            )
            return Delivery(
                channel="resend",
                ok=False,
                recipient=to,
                sender=sender,
                subject=subject,
                detail="RESEND_API_KEY not set — captured in the demo outbox",
            )

        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "authorization": f"Bearer {settings.resend_api_key}",
                    # One approval can only ever produce one email, even if
                    # Simulate Restock is double-clicked. Resend dedupes for 24h.
                    "idempotency-key": f"approval-{approval.approval_id}",
                },
                json={
                    "from": sender,
                    "to": [to],
                    "subject": subject,
                    "text": body,
                    "html": html,
                    # Keep vacation replies and link previewers away from a
                    # no-reply address. The decision endpoint is POST-only, so
                    # this is defence in depth rather than the control itself.
                    "headers": {
                        "X-Auto-Response-Suppress": "All",
                        "Auto-Submitted": "auto-generated",
                    },
                },
                timeout=settings.smtp_timeout_seconds,
            )
            if response.status_code >= 400:
                # Resend's body distinguishes a 403 (unverified sender domain)
                # from a 422 (malformed address). Surface it rather than making
                # someone open the dashboard mid-demo.
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
            message_id = str(response.json().get("id", ""))
        except Exception as exc:  # noqa: BLE001 - one failure path, reported not raised
            detail = f"{type(exc).__name__}: {exc}"
            log.warning("resend to %s failed: %s", to, detail)
            _remember(
                SentMail(
                    to=to,
                    subject=subject,
                    body=body,
                    resume_url=resume_url,
                    approval_id=approval.approval_id,
                    delivered=False,
                    detail=detail,
                )
            )
            return Delivery(
                channel="resend",
                ok=False,
                recipient=to,
                sender=sender,
                subject=subject,
                detail=detail,
            )

        log.info("resent approval %s to %s (%s)", approval.approval_id, to, message_id)
        _remember(
            SentMail(
                to=to,
                subject=subject,
                body=body,
                resume_url=resume_url,
                approval_id=approval.approval_id,
                delivered=True,
            )
        )
        return Delivery(
            channel="resend",
            ok=True,
            recipient=to,
            sender=sender,
            subject=subject,
            message_id=message_id,
        )


class ConsoleNotifier:
    """Prints the resume link. Kept for headless runs and the acceptance test."""

    name = "console"

    def notify(self, approval: Approval, resume_url: str, summary: str) -> Delivery:
        to = settings.notify_email_to or approval.subject_email
        subject, body, _html = _compose(approval, resume_url, summary)
        log.info(
            "APPROVAL REQUEST %s for %s\n  %s\n  resume: %s",
            approval.approval_id,
            to,
            summary,
            resume_url,
        )
        _remember(
            SentMail(
                to=to,
                subject=subject,
                body=body,
                resume_url=resume_url,
                approval_id=approval.approval_id,
                delivered=True,
                detail="console channel",
            )
        )
        return Delivery(channel="console", ok=True, recipient=to)


class CibaNotifier:
    """Placeholder for real Okta CIBA.

    Not implemented on purpose: Okta's CIBA requires a custom-branded
    authenticator built with the Devices SDK, which is weeks of mobile work and
    outside an MVP. The polling contract the UI already uses is CIBA's, so this
    is the only file that would need to change.
    """

    name = "ciba"

    def notify(self, approval: Approval, resume_url: str, summary: str) -> Delivery:
        raise NotImplementedError(
            "CIBA requires a custom authenticator built with the Okta Devices SDK"
        )


def get_notifier() -> Notifier:
    """Email by default; ``NOTIFY_CHANNEL`` overrides it.

    ``DEMO_MODE=ciba`` still wins, so the unimplemented path stays reachable and
    obvious rather than being silently replaced by email.
    """
    if settings.demo_mode == "ciba":
        return CibaNotifier()
    if settings.notify_channel == "console":
        return ConsoleNotifier()
    if settings.notify_channel == "resend":
        return ResendNotifier()
    return EmailNotifier()
