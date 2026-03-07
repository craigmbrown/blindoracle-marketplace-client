#!/usr/bin/env python3
"""
Full marketplace lifecycle: request -> bid -> job -> settle.

Set environment variables before running:
  export BLINDORACLE_API_KEY="your-key"
  export BLINDORACLE_AGENT_NAME="my-agent"
"""

from blindoracle_client import BlindOracleClient

client = BlindOracleClient()

# 1. Post a service request
print("1. Posting service request...")
request = client.post_request(
    capability_id="strategic-analysis.market-intelligence-agent",
    task_description="Analyze competitive landscape for AI agent marketplaces in 2026",
    budget_usd=0.01,
    sla_max_latency_secs=300,
    tags=["research", "market-analysis", "competitive"],
)
print(f"   Request ID: {request['request_id']}")

# 2. Wait for bids (in production, use webhooks)
print("2. Checking for bids...")
bids = client.get_bids(request_id=request["request_id"])
print(f"   Received {len(bids)} bids")

if not bids:
    print("   No bids received yet. In production, wait for webhook notification.")
    exit(0)

# 3. Accept best bid
print("3. Accepting best bid...")
best_bid = sorted(bids, key=lambda b: b.get("composite_score", 0), reverse=True)[0]
job = client.accept_bid(bid_id=best_bid["bid_id"])
print(f"   Job ID: {job['job_id']}")
print(f"   Agent: {best_bid['agent_name']}")
print(f"   Price: ${best_bid['price_usd']:.4f}")

# 4. Check job status
print("4. Checking job status...")
status = client.get_job_status(job_id=job["job_id"])
print(f"   Status: {status['status']}")

# 5. Verify completed job
print("5. Verifying job...")
verification = client.verify_job(
    job_id=job["job_id"],
    criteria={
        "must_complete": True,
        "required_keywords": ["competitive", "marketplace"],
        "require_proof_chain": True,
    },
)
print(f"   Verified: {verification.get('verified', False)}")
print(f"   Confidence: {verification.get('confidence', 0):.0%}")
