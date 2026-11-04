"""Compare the two talk-spot judgements in a day's trace: head depth camera vs chest webcam.

Every scene snapshot in ``trace.jsonl`` (~5 Hz) carries the webcam's own estimate
(``spot_webcam``, from shoulder width) and, when the head D435i works, the depth
detector's answer (``spot.occupied``). This adds up, over time, how often they agree and
lists the stretches where they don't, so a lab session can show which one to trust.

    python -m greeter.spot_compare recordings/2026-11-10/trace.jsonl [--min 1.0]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

GAP_S = 1.0  # a longer gap between snapshots counts as 1 s (the service was paused)


def samples(lines: Iterable[str]) -> List[Tuple[float, bool, bool]]:
    """(wall time, depth says occupied, webcam says occupied) for snapshots with fresh depth."""
    out = []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        data = rec.get("data") or {}
        spot = data.get("spot") or {}
        if rec.get("kind") != "tracks" or spot.get("source") != "depth" or spot.get("stale") or "occupied" not in spot:
            continue
        if "spot_webcam" not in data or rec.get("wall") is None:
            continue
        out.append((float(rec["wall"]), bool(spot["occupied"]), bool(data["spot_webcam"])))
    return out


def compare(rows: List[Tuple[float, bool, bool]], min_s: float = 1.0) -> dict:
    totals = {"both": 0.0, "depth_only": 0.0, "webcam_only": 0.0, "neither": 0.0}
    episodes: List[dict] = []
    current: Optional[dict] = None
    for (t, depth, webcam), nxt in zip(rows, rows[1:] + [None]):
        dt = min(GAP_S, nxt[0] - t) if nxt else 0.0
        key = "both" if depth and webcam else "depth_only" if depth else "webcam_only" if webcam else "neither"
        totals[key] += dt
        if key in ("depth_only", "webcam_only"):
            if current is not None and current["kind"] == key:
                current["seconds"] += dt
            else:
                if current is not None and current["seconds"] >= min_s:
                    episodes.append(current)
                current = {"kind": key, "start": t, "seconds": dt}
        elif current is not None:
            if current["seconds"] >= min_s:
                episodes.append(current)
            current = None
    if current is not None and current["seconds"] >= min_s:
        episodes.append(current)
    seen = sum(totals.values())
    return {"seconds": seen, "totals": totals, "agree": (totals["both"] + totals["neither"]) / seen if seen else None,
            "episodes": episodes}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trace", type=Path)
    p.add_argument("--min", type=float, default=1.0, help="shortest disagreement to list, seconds")
    args = p.parse_args(argv)
    with open(args.trace) as f:
        rows = samples(f)
    if len(rows) < 2:
        print("no snapshots with both a depth and a webcam answer in %s" % args.trace)
        return 1
    r = compare(rows, args.min)
    t = r["totals"]
    print("%.0f s compared, agree %.1f %% of the time" % (r["seconds"], 100 * r["agree"]))
    for key, label in (("both", "both: someone on the spot"), ("neither", "both: spot empty"),
                       ("depth_only", "only depth says occupied"), ("webcam_only", "only the webcam says occupied")):
        print("  %-30s %7.1f s" % (label, t[key]))
    if r["episodes"]:
        print("disagreements of %.0f s or more:" % args.min)
        for e in r["episodes"]:
            print("  %s  %5.1f s  %s" % (time.strftime("%H:%M:%S", time.localtime(e["start"])), e["seconds"],
                                         "only depth" if e["kind"] == "depth_only" else "only webcam"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
