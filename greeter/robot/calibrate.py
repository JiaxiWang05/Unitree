"""Headless tuning: prints what the scene sees once per second, and calibrates distance.

Stop the service first (``systemctl --user stop g1-greeter``): it holds the camera.

    python3 -m greeter.robot.calibrate                  # live numbers: green, distance, facing, speed
    python3 -m greeter.robot.calibrate --stand-at 1 2 3 # distance: stand on each floor mark in turn

``--stand-at`` measures the nearest person's shoulder width on each mark (8 s
each, the countdown is printed) and stores ``GREETER_DIST_K`` in the env file.
Accepts the same camera and scene flags as ``python -m greeter``.
"""

from __future__ import annotations

import argparse
import statistics
import time

from greeter.cli import add_vision_args, scene_config
from greeter.envfile import load_env_file, set_value
from greeter.robot.camera import Camera, parse_source
from greeter.robot.detector import PersonDetector
from greeter.vision import Scene, shoulder_px


def describe(person, scene: Scene) -> str:
    notes = []
    if scene.noticeable(person):
        notes.append("NOTICEABLE")
    dist = person.distance
    if dist is not None and 1.2 <= dist <= 2.2 and person.facing_for >= 0.8:
        notes.append("IN BID RANGE")
    if person.at_spot:
        notes.append("on talk spot")
    if person.group is not None:
        notes.append("group of %d" % person.group_size)
    facing = {True: "yes", False: "no", None: "n/a"}[person.facing]
    return "  track %-4d green %4.0f%% (%s)  dist %s  facing %-3s %4.1fs  speed %.2f m/s  %s" % (
        person.track_id,
        100 * person.green_ratio,
        "GREEN" if person.green else "no",
        "%.1f m" % dist if dist is not None else "  ?  ",
        facing,
        person.facing_for,
        person.speed,
        ", ".join(notes),
    )


def measure_marks(camera: Camera, detector: PersonDetector, marks, seconds: float) -> float:
    products = []
    for mark in marks:
        print("\n>>> stand on the %.1f m mark, facing the robot" % mark, flush=True)
        for left in range(3, 0, -1):
            print("    starting in %d" % left, flush=True)
            time.sleep(1.0)
        widths, end, last_seq = [], time.monotonic() + seconds, -1
        while time.monotonic() < end:
            seq, frame = camera.latest()
            if frame is None or seq == last_seq:
                time.sleep(0.01)
                continue
            last_seq = seq
            dets = detector.detect(frame)
            sized = [(shoulder_px(d.keypoints, d.keypoint_conf), d) for d in dets]
            sized = [s for s in sized if s[0] is not None]
            if sized:
                widths.append(max(s[0] for s in sized))  # nearest person = widest shoulders
        if not widths:
            print("    nobody measured on this mark; skipped")
            continue
        width = statistics.median(widths)
        products.append(width * mark)
        print("    shoulders %.0f px at %.1f m -> k = %.0f" % (width, mark, width * mark))
    if not products:
        raise SystemExit("no measurements: is someone in view?")
    return statistics.median(products)


def main(argv=None) -> None:
    load_env_file()  # same camera / model settings as the service
    p = argparse.ArgumentParser(prog="python -m greeter.robot.calibrate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seconds", type=float, default=0, help="stop after this long (0 = until Ctrl-C)")
    p.add_argument("--stand-at", type=float, nargs="+", metavar="M", help="calibrate distance on these floor marks (metres)")
    p.add_argument("--per-mark", type=float, default=8.0, help="seconds measured on each mark")
    add_vision_args(p)
    args = p.parse_args(argv)
    camera = Camera(parse_source(args.camera), args.width, args.height, lock_exposure=not args.no_lock_exposure).start()
    detector = PersonDetector(args.yolo_model, imgsz=args.imgsz, device=args.device, tracker=args.tracker)
    try:
        if args.stand_at:
            k = measure_marks(camera, detector, args.stand_at, args.per_mark)
            path = set_value("GREETER_DIST_K", "%.0f" % k)
            print("\nGREETER_DIST_K=%.0f saved to %s (restart the service to use it)" % (k, path))
            return
        scene = Scene(scene_config(args))
        cfg = scene.cfg
        print("green: CIELAB h %.0f-%.0f, C* > %.0f, >= %.0f%% of torso in %d/%d frames; dist_k %.0f"
              % (cfg.green.hue_lo, cfg.green.hue_hi, cfg.green.chroma_min, 100 * cfg.green.min_ratio,
                 cfg.green.hits, cfg.green.window, cfg.dist_k))
        start = last_print = time.monotonic()
        last_seq, frames = -1, 0
        while not args.seconds or time.monotonic() - start < args.seconds:
            seq, frame = camera.latest()
            if frame is None or seq == last_seq:
                time.sleep(0.005)
                continue
            last_seq = seq
            now = time.monotonic()
            snap = scene.update(frame, detector.detect(frame), now)
            frames += 1
            if now - last_print >= 1.0:
                flags = (" CROWD" if snap.crowd else "") + (" spot occupied" if snap.spot_occupied else "")
                print("%5.1f s  %.0f fps  %d people%s" % (now - start, frames / (now - last_print), len(snap.people), flags))
                for person in sorted(snap.people, key=lambda q: q.distance if q.distance is not None else 99):
                    print(describe(person, scene))
                last_print, frames = now, 0
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()


if __name__ == "__main__":
    main()
