"""Hardware interface behind the robot core, shared by the real G1 and the laptop mock.

The greeter never moves the robot: there is no arm, waist or locomotion
interface here at all. Only audio and the LED strip.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, Tuple

from greeter.protocol import AUDIO_RATE, SAMPLE_WIDTH

log = logging.getLogger(__name__)

RGB = Tuple[int, int, int]
MicCallback = Callable[[bytes], None]
BYTES_PER_S = AUDIO_RATE * SAMPLE_WIDTH


class LatestValueThrottle:
    """Calls ``fn(value)`` at most once per ``min_interval`` s, always with the newest value.

    Used for the G1 LED, which must not be updated more often than every 200 ms.
    Intermediate values are dropped; the last one submitted is always applied.
    """

    def __init__(self, fn: Callable[[RGB], None], min_interval: float, clock: Callable[[], float] = time.monotonic):
        self._fn, self._min, self._clock = fn, min_interval, clock
        self._cond = threading.Condition()
        self._pending: Optional[RGB] = None
        self._last_call = -1e9
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="throttle", daemon=True)
        self._thread.start()

    def submit(self, value: RGB) -> None:
        with self._cond:
            self._pending = value
            self._cond.notify()

    def _run(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._closed:
                    self._cond.wait()
                if self._closed:
                    return
                wait = self._last_call + self._min - self._clock()
                if wait > 0:
                    self._cond.wait(wait)
                    continue  # re-check: a newer value may have arrived
                value, self._pending = self._pending, None
                self._last_call = self._clock()
            try:
                self._fn(value)
            except Exception:
                log.exception("throttled call failed")

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify()
        self._thread.join(timeout=1.0)


class SoundDeviceAudio:
    """Mic and/or speaker through PortAudio (laptop audio, or a USB mic/DAC on the Jetson).

    16 kHz mono s16le in and out, like the G1's own audio path.
    """

    def __init__(self, input_device=None, output_device=None, use_input: bool = True, use_output: bool = True) -> None:
        self.input_device, self.output_device = input_device, output_device
        self.use_input, self.use_output = use_input, use_output
        self._lock = threading.Lock()
        self._buf = bytearray()
        self._out = self._in = None
        self._latency = 0.0

    def start(self, on_mic: Optional[MicCallback]) -> None:
        import sounddevice as sd

        if self.use_output:
            self._out = sd.RawOutputStream(
                samplerate=AUDIO_RATE, channels=1, dtype="int16", blocksize=320, latency="low",
                device=self.output_device, callback=self._fill,
            )
            self._out.start()
            self._latency = float(self._out.latency)
        if self.use_input and on_mic is not None:
            self._in = sd.RawInputStream(
                samplerate=AUDIO_RATE, channels=1, dtype="int16", blocksize=800, device=self.input_device,
                callback=lambda indata, frames, t, status: on_mic(bytes(indata)),
            )
            self._in.start()

    def _fill(self, outdata, frames, time_info, status) -> None:
        n = len(outdata)
        with self._lock:
            chunk = bytes(self._buf[:n])
            del self._buf[:n]
        outdata[: len(chunk)] = chunk
        if len(chunk) < n:
            outdata[len(chunk) :] = b"\x00" * (n - len(chunk))

    def play(self, pcm: bytes) -> None:
        with self._lock:
            self._buf.extend(pcm)

    def stop(self) -> None:
        with self._lock:
            self._buf.clear()

    def playing_until(self) -> float:
        with self._lock:
            if not self._buf:
                return 0.0
            return time.monotonic() + len(self._buf) / float(BYTES_PER_S) + self._latency

    def close(self) -> None:
        for stream in (self._in, self._out):
            if stream is not None:
                stream.stop()
                stream.close()


class RobotIO:
    """Speaker, mic and LED. Subclasses implement the ``_``-prefixed hooks.

    All public methods are thread-safe and non-blocking.
    """

    led_min_interval = 0.2  # G1 LedControl must be >= 200 ms apart

    def __init__(self) -> None:
        self._led = LatestValueThrottle(self._set_led, self.led_min_interval)

    def start(self, on_mic: MicCallback) -> None:
        """Begin delivering 16 kHz mono s16le mic audio to ``on_mic`` (any thread)."""
        raise NotImplementedError

    def close(self) -> None:
        self._led.close()

    def play(self, pcm: bytes) -> None:
        """Queue 16 kHz mono s16le speech."""
        raise NotImplementedError

    def stop_playback(self) -> None:
        raise NotImplementedError

    def playing_until(self) -> float:
        """``time.monotonic()`` at which queued speech is expected to finish."""
        raise NotImplementedError

    def led(self, rgb: RGB) -> None:
        r, g, b = (max(0, min(255, int(v))) for v in rgb)
        self._led.submit((r, g, b))

    def _set_led(self, rgb: RGB) -> None:
        raise NotImplementedError

    def status(self) -> dict:
        """Robot health for the logs (battery etc.); empty when unknown."""
        return {}

    def walking(self) -> Optional[bool]:
        """Whether the robot is being walked right now; None when not measured."""
        return None
