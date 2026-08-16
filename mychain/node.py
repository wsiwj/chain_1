"""The node: a tiny HTTP server that is your blockchain's front door.

This plays the role anvil/Geth played for the EVM chain. Pure Python
stdlib — no frameworks. Endpoints:

  GET  /chain      all blocks, raw
  GET  /state      derived state (owner, agents, access map)
  GET  /events     the notebook pages
  GET  /verify     full chain verification
  GET  /dashboard  live web dashboard (open in a browser)
  GET  /status     what the agent is doing right now (ephemeral)
  POST /status     agent reports its state ("thinking", "writing"...)
  POST /append     {"record": {...}, "signature": "0x..."} -> new block

Clients keep their private keys; only records + signatures travel over
the wire. The node checks everything before appending — exactly like a
real chain node validating a transaction.

Run:  .venv/bin/python -m mychain.node   (from the pi-chain folder)
"""

import json
import os
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .chain import Chain, InvalidBlock
from . import store

PORT = int(os.getenv("MYCHAIN_PORT", "9545"))
DATA = Path(os.getenv("MYCHAIN_DATA", Path(__file__).parent.parent / "mychain-data" / "blocks.jsonl"))

# The chain owner. Defaults to the same dev address the agent uses
# (anvil account #0), so the whole existing setup carries over.
OWNER = os.getenv("MYCHAIN_OWNER", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")

chain = store.load(DATA)
if chain is None:
    chain = Chain.genesis(OWNER)
    store.save(chain, DATA)
    print(f"[node] new chain created, owner {OWNER}")
else:
    ok, msg = chain.verify()
    if not ok:
        sys.exit(f"[node] REFUSING TO START — stored chain fails verification: {msg}")
    print(f"[node] loaded {len(chain.blocks)} blocks from disk — {msg}")


# Ephemeral "what is the agent doing right now" — for the dashboard's
# live light. Not part of the chain: it's UI state, gone on restart.
status = {"state": "idle", "detail": "", "ts": 0.0}

DASHBOARD = Path(__file__).parent / "dashboard.html"


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/chain":
            self._json(200, [asdict(b) for b in chain.blocks])
        elif self.path == "/state":
            self._json(200, chain.state())
        elif self.path == "/events":
            self._json(200, chain.events())
        elif self.path == "/verify":
            ok, msg = chain.verify()
            self._json(200, {"ok": ok, "message": msg})
        elif self.path == "/status":
            self._json(200, status)
        elif self.path in ("/", "/dashboard"):
            body = DASHBOARD.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json(404, {"error": "unknown path"})

    def do_POST(self):
        if self.path == "/status":
            try:
                import time
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length))
                status["state"] = str(payload.get("state", "idle"))[:32]
                status["detail"] = str(payload.get("detail", ""))[:200]
                status["ts"] = time.time()
                return self._json(200, status)
            except Exception as e:
                return self._json(400, {"error": f"bad request: {e}"})
        if self.path != "/append":
            return self._json(404, {"error": "unknown path"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            block = chain.append(payload["record"], payload["signature"])
            store.append_block(block, DATA)
            self._json(200, asdict(block))
        except InvalidBlock as e:
            self._json(403, {"error": str(e)})       # rule broken -> rejected
        except Exception as e:
            self._json(400, {"error": f"bad request: {e}"})

    def log_message(self, *args):  # quiet the default per-request noise
        pass


if __name__ == "__main__":
    # 127.0.0.1 = this machine only (safe default for development).
    # On the Pi, set MYCHAIN_BIND=0.0.0.0 so your phone/laptop on the same
    # WiFi can open http://<pi-address>:9545/dashboard
    bind = os.getenv("MYCHAIN_BIND", "127.0.0.1")
    print(f"[node] mychain listening on http://{bind}:{PORT}  (data: {DATA})")
    HTTPServer((bind, PORT), Handler).serve_forever()
