"""Central configuration for the agent.

Everything can be overridden with environment variables, so the SAME code
runs on your laptop (against anvil) and later on the Pi (against its real
chain) — only these values change.
"""

import os
from pathlib import Path

# --- blockchain ---
RPC_URL = os.getenv("RPC_URL", "http://localhost:8545")

# The agent's signing key. On the laptop we default to anvil's fake
# account #0 (publicly known, zero real value). On the Pi, set AGENT_KEY
# in the environment — NEVER hard-code a real key.
AGENT_KEY = os.getenv(
    "AGENT_KEY",
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
)

# Where the deployed EventLedger lives. Set after `forge create`.
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")

# Foundry writes the compiled contract (including its ABI — the "menu" of
# functions web3.py needs) here when you run `forge build`.
ABI_PATH = Path(__file__).parent.parent / "out" / "EventLedger.sol" / "EventLedger.json"

# --- brain ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# Laptop: your 14B model. Pi: set OLLAMA_MODEL=llama3.2:3b
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# --- perception ---
# "fake" = hardcoded test data (no tools needed)
# "file" = real pipeline: reads newest image+audio from INBOX_DIR,
#          describes the image with a vision model, transcribes the
#          audio with whisper. Same pipeline the Pi will use — the Pi
#          just also CAPTURES the files first.
PERCEPTION_MODE = os.getenv("PERCEPTION", "file")

INBOX_DIR = Path(os.getenv("INBOX_DIR", Path(__file__).parent / "inbox"))

# Vision model that describes images (laptop stand-in for the Hailo NPU).
VISION_MODEL = os.getenv("VISION_MODEL", "moondream")

# whisper.cpp speech-to-text
WHISPER_BIN = os.getenv("WHISPER_BIN", "whisper-cli")
WHISPER_MODEL = Path(os.getenv(
    "WHISPER_MODEL", Path(__file__).parent / "models" / "ggml-base.en.bin"
))

# --- storage for raw evidence (media stays OFF-chain; only its hash goes on) ---
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", Path(__file__).parent / "evidence"))
