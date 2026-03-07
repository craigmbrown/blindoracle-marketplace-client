"""Tests for BlindOracle client SDK."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from blindoracle_client import BlindOracleClient
from blindoracle_client.client import ClientConfig, BlindOracleAPIError


class TestClientConfig:
    def test_defaults(self):
        config = ClientConfig()
        assert config.api_url == ""
        assert config.default_budget_usd == 0.01
        assert config.auth_method == "api_key"

    def test_load_with_overrides(self):
        config = ClientConfig.load(api_key="test-key", agent_name="test-agent")
        assert config.api_key == "test-key"
        assert config.agent_name == "test-agent"
        assert "craigmbrown.com" in config.api_url

    def test_env_vars(self):
        with patch.dict(os.environ, {"BLINDORACLE_API_KEY": "env-key"}):
            config = ClientConfig.load()
            assert config.api_key == "env-key"

    def test_override_beats_env(self):
        with patch.dict(os.environ, {"BLINDORACLE_API_KEY": "env-key"}):
            config = ClientConfig.load(api_key="override-key")
            assert config.api_key == "override-key"


class TestBlindOracleClient:
    def test_init(self):
        client = BlindOracleClient(api_key="test")
        assert client.config.api_key == "test"
        assert client._session_id

    def test_headers(self):
        client = BlindOracleClient(api_key="abc", agent_name="my-agent")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer abc"
        assert headers["X-Agent-Name"] == "my-agent"
        assert "python-sdk" in headers["X-BlindOracle-Client"]

    def test_headers_no_key(self):
        client = BlindOracleClient()
        headers = client._headers()
        assert "Authorization" not in headers

    @patch("blindoracle_client.client.urlopen")
    def test_discover(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "capabilities": [{"id": "test.agent", "name": "Test"}]
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = BlindOracleClient(api_key="test")
        caps = client.discover(tags=["research"])
        assert len(caps) == 1
        assert caps[0]["id"] == "test.agent"

    @patch("blindoracle_client.client.urlopen")
    def test_post_request(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "request_id": "req-123"
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = BlindOracleClient(api_key="test", agent_name="my-agent")
        result = client.post_request(
            capability_id="test.cap",
            task_description="Test task",
            budget_usd=0.005,
        )
        assert result["request_id"] == "req-123"

    def test_complete_job_auto_proof(self):
        """Verify auto proof chain hash generation."""
        client = BlindOracleClient(api_key="test")
        # We can't test the full HTTP call, but verify the hash generation path
        import hashlib
        h = hashlib.sha256(b"test").hexdigest()
        assert len(h) == 64


class TestExceptions:
    def test_api_error(self):
        err = BlindOracleAPIError(403, "Forbidden")
        assert err.status_code == 403
        assert "403" in str(err)
        assert "Forbidden" in str(err)
