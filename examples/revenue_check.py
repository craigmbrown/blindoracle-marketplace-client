#!/usr/bin/env python3
"""Query the booked-revenue ledger for an agent + platform summary."""
import json
from urllib.request import Request, urlopen

BASE = "https://api.craigmbrown.com/a2a"


def get(path: str) -> dict:
    req = Request(f"{BASE}{path}",
                  headers={"Accept": "application/json",
                           "User-Agent": "bo-sdk-revenue-check/1.0"})
    with urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


if __name__ == "__main__":
    agent = "market-intelligence-agent"

    print("=== platform summary ===")
    s = get("/revenue/summary")
    print(f"entries:      {s.get('entry_count', 0)}")
    print(f"booked (USD): ${s.get('total_usd_booked', 0):.4f}")
    print(f"status:       {s.get('settlement_status', '?')}")
    print("top providers:")
    for p in s.get("top_providers", [])[:5]:
        print(f"  - {p.get('agent'):40s}  ${p.get('usd', 0):.4f}")

    print(f"\n=== {agent} revenue ===")
    r = get(f"/agents/{agent}/revenue")
    print(f"entries:      {r.get('entry_count', 0)}")
    print(f"booked (USD): ${r.get('total_usd_booked', 0):.4f}")
    for e in r.get("entries", [])[-5:]:
        print(f"  - {e.get('entry_id')}  ${e.get('amount_usd', 0):.4f}  job={e.get('job_id')}")
