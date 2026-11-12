"""Deployment helpers: env file, camera auto-detection, CLI defaults."""

import ast
import os
import stat
import wave
from pathlib import Path

import pytest

from greeter import cli
from greeter.envfile import load_env_file, mask, parse_env, set_value
from greeter.robot.camera import Camera, find_usb_camera


def test_parse_env():
    text = """
# comment
OPENAI_API_KEY=sk-abc
export GREETER_CAMERA="/dev/v4l/by-id/usb-Logi_C920-video-index0"
GREETER_VOLUME=70  # inline comment
EMPTY=
not a line
"""
    assert parse_env(text) == {
        "OPENAI_API_KEY": "sk-abc",
        "GREETER_CAMERA": "/dev/v4l/by-id/usb-Logi_C920-video-index0",
        "GREETER_VOLUME": "70",
        "EMPTY": "",
    }


def test_load_env_file_does_not_override(tmp_path, monkeypatch):
    path = tmp_path / "g.env"
    path.write_text("GREETER_TEST_A=from-file\nGREETER_TEST_B=from-file\n")
    os.chmod(path, 0o600)
    monkeypatch.setenv("GREETER_TEST_A", "from-env")
    monkeypatch.delenv("GREETER_TEST_B", raising=False)
    assert load_env_file(path) == ["GREETER_TEST_B"]
    assert os.environ["GREETER_TEST_A"] == "from-env"
    assert os.environ["GREETER_TEST_B"] == "from-file"
    monkeypatch.delenv("GREETER_TEST_B")


def test_set_value_creates_private_file_and_replaces(tmp_path):
    path = tmp_path / "sub" / "g.env"
    set_value("OPENAI_API_KEY", "sk-old", path)
    set_value("GREETER_CAMERA", "auto", path)
    set_value("OPENAI_API_KEY", "sk-new", path)
    assert parse_env(path.read_text()) == {"GREETER_CAMERA": "auto", "OPENAI_API_KEY": "sk-new"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_mask_never_shows_the_key():
    key = "sk-proj-abcdefghijklmnopqrstuvwxyz0123"
    shown = mask(key)
    assert key[:-4] not in shown and "missing" == mask(None)


def test_find_usb_camera_skips_realsense(tmp_path):
    for name in (
        "usb-Intel_R__RealSense_TM__Depth_Camera_435i_123-video-index0",
        "usb-Intel_R__RealSense_TM__Depth_Camera_435i_123-video-index1",
        "usb-046d_HD_Pro_Webcam_C920_ABC-video-index0",
        "usb-046d_HD_Pro_Webcam_C920_ABC-video-index1",
    ):
        (tmp_path / name).touch()
    assert find_usb_camera(str(tmp_path)) == str(tmp_path / "usb-046d_HD_Pro_Webcam_C920_ABC-video-index0")


def test_camera_lock_sets_50hz_and_frame_rate_first_then_freezes_wb_exposure_focus(monkeypatch):
    import shutil
    import subprocess

    import cv2

    log = []

    class FakeCap:
        def read(self):
            log.append("read")
            return True, None

        def set(self, prop, value):
            log.append(("cv2", prop, value))
            return True

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: log.append(cmd[-1]))
    cam = Camera("/dev/v4l/by-id/usb-046d_Brio-video-index0", lock_exposure=True)
    cam._cap = FakeCap()
    cam._lock_auto_controls(settle_s=0.01)

    first_read = log.index("read")
    before = log[:first_read]
    after = log[first_read:]
    assert before == ["power_line_frequency=1", "exposure_dynamic_framerate=0", "exposure_auto_priority=0"]
    for ctrl in ("white_balance_temperature_auto=0", "exposure_auto=1", "focus_auto=0", "focus_automatic_continuous=0"):
        assert ctrl in after
    assert ("cv2", cv2.CAP_PROP_AUTOFOCUS, 0) in after


def test_find_usb_camera_none(tmp_path):
    (tmp_path / "usb-Intel_R__RealSense_TM__Depth_Camera_435i-video-index0").touch()
    assert find_usb_camera(str(tmp_path)) is None
    assert find_usb_camera(str(tmp_path / "missing")) is None


def test_cli_defaults_are_all_on_jetson_with_openai(monkeypatch):
    for name in ("GREETER_BACKEND", "GREETER_CAMERA", "GREETER_TRACKER", "GREETER_DIST_K"):
        monkeypatch.delenv(name, raising=False)
    args = cli.parse_args([])
    assert args.backend == "openai" and args.openai_model == "gpt-realtime-2.1"
    assert args.openai_fallback_model == "gpt-realtime-2.1-mini"
    assert not args.mock and not args.serve and args.robot is None  # one process, no bridge
    assert args.camera == "auto" and args.iface == "eth0"
    assert args.tracker.endswith("botsort_reid.yaml") and os.path.exists(args.tracker)
    assert not args.no_record  # tuning data is kept by default
    cfg = cli.scene_config(args)
    assert (cfg.green.hue_lo, cfg.green.hue_hi, cfg.green.min_ratio) == (110.0, 170.0, 0.25)
    assert cli.parse_args(["--local"]).backend == "local"


def test_cli_rejects_both_split_halves():
    with pytest.raises(SystemExit):
        cli.parse_args(["--serve", "--robot", "ws://x:8765"])


def test_missing_openai_key_message_points_at_env_file(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = cli.parse_args(["--env-file", "/nonexistent/greeter.env"])
    with pytest.raises(SystemExit) as exc:
        cli.providers(args)
    assert "OPENAI_API_KEY" in str(exc.value) and "/nonexistent/greeter.env" in str(exc.value)


def test_provider_chain(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    names = [n for n, _ in cli.providers(cli.parse_args([]))]
    assert names[:2] == ["openai:gpt-realtime-2.1", "openai:gpt-realtime-2.1-mini"]
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    names = [n for n, _ in cli.providers(cli.parse_args([]))]
    assert names[:3] == ["openai:gpt-realtime-2.1", "gemini:gemini-3.8-live", "openai:gpt-realtime-2.1-mini"]
    assert [n for n, _ in cli.providers(cli.parse_args(["--scripted"]))] == ["scripted"]


def test_robot_is_never_moved():
    """No module imports or calls an arm, waist or locomotion client."""
    pkg = Path(cli.__file__).resolve().parent
    forbidden = ("G1ArmActionClient", "g1_arm_action_client", "LocoClient", "loco_client", "arm_sdk", "ExecuteAction")
    for path in pkg.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            elif isinstance(node, ast.Name):
                names = [node.id]
            for name in names:
                assert not any(f in name for f in forbidden), "%s uses %s" % (path.name, name)


def test_recorder_writes_visit(tmp_path):
    from greeter.recorder import NullRecorder, Recorder

    rec = Recorder(tmp_path)
    rec.trace("tracks", {"people": []})
    rec.start_visit("track7")
    rec.mic(b"\x01\x00" * 1600)
    rec.robot(b"\x02\x00" * 800)
    rec.frame(b"\xff\xd8jpeg", "notice")
    rec.event("visitor", "hello robot")
    visit = rec.visit
    rec.end_visit()
    files = {f.name for f in visit.iterdir()}
    assert {"mic.wav", "robot.wav", "events.jsonl", "frame-000-notice.jpg"} <= files
    with wave.open(str(visit / "mic.wav")) as w:
        assert (w.getframerate(), w.getnframes()) == (16000, 1600)
    assert "hello robot" in (visit / "events.jsonl").read_text()
    assert (visit.parent / "trace.jsonl").exists()
    null = NullRecorder()
    null.start_visit("x")
    null.mic(b"..")
    assert null.visit is None


def test_clips_load_only_valid_wavs(tmp_path):
    from greeter import clips

    with wave.open(str(tmp_path / "hey_green.wav"), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 160)
    with wave.open(str(tmp_path / "hello.wav"), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(44100)  # wrong rate: skipped
        w.writeframes(b"\x00\x00" * 160)
    loaded = clips.load(tmp_path)
    assert list(loaded) == ["hey_green"] and len(loaded["hey_green"]) == 320
    assert len(clips.LINES) >= 15 and "Hey, you in the green" in clips.LINES["hey_green"]


def test_offline_clips_are_marked_and_replaced_later(tmp_path, monkeypatch):
    """Without a key the lines are spoken by the machine's own program, at 16 kHz mono."""
    import sys

    from greeter import clips

    writer = ("import sys, wave; w = wave.open(sys.argv[1], 'wb'); w.setnchannels(2); w.setsampwidth(2); "
              "w.setframerate(22050); w.writeframes(b'\\x10\\x00' * 2 * 22050); w.close()")
    monkeypatch.setattr(clips, "offline_command", lambda text, out: [sys.executable, "-c", writer, str(out)])
    assert clips.render_offline(tmp_path) == len(clips.LINES)
    loaded = clips.load(tmp_path)
    assert set(loaded) == set(clips.LINES)
    assert abs(len(loaded["hello"]) - 32000) < 400  # 1 s of stereo 22.05 kHz became 1 s of mono 16 kHz
    assert (tmp_path / clips.OFFLINE_MARK).exists()
    assert clips.render_offline(tmp_path) == 0  # nothing missing: nothing redone

    monkeypatch.setattr(clips, "offline_command", lambda text, out: None)
    with pytest.raises(RuntimeError):
        clips.render_offline(tmp_path / "empty")


def test_scripted_backend_speaks_clips_when_present():
    import asyncio

    from greeter.backends.scripted import OPENER, ScriptedBackend

    async def opener(backend):
        await backend.prepare_opener(b"", "invite")
        async for event in backend.events():
            if event.kind == "opener_ready":
                return event.data

    clip = b"\x01\x00" * 800
    spoken = asyncio.run(opener(ScriptedBackend(opener_delay_s=0, clips={"hey_there": clip}, texts={"hey_there": "Hey there!"})))
    assert spoken == {"pcm": clip, "rate": 16000, "text": "Hey there!"}
    chimed = asyncio.run(opener(ScriptedBackend(opener_delay_s=0)))
    assert chimed["rate"] == 24000 and chimed["text"] == OPENER


def test_no_key_stops_before_the_camera_and_does_not_restart(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GREETER_BACKEND", raising=False)
    args = cli.parse_args(["--env-file", "/nonexistent/greeter.env"])
    with pytest.raises(SystemExit) as exc:
        cli.require_providers(args)
    assert exc.value.code == cli.EX_CONFIG == 78
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    cli.require_providers(cli.parse_args(["--scripted"]))  # needs no key
    install = (Path(__file__).resolve().parent.parent / "scripts" / "install.sh").read_text()
    assert "RestartPreventExitStatus=78" in install and "sounddevice" in install
    assert "libportaudio2" in (Path(__file__).resolve().parent.parent / "scripts" / "setup-jetson.sh").read_text()


def test_library_path_only_adds_folders_that_exist(tmp_path):
    from greeter import libpath

    assert libpath.missing(tmp_path, "") == []
    lib = tmp_path / "cyclonedds" / "install" / "lib"
    lib.mkdir(parents=True)
    assert libpath.missing(tmp_path, "/usr/lib") == [str(lib)]
    assert libpath.missing(tmp_path, "/usr/lib:%s" % lib) == []
