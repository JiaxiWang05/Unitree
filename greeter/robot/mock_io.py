"""Laptop stand-ins for the G1 hardware: laptop mic and speaker; the LED is logged."""

from __future__ import annotations

import logging
import threading
import time

from greeter.robot.io_base import BYTES_PER_S, RGB, MicCallback, RobotIO, SoundDeviceAudio

log = logging.getLogger(__name__)


class MockRobotIO(RobotIO):
    """``speaker=False`` / ``mic=False`` run headless: playback is only timed, the mic sends silence."""

    def __init__(self, speaker: bool = True, mic: bool = True, input_device=None, output_device=None) -> None:
        super().__init__()
        self._speaker, self._mic = speaker, mic
        self._audio = SoundDeviceAudio(input_device, output_device, use_input=mic, use_output=speaker)
        self._lock = threading.Lock()
        self._sim_until = 0.0
        self._stop = threading.Event()
        self.leds = []  # for tests
        self.played = bytearray()

    def start(self, on_mic: MicCallback) -> None:
        if self._speaker or self._mic:
            self._audio.start(on_mic if self._mic else None)
        if not self._mic:
            threading.Thread(target=self._silence, args=(on_mic,), name="mock-mic", daemon=True).start()
        log.info("[mock] speaker=%s mic=%s", "laptop" if self._speaker else "timed only", "laptop" if self._mic else "silence")

    def _silence(self, on_mic: MicCallback) -> None:
        chunk = b"\x00" * (BYTES_PER_S // 20)
        while not self._stop.wait(0.05):
            on_mic(chunk)

    def play(self, pcm: bytes) -> None:
        with self._lock:
            self.played.extend(pcm)
            if self._speaker:
                self._audio.play(pcm)
            else:
                self._sim_until = max(self._sim_until, time.monotonic()) + len(pcm) / float(BYTES_PER_S)

    def stop_playback(self) -> None:
        with self._lock:
            self._audio.stop()
            self._sim_until = time.monotonic()

    def playing_until(self) -> float:
        if self._speaker:
            return self._audio.playing_until()
        with self._lock:
            return self._sim_until

    def _set_led(self, rgb: RGB) -> None:
        self.leds.append(rgb)
        log.debug("[mock] LED rgb%s", rgb)

    def close(self) -> None:
        self._stop.set()
        self._audio.close()
        super().close()
