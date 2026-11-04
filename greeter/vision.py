"""Scene understanding for the greeter: who is there, how far, facing us, moving, in a group, in green.

Pure NumPy/OpenCV (no YOLO, no robot) so all of it is unit-testable. The
detector (``greeter.robot.detector``) turns Ultralytics results into
:class:`Detection` objects; :class:`Scene` turns a frame of detections into a
:class:`Snapshot` of :class:`Person` records and decides when someone is worth
*noticing* (the first rung of the interaction ladder in
``greeter.dialogue.machine``).

Green test (design doc 5.3): CIELAB hue 110–170 deg and chroma C* > 20 inside the
torso; fluorescent hi-vis (L* > 85, C* > 70, h < 125) rejected; a person counts
as green when >= 25 % of the torso is green in 6 of the last 10 frames.

Geometry: distance from shoulder width (``dist_k`` = shoulder pixels x metres,
calibrated on floor marks with ``python -m greeter.robot.calibrate --distance``),
lateral position from the box centre, velocities by exponential smoothing.
No face recognition: only body keypoints and track IDs.
"""

from __future__ import annotations

import math
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

BBox = Tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels

# COCO-17 keypoint indices (Ultralytics pose models)
NOSE, LEFT_EYE, RIGHT_EYE = 0, 1, 2
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_HIP, RIGHT_HIP = 11, 12

PERSON_HEIGHT_M = 1.70  # for the full-body fallback distance estimate


@dataclass
class GreenConfig:
    hue_lo: float = 110.0  # CIELAB hue angle h_ab, degrees
    hue_hi: float = 170.0
    chroma_min: float = 20.0
    hivis_l: float = 85.0  # fluorescent yellow-green safety vests: L* > 85, C* > 70, h < 125
    hivis_c: float = 70.0
    hivis_h: float = 125.0
    min_ratio: float = 0.25  # fraction of torso pixels that must be green
    window: int = 10  # ... in at least `hits` of the last `window` frames
    hits: int = 6


@dataclass
class SceneConfig:
    green: GreenConfig = field(default_factory=GreenConfig)
    keypoint_conf: float = 0.5
    dist_k: float = 160.0  # shoulder width in px x distance in m (calibrate: 3 floor marks)
    shoulder_m: float = 0.40  # typical adult shoulder width, used to derive the focal length
    max_head_yaw_deg: float = 30.0
    max_torso_yaw_deg: float = 30.0
    frontal_shoulder_ratio: float = 0.80  # shoulder width / shoulder-to-hip length, facing straight on
    notice_max_dist: float = 5.0
    notice_max_speed: float = 0.6  # lateral (tangential) m/s: faster means walking past
    notice_min_present_s: float = 1.0  # watch someone this long before deciding they aren't passing by
    group_dist: float = 1.5
    group_speed: float = 0.4
    group_min_s: float = 1.0
    crowd_radius: float = 2.5
    crowd_people: int = 8  # more than this many people within crowd_radius ...
    crowd_groups: int = 3  # ... or this many groups: don't bid, only answer the talk spot
    spot_near: float = 0.6  # talk spot: distance band and half-width in front of the robot
    spot_far: float = 1.4
    spot_half_width: float = 0.6
    speed_tau_s: float = 0.5
    forget_after_s: float = 5.0
    inherit_iou: float = 0.4  # a new track on top of a recently lost noticed one is the same person
    inherit_window_s: float = 8.0
    max_remembered: int = 10000
    invite: str = "anyone"  # "anyone": invite whoever is near and interested; "green": only people in green


@dataclass
class Detection:
    track_id: Optional[int]
    bbox: BBox
    conf: float = 1.0
    keypoints: Optional[np.ndarray] = None  # (17, 2) pixel xy
    keypoint_conf: Optional[np.ndarray] = None  # (17,)


@dataclass
class Person:
    track_id: int
    bbox: BBox
    green_ratio: float  # this frame
    green: bool  # windowed decision
    distance: Optional[float]  # metres
    x: Optional[float]  # metres sideways from the camera axis (+ = right of the image)
    speed: float  # lateral m/s (walking past)
    velocity: Tuple[float, float]  # (vx, vz) m/s
    facing: Optional[bool]
    facing_for: float  # seconds facing continuously
    present_for: float
    at_spot: bool = False
    group: Optional[int] = None  # smallest track id of the group, None when alone
    group_size: int = 1

    def to_dict(self) -> dict:
        r = lambda v, n=2: None if v is None else round(float(v), n)  # noqa: E731
        return {
            "id": self.track_id,
            "bbox": [round(v, 1) for v in self.bbox],
            "green": self.green,
            "green_ratio": r(self.green_ratio, 3),
            "distance": r(self.distance),
            "x": r(self.x),
            "speed": r(self.speed),
            "facing": self.facing,
            "facing_for": r(self.facing_for),
            "present_for": r(self.present_for, 1),
            "at_spot": self.at_spot,
            "group": self.group,
            "group_size": self.group_size,
        }


@dataclass
class Snapshot:
    t: float
    people: List[Person]
    crowd: bool = False
    spot_occupied: bool = False  # from the head D435i depth when available, else the webcam estimate
    spot: Optional[dict] = None  # depth talk-spot details (greeter.robot.depth_spot.SpotState)
    spot_webcam: bool = False  # the webcam's own estimate, kept even when depth decides (to compare them)
    walking: Optional[bool] = None  # the robot is being walked (None: not measured)

    def get(self, track_id: int) -> Optional[Person]:
        return next((p for p in self.people if p.track_id == track_id), None)

    def to_dict(self) -> dict:
        d = {"people": [p.to_dict() for p in self.people], "crowd": self.crowd, "spot_occupied": self.spot_occupied,
             "spot_webcam": self.spot_webcam}
        if self.spot is not None:
            d["spot"] = self.spot
        if self.walking is not None:
            d["walking"] = self.walking
        return d


# --- colour --------------------------------------------------------------------
def lab_lch(bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """CIE L* (0..100), chroma C* and hue angle h (degrees 0..360) per pixel."""
    lab = cv2.cvtColor(bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)
    lightness, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360.0
    return lightness, chroma, hue


def green_mask(bgr: np.ndarray, cfg: GreenConfig) -> np.ndarray:
    lightness, chroma, hue = lab_lch(bgr)
    green = (hue >= cfg.hue_lo) & (hue <= cfg.hue_hi) & (chroma > cfg.chroma_min)
    hivis = (lightness > cfg.hivis_l) & (chroma > cfg.hivis_c) & (hue < cfg.hivis_h)
    return green & ~hivis


def green_ratio(bgr_crop: Optional[np.ndarray], cfg: GreenConfig) -> float:
    if bgr_crop is None or bgr_crop.size == 0:
        return 0.0
    mask = green_mask(bgr_crop, cfg)
    return float(np.count_nonzero(mask)) / float(mask.size)


# --- body geometry -------------------------------------------------------------
def _visible(kconf: Optional[np.ndarray], idx: Sequence[int], min_conf: float) -> bool:
    return kconf is not None and all(float(kconf[i]) >= min_conf for i in idx)


def torso_box(
    bbox: BBox,
    frame_w: int,
    frame_h: int,
    keypoints: Optional[np.ndarray] = None,
    keypoint_conf: Optional[np.ndarray] = None,
    min_conf: float = 0.5,
) -> Optional[Tuple[int, int, int, int]]:
    """Pixel box around the torso, clipped to the frame; None if degenerate.

    Shoulders to hips (inner 80 %); hips out of frame (close visitor): 1.4
    shoulder widths down from the shoulders; no shoulders: a fixed band of the box.
    """
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    if w <= 0 or h <= 0:
        return None
    box = None
    if keypoints is not None and _visible(keypoint_conf, (LEFT_SHOULDER, RIGHT_SHOULDER), min_conf):
        shoulders = keypoints[[LEFT_SHOULDER, RIGHT_SHOULDER]]
        tx1, tx2 = float(shoulders[:, 0].min()), float(shoulders[:, 0].max())
        ty1 = float(shoulders[:, 1].min())
        if tx2 - tx1 < 0.3 * w:  # side-on: shoulders overlap
            cx = (tx1 + tx2) / 2.0
            tx1, tx2 = cx - 0.15 * w, cx + 0.15 * w
        if _visible(keypoint_conf, (LEFT_HIP, RIGHT_HIP), min_conf):
            hips = keypoints[[LEFT_HIP, RIGHT_HIP]]
            tx1, tx2 = min(tx1, float(hips[:, 0].min())), max(tx2, float(hips[:, 0].max()))
            ty2 = float(hips[:, 1].max())
        else:
            ty2 = min(float(y2), ty1 + 1.4 * (tx2 - tx1))
        mx, my = 0.1 * (tx2 - tx1), 0.1 * (ty2 - ty1)
        box = (tx1 + mx, ty1 + my, tx2 - mx, ty2 - my)
    if box is None:
        band = (0.30, 0.75) if y2 >= frame_h - 2 else (0.20, 0.50)
        box = (x1 + 0.25 * w, y1 + band[0] * h, x2 - 0.25 * w, y1 + band[1] * h)
    bx1 = int(max(0, min(frame_w, round(box[0]))))
    by1 = int(max(0, min(frame_h, round(box[1]))))
    bx2 = int(max(0, min(frame_w, round(box[2]))))
    by2 = int(max(0, min(frame_h, round(box[3]))))
    if bx2 - bx1 < 4 or by2 - by1 < 4:
        return None
    return bx1, by1, bx2, by2


def head_yaw_deg(keypoints: Optional[np.ndarray], keypoint_conf: Optional[np.ndarray], min_conf: float = 0.5) -> Optional[float]:
    """Signed head yaw from the nose's offset between the eyes (0 = looking at us)."""
    if keypoints is None or not _visible(keypoint_conf, (NOSE, LEFT_EYE, RIGHT_EYE), min_conf):
        return None
    half_ipd = abs(float(keypoints[LEFT_EYE, 0] - keypoints[RIGHT_EYE, 0])) / 2.0
    if half_ipd < 1.0:
        return 90.0
    offset = float(keypoints[NOSE, 0]) - float(keypoints[LEFT_EYE, 0] + keypoints[RIGHT_EYE, 0]) / 2.0
    # the nose sits ~0.8 half-eye-distances in front of the eyes: offset/half_ipd ~= 0.8 tan(yaw)
    return math.degrees(math.atan2(offset / half_ipd, 0.8))


def torso_yaw_deg(keypoints: Optional[np.ndarray], keypoint_conf: Optional[np.ndarray], frontal_ratio: float, min_conf: float = 0.5) -> Optional[float]:
    """Angle between the shoulder line and the camera plane, from shoulder width vs torso length."""
    if keypoints is None or not _visible(keypoint_conf, (LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP), min_conf):
        return None
    width = abs(float(keypoints[LEFT_SHOULDER, 0] - keypoints[RIGHT_SHOULDER, 0]))
    shoulder_y = (keypoints[LEFT_SHOULDER, 1] + keypoints[RIGHT_SHOULDER, 1]) / 2.0
    hip_y = (keypoints[LEFT_HIP, 1] + keypoints[RIGHT_HIP, 1]) / 2.0
    length = float(hip_y - shoulder_y)
    if length <= 1.0:
        return None
    return math.degrees(math.acos(min(1.0, (width / length) / frontal_ratio)))


def is_facing(keypoints: Optional[np.ndarray], keypoint_conf: Optional[np.ndarray], cfg: SceneConfig) -> Optional[bool]:
    """Nose and both eyes visible, head yaw and shoulder line within the limits, not their back."""
    if keypoints is None or keypoint_conf is None:
        return None
    yaw = head_yaw_deg(keypoints, keypoint_conf, cfg.keypoint_conf)
    if yaw is None or abs(yaw) > cfg.max_head_yaw_deg:
        return False
    if _visible(keypoint_conf, (LEFT_SHOULDER, RIGHT_SHOULDER), cfg.keypoint_conf):
        if keypoints[LEFT_SHOULDER, 0] <= keypoints[RIGHT_SHOULDER, 0]:
            return False  # their left shoulder on the image left: we see their back
    torso = torso_yaw_deg(keypoints, keypoint_conf, cfg.frontal_shoulder_ratio, cfg.keypoint_conf)
    if torso is not None and torso > cfg.max_torso_yaw_deg:
        return False
    return True


def shoulder_px(keypoints: Optional[np.ndarray], keypoint_conf: Optional[np.ndarray], min_conf: float = 0.5) -> Optional[float]:
    if keypoints is None or not _visible(keypoint_conf, (LEFT_SHOULDER, RIGHT_SHOULDER), min_conf):
        return None
    width = float(np.hypot(*(keypoints[LEFT_SHOULDER] - keypoints[RIGHT_SHOULDER])))
    return width if width > 2.0 else None


def estimate_distance(det: Detection, frame_h: int, cfg: SceneConfig) -> Optional[float]:
    """Metres to the person: from shoulder width, else from full-body height."""
    width = shoulder_px(det.keypoints, det.keypoint_conf, cfg.keypoint_conf)
    if width is not None:
        return cfg.dist_k / width
    x1, y1, x2, y2 = det.bbox
    if y1 > 2 and y2 < frame_h - 2 and y2 - y1 > 10:  # whole body in view
        focal = cfg.dist_k / cfg.shoulder_m
        return focal * PERSON_HEIGHT_M / (y2 - y1)
    return None


def iou(a: BBox, b: BBox) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


# --- tracking state ------------------------------------------------------------
@dataclass
class _Track:
    first_seen: float
    last_seen: float
    box: BBox
    green_hist: Deque[bool]
    facing_since: Optional[float] = None
    pos: Optional[Tuple[float, float]] = None  # smoothed (x, z)
    raw: Optional[Tuple[float, float]] = None  # last measured (x, z)
    vel: Tuple[float, float] = (0.0, 0.0)
    pos_t: float = 0.0


class Scene:
    """Per-frame scene state. Call :meth:`update` with each frame's detections."""

    def __init__(self, cfg: Optional[SceneConfig] = None) -> None:
        self.cfg = cfg or SceneConfig()
        self.enabled = True  # noticing on/off (off while a conversation runs)
        self._tracks: Dict[int, _Track] = {}
        self._pairs: Dict[Tuple[int, int], float] = {}
        self._noticed: "OrderedDict[int, None]" = OrderedDict()

    # --- per-person measurements -------------------------------------------
    def _measure(self, frame: np.ndarray, det: Detection, now: float) -> Person:
        cfg = self.cfg
        frame_h, frame_w = frame.shape[:2]
        tid = int(det.track_id)
        tr = self._tracks.get(tid)
        if tr is None:
            tr = self._tracks[tid] = _Track(now, now, det.bbox, deque(maxlen=cfg.green.window))
        box = torso_box(det.bbox, frame_w, frame_h, det.keypoints, det.keypoint_conf, cfg.keypoint_conf)
        ratio = 0.0
        if box is not None:
            bx1, by1, bx2, by2 = box
            ratio = green_ratio(frame[by1:by2, bx1:bx2], cfg.green)
        tr.green_hist.append(ratio >= cfg.green.min_ratio)
        green = sum(tr.green_hist) >= cfg.green.hits

        facing = is_facing(det.keypoints, det.keypoint_conf, cfg)
        if facing is False:
            tr.facing_since = None
        elif tr.facing_since is None:
            tr.facing_since = now
        facing_for = 0.0 if tr.facing_since is None else now - tr.facing_since

        distance = estimate_distance(det, frame_h, cfg)
        x = None
        if distance is not None:
            focal = cfg.dist_k / cfg.shoulder_m
            x = ((det.bbox[0] + det.bbox[2]) / 2.0 - frame_w / 2.0) * distance / focal
            self._smooth(tr, x, distance, now)
        tr.last_seen, tr.box = now, det.bbox
        sx, sz = tr.pos if tr.pos is not None else (x, distance)
        at_spot = (
            sz is not None
            and cfg.spot_near <= sz <= cfg.spot_far
            and abs(sx) <= cfg.spot_half_width
        )
        return Person(
            track_id=tid,
            bbox=tuple(float(v) for v in det.bbox),
            green_ratio=ratio,
            green=green,
            distance=sz,
            x=sx,
            speed=abs(tr.vel[0]),
            velocity=tr.vel,
            facing=facing,
            facing_for=facing_for,
            present_for=now - tr.first_seen,
            at_spot=at_spot,
        )

    def _smooth(self, tr: _Track, x: float, z: float, now: float) -> None:
        if tr.pos is None or tr.raw is None:
            tr.pos, tr.raw, tr.pos_t = (x, z), (x, z), now
            return
        dt = now - tr.pos_t
        if dt <= 0:
            return
        alpha = 1.0 - math.exp(-dt / self.cfg.speed_tau_s)
        vx, vz = (x - tr.raw[0]) / dt, (z - tr.raw[1]) / dt  # from raw positions: converges faster
        ovx, ovz = tr.vel
        tr.vel = (ovx + alpha * (vx - ovx), ovz + alpha * (vz - ovz))
        px, pz = tr.pos
        tr.pos = (px + alpha * (x - px), pz + alpha * (z - pz))
        tr.raw, tr.pos_t = (x, z), now

    # --- groups and crowd ----------------------------------------------------
    def _groups(self, people: List[Person], now: float) -> None:
        cfg = self.cfg
        placed = [p for p in people if p.distance is not None and p.x is not None]
        seen_pairs = set()
        parent = {p.track_id: p.track_id for p in placed}

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i, a in enumerate(placed):
            for b in placed[i + 1 :]:
                key = (min(a.track_id, b.track_id), max(a.track_id, b.track_id))
                close = math.hypot(a.x - b.x, a.distance - b.distance) <= cfg.group_dist
                together = math.hypot(a.velocity[0] - b.velocity[0], a.velocity[1] - b.velocity[1]) < cfg.group_speed
                if close and together:
                    seen_pairs.add(key)
                    since = self._pairs.setdefault(key, now)
                    if now - since >= cfg.group_min_s:
                        parent[find(a.track_id)] = find(b.track_id)
        for key in list(self._pairs):
            if key not in seen_pairs:
                del self._pairs[key]
        members: Dict[int, List[int]] = {}
        for p in placed:
            members.setdefault(find(p.track_id), []).append(p.track_id)
        for p in placed:
            group = members[find(p.track_id)]
            if len(group) > 1:
                p.group, p.group_size = min(group), len(group)

    def _crowded(self, people: List[Person]) -> bool:
        cfg = self.cfg
        near = [p for p in people if p.distance is not None and p.distance <= cfg.crowd_radius]
        groups = {p.group for p in near if p.group is not None}
        return len(near) > cfg.crowd_people or len(groups) >= cfg.crowd_groups

    # --- main entry ----------------------------------------------------------
    def update(self, frame: np.ndarray, detections: Sequence[Detection], now: float) -> Snapshot:
        visible = {int(d.track_id) for d in detections if d.track_id is not None}
        new_ids = [tid for tid in visible if tid not in self._tracks]
        people = [self._measure(frame, d, now) for d in detections if d.track_id is not None]
        for tid in new_ids:  # tracker ID switch: inherit "already noticed"
            if self._inherits_notice(self._tracks[tid].box, visible, now):
                self._mark(tid)
        cutoff = max(self.cfg.forget_after_s, self.cfg.inherit_window_s)
        for tid in [t for t, tr in self._tracks.items() if now - tr.last_seen > cutoff]:
            del self._tracks[tid]
        self._groups(people, now)
        at_spot = any(p.at_spot for p in people)
        return Snapshot(
            t=now,
            people=people,
            crowd=self._crowded(people),
            spot_occupied=at_spot,
            spot_webcam=at_spot,
        )

    # --- noticing (first rung of the ladder) ---------------------------------
    def _mark(self, tid: int) -> None:
        self._noticed[tid] = None
        self._noticed.move_to_end(tid)
        while len(self._noticed) > self.cfg.max_remembered:
            self._noticed.popitem(last=False)

    def _inherits_notice(self, box: BBox, visible: set, now: float) -> bool:
        for tid in self._noticed:
            tr = self._tracks.get(tid)
            if tr is None or tid in visible or now - tr.last_seen > self.cfg.inherit_window_s:
                continue
            if iou(box, tr.box) >= self.cfg.inherit_iou:
                return True
        return False

    def was_noticed(self, track_id: int) -> bool:
        return track_id in self._noticed

    def release(self, track_id: int) -> None:
        """Forget a notice that never became an invitation (they may come closer later)."""
        self._noticed.pop(track_id, None)

    def noticeable(self, person: Person) -> bool:
        cfg = self.cfg
        return (
            (person.green or cfg.invite != "green")
            and person.distance is not None
            and person.distance <= cfg.notice_max_dist
            and person.speed < cfg.notice_max_speed
            and person.present_for >= cfg.notice_min_present_s
        )

    def notice(self, snap: Snapshot) -> Optional[Person]:
        """At most one newly noticeable person per frame (nearest first); marks them."""
        if not self.enabled or snap.crowd or snap.walking:
            return None
        ready = [p for p in snap.people if not self.was_noticed(p.track_id) and self.noticeable(p)]
        if not ready:
            return None
        best = min(ready, key=lambda p: p.distance)
        self._mark(best.track_id)
        return best
