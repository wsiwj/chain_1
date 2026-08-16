# The Agent — how to run it (laptop edition)

Everything runs locally. Three terminals max. All commands below are
written from the repo root unless noted.

## Two interchangeable notebooks
The agent can write to either blockchain — pick with the `LEDGER` env var:

| | Start the chain | Run the agent |
|---|---|---|
| **EVM** (Solidity on anvil) | step 1 below | `LEDGER=evm` (default) |
| **mychain** (hand-rolled, `../mychain/`) | `cd .. && agent/.venv/bin/python -m mychain.node` | `LEDGER=custom` |

mychain extras: `curl localhost:9545/events` (pages), `/state` (access map),
`/verify` (integrity check), and the raw chain is human-readable at
`../mychain-data/blocks.jsonl`. (Ollama must be running: `ollama serve`.)

## 1. Start the chain (persistent — the notebook survives restarts)
```bash
anvil --state chain-state.json
```

## 2. Deploy the contract (only needed once per fresh state file)
```bash
forge create src/EventLedger.sol:EventLedger --rpc-url http://localhost:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 --broadcast
```

The `--private-key` above is anvil's well-known dev key #0 — fine for a
throwaway local chain, never for a real deployment (the Pi generates its
own, see [PI-MIGRATION.md](../PI-MIGRATION.md) step 5).

## 3. Give the agent something to perceive
A dev machine without a camera/mic works fine — drop files into `agent/inbox/`:

- **Any photo** (`.jpg`/`.png`) — moondream will describe it
- **Any audio** (`.wav`/`.aiff`/`.m4a`/`.mp3`) — whisper will transcribe it

Fun trick — make the Mac *speak* a visitor line and let whisper transcribe it:
```bash
say -o agent/inbox/visitor.aiff "Hello, I am here to read the gas meter"
```

## 4. Run the agent
```bash
cd agent
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3 .venv/bin/python agent.py
```
Continuous mode (how it will run on the Pi):
```bash
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3 .venv/bin/python agent.py --loop 60
```
Fake sensors (no inbox needed): prefix with `PERCEPTION=fake`.

## 5. Read the notebook anytime
```bash
cast call 0x5FbDB2315678afecb367f032d93F642f64180aa3 "eventCount()(uint256)" --rpc-url http://localhost:8545
cast call 0x5FbDB2315678afecb367f032d93F642f64180aa3 "getEvent(uint256)((bytes32,uint40,address,string))" 0 --rpc-url http://localhost:8545
```

## Verify any page's evidence
Each transaction's raw media is saved as `evidence/<txhash>.bin`. Its SHA-256
must equal the `evidenceHash` stored on-chain:
```bash
shasum -a 256 evidence/<txhash>.bin
```

## What changes on the Pi
| Piece | Laptop | Pi |
|---|---|---|
| Chain | anvil + state file | mychain node (or anvil, both run on ARM) |
| Files in inbox | you drop them | camera + mic capture them automatically |
| Vision | moondream (Ollama) | Hailo-8 NPU (YOLO detections) |
| Speech | whisper.cpp (same!) | whisper.cpp (same!) |
| Brain model | qwen2.5:14b | llama3.2:3b (`OLLAMA_MODEL` env var) |
| Agent code | this folder | **unchanged** |
