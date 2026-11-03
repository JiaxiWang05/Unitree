"""Front USB UVC camera capture on a background thread (latest frame only, never saved)."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Optional, Tuple, Union

import cv2
import numpy as np

log = logging.getLogger(__name__)

Source = Union[int, str]


SKIP_CAMERAS = ("realsense", "intel")  # the G1's head D435i exposes several video nodes

# V4L2 control names changed between kernels (newer name first, JetPack 5's kernel 5.10 name
# second). Every name in a group is tried; a camera without the control just ignores it.
BEFORE_SETTLE = (
    ("power_line_frequency=1",),  # 50 Hz mains (UK): no flicker bands under hall lighting
    ("exposure_dynamic_framerate=0", "exposure_auto_priority=0"),  # keep 30 fps in dim light
)
LOCKED = (
    ("white_balance_automatic=0", "white_balance_temperature_auto=0"),
    ("auto_exposure=1", "exposure_auto=1"),  # 1 = manual
    ("focus_automatic_continuous=0", "focus_auto=0"),  # no focus hunting as people walk past
)


def set_v4l2_controls(device: str, groups) -> None:
    """Best effort: set each control with v4l2-ctl, trying every name in a group."""
    import shutil
    import subprocess

    if not shutil.which("v4l2-ctl"):
        log.warning("v4l2-ctl not found (apt install v4l-utils): camera controls left on auto")
        return
    for names in groups:
        for ctrl in names:
            subprocess.run(["v4l2-ctl", "-d", device, "-c", ctrl], capture_output=True)


def find_usb_camera(by_id: str = "/dev/v4l/by-id") -> Optional[str]:
    """First UVC camera under /dev/v4l/by-id that is not the RealSense (Linux only)."""
    try:
        names = sorted(os.listdir(by_id))
    except OSError:
        return None
    for name in names:
        if name.endswith("-video-index0") and not any(s in name.lower() for s in SKIP_CAMERAS):
            return os.path.join(by_id, name)
    return None


def parse_source(source: str) -> Source:
    """``"auto"`` -> the front USB camera on Linux, webcam 0 elsewhere; ``"0"`` -> index 0;
    anything else (``/dev/video2``, a ``/dev/v4l/by-id`` path, a video file) as is."""
    if source == "auto":
        if sys.platform.startswith("linux"):
            found = find_usb_camera()
            if found is None:
                raise RuntimeError("no USB camera found under /dev/v4l/by-id (is it plugged into the Jetson?)")
            return found
        return 0
    return int(source) if source.isdigit() else source


class Camera:
    """Keeps only the most recent frame in memory; older frames are dropped.

    ``source`` may be a camera index, a V4L2 device path or a video file. Video
    files are paced at their own frame rate and looped, which makes them handy
    for repeatable tests of the whole pipeline.
    """

    def __init__(self, source: Source = 0, width: int = 640, height: int = 480, fps: int = 30, lock_exposure: bool = False) -> None:
        self.source = source
        self.lock_exposure = lock_exposure
        self.width, self.height, self.fps = width, height, fps
        self._is_file = isinstance(source, str) and not source.startswith("/dev/")
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._seq = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None

    def _open(self) -> cv2.VideoCapture:
        if self._is_file:
            cap = cv2.VideoCapture(self.source)
        elif sys.platform.startswith("linux"):
            cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
            # MJPG lets most UVC webcams deliver 30 fps over USB 2
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        else:
            cap = cv2.VideoCapture(self.source)
        if not self._is_file:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            raise RuntimeError(
                "cannot open camera %r (on macOS, allow camera access for your terminal "
                "in System Settings > Privacy & Security > Camera)" % (self.source,)
            )
        return cap

    def start(self) -> "Camera":
        self._cap = self._open()
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("camera %r opened but returned no frame" % (self.source,))
        self._publish(frame)
        log.info("camera %r: %dx%d", self.source, frame.shape[1], frame.shape[0])
        if self.lock_exposure and not self._is_file:
            self._lock_auto_controls()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()
        return self

    def _lock_auto_controls(self, settle_s: float = 2.0) -> None:
        """Let auto exposure, white balance and focus settle, then freeze them so colours stay stable.

        Before settling: 50 Hz anti-flicker, and auto exposure may not lower the frame rate.
        """
        assert self._cap is not None
        device = self.source if isinstance(self.source, str) and self.source.startswith("/dev/") else None
        if device:
            set_v4l2_controls(device, BEFORE_SETTLE)
        end = time.monotonic() + settle_s
        while time.monotonic() < end:
            self._cap.read()
        self._cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1 if sys.platform.startswith("linux") else 0.25)  # V4L2: 1 = manual
        self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        if device:
            set_v4l2_controls(device, LOCKED)
        log.info("camera white balance, exposure and focus locked (50 Hz, fixed frame rate)")

    def _publish(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame
            self._seq += 1

    def _run(self) -> None:
        assert self._cap is not None
        file_period = 1.0 / (self._cap.get(cv2.CAP_PROP_FPS) or self.fps) if self._is_file else 0.0
        next_t = time.monotonic()
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                if self._is_file:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                log.warning("camera read failed; retrying")
                time.sleep(0.2)
                continue
            self._publish(frame)
            if file_period:
                next_t += file_period
                time.sleep(max(0.0, next_t - time.monotonic()))

    def latest(self) -> Tuple[int, Optional[np.ndarray]]:
        """(sequence number, frame). The sequence number grows with every new frame."""
        with self._lock:
            return self._seq, self._frame

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()


def encode_jpeg(frame: np.ndarray, max_side: int = 768, quality: int = 75) -> bytes:
    """Downscale so the long side is at most ``max_side`` and JPEG-encode in memory."""
    h, w = frame.shape[:2]
    scale = max_side / float(max(h, w))
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()
