"""Configuration for the Oktane B2C agent service.

`DEMO_MODE` is the switch that makes this repo demoable with no Okta org at all:

- ``mock`` — the agent runs a local authorization server, mints real RS256
  tokens, and serves a JWKS the MCP server verifies against. The full
  token-exchange shape and every scope check is exercised for real; only the
  issuer is local.
- ``okta`` — the same code paths point at a real Okta org.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"The agent requires Python 3.10+ (okta-client and modern typing); "
        f"found {sys.version.split()[0]}. Recreate the venv with python3.13."
    )

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent.parent
load_dotenv(_HERE.parent / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _flag(name: str, default: bool = False) -> bool:
    raw = _env(name)
    return raw.lower() in {"1", "true", "yes", "on"} if raw else default


@dataclass(frozen=True)
class AuthServer:
    """One custom authorization server: an issuer, an audience, and its scopes."""

    name: str
    issuer: str
    audience: str
    scopes: tuple[str, ...]

    @property
    def token_url(self) -> str:
        """Leg 2 of the exchange posts here — the *custom* AS, not the org one."""
        return f"{self.issuer}/v1/token"

    @property
    def keys_url(self) -> str:
        return f"{self.issuer}/v1/keys"


@dataclass(frozen=True)
class Settings:
    demo_mode: str = field(default_factory=lambda: _env("DEMO_MODE", "mock").lower())
    host: str = field(default_factory=lambda: _env("AGENT_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("AGENT_PORT", "8788")))
    public_base: str = field(
        default_factory=lambda: _env("AGENT_PUBLIC_BASE", "http://localhost:8788")
    )
    web_base: str = field(default_factory=lambda: _env("WEB_BASE", "http://localhost:3000"))
    mcp_url: str = field(default_factory=lambda: _env("MCP_URL", "http://localhost:8787"))

    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(
        default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-opus-4-7")
    )

    okta_domain: str = field(default_factory=lambda: _env("OKTA_DOMAIN"))
    # Also the client the *shopper* signs into. Okta refuses ID_TOKEN delegation
    # links ("register the agent with a signOnProvider to use its ID tokens") and
    # leg 1 accepts only a subject token minted for the requesting client, so the
    # agent's own app must be the relying party. A separate storefront app cannot
    # seed the exchange no matter how it is configured.
    agent_client_id: str = field(
        default_factory=lambda: _env("OKTA_AGENT_CLIENT_ID", "wlp-oktane-demo-agent")
    )
    agent_private_key_jwk: str = field(
        default_factory=lambda: _env("OKTA_AGENT_PRIVATE_KEY_JWK")
    )
    agent_key_id: str = field(default_factory=lambda: _env("OKTA_AGENT_KEY_ID"))
    token_exchange_impl: str = field(
        default_factory=lambda: _env("TOKEN_EXCHANGE_IMPL", "mock").lower()
    )

    catalog_audience: str = field(
        default_factory=lambda: _env("OKTA_CATALOG_AUDIENCE", "api://oktane-catalog")
    )
    orders_audience: str = field(
        default_factory=lambda: _env("OKTA_ORDERS_AUDIENCE", "api://oktane-orders")
    )
    catalog_issuer_okta: str = field(default_factory=lambda: _env("OKTA_CATALOG_ISSUER"))
    orders_issuer_okta: str = field(default_factory=lambda: _env("OKTA_ORDERS_ISSUER"))

    # ---- out-of-band notification ------------------------------------------
    # email | console. Email is the default: it is the channel a shopper would
    # really get, and it makes the out-of-band hop visible on stage. Console is
    # for headless runs and the acceptance test.
    notify_channel: str = field(
        default_factory=lambda: _env("NOTIFY_CHANNEL", "email").lower()
    )
    # Where approval mail actually goes. The demo shoppers have unroutable
    # addresses (alex@oktane.demo), so a live demo must redirect to a real inbox
    # or nothing arrives. Empty falls back to the shopper's own address, which is
    # the right behaviour once shoppers are real Okta users.
    notify_email_to: str = field(default_factory=lambda: _env("NOTIFY_EMAIL_TO"))
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER"))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD"))
    smtp_from: str = field(
        default_factory=lambda: _env("SMTP_FROM", "no-reply@courtedge.demo")
    )
    smtp_from_name: str = field(default_factory=lambda: _env("SMTP_FROM_NAME", "CourtEdge"))
    smtp_use_starttls: bool = field(default_factory=lambda: _flag("SMTP_STARTTLS", True))
    smtp_use_ssl: bool = field(default_factory=lambda: _flag("SMTP_SSL", False))
    # Short on purpose: a stalled mail server must not hold up the restock
    # response while an audience watches a spinner.
    smtp_timeout_seconds: float = field(
        default_factory=lambda: float(_env("SMTP_TIMEOUT_SECONDS", "10"))
    )
    # Resend's HTTPS API, used instead of SMTP when NOTIFY_CHANNEL=resend.
    # Render's free tier blocks outbound 25/465/587, so a deployed agent cannot
    # deliver over smtplib at all; :443 is not blocked. The sending domain must
    # be verified in Resend or the API answers 403 — hence the default is
    # Resend's own sandbox sender, which needs no DNS at all. An unverified
    # account may only mail its own owner from it, so the account has to belong
    # to whoever NOTIFY_EMAIL_TO names.
    resend_api_key: str = field(default_factory=lambda: _env("RESEND_API_KEY"))
    resend_from: str = field(
        default_factory=lambda: _env("RESEND_FROM", "onboarding@resend.dev")
    )
    resend_from_name: str = field(
        default_factory=lambda: _env("RESEND_FROM_NAME", "CourtEdge")
    )

    approval_ttl_seconds: int = field(
        default_factory=lambda: int(_env("APPROVAL_TTL_SECONDS", "900"))
    )
    stepup_freshness_seconds: int = field(
        default_factory=lambda: int(_env("STEPUP_FRESHNESS_SECONDS", "120"))
    )
    required_acr: str = field(
        default_factory=lambda: _env("REQUIRED_ACR", "urn:okta:loa:2fa:any")
    )

    @property
    def mock(self) -> bool:
        return self.demo_mode == "mock"

    @property
    def smtp_configured(self) -> bool:
        """A host is the minimum. Everything else has a usable default.

        Auth is optional deliberately: a local relay (MailHog, Mailpit) needs no
        credentials, and that is the easiest way to rehearse the email beat.
        """
        return bool(self.smtp_host)

    @property
    def resend_configured(self) -> bool:
        """The API key is the only thing without a usable default."""
        return bool(self.resend_api_key)

    @property
    def org_issuer(self) -> str:
        """The **org** authorization server, which mints ID-JAGs.

        Leg 1 of Cross App Access goes here, not to the custom AS — the org AS is
        the only party that can assert "this agent may act for this user against
        that resource". Leg 2 then goes to the custom AS named in the assertion.
        """
        if self.mock:
            return f"{self.public_base}/mock-as/org"
        if not self.okta_domain.startswith("https://"):
            raise ValueError(
                f"OKTA_DOMAIN must be an https:// org URL when DEMO_MODE={self.demo_mode}; "
                f"got {self.okta_domain!r}"
            )
        return f"{self.okta_domain.rstrip('/')}/oauth2"

    @property
    def org_token_url(self) -> str:
        return f"{self.org_issuer}/v1/token"

    @property
    def user_authorize_url(self) -> str:
        """Where a *human* is sent to authenticate.

        Mock mode serves its own consent form; the real org uses the same
        endpoints as ``org_issuer``, which is also what validates that
        ``OKTA_DOMAIN`` already carries its scheme.
        """
        if self.mock:
            return f"{self.public_base}/mock-as/users/v1/authorize"
        return f"{self.org_issuer}/v1/authorize"

    @property
    def user_token_url(self) -> str:
        if self.mock:
            return f"{self.public_base}/mock-as/users/v1/token"
        return f"{self.org_issuer}/v1/token"

    @property
    def user_token_issuer(self) -> str:
        """The ``iss`` a shopper's ID token actually carries.

        Deliberately not ``org_issuer``. Okta's org authorization server serves
        its endpoints under ``/oauth2/v1/*`` but stamps tokens with the bare org
        URL, so reusing ``org_issuer`` here rejects every valid token.
        """
        if self.mock:
            return f"{self.public_base}/mock-as/users"
        return self.okta_domain.rstrip("/")

    @property
    def user_keys_url(self) -> str:
        if self.mock:
            return f"{self.public_base}/mock-as/users/v1/keys"
        return f"{self.org_issuer}/v1/keys"

    @property
    def user_logout_url(self) -> str | None:
        """RP-initiated logout (``end_session``) for the shopper's own sign-in.

        None in mock mode: the mock authorization server never sets a browser
        session, so there is nothing at the IdP for a logout redirect to clear
        — only this app's own cookie, which the caller already drops.
        """
        if self.mock:
            return None
        return f"{self.org_issuer}/v1/logout"

    @property
    def catalog(self) -> AuthServer:
        return AuthServer(
            name="oktane-catalog",
            issuer=self.catalog_issuer_okta
            if not self.mock
            else f"{self.public_base}/mock-as/catalog",
            audience=self.catalog_audience,
            scopes=("catalog:read", "inventory:read"),
        )

    @property
    def orders(self) -> AuthServer:
        return AuthServer(
            name="oktane-orders",
            issuer=self.orders_issuer_okta
            if not self.mock
            else f"{self.public_base}/mock-as/orders",
            audience=self.orders_audience,
            scopes=("orders:read", "orders:write"),
        )

    def server_for_scope(self, scope: str) -> AuthServer:
        if scope in self.orders.scopes:
            return self.orders
        if scope in self.catalog.scopes:
            return self.catalog
        raise ValueError(f"no authorization server owns scope {scope!r}")


settings = Settings()
