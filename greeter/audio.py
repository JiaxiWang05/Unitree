"""PCM helpers shared by both sides: streaming resampler and simple levels."""

from __future__ import annotations

from math import gcd

import numpy as np


def pcm_to_int16(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype="<i2")


def int16_to_pcm(samples: np.ndarray) -> bytes:
    return np.asarray(samples, dtype="<i2").tobytes()


def float_to_int16(samples: np.ndarray) -> np.ndarray:
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")


def pcm_duration(pcm: bytes, rate: int, sample_width: int = 2) -> float:
    return len(pcm) / float(rate * sample_width)


def is_flat(pcm: bytes, tolerance: int = 2) -> bool:
    """True for audio no live microphone produces: every sample (nearly) the same, e.g. all zeros."""
    x = pcm_to_int16(pcm)
    return x.size == 0 or int(x.max()) - int(x.min()) <= tolerance


def rms_dbfs(pcm: bytes) -> float:
    x = pcm_to_int16(pcm).astype(np.float64)
    if x.size == 0:
        return -120.0
    rms = np.sqrt(np.mean(x * x)) / 32768.0
    return float(20.0 * np.log10(max(rms, 1e-6)))


class StreamResampler:
    """Stateful rational resampler for mono int16 PCM (e.g. Gemini 24 kHz -> robot 16 kHz).

    Upsample by L, low-pass with a Kaiser-windowed sinc, keep every M-th
    sample. Filter history and output phase carry across calls, so feeding a
    stream in arbitrary chunks gives exactly the same samples as one call.
    """

    def __init__(self, src_rate: int, dst_rate: int, taps_per_phase: int = 24) -> None:
        g = gcd(src_rate, dst_rate)
        self.src_rate, self.dst_rate = src_rate, dst_rate
        self.up, self.down = dst_rate // g, src_rate // g
        n_taps = taps_per_phase * max(self.up, self.down) | 1  # odd => integer delay
        cutoff = 0.5 / max(self.up, self.down) * 0.92  # cycles/sample at the upsampled rate
        t = np.arange(n_taps) - (n_taps - 1) / 2.0
        h = 2.0 * cutoff * np.sinc(2.0 * cutoff * t) * np.kaiser(n_taps, 8.0)
        self._h = h * (self.up / h.sum())  # unity DC gain after zero stuffing
        self._hist = np.zeros(n_taps - 1)
        self._phase = 0

    def process(self, pcm: bytes) -> bytes:
        if self.up == self.down:
            return pcm
        x = pcm_to_int16(pcm).astype(np.float64)
        if x.size == 0:
            return b""
        xu = np.zeros(x.size * self.up)
        xu[:: self.up] = x
        buf = np.concatenate([self._hist, xu])
        filtered = np.convolve(buf, self._h, mode="valid")  # one value per sample of xu
        out = filtered[self._phase :: self.down]
        self._phase = self._phase + out.size * self.down - xu.size
        self._hist = buf[-(self._h.size - 1) :]
        return int16_to_pcm(np.clip(np.round(out), -32768, 32767))

    def reset(self) -> None:
        self._hist[:] = 0.0
        self._phase = 0
