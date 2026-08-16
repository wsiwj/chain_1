"""The eyes and ears.

Two modes (set PERCEPTION env var):

  "fake"  — hardcoded test observation, no tools needed.
  "file"  — the REAL pipeline: picks up the newest image + audio file from
            the inbox/ folder, then:
              image  -> vision model (moondream)  -> scene description
              audio  -> whisper.cpp               -> transcript

This laptop (a Mac mini) has no camera or mic, so files land in inbox/
by hand (or via the `say` trick — see agent README). On the Pi, the ONLY
change is that the camera/mic drop files into inbox/ automatically —
everything downstream is identical.
"""

import base64
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import requests

from config import (
    PERCEPTION_MODE, INBOX_DIR, OLLAMA_URL, VISION_MODEL,
    WHISPER_BIN, WHISPER_MODEL,
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
AUDIO_EXTS = {".wav", ".aiff", ".m4a", ".mp3", ".flac"}


@dataclass
class Perception:
    """One observation: what was seen and heard at a moment in time."""
    detections: list[str] = field(default_factory=list)  # NPU labels (Pi only, later)
    scene: str = ""                                      # vision model's description
    transcript: str = ""                                 # whisper's transcription
    raw_evidence: bytes = b""                            # exact bytes that get hashed


# ---------- fake mode ----------

def _observe_fake() -> Perception:
    fake_photo = b"pretend-jpeg-bytes: person standing at front door, evening"
    return Perception(
        detections=["person"],
        scene="a person standing at the front door in the evening",
        transcript="hey, it's me, I forgot my keys",
        raw_evidence=fake_photo,
    )


# ---------- file mode (the real pipeline) ----------

def _newest(folder: Path, exts: set[str]) -> Path | None:
    files = [f for f in folder.iterdir() if f.suffix.lower() in exts] if folder.exists() else []
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


def _describe_image(image_path: Path) -> str:
    """Ask the vision model what's in the picture (stand-in for the Hailo NPU)."""
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": VISION_MODEL,
            "prompt": "Briefly describe what you see. One or two sentences.",
            "images": [b64],
            "stream": False,
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def _transcribe_audio(audio_path: Path) -> str:
    """whisper.cpp wants 16kHz mono WAV; convert with ffmpeg, then transcribe."""
    wav = audio_path.with_suffix(".16k.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_path),
         "-ar", "16000", "-ac", "1", str(wav)],
        check=True,
    )
    out = subprocess.run(
        [WHISPER_BIN, "-m", str(WHISPER_MODEL), "-f", str(wav),
         "-nt", "--no-prints"],  # -nt = no timestamps, just the words
        check=True, capture_output=True, text=True,
    )
    wav.unlink(missing_ok=True)
    return out.stdout.strip()


def _observe_file() -> Perception:
    image = _newest(INBOX_DIR, IMAGE_EXTS)
    audio = _newest(INBOX_DIR, AUDIO_EXTS)
    if image is None and audio is None:
        raise FileNotFoundError(
            f"inbox is empty — drop an image and/or audio file into {INBOX_DIR}"
        )

    scene = _describe_image(image) if image else ""
    transcript = _transcribe_audio(audio) if audio else ""

    # Evidence = the exact bytes of what was perceived, image then audio.
    # Hash of this blob goes on-chain; the blob itself is saved locally.
    evidence = (image.read_bytes() if image else b"") + \
               (audio.read_bytes() if audio else b"")

    return Perception(scene=scene, transcript=transcript, raw_evidence=evidence)


# ---------- entry point ----------

def observe() -> Perception:
    if PERCEPTION_MODE == "fake":
        return _observe_fake()
    return _observe_file()
