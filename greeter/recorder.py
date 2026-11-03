"""Records visits to disk for tuning (privacy is not a requirement for this deployment).

Layout under ``base`` (default ``~/g1-greeter/recordings``)::

    2026-10-20/
      trace.jsonl                 every scene snapshot (~5 Hz) and robot status, all day
      103512-track7/              one folder per visit
        mic.wav  robot.wav        16 kHz mono: what the robot heard / said
        frame-000-notice.jpg ...  frames shown to the model
        events.jsonl              states, transcripts, usage

Stops writing when free disk space drops below ``min_free_gb``.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import wave
from pathlib import Path
from typing import Any, Optional

from greeter.protocol import AUDIO_RATE

log = logging.getLogger(__name__)


class Recorder:
    def __init__(self, base: Path, min_free_gb: float = 2.0) -> None:
        self.base = Path(base).expanduser()
        self.min_free_gb = min_free_gb
        self.visit: Optional[Path] = None
        self._mic: Optional[wave.Wave_write] = None
        self._robot: Optional[wave.Wave_write] = None
        self._frames = 0
        self._ok_until = 0.0
        self._space_ok = True

    def _space(self) -> bool:
        now = time.monotonic()
        if now >= self._ok_until:
            self._ok_until = now + 30.0
            self.base.mkdir(parents=True, exist_ok=True)
            free_gb = shutil.disk_usage(str(self.base)).free / 1e9
            if self._space_ok and free_gb < self.min_free_gb:
                log.warning("recording paused: only %.1f GB free", free_gb)
            self._space_ok = free_gb >= self.min_free_gb
        return self._space_ok

    def _day(self) -> Path:
        day = self.base / time.strftime("%Y-%m-%d")
        day.mkdir(parents=True, exist_ok=True)
        return day

    @staticmethod
    def _jsonl(path: Path, record: dict) -> None:
        record = dict(record, wall=round(time.time(), 3))
        with open(path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def trace(self, kind: str, data: Any) -> None:
        if self._space():
            self._jsonl(self._day() / "trace.jsonl", {"kind": kind, "data": data})

    def start_visit(self, label: str) -> None:
        self.end_visit()
        if not self._space():
            return
        self.visit = self._day() / ("%s-%s" % (time.strftime("%H%M%S"), label))
        self.visit.mkdir(parents=True, exist_ok=True)
        self._mic, self._robot, self._frames = self._wav("mic.wav"), self._wav("robot.wav"), 0
        log.info("recording visit to %s", self.visit)

    def _wav(self, name: str) -> wave.Wave_write:
        w = wave.open(str(self.visit / name), "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(AUDIO_RATE)
        return w

    def mic(self, pcm: bytes) -> None:
        if self._mic is not None:
            self._mic.writeframes(pcm)

    def robot(self, pcm: bytes) -> None:
        if self._robot is not None:
            self._robot.writeframes(pcm)

    def frame(self, jpeg: bytes, tag: str) -> None:
        if self.visit is not None and jpeg:
            (self.visit / ("frame-%03d-%s.jpg" % (self._frames, tag))).write_bytes(jpeg)
            self._frames += 1

    def event(self, kind: str, data: Any = None) -> None:
        if self.visit is not None:
            self._jsonl(self.visit / "events.jsonl", {"kind": kind, "data": data})

    def end_visit(self) -> None:
        for w in (self._mic, self._robot):
            if w is not None:
                w.close()
        self._mic = self._robot = None
        self.visit = None


class NullRecorder(Recorder):
    """``--no-record``."""

    def __init__(self) -> None:
        super().__init__(Path("."))

    def trace(self, kind: str, data: Any) -> None:
        pass

    def start_visit(self, label: str) -> None:
        pass
