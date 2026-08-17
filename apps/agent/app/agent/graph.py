"""The assistant's reasoning graph.

    understand ─┬─> catalog_lookup ─> stock_lookup ─> compose
                ├─> stock_lookup ──────────────────> compose
                ├─> record_intent ─────────────────> compose
                └─> order_status ──────────────────> compose

Every data-bearing node reaches the MCP server with a scoped access token
obtained on the shopper's behalf. The graph holds no database access of its own,
which is why the size recommendation at beat 3 is a genuine authorization event
and not a model recollection.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from .. import mcp_client
from ..approvals.store import store
from ..tokens.base import TraceEvent
from . import llm, prompts

log = logging.getLogger("oktane.graph")

# The demo's sizing question is about basketballs; make that the default subject
# when the shopper asks "what size" without naming a product.
DEFAULT_QUERY = "basketball"

INTENT_PATTERNS = (
    r"\bwhen (?:it'?s |they'?re )?(?:back )?in stock\b",
    r"\bwhen (?:it|they)(?:'s| is|'re| are)? (?:back|available|restocked)\b",
    r"\bonce (?:it|they)(?:'s| is|'re| are)? (?:back|available|restocked|in stock)\b",
    r"\b(?:buy|purchase|order|get) (?:it|that|one)? ?(?:for me )?(?:later|when|once)\b",
    r"\bstanding (?:order|intent)\b",
    r"\bback ?order\b",
    r"\bnotify me and (?:buy|order|purchase)\b",
)

SIZE_PATTERNS = (r"\bwhat size\b", r"\bwhich size\b", r"\bright size\b", r"\bsize for\b", r"\bfit\b")
STOCK_PATTERNS = (r"\bin stock\b", r"\bavailable\b", r"\bstock\b", r"\bsold out\b")
ORDER_PATTERNS = (r"\bmy orders?\b", r"\border status\b", r"\bwhat did i (?:buy|order)\b")


def _merge(left: list[Any], right: list[Any]) -> list[Any]:
    """Concatenate node traces, keeping the shopper's ID token to one entry.

    Each node builds its own trace list, so without this the root of the chain
    would appear once per exchange and two exchanges would look like three.
    """
    rooted = any(getattr(event, "kind", None) == "user_token" for event in left)
    return [
        *left,
        *(e for e in right if not (rooted and getattr(e, "kind", None) == "user_token")),
    ]


class AgentState(TypedDict, total=False):
    message: str
    id_token: str
    subject: str
    subject_email: str
    kind: str
    query: str
    age: int | None
    size: str
    products: list[dict[str, Any]]
    sizing: dict[str, Any]
    variants: list[dict[str, Any]]
    chosen: dict[str, Any]
    product: dict[str, Any]
    orders: list[dict[str, Any]]
    intent: dict[str, Any] | None
    reply: str
    error: str
    trace: Annotated[list[TraceEvent], _merge]


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _extract_age(text: str) -> int | None:
    for pattern in (
        r"\b(\d{1,2})\s*(?:-|\s)?\s*year[- ]?old\b",
        r"\bage(?:d)?\s*(?:of\s*)?(\d{1,2})\b",
        r"\b(\d{1,2})\s*(?:yo|y/o|yrs?)\b",
    ):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


async def understand(state: AgentState) -> dict[str, Any]:
    """Classify the turn. The LLM helps; regex guarantees the demo path."""
    text = state["message"].lower()

    kind = "general"
    if _matches(text, INTENT_PATTERNS):
        kind = "standing_intent"
    elif _matches(text, SIZE_PATTERNS) or (_extract_age(text) and "size" in text):
        kind = "size_question"
    elif _matches(text, ORDER_PATTERNS):
        kind = "order_status"
    elif _matches(text, STOCK_PATTERNS):
        kind = "stock_question"

    age = _extract_age(text)
    query = ""
    size = ""

    parsed = await llm.complete_json(prompts.CLASSIFY_SYSTEM, state["message"])
    if parsed:
        # Trust the model for extraction, but never let it override a
        # confidently pattern-matched standing intent — that beat must not flake.
        if kind == "general" and isinstance(parsed.get("kind"), str):
            kind = parsed["kind"]
        if age is None and isinstance(parsed.get("age"), int):
            age = parsed["age"]
        if isinstance(parsed.get("query"), str):
            query = parsed["query"].strip()
        if isinstance(parsed.get("size"), str):
            size = parsed["size"].strip()

    if not query:
        match = re.search(
            r"\b(basketball|shoe|sneaker|hoop|jersey|pump|bag|backpack)\w*\b", text
        )
        query = match.group(1) if match else DEFAULT_QUERY

    return {"kind": kind, "query": query, "age": age, "size": size}


def route(state: AgentState) -> str:
    kind = state.get("kind", "general")
    if kind == "standing_intent":
        return "record_intent"
    if kind == "order_status":
        return "order_status"
    if kind == "stock_question":
        return "catalog_lookup"
    if kind == "size_question":
        return "catalog_lookup"
    return "compose"


async def catalog_lookup(state: AgentState) -> dict[str, Any]:
    """catalog:read — find the product and pull its sizing table."""
    trace: list[TraceEvent] = []
    try:
        found = await mcp_client.call_tool(
            "catalog.search",
            {"query": state.get("query") or DEFAULT_QUERY, "limit": 3},
            id_token=state["id_token"],
            subject=state["subject"],
            trace=trace,
        )
    except mcp_client.McpError as exc:
        return {"error": str(exc), "trace": trace}

    products = found.get("products", [])
    if not products:
        return {"products": [], "trace": trace}

    product = products[0]
    sizing: dict[str, Any] = {}
    if product.get("sizing_guide"):
        try:
            args: dict[str, Any] = {"guide": product["sizing_guide"]}
            if state.get("age") is not None:
                args["age"] = state["age"]
            sizing = await mcp_client.call_tool(
                "catalog.sizing_guide",
                args,
                id_token=state["id_token"],
                subject=state["subject"],
                trace=trace,
            )
        except mcp_client.McpError as exc:
            return {"error": str(exc), "products": products, "trace": trace}

    return {"products": products, "product": product, "sizing": sizing, "trace": trace}


async def stock_lookup(state: AgentState) -> dict[str, Any]:
    """inventory:read — a different scope from the catalog read above."""
    product = state.get("product")
    if not product:
        return {}

    trace: list[TraceEvent] = []
    try:
        result = await mcp_client.call_tool(
            "inventory.check",
            {"product_sku": product["sku"]},
            id_token=state["id_token"],
            subject=state["subject"],
            trace=trace,
        )
    except mcp_client.McpError as exc:
        return {"error": str(exc), "trace": trace}

    variants = result.get("variants", [])
    chosen: dict[str, Any] = {}

    wanted = state.get("size") or (state.get("sizing", {}).get("recommended") or {}).get("size")
    if wanted:
        chosen = next((v for v in variants if str(v["size"]) == str(wanted)), {})
    if not chosen and variants:
        chosen = variants[0]

    return {"variants": variants, "chosen": chosen, "trace": trace}


async def record_intent(state: AgentState) -> dict[str, Any]:
    """Beat 5: remember the purchase without making it.

    Resolving the SKU still needs authorized catalog and inventory reads — the
    agent cannot record an intent against a product it was not allowed to see.
    """
    trace: list[TraceEvent] = []
    try:
        found = await mcp_client.call_tool(
            "catalog.search",
            {"query": state.get("query") or DEFAULT_QUERY, "limit": 3},
            id_token=state["id_token"],
            subject=state["subject"],
            trace=trace,
        )
        products = found.get("products", [])
        if not products:
            return {"reply": prompts.NO_MATCH_FALLBACK, "trace": trace}

        product = products[0]
        stock = await mcp_client.call_tool(
            "inventory.check",
            {"product_sku": product["sku"]},
            id_token=state["id_token"],
            subject=state["subject"],
            trace=trace,
        )
    except mcp_client.McpError as exc:
        return {"error": str(exc), "trace": trace}

    variants = stock.get("variants", [])
    wanted = state.get("size")
    if not wanted and product.get("sizing_guide") and state.get("age") is not None:
        guide = await mcp_client.call_tool(
            "catalog.sizing_guide",
            {"guide": product["sizing_guide"], "age": state["age"]},
            id_token=state["id_token"],
            subject=state["subject"],
            trace=trace,
        )
        wanted = (guide.get("recommended") or {}).get("size")

    target = next((v for v in variants if str(v["size"]) == str(wanted)), None) if wanted else None
    # Default to whatever is actually out of stock — that is what a shopper
    # asking to "buy when in stock" is talking about.
    if target is None:
        target = next((v for v in variants if not v["in_stock"]), None) or (
            variants[0] if variants else None
        )
    if target is None:
        return {"reply": prompts.NO_MATCH_FALLBACK, "trace": trace}

    existing = [
        i for i in store.intents_for(state["subject"]) if i.variant_sku == target["sku"]
    ]
    if existing and existing[0].state == "PENDING_STOCK":
        intent = existing[0]
        trace.append(
            TraceEvent(
                kind="note",
                label="Standing intent already recorded",
                detail=f"{intent.intent_id} for {target['sku']}",
            )
        )
    else:
        intent = store.create_intent(
            subject=state["subject"],
            subject_email=state.get("subject_email", ""),
            variant_sku=target["sku"],
            product_name=target["product_name"],
            variant_label=target["label"],
            qty=1,
            unit_cents=target["price_cents"],
            # A ceiling, not the price: if the item is repriced upward while the
            # intent waits, the order must fail rather than overspend.
            max_total_cents=target["price_cents"],
        )
        trace.append(
            TraceEvent(
                kind="note",
                label="Standing intent recorded — no purchase made",
                detail=f"{intent.intent_id} {target['sku']} ceiling ${target['price_cents'] / 100:.2f}",
                claims={
                    "state": intent.state,
                    "requires": "human approval with step-up before any order",
                },
            )
        )

    return {
        "intent": intent.public(),
        "product": {"sku": target["product_sku"], "name": target["product_name"]},
        "chosen": target,
        "reply": prompts.intent_answer(
            target["product_name"], target["label"], target["price_cents"]
        ),
        "trace": trace,
    }


async def order_status(state: AgentState) -> dict[str, Any]:
    """orders:read — a token from the orders authorization server, not the catalog one."""
    trace: list[TraceEvent] = []
    orders: list[dict[str, Any]] = []
    try:
        result = await mcp_client.call_tool(
            "orders.list",
            {},
            id_token=state["id_token"],
            subject=state["subject"],
            trace=trace,
        )
        orders = result.get("orders", [])
    except mcp_client.McpError as exc:
        return {"error": str(exc), "trace": trace}

    lines = [
        f"{o.get('product_name', o['variant_sku'])} ({o.get('variant_label', '')}) "
        f"— ${o['total_cents'] / 100:.2f}, placed {o['created_at'][:10]}"
        for o in orders
    ]
    for intent in store.intents_for(state["subject"]):
        if intent.state not in {"COMPLETED", "DENIED", "EXPIRED"}:
            lines.append(
                f"{intent.product_name} ({intent.variant_label}) — standing order, {intent.state}"
            )

    return {"orders": orders, "reply": prompts.orders_answer(lines), "trace": trace}


async def compose(state: AgentState) -> dict[str, Any]:
    """Phrase the answer. Facts come only from what the tool nodes retrieved."""
    if state.get("error"):
        return {
            "reply": (
                "I couldn't reach the store's systems with the right authorization for "
                f"that. The details are in the trace: {state['error']}"
            )
        }
    if state.get("reply"):
        return {}

    kind = state.get("kind", "general")
    chosen = state.get("chosen") or {}
    product = state.get("product") or {}
    recommended = (state.get("sizing") or {}).get("recommended") or {}

    if kind == "size_question" and recommended and chosen:
        deterministic = prompts.size_answer(
            product_name=product.get("name", "ball"),
            size=str(recommended.get("size", chosen.get("size", ""))),
            circumference=str(recommended.get("circumference", "")),
            label=str(recommended.get("label", "")),
            age=state.get("age"),
            in_stock=bool(chosen.get("in_stock")),
            price_cents=int(chosen.get("price_cents", 0)),
            notes=str(recommended.get("notes", "")),
        )
    elif kind == "stock_question" and state.get("variants"):
        lines = [
            f"{v['label']} — {'in stock' if v['in_stock'] else 'out of stock'}"
            f"{'' if not v['in_stock'] else f' ({v['stock']} left)'}"
            for v in state["variants"]
        ]
        deterministic = prompts.stock_answer(product.get("name", "product"), lines)
    elif not state.get("products") and kind in {"size_question", "stock_question"}:
        deterministic = prompts.NO_MATCH_FALLBACK
    else:
        deterministic = prompts.GENERAL_FALLBACK

    facts = {
        "product": {k: product.get(k) for k in ("sku", "name", "blurb") if product.get(k)},
        "recommended_size": recommended,
        "selected_variant": chosen,
        "all_variants": state.get("variants", []),
        "shopper_age": state.get("age"),
    }
    phrased = await llm.complete(
        prompts.ANSWER_SYSTEM,
        f"Shopper said: {state['message']}\n\n"
        f"Verified store data retrieved on their behalf:\n{facts}\n\n"
        f"Write the reply.",
    )
    return {"reply": phrased or deterministic}


def build_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("understand", understand)
    graph.add_node("catalog_lookup", catalog_lookup)
    graph.add_node("stock_lookup", stock_lookup)
    graph.add_node("record_intent", record_intent)
    graph.add_node("order_status", order_status)
    graph.add_node("compose", compose)

    graph.set_entry_point("understand")
    graph.add_conditional_edges(
        "understand",
        route,
        {
            "catalog_lookup": "catalog_lookup",
            "record_intent": "record_intent",
            "order_status": "order_status",
            "compose": "compose",
        },
    )
    graph.add_edge("catalog_lookup", "stock_lookup")
    graph.add_edge("stock_lookup", "compose")
    graph.add_edge("record_intent", "compose")
    graph.add_edge("order_status", "compose")
    graph.add_edge("compose", END)
    return graph.compile()


compiled = build_graph()


async def run_turn(
    message: str, id_token: str, subject: str, subject_email: str
) -> AgentState:
    return await compiled.ainvoke(
        {
            "message": message,
            "id_token": id_token,
            "subject": subject,
            "subject_email": subject_email,
            "trace": [],
        }
    )
