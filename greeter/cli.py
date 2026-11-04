"""Proactive greeter for the Unitree G1 EDU.

Default: everything in one process on the G1's Jetson (chest webcam, detector,
interaction ladder, OpenAI Realtime, mic, speaker, LED). The robot never moves.

  python -m greeter                       all on the Jetson, OpenAI Realtime (gpt-realtime-2.1)
  python -m greeter --backend gemini      Gemini Live (gemini-3.8-live) first instead
  python -m greeter --local               offline cascade (Silero, Whisper, Ollama VLM, Kokoro)
  python -m greeter --check               self-test: keys, internet, camera, YOLO, robot SDK, mic
  python -m greeter --mock [--scripted]   laptop webcam/mic/speaker stand in for the G1

Optional laptop split (not needed for normal use):
  python -m greeter --serve               robot side: hardware + detector behind ws://0.0.0.0:8765
  python -m greeter --robot ws://IP:8765  laptop side: dialogue only

Settings and API keys come from ~/.config/g1-greeter/greeter.env (see README).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from greeter import protocol
from greeter.dialogue.prompts import INVITE_MODES, system_prompt
from greeter.envfile import DEFAULT_ENV_FILE, load_env_file
from greeter.vision import GreenConfig, SceneConfig

REPO = Path(__file__).resolve().parent.parent
BACKENDS = ("openai", "gemini", "local", "scripted")
BOTSORT_REID = Path(__file__).resolve().parent / "robot" / "botsort_reid.yaml"


def on_jetson() -> bool:
    return os.path.exists("/etc/nv_tegra_release")


def env(name: str, default=None):
    return os.environ.get(name) or default


def default_yolo_model() -> str:
    for name in ("yolo26n-pose.engine", "yolo26n-pose.pt"):
        bundled = REPO / "models" / name
        if bundled.exists():
            return env("GREETER_YOLO_MODEL", str(bundled))
    return env("GREETER_YOLO_MODEL", "yolo26n-pose.pt")


def add_vision_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("camera and scene")
    g.add_argument("--camera", default=env("GREETER_CAMERA", "auto"), help="auto, an index, /dev/v4l/by-id/... or a video file (looped)")
    g.add_argument("--width", type=int, default=640)
    g.add_argument("--height", type=int, default=480)
    g.add_argument("--no-lock-exposure", action="store_true", help="leave white balance/exposure on auto")
    g.add_argument("--yolo-model", default=default_yolo_model(), help="yolo26n-pose .pt or exported .engine")
    g.add_argument("--imgsz", type=int, default=int(env("GREETER_IMGSZ", 640)))
    g.add_argument("--device", default=env("GREETER_DEVICE"), help="Ultralytics device, e.g. 0 (CUDA) or cpu")
    g.add_argument("--tracker", default=env("GREETER_TRACKER", str(BOTSORT_REID)), help="Ultralytics tracker yaml (default: BoT-SORT with ReID)")
    g.add_argument("--min-green", type=float, default=float(env("GREETER_MIN_GREEN", 0.25)), help="green fraction of the torso")
    g.add_argument("--hue", type=float, nargs=2, default=(110.0, 170.0), metavar=("LO", "HI"), help="CIELAB hue window, degrees")
    g.add_argument("--min-chroma", type=float, default=20.0, help="CIELAB C* above which a pixel counts as coloured")
    g.add_argument("--dist-k", type=float, default=float(env("GREETER_DIST_K", 160.0)),
                   help="shoulder px x metres; calibrate with python -m greeter.robot.calibrate --stand-at 1 2 3")
    g.add_argument("--depth", choices=("auto", "realsense", "synthetic", "off"), default=env("GREETER_DEPTH", "auto"),
                   help="talk spot from the head D435i depth (auto: on the robot when pyrealsense2 works; off in --mock)")
    g.add_argument("--depth-scenario", choices=("visit", "walkby", "bag", "empty"), default="visit",
                   help="--depth synthetic: what the fake D435i sees (visit is timed to scripts/make_test_clip.py)")
    g.add_argument("--depth-pitch", type=float, default=float(env("GREETER_DEPTH_PITCH", 47.6)), help="D435i pitch below horizontal (URDF 47.6); refined from the floor")
    g.add_argument("--depth-height", type=float, default=float(env("GREETER_DEPTH_HEIGHT", 1.258)), help="D435i height above the floor (m)")


def resolve_depth(args: argparse.Namespace) -> str:
    """auto -> realsense on the robot if pyrealsense2 imports, otherwise off (always off in --mock)."""
    if args.depth != "auto":
        return args.depth
    if getattr(args, "mock", False):
        return "off"
    try:
        import pyrealsense2  # noqa: F401
    except ImportError:
        return "off"
    return "realsense"


def open_depth_source(args: argparse.Namespace):
    """Start the depth source, or return None (talk spot then comes from the webcam estimate)."""
    from greeter.robot.depth_source import open_depth

    kind = resolve_depth(args)
    try:
        return open_depth(kind, args.depth_scenario)
    except Exception as exc:
        if args.depth == "auto":
            logging.getLogger("greeter").warning("head D435i depth unavailable (%s): talk spot from the webcam only", exc)
            return None
        raise


def scene_config(args: argparse.Namespace) -> SceneConfig:
    return SceneConfig(
        green=GreenConfig(hue_lo=args.hue[0], hue_hi=args.hue[1], chroma_min=args.min_chroma, min_ratio=args.min_green),
        dist_k=args.dist_k,
        invite=args.invite,
    )


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m greeter", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="settings and API keys (KEY=value lines)")
    p.add_argument("--check", action="store_true", help="run the self-test and exit")
    p.add_argument("--check-sound", action="store_true", help="with --check: also play a short line on the speaker")
    p.add_argument("-v", "--verbose", action="store_true")

    b = p.add_argument_group("conversation backend")
    b.add_argument("--backend", choices=BACKENDS, default=env("GREETER_BACKEND", "openai"))
    b.add_argument("--local", dest="backend", action="store_const", const="local", help="same as --backend local")
    b.add_argument("--scripted", dest="backend", action="store_const", const="scripted", help="canned replies, for plumbing tests")
    b.add_argument("--openai-model", default=env("GREETER_OPENAI_MODEL", "gpt-realtime-2.1"))
    b.add_argument("--openai-fallback-model", default=env("GREETER_OPENAI_FALLBACK_MODEL", "gpt-realtime-2.1-mini"))
    b.add_argument("--openai-voice", default=env("GREETER_OPENAI_VOICE", "marin"), help="marin, cedar, alloy, coral, ...")
    b.add_argument("--vad-eagerness", choices=("auto", "low", "medium", "high"), default=env("GREETER_VAD_EAGERNESS", "auto"))
    b.add_argument("--gemini-model", default=env("GREETER_GEMINI_MODEL", "gemini-3.8-live"))
    b.add_argument("--gemini-voice", default=env("GREETER_GEMINI_VOICE", "Puck"))
    b.add_argument("--media-resolution", choices=("low", "medium", "high"), default=None, help="Gemini only")
    b.add_argument("--vlm", default=env("GREETER_VLM", "qwen3-vl:2b-instruct" if on_jetson() else "qwen3.5:4b"), help="Ollama model for --local")
    b.add_argument("--ollama-host", default=env("OLLAMA_HOST"))
    b.add_argument("--asr", choices=("whisper", "parakeet"), default="whisper")
    b.add_argument("--asr-model", default=env("GREETER_ASR_MODEL"), help="default base.en on the Jetson, small.en elsewhere")
    b.add_argument("--kokoro-voice", default="bf_emma")

    d = p.add_argument_group("dialogue")
    d.add_argument("--invite", choices=INVITE_MODES, default=env("GREETER_INVITE", "anyone"),
                   help="anyone (default): invite whoever looks interested; green: only people wearing green")
    d.add_argument("--roam", action="store_true", default=env("GREETER_ROAM") == "1",
                   help="a team member walks the robot with the Unitree remote: pause invitations while it walks")
    d.add_argument("--max-visit", type=float, default=float(env("GREETER_MAX_VISIT", 240.0)), help="seconds")
    d.add_argument("--silence", type=float, default=float(env("GREETER_SILENCE", 15.0)), help="close after this much silence (0 = never)")
    d.add_argument("--no-transcripts", action="store_true", default=env("GREETER_TRANSCRIPTS") == "0", help="don't print what is said")

    rec = p.add_argument_group("recording (for tuning)")
    rec.add_argument("--record-dir", default=env("GREETER_RECORD_DIR", str(REPO / "recordings")))
    rec.add_argument("--no-record", action="store_true", default=env("GREETER_RECORD") == "0")

    r = p.add_argument_group("robot hardware")
    r.add_argument("--iface", default=env("GREETER_IFACE", "eth0"), help="Jetson interface on 192.168.123.0/24")
    r.add_argument("--local-ip", default=env("GREETER_LOCAL_IP", "192.168.123.164"), help="address used to join the mic multicast group")
    r.add_argument("--volume", type=int, default=int(env("GREETER_VOLUME", 80)), help="G1 speaker volume 0..100")
    r.add_argument("--duplex", action="store_true", default=env("GREETER_DUPLEX") == "1", help="keep the mic open while the robot speaks (barge-in)")
    r.add_argument("--mic-device", default=env("GREETER_MIC_DEVICE"), help="Tier 1: USB mic (ALSA/PortAudio name) instead of the robot mic")
    r.add_argument("--speaker-device", default=env("GREETER_SPEAKER_DEVICE"), help="Tier 1: USB DAC instead of PlayStream")

    m = p.add_argument_group("mock robot (laptop testing)")
    m.add_argument("--mock", action="store_true", help="laptop webcam/mic/speaker instead of the G1")
    m.add_argument("--no-mic", action="store_true", help="send silence instead of the laptop mic")
    m.add_argument("--no-speaker", action="store_true", help="time playback without playing it")

    s = p.add_argument_group("optional laptop split")
    s.add_argument("--serve", action="store_true", help="robot side only: serve the hardware over WebSocket")
    s.add_argument("--robot", metavar="URL", help="laptop side only: connect to a bridge, e.g. ws://192.168.123.164:8765")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=protocol.DEFAULT_PORT)
    s.add_argument("--token", default=env("GREETER_TOKEN"), help="bridge shared secret")
    add_vision_args(p)
    args = p.parse_args(argv)
    if args.serve and args.robot:
        p.error("--serve and --robot are the two halves of the split; pick one")
    # values from the env file arrive as defaults, which argparse doesn't check against choices
    for name, allowed in (("backend", BACKENDS), ("depth", ("auto", "realsense", "synthetic", "off")), ("invite", INVITE_MODES)):
        if getattr(args, name) not in allowed:
            p.error("%s must be one of %s, not %r (check GREETER_%s in the env file)" % (name, ", ".join(allowed), getattr(args, name), name.upper()))
    return args


def _has(*names: str) -> bool:
    return any(os.environ.get(n) for n in names)


def providers(args: argparse.Namespace):
    """The fallback chain: the chosen backend first, then whatever else is configured, then clips."""
    from greeter import clips

    persona = system_prompt(args.invite, args.roam)

    def openai(model):
        from greeter.backends.openai_realtime import OpenAIRealtimeBackend

        return ("openai:" + model, lambda: OpenAIRealtimeBackend(model=model, voice=args.openai_voice, eagerness=args.vad_eagerness, system_prompt=persona))

    def gemini():
        from greeter.backends.gemini import GeminiBackend

        return ("gemini:" + args.gemini_model, lambda: GeminiBackend(model=args.gemini_model, voice=args.gemini_voice, media_resolution=args.media_resolution, system_prompt=persona))

    def gemini_available() -> bool:
        if not _has("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            return False
        try:
            import google.genai  # noqa: F401
        except ImportError:
            return False
        return True

    backend = args.backend
    if backend == "scripted":
        from greeter.backends.scripted import ScriptedBackend

        return [("scripted", ScriptedBackend)]
    chain = []
    if backend == "local":
        from greeter.backends.local import LocalBackend

        asr_model = args.asr_model or ("base.en" if on_jetson() else None)
        chain.append(("local", lambda: LocalBackend(
            vlm_model=args.vlm, ollama_host=args.ollama_host, asr=args.asr, asr_model=asr_model, voice=args.kokoro_voice,
            system_prompt=persona,
        )))
    elif backend == "gemini":
        if not gemini_available():
            sys.exit("--backend gemini needs GEMINI_API_KEY and google-genai (Python 3.10+)")
        chain.append(gemini())
    elif not _has("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Put it in %s (README: What the human does), or try --scripted." % args.env_file)
    if backend in ("openai", "gemini") and _has("OPENAI_API_KEY"):
        chain.append(openai(args.openai_model))
        if backend == "openai" and gemini_available():
            chain.append(gemini())  # hot standby on another provider
        if args.openai_fallback_model:
            chain.append(openai(args.openai_fallback_model))
    loaded = clips.load()
    if loaded:
        from greeter.backends.scripted import CannedBackend

        chain.append(("clips", lambda: CannedBackend(loaded, clips.LINES)))
    return chain


def make_io(args: argparse.Namespace):
    if args.mock:
        from greeter.robot.mock_io import MockRobotIO

        return MockRobotIO(speaker=not args.no_speaker, mic=not args.no_mic)
    from greeter.robot.g1_io import G1RobotIO

    return G1RobotIO(
        iface=args.iface, local_ip=args.local_ip, volume=args.volume,
        mic_device=args.mic_device, speaker_device=args.speaker_device, walk_detect=args.roam,
    )


def build_core(args: argparse.Namespace, io):
    from greeter.robot.camera import Camera, parse_source
    from greeter.robot.core import RobotCore
    from greeter.robot.detector import PersonDetector

    from greeter.robot.depth_spot import CameraPose

    camera = Camera(parse_source(args.camera), args.width, args.height, lock_exposure=not args.no_lock_exposure).start()
    detector = PersonDetector(args.yolo_model, imgsz=args.imgsz, device=args.device, tracker=args.tracker)
    depth = open_depth_source(args)
    pose = CameraPose(pitch_deg=args.depth_pitch, height_m=args.depth_height)
    return RobotCore(io, camera, detector, scene_config(args), mock=args.mock, gate_mic=not args.duplex, depth=depth, depth_pose=pose)


def dialogue_config(args: argparse.Namespace):
    from greeter.dialogue.machine import DialogueConfig

    return DialogueConfig(max_visit_s=args.max_visit, silence_s=args.silence, invite=args.invite, roam=args.roam)


def make_app(link, args):
    from greeter import clips
    from greeter.dialogue.app import GreeterApp
    from greeter.recorder import NullRecorder, Recorder

    chain = providers(args)
    logging.getLogger("greeter").info("providers: %s", " -> ".join(name for name, _ in chain))
    recorder = NullRecorder() if args.no_record else Recorder(Path(args.record_dir))
    return GreeterApp(link, chain, dialogue_config(args), transcripts=not args.no_transcripts, recorder=recorder, clips=clips.load())


def _install_stop_signals(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):  # Windows
            pass


async def run_all_in_one(core, app) -> None:
    """Default mode: robot core and dialogue in one event loop, linked by direct calls."""
    stop = asyncio.Event()
    _install_stop_signals(stop)
    core_task = asyncio.ensure_future(core.run(stop))
    app_task = asyncio.ensure_future(app.run())
    stop_task = asyncio.ensure_future(stop.wait())
    try:
        done, _ = await asyncio.wait({core_task, app_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in done & {core_task, app_task}:
            task.result()  # surface a crash so systemd restarts us
    finally:
        await app.stop()
        app_task.cancel()
        stop.set()
        await asyncio.wait({core_task}, timeout=5)
        stop_task.cancel()


async def run_bridge(core, args) -> None:
    from greeter.robot.server import BridgeServer

    stop = asyncio.Event()
    _install_stop_signals(stop)
    await BridgeServer(core, args.host, args.port, token=args.token).run(stop)


async def run_remote(app) -> None:
    stop = asyncio.Event()
    _install_stop_signals(stop)
    app_task = asyncio.ensure_future(app.run())
    await stop.wait()
    await app.stop()
    app_task.cancel()


def main(argv=None) -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    known, _ = pre.parse_known_args(argv)
    loaded = load_env_file(Path(known.env_file))  # before parse_args: the file supplies defaults
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("websockets", "httpx", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if loaded:
        logging.getLogger("greeter").info("settings from %s: %s", args.env_file, ", ".join(sorted(loaded)))

    if args.check:
        from greeter.check import run_checks

        sys.exit(run_checks(args))
    if args.serve:
        asyncio.run(run_bridge(build_core(args, make_io(args)), args))
        return
    if args.robot:
        from greeter.dialogue.links import WebSocketLink

        url = args.robot
        if args.token:
            url += ("&" if "?" in url else "?") + "token=" + args.token
        asyncio.run(run_remote(make_app(WebSocketLink(url), args)))
        return
    from greeter.dialogue.links import InProcessLink

    core = build_core(args, make_io(args))
    asyncio.run(run_all_in_one(core, make_app(InProcessLink(core), args)))
