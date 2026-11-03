"""Chest bracket for a Logitech Brio 4K on a Unitree G1 (two lower front M6 holes).

Coordinates are the G1 torso_link frame from unitree_ros (mm): x forward, y left, z up.
Hole positions come from Unitree's front drawing (4-M6; lower pair 64.5 mm apart, 194.2 mm
below the upper pair) and the chest surface from torso_link_23dof_rev_1_0.STL.

The Brio's 1/4"-20 tripod thread is under the camera body, hidden by its clip (Logitech:
remove the clip and the thread is exposed), so the clip comes off and the bare camera sits on
a seat tilted TILT_DEG upwards, held by one screw from below. The thread sits about 14.5 mm in
front of the camera's back face and is shallow (a thin steel plate held in with tape), so the
screw only goes SCREW_IN mm into it. The USB-C socket is low on the back face, so the back lip
has a gap for the plug and the shelf behind the camera is open for the plug and the cable bend.

    python brio_chest_mount.py            # writes brio_chest_mount.step / .stl next to this file
"""
import math
from pathlib import Path

import cadquery as cq

# ---- robot (measured from Unitree's model and drawing) ----
HOLE_SPACING = 64.5          # lower M6 pair, centre to centre
HOLE_Z = 110.0               # torso frame; drawing gives 104-112
SURFACE_X = 65.1             # chest surface at the holes
HOLE_NORMAL = (0.990, 0.106, -0.088)   # local surface normal at the +y hole (mirror for -y)

# ---- Brio 4K body with the clip removed (Logitech, 960-001746: 102 x 27 x 26.5 deep) ----
CAM_W, CAM_D, CAM_H = 102.0, 27.0, 27.0   # width, front to back (0.5 spare), height
THREAD_FROM_BACK = 14.5      # tripod thread centre to the camera's back face (+/-1)
USB_Z, PLUG_W, PLUG_T, PLUG_L = 7.0, 13.0, 7.0, 35.0  # socket centre above the underside; plug body

# ---- bracket ----
PAD_D, PAD_T = 18.0, 12.0    # round pads that sit on the chest around each hole
BOLT_HOLE = 7.5              # M6 clearance, generous so a few degrees of hole angle still fits
SEAT_D, SEAT_T = 15.0, 10.0  # flat seat for the M6 washer, 10 mm from the chest
RISER_W, RISER_T = 84.0, 5.0
RISER_GAP = 5.0              # riser back face to chest plane (chest bulges <= 1.7 mm between holes)
SHELF_Z = 120.0              # top of the flat shelf (torso frame) -> about 0.95 m above the floor;
                             # low enough that the head depth camera still sees the talk spot past the Brio
SHELF_T, SHELF_W = 6.0, 46.0
SHELF_D = 96.7               # long enough for the straight USB-C plug and a ~24 mm cable bend behind the camera
TILT_DEG = 20.0              # camera looks up this much, so faces stay in frame near the robot
SEAT_MIN = 2.0               # wedge thickness at the back of the camera seat
SEAT_SETBACK = 3.0           # seat front this far behind the shelf front
WEDGE_W = SHELF_W - 8.0      # stays inside the shelf's rounded corners
LIP_H, LIP_T = 4.0, 3.0      # front and back lips stop the camera turning on its one screw
LIP_GAP = CAM_D + 1.0
BACK_LIP_GAP = 20.0          # the USB-C plug goes out through this gap in the back lip
CHANNEL_W = 24.0             # open slot through the shelf behind the seat for the plug and cable
SLOT_W, SLOT_PLAY = 7.0, 6.0  # 1/4" screw slot; the play allows for where the thread really is
SCREW_L, WASHER_T, SCREW_IN = 15.875, 1.6, 4.0  # 5/8" screw, one M6 washer, depth into the camera
SPOT_D = 16.0                # flat spot face for the screw head and washer
GRIP = SCREW_L - WASHER_T - SCREW_IN   # plastic between the spot face and the camera seat
RIB_T, RIB_Y, RIB_DROP = 4.0, 17.0, 38.0


def v(*a):
    return cq.Vector(*a)


def mount_plane_x(z):
    """x of the riser's back face at height z (it leans forward with the chest, about 5 deg)."""
    nx, nz = 0.996, -0.088
    return SURFACE_X + RISER_GAP / nx + (z - HOLE_Z) * (-nz / nx)


def shelf_back():
    return mount_plane_x(SHELF_Z) + RISER_T - 1.0


def seat_plane():
    """The camera seat's top surface: origin at its back edge, local x up the slope, local y = y."""
    t = math.radians(TILT_DEG)
    length = 2 * LIP_T + LIP_GAP
    x0 = shelf_back() + SHELF_D - SEAT_SETBACK - length * math.cos(t)
    plane = cq.Plane(origin=v(x0, 0, SHELF_Z + SEAT_MIN), xDir=v(math.cos(t), 0, math.sin(t)),
                     normal=v(-math.sin(t), 0, math.cos(t)))
    assert (plane.yDir - v(0, 1, 0)).Length < 1e-6
    return plane, length


def camera_pose():
    """Where the bare Brio sits (slid back against the back lip, as it does on the slope):
    centre of its front face, centre of its body, tilt in degrees."""
    plane, _ = seat_plane()
    uc = LIP_T + CAM_D / 2
    front = plane.toWorldCoords((uc + CAM_D / 2, 0, CAM_H / 2))
    body = plane.toWorldCoords((uc, 0, CAM_H / 2))
    return front, body, TILT_DEG


def screw_u():
    """Screw slot centre along the seat, from the seat's back edge."""
    return LIP_T + THREAD_FROM_BACK


def pad(side):
    n = v(HOLE_NORMAL[0], side * HOLE_NORMAL[1], HOLE_NORMAL[2]).normalized()
    centre = v(SURFACE_X, side * HOLE_SPACING / 2, HOLE_Z)
    plane = cq.Plane(origin=centre, xDir=v(0, 0, 1).cross(n), normal=n)
    body = cq.Workplane(plane).circle(PAD_D / 2).extrude(PAD_T)
    hole = cq.Workplane(plane).workplane(offset=-5).circle(BOLT_HOLE / 2).extrude(PAD_T + 40)
    seat = cq.Workplane(plane).workplane(offset=SEAT_T).circle(SEAT_D / 2).extrude(40)
    return body, hole, seat


def riser():
    z0, z1 = HOLE_Z - 14.0, SHELF_Z
    n = v(0.996, 0, -0.088).normalized()
    up = v(-n.z, 0, n.x)  # along the chest, upwards
    origin = v(mount_plane_x(z0), 0, z0)
    plane = cq.Plane(origin=origin, xDir=up.cross(n), normal=n)  # local y = up
    assert (plane.yDir - up).Length < 1e-6
    length = (z1 - z0) / up.z
    return (cq.Workplane(plane).center(0, length / 2).rect(RISER_W, length).extrude(RISER_T)
            .edges(cq.selectors.ParallelDirSelector(n)).fillet(4))


def shelf():
    x_back = shelf_back()
    s = (cq.Workplane("XY").workplane(offset=SHELF_Z - SHELF_T)
         .center(x_back + SHELF_D / 2, 0).rect(SHELF_D, SHELF_W).extrude(SHELF_T)
         .edges("|Z").fillet(4))
    # wedge on the shelf whose top is the tilted camera seat
    plane, length = seat_plane()
    t = math.radians(TILT_DEG)
    x0, x1 = plane.origin.x, plane.origin.x + length * math.cos(t)
    wedge = (cq.Workplane("XZ")
             .polyline([(x0, SHELF_Z - 0.5), (x1, SHELF_Z - 0.5),
                        (x1, SHELF_Z + SEAT_MIN + length * math.sin(t)), (x0, SHELF_Z + SEAT_MIN)])
             .close().extrude(WEDGE_W / 2, both=True))
    s = s.union(wedge)
    s = s.union(cq.Workplane(plane).center(length - LIP_T / 2, 0).rect(LIP_T, WEDGE_W).extrude(LIP_H))
    back_w = (WEDGE_W - BACK_LIP_GAP) / 2
    for side in (1, -1):
        s = s.union(cq.Workplane(plane).center(LIP_T / 2, side * (BACK_LIP_GAP + back_w) / 2)
                    .rect(LIP_T, back_w).extrude(LIP_H))
    # open channel through the shelf behind the seat, for the plug and the cable bend
    s = s.cut(cq.Workplane("XY").workplane(offset=SHELF_Z - SHELF_T - 1)
              .center((x_back + 3 + x0) / 2, 0).rect(x0 - x_back - 3, CHANNEL_W).extrude(SHELF_T + 2)
              .edges("|Z").fillet(3))
    # screw slot square to the seat, under the thread, and a flat face for its head and washer
    uc = screw_u()
    slot = (cq.Workplane(plane).workplane(offset=10).center(uc, 0)
            .slot2D(SLOT_W + SLOT_PLAY, SLOT_W).extrude(-80))
    spot = (cq.Workplane(plane).workplane(offset=-GRIP).center(uc, 0)
            .slot2D(SPOT_D + SLOT_PLAY, SPOT_D).extrude(-60))
    return s.cut(slot).cut(spot), x_back


def ribs(x_back):
    out = None
    z_top = SHELF_Z - SHELF_T + 0.5
    for side in (1, -1):
        pts = [(mount_plane_x(z_top) + 1, z_top), (x_back + SHELF_D - 8, z_top),
               (mount_plane_x(z_top - RIB_DROP) + 1, z_top - RIB_DROP)]
        r = (cq.Workplane("XZ", origin=(0, side * RIB_Y + RIB_T / 2, 0))
             .polyline(pts).close().extrude(RIB_T))
        out = r if out is None else out.union(r)
    return out


def build():
    part = riser()
    s, x_back = shelf()
    part = part.union(s).union(ribs(x_back))
    cuts = []
    for side in (1, -1):
        body, hole, seat = pad(side)
        part = part.union(body)
        cuts += [hole, seat]
    for c in cuts:
        part = part.cut(c)
    # flat bottom edge so it can print standing up
    part = part.cut(cq.Workplane("XY").workplane(offset=HOLE_Z - 200).rect(400, 400).extrude(200 - 13.0))
    assert len(part.solids().vals()) == 1, "bracket must be one piece"
    return part


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    part = build()
    cq.exporters.export(part, str(here / "brio_chest_mount.step"))
    cq.exporters.export(part, str(here / "brio_chest_mount.stl"), tolerance=0.05, angularTolerance=0.1)
    bb = part.val().BoundingBox()
    print("volume %.1f cm3, bbox %.1f x %.1f x %.1f mm" % (part.val().Volume() / 1000, bb.xlen, bb.ylen, bb.zlen))
