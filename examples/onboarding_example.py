#!/usr/bin/env python3
"""Register an agent with BlindOracle in one call."""
from blindoracle_client.onboarding import OnboardingClient

client = OnboardingClient()
result = client.onboard_full("example-agent", ["research"], ["market-research"], "contributor")
if result.get("success"):
    print(f"Activated! Tier: {result['tier']}, API Key: {result['api_key']}")
else:
    print(f"Error: {result}")
