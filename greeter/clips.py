"""Pre-recorded lines in the robot's voice: instant fallbacks when a model is slow or offline.

Rendered once with OpenAI text-to-speech (``python -m greeter.clips --render``;
``install.sh`` does it when a key is present) into ``models/clips/*.wav``
(16 kHz mono). Missing clips are simply skipped: the robot then speaks live.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
import wave
from pathlib import Path
from typing import Dict

log = logging.getLogger(__name__)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "models" / "clips"

LINES: Dict[str, str] = {
    "hey_green": "Hey, you in the green! Come and say hi!",
    "hey_there": "Hey there! Come and say hi!",
    "hello": "Hello! Lovely to meet you.",
    "step_closer": "Come and stand on the green spot in front of me.",
    "say_again": "Sorry, it's a bit noisy in here. Could you say that again?",
    "one_moment": "Ooh, good question, give me a second.",
    "cant_move": "I can't move my arms today, but I'm very happy to chat.",
    "brain_offline": "Oops, my cloud brain has dropped out. Please ask one of the team!",
    "ask_team": "The researchers on the stand can tell you much more about that.",
    "busy": "Lots of people here! Step onto the green spot if you'd like a chat.",
    "what_am_i": "I'm a Unitree G1 humanoid robot, here to chat about robotics research.",
    "recorded": "Our chats are recorded on the robot to help the team improve me.",
    "battery": "My battery needs a swap in two minutes. Back soon!",
    "thanks": "Thank you!",
    "goodbye": "Thanks for stopping by, and enjoy the open day!",
    "welcome_back": "Welcome back!",
}


def load(directory: Path = DEFAULT_DIR) -> Dict[str, bytes]:
    """name -> 16 kHz mono s16le PCM, for every clip that exists."""
    clips = {}
    for name in LINES:
        path = Path(directory) / (name + ".wav")
        if not path.is_file():
            continue
        with wave.open(str(path), "rb") as w:
            if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
                log.warning("skipping %s: not 16 kHz mono 16-bit", path)
                continue
            clips[name] = w.readframes(w.getnframes())
    return clips


def render(directory: Path, api_key: str, voice: str = "marin", model: str = "gpt-4o-mini-tts", force: bool = False) -> int:
    """Render every line with OpenAI TTS (24 kHz PCM) and save 16 kHz WAVs. Returns how many were made."""
    from greeter.audio import StreamResampler

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    made = 0
    for name, text in LINES.items():
        path = directory / (name + ".wav")
        if path.exists() and not force:
            continue
        body = json.dumps({
            "model": model, "voice": voice, "input": text, "response_format": "pcm",
            "instructions": "Warm, quick, friendly British robot greeter at a busy university open day.",
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=body,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            pcm24 = resp.read()
        pcm16 = StreamResampler(24000, 16000).process(pcm24)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm16)
        made += 1
    return made


def main(argv=None) -> None:
    from greeter.envfile import load_env_file

    load_env_file()
    p = argparse.ArgumentParser(prog="python -m greeter.clips")
    p.add_argument("--render", action="store_true", help="render missing clips with OpenAI TTS")
    p.add_argument("--force", action="store_true", help="re-render all clips")
    p.add_argument("--dir", default=str(DEFAULT_DIR))
    p.add_argument("--voice", default=os.environ.get("GREETER_OPENAI_VOICE", "marin"))
    args = p.parse_args(argv)
    if args.render:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            sys.exit("OPENAI_API_KEY is not set")
        made = render(Path(args.dir), key, voice=args.voice, force=args.force)
        print("rendered %d clips into %s" % (made, args.dir))
    have = load(Path(args.dir))
    print("%d/%d clips present" % (len(have), len(LINES)))


if __name__ == "__main__":
    main()
