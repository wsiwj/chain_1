"""The hand that writes in YOUR hand-rolled blockchain (mychain).

Same five methods as chain.py's EVM Ledger — the agent can't tell the
difference. It signs each record with the SAME private key it uses on
the EVM chain (same cryptography!), so the agent has the same identity
on both: 0xf39F...
"""

import hashlib
import sys
from pathlib import Path

import requests

# import mychain's helpers from the sibling folder
sys.path.insert(0, str(Path(__file__).parent.parent))
from mychain.block import record_hash          # noqa: E402
from mychain.keys import sign, address_of      # noqa: E402

from config import AGENT_KEY                   # noqa: E402
import os

NODE_URL = os.getenv("MYCHAIN_URL", "http://localhost:9545")


class _Account:
    def __init__(self, address): self.address = address


class CustomLedger:
    def __init__(self):
        try:
            requests.get(f"{NODE_URL}/state", timeout=5).raise_for_status()
        except Exception:
            raise ConnectionError(f"No mychain node at {NODE_URL} — start it with: "
                                  f".venv/bin/python -m mychain.node")
        self.account = _Account(address_of(AGENT_KEY))

    def _append(self, record: dict) -> str:
        """Sign the record, send it, return the new block's hash."""
        signature = sign(AGENT_KEY, record_hash(record))
        resp = requests.post(f"{NODE_URL}/append",
                             json={"record": record, "signature": signature},
                             timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"node rejected record: {resp.json().get('error')}")
        return resp.json()["hash"]

    # --- the same three writes the EVM version has ---

    def log_event(self, evidence: bytes, label: str) -> str:
        return self._append({
            "type": "log_event",
            "evidence_hash": hashlib.sha256(evidence).hexdigest(),
            "label": label,
        })

    def decide_access(self, subject: str, allowed: bool, evidence: bytes, label: str) -> str:
        return self._append({
            "type": "decide_access",
            "subject": subject,
            "allowed": allowed,
            "evidence_hash": hashlib.sha256(evidence).hexdigest(),
            "label": label,
        })

    # --- and the same reads ---

    def event_count(self) -> int:
        return len(requests.get(f"{NODE_URL}/events", timeout=10).json())

    def get_event(self, event_id: int):
        e = requests.get(f"{NODE_URL}/events", timeout=10).json()[event_id]
        # same shape the EVM version returns: (hash, timestamp, reporter, label)
        return (bytes.fromhex(e["evidence_hash"]), int(e["timestamp"]), "", e["label"])

    def is_allowed(self, subject: str) -> bool:
        state = requests.get(f"{NODE_URL}/state", timeout=10).json()
        return bool(state["access"].get(subject, False))
