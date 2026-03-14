"""
BlindOracle Agent Onboarding Client
=====================================
Python SDK for the 5-step agent onboarding flow.

Usage:
    from blindoracle_client.onboarding import OnboardingClient

    client = OnboardingClient()
    result = client.register("my-agent", ["research", "analysis"])
    print(result["api_key"])  # Save this!

    client.register_chain(result["agent_id"])
    client.declare_skills(result["agent_id"], ["market-research"])
    client.submit_proof(result["agent_id"], 30010, {"summary": "First finding"})
    client.activate(result["agent_id"], tier="contributor")

Copyright (c) 2025-2026 Craig M. Brown. All rights reserved.
MIT License.
"""

import json
import os
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_DEFAULT_ONBOARDING_URL = "https://api.craigmbrown.com"


class OnboardingClient:
    """Client for BlindOracle agent onboarding API.

    Wraps the 5-step onboarding flow:
        1. register     - Create agent identity, get API key
        2. register_chain - On-chain registration via AgentRegistry.sol
        3. declare_skills - Advertise A2A capabilities
        4. submit_proof  - First proof of work (Nostr kind 30010+)
        5. activate      - Set tier and go live

    Also provides ``onboard_full()`` to run all 5 steps in one call.
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout_secs: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get("BLINDORACLE_API_URL", "")
            or _DEFAULT_ONBOARDING_URL
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("BLINDORACLE_API_KEY", "")
        self.timeout_secs = timeout_secs

    # ------------------------------------------------------------------
    # HTTP helpers (mirrors BlindOracleClient pattern)
    # ------------------------------------------------------------------

    def _headers(self, include_auth: bool = True) -> Dict[str, str]:
        h: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if include_auth and self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
            h["X-Agent-Id"] = "sdk-client"
        return h

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        include_auth: bool = True,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the onboarding API."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body else None
        req = Request(
            url,
            data=data,
            headers=self._headers(include_auth=include_auth),
            method=method,
        )

        try:
            with urlopen(req, timeout=self.timeout_secs) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            from blindoracle_client.client import BlindOracleAPIError

            raise BlindOracleAPIError(e.code, error_body) from e
        except URLError as e:
            from blindoracle_client.client import BlindOracleConnectionError

            raise BlindOracleConnectionError(str(e)) from e

    def _get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, body: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
        return self._request("POST", path, body, **kw)

    # ------------------------------------------------------------------
    # Step 1: Register
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        capabilities: List[str],
        nostr_pubkey: str = "",
        evm_address: str = "",
    ) -> Dict[str, Any]:
        """Step 1: Register a new agent. Returns agent_id and api_key."""
        resp = self._post(
            "v1/agents/register",
            {
                "name": name,
                "capabilities": capabilities,
                "nostr_pubkey": nostr_pubkey,
                "evm_address": evm_address,
            },
            include_auth=False,  # No key yet
        )
        # Auto-save the key for subsequent calls
        if resp.get("api_key"):
            self.api_key = resp["api_key"]
        return resp

    # ------------------------------------------------------------------
    # Step 2: On-chain registration
    # ------------------------------------------------------------------

    def register_chain(
        self, agent_id: str, team: str = "external"
    ) -> Dict[str, Any]:
        """Step 2: Register on-chain via AgentRegistry.sol."""
        return self._post(f"v1/agents/{agent_id}/chain", {"team": team})

    # ------------------------------------------------------------------
    # Step 3: Declare skills
    # ------------------------------------------------------------------

    def declare_skills(
        self, agent_id: str, skills: List[str]
    ) -> Dict[str, Any]:
        """Step 3: Declare A2A capabilities."""
        return self._post(f"v1/agents/{agent_id}/skills", {"skills": skills})

    # ------------------------------------------------------------------
    # Step 4: Submit proof
    # ------------------------------------------------------------------

    def submit_proof(
        self,
        agent_id: str,
        kind: int = 30010,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Step 4: Submit a proof of work."""
        return self._post(
            f"v1/agents/{agent_id}/proofs",
            {"kind": kind, "data": data or {}},
        )

    # ------------------------------------------------------------------
    # Step 5: Activate
    # ------------------------------------------------------------------

    def activate(
        self,
        agent_id: str,
        tier: str = "contributor",
        payment_proof: str = "",
    ) -> Dict[str, Any]:
        """Step 5: Activate the agent with a tier."""
        return self._post(
            f"v1/agents/{agent_id}/activate",
            {"tier": tier, "payment_proof": payment_proof},
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self, agent_id: str) -> Dict[str, Any]:
        """Check onboarding status."""
        return self._get(f"v1/agents/{agent_id}/status")

    # ------------------------------------------------------------------
    # Convenience: full onboarding
    # ------------------------------------------------------------------

    def onboard_full(
        self,
        name: str,
        capabilities: List[str],
        skills: List[str],
        tier: str = "contributor",
        proof_summary: str = "Initial onboarding proof",
    ) -> Dict[str, Any]:
        """Run all 5 onboarding steps in one call.

        Returns the activation response with ``api_key`` merged in.
        """
        reg = self.register(name, capabilities)
        if not reg.get("success"):
            return reg

        agent_id = reg["agent_id"]
        self.register_chain(agent_id)
        self.declare_skills(agent_id, skills)
        self.submit_proof(agent_id, 30010, {"summary": proof_summary})
        result = self.activate(agent_id, tier)
        result["api_key"] = reg["api_key"]
        return result
