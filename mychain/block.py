"""The block — the single idea every blockchain is built on.

A block is just a small package of data that contains THE HASH OF THE
PREVIOUS BLOCK. That one field is the whole trick:

    block 0        block 1              block 2
    hash=aaaa  <-  prev_hash=aaaa   <-  prev_hash=bbbb
                   hash=bbbb            hash=cccc

If anyone edits block 0, its hash is no longer "aaaa" — so block 1's
prev_hash doesn't match anymore, which changes what block 1 *is*, which
breaks block 2, and so on. Tampering with history breaks every link after
it, and anyone can detect that in milliseconds. That's "tamper-evident".
"""

import hashlib
import json
from dataclasses import dataclass, asdict


def canonical(obj) -> bytes:
    """Turn data into bytes THE SAME WAY every time.

    Hashing is byte-exact, so {"a":1,"b":2} and {"b":2,"a":1} must not
    produce different bytes. Sorting keys + fixed separators guarantees
    everyone computes identical hashes for identical data.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_hash(record: dict) -> bytes:
    """The 32-byte fingerprint of a record — this is what gets SIGNED."""
    return hashlib.sha256(canonical(record)).digest()


@dataclass
class Block:
    index: int        # position in the chain (0 = genesis)
    timestamp: float  # when it was added
    prev_hash: str    # hash of the previous block  <-- THE magic field
    record: dict      # the actual content (an event, an access decision...)
    signature: str    # who vouches for the record (hex, empty for genesis)
    hash: str = ""    # this block's own fingerprint, filled in by seal()

    def compute_hash(self) -> str:
        """Fingerprint of everything in the block (except the hash field
        itself — a thing can't contain its own fingerprint)."""
        content = asdict(self)
        content.pop("hash")
        return sha256_hex(canonical(content))

    def seal(self) -> "Block":
        self.hash = self.compute_hash()
        return self

    def is_intact(self) -> bool:
        """Recompute the fingerprint — if it differs, the block was edited."""
        return self.hash == self.compute_hash()
