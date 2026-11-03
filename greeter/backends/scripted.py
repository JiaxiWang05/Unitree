"""Backends that need no model.

* :class:`ScriptedBackend`: canned lines + a chime, for plumbing tests (``--scripted``).
* :class:`CannedBackend`: the last rung of the provider chain when every cloud
  provider is down: plays pre-rendered clips (``greeter.clips``) in the same voice.

Both "hear" the visitor with a simple energy detector.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

import numpy as np

from greeter.audio import float_to_int16, int16_to_pcm, rms_dbfs
from greeter.backends.base import Backend

log = logging.getLogger(__name__)

RATE = 24000  # same output rate as the cloud models, so the resampler is exercised

OPENER = "Hey, green top! Come and stand on the green spot and say hi?"
BEGIN = "Hello! Are you enjoying the open day?"
REPLY = "That's lovely to hear, thanks for telling me."
CLOSE = "Do say hi to the team on the stand, and enjoy the day in that green top!"


def chime(notes=(660.0, 880.0), note_s: float = 0.35) -> bytes:
    t = np.arange(int(RATE * note_s)) / RATE
    env = np.minimum(1.0, t / 0.01) * np.exp(-4.0 * t)
    wave = np.concatenate([0.35 * env * np.sin(2 * np.pi * f * t) for f in notes])
    return int16_to_pcm(float_to_int16(wave))


class _EnergyEars:
    """Speech start/end from loudness: good enough for tests and the canned fallback."""

    def __init__(self, speech_dbfs: float = -38.0, end_silence_s: float = 0.8) -> None:
        self.speech_dbfs, self.end_silence_s = speech_dbfs, end_silence_s
        self.speech_s = self.silence_s = 0.0

    def feed(self, pcm: bytes) -> Optional[str]:
        """Returns "speaking" while speech goes on, "end" once at the end of a turn."""
        seconds = len(pcm) / 32000.0
        if rms_dbfs(pcm) > self.speech_dbfs:
            self.speech_s += seconds
            self.silence_s = 0.0
            return "speaking" if self.speech_s > 0.2 else None
        if self.speech_s > 0.0:
            self.silence_s += seconds
            if self.silence_s >= self.end_silence_s:
                heard, self.speech_s, self.silence_s = self.speech_s, 0.0, 0.0
                return "end" if heard >= 0.3 else None
        return None


class ScriptedBackend(Backend):
    name = "scripted"
    supports_opener = True

    def __init__(self, opener_delay_s: float = 0.2) -> None:
        super().__init__()
        self.opener_delay_s = opener_delay_s
        self.frames = 0
        self.audio_bytes = 0
        self.committed = []
        self._ears = _EnergyEars()
        self._busy = False
        self._tasks = set()

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _say(self, text: str, notes) -> None:
        self._busy = True
        try:
            await asyncio.sleep(0.3)  # "thinking"
            self._emit("bot_text", text)
            pcm = chime(notes)
            step = RATE // 10 * 2  # 100 ms chunks, faster than real time like the cloud models
            for i in range(0, len(pcm), step):
                self._emit("audio", pcm[i : i + step], RATE)
                await asyncio.sleep(0.02)
            self._emit("turn_complete")
        finally:
            self._busy = False

    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        if jpeg is not None:
            import cv2

            if cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR) is None:
                raise ValueError("notice frame is not a valid JPEG")

    async def prepare_opener(self, jpeg: bytes, instruction: str) -> None:
        self._opener_request = (jpeg, instruction)

        async def ready() -> None:
            await asyncio.sleep(self.opener_delay_s)
            self._emit("opener_ready", {"pcm": chime((660.0, 880.0)), "rate": RATE, "text": OPENER})

        self._spawn(ready())

    async def commit_opener(self, text: str) -> None:
        self.committed.append(text)

    async def begin(self, instruction: Optional[str]) -> None:
        if instruction:
            self._spawn(self._say(BEGIN, (740.0,)))

    async def send_audio(self, pcm: bytes) -> None:
        self.audio_bytes += len(pcm)
        heard = self._ears.feed(pcm)
        if heard == "speaking":
            self._emit("user_activity")
        elif heard == "end" and not self._busy:
            self._emit("user_turn_end")
            self._emit("user_text", "(speech)")
            self._spawn(self._say(REPLY, (880.0,)))

    async def send_frame(self, jpeg: bytes) -> None:
        self.frames += 1

    async def send_text(self, text: str) -> None:
        self._spawn(self._say(CLOSE, (880.0, 660.0)))

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await super().close()


class CannedBackend(Backend):
    """No network: invitation and replies come from pre-rendered clips (16 kHz PCM)."""

    name = "canned"
    supports_opener = True

    def __init__(self, clips: Dict[str, bytes], texts: Dict[str, str]) -> None:
        super().__init__()
        self.clips, self.texts = clips, texts
        self._ears = _EnergyEars()
        self._replied = False

    def _clip(self, name: str) -> None:
        pcm = self.clips.get(name)
        if pcm:
            self._emit("bot_text", self.texts.get(name, ""))
            self._emit("audio", pcm, 16000)
        self._emit("turn_complete")

    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        pass

    async def prepare_opener(self, jpeg: bytes, instruction: str) -> None:
        self._emit("opener_ready", {"pcm": self.clips.get("hey_green", b""), "rate": 16000, "text": self.texts.get("hey_green", "")})

    async def begin(self, instruction: Optional[str]) -> None:
        if instruction:
            self._clip("hello")

    async def send_audio(self, pcm: bytes) -> None:
        if self._ears.feed(pcm) == "end" and not self._replied:
            self._replied = True  # say it once, then let the visitor find a human
            self._emit("user_turn_end")
            self._clip("brain_offline")

    async def send_frame(self, jpeg: bytes) -> None:
        pass

    async def send_text(self, text: str) -> None:
        self._clip("goodbye")
