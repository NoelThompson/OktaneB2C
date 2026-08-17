"""Prompts and the deterministic fallback.

Two rules shape everything here:

1. **The model never supplies facts.** Sizes, prices, and stock come from MCP
   tool results. The model classifies the turn and phrases the answer. If it
   were left to recall that a 16-year-old needs a size 7, the demo's central
   claim — that the answer required an authorized data call — would be false.
2. **The demo must run without an API key.** Every LLM call has a deterministic
   counterpart, so the eight beats work before ``ANTHROPIC_API_KEY`` exists.
"""

from __future__ import annotations

CLASSIFY_SYSTEM = """You classify one shopper message for a sporting-goods store's assistant.

Reply with ONLY a JSON object, no prose:
{
  "kind": "size_question" | "standing_intent" | "stock_question" | "order_status" | "general",
  "query": "<product search terms, or empty>",
  "age": <integer age if the shopper mentioned one, else null>,
  "size": "<explicit size if named, else empty>"
}

Definitions:
- size_question: asking which size fits, often mentioning an age or a person.
- standing_intent: asking to buy later, when stock returns. Phrases like
  "purchase when in stock", "buy it when available", "order it once restocked",
  "let me know and get it".
- stock_question: asking only about availability.
- order_status: asking about existing or pending orders.
- general: anything else."""

ANSWER_SYSTEM = """You are the shopping assistant for CourtEdge, a basketball retailer.

You have been given verified data retrieved from the store's systems on this
shopper's behalf. Ground every factual statement in that data.

- Never invent a size, price, or stock number. If the data does not contain it,
  say you could not retrieve it.
- Quote sizes with their circumference exactly as the data gives them.
- When the recommended item is out of stock, say so plainly and offer to place a
  standing order for when it is restocked. Do not offer to buy it now.
- You cannot complete a purchase yourself; a purchase always needs the shopper's
  own approval. Say this naturally, not as a disclaimer.
- Two or three short sentences. Warm, direct, no bullet lists, no emoji."""


def size_answer(
    product_name: str,
    size: str,
    circumference: str,
    label: str,
    age: int | None,
    in_stock: bool,
    price_cents: int,
    notes: str,
) -> str:
    """Deterministic phrasing of the size recommendation."""
    who = f"a {age}-year-old" if age else "that age group"
    price = f"${price_cents / 100:.2f}"
    lead = (
        f"For {who}, you want size {size} — {circumference} circumference, "
        f"the {label.lower()} ball. {notes}"
    )
    if in_stock:
        return (
            f"{lead} The {product_name} in size {size} is {price} and in stock. "
            f"Want me to add it to your cart?"
        )
    return (
        f"{lead} The {product_name} in size {size} is {price}, but it's out of stock "
        f"right now. I can place a standing order and buy it the moment it's back — "
        f"you'd approve the purchase yourself before any money moves."
    )


def intent_answer(product_name: str, variant_label: str, total_cents: int) -> str:
    total = f"${total_cents / 100:.2f}"
    return (
        f"Done — I've recorded a standing order for the {product_name}, {variant_label}, "
        f"at {total}. When it's restocked I'll ask you to approve it. "
        f"I can't spend your money on my own, so nothing happens until you verify it's you."
    )


def stock_answer(product_name: str, lines: list[str]) -> str:
    return f"Here's what's on the shelf for the {product_name}: " + "; ".join(lines) + "."


def orders_answer(lines: list[str]) -> str:
    if not lines:
        return "You don't have any orders yet, and nothing is waiting on your approval."
    return "Here's where your orders stand: " + "; ".join(lines) + "."


GENERAL_FALLBACK = (
    "I can help you find the right basketball, check what's in stock, or set up a "
    "standing order for something that's sold out. What are you shopping for?"
)

NO_MATCH_FALLBACK = (
    "I couldn't find that in our catalog. We carry basketballs, footwear, hoops, "
    "apparel, and accessories — what are you after?"
)
