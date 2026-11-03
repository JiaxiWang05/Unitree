"""Whole loop with mock robot I/O and the scripted backend.

* default all-on-Jetson path: RobotCore and GreeterApp in one event loop (InProcessLink);
* optional laptop split: BridgeServer in a thread + WebSocketLink over a real socket.

Camera and detector are faked (a green visitor 1.6 m away, facing the robot) so
no webcam, YOLO weights or API key are needed.
"""

import asyncio
import json
import threading
import time

import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from greeter.backends.scripted import ScriptedBackend
from greeter.dialogue.app import GreeterApp, SpotEars, led_colour
from greeter.dialogue.links import InProcessLink, WebSocketLink
from greeter.dialogue.machine import DialogueConfig
from greeter.recorder import Recorder
from greeter.robot.core import RobotCore
from greeter.robot.mock_io import MockRobotIO
from greeter.robot.server import BridgeServer
from greeter.vision import LEFT_EYE, LEFT_HIP, LEFT_SHOULDER, NOSE, RIGHT_EYE, RIGHT_HIP, RIGHT_SHOULDER, Detection

W = 100.0  # shoulder width in px -> 160 / 100 = 1.6 m: inside the 1.2-2.2 m bid range
CHIME = int(0.35 * 16000) * 2  # one scripted chime note at 16 kHz
CFG = DialogueConfig(silence_s=1.0, cooldown_s=0.5, close_timeout_s=4.0)


def keypoints(cx=320.0, top=60.0):
    k = np.zeros((17, 2))
    k[NOSE] = (cx, top + 30)
    k[LEFT_EYE], k[RIGHT_EYE] = (cx + 12, top + 20), (cx - 12, top + 20)
    k[LEFT_SHOULDER], k[RIGHT_SHOULDER] = (cx + W / 2, top + 80), (cx - W / 2, top + 80)
    k[LEFT_HIP], k[RIGHT_HIP] = (cx + 0.4 * W, top + 80 + 1.25 * W), (cx - 0.4 * W, top + 80 + 1.25 * W)
    return k, np.full(17, 0.9)


def green_scene():
    frame = np.full((480, 640, 3), 90, dtype=np.uint8)
    frame[140:265, 270:370] = (40, 180, 40)  # green top between shoulders and hips
    return frame


class FakeCamera:
    def __init__(self, frame):
        self.frame, self.seq = frame, 0

    def latest(self):
        self.seq += 1
        return self.seq, self.frame

    def stop(self):
        pass


class FakeDetector:
    def __init__(self):
        self.present = True

    def detect(self, frame):
        time.sleep(0.02)
        if not self.present:
            return []
        k, c = keypoints()
        return [Detection(1, (250.0, 60.0, 390.0, 479.0), 0.9, k, c)]


def make_core():
    io = MockRobotIO(speaker=False, mic=False)
    detector = FakeDetector()
    return RobotCore(io, FakeCamera(green_scene()), detector, mock=True), io, detector


async def wait_until(cond, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        await asyncio.sleep(0.05)
    return False


def states(app):
    return [(a, b) for a, b, _ in app.dialogue.transitions]


FULL_VISIT = [
    ("idle", "idle"),
    ("idle", "noticed"),
    ("noticed", "bid"),
    ("bid", "open"),
    ("open", "converse"),
    ("converse", "close"),
    ("close", "cooldown"),
    ("cooldown", "idle"),
]


def make_app(link, recorder=None, cfg=CFG):
    backends = []

    def make():
        backends.append(ScriptedBackend())
        return backends[-1]

    return GreeterApp(link, [("scripted", make)], cfg, transcripts=False, recorder=recorder), backends


def run_in_process(core, scenario, recorder=None, cfg=CFG):
    async def main():
        stop = asyncio.Event()
        app, backends = make_app(InProcessLink(core), recorder, cfg)
        core_task = asyncio.ensure_future(core.run(stop))
        app_task = asyncio.ensure_future(app.run())
        try:
            await scenario(app)
        finally:
            await app.stop()
            await asyncio.wait_for(app_task, 5)
            stop.set()
            await asyncio.wait_for(core_task, 5)
        return app, backends

    return asyncio.run(main())


class BackgroundBridge:
    """The optional bridge in its own thread and event loop, like a separate machine."""

    def __init__(self, server):
        self.server = server
        self._loop = self._stop = None
        self._thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True)

    async def _main(self):
        self._loop, self._stop = asyncio.get_running_loop(), asyncio.Event()
        await self.server.run(self._stop)

    def start(self):
        self._thread.start()
        assert self.server.ready.wait(10)
        return "ws://127.0.0.1:%d" % self.server.port

    def stop(self):
        self._loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(5)


def test_full_ladder_in_one_process(tmp_path):
    core, io, _ = make_core()

    async def scenario(app):
        assert await wait_until(lambda: ("cooldown", "idle") in states(app), 25)
        await asyncio.sleep(1.5)  # same visitor still there, still green

    app, backends = run_in_process(core, scenario, Recorder(tmp_path))
    assert states(app)[: len(FULL_VISIT)] == FULL_VISIT
    assert ("open", "converse", "kept facing") in app.dialogue.transitions
    assert app.stats["notices"] == 1  # never re-invited
    assert len(backends) == 1 and backends[0].committed == ["Hey, green top! Come and stand on the green spot and say hi?"]
    # opener (2 notes) + hello after keeping facing (1 note) + takeaway (2 notes), 24 -> 16 kHz
    assert len(io.played) == pytest.approx(5 * CHIME, abs=300)
    assert backends[0].frames >= 1 and backends[0].audio_bytes > 0
    assert (0, 255, 0) in io.leds and any(r == g == b for r, g, b in io.leds)  # listening green, idle white
    # recordings for tuning
    day = next(tmp_path.iterdir())
    visit = next(d for d in day.iterdir() if d.is_dir())
    assert {"mic.wav", "robot.wav", "events.jsonl"} <= {f.name for f in visit.iterdir()}
    assert any(f.name.endswith("notice.jpg") for f in visit.iterdir())
    events = [json.loads(line) for line in (visit / "events.jsonl").read_text().splitlines()]
    assert any(e["kind"] == "robot" for e in events)
    assert (day / "trace.jsonl").stat().st_size > 0


def test_visitor_walks_away_mid_conversation():
    core, io, detector = make_core()

    async def scenario(app):
        assert await wait_until(lambda: ("open", "converse") in states(app), 15)
        detector.present = False
        assert await wait_until(lambda: ("close", "cooldown") in states(app), 10)

    app, _ = run_in_process(core, scenario, cfg=DialogueConfig(silence_s=0, cooldown_s=0.5))
    assert ("converse", "close", "nobody there") in app.dialogue.transitions
    assert len(io.played) == pytest.approx(3 * CHIME, abs=300)  # no goodbye to an empty room


def test_apology_clip_plays_out_after_a_session_error():
    core, io, _ = make_core()

    async def scenario(app):
        app.clips["brain_offline"] = b"\x00\x01" * 32000  # 2 s at 16 kHz
        assert await wait_until(lambda: ("open", "converse") in states(app), 15)
        app.backend._emit("error", "connection closed")
        assert await wait_until(lambda: ("converse", "cooldown") in states(app), 5)
        assert io.playing_until() > time.monotonic() + 1.0  # still playing, not cut off
        assert await wait_until(lambda: ("cooldown", "idle") in states(app), 10)

    run_in_process(core, scenario, cfg=DialogueConfig(silence_s=0, cooldown_s=0.5))


def test_optional_split_over_websocket():
    core, io, _ = make_core()
    bridge = BackgroundBridge(BridgeServer(core, "127.0.0.1", 0))
    url = bridge.start()

    async def main():
        app, backends = make_app(WebSocketLink(url))
        task = asyncio.ensure_future(app.run())
        try:
            assert await wait_until(lambda: ("cooldown", "idle") in states(app), 25)
        finally:
            await app.stop()
            await asyncio.wait_for(task, 5)
        return app, backends

    try:
        app, backends = asyncio.run(main())
    finally:
        bridge.stop()
    assert states(app)[: len(FULL_VISIT)] == FULL_VISIT
    assert len(io.played) == pytest.approx(5 * CHIME, abs=300)
    assert backends[0].frames >= 1 and backends[0].audio_bytes > 0


def test_bridge_rejects_wrong_token():
    core, _, _ = make_core()
    bridge = BackgroundBridge(BridgeServer(core, "127.0.0.1", 0, token="s3cret"))
    url = bridge.start()

    async def probe(u):
        async with connect(u) as ws:
            try:
                return await asyncio.wait_for(ws.recv(), 2)
            except ConnectionClosed as exc:
                return exc.rcvd.code

    try:
        assert asyncio.run(probe(url)) == 4001
        assert '"type":"hello"' in asyncio.run(probe(url + "/?token=s3cret"))
    finally:
        bridge.stop()


def test_led_updates_are_rate_limited():
    io = MockRobotIO(speaker=False, mic=False)
    try:
        for i in range(20):
            io.led((i, 0, 0))
            time.sleep(0.01)
        time.sleep(0.5)
        assert io.leds[-1] == (19, 0, 0)  # the latest colour always lands
        assert len(io.leds) <= 3
    finally:
        io.close()


def test_led_colours():
    assert led_colour("listening", 0) == (0, 255, 0)
    assert led_colour("thinking", 0) == (255, 140, 0)
    dim, bright = led_colour("idle", 0.0), led_colour("idle", 2.0)
    assert dim[0] == dim[1] == dim[2] and bright[0] > dim[0]  # white breathing


def test_spot_ears_hear_speech_over_hall_noise():
    rng = np.random.default_rng(0)
    ears = SpotEars()
    noise = lambda amp: (rng.normal(0, amp, 800)).astype("<i2").tobytes()  # noqa: E731
    assert not any(ears.feed(noise(300)) for _ in range(100))  # 5 s of steady hall noise
    assert any(ears.feed(noise(3000)) for _ in range(10))  # someone speaks into the robot
    loud_hall = SpotEars()
    assert not any(loud_hall.feed(noise(1500)) for _ in range(200))  # a loud but steady hall is learned
