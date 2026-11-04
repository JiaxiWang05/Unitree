"""Robot core: camera + detector + scene + robot I/O, with no networking.

By default the dialogue app attaches to it in the same process, so everything
runs on the G1's Jetson. The optional WebSocket bridge (``greeter.robot.server``)
puts the same core behind a socket.

Threads: camera capture, vision (YOLO + :class:`greeter.vision.Scene`), mic
receiver and speaker live in their own threads. Events reach the attached
consumer on the asyncio loop thread.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from greeter.robot.camera import encode_jpeg
from greeter.robot.depth_spot import CameraPose, DepthSpotDetector, SpotConfig
from greeter.robot.io_base import RGB, RobotIO
from greeter.vision import Scene, SceneConfig

log = logging.getLogger(__name__)


@dataclass
class RobotEvent:
    """``kind`` and ``data``:

    ``notice``    dict: track_id, distance, bbox, green_ratio, group_size, frame_size, jpeg (bytes)
    ``tracks``    dict: people (list of Person dicts), crowd, spot_occupied, spot_webcam, walking (about 5 Hz)
    ``playback``  "playing" or "idle"
    ``mic``       16 kHz mono s16le bytes (only while mic streaming is on)
    ``video``     JPEG bytes, every ``frame_interval_s`` (only while video streaming is on)
    ``status``    dict: robot health, e.g. battery (every 10 s)
    ``hello``     dict about the robot, sent when a consumer attaches
    """

    kind: str
    data: Any = None


Sink = Callable[[RobotEvent], None]


class RobotCore:
    def __init__(
        self,
        io: RobotIO,
        camera,
        detector,
        scene_cfg: Optional[SceneConfig] = None,
        mock: bool = False,
        gate_mic: bool = True,
        gate_tail_s: float = 0.35,
        frame_interval_s: float = 0.5,
        tracks_interval_s: float = 0.2,
        status_interval_s: float = 10.0,
        max_detect_fps: float = 15.0,
        depth=None,
        spot_cfg: Optional[SpotConfig] = None,
        depth_pose: Optional[CameraPose] = None,
    ) -> None:
        self.io, self.camera, self.detector = io, camera, detector
        self.scene = Scene(scene_cfg)
        # optional head D435i talk-spot detector: standalone, no matching to webcam tracks
        self.depth = depth
        self.spot_detector: Optional[DepthSpotDetector] = None
        self.spot_state = None
        if depth is not None:
            sc = self.scene.cfg
            spot_cfg = spot_cfg or SpotConfig(near=sc.spot_near, far=sc.spot_far, half_width=sc.spot_half_width)
            self.spot_detector = DepthSpotDetector(depth.intrinsics, spot_cfg, depth_pose)
        self.scene.enabled = False  # until a consumer attaches
        self.mock = mock
        self.gate_mic, self.gate_tail_s = gate_mic, gate_tail_s
        self.frame_interval_s = frame_interval_s
        self.tracks_interval_s = tracks_interval_s
        self.status_interval_s = status_interval_s
        self.detect_period = 1.0 / max_detect_fps

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._sink: Optional[Sink] = None
        self._consumer_triggers = True
        self.mic_enabled = False
        self.video_enabled = False
        self._stop = threading.Event()

    # --- consumer ----------------------------------------------------------
    def attach(self, sink: Sink) -> None:
        """Route events to ``sink`` (called on the loop thread). Replaces any previous consumer."""
        self._sink = sink
        self._consumer_triggers = True
        self._refresh()
        sink(RobotEvent("hello", {"robot": "g1", "mock": self.mock}))

    def detach(self, sink: Optional[Sink] = None) -> None:
        if sink is not None and self._sink is not sink:
            return  # already replaced by a newer consumer
        self._sink = None
        self.mic_enabled = self.video_enabled = False
        self._refresh()
        self.io.stop_playback()

    def deliver(self, event: RobotEvent) -> None:
        if self._sink is not None:
            self._sink(event)

    def _deliver_threadsafe(self, event: RobotEvent) -> None:
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self.deliver, event)

    def _refresh(self) -> None:
        self.scene.enabled = self._sink is not None and self._consumer_triggers

    # --- commands (call from the loop thread) --------------------------------
    def set_triggers(self, enabled: bool) -> None:
        self._consumer_triggers = bool(enabled)
        self._refresh()

    def release(self, track_id: int) -> None:
        self.scene.release(track_id)

    def set_stream(self, mic: Optional[bool] = None, video: Optional[bool] = None) -> None:
        changed = (mic is not None and bool(mic) != self.mic_enabled) or (video is not None and bool(video) != self.video_enabled)
        if mic is not None:
            self.mic_enabled = bool(mic)
        if video is not None:
            self.video_enabled = bool(video)
        if changed:
            log.info("streaming mic=%s video=%s", self.mic_enabled, self.video_enabled)

    def play(self, pcm: bytes) -> None:
        self.io.play(pcm)

    def stop_audio(self) -> None:
        self.io.stop_playback()

    def led(self, rgb: RGB) -> None:
        self.io.led(rgb)

    # --- mic -----------------------------------------------------------------
    def _on_mic_threadsafe(self, pcm: bytes) -> None:
        if self.loop is not None and self.mic_enabled:
            self.loop.call_soon_threadsafe(self._on_mic, pcm)

    def _on_mic(self, pcm: bytes) -> None:
        if not self.mic_enabled:
            return
        if self.gate_mic and time.monotonic() < self.io.playing_until() + self.gate_tail_s:
            return  # half duplex: don't send the robot's own voice back to the model
        self.deliver(RobotEvent("mic", pcm))

    # --- vision thread -------------------------------------------------------
    def _vision_loop(self) -> None:
        last_seq, last_tracks = -1, 0.0
        while not self._stop.is_set():
            t0 = time.monotonic()
            seq, frame = self.camera.latest()
            if frame is None or seq == last_seq:
                time.sleep(0.005)
                continue
            last_seq = seq
            try:
                detections = self.detector.detect(frame)
            except Exception:
                log.exception("detector failed")
                time.sleep(0.5)
                continue
            now = time.monotonic()
            snap = self.scene.update(frame, detections, now)
            if self.spot_detector is not None:
                spot = self.spot_state
                if spot is not None and now - spot.t < 5.0:  # ride out short stalls on the last reading
                    snap.spot_occupied, snap.spot = spot.occupied, spot.to_dict()
                else:  # depth gone for a while: fall back to the webcam's own estimate
                    snap.spot = {"source": "depth", "stale": True}
            snap.walking = self.io.walking()
            person = self.scene.notice(snap)
            if person is not None:
                log.info(
                    "NOTICED track %d: green %.0f%%, %.1f m, %s",
                    person.track_id, 100 * person.green_ratio, person.distance,
                    "group of %d" % person.group_size if person.group_size > 1 else "alone",
                )
                self._deliver_threadsafe(
                    RobotEvent(
                        "notice",
                        {
                            "track_id": person.track_id,
                            "bbox": [round(v, 1) for v in person.bbox],
                            "distance": round(person.distance, 2),
                            "green_ratio": round(person.green_ratio, 3),
                            "group_size": person.group_size,
                            "frame_size": [frame.shape[1], frame.shape[0]],
                            "jpeg": encode_jpeg(frame),
                        },
                    )
                )
            if now - last_tracks >= self.tracks_interval_s:
                last_tracks = now
                self._deliver_threadsafe(RobotEvent("tracks", snap.to_dict()))
            time.sleep(max(0.0, self.detect_period - (time.monotonic() - t0)))

    def _depth_loop(self) -> None:
        last_seq, was = -1, (False, False)
        while not self._stop.is_set():
            seq, depth = self.depth.latest()
            if depth is None or seq == last_seq:
                time.sleep(0.005)
                continue
            last_seq = seq
            try:
                state = self.spot_detector.update(depth, time.monotonic())
            except Exception:
                log.exception("depth talk-spot detector failed")
                time.sleep(0.5)
                continue
            self.spot_state = state
            now_is = (state.occupied, state.static)
            if now_is != was:
                if state.static and not was[1]:
                    log.info("talk spot: something static (%d points) - treated as an object, not a visitor", state.points)
                elif state.occupied:
                    log.info("talk spot OCCUPIED (depth: %d points, %d at thigh height, %.1f m ahead)", state.points, state.tall, state.x or 0)
                elif was[0]:
                    log.info("talk spot free (depth)")
                was = now_is

    # --- periodic tasks ------------------------------------------------------
    async def _frame_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(self.frame_interval_s)
            if self._sink is None or not self.video_enabled:
                continue
            _, frame = self.camera.latest()
            if frame is None:
                continue
            jpeg = await loop.run_in_executor(None, encode_jpeg, frame)
            self.deliver(RobotEvent("video", jpeg))

    async def _playback_loop(self) -> None:
        playing = False
        while True:
            await asyncio.sleep(0.1)
            now_playing = self.io.playing_until() > time.monotonic()
            if now_playing != playing:
                playing = now_playing
                self.deliver(RobotEvent("playback", "playing" if playing else "idle"))

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(self.status_interval_s)
            status = self.io.status()
            if status:
                log.info("robot status: %s", status)
                self.deliver(RobotEvent("status", status))

    async def run(self, stop: Optional[asyncio.Event] = None) -> None:
        """Start the hardware and run until ``stop`` is set (or forever)."""
        self.loop = asyncio.get_running_loop()
        self.io.start(self._on_mic_threadsafe)
        vision = threading.Thread(target=self._vision_loop, name="vision", daemon=True)
        vision.start()
        depth_thread = None
        if self.spot_detector is not None:
            depth_thread = threading.Thread(target=self._depth_loop, name="depth-spot", daemon=True)
            depth_thread.start()
        tasks = [asyncio.ensure_future(c) for c in (self._frame_loop(), self._playback_loop(), self._status_loop())]
        try:
            if stop is None:
                await asyncio.Future()
            else:
                await stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            self._stop.set()
            vision.join(timeout=2.0)
            if depth_thread is not None:
                depth_thread.join(timeout=2.0)
                self.depth.stop()
            self.io.close()
            self.camera.stop()
