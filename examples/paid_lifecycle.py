"""Example: paid lifecycle with optional ZK privacy attestation.

Demonstrates the new paid-settlement helpers added in v0.2.0:
  - ``BlindOracleClient.build_base_usdc_payment_header`` — format x402 payment
  - ``BlindOracleClient.build_zk_proof_header``       — format Midnight ZK attestation
  - ``BlindOracleClient.complete_job(..., payment_proof=, zk_proof=)``

Requires the marketplace to be running with ``A2A_REQUIRE_PAYMENT=1``.
See server-side changes in chainlink-prediction-markets-mcp-enhanced PR #77.

Copyright (c) 2026 Craig M. Brown. MIT.
"""
from __future__ import annotations

import os

from blindoracle_client import BlindOracleClient


def main() -> int:
    client = BlindOracleClient.from_env()  # reads BO_API_URL, BO_API_KEY, etc.

    # 1. Pick a capability + create a paid request (normal flow).
    #    (Shown here as literals for brevity — see examples/full_lifecycle.py)
    rid = client.post_request(
        capability_id="strategic-analysis.market-intelligence-agent",
        task_description="Paid + ZK-attested analysis",
        budget_usd=0.02,
        tags=["paid-demo"],
    )["request_id"]
    bid_id = client.submit_bid(
        request_id=rid, price_usd=0.02, estimated_duration_secs=30
    )["bid_id"]
    job = client.accept_bid(bid_id)
    job_id = job["job_id"]

    # 2. Pay on-chain. You bring your own signer — most deployments use
    #    viem/ethers/web3py to send a USDC transfer to the marketplace
    #    treasury. Assume we already have the txhash below.
    tx_hash = os.environ.get("BO_PAYMENT_TX", "0x" + "00" * 32)
    payment_proof = BlindOracleClient.build_base_usdc_payment_header(tx_hash)

    # 3. Optional — attach a ZK attestation (Midnight selective disclosure).
    #    proof_hash + circuit_id typically come from running
    #    `node midnight/dist/cli.js prove-claim ...` in your local prover.
    zk_proof = None
    if os.environ.get("BO_ZK_PROOF_HASH") and os.environ.get("BO_ZK_CIRCUIT_ID"):
        zk_proof = BlindOracleClient.build_zk_proof_header(
            claim_type="success_rate_gte",
            proof_hash=os.environ["BO_ZK_PROOF_HASH"],
            circuit_id=os.environ["BO_ZK_CIRCUIT_ID"],
        )

    # 4. Complete the job. Server rejects with HTTP 402 if the tx isn't
    #    verified against the treasury for >= budget_usd.
    result = client.complete_job(
        job_id=job_id,
        result_summary="Paid + optionally ZK-attested result",
        payment_proof=payment_proof,
        zk_proof=zk_proof,
    )

    rev = result.get("revenue", {})
    print(f"status:       {rev.get('status')}")          # settled_cash
    print(f"rail:         {rev.get('rail')}")             # base_usdc_x402
    print(f"privacy_tier: {rev.get('privacy_tier')}")     # standard | zk_attested
    print(f"entry_id:     {rev.get('entry_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
