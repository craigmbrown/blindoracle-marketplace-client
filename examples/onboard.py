#!/usr/bin/env python3
"""Submit a lead to the BlindOracle marketplace via POST /a2a/onboard."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ONBOARD_URL = "https://api.craigmbrown.com/a2a/onboard"

payload = {
    "customerId": "sdk-readme-example-001",
    "fullName": "Demo External Agent",
    "email": "demo@example.com",
    "company": "Acme AI",
    "services": "blindoracle-marketplace-client-v0.2.0",
}
data = json.dumps(payload).encode()

req = Request(ONBOARD_URL, data=data,
              headers={"Content-Type": "application/json",
                       "User-Agent": "bo-sdk-onboard/1.0"},
              method="POST")
try:
    with urlopen(req, timeout=10) as r:
        print("HTTP", r.getcode())
        print(r.read().decode())
except HTTPError as e:
    print("HTTP", e.code, e.read().decode())
