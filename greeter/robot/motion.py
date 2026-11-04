"""Is the robot being walked? Read from its leg joint speeds; this module never commands motion.

With ``--roam`` a team member walks the G1 around with the Unitree remote (the robot's own
locomotion). The greeter only needs to know when that is happening, so it stops inviting
people while the robot moves and starts again once it stands still.

The G1 publishes ``rt/lowstate`` (``unitree_hg`` ``LowState_``) at about 500 Hz; the first
12 motors are the legs (hip pitch/roll/yaw, knee, ankle pitch/roll, left then right).
Standing in balance mode, the legs barely move (well under 0.2 rad/s RMS); walking swings
hips and knees at several rad/s. The thresholds below are guesses to check on the robot.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional, Sequence, Tuple

LEG_MOTORS = 12


class WalkDetector:
    """Leg-speed RMS over a short window, with hysteresis: walking starts fast, stops slowly."""

    def __init__(self, window_s: float = 0.5, start_rms: float = 0.6, stop_rms: float = 0.25, stop_after_s: float = 1.5) -> None:
        self.window_s, self.start_rms, self.stop_rms, self.stop_after_s = window_s, start_rms, stop_rms, stop_after_s
        self._samples: Deque[Tuple[float, float]] = deque()  # (t, mean square leg speed)
        self._quiet_since: Optional[float] = None
        self.walking = False
        self.rms = 0.0

    def feed(self, leg_dq: Sequence[float], now: float) -> bool:
        speeds = [float(v) for v in leg_dq[:LEG_MOTORS]]
        if not speeds:
            return self.walking
        self._samples.append((now, sum(v * v for v in speeds) / len(speeds)))
        while self._samples and now - self._samples[0][0] > self.window_s:
            self._samples.popleft()
        self.rms = math.sqrt(sum(ms for _, ms in self._samples) / len(self._samples))
        if not self.walking:
            if self.rms > self.start_rms:
                self.walking, self._quiet_since = True, None
        elif self.rms < self.stop_rms:
            if self._quiet_since is None:
                self._quiet_since = now
            elif now - self._quiet_since >= self.stop_after_s:
                self.walking = False
        else:
            self._quiet_since = None
        return self.walking
