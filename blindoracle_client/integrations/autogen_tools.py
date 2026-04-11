"""
BlindOracle AutoGen Tools
Function-based tools compatible with AutoGen's register_function pattern.

Usage:
    import autogen
    from blindoracle_sdk.integrations.autogen_tools import register_blindoracle_tools

    assistant = autogen.AssistantAgent("assistant", llm_config={"config_list": [...]})
    user_proxy = autogen.UserProxyAgent("user_proxy", human_input_mode="NEVER")

    register_blindoracle_tools(assistant, user_proxy, api_key="bo_live_...")

    user_proxy.initiate_chat(
        assistant,
        message="What is the compliance risk on Aave-v3 today?"
    )
"""

import os
from typing import Optional, Annotated

from blindoracle_client.client import BlindOracleClient

try:
    from autogen import ConversableAgent
    from autogen import register_function
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False


def _make_tools(client: BlindOracleClient):
    """Return function definitions for AutoGen tool registration."""

    def check_defi_compliance(
        protocol: Annotated[str, "DeFi protocol name: aave-v3, uniswap-v4, compound-v3, curve, lido, maker-dao"],
    ) -> str:
        """Check DeFi protocol compliance and risk score via BlindOracle."""
        result = client.compliance.check(protocol)
        return (
            f"BlindOracle Compliance Result:\n"
            f"  Protocol: {result.protocol}\n"
            f"  Risk Score: {result.risk_score}/100\n"
            f"  Tail Risk: {result.tail_risk_pct}%\n"
            f"  Assessment: {'SAFE' if result.is_safe() else 'ELEVATED RISK'}\n"
            f"  Findings: {'; '.join(result.findings) if result.findings else 'None detected'}"
        )

    def get_prediction_markets(
        category: Annotated[str, "Market category: defi, ai, crypto, macro, or all"] = "all",
    ) -> str:
        """List active prediction markets from BlindOracle."""
        cat = None if category == "all" else category
        markets = client.markets.list(category=cat, limit=5)
        if not markets:
            return "No active BlindOracle markets found."
        lines = ["Active Prediction Markets:"]
        for m in markets:
            lines.append(f"  - {m.title} | P(yes)={m.yes_probability} | ID: {m.id}")
        return "\n".join(lines)

    def get_market_signal(
        category: Annotated[str, "Signal category: defi, ai, crypto, macro"] = "defi",
    ) -> str:
        """Get the latest market intelligence signal from BlindOracle."""
        signal = client.signals.latest(category=category)
        return (
            f"BlindOracle Signal [{signal.signal_type.upper()}]:\n"
            f"  Title: {signal.title}\n"
            f"  Confidence: {signal.confidence:.0%}\n"
            f"  Detail: {signal.body}"
        )

    return check_defi_compliance, get_prediction_markets, get_market_signal


def register_blindoracle_tools(
    caller: "ConversableAgent",
    executor: "ConversableAgent",
    api_key: Optional[str] = None,
) -> None:
    """
    Register BlindOracle tools with an AutoGen agent pair.

    Args:
        caller: The AssistantAgent that will call the tools
        executor: The UserProxyAgent that will execute the tools
        api_key: BlindOracle API key (or set BLINDORACLE_API_KEY env var)

    Example:
        import autogen
        from blindoracle_sdk.integrations.autogen_tools import register_blindoracle_tools

        config_list = [{"model": "gpt-4o", "api_key": "..."}]
        assistant = autogen.AssistantAgent("assistant", llm_config={"config_list": config_list})
        user_proxy = autogen.UserProxyAgent("user_proxy", human_input_mode="NEVER",
                                             max_consecutive_auto_reply=5)

        register_blindoracle_tools(assistant, user_proxy, api_key="bo_live_...")
    """
    if not AUTOGEN_AVAILABLE:
        raise ImportError(
            "pyautogen not installed. Run: pip install blindoracle-sdk[autogen]"
        )

    client = BlindOracleClient(api_key=api_key or os.environ.get("BLINDORACLE_API_KEY"))
    check_compliance, list_markets, get_signal = _make_tools(client)

    for func, name, desc in [
        (check_compliance, "check_defi_compliance",
         "Check DeFi protocol compliance risk via BlindOracle Chainlink-verified stress-test"),
        (list_markets, "get_prediction_markets",
         "List active prediction markets from BlindOracle"),
        (get_signal, "get_market_signal",
         "Get latest market intelligence signal from BlindOracle agent network"),
    ]:
        register_function(
            func,
            caller=caller,
            executor=executor,
            name=name,
            description=desc,
        )
