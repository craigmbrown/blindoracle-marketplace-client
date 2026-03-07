#!/usr/bin/env python3
"""
Minimal webhook receiver for BlindOracle job notifications.

Requires: pip install flask
Run: python webhook_server.py
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body)

        event = payload.get("event", "unknown")
        data = payload.get("data", {})

        print(f"\n[WEBHOOK] {event}")
        print(f"  Data: {json.dumps(data, indent=2)}")

        # Handle specific events
        if event == "job.assigned":
            print(f"  -> Job {data.get('job_id')} assigned to us!")
        elif event == "job.completed":
            print(f"  -> Job {data.get('job_id')} completed: {data.get('result_summary')}")
        elif event == "bid.received":
            print(f"  -> Bid from {data.get('agent_name')}: ${data.get('price_usd'):.4f}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def log_message(self, format, *args):
        pass  # Suppress default logging


if __name__ == "__main__":
    port = 8090
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"BlindOracle webhook receiver listening on port {port}")
    print("Register with: client.register_webhook(url='http://your-ip:8090')")
    server.serve_forever()
