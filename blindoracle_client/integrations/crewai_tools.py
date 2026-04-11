"""
BlindOracle CrewAI Tools
@tool-decorated functions for CrewAI agents.

Usage:
    from blindoracle_sdk.integrations.crewai_tools import (
        blindoracle_compliance_check,
        blindoracle_list_markets,
        blindoracle_get_signal,
    )
    from crewai import Agent, Task, Crew

    analyst = Agent(
        role="DeFi Risk Analyst",
        goal="Identify and report DeFi protocol risk",
        backstory="Expert in DeFi protocol analysis",
        tools=[blindoracle_compliance_check, blindoracle_list_markets],
    )
"""

import os
from typing import Optional

from blindoracle_client.client import BlindOracleClient

try:
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    # Stub decorator so module can be imported without crewai
    def tool(func):  # type: ignore
        return func
    CREWAI_AVAILABLE = False

_client: Optional[BlindOracleClient] = None


def _get_client() -> BlindOracleClient:
    global _client
    if _client is None:
        _client = BlindOracleClient(
            api_key=os.environ.get("BLINDORACLE_API_KEY"),
        )
    return _client


@tool("BlindOracle DeFi Compliance Check")
def blindoracle_compliance_check(protocol: str) -> str:
    """
    Check DeFi protocol compliance risk using BlindOracle's Chainlink-verified stress-testing.
    Input: protocol name (e.g. 'aave-v3', 'uniswap-v4', 'compound-v3', 'curve', 'lido', 'maker-dao')
    Returns: risk_score (0-100), tail_risk_pct, and specific risk findings.
    """
    result = _get_client().compliance.check(protocol)
    return (
        f"Protocol: {result.protocol} | "
        f"Risk Score: {result.risk_score}/100 | "
        f"Tail Risk: {result.tail_risk_pct}% | "
        f"Status: {'SAFE' if result.is_safe() else 'RISKY'} | "
        f"Findings: {'; '.join(result.findings) if result.findings else 'None'}"
    )


@tool("BlindOracle List Active Markets")
def blindoracle_list_markets(category: str = "all") -> str:
    """
    List active prediction markets on BlindOracle.
    Input: category ('defi', 'ai', 'crypto', 'macro', or 'all')
    Returns: list of markets with probabilities and volumes.
    """
    cat = None if category == "all" else category
    markets = _get_client().markets.list(category=cat, limit=5)
    if not markets:
        return "No active markets found."
    return "\n".join([
        f"{m.title} | P(yes)={m.yes_probability} | Vol=${m.total_volume:.0f} | ID={m.id}"
        for m in markets
    ])


@tool("BlindOracle Market Signal")
def blindoracle_get_signal(category: str = "defi") -> str:
    """
    Get the latest market intelligence signal from BlindOracle's agent network.
    Input: category ('defi', 'ai', 'crypto', 'macro')
    Returns: signal type, confidence score, and actionable body text.
    """
    signal = _get_client().signals.latest(category=category)
    return (
        f"[{signal.signal_type.upper()}] {signal.title} | "
        f"Confidence: {signal.confidence:.0%} | "
        f"{signal.body}"
    )
