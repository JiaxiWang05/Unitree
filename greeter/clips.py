"""Pre-recorded lines in the robot's voice: instant fallbacks when a model is slow or offline.

Rendered once with OpenAI text-to-speech (``python -m greeter.clips --render``;
``install.sh`` does it when a key is present) into ``models/clips/*.wav``
(16 kHz mono). Missing clips are simply skipped: the robot then speaks live.

Without a key, ``--render-offline`` makes stand-ins with the machine's own speech program
(``espeak-ng`` on the Jetson, ``say`` on a Mac), so ``--scripted`` and the speaker test can
talk. They are marked, and the next ``--render`` with a key replaces them.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path
from typing import Dict

log = logging.getLogger(__name__)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "models" / "clips"
OFFLINE_MARK = "OFFLINE"  # file in the clips folder: these were made without OpenAI

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
    stand_ins = (directory / OFFLINE_MARK).exists()  # replace the offline stand-ins
    made = 0
    for name, text in LINES.items():
        path = directory / (name + ".wav")
        if path.exists() and not (force or stand_ins):
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
    if stand_ins:
        (directory / OFFLINE_MARK).unlink()
    return made


def offline_command(text: str, out: Path):
    """The command that speaks ``text`` into the WAV file ``out``, or None if this machine has none."""
    if shutil.which("espeak-ng"):
        return ["espeak-ng", "-v", "en-gb", "-s", "155", "-w", str(out), text]
    if sys.platform == "darwin" and shutil.which("say"):
        return ["say", "-o", str(out), "--data-format=LEI16@16000", text]
    return None


def to_clip(src: Path, dest: Path) -> None:
    """Any 16-bit PCM WAV -> the clip format (16 kHz mono)."""
    import numpy as np

    from greeter.audio import StreamResampler

    with wave.open(str(src), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("%s is not 16-bit PCM" % src)
        rate, channels = w.getframerate(), w.getnchannels()
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    if channels > 1:
        samples = samples[: len(samples) // channels * channels].reshape(-1, channels).mean(axis=1).astype("<i2")
    pcm = samples.tobytes()
    if rate != 16000:
        pcm = StreamResampler(rate, 16000).process(pcm)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)


def render_offline(directory: Path, force: bool = False) -> int:
    """Make the missing clips with the machine's own speech program. Returns how many were made;
    raises RuntimeError if there is no such program."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    made = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in LINES.items():
            path = directory / (name + ".wav")
            if path.exists() and not force:
                continue
            raw = Path(tmp) / (name + ".wav")
            cmd = offline_command(text, raw)
            if cmd is None:
                raise RuntimeError("no offline speech program found (espeak-ng, or say on a Mac)")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            to_clip(raw, path)
            made += 1
    if made:
        (directory / OFFLINE_MARK).write_text("made without OpenAI; `python -m greeter.clips --render` with a key replaces them\n")
    return made


def main(argv=None) -> None:
    from greeter.envfile import load_env_file

    load_env_file()
    p = argparse.ArgumentParser(prog="python -m greeter.clips")
    p.add_argument("--render", action="store_true", help="render missing clips with OpenAI TTS")
    p.add_argument("--render-offline", action="store_true", help="render missing clips without a key (espeak-ng, or say on a Mac)")
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
    if args.render_offline:
        try:
            made = render_offline(Path(args.dir), force=args.force)
        except (RuntimeError, OSError, subprocess.CalledProcessError, ValueError) as exc:
            sys.exit("offline clips not rendered: %s" % exc)
        print("rendered %d offline clips into %s" % (made, args.dir))
    have = load(Path(args.dir))
    print("%d/%d clips present" % (len(have), len(LINES)))


if __name__ == "__main__":
    main()
