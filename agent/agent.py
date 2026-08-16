"""The messenger: glues eyes/ears -> brain -> notebook together.

One cycle =  perceive -> decide -> validate -> act -> verify.

Run it:            python agent.py          (one cycle)
On the Pi later:   same file — only perception.py and config env vars change.
"""

import sys
import time

import os

from config import EVIDENCE_DIR
from perception import observe
from brain import decide, validate_decision

# Which notebook? LEDGER=evm (Solidity contract on anvil/Geth)
#                 LEDGER=custom (your own hand-rolled mychain)
# The rest of the agent is identical either way.
if os.getenv("LEDGER", "evm") == "custom":
    from custom_ledger import CustomLedger as Ledger
else:
    from chain import Ledger

# On a private chain, the "subject" whose access we flip. For now: a fixed
# demo address representing "the front door". Later this could be per-person.
FRONT_DOOR = "0x00000000000000000000000000000000000D0001"

NODE_URL = os.getenv("MYCHAIN_URL", "http://localhost:9545")


def report(state: str, detail: str = "") -> None:
    """Tell the dashboard what we're doing. Purely cosmetic — never let a
    dashboard hiccup break the actual work, hence the bare except."""
    try:
        import requests
        requests.post(f"{NODE_URL}/status",
                      json={"state": state, "detail": detail}, timeout=2)
    except Exception:
        pass


def save_evidence(evidence: bytes, tx_hash: str) -> None:
    """Keep the raw media locally, named by its transaction — so that any
    notebook page can be traced back to the exact bytes it fingerprints."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / f"{tx_hash}.bin").write_bytes(evidence)


def run_cycle(ledger: Ledger) -> None:
    # 1. PERCEIVE — what's out there?
    report("listening", "capturing and transcribing...")
    p = observe()
    if p.detections:
        print(f"[eyes ] detections: {p.detections}")
    print(f"[eyes ] scene: {p.scene or '(no image)'}")
    print(f"[ears ] transcript: \"{p.transcript or '(silence)'}\"")

    # 2. DECIDE — ask the local LLM (may take a while on small hardware)
    print("[brain] thinking...")
    report("thinking", f'heard: "{p.transcript[:80]}"' if p.transcript else "analyzing the scene...")
    t0 = time.time()
    raw_decision = decide(p)
    print(f"[brain] answered in {time.time() - t0:.1f}s: {raw_decision}")

    # 3. VALIDATE — plain code has the final say, not the LLM
    try:
        action, label = validate_decision(raw_decision)
    except ValueError as e:
        print(f"[gate ] REJECTED brain output: {e}")
        return

    # 4. ACT — write the page / flip the switch
    report("writing", f"{action}: {label}")
    if action == "log_event":
        tx = ledger.log_event(p.raw_evidence, label)
        final = ("logged", label)
    elif action == "grant_access":
        tx = ledger.decide_access(FRONT_DOOR, True, p.raw_evidence, label)
        final = ("allowed", label)
    else:  # deny_access
        tx = ledger.decide_access(FRONT_DOOR, False, p.raw_evidence, label)
        final = ("denied", label)
    report(*final)

    save_evidence(p.raw_evidence, tx)
    print(f"[chain] {action} written, tx {tx}")

    # 5. VERIFY — read the notebook back
    n = ledger.event_count()
    rec = ledger.get_event(n - 1)
    print(f"[chain] notebook now has {n} page(s); latest: "
          f"hash=0x{rec[0].hex()[:16]}... label=\"{rec[3]}\"")
    if action != "log_event":
        print(f"[chain] front door allowed: {ledger.is_allowed(FRONT_DOOR)}")


if __name__ == "__main__":
    try:
        ledger = Ledger()
    except (ConnectionError, ValueError) as e:
        sys.exit(f"setup problem: {e}")
    print(f"[agent] signing as {ledger.account.address}")

    # `python agent.py`           -> one cycle
    # `python agent.py --loop 30` -> a cycle every 30s, forever (Ctrl+C stops).
    #                                This is how it will run on the Pi.
    if len(sys.argv) >= 2 and sys.argv[1] == "--loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        print(f"[agent] looping every {interval}s — Ctrl+C to stop")
        while True:
            try:
                run_cycle(ledger)
            except FileNotFoundError as e:
                print(f"[agent] nothing to observe: {e}")
            except Exception as e:
                print(f"[agent] cycle failed, will retry: {e}")
            time.sleep(interval)
    else:
        run_cycle(ledger)
