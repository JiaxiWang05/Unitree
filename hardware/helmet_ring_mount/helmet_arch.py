"""Full head arch: carries the Brio on top of the G1's head, hanging on the two shoulder rings.

Three printed pieces, bolted together:

* two feet (left, right): the trial feet from trial_feet.py, with the leg stub cut at
  z 385 and replaced by the front half of a lap joint up to z 409;
* the crown: both legs from the lap joint up, the arch over the head, and the camera block
  on top. Its whole back is one flat plane (x = -6.9), so it prints lying on its back with no
  supports, and it fits a 256 mm bed.

Each lap joint takes 2 M3 x 12 socket cap screws (heads on the back) into M3 nuts in hex
pockets on the front of the foot's half. The feet take the same M5 x 20 screws and DIN 985
nuts as the trial feet. The arch's weight rests on the head top through a saddle under the
camera block, lined with 3 mm EVA foam; the ring screws only keep it from lifting or tipping.

Camera: Brio 4K with its clip removed, tilted 10 degrees up, between front and back lips,
held from below by a 1/4"-20 x 5/8" screw with one M6 washer (4.0 mm into the camera, as on
the chest bracket). The screw goes in from the saddle's underside before the arch goes on.
The lens ends up about 1.365 m above the floor.

Coordinates are the G1 torso_link frame from unitree_ros (mm): x forward, y left, z up.
The head-top surface under the saddle is an ellipsoid fitted to head_link.STL there
(residual -0.2 to +0.9 mm, taken up by the foam).

    python helmet_arch.py     # writes the print STLs, robot-frame STLs and helmet_arch.step
"""
import math
import sys
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brio_chest_mount"))
import trial_feet as tf  # noqa: E402
from brio_chest_mount import (BACK_LIP_GAP, CAM_D, CAM_H, CAM_W, GRIP, LIP_H, LIP_T,  # noqa: E402
                              PLUG_L, PLUG_T, PLUG_W, SLOT_PLAY, SLOT_W, SPOT_D, THREAD_FROM_BACK, USB_Z)

# ---- arch ----
XA = tf.RING_X               # arch plane: straight above the rings
HALF_X = tf.LEG_W / 2        # 12 mm front-back: the lidar's shadow is this wide
T = tf.LEG_D                 # 11 mm across the arch
EDGE_R = tf.LEG_R            # same rounded section as the feet's leg stubs
BACK_X = XA - HALF_X         # the crown's flat back, its print bed
LAP_Z0, LAP_Z1 = 385.0, 409.0  # lap joint between foot and crown
M3_Z = (391.0, 403.0)
M3_HOLE, M3_NUT_AF, M3_NUT_DEPTH = 3.4, 5.7, 3.0
Z0 = 420.0                   # legs straight up to here, then the arch
ARCH_TOP = 499.0             # arch centreline over the middle of the head
ARCH_N = 2.6                 # superellipse exponent: rounder than a box, fuller than an ellipse

# ---- head top under the saddle (ellipsoid fit to head_link.STL, x -12..34, |y| <= 30) ----
HEAD_TOP = (5.48, 0.0, 336.56)          # centre
HEAD_AXES = (119.5, 96.6, 150.0)        # semi-axes: top at z 486.56, curvatures 0.00525 / 0.00804 per mm
FOAM = 3.0                               # adhesive EVA foam between saddle and head

# ---- camera block ----
TILT = 10.0                  # camera looks up this much
CAM_X = 10.5                 # camera underside centre: far enough forward that the back lip clears BACK_X
LENS_Z = 529.0               # lens height in the torso frame -> 836 + 529 = 1365 mm above the floor
BLOCK_W = 46.0               # seat width, inside the flat middle of the camera's underside
LIP_GAP = CAM_D + 1.0
FRONT_X = None               # set below from the lip
TIE_W, TIE_H = 3.0, 4.0      # cable-tie tunnels (fits 2.5-3.6 mm ties)
SPOT_DEPTH = 30.0            # spot face pocket reaches this far below the seat: through the saddle

s, c = math.sin(math.radians(TILT)), math.cos(math.radians(TILT))
U = (c, 0.0, s)              # camera forward
W = (-s, 0.0, c)             # camera up
CAM_Z = LENS_Z - (CAM_D / 2) * s - (CAM_H / 2) * c   # underside centre, so the lens lands at LENS_Z
P0 = (CAM_X, 0.0, CAM_Z)
FRONT_X = CAM_X + (LIP_GAP / 2 + LIP_T) * c + 3.0   # 3 mm ledge in front of the lip keeps the spot face inside


def at(uu, ww, y=0.0):
    """Point from camera-frame coordinates (u forward, w up, y left) about the underside centre."""
    return (P0[0] + uu * U[0] + ww * W[0], y, P0[2] + uu * U[2] + ww * W[2])


def cam_plane(uu=0.0, ww=0.0):
    """Workplane on the camera underside: local x = robot right (-y), local y = camera forward, normal = up."""
    return cq.Plane(origin=at(uu, ww), xDir=(0, -1, 0), normal=W)


def rounded_rect(w, h, r):
    return cq.Sketch().rect(w, h).vertices().fillet(r)


# ---- arch centreline ----
def centreline(side, n=120):
    """Points (y, z) from the leg at z LAP_Z1 up to the top of the arch, for one side."""
    a = tf.RING_Y[side]
    b = ARCH_TOP - Z0
    pts = [(side * a, LAP_Z1), (side * a, Z0)]
    for i in range(1, n + 1):
        phi = (math.pi / 2) * i / n
        yy = a * math.cos(phi) ** (2 / ARCH_N)
        zz = Z0 + b * math.sin(phi) ** (2 / ARCH_N)
        pts.append((side * yy, zz))
    return pts


def offset(pts, d):
    """Offset a (y, z) polyline by d to its left (towards the head for the left side's upward run)."""
    out = []
    for i, (y, z) in enumerate(pts):
        y0, z0 = pts[max(0, i - 1)]
        y1, z1 = pts[min(len(pts) - 1, i + 1)]
        ty, tz = y1 - y0, z1 - z0
        L = math.hypot(ty, tz) or 1.0
        out.append((y - d * tz / L, z + d * ty / L))
    return out


def arch_path():
    """The whole centreline, left leg bottom -> top -> right leg bottom."""
    left = centreline(1)
    right = centreline(-1)
    return left + right[::-1][1:]


def arch():
    path = arch_path()
    inner = offset(path, T / 2)      # path runs left -> right over the top: its left normal points down/inwards
    outer = offset(path, -T / 2)
    # thin the point lists for the splines (every 3rd point plus the ends)
    pick = lambda p: [p[0]] + p[1:-1:3] + [p[-1]]  # noqa: E731
    o, i = pick(outer), pick(inner)
    wp = (
        cq.Workplane("YZ").moveTo(*o[0]).spline(o[1:], includeCurrent=True)
        .lineTo(*i[-1]).spline(i[::-1][1:], includeCurrent=True).close()
    )
    solid = wp.extrude(HALF_X, both=True).translate((XA, 0, 0))
    long_edges = [e for e in solid.edges().vals() if e.geomType() != "LINE"]
    return solid.newObject(long_edges).fillet(EDGE_R)


def lap(side, front):
    """Half of the leg section between LAP_Z0 and LAP_Z1: front half for the foot, back half for the crown."""
    yc = side * tf.RING_Y[side]
    full = (
        cq.Workplane("XY").workplane(offset=LAP_Z0)
        .placeSketch(rounded_rect(tf.LEG_W, tf.LEG_D, tf.LEG_R).moved(cq.Location(cq.Vector(XA, yc, 0))))
        .extrude(LAP_Z1 - LAP_Z0)
    )
    half = cq.Workplane("XY").box(HALF_X, 40, 60, centered=(False, True, True)).translate(
        (XA if front else XA - HALF_X, yc, (LAP_Z0 + LAP_Z1) / 2))
    return full.intersect(half)


def m3_holes(side):
    yc = side * tf.RING_Y[side]
    h = None
    for z in M3_Z:
        cyl = cq.Workplane("YZ", origin=(0, yc, z)).circle(M3_HOLE / 2).extrude(100, both=True)
        h = cyl if h is None else h.union(cyl)
    return h


def m3_nuts(side):
    yc = side * tf.RING_Y[side]
    front = XA + HALF_X
    h = None
    for z in M3_Z:
        nut = (
            cq.Workplane("YZ", origin=(0, yc, z)).transformed(rotate=(0, 0, 30))
            .polygon(6, M3_NUT_AF / 0.8660254).extrude((M3_NUT_DEPTH + 1) / 2, both=True)
            .translate((front - (M3_NUT_DEPTH - 1) / 2, 0, 0))
        )
        h = nut if h is None else h.union(nut)
    return h


def foot(side):
    """Trial foot with its stub cut at LAP_Z0 and the front half of the lap joint added."""
    yc = side * tf.RING_Y[side]
    f = tf.foot(side)
    cut = cq.Workplane("XY").box(30, 30, 40, centered=(True, True, False)).translate((XA, yc, LAP_Z0))
    f = f.cut(cut).union(lap(side, front=True))
    f = f.cut(m3_holes(side)).cut(m3_nuts(side))
    assert len(f.solids().vals()) == 1, "foot must be one piece"
    return f


def head_top(extra):
    """The fitted head-top ellipsoid grown by `extra` mm."""
    ax, ay, az = (a + extra for a in HEAD_AXES)
    sph = cq.Solid.makeSphere(1.0, angleDegrees1=-90, angleDegrees2=90)
    m = cq.Matrix([[ax, 0, 0, HEAD_TOP[0]], [0, ay, 0, HEAD_TOP[1]], [0, 0, az, HEAD_TOP[2]]])
    return cq.Workplane("XY").add(sph.transformGeometry(m))


def block():
    """Camera block: seat with lips on top, saddle on the head underneath, flat back at BACK_X."""
    box = cq.Workplane("XY").box(FRONT_X - BACK_X, BLOCK_W, 120, centered=(False, True, False)).translate(
        (BACK_X, 0, 440))
    below_seat = cq.Workplane(cam_plane()).rect(400, 400).extrude(-200)
    b = box.intersect(below_seat).cut(head_top(FOAM))
    b = b.edges("|Z").edges(">X").fillet(4.0)
    for uu in (-(LIP_GAP / 2 + LIP_T / 2), LIP_GAP / 2 + LIP_T / 2):
        lip = cq.Workplane(cam_plane(uu)).rect(BLOCK_W, LIP_T).extrude(LIP_H)
        if uu < 0:   # gap in the back lip for the straight USB-C plug
            lip = lip.cut(cq.Workplane(cam_plane(uu)).rect(BACK_LIP_GAP, LIP_T + 2).extrude(LIP_H + 1))
        b = b.union(lip)
    return b


def block_cuts():
    """Screw slot and its spot face, and the tie tunnel under the back lip for the plug."""
    t0 = THREAD_FROM_BACK - CAM_D / 2            # thread, forward of the underside centre
    slot = cq.Workplane(cam_plane(t0)).slot2D(SLOT_W + SLOT_PLAY, SLOT_W, angle=90).extrude(-80, both=False)
    # spot face for the screw head and washer, open through the saddle underneath (not through the front)
    spot = cq.Workplane(cam_plane(t0, -GRIP)).slot2D(SPOT_D + SLOT_PLAY, SPOT_D, angle=90).extrude(-(SPOT_DEPTH - GRIP))
    seat_z = P0[2] + (BACK_X + 3.5 - CAM_X) * math.tan(math.radians(TILT))
    tunnel = cq.Workplane("XY").box(TIE_W, 80, TIE_H).translate((BACK_X + 2.0 + TIE_W / 2, 0, seat_z - 6.5 - TIE_H / 2))
    return slot.union(spot).union(tunnel)


def leg_ties(side=1, heights=(415.0, 455.0, 480.0)):
    """Cable-tie tunnels across one leg, near its back face, for the camera cable."""
    path = centreline(side)
    out = None
    for zt in heights:
        k = min(range(len(path) - 1), key=lambda j: abs(path[j][1] - zt))
        (y0, z0), (y1, z1) = path[k], path[k + 1]
        ty, tz = y1 - y0, z1 - z0
        L = math.hypot(ty, tz)
        ang = math.degrees(math.atan2(-ty / L, tz / L))
        t = (
            cq.Workplane("XY").box(TIE_W, T + 6, TIE_H)
            .rotate((0, 0, 0), (1, 0, 0), ang)
            .translate((BACK_X + 2.5 + TIE_W / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        )
        out = t if out is None else out.union(t)
    return out


def crown():
    cr = arch().union(lap(1, front=False)).union(lap(-1, front=False)).union(block())
    cr = cr.cut(block_cuts()).cut(leg_ties(1)).cut(m3_holes(1)).cut(m3_holes(-1))
    assert len(cr.solids().vals()) == 1, "crown must be one piece"
    return cr


def camera():
    """Brio body (clip removed) and its straight USB-C plug, for checks and pictures."""
    body = cq.Workplane(cam_plane()).rect(CAM_W, CAM_D).extrude(CAM_H)
    plug = cq.Workplane(cq.Plane(origin=at(-CAM_D / 2, USB_Z), xDir=(0, 1, 0), normal=tuple(-v for v in U))) \
        .rect(PLUG_W, PLUG_T).extrude(PLUG_L)
    return body, plug


def lens():
    return at(CAM_D / 2, CAM_H / 2)


def to_print_crown(cr):
    """Crown lying on its flat back: robot +x becomes up."""
    return cr.rotate((0, 0, 0), (0, 1, 0), -90).translate((0, 0, -BACK_X))


if __name__ == "__main__":
    pieces = {"helmet_foot_left": foot(1), "helmet_foot_right": foot(-1), "helmet_crown": crown()}
    for name, part in pieces.items():
        cq.exporters.export(part, str(HERE / (name + "_robot_frame.stl")), tolerance=0.03, angularTolerance=0.1)
    cam, plug = camera()
    cq.exporters.export(cam.union(plug), str(HERE / "helmet_brio_robot_frame.stl"), tolerance=0.1, angularTolerance=0.2)
    # print orientation
    for side, name in ((1, "helmet_foot_left"), (-1, "helmet_foot_right")):
        p = pieces[name].translate((0, -side * tf.RING_Y[side], -tf.BOTTOM_Z))
        cq.exporters.export(p, str(HERE / (name + ".stl")), tolerance=0.03, angularTolerance=0.1)
    pc = to_print_crown(pieces["helmet_crown"])
    bb = pc.val().BoundingBox()
    pc = pc.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
    cq.exporters.export(pc, str(HERE / "helmet_crown.stl"), tolerance=0.03, angularTolerance=0.1)
    asm = cq.Assembly()
    for name, part in pieces.items():
        asm.add(part, name=name)
    asm.save(str(HERE / "helmet_arch.step"))
    total = 0.0
    for name, part in pieces.items():
        v = part.val().Volume() / 1000
        total += v
        bbp = (pc if name == "helmet_crown" else part).val().BoundingBox()
        print("%-18s %6.1f cm3  %5.1f g PETG solid   print box %.1f x %.1f x %.1f mm" % (
            name, v, v * 1.27, bbp.xlen, bbp.ylen, bbp.zlen))
    lx, ly, lz = lens()
    print("total %.1f cm3, %.0f g solid PETG; lens at x %.1f z %.1f -> %.0f mm above the floor" % (
        total, total * 1.27, lx, lz, 836 + lz))
