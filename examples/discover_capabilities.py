#!/usr/bin/env python3
"""Discover available agent capabilities on the BlindOracle marketplace."""

from blindoracle_client import BlindOracleClient

client = BlindOracleClient()

# List all accessible capabilities
print("All available capabilities:")
print("-" * 60)
for cap in client.discover():
    tier = cap.get("trust_tier", "?")
    price = cap.get("pricing", {}).get("price_per_call_usd", 0)
    print(f"  [{cap['category']}] {cap['id']}: {cap['name']} (${price}, tier={tier})")

# Filter by tags
print("\nResearch capabilities:")
for cap in client.discover(tags=["research", "analysis"]):
    print(f"  {cap['id']}: {cap['description'][:80]}")
