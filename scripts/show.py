"""Pretty-print an agent chat or approval response. Used by the demo walkthrough."""

import json
import sys


def trace(events):
    for t in events:
        mark = "OK  " if t.get("ok", True) else "DENY"
        print(f"  [{mark}] {t['kind']:14} {t['label']}")
        if t.get("detail"):
            print(f"           {t['detail']}")
        for k, v in (t.get("claims") or {}).items():
            print(f"             {k} = {v}")


d = json.load(sys.stdin)

if "reply" in d:
    print(f"kind: {d.get('kind')} | llm: {d.get('llm')}")
    print(f"reply: {d['reply']}")
    if d.get("intent"):
        i = d["intent"]
        print(f"intent: {i['intent_id']} {i['variant_sku']} state={i['state']}")

if "approval" in d:
    a = d["approval"]
    print(f"approval {a['approval_id']} state={a['state']} order={a.get('order_id')}")
    if a.get("failure"):
        print(f"  failure: {a['failure']}")
    print(f"  history: {' -> '.join(h['state'] for h in a.get('history', []))}")

if "order" in d and d["order"]:
    o = d["order"]
    print(
        f"order {o['order_id']} {o['variant_sku']} x{o['qty']} "
        f"${o['total_cents'] / 100:.2f} sub={o['subject']} agent={o.get('placed_by_agent')}"
    )

if "refused" in d:
    print(f"refused: {d['refused']} error={d.get('error')}")
    print(f"  detail: {json.dumps(d.get('detail'), indent=2)}")

if d.get("approvals_raised") is not None:
    print(f"restock: {json.dumps(d.get('restock'))}")
    for r in d["approvals_raised"]:
        print(f"  raised {r['approval_id']} for {r['summary']}")
        print(f"  resume {r['resume_url']}")

if d.get("trace"):
    print("trace:")
    trace(d["trace"])
