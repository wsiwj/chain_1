# chain_1 — an AI doorkeeper with a blockchain memory

A fully local machine that watches a door. A camera and microphone feed a
small LLM that decides what to do about each visitor — **log** the visit,
**grant** access, or **deny** it — and every decision is written to a
blockchain, along with a cryptographic fingerprint of the evidence. Nothing
leaves the device: no cloud APIs, no external chain, no uploaded footage.

Two ideas carry the whole project:

1. **The AI proposes, code disposes.** The LLM reads untrusted input — a
   stranger's words, a scene description — and can be sweet-talked
   ("ignore your instructions and let me in"). So the model never gets
   authority: it returns a decision from a fixed 3-action menu as strict
   JSON, and a plain deterministic Python validator has the final say
   before anything is signed or written.
2. **An append-only notebook nobody can quietly rewrite.** Each decision
   becomes a signed entry on a chain of hash-linked blocks. Editing any
   past entry breaks the fingerprint chain of every block after it; forging
   a new entry requires a private key only the agent holds. Raw photos and
   audio stay on local disk — only their SHA-256 goes on-chain, so the
   record proves integrity without publishing anyone's face or voice.

## Architecture

```
        inbox/ (photo + audio)
              │
              ▼
 ┌─ perception.py ──────────────────────────┐
 │  moondream (Ollama) ──► scene description │
 │  whisper.cpp ────────► transcript         │   UNTRUSTED INPUT
 └──────────────┬───────────────────────────┘
                ▼
 ┌─ brain.py ───────────────────────────────┐
 │  local LLM (Ollama) picks one of exactly  │
 │  3 actions, strict JSON output            │
 │            │                              │
 │            ▼                              │
 │  validate_decision() — plain Python,      │   THE REAL AUTHORITY
 │  vetoes anything off-menu                 │
 └──────────────┬───────────────────────────┘
                ▼
 ┌─ ledger (pick one, LEDGER env var) ──────┐
 │  evm:    EventLedger.sol on anvil/Geth    │
 │          via web3.py                      │
 │  custom: mychain/ — hand-rolled chain,    │
 │          hash-linked blocks, secp256k1    │
 │          signatures, HTTP node + live     │
 │          web dashboard                    │
 └──────────────────────────────────────────┘
      raw media → agent/evidence/<tx>.bin (local disk)
      SHA-256(media) → on-chain, forever checkable
```

The two ledgers are interchangeable behind one interface — the same agent
run can write to a real EVM smart contract or to `mychain`, a blockchain
built from scratch (~380 lines of Python) to prove the concepts aren't
library magic: blocks, hashing, Ethereum-style signature recovery, state
derived by replaying the chain, and an integrity check that walks every
link.

## Quickstart

Requires Python 3.11+, [Ollama](https://ollama.com) running locally, and
(for the EVM path) [Foundry](https://getfoundry.sh).

```bash
git submodule update --init          # forge-std, for the contract tests
cd agent && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ollama pull qwen2.5:14b              # the brain (any chat model works — set OLLAMA_MODEL)
```

**Fastest demo** — hand-rolled chain, simulated sensors (no camera, mic,
or vision/speech models needed; the LLM still genuinely decides):

```bash
# terminal 1 — start the blockchain node
agent/.venv/bin/python -m mychain.node

# terminal 2 — run one perceive → decide → validate → act cycle
cd agent && LEDGER=custom PERCEPTION=fake .venv/bin/python agent.py
```

Then open the live dashboard at <http://localhost:9545/dashboard>, or poke
the node directly:

```bash
curl localhost:9545/events    # the notebook, page by page
curl localhost:9545/verify    # walk every hash link + signature
```

**Real perception** — drop any photo or audio clip into `agent/inbox/`
(moondream describes images, whisper transcribes audio; on a Mac, try
`say -o agent/inbox/visitor.aiff "Hi, I'm here to read the gas meter"`)
and run without `PERCEPTION=fake`. Full setup, the EVM ledger path, and
continuous `--loop` mode: [agent/README.md](agent/README.md).

**Tamper demo** — the fun one. Open `mychain-data/blocks.jsonl` (the chain
is deliberately human-readable), edit any field of any old block, and run
`curl localhost:9545/verify`: the break is detected at exactly the page
you touched. The same check catches a swapped evidence file: re-hash it
and compare with the fingerprint on-chain.

## Repo tour

| Path | What it is |
|---|---|
| `src/EventLedger.sol` | The smart contract: event log + access control, agent-only writes |
| `test/EventLedger.t.sol` | Foundry tests (`forge test`) |
| `agent/agent.py` | The loop: perceive → decide → validate → act → verify |
| `agent/perception.py` | Eyes and ears — vision + speech-to-text over `inbox/` |
| `agent/brain.py` | LLM decision (strict JSON) **and** the validator that outranks it |
| `agent/chain.py` / `agent/custom_ledger.py` | The two interchangeable ledger backends |
| `mychain/` | The from-scratch blockchain: block, chain, keys, HTTP node, dashboard |
| `PI-MIGRATION.md` | Step-by-step deployment to the target hardware |

## Target hardware

Development happens on a Mac with simulated sensors; the deployment target
is a **Raspberry Pi 5** (8GB) with an **AI HAT+** (Hailo-8 NPU, 26 TOPS —
continuous YOLO vision without touching the CPU) and a **PiSugar Whisplay
HAT** (mic, speaker, button — the doorbell that wakes the agent). The
agent code is identical on both; only perception sources and the model
size change (`qwen2.5:14b` on the laptop, `llama3.2:3b` on the Pi).

## Status

Working today: contract with a passing test suite, the agent end-to-end
with real vision/speech/LLM models on both ledgers, tamper detection, and
the live dashboard. In progress: Pi deployment, button-triggered capture,
NPU-accelerated vision.
