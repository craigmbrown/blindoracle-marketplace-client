"""
BlindOracle LangChain Tools
Drop-in tools for LangChain agents to access BlindOracle's prediction market API.

Usage:
    from blindoracle_sdk.integrations.langchain_tools import get_blindoracle_tools
    from langchain.agents import initialize_agent, AgentType
    from langchain_openai import ChatOpenAI

    tools = get_blindoracle_tools(api_key="bo_live_...")
    agent = initialize_agent(tools, ChatOpenAI(), agent=AgentType.OPENAI_FUNCTIONS)
    agent.run("Check the compliance risk score for Aave-v3")
"""

from typing import List, Optional, Type

try:
    from langchain.tools import BaseTool
    from langchain.callbacks.manager import CallbackManagerForToolRun
    from pydantic import BaseModel, Field
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # Provide stub base classes so module can be imported without langchain
    class BaseTool:  # type: ignore
        pass
    class BaseModel:  # type: ignore
        pass
    def Field(*args, **kwargs):  # type: ignore
        return None

from blindoracle_client.client import BlindOracleClient


# ── Input Schemas ──────────────────────────────────────────────────────────

class ComplianceCheckInput(BaseModel):
    protocol: str = Field(description="DeFi protocol name (e.g. 'aave-v3', 'uniswap-v4', 'compound-v3')")

class MarketListInput(BaseModel):
    category: Optional[str] = Field(default=None, description="Market category: 'defi', 'ai', 'crypto', 'macro'")
    limit: int = Field(default=5, description="Number of markets to return (1-20)")

class MarketGetInput(BaseModel):
    market_id: str = Field(description="Market ID to retrieve")

class SignalInput(BaseModel):
    category: Optional[str] = Field(default=None, description="Signal category: 'defi', 'ai', 'crypto', 'macro'")


# ── Tools ──────────────────────────────────────────────────────────────────

class BlindOracleComplianceTool(BaseTool):
    """Check DeFi protocol compliance risk via Chainlink-verified data."""
    name: str = "blindoracle_compliance_check"
    description: str = (
        "Check the compliance risk score for a DeFi protocol using BlindOracle's "
        "Chainlink-verified stress-testing. Returns risk_score (0-100, higher is safer), "
        "tail_risk_pct (probability of >10% drawdown), and specific risk findings. "
        "Supports: aave-v3, uniswap-v4, compound-v3, curve, lido, maker-dao. "
        "Cost: $0.50/call."
    )
    args_schema: Type[BaseModel] = ComplianceCheckInput

    client: object = None  # BlindOracleClient

    class Config:
        arbitrary_types_allowed = True

    def _run(self, protocol: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        result = self.client.compliance.check(protocol)
        return (
            f"Protocol: {result.protocol}\n"
            f"Risk Score: {result.risk_score}/100 ({'SAFE' if result.is_safe() else 'RISKY'})\n"
            f"Tail Risk (10%+ drawdown): {result.tail_risk_pct}%\n"
            f"Chainlink Feed: {result.chainlink_feed}\n"
            f"Findings: {'; '.join(result.findings) if result.findings else 'None'}\n"
            f"Verified At: {result.verified_at}"
        )

    async def _arun(self, protocol: str, run_manager=None) -> str:
        return self._run(protocol)


class BlindOracleMarketsListTool(BaseTool):
    """List active prediction markets from BlindOracle."""
    name: str = "blindoracle_list_markets"
    description: str = (
        "List active prediction markets on BlindOracle. Returns market titles, "
        "current yes/no probability, volume, and resolution date. "
        "Useful for understanding what events are being predicted and at what probability."
    )
    args_schema: Type[BaseModel] = MarketListInput

    client: object = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        category: Optional[str] = None,
        limit: int = 5,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        markets = self.client.markets.list(category=category, limit=limit)
        if not markets:
            return "No active markets found."
        lines = [f"Active BlindOracle Markets ({len(markets)} returned):"]
        for m in markets:
            lines.append(
                f"- [{m.id}] {m.title} | P(yes)={m.yes_probability} | "
                f"Vol=${m.total_volume:.0f} | Resolves: {m.resolution_date}"
            )
        return "\n".join(lines)

    async def _arun(self, category=None, limit=5, run_manager=None) -> str:
        return self._run(category=category, limit=limit)


class BlindOracleSignalTool(BaseTool):
    """Get the latest market intelligence signal from BlindOracle."""
    name: str = "blindoracle_get_signal"
    description: str = (
        "Get the latest market intelligence signal from BlindOracle's 25-agent analysis network. "
        "Signals cover DeFi risk, crypto opportunities, AI market trends, and macro conditions. "
        "Each signal includes a confidence score (0-1) and related prediction markets."
    )
    args_schema: Type[BaseModel] = SignalInput

    client: object = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        category: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        signal = self.client.signals.latest(category=category)
        return (
            f"Signal Type: {signal.signal_type}\n"
            f"Title: {signal.title}\n"
            f"Confidence: {signal.confidence:.0%}\n"
            f"Body: {signal.body}\n"
            f"Related Markets: {', '.join(signal.related_markets) if signal.related_markets else 'None'}\n"
            f"Generated: {signal.generated_at}"
        )

    async def _arun(self, category=None, run_manager=None) -> str:
        return self._run(category=category)


# ── Factory ────────────────────────────────────────────────────────────────

def get_blindoracle_tools(
    api_key: Optional[str] = None,
    base_url: str = BlindOracleClient.DEFAULT_BASE_URL,
    include: Optional[List[str]] = None,
) -> List[BaseTool]:
    """
    Get BlindOracle tools for use with LangChain agents.

    Args:
        api_key: BlindOracle API key (optional for public endpoints)
        base_url: API base URL
        include: List of tool names to include. Default: all tools.
                 Options: ["compliance", "markets", "signals"]

    Returns:
        List of LangChain BaseTool instances

    Example:
        from langchain.agents import initialize_agent, AgentType
        from langchain_openai import ChatOpenAI

        tools = get_blindoracle_tools(api_key="bo_live_...")
        llm = ChatOpenAI(model="gpt-4o")
        agent = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)
        result = agent.run("What's the current DeFi risk environment?")
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain not installed. Run: pip install blindoracle-sdk[langchain]"
        )

    client = BlindOracleClient(api_key=api_key, base_url=base_url)

    all_tools = {
        "compliance": BlindOracleComplianceTool(client=client),
        "markets": BlindOracleMarketsListTool(client=client),
        "signals": BlindOracleSignalTool(client=client),
    }

    if include:
        return [all_tools[name] for name in include if name in all_tools]
    return list(all_tools.values())
