"""``python -m greeter --check``: one-shot self-test, safe to run over SSH.

Checks the env file and API key (without printing it), internet access to the
chosen backend, the camera, YOLO speed, the robot SDK, mic multicast audio and,
with ``--check-sound``, the speaker. It never waves and never stores anything.
Exit status is non-zero if anything failed.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from greeter.envfile import mask

_failed = []


def report(status: str, name: str, detail: str) -> None:
    if status == "FAIL":
        _failed.append(name)
    print("%-4s  %-12s %s" % (status, name, detail), flush=True)


def _get(url: str, headers: dict, timeout: float = 8.0):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def check_env_file(args) -> None:
    path = Path(args.env_file).expanduser()
    if not path.is_file():
        report("WARN", "env file", "%s not found (settings come from the environment only)" % path)
        return
    loose = path.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH)
    report("WARN" if loose else "PASS", "env file", "%s%s" % (path, " is readable by others: chmod 600" if loose else ""))


def check_backend(args) -> None:
    backend = args.backend
    if backend == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        report("PASS" if key else "FAIL", "api key", "OPENAI_API_KEY " + mask(key))
        if not key:
            return
        try:
            code, body = _get("https://api.openai.com/v1/models/" + args.openai_model, {"Authorization": "Bearer " + key})
        except OSError as exc:
            report("FAIL", "internet", "cannot reach api.openai.com: %s" % exc)
            return
        if code == 200:
            report("PASS", "openai", "key works and %s is available" % args.openai_model)
        elif code == 401:
            report("FAIL", "openai", "key rejected (401): check the key and that billing is set up")
        elif code == 404:
            report("FAIL", "openai", "%s not available to this account (404)" % args.openai_model)
        else:
            report("FAIL", "openai", "HTTP %d: %s" % (code, body[:200].decode("utf-8", "replace")))
    elif backend == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        report("PASS" if key else "FAIL", "api key", "GEMINI_API_KEY " + mask(key))
        if not key:
            return
        try:
            code, _ = _get("https://generativelanguage.googleapis.com/v1beta/models/" + args.gemini_model, {"x-goog-api-key": key})
        except OSError as exc:
            report("FAIL", "internet", "cannot reach generativelanguage.googleapis.com: %s" % exc)
            return
        report("PASS" if code == 200 else "FAIL", "gemini", "%s: HTTP %d" % (args.gemini_model, code))
    elif backend == "local":
        host = (args.ollama_host or "http://127.0.0.1:11434").rstrip("/")
        if "://" not in host:
            host = "http://" + host
        try:
            code, body = _get(host + "/api/tags", {})
            names = [m.get("name") for m in json.loads(body).get("models", [])] if code == 200 else []
        except (OSError, ValueError) as exc:
            report("FAIL", "ollama", "not reachable at %s: %s" % (host, exc))
            return
        ok = any(n == args.vlm or n == args.vlm + ":latest" for n in names)
        report("PASS" if ok else "FAIL", "ollama", "%s %s" % (args.vlm, "pulled" if ok else "missing: ollama pull " + args.vlm))
    else:
        report("PASS", "backend", "scripted (no network needed)")


def check_vision(args):
    from greeter.robot.camera import Camera, parse_source

    try:
        source = parse_source(args.camera)
        camera = Camera(source, args.width, args.height, lock_exposure=False).start()
    except Exception as exc:
        report("FAIL", "camera", str(exc))
        return None
    time.sleep(0.5)
    _, frame = camera.latest()
    camera.stop()
    report("PASS", "camera", "%s: %dx%d" % (source, frame.shape[1], frame.shape[0]))
    try:
        from greeter.cli import scene_config
        from greeter.robot.detector import PersonDetector
        from greeter.vision import Scene

        detector = PersonDetector(args.yolo_model, imgsz=args.imgsz, device=args.device, tracker=args.tracker)
        detector.detect(frame)  # warm-up
        t0 = time.monotonic()
        for _ in range(5):
            detections = detector.detect(frame)
        ms = (time.monotonic() - t0) / 5 * 1000
        snap = Scene(scene_config(args)).update(frame, detections, time.monotonic())
        greens = ", ".join(
            "%.0f%% green at %s" % (100 * p.green_ratio, "%.1f m" % p.distance if p.distance else "?") for p in snap.people
        ) or "nobody in view"
        report("PASS" if ms < 250 else "WARN", "yolo", "%s: %.0f ms/frame (%s)" % (Path(args.yolo_model).name, ms, greens))
    except Exception as exc:
        report("FAIL", "yolo", str(exc))
    return frame


def check_depth(args) -> None:
    from greeter.cli import resolve_depth
    from greeter.robot.depth_source import open_depth
    from greeter.robot.depth_spot import CameraPose, DepthSpotDetector, SpotConfig

    kind = resolve_depth(args)
    if kind == "off":
        report("SKIP", "depth", "talk spot from the webcam only (--depth off, or pyrealsense2 missing)")
        return
    try:
        source = open_depth(kind, args.depth_scenario)
    except Exception as exc:
        report("FAIL" if args.depth == "realsense" else "WARN", "depth", "head D435i not usable: %s" % exc)
        return
    try:
        detector = DepthSpotDetector(source.intrinsics, SpotConfig(), CameraPose(args.depth_pitch, args.depth_height))
        last, frames, end = -1, 0, time.monotonic() + 4.0
        state = None
        while frames < 15 and time.monotonic() < end:
            seq, depth = source.latest()
            if depth is None or seq == last:
                time.sleep(0.02)
                continue
            last, frames = seq, frames + 1
            state = detector.update(depth, time.monotonic())
        if state is None:
            report("FAIL", "depth", "no depth frames in 4 s")
            return
        intr = source.intrinsics
        report(
            "PASS" if detector.floor.fitted else "WARN", "depth",
            "%s %dx%d: floor fit -> pitch %.1f deg (URDF 47.6), height %.2f m; %.0f%% valid; talk spot %s (%d points)"
            % (kind, intr.width, intr.height, state.floor_pitch_deg, state.floor_height_m, 100 * state.valid_ratio,
               "occupied" if state.raw else "empty", state.points),
        )
    finally:
        source.stop()


def check_robot(args) -> None:
    if args.mock:
        report("SKIP", "robot", "--mock: no robot SDK")
        return
    try:
        from greeter.robot.g1_io import G1RobotIO
    except ImportError as exc:
        report("FAIL", "robot sdk", "unitree_sdk2py not importable: %s" % exc)
        return
    try:
        io = G1RobotIO(iface=args.iface, local_ip=args.local_ip, volume=None,
                       mic_device=args.mic_device, speaker_device=args.speaker_device)
        code, data = io.audio.GetVolume()
        report("PASS" if code == 0 else "FAIL", "robot sdk", "voice service on %s: GetVolume -> %s %s" % (args.iface, code, data or ""))
        if io.status():
            report("INFO", "battery", str(io.status()))
    except Exception as exc:
        report("FAIL", "robot sdk", "DDS/voice service: %s" % exc)
        return
    from greeter.audio import is_flat, rms_dbfs
    from greeter.robot.g1_io import WAKE_UP_HINT

    got = bytearray()
    try:
        io.start(got.extend)
    except Exception as exc:  # a USB device that is missing, busy or has no PortAudio
        report("FAIL", "mic", "cannot open %s: %s" % (args.mic_device or args.speaker_device, exc))
        io.close()
        return
    time.sleep(3.0)
    level = rms_dbfs(bytes(got)) if got else -120.0
    if args.mic_device:
        source, fix = "USB mic '%s'" % args.mic_device, "check GREETER_MIC_DEVICE against `python -m sounddevice`"
    else:
        source, fix = "239.168.123.161:5555", "%s, see README" % WAKE_UP_HINT
    if not got:
        hint = " (no audio: %s)" % fix
    elif is_flat(bytes(got)):
        hint = " (all zeros, the mic is muted: %s)" % fix
    elif level > -3.0:
        hint = " (clipping: turn the capture level down, e.g. with alsamixer)"
    else:
        hint = ""
    status = "PASS" if not hint else ("WARN" if "clipping" in hint else "FAIL")
    report(status, "mic", "%d bytes in 3 s from %s, level %.0f dBFS%s" % (len(got), source, level, hint))
    io.led((255, 255, 255))
    if args.check_sound:
        from greeter import clips

        pcm = clips.load().get("hello")
        if pcm is None:
            import numpy as np

            from greeter.audio import float_to_int16, int16_to_pcm

            t = np.arange(8000) / 16000.0
            pcm = int16_to_pcm(float_to_int16(0.3 * np.sin(2 * np.pi * 660 * t)))
        io.play(pcm)
        time.sleep(len(pcm) / 32000.0 + 1.0)
        report("INFO", "speaker", "played a short line through PlayStream; did you hear it?")
    io.close()


def run_checks(args) -> int:
    print("greeter self-test on %s (%s, Python %s)" % (platform.node(), platform.machine(), platform.python_version()))
    try:
        with open("/etc/nv_tegra_release") as f:
            report("INFO", "jetpack", f.readline().strip().lstrip("# "))
    except OSError:
        pass
    check_env_file(args)
    check_backend(args)
    check_vision(args)
    check_depth(args)
    check_robot(args)
    print("FAILED: %s" % ", ".join(_failed) if _failed else "all checks passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    from greeter.cli import main

    main(["--check"] + sys.argv[1:])
