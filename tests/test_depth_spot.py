"""Talk spot from the G1's built-in head D435i: detector on rendered depth, ladder hook, end to end."""

import asyncio
import time

import numpy as np
import pytest

from greeter import cli
from greeter.backends.scripted import ScriptedBackend
from greeter.dialogue.app import GreeterApp
from greeter.dialogue.links import InProcessLink
from greeter.dialogue.machine import DialogueConfig
from greeter.robot.core import RobotCore
from greeter.robot.depth_source import Body, SyntheticDepth, scenario_visit, scenario_walkby
from greeter.robot.depth_spot import CameraPose, DepthSpotDetector, SpotConfig, ground_points
from greeter.robot.mock_io import MockRobotIO

FPS = 15.0


def run(bodies_at, t0, t1, det=None, cam=None, **cam_kw):
    """Feed rendered frames from t0 to t1 s; ``bodies_at(t)`` -> bodies. Returns (detector, [(t, state)])."""
    cam = cam or SyntheticDepth(bodies_at, **cam_kw)
    det = det or DepthSpotDetector(cam.intrinsics)
    out, t = [], t0
    while t <= t1 + 1e-9:
        out.append((t, det.update(cam.render(t), t)))
        t += 1.0 / FPS
    return det, out


def occupied_times(states):
    return [t for t, s in states if s.occupied]


def standing(x=1.0, y=0.0, **kw):
    return lambda t: [Body(x, y + 0.015 * np.sin(2 * np.pi * 0.3 * t), **kw)]


# --- geometry -----------------------------------------------------------------------


def test_floor_lies_at_zero_height():
    cam = SyntheticDepth(lambda t: [], noise=False)
    fwd, left, up, valid = ground_points(cam.render(0.0), cam.intrinsics, CameraPose(), 1)
    assert valid > 0.95
    assert np.abs(up).max() < 0.01  # every pixel sees the floor at the URDF pose
    assert 0.30 < fwd.min() < 0.40 and 3.6 < fwd.max() < 4.0  # ~0.30-3.74 m from the camera, +5.4 cm to the pelvis


@pytest.mark.parametrize("pitch, height", [(49.6, 1.21), (44.0, 1.30), (47.6, 1.258)])
def test_floor_fit_recovers_lean_and_height(pitch, height):
    cam = SyntheticDepth(standing(), pose=CameraPose(pitch, height))
    det = DepthSpotDetector(cam.intrinsics)  # starts from the URDF pose
    state = det.update(cam.render(0.0), 0.0)
    assert state.floor_pitch_deg == pytest.approx(pitch, abs=0.2)
    assert state.floor_height_m == pytest.approx(height, abs=0.01)
    assert state.raw  # the visitor on the spot during the fit doesn't spoil it


# --- occupancy ------------------------------------------------------------------------


def test_empty_floor_is_free():
    _, states = run(lambda t: [], 0.0, 3.0)
    assert occupied_times(states) == [] and all(s.points == 0 for _, s in states)


def test_visitor_counts_after_1_5_s_dwell():
    _, states = run(standing(), 0.0, 3.0)
    first = occupied_times(states)[0]
    assert 1.45 <= first <= 1.7
    assert all(s.raw for _, s in states)


@pytest.mark.parametrize("x, y", [(0.65, 0.0), (1.35, 0.0), (1.35, 0.5), (1.0, -0.5)])
def test_anywhere_on_the_spot(x, y):
    _, states = run(standing(x, y), 0.0, 2.5)
    assert occupied_times(states)


@pytest.mark.parametrize("x, y", [(2.0, 0.0), (0.3, 0.0), (1.0, 0.9), (1.0, -0.9)])
def test_outside_the_spot_is_ignored(x, y):
    _, states = run(standing(x, y), 0.0, 2.5)
    assert occupied_times(states) == []


def test_people_walking_across_dont_count():
    _, states = run(scenario_walkby, 0.0, 12.0)
    assert occupied_times(states) == []
    assert any(s.raw for _, s in states)  # they were seen, just not for long or slowly enough


def test_bag_on_the_spot_is_not_a_visitor():
    bag = lambda t: [Body(1.0, 0.0, kind="box", height=0.4, width=0.35, depth=0.25)]  # noqa: E731
    _, states = run(bag, 0.0, 3.0)
    assert occupied_times(states) == [] and max(s.points for _, s in states) > 500
    assert all(s.tall == 0 for _, s in states)


def test_release_after_leaving():
    leave_at = 3.0
    _, states = run(lambda t: standing()(t) if t < leave_at else [], 0.0, 4.5)
    free = [t for t, s in states if t > leave_at and not s.occupied]
    assert free and leave_at + 0.6 <= free[0] <= leave_at + 0.9  # 0.7 s release delay


def test_still_object_is_absorbed_but_swaying_person_is_not():
    cfg = SpotConfig(static_s=4.0)
    sign = lambda t: [Body(1.0, 0.0, kind="box", height=1.0, width=0.4, depth=0.3)]  # noqa: E731
    cam = SyntheticDepth(sign)
    _, states = run(sign, 0.0, 6.0, det=DepthSpotDetector(cam.intrinsics, cfg), cam=cam)
    assert occupied_times(states) and not states[-1][1].occupied and states[-1][1].static
    cam = SyntheticDepth(standing())
    _, states = run(standing(), 0.0, 6.0, det=DepthSpotDetector(cam.intrinsics, cfg), cam=cam)
    assert states[-1][1].occupied and not states[-1][1].static


def test_full_resolution_stream_behaves_the_same():
    _, states = run(standing(), 0.0, 2.0, width=848, height=480)
    assert occupied_times(states)


def test_visit_scenario_timeline():
    """Matches scripts/make_test_clip.py: on the spot 7-16 s; a passer-by crosses at 19-21.5 s."""
    _, states = run(scenario_visit, 0.0, 24.0)
    times = occupied_times(states)
    assert 7.5 <= times[0] <= 9.0 and 16.0 <= times[-1] <= 17.0
    assert not any(18.0 <= t <= 24.0 for t in times)


# --- ladder hook --------------------------------------------------------------------

PERSON = {"id": 3, "bbox": [250, 100, 390, 400], "distance": 1.8, "facing_for": 0.0, "at_spot": False, "present_for": 5}
NOTICE = {"track_id": 3, "bbox": [250, 100, 390, 400], "distance": 2.0, "group_size": 1}


def depth_snap(people, occupied, stale=False):
    spot = {"source": "depth", "stale": True} if stale else {"source": "depth", "occupied": occupied}
    return {"people": people, "spot_occupied": occupied, "spot": spot}


def to_open(d, bid_audio_s=0.5, t0=1.0):
    """Notice -> bid (opener ready) -> open, with the depth spot empty throughout."""
    from greeter.dialogue.machine import State

    d.start(0.0)
    d.on_notice(NOTICE, b"j", t0)
    d.on_opener_ready(t0)
    d.on_tracks(depth_snap([dict(PERSON, facing_for=2.0)], False), t0 + 0.1)
    d.tick(t0 + 0.1)
    d.on_bot_audio(bid_audio_s, t0 + 0.2)
    t = t0 + 0.3
    while d.state is not State.OPEN and t < t0 + 10:
        d.on_tracks(depth_snap([PERSON], False), t)
        d.tick(t)
        t += 0.1
    assert d.state is State.OPEN
    return t


def test_spot_filling_during_open_accepts_the_invitation():
    from greeter.dialogue.machine import Dialogue, State

    d = Dialogue()
    t = to_open(d)
    d.on_tracks(depth_snap([PERSON], True), t)
    d.tick(t)
    assert d.state is State.CONVERSE and ("open", "converse", "stepped onto the spot") in d.transitions


def test_stepping_on_early_in_a_long_invitation_still_counts():
    """Spot fills 2 s into a 5.5 s invitation; OPEN starts after it: still an acceptance."""
    from greeter.dialogue.machine import Dialogue, State

    d = Dialogue(DialogueConfig(open_facing_s=60))
    d.start(0.0)
    d.on_notice(NOTICE, b"j", 1.0)
    d.on_opener_ready(1.0)
    d.on_tracks(depth_snap([dict(PERSON, facing_for=2.0)], False), 1.1)
    d.tick(1.1)  # BID at 1.1
    d.on_bot_audio(5.5, 1.2)
    t = 1.2
    while d.state is State.BID:
        d.on_tracks(depth_snap([PERSON], t >= 3.1), t)  # depth says occupied from 3.1 s
        d.tick(t)
        t += 0.1
    d.on_tracks(depth_snap([PERSON], True), t)
    d.tick(t)
    assert d.state is State.CONVERSE and ("open", "converse", "stepped onto the spot") in d.transitions


def test_depth_stall_flip_is_not_an_acceptance():
    from greeter.dialogue.machine import Dialogue, State

    d = Dialogue(DialogueConfig(open_facing_s=60))
    d.start(0.0)
    d.on_tracks(depth_snap([], True), 0.5)  # someone has been on the spot all along
    d.on_notice(NOTICE, b"j", 1.0)
    d.on_opener_ready(1.0)
    d.on_tracks(depth_snap([dict(PERSON, facing_for=2.0)], True), 1.1)
    d.tick(1.1)
    d.on_bot_audio(0.3, 1.2)
    for t in np.arange(1.3, 2.5, 0.1):
        d.on_tracks(depth_snap([PERSON], True), t)
        d.tick(t)
    assert d.state is State.OPEN
    d.on_tracks(depth_snap([PERSON], False, stale=True), 2.6)  # depth stalls: webcam says nobody there
    d.on_tracks(depth_snap([PERSON], True), 2.7)  # depth is back
    for t in np.arange(2.8, 3.5, 0.1):
        d.on_tracks(depth_snap([PERSON], True), t)
        d.tick(t)
    assert d.state is not State.CONVERSE


def test_talk_spot_chat_seen_only_by_depth_stays_open():
    from greeter.dialogue.machine import Dialogue, State

    d = Dialogue(DialogueConfig(silence_s=0))
    d.start(0.0)
    d.on_tracks(depth_snap([], True), 0.5)  # a child the webcam doesn't place on the spot
    assert d.on_spot_speech(1.0) and d.state is State.CONVERSE and d.target_id is None
    for t in np.arange(1.1, 20.0, 0.5):
        d.on_tracks(depth_snap([], True), t)
        d.tick(t)
    assert d.state is State.CONVERSE
    for t in np.arange(20.0, 25.0, 0.5):
        d.on_tracks(depth_snap([], False), t)
        d.tick(t)
    assert d.state in (State.COOLDOWN, State.IDLE)


def test_visitor_lingering_after_goodbye_cannot_restart_at_once():
    from greeter.dialogue.machine import Dialogue, State

    d = Dialogue()
    d.start(0.0)
    d.on_tracks(depth_snap([], True), 0.5)
    d.on_spot_speech(1.0)
    d.on_user_text("ok bye!", 5.0)
    assert d.state is State.CLOSE
    d.on_turn_complete(5.5)
    for t in np.arange(5.6, 15.0, 0.2):
        d.on_tracks(depth_snap([], True), t)
        d.tick(t)
    assert d.state is State.IDLE
    assert d.on_spot_speech(15.0) == []  # same person, never left the spot
    d.on_tracks(depth_snap([], False), 16.0)
    d.on_tracks(depth_snap([], True), 20.0)  # someone (new) steps on
    assert d.on_spot_speech(21.0) and d.state is State.CONVERSE


def test_someone_already_on_the_spot_is_not_an_acceptance():
    from greeter.dialogue.machine import Dialogue, State

    d = Dialogue(DialogueConfig(open_facing_s=60))
    d.start(0.0)
    d.on_tracks({"people": [], "spot_occupied": True}, 0.5)  # a previous visitor lingering on the spot
    d.on_notice({"track_id": 3, "bbox": [250, 100, 390, 400], "distance": 2.0, "group_size": 1}, b"j", 1.0)
    person = {"id": 3, "bbox": [250, 100, 390, 400], "distance": 1.8, "facing_for": 2.0, "at_spot": False, "present_for": 9}
    d.on_opener_ready(9.0)
    for t in np.arange(9.0, 13.0, 0.1):
        d.on_tracks({"people": [person], "spot_occupied": True}, t)
        if d.state.value == "bid" and t > 9.1:
            d.on_bot_audio(0.2, t)
        d.tick(t)
    assert d.state is not State.CONVERSE


# --- end to end ---------------------------------------------------------------------


def test_stepping_onto_the_spot_opens_the_conversation_end_to_end():
    """Webcam sees a green visitor at 1.6 m; only the depth spot can open (facing would take 60 s)."""
    from tests.test_e2e import FakeCamera, FakeDetector, green_scene, states, wait_until

    bodies = []
    depth = SyntheticDepth(lambda t: list(bodies)).start()
    io = MockRobotIO(speaker=False, mic=False)
    core = RobotCore(io, FakeCamera(green_scene()), FakeDetector(), mock=True, depth=depth)
    cfg = DialogueConfig(open_facing_s=60.0, open_timeout_s=30.0, silence_s=0, cooldown_s=0.5)
    snapshots = []

    async def main():
        stop = asyncio.Event()
        app = GreeterApp(InProcessLink(core), [("scripted", ScriptedBackend)], cfg, transcripts=False)
        original = app.dialogue.on_tracks
        app.dialogue.on_tracks = lambda snap, now: (snapshots.append(snap), original(snap, now))[1]
        core_task, app_task = asyncio.ensure_future(core.run(stop)), asyncio.ensure_future(app.run())
        try:
            assert await wait_until(lambda: app.dialogue.state.value == "open", 15)
            await asyncio.sleep(0.5)
            assert app.dialogue.state.value == "open"  # nobody on the spot yet
            bodies.append(Body(1.0, 0.0))  # the visitor steps onto the talk spot
            assert await wait_until(lambda: ("open", "converse") in states(app), 5)
        finally:
            await app.stop()
            await asyncio.wait_for(app_task, 5)
            stop.set()
            await asyncio.wait_for(core_task, 5)
        return app

    app = asyncio.run(main())
    assert ("open", "converse", "stepped onto the spot") in app.dialogue.transitions
    depth_snaps = [s for s in snapshots if (s.get("spot") or {}).get("source") == "depth"]
    assert depth_snaps and any(s["spot_occupied"] for s in depth_snaps)


def test_cli_depth_resolution():
    assert cli.resolve_depth(cli.parse_args(["--mock"])) == "off"  # mock: off unless asked
    assert cli.resolve_depth(cli.parse_args(["--mock", "--depth", "synthetic"])) == "synthetic"
    assert cli.resolve_depth(cli.parse_args(["--depth", "off"])) == "off"
    try:
        import pyrealsense2  # noqa: F401
    except ImportError:
        assert cli.resolve_depth(cli.parse_args([])) == "off"  # no driver: webcam estimate only



# --- regression tests from the review ---------------------------------------------------


def test_quiet_visitor_is_not_taken_for_an_object():
    cfg = SpotConfig(static_s=4.0)
    quiet = lambda t: [Body(1.0, 0.003 * np.sin(2 * np.pi * 0.25 * t))]  # noqa: E731  3 mm sway
    cam = SyntheticDepth(quiet)
    _, states = run(quiet, 0.0, 6.0, det=DepthSpotDetector(cam.intrinsics, cfg), cam=cam)
    assert states[-1][1].occupied and not states[-1][1].static


def test_visitor_joining_a_static_object_is_seen():
    cfg = SpotConfig(static_s=3.0)
    sign = Body(1.0, -0.35, kind="box", height=1.0, width=0.3, depth=0.3)
    scene = lambda t: [sign] + ([Body(1.0, 0.25 + 0.015 * np.sin(2 * np.pi * 0.3 * t))] if t >= 5.0 else [])  # noqa: E731
    cam = SyntheticDepth(scene)
    _, states = run(scene, 0.0, 8.0, det=DepthSpotDetector(cam.intrinsics, cfg), cam=cam)
    by_t = dict(states)
    assert any(s.static and not s.occupied for t, s in states if 3.5 <= t < 5.0)  # the sign alone
    assert states[-1][1].occupied and not states[-1][1].static  # visitor next to it


def test_bystander_beside_the_spot_is_ignored():
    _, states = run(standing(1.0, 0.75), 0.0, 3.0)
    assert occupied_times(states) == []


def test_slow_walker_across_the_spot_is_ignored():
    walker = lambda t: [Body(1.0, -1.2 + 0.4 * t)]  # noqa: E731  0.4 m/s, ~3 s on the footprint
    _, states = run(walker, 0.0, 6.0)
    assert occupied_times(states) == []


def test_usb2_mode_scales_thresholds():
    cam = SyntheticDepth(standing(), width=640, height=480)
    det = DepthSpotDetector(cam.intrinsics)
    assert 0.6 < det.density < 1.6
    _, states = run(standing(), 0.0, 2.5, det=det, cam=cam)
    assert occupied_times(states)


class _FakeRS:
    """Stand-in for pyrealsense2: start works, then the camera drops off USB and comes back."""

    class stream:  # noqa: N801
        depth = "depth"

    class format:  # noqa: N801
        z16 = "z16"

    def __init__(self):
        self.calls = 0
        self.starts = 0
        self.present = True
        self.dropped = False

    def config(self):
        class Cfg:
            def enable_stream(self, *a):
                pass

            def enable_device(self, *a):
                pass

        return Cfg()

    def pipeline(self):
        rs = self

        class Intr:
            width, height, fx, fy, ppx, ppy = 848, 480, 423.0, 423.0, 424.0, 240.0

        class Profile:
            def get_stream(self, s):
                return type("S", (), {"as_video_stream_profile": lambda self: type("V", (), {"get_intrinsics": lambda self: Intr()})()})()

            def get_device(self):
                return type("D", (), {"first_depth_sensor": lambda self: type("Sn", (), {"get_depth_scale": lambda self: 0.001})()})()

        class Frame:
            def get_depth_frame(self):
                return type("DF", (), {"get_data": lambda self: np.zeros((480, 848), np.uint16), "__bool__": lambda self: True})()

        class Pipe:
            started = False

            def start(self, cfg):
                rs.starts += 1
                if not rs.present:
                    raise RuntimeError("No device connected")
                self.started = True
                return Profile()

            def stop(self):
                self.started = False

            def wait_for_frames(self, timeout):
                rs.calls += 1
                if rs.dropped and not self.started_after_drop():
                    raise RuntimeError("wait_for_frames cannot be called before start()")
                time.sleep(0.01)
                return Frame()

            def started_after_drop(self):
                return getattr(self, "_fresh", False)

        pipe = Pipe()
        if self.dropped and self.present:
            pipe._fresh = True
        return pipe


def test_realsense_reader_backs_off_and_restarts_after_a_usb_drop():
    from greeter.robot.depth_source import RealSenseDepth

    rs = _FakeRS()
    reader = RealSenseDepth(rs_module=rs).start()
    try:
        time.sleep(0.2)
        seq_before, _ = reader.latest()
        assert seq_before > 0
        rs.dropped, rs.present = True, False  # camera falls off USB
        rs.calls = 0
        time.sleep(1.5)
        assert rs.calls < 30  # backed off, not ~250k spins per second
        rs.present = True  # camera re-enumerates
        time.sleep(2.5)
        seq_after, _ = reader.latest()
        assert reader.restarts >= 1 and seq_after > seq_before
        assert reader.intrinsics.width == 848  # same mode, so the detector's intrinsics stay valid
    finally:
        reader.stop()


def test_bad_depth_value_in_env_file_is_rejected(monkeypatch):
    monkeypatch.setenv("GREETER_DEPTH", "on")
    with pytest.raises(SystemExit):
        cli.parse_args([])
