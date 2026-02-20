"""
Download VibeVoice voice presets from the GitHub repository.

Runs at container startup before the server. Downloads .pt voice preset
files into VOICES_DIR if they are not already cached (volume-mounted).
"""

import os
from pathlib import Path

import requests

VOICES_DIR = Path(os.environ.get("VOICES_DIR", "/app/voices/streaming_model"))

GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/microsoft/VibeVoice/main/demo/voices/streaming_model"
)

VOICE_FILES = [
    "en-Emma_woman.pt",
    "en-Carter_man.pt",
    "en-Davis_man.pt",
    "en-Frank_man.pt",
    "en-Grace_woman.pt",
    "en-Mike_man.pt",
    "in-Samuel_man.pt",
    "de-Spk0_man.pt",
    "de-Spk1_woman.pt",
    "es-Spk0_woman.pt",
    "es-Spk1_man.pt",
    "fr-Spk0_man.pt",
    "fr-Spk1_woman.pt",
    "it-Spk0_woman.pt",
    "it-Spk1_man.pt",
    "ja-Spk0_man.pt",
    "ja-Spk1_woman.pt",
    "ko-Spk0_woman.pt",
    "ko-Spk1_man.pt",
    "nl-Spk0_man.pt",
    "nl-Spk1_woman.pt",
    "pl-Spk0_man.pt",
    "pl-Spk1_woman.pt",
    "pt-Spk0_woman.pt",
    "pt-Spk1_man.pt",
]


def download_voices():
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    existing = set(p.name for p in VOICES_DIR.glob("*.pt"))
    if existing:
        print(f"[voices] Found {len(existing)} cached voice presets, checking for missing...")

    to_download = [f for f in VOICE_FILES if f not in existing]

    if not to_download:
        print("[voices] All voice presets already cached.")
        return

    print(f"[voices] Downloading {len(to_download)} voice presets...")
    for filename in to_download:
        url = f"{GITHUB_RAW_BASE}/{filename}"
        dest = VOICES_DIR / filename
        print(f"  Downloading {filename}...")
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            print(f"  Saved {filename} ({len(resp.content) / 1024:.0f} KB)")
        except Exception as e:
            print(f"  WARNING: Failed to download {filename}: {e}")

    final_count = len(list(VOICES_DIR.glob("*.pt")))
    print(f"[voices] {final_count} voice presets ready in {VOICES_DIR}")


if __name__ == "__main__":
    download_voices()
