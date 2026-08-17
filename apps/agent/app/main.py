"""Oktane B2C agent service.

Owns the shopper's identity, the token exchanges, the intent/approval state
machine, and step-up verification. It deliberately owns no data access: every
read and write goes through the MCP server with a scoped token.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import approvals, chat, demo, mock_as

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("oktane.agent")

app = FastAPI(title="Oktane B2C Agent", version="1.0.0")

# The storefront talks to this service through its own server-side route
# handlers, so the browser origin only needs to be allowed for the approve page.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_base],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(approvals.router)
app.include_router(demo.router)
if settings.mock:
    app.include_router(mock_as.router)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "demo_mode": settings.demo_mode,
        "token_exchange_impl": "mock" if settings.mock else settings.token_exchange_impl,
        "mcp_url": settings.mcp_url,
        "catalog_issuer": settings.catalog.issuer,
        "orders_issuer": settings.orders.issuer,
        "required_acr": settings.required_acr,
    }


@app.on_event("startup")
def announce() -> None:
    log.info("agent up  DEMO_MODE=%s  mcp=%s", settings.demo_mode, settings.mcp_url)
    if settings.mock:
        log.info("mock authorization servers:")
        log.info("  catalog %s", settings.catalog.issuer)
        log.info("  orders  %s", settings.orders.issuer)
        log.info("set MCP_REQUIRE_AUTH=true on the MCP server to enforce these for real")
