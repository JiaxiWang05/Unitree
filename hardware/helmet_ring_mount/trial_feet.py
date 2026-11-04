"""Trial feet for a head arch that hangs on the G1's two shoulder lifting rings.

The full arch (later) goes from one ring, over the head, to the other ring and carries the
Brio on top. These two small feet are only its ends: print them first, slide each one down
over its ring, push an M5 bolt through, and check the fit before the big part is drawn.

Coordinates are the G1 torso_link frame from unitree_ros (mm): x forward, y left, z up.
The rings are flat steel lugs on top of each shoulder, beside the neck, with the eye facing
sideways, so the bolt runs left-right through cheek, eye, cheek. Their shape comes from
torso_link_23dof_rev_1_0.STL (measured by ray casting, see check_trial_feet.py).

    python trial_feet.py      # writes trial_foot_left/right.stl, trial_feet_plate.stl and .step
"""
from pathlib import Path

import cadquery as cq

# ---- rings (from Unitree's model) ----
RING_X = -0.9                # eye centre, forward of the torso origin
EYE_Z = 345.0                # centre of the eye's round top
EYE_R = 5.83                 # eye: round top of this radius, straight sides down to z 339.5
RING_T = 4.2                 # plate thickness (left-right) where it is flat; the lower part
                             # is up to 6.2 mm across in the model (left 68.1-74.3, right 71.0-76.2)
RING_HALF = 10.9             # outer half-width (front-back)
RING_TOP = 356.0
RING_Y = {1: 71.2, -1: 73.6}  # middle of the plate's left-right extent, |y|; the model is 2.4 mm asymmetric

# ---- foot ----
SLOT_W = 8.5                 # >= 1.1 mm each side of the ring's widest part
SLOT_PLAY_X = 1.5            # beyond the ring's front and back edges
CHEEK_OUT_T = 6.0
CHEEK_IN_T = 7.0             # nut pocket 5.5 deep + 1.5 mm wall to the slot
BOTTOM_Z = 341.2             # >= 2 mm above the shoulder shell under the cheeks
ROOF_GAP, ROOF_T = 2.0, 6.0  # clearance over the ring top, roof thickness
PIN_Z = 347.0                # M5 bolt 2 mm above the eye centre: 1.3 mm clear of the eye's round top;
                             # high enough that the nut pocket stays above the cheek bottom
PIN_HOLE = 5.5               # M5 clearance
NUT_AF, NUT_DEPTH = 8.2, 5.5  # pocket for a DIN 985 M5 nylon-insert nut (8 mm across flats, 5 mm tall)
EDGE_CHAMFER = 1.0           # inner cheek's bottom edge: the shell rises towards the neck there
LEG_W, LEG_TOP = 12.0, 400.0  # stub of the arch's leg, up to the lidar band, to judge clearance

FOOT_LEN = 2 * (RING_HALF + SLOT_PLAY_X) + 6.0   # cheeks reach 3 mm past the slot at each end


def foot(side: int) -> cq.Workplane:
    """One foot at its ring; side +1 = robot's left, -1 = right."""
    yc = side * RING_Y[side]
    in_face = yc - side * (SLOT_W / 2 + CHEEK_IN_T)   # towards the neck
    out_face = yc + side * (SLOT_W / 2 + CHEEK_OUT_T)
    y0, y1 = sorted((in_face, out_face))
    top = RING_TOP + ROOF_GAP + ROOF_T
    body = (
        cq.Workplane("XY").workplane(offset=BOTTOM_Z)
        .center(RING_X, (y0 + y1) / 2)
        .rect(FOOT_LEN, y1 - y0).extrude(top - BOTTOM_Z)
        .edges("|Z").fillet(2.0)
    )
    slot = (
        cq.Workplane("XY").workplane(offset=BOTTOM_Z - 1)
        .center(RING_X, yc)
        .rect(FOOT_LEN + 2, SLOT_W).extrude(RING_TOP + ROOF_GAP - BOTTOM_Z + 1)
    )
    body = body.cut(slot)
    pin = (
        cq.Workplane("XZ", origin=(RING_X, 0, PIN_Z)).circle(PIN_HOLE / 2)
        .extrude(200, both=True)
    )
    body = body.cut(pin)
    # hex pocket on the neck side, a corner pointing up so it prints without support
    depth = NUT_DEPTH + 1.0   # 1 mm outside the face so the pocket opens cleanly
    nut = (
        cq.Workplane("XZ", origin=(RING_X, 0, PIN_Z))
        .transformed(rotate=(0, 0, 30)).polygon(6, NUT_AF / 0.8660254)
        .extrude(depth / 2, both=True)
        .translate((0, in_face + side * (NUT_DEPTH - 1.0) / 2, 0))
    )
    body = body.cut(nut)
    c = EDGE_CHAMFER
    corner = (
        cq.Workplane("YZ", origin=(RING_X, 0, 0))
        .polyline([(in_face - side, BOTTOM_Z + c + 1), (in_face + side * (c + 1), BOTTOM_Z - 1),
                   (in_face - side, BOTTOM_Z - 1)]).close()
        .extrude(FOOT_LEN, both=True)
    )
    body = body.cut(corner)
    leg = (
        cq.Workplane("XY").workplane(offset=top - 0.5)
        .center(RING_X, yc).rect(LEG_W, LEG_W).extrude(LEG_TOP - top + 0.5)
        .edges("|Z").fillet(1.5)
    )
    body = body.union(leg)
    # arrow on the roof pointing forward, so the feet go on the right way round
    ax = RING_X + FOOT_LEN / 2 - 7.5
    arrow = (
        cq.Workplane("XY").workplane(offset=top - 0.1)
        .polyline([(ax - 3, yc - 3.5), (ax + 4, yc), (ax - 3, yc + 3.5)]).close()
        .extrude(1.0)
    )
    body = body.union(arrow)
    assert len(body.solids().vals()) == 1, "foot must be one piece"
    return body


def plate(left: cq.Workplane, right: cq.Workplane) -> cq.Workplane:
    """Both feet standing on the bed as they sit on the robot, 20 mm apart."""
    l = left.translate((0, -RING_Y[1], -BOTTOM_Z))
    r = right.translate((0, RING_Y[-1], -BOTTOM_Z))
    gap = (l.val().BoundingBox().ymin - r.val().BoundingBox().ymax) - 20.0
    return l.translate((0, -gap / 2, 0)).union(r.translate((0, gap / 2, 0)))


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    left, right = foot(1), foot(-1)
    for name, part in (("trial_foot_left", left), ("trial_foot_right", right)):
        # in robot coordinates, so check_trial_feet.py can place them on Unitree's model
        cq.exporters.export(part, str(here / (name + "_robot_frame.stl")), tolerance=0.03, angularTolerance=0.1)
    both = plate(left, right)
    cq.exporters.export(both, str(here / "trial_feet_plate.stl"), tolerance=0.03, angularTolerance=0.1)
    cq.exporters.export(both, str(here / "trial_feet_plate.step"))
    bb = both.val().BoundingBox()
    print("plate: %.1f cm3 for both, %.1f x %.1f x %.1f mm" % (both.val().Volume() / 1000, bb.xlen, bb.ylen, bb.zlen))
