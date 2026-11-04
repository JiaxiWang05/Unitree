"""Depth vs webcam talk-spot comparison from a day's trace."""

import json

from greeter.spot_compare import compare, main, samples


def line(t, depth, webcam, stale=False, kind="tracks"):
    spot = {"source": "depth", "occupied": depth, "stale": stale} if depth is not None else None
    data = {"spot_occupied": depth, "spot_webcam": webcam}
    if spot:
        data["spot"] = spot
    return json.dumps({"kind": kind, "data": data, "wall": t})


def test_agreement_and_disagreement_episodes(tmp_path):
    lines = [line(100 + 0.2 * i, False, False) for i in range(10)]          # 2 s empty, both agree
    lines += [line(102 + 0.2 * i, True, False) for i in range(10)]          # 2 s only depth (a child?)
    lines += [line(104 + 0.2 * i, True, True) for i in range(10)]           # 2 s both
    lines += [line(106 + 0.2 * i, False, True) for i in range(3)]           # 0.6 s only webcam (too short to list)
    lines += [line(106.6, None, True), line(107, False, False, stale=True), line(107.2, False, False, kind="status")]
    rows = samples(lines)
    assert len(rows) == 33
    r = compare(rows, min_s=1.0)
    assert abs(r["totals"]["depth_only"] - 2.0) < 1e-6 and abs(r["totals"]["both"] - 2.0) < 1e-6
    assert [e["kind"] for e in r["episodes"]] == ["depth_only"]
    assert abs(r["agree"] - 4.0 / 6.4) < 0.01
    trace = tmp_path / "trace.jsonl"
    trace.write_text("\n".join(lines) + "\n")
    assert main([str(trace)]) == 0
