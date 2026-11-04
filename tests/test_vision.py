import numpy as np
import pytest

from greeter.vision import (
    LEFT_EYE,
    LEFT_HIP,
    LEFT_SHOULDER,
    NOSE,
    RIGHT_EYE,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    Detection,
    GreenConfig,
    Scene,
    SceneConfig,
    estimate_distance,
    green_ratio,
    head_yaw_deg,
    iou,
    is_facing,
    torso_box,
)

CFG = GreenConfig()
SHIRT = (40, 180, 40)  # BGR: CIELAB h ~137 deg, C* ~84


def solid(bgr, h=40, w=40):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = bgr
    return img


# --- CIELAB green test ---------------------------------------------------------


@pytest.mark.parametrize(
    "name, bgr, green",
    [
        ("green shirt", SHIRT, True),
        ("pure green", (0, 255, 0), True),
        ("olive", (60, 140, 30), True),
        ("jade", (107, 168, 0), True),
        ("forest", (34, 139, 34), True),
        ("hi-vis yellow-green #CCFF00", (0, 255, 204), False),
        ("hi-vis lime #9AFF00", (0, 255, 154), False),
        ("yellow", (0, 220, 220), False),
        ("teal", (160, 160, 0), False),
        ("cyan", (220, 220, 0), False),
        ("khaki", (140, 180, 195), False),
        ("washed-out sage", (150, 180, 150), False),
        ("green in deep shadow", (10, 30, 10), False),
        ("red", (0, 0, 255), False),
        ("blue", (255, 0, 0), False),
        ("grey", (128, 128, 128), False),
    ],
)
def test_green_colours(name, bgr, green):
    assert green_ratio(solid(bgr), CFG) == pytest.approx(1.0 if green else 0.0), name


def test_green_ratio_partial_and_empty():
    img = solid((200, 60, 60))
    img[:, :10] = SHIRT
    assert green_ratio(img, CFG) == pytest.approx(0.25)
    assert green_ratio(None, CFG) == 0.0
    assert green_ratio(np.zeros((0, 4, 3), np.uint8), CFG) == 0.0


def test_hue_window_is_configurable():
    teal = solid((160, 160, 0))  # h ~196
    assert green_ratio(teal, GreenConfig(hue_hi=200)) == pytest.approx(1.0)


# --- body geometry -------------------------------------------------------------


def frontal(cx=320.0, top=100.0, w=80.0):
    """Keypoints of someone facing the camera with shoulder width ``w`` px (their left = image right)."""
    k = np.zeros((17, 2))
    k[NOSE] = (cx, top + 30)
    k[LEFT_EYE] = (cx + 0.12 * w, top + 20)
    k[RIGHT_EYE] = (cx - 0.12 * w, top + 20)
    k[LEFT_SHOULDER] = (cx + w / 2, top + 80)
    k[RIGHT_SHOULDER] = (cx - w / 2, top + 80)
    k[LEFT_HIP] = (cx + 0.4 * w, top + 80 + 1.25 * w)  # shoulder width / torso length = 0.8 (frontal)
    k[RIGHT_HIP] = (cx - 0.4 * w, top + 80 + 1.25 * w)
    return k, np.full(17, 0.9)


def test_torso_box_variants():
    assert torso_box((100, 40, 300, 440), 640, 480) == (150, 120, 250, 240)  # no keypoints
    k, c = frontal(cx=200, top=60, w=120)
    box = torso_box((100, 40, 300, 440), 640, 480, k, c)
    assert box[1] > 140 and box[3] < 290  # shoulders to hips, inner 80 %
    c[[LEFT_HIP, RIGHT_HIP]] = 0.1
    box = torso_box((100, 40, 300, 440), 640, 480, k, c)
    assert box[3] <= 140 + 1.4 * 120  # close visitor: 1.4 shoulder widths
    assert torso_box((10, 10, 10, 200), 640, 480) is None


def test_head_yaw():
    k, c = frontal()
    assert head_yaw_deg(k, c) == pytest.approx(0.0, abs=1)
    k[NOSE, 0] += 0.12 * 80 * 0.6  # nose shifted towards their left eye
    assert 25 < head_yaw_deg(k, c) < 45
    c[LEFT_EYE] = 0.1
    assert head_yaw_deg(k, c) is None


def test_facing():
    cfg = SceneConfig()
    k, c = frontal()
    assert is_facing(k, c, cfg) is True
    assert is_facing(None, None, cfg) is None
    back = c.copy()
    back[[NOSE, LEFT_EYE, RIGHT_EYE]] = 0.05
    assert is_facing(k, back, cfg) is False
    turned = k.copy()
    turned[NOSE, 0] += 12
    assert is_facing(turned, c, cfg) is False  # head turned > 30 deg
    side = k.copy()
    side[LEFT_SHOULDER, 0] -= 30  # shoulder line rotated: narrow shoulders vs torso length
    side[RIGHT_SHOULDER, 0] += 30
    assert is_facing(side, c, cfg) is False
    mirrored = k.copy()
    mirrored[[LEFT_SHOULDER, RIGHT_SHOULDER]] = mirrored[[RIGHT_SHOULDER, LEFT_SHOULDER]]
    assert is_facing(mirrored, c, cfg) is False


def test_distance_from_shoulders_and_full_body():
    cfg = SceneConfig(dist_k=160.0)
    k, c = frontal(w=80)
    assert estimate_distance(Detection(1, (250, 100, 390, 400), keypoints=k, keypoint_conf=c), 480, cfg) == pytest.approx(2.0)
    # no keypoints, whole body in view: 1.7 m tall at focal 400 px, 272 px tall -> 2.5 m
    assert estimate_distance(Detection(1, (300, 100, 340, 372)), 480, cfg) == pytest.approx(2.5)
    assert estimate_distance(Detection(1, (300, 100, 340, 480)), 480, cfg) is None  # cut off, no keypoints


def test_iou():
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


# --- scene: who gets noticed ------------------------------------------------------


def person(tid, cx=320.0, w=80.0, top=100.0, shirt=SHIRT):
    """A detection plus what it looks like on the frame (torso painted ``shirt``)."""
    k, c = frontal(cx, top, w)
    bottom = min(479.0, top + 80 + 1.25 * w + 2 * w)
    det = Detection(tid, (cx - 0.7 * w, top, cx + 0.7 * w, bottom), 0.9, k, c)
    return det, shirt


def frame_of(*people):
    frame = np.full((480, 640, 3), 90, np.uint8)
    for det, shirt in people:
        k = det.keypoints
        x1, x2 = int(k[RIGHT_SHOULDER, 0]), int(k[LEFT_SHOULDER, 0])
        y1, y2 = int(k[LEFT_SHOULDER, 1]), int(k[LEFT_HIP, 1])
        frame[y1:y2, x1:x2] = shirt
    return frame


def run(scene, frames, t0=0.0, dt=0.1):
    """frames: list of lists of (det, shirt). Returns (noticed ids, last snapshot)."""
    noticed, snap = [], None
    for i, people in enumerate(frames):
        snap = scene.update(frame_of(*people), [d for d, _ in people], t0 + i * dt)
        p = scene.notice(snap)
        if p is not None:
            noticed.append(p.track_id)
    return noticed, snap


def test_green_needs_6_of_10_frames():
    scene = Scene(SceneConfig(notice_min_present_s=0.0, invite="green"))
    noticed, snap = run(scene, [[person(1)]] * 5)
    assert noticed == [] and not snap.people[0].green
    noticed, snap = run(scene, [[person(1)]], t0=0.5)
    assert noticed == [1] and snap.people[0].green


def test_flicker_does_not_count():
    scene = Scene(SceneConfig(notice_min_present_s=0.0, invite="green"))
    red = (30, 30, 200)
    frames = [[person(1, shirt=SHIRT if i % 2 else red)] for i in range(10)]
    assert run(scene, frames)[0] == []  # green in only 5 of 10 frames


def test_noticed_once_per_track():
    scene = Scene()
    assert run(scene, [[person(1)]] * 40)[0] == [1]


def test_too_far_is_not_noticed():
    scene = Scene(SceneConfig(dist_k=160.0))
    noticed, snap = run(scene, [[person(1, w=28)]] * 12)  # 160/28 = 5.7 m
    assert noticed == [] and snap.people[0].distance > 5.0


def test_walking_past_is_not_noticed():
    scene = Scene()
    frames = [[person(1, cx=150 + 20 * i)] for i in range(18)]  # 200 px/s at 2 m = 1 m/s sideways
    noticed, snap = run(scene, frames)
    assert noticed == [] and snap.people[0].speed > 0.6


def test_disabled_scene_does_not_use_up_ids():
    scene = Scene()
    scene.enabled = False
    assert run(scene, [[person(1)]] * 12)[0] == []
    scene.enabled = True
    assert run(scene, [[person(1)]], t0=2.0)[0] == [1]  # already watched long enough while disabled


def test_release_allows_noticing_again():
    scene = Scene()
    assert run(scene, [[person(1)]] * 12)[0] == [1]
    scene.release(1)
    assert run(scene, [[person(1)]], t0=1.0)[0] == [1]


def test_tracker_id_switch_inherits_notice():
    scene = Scene()
    assert run(scene, [[person(1)]] * 12)[0] == [1]
    frames = [[]] * 5 + [[person(9, cx=324)]] * 12
    assert run(scene, frames, t0=1.0)[0] == []
    assert scene.was_noticed(9)


def test_groups_and_crowd():
    scene = Scene()
    pair = [person(1, cx=260), person(2, cx=380)]  # 0.6 m apart at 2 m, standing still
    _, snap = run(scene, [pair] * 15)
    assert {p.group for p in snap.people} == {1} and all(p.group_size == 2 for p in snap.people)
    crowd = [person(i, cx=40 + 70 * i, w=80) for i in range(9)]
    _, snap = run(Scene(), [crowd] * 3)
    assert snap.crowd
    assert Scene().notice(snap) is None


def test_talk_spot():
    scene = Scene(SceneConfig(dist_k=160.0))
    _, snap = run(scene, [[person(1, w=160)]] * 3)  # 1.0 m, centred
    assert snap.people[0].at_spot and snap.spot_occupied
    _, snap = run(Scene(), [[person(1, w=80)]] * 3)  # 2.0 m
    assert not snap.spot_occupied


def test_must_be_watched_a_second_before_noticing():
    scene = Scene()
    noticed, _ = run(scene, [[person(1)]] * 10)  # 0.9 s
    assert noticed == []
    assert run(scene, [[person(1)]], t0=1.0)[0] == [1]


def test_anyone_is_invited_by_default_and_green_mode_needs_green():
    red = (30, 30, 200)
    noticed, snap = run(Scene(SceneConfig(notice_min_present_s=0.0)), [[person(1, shirt=red)]] * 12)
    assert noticed == [1] and not snap.people[0].green
    noticed, _ = run(Scene(SceneConfig(notice_min_present_s=0.0, invite="green")), [[person(1, shirt=red)]] * 12)
    assert noticed == []


def test_nobody_is_noticed_while_the_robot_walks():
    scene = Scene(SceneConfig(notice_min_present_s=0.0))
    for i in range(12):
        snap = scene.update(frame_of(person(1)), [person(1)[0]], i * 0.1)
        snap.walking = True
        assert scene.notice(snap) is None
    snap.walking = False
    assert scene.notice(snap).track_id == 1


def test_snapshot_keeps_the_webcam_spot_estimate_for_comparison():
    scene = Scene()
    snap = scene.update(frame_of(person(1, w=160)), [person(1, w=160)[0]], 0.0)  # 1 m away, centred
    d = snap.to_dict()
    assert d["spot_webcam"] is True and d["spot_occupied"] is True and "walking" not in d
    snap.spot_occupied, snap.walking = False, False  # depth overrules; walking now measured
    d = snap.to_dict()
    assert d["spot_webcam"] is True and d["spot_occupied"] is False and d["walking"] is False
