# Migrating to the Raspberry Pi 5

Goal: everything that runs on the laptop, running on the Pi — plus real
camera/mic capture. Work through the steps in order; each has a check
before moving on.

Assumes: Raspberry Pi OS **64-bit** (Bookworm), you can SSH in
(`ssh pi@raspberrypi.local` — adjust user/host to yours).

---

## Step 1 — Base setup on the Pi

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-pip ffmpeg cmake build-essential curl
```

Cooling check (do this under load later too — must stay `0x0`):
```bash
vcgencmd get_throttled
```

## Step 2 — Clone the project from GitHub

The repo is **private** (https://github.com/wsiwj/chain_1), so the Pi
has to prove it's you before GitHub will hand it over. Easiest way is the
GitHub CLI — on the **Pi**:
```bash
sudo apt install -y gh
gh auth login
```
Pick "GitHub.com" → "HTTPS" → "Login with a web browser", then open the
shown URL on any device and enter the one-time code. (This also sets up
git credentials, so plain `git pull` works from then on.)

Now clone, into `~/pi-chain` so the rest of this guide's paths match:
```bash
cd ~ && gh repo clone wsiwj/chain_1 pi-chain
cd ~/pi-chain && git submodule update --init   # pulls lib/forge-std for the contract tests
```

Two things git deliberately doesn't carry (they're in `.gitignore`), so
recreate them on the **Pi**:
```bash
# 1. The whisper speech-to-text model (~142MB)
cd ~/pi-chain/agent
mkdir -p models && curl -L -o models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

# 2. The Python environment (never copy a venv between machines —
#    it contains binaries built for the source machine's CPU/OS)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Step 3 — Ollama + the 3B brain

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b     # the Pi-sized brain (~2GB)
ollama pull moondream       # vision stand-in until the Hailo NPU takes over
```
Check: `curl localhost:11434/api/version` answers. (The installer sets
Ollama up as a service — it starts at boot automatically.)

## Step 4 — whisper.cpp (the ears)

```bash
cd ~ && git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp && cmake -B build && cmake --build build -j4 --config Release
sudo cp build/bin/whisper-cli /usr/local/bin/
```
Check: `whisper-cli -m ~/pi-chain/agent/models/ggml-base.en.bin -f samples/jfk.wav -nt`
prints a transcript. (Tip: if base.en is slow, `tiny.en` is ~3x faster.)

## Step 5 — NEW IDENTITY (important — do not skip)

The laptop used anvil's dev key, which is **publicly known**. The Pi gets
a real secret key:

```bash
cd ~/pi-chain/agent
.venv/bin/python -c "
from eth_account import Account
a = Account.create()
print('address:', a.address)
print('key:', a.key.hex())"
```

Store it where only you can read it:
```bash
mkdir -p ~/.config/agent && chmod 700 ~/.config/agent
nano ~/.config/agent/env        # paste the lines below, with YOUR values
chmod 600 ~/.config/agent/env
```

Contents of `~/.config/agent/env`:
```bash
export AGENT_KEY=0x<the new private key>
export MYCHAIN_OWNER=<the new address>
export LEDGER=custom
export OLLAMA_MODEL=llama3.2:3b
```
Load it in any shell with: `source ~/.config/agent/env`

The Pi's chain starts fresh: its genesis names YOUR new address as owner.
(If you ever want the laptop history carried over, copy
`mychain-data/blocks.jsonl` too — but a clean start on the Pi is simpler.)

## Step 6 — First full run on the Pi (fake sensors)

Terminal A:
```bash
cd ~/pi-chain && source ~/.config/agent/env && agent/.venv/bin/python -m mychain.node
```
Terminal B:
```bash
cd ~/pi-chain/agent && source ~/.config/agent/env && PERCEPTION=fake .venv/bin/python agent.py
```
Success = a block written, `curl localhost:9545/events` shows it.
Note the brain's answer time — that's your Pi's thinking speed.

## Step 7 — Real ears and eyes filling the inbox

The agent already reads from `inbox/` — the Pi just has to keep that
folder fresh. Create `~/pi-chain/capture.sh`:

```bash
#!/bin/bash
# one observation: photo + 5s of audio into the agent's inbox
rpicam-still --width 1280 --height 720 -t 500 -o ~/pi-chain/agent/inbox/frame.jpg
arecord -f S16_LE -r 16000 -c 1 -d 5 ~/pi-chain/agent/inbox/audio.wav
```
`chmod +x capture.sh`, then check each half:
- `rpicam-still` photo looks right (Camera Module 3 connected, enabled)
- `arecord -l` lists your USB mic; add `-D plughw:X,0` if it's not the default

Simplest full loop while testing (Terminal C):
```bash
while true; do ~/pi-chain/capture.sh; sleep 55; done
```
with the agent in `--loop 60` mode in Terminal B. Camera+mic feed the
inbox, the agent perceives/decides/writes — the machine is alive.

## Step 7b — Whisplay HAT (the face: mic, speaker, screen, button)

The PiSugar Whisplay HAT replaces the USB mic AND adds a speaker, a
1.69" status screen, RGB LEDs, and a button.

**Mounting with the AI HAT+:** the AI HAT+ talks to the Pi over PCIe and
doesn't use the GPIO functions, so the two don't conflict electrically.
Physically, either stack the Whisplay above the AI HAT+ on a tall
stacking header, or (nicer) put the Whisplay on a 40-pin GPIO ribbon
extension so the screen/mic/button can face the door while the Pi sits
elsewhere. Keep the Hailo's airflow clear.

**Driver:**
```bash
git clone https://github.com/PiSugar/Whisplay.git --depth 1
cd Whisplay && sudo bash install_driver.sh && sudo reboot
```
This enables I2C + I2S (audio codec) and SPI (LCD). Afterwards the codec
shows up as an ALSA sound card — check with `arecord -l`.

**Wiring into the agent (no agent code changes):**
- *Ears:* in `capture.sh`, record from the Whisplay card instead of USB:
  `arecord -D plughw:<card#>,0 -f S16_LE -r 16000 -c 1 -d 5 ...inbox/audio.wav`
- *Voice:* after a decision, `aplay` a canned clip or pipe the label
  through Piper TTS (small, runs fine on Pi 5).
- *Button:* the doorbell. Instead of a timed loop, a small script waits
  for the button (GPIO17 / pin 11), then runs capture.sh + one agent
  cycle. Event-driven — the LLM only wakes when someone presses.
- *Screen + LED:* PiSugar's Python examples drive the ST7789 LCD; show
  the verdict + page count, LED green/red/blue for allowed/denied/thinking.

## Step 8 — The Hailo NPU (the real eyes)

```bash
sudo apt install -y hailo-all && sudo reboot
```
Demo to confirm the HAT works (live YOLO object detection):
```bash
rpicam-hello -t 10s --post-process-file /usr/share/rpi-camera-assets/hailo_yolov8_inference.json
```
Wiring the detections into `perception.py` (filling the `detections`
field instead of / alongside moondream's description) is the last coding
task — do it once everything else runs. Until then moondream carries
vision.

## Step 9 — Make it survive reboots (systemd)

`sudo nano /etc/systemd/system/mychain.service`:
```ini
[Unit]
Description=mychain blockchain node
After=network.target

[Service]
User=pi
EnvironmentFile=/home/pi/.config/agent/env
WorkingDirectory=/home/pi/pi-chain
ExecStart=/home/pi/pi-chain/agent/.venv/bin/python -m mychain.node
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`sudo nano /etc/systemd/system/agent.service`:
```ini
[Unit]
Description=AI doorkeeper agent
After=mychain.service ollama.service

[Service]
User=pi
EnvironmentFile=/home/pi/.config/agent/env
WorkingDirectory=/home/pi/pi-chain/agent
ExecStart=/home/pi/pi-chain/agent/.venv/bin/python agent.py --loop 60
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mychain agent
journalctl -u agent -f     # watch it live
```

## Optional — the EVM chain on the Pi too

Foundry runs on ARM64 Linux: `curl -L https://foundry.paradigm.xyz | bash && foundryup`,
then the same `anvil --state` + `forge create` flow as the laptop, with
`LEDGER=evm`. Only worth it if you want to keep the Solidity path around.

---

## Order of battle (summary)

1. apt packages → 2. clone repo + model + venv → 3. Ollama + models →
4. build whisper.cpp → 5. **new key** → 6. fake-sensor run →
7. capture.sh real sensors → 8. Hailo NPU → 9. systemd services

RAM watch throughout: `free -h`. If tight: `tiny.en` whisper model, and
keep only one Ollama model warm (`OLLAMA_KEEP_ALIVE=2m` helps).
