"""Talk-spot occupancy from the G1's built-in head D435i depth camera.

The head D435i is fixed to the torso, pitched 47.6 deg down, about 1.26 m above
the floor (Unitree URDF ``d435_joint``). It only sees legs and feet, but the
talk spot (0.6-1.4 m in front of the robot) lies inside its floor view, so it
answers one question very well: *is someone standing on the talk spot?*

It runs standalone, next to the chest webcam: no person model, no matching to
webcam tracks. Per depth frame:

1. deproject a sub-sampled grid of pixels into the robot's ground frame
   (x forward, y left, z up) with the nominal camera pose;
2. correct for lean/sway with a floor plane re-fitted from the depth itself;
3. count points standing on the spot footprint 0.05-1.2 m above the floor,
   and require some of them at thigh height (>= 0.55 m) so bags don't count;
4. the blob (footprint plus a 0.35 m margin) must be centred on the spot, so a
   bystander beside it whose arm pokes in doesn't count;
5. occupied after 1.5 s of continuous presence while slow (< 0.3 m/s, so
   people walking across don't count); released after 0.7 s empty;
6. something tall that stays perfectly still (centroid jitter < 1.5 mm, well
   below a standing person's sway) for 60 s is treated as an object (sign,
   pushchair); the moment anything changes - someone joins it, it moves - it is
   reconsidered.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple

import numpy as np

# Unitree URDF: d435_joint rpy pitch 0.8307767 rad; 0.474 m above the pelvis, pelvis 0.784 m standing
NOMINAL_PITCH_DEG = 47.6
NOMINAL_HEIGHT_M = 1.258
FORWARD_OFFSET_M = 0.054  # camera ahead of the pelvis axis
LATERAL_OFFSET_M = 0.018  # camera left of the centre line


@dataclass
class DepthIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    ppx: float
    ppy: float
    depth_scale: float = 0.001  # metres per depth unit (D435i default: 1 mm)

    @classmethod
    def from_fov(cls, width: int, height: int, hfov_deg: float = 87.0, vfov_deg: float = 58.0, depth_scale: float = 0.001):
        return cls(
            width, height,
            fx=(width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0),
            fy=(height / 2.0) / math.tan(math.radians(vfov_deg) / 2.0),
            ppx=(width - 1) / 2.0, ppy=(height - 1) / 2.0, depth_scale=depth_scale,
        )


@dataclass
class CameraPose:
    pitch_deg: float = NOMINAL_PITCH_DEG
    height_m: float = NOMINAL_HEIGHT_M
    forward_m: float = FORWARD_OFFSET_M
    lateral_m: float = LATERAL_OFFSET_M


@dataclass
class SpotConfig:
    near: float = 0.6  # talk-spot footprint in the ground frame (matches SceneConfig.spot_*)
    far: float = 1.4
    half_width: float = 0.6
    low: float = 0.05  # height band above the floor that counts
    high: float = 1.2
    tall_min: float = 0.55  # a standing person shows points this high (thighs); bags don't
    min_points: int = 150  # at the reference sampling density (REF_PX_PER_RAD); a person gives 450-2250
    min_tall_points: int = 40
    blob_margin: float = 0.35  # the blob around the footprint whose centre must lie on the spot
    dwell_s: float = 1.5
    release_s: float = 0.7
    max_speed: float = 0.3  # m/s of the spot points' centroid
    speed_tau_s: float = 0.4
    static_s: float = 60.0
    static_tol_m: float = 0.0015  # objects: < 0.5 mm of noise; people standing still: 2.5 mm or more
    unstatic_move_m: float = 0.05  # a "static" thing that moves this much is reconsidered
    max_range_m: float = 4.5
    refit_s: float = 20.0  # re-fit the floor this often while the spot is empty


REF_PX_PER_RAD = 105.75  # sampling density the thresholds are tuned for (848x480 depth, fx ~423, every 4th pixel)


@dataclass
class SpotState:
    t: float
    occupied: bool = False
    raw: bool = False
    points: int = 0
    tall: int = 0
    dwell_s: float = 0.0
    x: Optional[float] = None  # centroid of the spot points (m forward, m left)
    y: Optional[float] = None
    speed: float = 0.0
    static: bool = False
    floor_pitch_deg: float = NOMINAL_PITCH_DEG
    floor_height_m: float = NOMINAL_HEIGHT_M
    valid_ratio: float = 0.0

    def to_dict(self) -> dict:
        r = lambda v, n=2: None if v is None else round(float(v), n)  # noqa: E731
        return {
            "source": "depth", "occupied": self.occupied, "raw": self.raw, "points": self.points, "tall": self.tall,
            "dwell_s": r(self.dwell_s, 1), "x": r(self.x), "y": r(self.y), "speed": r(self.speed),
            "static": self.static, "pitch_deg": r(self.floor_pitch_deg, 1), "height_m": r(self.floor_height_m, 3),
            "valid": r(self.valid_ratio),
        }


def ground_points(depth: np.ndarray, intr: DepthIntrinsics, pose: CameraPose, stride: int):
    """Sub-sample ``depth`` (z16) and return (forward, left, up) in metres for valid pixels.

    Camera optical frame: x right, y down, z forward, pitched ``pose.pitch_deg``
    nose-down. Ground frame: x forward, y left, z up from the floor.
    """
    v, u = np.mgrid[0 : intr.height : stride, 0 : intr.width : stride]
    z = depth[::stride, ::stride].astype(np.float32) * intr.depth_scale
    xn = (u.astype(np.float32) - intr.ppx) / intr.fx
    yn = (v.astype(np.float32) - intr.ppy) / intr.fy
    valid = (z > 0.15)
    xc, yc = xn * z, yn * z
    c, s = math.cos(math.radians(pose.pitch_deg)), math.sin(math.radians(pose.pitch_deg))
    fwd = z * c - yc * s + pose.forward_m
    left = -xc + pose.lateral_m
    up = pose.height_m - z * s - yc * c
    return fwd[valid], left[valid], up[valid], float(valid.mean()) if valid.size else 0.0


class FloorPlane:
    """Residual plane ``up = a*fwd + b*left + c`` of the floor in the nominal ground frame.

    Absorbs lean, sway and small pitch/height errors of the URDF pose.
    """

    def __init__(self) -> None:
        self.a = self.b = self.c = 0.0
        self.fitted = False

    def fit(self, fwd: np.ndarray, left: np.ndarray, up: np.ndarray, iters: int = 4) -> bool:
        cand = (fwd > 0.3) & (fwd < 3.5) & (np.abs(left) < 2.0)
        sel = cand & (np.abs(up - (self.a * fwd + self.b * left + self.c)) < 0.25)
        tol = 0.12
        for _ in range(iters):
            if int(sel.sum()) < 200:
                return False
            A = np.stack([fwd[sel], left[sel], np.ones(int(sel.sum()), np.float32)], axis=1)
            coef, *_ = np.linalg.lstsq(A, up[sel], rcond=None)
            a, b, c = (float(v) for v in coef)
            resid = up - (a * fwd + b * left + c)
            tol = max(0.03, tol * 0.6)
            sel = cand & (np.abs(resid) < tol)
        if abs(a) > 0.35 or abs(c) > 0.4:  # > ~20 deg or 40 cm off: not a floor, keep the old plane
            return False
        self.a, self.b, self.c, self.fitted = a, b, c, True
        return True

    def height(self, fwd: np.ndarray, left: np.ndarray, up: np.ndarray) -> np.ndarray:
        return up - (self.a * fwd + self.b * left + self.c)

    def corrected(self, pose: CameraPose) -> CameraPose:
        """The camera pose implied by the fitted plane: the floor rising ahead (a > 0) in the
        assumed frame means the camera actually looks down more steeply."""
        return CameraPose(
            pitch_deg=pose.pitch_deg + math.degrees(math.atan(self.a)),
            height_m=pose.height_m - self.c,
            forward_m=pose.forward_m,
            lateral_m=pose.lateral_m,
        )


class DepthSpotDetector:
    def __init__(self, intr: DepthIntrinsics, cfg: Optional[SpotConfig] = None, pose: Optional[CameraPose] = None) -> None:
        self.intr, self.cfg, self.pose = intr, cfg or SpotConfig(), pose or CameraPose()
        # sample about the same rays per radian whatever the stream mode, and scale the
        # count thresholds by what is left over (e.g. 640x480 on USB 2)
        self.stride = max(1, int(round(intr.fx / REF_PX_PER_RAD)))
        self.density = (intr.fx / self.stride) * (intr.fy / self.stride) / REF_PX_PER_RAD ** 2
        self.min_points = max(10, int(round(self.cfg.min_points * self.density)))
        self.min_tall = max(4, int(round(self.cfg.min_tall_points * self.density)))
        self.floor = FloorPlane()
        self.nominal_pose = self.pose
        self._last_fit = -1e9
        self._raw_since: Optional[float] = None
        self._clear_since: Optional[float] = None
        self._occupied = False
        self._static = False
        self._centroid: Optional[Tuple[float, float]] = None
        self._centroid_t = 0.0
        self._vel: Optional[Tuple[float, float]] = None
        self._history: Deque[Tuple[float, float, float]] = deque()
        self._static_base: Optional[Tuple[int, int, float, float]] = None
        self.state = SpotState(t=0.0)

    def _refine_pose(self, depth: np.ndarray) -> bool:
        """Fit the floor, fold pitch/height errors into the pose (so the footprint lands in the
        right place), then keep only the small left-right tilt as a residual plane."""
        pose = self.pose
        for _ in range(2):
            fwd, left, up, _ = ground_points(depth, self.intr, pose, self.stride)
            plane = FloorPlane()
            if not plane.fit(fwd, left, up):
                return False
            pose = plane.corrected(pose)
        if abs(pose.pitch_deg - self.nominal_pose.pitch_deg) > 15 or abs(pose.height_m - self.nominal_pose.height_m) > 0.3:
            return False  # far from the URDF: probably not looking at a floor, keep what we had
        fwd, left, up, _ = ground_points(depth, self.intr, pose, self.stride)
        residual = FloorPlane()
        if residual.fit(fwd, left, up):
            residual.a = residual.c = 0.0  # pitch and height are now in the pose
            self.floor = residual
        else:
            self.floor = FloorPlane()
            self.floor.fitted = True
        self.pose = pose
        return True

    def update(self, depth: np.ndarray, now: float) -> SpotState:
        cfg = self.cfg
        fwd, left, up, valid_ratio = ground_points(depth, self.intr, self.pose, self.stride)
        if not self.floor.fitted or (not self._occupied and not self.state.raw and now - self._last_fit >= cfg.refit_s):
            if self._refine_pose(depth):
                self._last_fit = now
                fwd, left, up, valid_ratio = ground_points(depth, self.intr, self.pose, self.stride)
        keep = fwd < cfg.max_range_m
        fwd, left, up = fwd[keep], left[keep], up[keep]
        h = self.floor.height(fwd, left, up)
        band = (h >= cfg.low) & (h <= cfg.high)
        m = cfg.blob_margin
        near = band & (fwd >= cfg.near - m) & (fwd <= cfg.far + m) & (np.abs(left) <= cfg.half_width + m)
        on_spot = near & (fwd >= cfg.near) & (fwd <= cfg.far) & (np.abs(left) <= cfg.half_width)
        count = int(on_spot.sum())
        tall = int((on_spot & (h >= cfg.tall_min)).sum())
        cx = cy = None
        if count:
            cx, cy = float(fwd[near].mean()), float(left[near].mean())  # where the whole blob is
        # the camera sees the front of the legs, so blob centres read ~6 cm nearer than the person
        centred = cx is not None and cfg.near - 0.1 <= cx <= cfg.far and abs(cy) <= cfg.half_width + 0.05
        raw = count >= self.min_points and tall >= self.min_tall and centred

        speed = 0.0
        if raw:
            if self._centroid is not None and now > self._centroid_t:
                dt = now - self._centroid_t
                vx, vy = (cx - self._centroid[0]) / dt, (cy - self._centroid[1]) / dt
                if self._vel is None:  # first pair: no smoothing, so walkers are slow-gated at once
                    self._vel = (vx, vy)
                else:
                    alpha = 1.0 - math.exp(-dt / cfg.speed_tau_s)
                    self._vel = (self._vel[0] + alpha * (vx - self._vel[0]), self._vel[1] + alpha * (vy - self._vel[1]))
            self._centroid, self._centroid_t = (cx, cy), now
            speed = math.hypot(*self._vel) if self._vel is not None else 0.0
            if self._raw_since is None or speed >= cfg.max_speed or self._vel is None:
                self._raw_since = now  # (re)start the dwell clock until it has been seen to be slow
            self._clear_since = None
            self._history.append((now, cx, cy))
            while self._history and now - self._history[0][0] > cfg.static_s + 1.0:  # a little slack, see below
                self._history.popleft()
        else:
            self._centroid, self._vel = None, None
            self._raw_since = None
            if self._clear_since is None:
                self._clear_since = now

        if raw and self._static and self._static_base is not None:
            base_count, base_tall, bx, by = self._static_base
            joined = count > base_count + self.min_points or tall > base_tall + self.min_tall
            if joined or math.hypot(cx - bx, cy - by) > cfg.unstatic_move_m:
                self._static, self._static_base = False, None  # something changed: think again
                self._history.clear()
                self._raw_since = now

        dwell = 0.0 if self._raw_since is None else now - self._raw_since
        if raw and not self._occupied and not self._static and dwell >= cfg.dwell_s:
            self._occupied = True
        if not raw and self._clear_since is not None and now - self._clear_since >= cfg.release_s:
            self._occupied = False
            self._static, self._static_base = False, None
            self._history.clear()
        if raw and not self._static and self._history and now - self._history[0][0] >= cfg.static_s:
            xs = np.array([p[1] for p in self._history])
            ys = np.array([p[2] for p in self._history])
            if float(np.hypot(xs.std(), ys.std())) < cfg.static_tol_m:
                self._static = True  # not a person: it hasn't moved a millimetre for a minute
                self._static_base = (count, tall, cx, cy)
                self._occupied = False

        pitch, height = self.pose.pitch_deg, self.pose.height_m
        self.state = SpotState(
            t=now, occupied=self._occupied, raw=raw, points=count, tall=tall, dwell_s=dwell,
            x=cx, y=cy, speed=speed, static=self._static, floor_pitch_deg=pitch, floor_height_m=height,
            valid_ratio=valid_ratio,
        )
        return self.state
