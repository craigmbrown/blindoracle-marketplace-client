"""Smoke tests against the live public API.

These tests hit api.craigmbrown.com and require network. Skip in offline CI
with `BO_SKIP_LIVE=1`.
"""
import json
import os
import unittest
from urllib.request import Request, urlopen

LIVE = not os.environ.get("BO_SKIP_LIVE")
BASE = "https://api.craigmbrown.com/a2a"


def _get(path):
    req = Request(f"{BASE}{path}",
                  headers={"User-Agent": "bo-sdk-smoke/1.0",
                           "Accept": "application/json"})
    with urlopen(req, timeout=10) as r:
        return r.getcode(), json.loads(r.read().decode())


@unittest.skipUnless(LIVE, "BO_SKIP_LIVE set")
class TestLiveAPI(unittest.TestCase):

    def test_capabilities_returns_list(self):
        status, body = _get("/capabilities")
        self.assertEqual(status, 200)
        self.assertIn("count", body)
        self.assertIn("capabilities", body)
        self.assertIsInstance(body["capabilities"], list)

    def test_capabilities_tag_filter(self):
        status, body = _get("/capabilities?tags=research")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body.get("count", 0), 0)

    def test_manifest_reachable(self):
        status, body = _get("/manifest")
        self.assertEqual(status, 200)
        self.assertIn("api_endpoint", body)

    def test_revenue_summary_shape(self):
        status, body = _get("/revenue/summary")
        self.assertEqual(status, 200)
        for key in ("entry_count", "total_usd_booked", "settlement_status",
                    "top_providers", "top_capabilities"):
            self.assertIn(key, body)

    def test_leaderboard_shape(self):
        status, body = _get("/agents/leaderboard?limit=3")
        self.assertEqual(status, 200)
        self.assertIn("agents", body)
        self.assertIn("source", body)


if __name__ == "__main__":
    unittest.main()
