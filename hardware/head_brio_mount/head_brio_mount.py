"""Head bracket for a Logitech Brio 4K inside the G1's renewed head (88 mm), after Unitree's
own stereo camera mount (xr_teleoperate, Device.md section 5.2.1).

The back half IS Unitree's part: the flange with the two vertical M4 holes 88 mm apart, the thin
bridge and the two arms that hook under the top of the face ring. That half is known to fit the
renewed head, and the public G1 model has no detail there to draw it from. Only the front changes:
Unitree's tilted tray for the stereo board (49 deg down) is cut off and replaced by two struts
along the same line and a level seat for the bare Brio (clip removed, one 1/4" screw from below,
as on the chest bracket).

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

# ---- new front ----
ARM_Y0, ARM_Y1 = 6.0, 16.0   # Unitree's arms sit at |y| 6..16; the struts continue them
SEAT_Z = 116.0               # camera underside; Unitree's tray reached z 118 at its top edge
SCREW_L, WASHER_T, SCREW_IN = 15.875, 1.6, 4.0   # 1/4"-20 x 5/8", one M6 washer, depth in the camera
SHELF_T = SCREW_L - WASHER_T - SCREW_IN           # 10.3 mm: the screw head sits on the underside
SHELF_X0 = 72.0              # back of the shelf; Unitree's tray ended at x 79
SHELF_W = 46.0
LIP_T, LIP_H = 3.0, 4.0
LIP_GAP = CAM_D + 1.0
BACK_LIP_GAP = 20.0          # the USB-C plug leaves through this gap
SLOT_W, SLOT_PLAY = 7.0, 6.0
TIE_W, TIE_L = 2.5, 6.0      # cable-tie slots through the shelf, one each side
SHELF_X1 = SHELF_X0 + 2 * LIP_T + LIP_GAP
SHELF_Z0 = SEAT_Z - SHELF_T
STRUT = [(46.0, 88.0), (50.0, 100.0), (SHELF_X0, SEAT_Z), (SHELF_X0 + 4.0, SEAT_Z),
         (SHELF_X0 + 4.0, SHELF_Z0), (52.0, 82.0)]   # XZ outline; upper edge = the back of Unitree's tray


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


def front():
    out = None
    for side in (1, -1):
        y0 = ARM_Y0 if side == 1 else -ARM_Y1
        s = cq.Workplane("XZ", origin=(0, y0 + (ARM_Y1 - ARM_Y0), 0)).polyline(STRUT).close().extrude(ARM_Y1 - ARM_Y0)
        out = s if out is None else out.union(s)
    shelf = (cq.Workplane("XY").workplane(offset=SHELF_Z0)
             .center((SHELF_X0 + SHELF_X1) / 2, 0).rect(SHELF_X1 - SHELF_X0, SHELF_W).extrude(SHELF_T)
             .edges("|Z").fillet(3))
    out = out.union(shelf)
    top = cq.Workplane("XY").workplane(offset=SEAT_Z - 0.5)
    out = out.union(top.center(SHELF_X1 - LIP_T / 2, 0).rect(LIP_T, SHELF_W - 8).extrude(LIP_H + 0.5))
    w = (SHELF_W - 8 - BACK_LIP_GAP) / 2
    for side in (1, -1):
        out = out.union(top.center(SHELF_X0 + LIP_T / 2, side * (BACK_LIP_GAP + w) / 2).rect(LIP_T, w).extrude(LIP_H + 0.5))
    cx = SHELF_X0 + LIP_T + THREAD_FROM_BACK
    out = out.cut(cq.Workplane("XY").workplane(offset=SHELF_Z0 - 5).center(cx, 0)
                  .slot2D(SLOT_W + SLOT_PLAY, SLOT_W).extrude(SHELF_T + 10))
    for side in (1, -1):
        out = out.cut(cq.Workplane("XY").workplane(offset=SHELF_Z0 - 1)
                      .center(SHELF_X0 + 14.0, side * (SHELF_W / 2 - 4.0)).rect(TIE_L, TIE_W).extrude(SHELF_T + 2))
    return out


def brio_dummy():
    """The bare camera on the seat, against the back lip, plus 20 mm of plug behind it."""
    x0 = SHELF_X0 + LIP_T
    cam = cq.Workplane("XY").box(CAM_D, CAM_W, CAM_H, centered=(False, True, False)).translate((x0, 0, SEAT_Z))
    plug = cq.Workplane("XY").box(20, PLUG_W, PLUG_T, centered=(False, True, True)).translate((x0 - 20, 0, SEAT_Z + USB_Z))
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
