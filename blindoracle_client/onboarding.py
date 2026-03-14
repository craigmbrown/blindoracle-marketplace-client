"""BlindOracle Agent Onboarding Client SDK."""
import requests
from typing import Any, Dict, List, Optional

class OnboardingClient:
    DEFAULT_BASE_URL = "https://api.craigmbrown.com"

    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key
        self._session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def register(self, name: str, capabilities: List[str], nostr_pubkey: str = "", evm_address: str = "") -> Dict[str, Any]:
        resp = self._session.post(f"{self.base_url}/v1/agents/register", json={"name": name, "capabilities": capabilities, "nostr_pubkey": nostr_pubkey, "evm_address": evm_address}, headers={"Content-Type": "application/json"}, timeout=30)
        data = resp.json()
        if data.get("api_key"):
            self.api_key = data["api_key"]
        return data

    def register_chain(self, agent_id: str, team: str = "external") -> Dict[str, Any]:
        return self._session.post(f"{self.base_url}/v1/agents/{agent_id}/chain", json={"team": team}, headers=self._headers(), timeout=30).json()

    def declare_skills(self, agent_id: str, skills: List[str]) -> Dict[str, Any]:
        return self._session.post(f"{self.base_url}/v1/agents/{agent_id}/skills", json={"skills": skills}, headers=self._headers(), timeout=30).json()

    def submit_proof(self, agent_id: str, kind: int = 30010, data: Optional[Dict] = None) -> Dict[str, Any]:
        return self._session.post(f"{self.base_url}/v1/agents/{agent_id}/proofs", json={"kind": kind, "data": data or {}}, headers=self._headers(), timeout=30).json()

    def activate(self, agent_id: str, tier: str = "contributor", payment_proof: str = "") -> Dict[str, Any]:
        return self._session.post(f"{self.base_url}/v1/agents/{agent_id}/activate", json={"tier": tier, "payment_proof": payment_proof}, headers=self._headers(), timeout=30).json()

    def status(self, agent_id: str) -> Dict[str, Any]:
        return self._session.get(f"{self.base_url}/v1/agents/{agent_id}/status", headers=self._headers(), timeout=30).json()

    def onboard_full(self, name: str, capabilities: List[str], skills: List[str], tier: str = "contributor", proof_summary: str = "Initial onboarding proof") -> Dict[str, Any]:
        reg = self.register(name, capabilities)
        if not reg.get("success"):
            return reg
        aid = reg["agent_id"]
        self.register_chain(aid)
        self.declare_skills(aid, skills)
        self.submit_proof(aid, 30010, {"summary": proof_summary})
        result = self.activate(aid, tier)
        result["api_key"] = reg["api_key"]
        return result
