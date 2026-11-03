"""Depth frames for the talk-spot detector: the real head D435i, or a synthetic one for --mock.

Both keep only the newest frame (z16, metres = value x depth_scale); nothing is saved.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

from greeter.robot.depth_spot import CameraPose, DepthIntrinsics

log = logging.getLogger(__name__)


class _LatestFrame:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._seq = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.intrinsics: Optional[DepthIntrinsics] = None

    def _publish(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame, self._seq = frame, self._seq + 1

    def latest(self) -> Tuple[int, Optional[np.ndarray]]:
        with self._lock:
            return self._seq, self._frame

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class RealSenseDepth(_LatestFrame):
    """The G1's head D435i through pyrealsense2 (depth only; its RGB is not used).

    If the camera drops off USB, librealsense's own reconnect can leave the
    pipeline stopped; the reader then backs off and restarts it in the same mode
    (so the detector's intrinsics stay valid) until the camera is back.
    """

    MODES = ((848, 480, 15), (640, 480, 15), (480, 270, 15))  # the last two also work over USB 2

    def __init__(self, serial: Optional[str] = None, rs_module=None) -> None:
        super().__init__()
        self.serial = serial
        self._rs = rs_module
        self._pipe = None
        self._mode: Optional[Tuple[int, int, int]] = None
        self._pipe_lock = threading.Lock()
        self.restarts = 0

    def _open(self, modes) -> None:
        rs = self._rs
        last_error = None
        for width, height, fps in modes:
            pipe, cfg = rs.pipeline(), rs.config()
            if self.serial:
                cfg.enable_device(self.serial)
            cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
            try:
                profile = pipe.start(cfg)
            except RuntimeError as exc:  # mode not available (e.g. USB 2), device busy or gone
                last_error = exc
                continue
            intr = profile.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
            scale = profile.get_device().first_depth_sensor().get_depth_scale()
            with self._pipe_lock:
                self._pipe = pipe
            self._mode = (width, height, fps)
            self.intrinsics = DepthIntrinsics(intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy, scale)
            log.info("head D435i depth %dx%d@%d (scale %.4f m)", intr.width, intr.height, fps, scale)
            return
        raise RuntimeError("cannot start the head D435i depth stream: %s" % last_error)

    def start(self) -> "RealSenseDepth":
        if self._rs is None:
            import pyrealsense2 as rs

            self._rs = rs
        self._open(self.MODES)
        self._thread = threading.Thread(target=self._run, name="d435i", daemon=True)
        self._thread.start()
        return self

    def _stop_pipe(self) -> None:
        with self._pipe_lock:
            pipe = self._pipe
        if pipe is not None:
            try:
                pipe.stop()
            except Exception:
                pass

    def _run(self) -> None:
        fails = 0
        while not self._stop.is_set():
            try:
                frames = self._pipe.wait_for_frames(1000)
                depth = frames.get_depth_frame()
                if depth:
                    self._publish(np.asanyarray(depth.get_data()).copy())
                fails = 0
                continue
            except Exception as exc:  # RuntimeError from librealsense, or anything unexpected
                fails += 1
                if fails == 1 or fails % 30 == 0:
                    log.warning("D435i: no depth frame (%s); %d failure(s) in a row", exc, fails)
                restart = fails >= 3 or "before start" in str(exc)
            if self._stop.wait(1.0 if restart else 0.2):
                break
            if restart:
                self._stop_pipe()
                try:
                    self._open((self._mode,))
                    self.restarts += 1
                    fails = 0
                    log.info("D435i depth stream restarted")
                except Exception as exc:
                    log.debug("D435i restart failed: %s", exc)

    def stop(self) -> None:
        super().stop()
        self._stop_pipe()


# --- synthetic D435i for --mock and tests ------------------------------------------


@dataclass
class Body:
    """Something standing on the floor, in the robot's ground frame (x forward, y left)."""

    x: float
    y: float
    kind: str = "person"  # "person" (two legs + torso) or "box"
    height: float = 1.70
    width: float = 0.40
    depth: float = 0.25


Scenario = Callable[[float], List[Body]]


def _sway(t: float) -> float:
    return 0.015 * math.sin(2 * math.pi * 0.3 * t)  # people never stand perfectly still


def scenario_visit(t: float) -> List[Body]:
    """24 s loop aligned with scripts/make_test_clip.py (red 0-2 s, green 2-16 s, empty 16-24 s).

    The visitor waits at 1.8 m, steps onto the talk spot at 6 s, leaves at 16 s;
    a passer-by then walks straight across the spot (must not count)."""
    t = t % 24.0
    bodies = []
    if t < 4.0:
        bodies.append(Body(3.0 - 0.3 * t, 0.1))
    elif t < 6.0:
        bodies.append(Body(1.8, 0.1 + _sway(t)))
    elif t < 7.0:
        bodies.append(Body(1.8 - 0.8 * (t - 6.0), 0.1 - 0.1 * (t - 6.0)))
    elif t < 16.0:
        bodies.append(Body(1.0, _sway(t)))
    if 19.0 <= t < 21.5:
        bodies.append(Body(1.0, -1.5 + 1.2 * (t - 19.0)))
    return bodies


def scenario_walkby(t: float) -> List[Body]:
    t = t % 6.0
    return [Body(1.0, -1.8 + 1.0 * t)] if t < 3.6 else []


def scenario_bag(t: float) -> List[Body]:
    return [Body(1.0, 0.0, kind="box", height=0.4, width=0.35, depth=0.25)]


def scenario_empty(t: float) -> List[Body]:
    return []


SCENARIOS = {"visit": scenario_visit, "walkby": scenario_walkby, "bag": scenario_bag, "empty": scenario_empty}


class SyntheticDepth(_LatestFrame):
    """Ray-casts a floor and simple people/boxes through the D435i's real pose and FOV.

    Noise follows Intel's RMS model (about 1.5 cm at 2 m), plus 2 % dropouts.
    ``scenario`` maps seconds since start to the bodies in view.
    """

    def __init__(
        self,
        scenario: Scenario = scenario_visit,
        width: int = 424,
        height: int = 240,
        fps: float = 15.0,
        pose: Optional[CameraPose] = None,
        noise: bool = True,
        seed: int = 0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self.scenario, self.fps, self.noise, self.clock = scenario, fps, noise, clock
        self.pose = pose or CameraPose()
        self.intrinsics = DepthIntrinsics.from_fov(width, height)
        self._rng = np.random.default_rng(seed)
        v, u = np.mgrid[0:height, 0:width]
        xn = (u - self.intrinsics.ppx) / self.intrinsics.fx
        yn = (v - self.intrinsics.ppy) / self.intrinsics.fy
        c, s = math.cos(math.radians(self.pose.pitch_deg)), math.sin(math.radians(self.pose.pitch_deg))
        # ray direction per unit of optical-axis depth, in the ground frame
        self._df = c - yn * s
        self._dl = -xn
        self._du = -s - yn * c
        self._t0 = None

    def render(self, t: float) -> np.ndarray:
        pose = self.pose
        o_f, o_l, o_u = pose.forward_m, pose.lateral_m, pose.height_m
        df, dl, du = self._df, self._dl, self._du
        best = np.full(df.shape, np.inf)
        with np.errstate(divide="ignore", invalid="ignore"):
            floor = np.where(du < 0, -o_u / du, np.inf)
        best = np.minimum(best, floor)
        for body in self.scenario(t):
            parts = []
            if body.kind == "person":
                for side in (-0.1, 0.1):
                    parts.append(("cyl", body.x, body.y + side, 0.065, 0.0, 0.85))
                parts.append(("box", body.x - 0.12, body.x + 0.12, body.y - 0.2, body.y + 0.2, 0.85, 1.45))
            else:
                parts.append(("box", body.x - body.depth / 2, body.x + body.depth / 2,
                              body.y - body.width / 2, body.y + body.width / 2, 0.0, body.height))
            for part in parts:
                best = np.minimum(best, self._cylinder(*part[1:]) if part[0] == "cyl" else self._box(*part[1:]))
        z = best
        if self.noise:
            z = z + self._rng.normal(0.0, 1.0, z.shape) * 0.0037 * np.square(np.minimum(z, 10.0))
            z = np.where(self._rng.random(z.shape) < 0.02, 0.0, z)
        z = np.where((z > 0.1) & (z < 6.0) & np.isfinite(z), z, 0.0)
        return np.round(z / self.intrinsics.depth_scale).astype(np.uint16)

    def _cylinder(self, cx: float, cy: float, r: float, z0: float, z1: float) -> np.ndarray:
        o_f, o_l, o_u = self.pose.forward_m, self.pose.lateral_m, self.pose.height_m
        a = self._df ** 2 + self._dl ** 2
        b = 2 * ((o_f - cx) * self._df + (o_l - cy) * self._dl)
        c = (o_f - cx) ** 2 + (o_l - cy) ** 2 - r * r
        disc = b * b - 4 * a * c
        with np.errstate(invalid="ignore"):
            t = (-b - np.sqrt(disc)) / (2 * a)
        h = o_u + t * self._du
        hit = (disc >= 0) & (t > 0) & (h >= z0) & (h <= z1)
        return np.where(hit, t, np.inf)

    def _box(self, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> np.ndarray:
        o = (self.pose.forward_m, self.pose.lateral_m, self.pose.height_m)
        tmin = np.full(self._df.shape, -np.inf)
        tmax = np.full(self._df.shape, np.inf)
        with np.errstate(divide="ignore", invalid="ignore"):
            for d, lo, hi, oo in ((self._df, x0, x1, o[0]), (self._dl, y0, y1, o[1]), (self._du, z0, z1, o[2])):
                t1, t2 = (lo - oo) / d, (hi - oo) / d
                tmin = np.maximum(tmin, np.minimum(t1, t2))
                tmax = np.minimum(tmax, np.maximum(t1, t2))
        hit = (tmax >= np.maximum(tmin, 0.0)) & (tmin > 0)
        return np.where(hit, tmin, np.inf)

    def start(self) -> "SyntheticDepth":
        self._t0 = self.clock()
        self._thread = threading.Thread(target=self._run, name="synthetic-d435i", daemon=True)
        self._thread.start()
        log.info("synthetic head D435i %dx%d@%.0f", self.intrinsics.width, self.intrinsics.height, self.fps)
        return self

    def _run(self) -> None:
        period = 1.0 / self.fps
        while not self._stop.wait(period):
            self._publish(self.render(self.clock() - self._t0))


def open_depth(kind: str, scenario: str = "visit"):
    """``realsense`` | ``synthetic`` | ``off`` -> a started source or None."""
    if kind == "off":
        return None
    if kind == "synthetic":
        return SyntheticDepth(SCENARIOS[scenario]).start()
    if kind == "realsense":
        return RealSenseDepth().start()
    raise ValueError("unknown depth source %r" % kind)
