"""Persistence: the chain lives in a plain text file, one block per line.

Human-readable on purpose — `cat blocks.jsonl` and you can READ your
blockchain. Deliberately editable too: tamper with it, and watch verify()
catch you. (Real chains use fancier databases; the idea is identical.)
"""

import json
from dataclasses import asdict
from pathlib import Path

from .block import Block
from .chain import Chain


def save(chain: Chain, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for b in chain.blocks:
            f.write(json.dumps(asdict(b)) + "\n")


def append_block(block: Block, path: Path) -> None:
    """Normal operation: just add the newest line."""
    with open(path, "a") as f:
        f.write(json.dumps(asdict(block)) + "\n")


def load(path: Path) -> Chain | None:
    if not path.exists():
        return None
    blocks = [Block(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    return Chain(blocks) if blocks else None
