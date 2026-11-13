"""Head bracket for a Logitech Brio 4K inside the G1's renewed head (88 mm), after Unitree's
own stereo camera mount (xr_teleoperate, Device.md section 5.2.1).

The back half IS Unitree's part: the flange with the two vertical M4 holes 88 mm apart, the thin
bridge and the two arms that hook under the top of the face ring. That half is known to fit the
renewed head, and the public G1 model has no detail there to draw it from. Only the front changes:
Unitree's tilted tray for the stereo board (49 deg down) covers the built-in depth camera's
window. It is cut off and replaced by a crossbar under the brow, a plate up each side of that
window and a level seat above it for the bare Brio (clip removed, one 1/4" screw from below, as
on the chest bracket), so the depth camera keeps its view of the talk spot.

Frame used here (mm): X forward, Y left, Z up. It is Unitree's STEP frame turned 180 deg about Z.

    python head_brio_mount.py [folder to keep Unitree's STEP in]

Downloads Unitree's zip once (480 kB) and writes head_brio_mount.step / .stl (as mounted),
head_brio_mount_print.stl (lowest point on the bed) and brio_dummy.stl next to this file.
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import cadquery as cq

UNITREE_ZIP = "https://oss-global-cdn.unitree.com/static/950f53b95d5943589e278241b59c86ff.zip"
UNITREE_STEP = "stero-camera-mount-60hz-88.step"

# ---- kept from Unitree's part ----
CUT_X = 52.0                 # everything in front of this goes (the tray and its lower lip) ...
CUT_X_HIGH, CUT_Z_HIGH = 49.0, 99.0   # ... and the tray's root above the arms
TRIM_X, TRIM_Y = 46.5, 16.6    # ... and the tray's fillets beside the arms
M4_Y, M4_X = 44.0, 10.5      # the two head screws (checked below against the imported part)

# ---- Brio 4K body with the clip removed (as hardware/brio_chest_mount) ----
CAM_W, CAM_D, CAM_H = 102.0, 27.0, 27.0
THREAD_FROM_BACK = 14.5      # tripod thread centre to the camera's back face (+/-1)
USB_Z, PLUG_W, PLUG_T = 7.0, 13.0, 7.0

# ---- where this sits in Unitree's public G1 model (torso frame = this frame + HEAD_SHIFT) ----
# Found by sliding Unitree's own mount inside head_link.STL until it stops against the head
# without cutting into it: it fits in one place only, 0.4 mm clear (check_head_brio_mount.py).
HEAD_SHIFT = (0.5, 0.0, 317.0)
DEPTH_CAM = (57.6235, 17.53, 429.87)   # URDF d435_joint, torso frame; looks 47.6 deg down
DEPTH_BASELINE = 50.0                  # the D435i's two infrared imagers, 50 mm apart

# ---- new front (version 2) ----
# Version 1 put two struts and the seat straight in front of the brow, where the depth camera's
# window is: the camera's back and plug cut 11 mm into the head and 41% of the depth camera's
# sight lines to the talk spot were blocked. Version 2 goes round the window: a crossbar below
# and behind the lens, a plate up each side of the view, and the seat above the lens height.
ARM_Y1 = 16.0                # Unitree's arms end at |y| 6..16
BAR_X0, BAR_X1 = 51.5, 59.0  # crossbar: in front of the face ring's sides, behind the steepest depth ray
BAR_X0_MID, BAR_MID_Y = 46.0, 30.0   # ... and further back between the arms, to join them
BAR_Z0, BAR_Z1 = 81.0, 90.0
PLATE_Y0, PLATE_Y1 = 52.0, 58.0      # side plates: outside the head's widest point in front (49-53)
SEAT_Z = 126.0               # camera underside = 443 in the torso frame, 13 mm above the depth lens
SCREW_L, WASHER_T, SCREW_IN = 15.875, 1.6, 4.0   # 1/4"-20 x 5/8", one M6 washer, depth in the camera
SHELF_T = SCREW_L - WASHER_T - SCREW_IN           # 10.3 mm under the screw: its head sits on the underside
SHELF_THIN = 5.0             # the rest of the shelf
SHELF_X0 = 90.5              # back of the shelf: the camera's back face is 16 mm in front of the forehead
SHELF_MID_W = 46.0           # thick middle of the shelf
LIP_T, LIP_H = 3.0, 4.0
LIP_GAP = CAM_D + 1.0
BACK_LIP_GAP = 20.0          # the USB-C plug leaves through this gap
SLOT_W, SLOT_PLAY = 7.0, 6.0
TIE_W, TIE_L = 2.5, 6.0      # cable-tie slots through the shelf, one each side
SHELF_X1 = SHELF_X0 + 2 * LIP_T + LIP_GAP
SHELF_Z0 = SEAT_Z - SHELF_T
PLATE = [(BAR_X0, BAR_Z0), (BAR_X1, BAR_Z0), (SHELF_X0 + 14.0, SEAT_Z - SHELF_THIN), (SHELF_X0 + 14.0, SEAT_Z),
         (SHELF_X0 - 2.0, SEAT_Z), (BAR_X0, BAR_Z1)]   # XZ outline of each side plate
ADAPTER_L = 13.0             # right-angle USB-C adapter: how far it stands off the camera's back


def unitree_step(cache: Path) -> Path:
    path = cache / UNITREE_STEP
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(UNITREE_ZIP, timeout=60) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        name = next(n for n in z.namelist() if n.endswith(UNITREE_STEP))
        path.write_bytes(z.read(name))
    return path


def unitree_back(step: Path):
    """Unitree's mount turned into this frame, without the camera tray."""
    part = cq.importers.importStep(str(step)).rotate((0, 0, 0), (0, 0, 1), 180)
    big = 400.0
    part = part.cut(cq.Workplane("XY").box(big, big, big, centered=(False, True, True)).translate((CUT_X, 0, 0)))
    part = part.cut(cq.Workplane("XY").box(big, big, big, centered=(False, True, False)).translate((CUT_X_HIGH, 0, CUT_Z_HIGH)))
    for side in (1, -1):  # what is left of the tray's fillets outside the arms
        part = part.cut(cq.Workplane("XY").box(big, big, big, centered=(False, False, True))
                        .translate((TRIM_X, TRIM_Y if side == 1 else -TRIM_Y - big, 0)))
    return part


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def front():
    # crossbar under the brow
    out = box(BAR_X0, BAR_X1, -PLATE_Y1, PLATE_Y1, BAR_Z0, BAR_Z1)
    out = out.union(box(BAR_X0_MID, BAR_X1, -BAR_MID_Y, BAR_MID_Y, BAR_Z0, BAR_Z1))
    # a plate up each side of the depth camera's view
    for side in (1, -1):
        y = PLATE_Y1 if side == 1 else -PLATE_Y0
        out = out.union(cq.Workplane("XZ", origin=(0, y, 0)).polyline(PLATE).close().extrude(PLATE_Y1 - PLATE_Y0))
    # shelf between the plates: thin, with a thick middle for the screw
    out = out.union(box(SHELF_X0, SHELF_X1, -PLATE_Y1, PLATE_Y1, SEAT_Z - SHELF_THIN, SEAT_Z))
    out = out.union(box(SHELF_X0, SHELF_X1, -SHELF_MID_W / 2, SHELF_MID_W / 2, SHELF_Z0, SEAT_Z))
    # lips: full width in front, two pieces behind with a gap for the plug
    out = out.union(box(SHELF_X1 - LIP_T, SHELF_X1, -PLATE_Y1, PLATE_Y1, SEAT_Z - 0.5, SEAT_Z + LIP_H))
    for side in (1, -1):
        y0, y1 = (BACK_LIP_GAP / 2, PLATE_Y1) if side == 1 else (-PLATE_Y1, -BACK_LIP_GAP / 2)
        out = out.union(box(SHELF_X0, SHELF_X0 + LIP_T, y0, y1, SEAT_Z - 0.5, SEAT_Z + LIP_H))
    cx = SHELF_X0 + LIP_T + THREAD_FROM_BACK
    out = out.cut(cq.Workplane("XY").workplane(offset=SHELF_Z0 - 5).center(cx, 0)
                  .slot2D(SLOT_W + SLOT_PLAY, SLOT_W).extrude(SHELF_T + 10))
    for side in (1, -1):
        out = out.cut(cq.Workplane("XY").workplane(offset=SEAT_Z - SHELF_THIN - 1)
                      .center(SHELF_X0 + 14.0, side * (SHELF_MID_W / 2 + 8.0)).rect(TIE_L, TIE_W).extrude(SHELF_THIN + 2))
    return out


def brio_dummy():
    """The bare camera on the seat, against the back lip, with a right-angle USB-C adapter
    behind it (the cable leaves sideways)."""
    x0 = SHELF_X0 + LIP_T
    cam = cq.Workplane("XY").box(CAM_D, CAM_W, CAM_H, centered=(False, True, False)).translate((x0, 0, SEAT_Z))
    plug = cq.Workplane("XY").box(ADAPTER_L, PLUG_W, PLUG_T + 3, centered=(False, True, True)).translate((x0 - ADAPTER_L, 0, SEAT_Z + USB_Z))
    return cam.union(plug)


def build(step: Path):
    back = unitree_back(step)
    part = back.union(front())
    solids = part.solids().vals()
    assert len(solids) == 1, "bracket must be one piece, got %d" % len(solids)
    return part, back


def closed_mesh(part):
    """Triangles for printing. Unitree's STEP leaves a few hairline cracks (under 0.3 mm long)
    when meshed, in the part we keep, so the mesh is closed with MeshFix; it moves nothing by
    more than 0.03 mm."""
    import numpy as np
    import pymeshfix
    import trimesh

    v, f = part.val().tessellate(0.05, 0.1)
    raw = trimesh.Trimesh([[p.x, p.y, p.z] for p in v], f)
    raw.merge_vertices(digits_vertex=4)
    v2, f2 = pymeshfix.clean_from_arrays(np.ascontiguousarray(raw.vertices, dtype=np.float64),
                                         np.ascontiguousarray(raw.faces, dtype=np.int32))
    mesh = trimesh.Trimesh(v2, f2)
    assert mesh.is_watertight and len(mesh.split()) == 1, "mesh is not one closed body"
    assert abs(mesh.volume - raw.volume) < 5.0, "closing the mesh changed its volume"
    return mesh


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "unitree_ref"
    part, back = build(unitree_step(cache))
    cq.exporters.export(part, str(here / "head_brio_mount.step"))
    mesh = closed_mesh(part)
    mesh.export(here / "head_brio_mount.stl")
    flat = mesh.copy()
    flat.apply_translation((0, 0, -mesh.bounds[0][2]))
    flat.export(here / "head_brio_mount_print.stl")
    cq.exporters.export(brio_dummy(), str(here / "brio_dummy.stl"), tolerance=0.1)
    bb = part.val().BoundingBox()
    print("volume %.1f cm3, bbox x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f mm, %d triangles, closed" % (
        part.val().Volume() / 1000, bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax, len(mesh.faces)))
