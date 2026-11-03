import json

import numpy as np
import pytest

from greeter import protocol
from greeter.audio import StreamResampler, int16_to_pcm, is_flat, pcm_duration, pcm_to_int16, rms_dbfs


def tone(freq, rate, seconds, amp=0.5):
    t = np.arange(int(rate * seconds)) / rate
    return int16_to_pcm(np.round(amp * 32767 * np.sin(2 * np.pi * freq * t)))


def dominant_freq(pcm, rate):
    x = pcm_to_int16(pcm).astype(float)
    spectrum = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return np.fft.rfftfreq(x.size, 1 / rate)[np.argmax(spectrum)]


def test_resample_24k_to_16k_length_and_pitch():
    out = StreamResampler(24000, 16000).process(tone(1000, 24000, 1.0))
    assert len(out) // 2 == 16000
    assert dominant_freq(out, 16000) == pytest.approx(1000, abs=2)


def test_resample_keeps_level():
    out = pcm_to_int16(StreamResampler(24000, 16000).process(tone(440, 24000, 1.0)))
    steady = out[2000:-2000].astype(float)
    assert np.sqrt(np.mean(steady**2)) == pytest.approx(0.5 * 32767 / np.sqrt(2), rel=0.02)


def test_resample_removes_content_above_new_nyquist():
    out = StreamResampler(24000, 16000).process(tone(10000, 24000, 1.0))
    assert rms_dbfs(out) < -40  # 10 kHz cannot exist at 16 kHz: must be filtered, not aliased


def test_resample_chunking_is_seamless():
    pcm = tone(700, 24000, 0.5)
    whole = StreamResampler(24000, 16000).process(pcm)
    rs = StreamResampler(24000, 16000)
    rng = np.random.default_rng(0)
    pieces, i = [], 0
    while i < len(pcm):
        n = int(rng.integers(1, 900)) * 2  # odd chunk sizes, never split a sample
        pieces.append(rs.process(pcm[i : i + n]))
        i += n
    assert b"".join(pieces) == whole


def test_resample_identity_and_empty():
    pcm = tone(440, 16000, 0.1)
    assert StreamResampler(16000, 16000).process(pcm) == pcm
    assert StreamResampler(24000, 16000).process(b"") == b""


def test_is_flat_spots_a_muted_mic():
    assert is_flat(b"\x00\x00" * 2560)  # what the G1 sends outside wake-up mode
    assert is_flat(int16_to_pcm(np.full(2560, 7)))
    assert is_flat(b"")
    quiet_room = int16_to_pcm(np.random.default_rng(0).normal(0, 20, 2560))
    assert not is_flat(quiet_room)
    assert not is_flat(tone(440, 16000, 0.16, amp=0.01))


def test_pcm_duration():
    assert pcm_duration(b"\x00" * 32000, 16000) == pytest.approx(1.0)


def test_binary_round_trip():
    msg = protocol.encode_binary(protocol.TAG_PLAY, b"\x01\x02")
    assert protocol.decode_binary(msg) == (protocol.TAG_PLAY, b"\x01\x02")
    with pytest.raises(ValueError):
        protocol.decode_binary(b"Zxx")
    with pytest.raises(ValueError):
        protocol.encode_binary(b"Q", b"")


def test_event_round_trip():
    text = protocol.encode_event("led", rgb=[0, 255, 0])
    assert json.loads(text) == {"type": "led", "rgb": [0, 255, 0]}
    assert protocol.decode_event(text)["rgb"] == [0, 255, 0]
    with pytest.raises(ValueError):
        protocol.decode_event("[1, 2]")
