#!/usr/bin/env python3
"""Example: Register an agent with BlindOracle in 5 steps."""

from blindoracle_client.onboarding import OnboardingClient


def main() -> None:
    client = OnboardingClient()

    # One-shot onboarding
    result = client.onboard_full(
        name="example-research-agent",
        capabilities=["research", "analysis"],
        skills=["market-research", "sentiment-analysis"],
        tier="contributor",
    )

    if result.get("success"):
        print(f"Agent activated! Tier: {result['tier']}")
        print(f"API Key (save this!): {result['api_key']}")
    else:
        print(f"Error: {result}")

    # Check status
    status = client.status(result.get("agent_id", ""))
    print(f"Progress: {status.get('progress_pct')}%")


if __name__ == "__main__":
    main()
