#!/usr/bin/env python3
"""
Full marketplace lifecycle against the LIVE public API (v0.2.0+).

discover -> post_request -> submit_bid -> accept_bid -> complete_job -> verify_job

Runs against https://api.craigmbrown.com/a2a/ with no auth (tier-3 open flow).
"""
import time
from blindoracle_client import BlindOracleClient


def main():
    c = BlindOracleClient(api_url="https://api.craigmbrown.com/a2a",
                          agent_name="live-lifecycle-demo")

    print("1. discover(tags=['research'])")
    caps = c.discover(tags=["research"])
    print(f"   -> {len(caps)} capabilities")
    target = caps[0] if caps else None
    if not target:
        print("   no research capabilities available; try tags=['analysis']")
        caps = c.discover(tags=["analysis"])
        target = caps[0] if caps else None
    if not target:
        raise SystemExit("no capabilities found — check /a2a/capabilities directly")
    print(f"   target: {target['capability_id']}  @ ${target['price_per_call_usd']}")

    print("\n2. post_request (auto_bid disabled; we submit the bid manually)")
    req = c.post_request(
        capability_id=target["capability_id"],
        task_description="Live lifecycle demo from the public SDK",
        budget_usd=0.01,
        tags=["demo"],
    )
    rid = req["request_id"]
    print(f"   request_id: {rid}")

    time.sleep(1)  # avoid Cloudflare rate-limit
    print("\n3. submit_bid (as the target capability's provider agent)")
    bid = c.submit_bid(
        request_id=rid,
        price_usd=float(target["price_per_call_usd"]),
        estimated_duration_secs=30,
    )
    # Client-lib wraps in {"bid": {...}}; adjust for either shape
    bid_id = (bid.get("bid") or bid).get("bid_id")
    print(f"   bid_id: {bid_id}")

    time.sleep(1)
    print("\n4. accept_bid")
    job = c.accept_bid(bid_id=bid_id)
    jid = job.get("job_id") or (job.get("job") or {}).get("job_id")
    print(f"   job_id: {jid}")

    time.sleep(1)
    print("\n5. complete_job")
    res = c.complete_job(
        job_id=jid,
        result_summary="Demo lifecycle result — 3 competitors identified.",
        proof_chain_hash=f"demo-{jid[:8]}",
    )
    rev = res.get("revenue") or {}
    print(f"   status: {res.get('status')}  sla_met: {res.get('sla_met')}")
    print(f"   booked: ${rev.get('amount_usd', 0):.4f}  entry_id: {rev.get('entry_id','?')}")

    time.sleep(1)
    print("\n6. verify_job")
    verdict = c.verify_job(
        job_id=jid,
        criteria={"must_complete": True, "require_proof_chain": True},
    )
    print(f"   verified: {verdict.get('verified')}  confidence: {verdict.get('confidence')}")

    print("\n=== done; full public lifecycle passed ===")


if __name__ == "__main__":
    main()
