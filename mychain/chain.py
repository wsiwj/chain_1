"""The chain: validation rules + state.

This file replaces the ENTIRE Solidity contract. The rules that were
EventLedger.sol are now plain Python:

  - "genesis"       block 0; names the owner (like the contract constructor)
  - "log_event"     signer must be an agent          (was: logEvent)
  - "decide_access" signer must be an agent          (was: decideAccess)
  - "set_agent"     signer must be the owner         (was: setAgent)

A key blockchain idea lives here: STATE IS DERIVED, NOT STORED.
We never keep a "current access list" as the source of truth — we REPLAY
the whole history from block 0 and recompute it. The history is the truth;
the state is just its summary. (Ethereum works exactly the same way.)
"""

import time

from .block import Block, record_hash
from .keys import recover_signer


class InvalidBlock(Exception):
    """Raised when a record breaks the rules — the chain refuses it."""


class Chain:
    def __init__(self, blocks: list[Block] | None = None):
        self.blocks: list[Block] = blocks or []

    # ---------- creating ----------

    @classmethod
    def genesis(cls, owner_address: str) -> "Chain":
        """Start a brand-new chain. Block 0 declares who the owner is."""
        chain = cls()
        block = Block(
            index=0,
            timestamp=time.time(),
            prev_hash="0" * 64,          # nothing comes before genesis
            record={"type": "genesis", "owner": owner_address},
            signature="",                 # genesis is self-evident, unsigned
        ).seal()
        chain.blocks.append(block)
        return chain

    def append(self, record: dict, signature: str) -> Block:
        """The gatekeeper. Every new record passes through here."""
        # 1. WHO signed this? (recovered from the signature itself)
        signer = recover_signer(signature, record_hash(record))

        # 2. Is that identity ALLOWED to do this? (replay-derived state)
        self._authorize(record, signer)

        # 3. All good — link it to the tip of the chain and seal it.
        prev = self.blocks[-1]
        block = Block(
            index=prev.index + 1,
            timestamp=time.time(),
            prev_hash=prev.hash,          # <-- the link that makes it a chain
            record=record,
            signature=signature,
        ).seal()
        self.blocks.append(block)
        return block

    def _authorize(self, record: dict, signer: str) -> None:
        state = self.state()
        kind = record.get("type")
        if kind in ("log_event", "decide_access"):
            if signer not in state["agents"]:
                raise InvalidBlock(f"NotAgent: {signer}")
        elif kind == "set_agent":
            if signer != state["owner"]:
                raise InvalidBlock(f"NotOwner: {signer}")
        else:
            raise InvalidBlock(f"unknown record type: {kind!r}")

    # ---------- state = replaying history ----------

    def state(self) -> dict:
        """Recompute current state by replaying every block from genesis."""
        owner, agents, access = None, set(), {}
        for b in self.blocks:
            r = b.record
            if r["type"] == "genesis":
                owner = r["owner"]
                agents.add(r["owner"])    # owner starts as the first agent
            elif r["type"] == "set_agent":
                (agents.add if r["enabled"] else agents.discard)(r["agent"])
            elif r["type"] == "decide_access":
                access[r["subject"]] = r["allowed"]
        return {"owner": owner, "agents": sorted(agents), "access": access}

    def events(self) -> list[dict]:
        """All notebook pages (log_event + decide_access records)."""
        return [
            {"index": b.index, "timestamp": b.timestamp, **b.record}
            for b in self.blocks
            if b.record["type"] in ("log_event", "decide_access")
        ]

    # ---------- verifying (the whole point) ----------

    def verify(self) -> tuple[bool, str]:
        """Re-check EVERYTHING from block 0: intactness, links, signatures,
        and authorization. Any single edited byte anywhere fails this."""
        replay = Chain()
        for i, b in enumerate(self.blocks):
            if not b.is_intact():
                return False, f"block {i}: contents were EDITED (hash mismatch)"
            if i == 0:
                if b.record.get("type") != "genesis":
                    return False, "block 0 is not a genesis block"
                replay.blocks.append(b)
                continue
            if b.prev_hash != self.blocks[i - 1].hash:
                return False, f"block {i}: broken link to block {i - 1}"
            try:
                signer = recover_signer(b.signature, record_hash(b.record))
                replay._authorize(b.record, signer)
            except InvalidBlock as e:
                return False, f"block {i}: unauthorized ({e})"
            except Exception:
                return False, f"block {i}: bad signature"
            replay.blocks.append(b)
        return True, f"all {len(self.blocks)} blocks check out"
