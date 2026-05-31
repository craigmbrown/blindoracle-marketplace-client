"""Markets / Compliance / Signals namespaces for the canonical BlindOracle client.

These hit the gateway's /v1 SDK routes (markets, compliance, signals) via the
client's _root_get / _root_post helpers, so the one canonical package
(blindoracle-marketplace-client) covers the full surface advertised on the site.
"""
from typing import List, Optional


# --------------------------------------------------------------------------- #
# Markets
# --------------------------------------------------------------------------- #
class Market:
    """A BlindOracle prediction market."""
    def __init__(self, data: dict):
        self.id = data.get("id")
        self.title = data.get("title")
        self.status = data.get("status")
        self.resolution_date = data.get("resolution_date")
        self.yes_probability = data.get("yes_probability")
        self.total_volume = data.get("total_volume_usd", 0)
        self.oracle = data.get("oracle_source")
        self.raw = data

    def __repr__(self):
        return f"<Market id={self.id!r} title={self.title!r} p={self.yes_probability}>"


class MarketsAPI:
    def __init__(self, client):
        self._c = client

    def list(self, status: Optional[str] = "active", category: Optional[str] = None,
             limit: int = 20, offset: int = 0) -> List[Market]:
        params = {"limit": limit, "offset": offset}
        if status and status != "all":
            params["status"] = status
        if category:
            params["category"] = category
        data = self._c._root_get("v1/markets", params)
        return [Market(m) for m in data.get("markets", [])]

    def get(self, market_id: str) -> Market:
        return Market(self._c._root_get(f"v1/markets/{market_id}"))

    def predict(self, market_id: str, outcome: str, amount_sats: int,
                agent_id: Optional[str] = None) -> dict:
        body = {"market_id": market_id, "outcome": outcome, "amount_sats": amount_sats}
        if agent_id:
            body["agent_id"] = agent_id
        return self._c._root_post("v1/markets/predict", body)


# --------------------------------------------------------------------------- #
# Compliance
# --------------------------------------------------------------------------- #
class ComplianceResult:
    def __init__(self, data: dict):
        self.protocol = data.get("protocol")
        self.address = data.get("address")
        self.risk_score = data.get("risk_score")
        self.tail_risk_pct = data.get("tail_risk_pct")
        self.findings = data.get("findings", [])
        self.chainlink_feed = data.get("chainlink_feed")
        self.cost_usd = data.get("cost_usd", 0.50)
        self.raw = data

    def is_safe(self, min_score: int = 70) -> bool:
        return (self.risk_score or 0) >= min_score

    def __repr__(self):
        return f"<ComplianceResult protocol={self.protocol!r} score={self.risk_score}>"


class ComplianceAPI:
    def __init__(self, client):
        self._c = client

    def check(self, protocol: str, address: Optional[str] = None) -> ComplianceResult:
        body = {"protocol": protocol}
        if address:
            body["address"] = address
        return ComplianceResult(self._c._root_post("v1/compliance/check", body))

    def check_all(self) -> List[ComplianceResult]:
        data = self._c._root_post("v1/compliance/check-all", {})
        return [ComplianceResult(r) for r in data.get("results", [])]

    def get_supported_protocols(self) -> List[str]:
        return self._c._root_get("v1/compliance/protocols").get("protocols", [])


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #
class Signal:
    def __init__(self, data: dict):
        self.id = data.get("id")
        self.signal_type = data.get("signal_type")
        self.category = data.get("category")
        self.title = data.get("title")
        self.body = data.get("body")
        self.confidence = data.get("confidence")
        self.related_markets = data.get("related_markets", [])
        self.generated_at = data.get("generated_at")
        self.raw = data

    def __repr__(self):
        return f"<Signal type={self.signal_type!r} confidence={self.confidence}>"


class SignalsAPI:
    def __init__(self, client):
        self._c = client

    def latest(self, category: Optional[str] = None) -> Signal:
        params = {"category": category} if category else None
        return Signal(self._c._root_get("v1/signals/latest", params))

    def list(self, category: Optional[str] = None, signal_type: Optional[str] = None,
             limit: int = 10) -> List[Signal]:
        params = {"limit": limit}
        if category:
            params["category"] = category
        if signal_type:
            params["signal_type"] = signal_type
        data = self._c._root_get("v1/signals", params)
        return [Signal(s) for s in data.get("signals", [])]
