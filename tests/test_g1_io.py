"""G1 mic multicast watch: warn when the stream stops or arrives muted (wrong voice-assistant mode)."""

import numpy as np

from greeter.audio import int16_to_pcm
from greeter.robot.g1_io import MicWatch

ZEROS = b"\x00\x00" * 2560  # one 160 ms packet as the robot sends it outside wake-up mode
VOICE = int16_to_pcm(np.random.default_rng(1).normal(0, 300, 2560))


def test_no_packets_warns_once_with_the_wake_up_hint():
    w = MicWatch(now=0.0)
    assert w.timeout(4.0) is None
    msg = w.timeout(5.5)
    assert "no multicast audio" in msg and "wake-up mode" in msg and "L1+L2" in msg
    assert w.timeout(9.0) is None  # once
    assert w.packet(VOICE, 10.0) is None
    assert w.timeout(16.0) is not None  # stops again: warns again


def test_all_zero_packets_warn_once_after_5_s():
    w = MicWatch(now=0.0)
    warnings = [w.packet(ZEROS, t / 10) for t in range(0, 80)]
    hits = [m for m in warnings if m]
    assert len(hits) == 1 and "all zeros" in hits[0] and "wake-up mode" in hits[0]
    assert warnings.index(hits[0]) == 50


def test_real_audio_resets_the_muted_warning():
    w = MicWatch(now=0.0)
    for t in range(0, 60):
        w.packet(ZEROS, t / 10)
    assert w.warned_flat
    assert w.packet(VOICE, 6.1) is None and not w.warned_flat
    assert w.packet(ZEROS, 6.2) is None  # a short silence is not muting
