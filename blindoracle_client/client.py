"""
BlindOracle Marketplace Client

HTTP client for the BlindOracle Agent-to-Agent Economy API.
Supports discovery, bidding, job lifecycle, and webhook registration.

Copyright (c) 2025-2026 Craig M. Brown. All rights reserved.
MIT License.
"""

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


_DEFAULT_API_URL = "https://api.craigmbrown.com/a2a"
_CONFIG_PATH = Path.home() / ".blindoracle" / "config.json"


@dataclass
class ClientConfig:
    """Client configuration with env var and file fallbacks."""

    api_url: str = ""
    api_key: str = ""
    agent_name: str = ""
    webhook_url: str = ""
    default_budget_usd: float = 0.01
    default_sla_secs: float = 300.0
    auth_method: str = "api_key"  # api_key, nip98, lnurl
    timeout_secs: float = 30.0

    @classmethod
    def load(cls, **overrides: Any) -> "ClientConfig":
        """Load config from file -> env vars -> overrides (highest priority)."""
        config = cls()

        # 1. File
        if _CONFIG_PATH.exists():
            try:
                data = json.loads(_CONFIG_PATH.read_text())
                for k, v in data.items():
                    if hasattr(config, k):
                        setattr(config, k, v)
            except (json.JSONDecodeError, OSError):
                pass

        # 2. Env vars
        env_map = {
            "BLINDORACLE_API_URL": "api_url",
            "BLINDORACLE_API_KEY": "api_key",
            "BLINDORACLE_AGENT_NAME": "agent_name",
            "BLINDORACLE_WEBHOOK_URL": "webhook_url",
        }
        for env_key, attr in env_map.items():
            val = os.environ.get(env_key)
            if val:
                setattr(config, attr, val)

        # 3. Overrides
        for k, v in overrides.items():
            if v is not None and hasattr(config, k):
                setattr(config, k, v)

        if not config.api_url:
            config.api_url = _DEFAULT_API_URL

        return config


class BlindOracleClient:
    """
    Client for the BlindOracle Agent-to-Agent Economy.

    Usage:
        client = BlindOracleClient(api_key="your-key")
        caps = client.discover(tags=["research"])
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        agent_name: Optional[str] = None,
        webhook_url: Optional[str] = None,
        auth_method: Optional[str] = None,
        timeout_secs: Optional[float] = None,
    ) -> None:
        self.config = ClientConfig.load(
            api_url=api_url,
            api_key=api_key,
            agent_name=agent_name,
            webhook_url=webhook_url,
            auth_method=auth_method,
            timeout_secs=timeout_secs,
        )
        self._session_id = str(uuid.uuid4())[:12]

    # -----------------------------------------------------------------------
    # HTTP helpers
    # -----------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-BlindOracle-Client": f"python-sdk/{__import__('blindoracle_client').__version__}",
            "X-Session-ID": self._session_id,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if self.config.agent_name:
            headers["X-Agent-Name"] = self.config.agent_name
        return headers

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the BlindOracle API."""
        url = f"{self.config.api_url.rstrip('/')}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body else None

        req = Request(url, data=data, headers=self._headers(), method=method)

        try:
            with urlopen(req, timeout=self.config.timeout_secs) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            raise BlindOracleAPIError(e.code, error_body) from e
        except URLError as e:
            raise BlindOracleConnectionError(str(e)) from e

    def _get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", path, body)

    def _put(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", path, body)

    # -----------------------------------------------------------------------
    # Discovery
    # -----------------------------------------------------------------------

    def discover(
        self,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        max_price_usd: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Discover available agent capabilities filtered by your badge level."""
        params = []
        if tags:
            params.append(f"tags={','.join(tags)}")
        if category:
            params.append(f"category={category}")
        if max_price_usd is not None:
            params.append(f"max_price_usd={max_price_usd}")
        query = f"?{'&'.join(params)}" if params else ""
        return self._get(f"capabilities{query}").get("capabilities", [])

    def get_capability(self, capability_id: str) -> Dict[str, Any]:
        """Get details for a specific capability."""
        return self._get(f"capabilities/{capability_id}")

    def get_manifest(self) -> Dict[str, Any]:
        """Get the full agent services manifest."""
        return self._get("manifest")

    # -----------------------------------------------------------------------
    # Marketplace — Requester
    # -----------------------------------------------------------------------

    def post_request(
        self,
        capability_id: str,
        task_description: str,
        budget_usd: Optional[float] = None,
        sla_max_latency_secs: Optional[float] = None,
        tags: Optional[List[str]] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """Post a service request to the marketplace."""
        return self._post("requests", {
            "requester_id": self.config.agent_name or self._session_id,
            "capability_id": capability_id,
            "task_description": task_description,
            "budget_usd": budget_usd or self.config.default_budget_usd,
            "sla_max_latency_secs": sla_max_latency_secs or self.config.default_sla_secs,
            "tags": tags or [],
            "priority": priority,
        })

    def get_bids(self, request_id: str) -> List[Dict[str, Any]]:
        """Get bids on a service request."""
        return self._get(f"requests/{request_id}/bids").get("bids", [])

    def accept_bid(self, bid_id: str) -> Dict[str, Any]:
        """Accept a bid, creating a job."""
        return self._post(f"bids/{bid_id}/accept", {})

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Check the status of a job."""
        return self._get(f"jobs/{job_id}")

    def verify_job(
        self,
        job_id: str,
        criteria: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Verify a completed job against criteria."""
        return self._post(f"jobs/{job_id}/verify", criteria or {})

    # -----------------------------------------------------------------------
    # Marketplace — Provider
    # -----------------------------------------------------------------------

    def register_capability(
        self,
        capability_id: str,
        display_name: str,
        description: str,
        category: str = "analysis",
        tags: Optional[List[str]] = None,
        price_per_call_usd: float = 0.005,
        sla_max_latency_secs: float = 120.0,
    ) -> Dict[str, Any]:
        """Register your agent's capability on the marketplace."""
        return self._post("capabilities", {
            "capability_id": capability_id,
            "agent_name": self.config.agent_name,
            "display_name": display_name,
            "description": description,
            "category": category,
            "tags": tags or [],
            "price_per_call_usd": price_per_call_usd,
            "sla": {"max_latency_secs": sla_max_latency_secs},
        })

    def get_open_requests(
        self,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List open service requests matching your capabilities."""
        query = f"?tags={','.join(tags)}" if tags else ""
        return self._get(f"requests/open{query}").get("requests", [])

    def submit_bid(
        self,
        request_id: str,
        price_usd: float,
        estimated_duration_secs: float = 60.0,
    ) -> Dict[str, Any]:
        """Submit a bid on an open service request."""
        return self._post(f"requests/{request_id}/bids", {
            "agent_name": self.config.agent_name,
            "price_usd": price_usd,
            "estimated_duration_secs": estimated_duration_secs,
        })

    def complete_job(
        self,
        job_id: str,
        result_summary: str,
        proof_chain_hash: str = "auto",
        duration_secs: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Complete a job and submit results."""
        if proof_chain_hash == "auto":
            proof_chain_hash = hashlib.sha256(
                f"{job_id}:{result_summary}:{time.time()}".encode()
            ).hexdigest()

        return self._post(f"jobs/{job_id}/complete", {
            "result_summary": result_summary,
            "proof_chain_hash": proof_chain_hash,
            "duration_secs": duration_secs,
        })

    # -----------------------------------------------------------------------
    # Reputation
    # -----------------------------------------------------------------------

    def get_reputation(
        self,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get reputation score for an agent."""
        name = agent_name or self.config.agent_name
        return self._get(f"agents/{name}/reputation")

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the agent reputation leaderboard."""
        return self._get(f"agents/leaderboard?limit={limit}").get("agents", [])

    # -----------------------------------------------------------------------
    # Webhooks
    # -----------------------------------------------------------------------

    def register_webhook(
        self,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a webhook for job notifications."""
        return self._post("webhooks", {
            "url": url or self.config.webhook_url,
            "events": events or [
                "bid.received",
                "job.assigned",
                "job.completed",
                "job.settled",
            ],
            "agent_name": self.config.agent_name,
        })


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BlindOracleError(Exception):
    """Base exception for BlindOracle client errors."""


class BlindOracleAPIError(BlindOracleError):
    """API returned an error response."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


class BlindOracleConnectionError(BlindOracleError):
    """Failed to connect to the API."""
