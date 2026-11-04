"""Trial feet for a head arch that hangs on the G1's two shoulder lifting rings.

The full arch (later) goes from one ring, over the head, to the other ring and carries the
Brio on top. These two small feet are only its ends: print them first, slide each one down
over its ring, push an M5 bolt through, and check the fit before the big part is drawn.

Coordinates are the G1 torso_link frame from unitree_ros (mm): x forward, y left, z up.
The rings are flat steel lugs on top of each shoulder, beside the neck, with the eye facing
sideways, so the bolt runs left-right through cheek, eye, cheek. Their shape comes from
torso_link_23dof_rev_1_0.STL (measured by ray casting, see check_trial_feet.py): a round top
of radius 10.9 mm around the eye centre, straight sides below it.

Each foot follows the ring: its slot and its outside are arches concentric with the ring's
round top, so the wall is the same 5 mm all round. The leg stub flares out of the arch, the
outside edges are rounded, the slot mouth is chamfered so it finds the ring, the screw head
sits in a counterbore, and L / R and a forward arrow are engraved on the outer cheek.

    python trial_feet.py      # writes trial_foot_left/right.stl, trial_feet_plate.stl and .step
"""
from pathlib import Path

import cadquery as cq

# ---- rings (from Unitree's model) ----
RING_X = -0.9                # eye centre, forward of the torso origin
EYE_Z = 345.0                # centre of the eye's round top and of the ring's outer round top
EYE_R = 5.83                 # eye: round top of this radius, straight sides down to z 339.5
RING_T = 4.2                 # plate thickness (left-right) where it is flat; the lower part
                             # is up to 6.2 mm across in the model (left 68.1-74.3, right 71.0-76.2)
RING_HALF = 10.9             # outer radius of the round top = half-width of the straight sides
RING_TOP = EYE_Z + RING_HALF
RING_Y = {1: 71.2, -1: 73.6}  # middle of the plate's left-right extent, |y|; the model is 2.4 mm asymmetric

# ---- foot ----
SLOT_W = 8.5                 # >= 1.1 mm each side of the ring's widest part
SLOT_R = RING_HALF + 1.6     # slot arch: 1.6 mm clear of the ring's edge all round
WALL = 5.0
OUTER_R = SLOT_R + WALL      # outside arch, concentric with the slot
FOOT_LEN = 2 * OUTER_R
CHEEK_OUT_T = 6.0
CHEEK_IN_T = 7.0             # nut pocket 5.5 deep + 1.5 mm wall to the slot
BOTTOM_Z = 341.2             # >= 2 mm above the shoulder shell under the cheeks
PIN_Z = 347.0                # M5 bolt 2 mm above the eye centre: 1.3 mm clear of the eye's round top;
                             # high enough that the nut pocket stays above the cheek bottom
PIN_HOLE = 5.5               # M5 clearance
CB_D, CB_DEPTH = 10.6, 3.0   # counterbore for the M5 head (8.5 mm) on a 10 mm washer
BOLT_SEAT = CB_DEPTH - 1.0   # screw head's underside below the outer face (1 mm washer)
NUT_AF, NUT_DEPTH = 8.2, 5.5  # pocket for a DIN 985 M5 nylon-insert nut (8 mm across flats, 5 mm tall)
EDGE_CHAMFER = 1.0           # inner cheek's bottom edge: the shell rises towards the neck there
EDGE_R = 1.2                 # rounding on the outside edges
LEAD_IN = 0.8                # chamfer on the slot mouth
LEG_W, LEG_D = 12.0, 11.0    # leg stub: front-back (sets the lidar shadow) and left-right
LEG_R = 3.5                  # its corner radius
NECK_Z = EYE_Z + OUTER_R + 9.0  # where the flare has narrowed to the leg
LEG_TOP = 400.0              # up to the lidar band, to judge clearance
ENGRAVE = 0.6


def rounded_rect(w, h, r):
    return cq.Sketch().rect(w, h).vertices().fillet(r)


def foot(side: int) -> cq.Workplane:
    """One foot at its ring; side +1 = robot's left, -1 = right."""
    yc = side * RING_Y[side]
    in_face = yc - side * (SLOT_W / 2 + CHEEK_IN_T)   # towards the neck
    out_face = yc + side * (SLOT_W / 2 + CHEEK_OUT_T)
    y0, y1 = sorted((in_face, out_face))
    ymid = (y0 + y1) / 2

    def arch(r, z_bottom):
        """U shape in the x-z plane: straight sides from z_bottom up to the eye centre, round top."""
        return (
            cq.Workplane("XZ")
            .moveTo(RING_X - r, z_bottom).lineTo(RING_X - r, EYE_Z)
            .threePointArc((RING_X, EYE_Z + r), (RING_X + r, EYE_Z))
            .lineTo(RING_X + r, z_bottom).close()
        )

    body = arch(OUTER_R, BOTTOM_Z).extrude((y1 - y0) / 2, both=True).translate((0, ymid, 0))
    rim = [e for e in body.faces(">Y or <Y").edges().vals() if e.Center().z > BOTTOM_Z + 0.5]
    body = body.newObject(rim).fillet(EDGE_R)

    # leg stub, flaring out of the top of the arch
    base_z = EYE_Z + OUTER_R - 7.0
    flare = (
        cq.Workplane("XY")
        .placeSketch(
            rounded_rect(22.0, y1 - y0 - 2 * EDGE_R, 5.0).moved(cq.Location(cq.Vector(RING_X, ymid, base_z))),
            rounded_rect(LEG_W, LEG_D, LEG_R).moved(cq.Location(cq.Vector(RING_X, yc, NECK_Z))),
        )
        .loft()
    )
    leg = (
        cq.Workplane("XY").workplane(offset=NECK_Z - 0.01)
        .placeSketch(rounded_rect(LEG_W, LEG_D, LEG_R).moved(cq.Location(cq.Vector(RING_X, yc, 0))))
        .extrude(LEG_TOP - NECK_Z + 0.01)
        .faces(">Z").edges().fillet(2.5)
    )
    body = body.union(flare).union(leg)

    slot = arch(SLOT_R, BOTTOM_Z - 1).extrude(SLOT_W / 2, both=True).translate((0, yc, 0))
    body = body.cut(slot)
    mouth = [e for e in body.edges().vals()
             if abs(e.Center().z - BOTTOM_Z) < 0.01 and abs(abs(e.Center().y - yc) - SLOT_W / 2) < 0.01]
    body = body.newObject(mouth).chamfer(LEAD_IN)

    pin = cq.Workplane("XZ", origin=(RING_X, 0, PIN_Z)).circle(PIN_HOLE / 2).extrude(200, both=True)
    body = body.cut(pin)
    cb = (
        cq.Workplane("XZ", origin=(RING_X, 0, PIN_Z)).circle(CB_D / 2)
        .extrude((CB_DEPTH + 1) / 2, both=True)
        .translate((0, out_face - side * (CB_DEPTH - 1) / 2, 0))
    )
    body = body.cut(cb)
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

    # engravings on the outer cheek: a forward arrow above the screw, L or R in front of it
    ax, az = RING_X, EYE_Z + 10.5
    arrow = (
        cq.Workplane("XZ")
        .polyline([(ax - 7, az - 0.9), (ax + 2.5, az - 0.9), (ax + 2.5, az - 2.6), (ax + 7, az),
                   (ax + 2.5, az + 2.6), (ax + 2.5, az + 0.9), (ax - 7, az + 0.9)]).close()
        .extrude(ENGRAVE, both=True).translate((0, out_face, 0))
    )
    body = body.cut(arrow)
    face = cq.Plane(origin=(RING_X + 11.2, out_face, BOTTOM_Z + 6.2),
                    xDir=(-side, 0, 0), normal=(0, side, 0))   # reads the right way from outside
    letter = cq.Workplane(face).text("L" if side > 0 else "R", 6.5, -ENGRAVE, combine=False,
                                     halign="center", valign="center", kind="bold")
    body = body.cut(letter)
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
        cq.exporters.export(part, str(here / (name + "_robot_frame.stl")), tolerance=0.02, angularTolerance=0.08)
    both = plate(left, right)
    cq.exporters.export(both, str(here / "trial_feet_plate.stl"), tolerance=0.02, angularTolerance=0.08)
    cq.exporters.export(both, str(here / "trial_feet_plate.step"))
    bb = both.val().BoundingBox()
    print("plate: %.1f cm3 for both, %.1f x %.1f x %.1f mm" % (both.val().Volume() / 1000, bb.xlen, bb.ylen, bb.zlen))
