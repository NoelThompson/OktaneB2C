"""Out-of-band notification for an approval request.

Deliberately one small interface. The demo uses the console notifier and shows
the link in the UI, but the shape is CIBA's: raise a request, notify the human
out of band, then poll for a decision. Swapping in real CIBA (or email, or
push) means writing one class here — the state machine does not change.
"""

from __future__ import annotations

import logging
from typing import Protocol

from ..config import settings
from .store import Approval

log = logging.getLogger("oktane.notify")


class Notifier(Protocol):
    name: str

    def notify(self, approval: Approval, resume_url: str, summary: str) -> None: ...


class ConsoleNotifier:
    """Prints the resume link. Stands in for the email or push a shopper would get."""

    name = "console"

    def notify(self, approval: Approval, resume_url: str, summary: str) -> None:
        log.info(
            "APPROVAL REQUEST %s for %s\n  %s\n  resume: %s",
            approval.approval_id,
            approval.subject_email,
            summary,
            resume_url,
        )


class CibaNotifier:
    """Placeholder for real Okta CIBA.

    Not implemented on purpose: Okta's CIBA requires a custom-branded
    authenticator built with the Devices SDK, which is weeks of mobile work and
    outside an MVP. The polling contract the UI already uses is CIBA's, so this
    is the only file that would need to change.
    """

    name = "ciba"

    def notify(self, approval: Approval, resume_url: str, summary: str) -> None:
        raise NotImplementedError(
            "CIBA requires a custom authenticator built with the Okta Devices SDK"
        )


def get_notifier() -> Notifier:
    if settings.demo_mode == "ciba":
        return CibaNotifier()
    return ConsoleNotifier()
