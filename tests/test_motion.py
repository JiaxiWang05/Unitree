"""Walk detection from leg joint speeds (read only, for --roam)."""

import math

from greeter.robot.motion import WalkDetector


def run(det, t0, t1, speed, dt=0.02):
    t, states = t0, []
    while t <= t1 + 1e-9:
        wobble = speed * math.sin(2 * math.pi * 1.8 * t)  # gait at ~1.8 Hz
        states.append(det.feed([wobble] * 12, t))
        t += dt
    return states


def test_standing_balance_is_not_walking():
    det = WalkDetector()
    assert not any(run(det, 0.0, 5.0, 0.15))


def test_walking_starts_quickly_and_stops_after_a_quiet_pause():
    det = WalkDetector()
    states = run(det, 0.0, 2.0, 3.0)
    assert states[-1] and states.index(True) < 30  # within 0.6 s
    assert run(det, 2.02, 3.0, 0.05)[-1]  # still "walking" during a short stop
    assert not run(det, 3.02, 5.0, 0.05)[-1]  # quiet for 1.5 s: standing


def test_a_brief_sway_does_not_stop_walking_early():
    det = WalkDetector()
    run(det, 0.0, 2.0, 3.0)
    run(det, 2.02, 3.0, 0.05)
    assert run(det, 3.02, 3.4, 3.0)[-1]  # moving again before 1.5 s of quiet
    assert run(det, 3.42, 4.6, 0.05)[-1]
