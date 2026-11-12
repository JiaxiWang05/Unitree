"""Check the head Brio bracket: printable solid, the M4 holes as Unitree's, the camera's fit,
mass and where the weight sits. Run head_brio_mount.py first.

    python check_head_brio_mount.py [folder with Unitree's STEP]   # also writes the previews
"""
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import head_brio_mount as hb  # noqa: E402

PETG = 1.27e-3  # g per mm3
BRIO_G = 63.0   # Brio without its clip
problems = []


def need(ok, msg):
    if not ok:
        problems.append(msg)


def holes(mesh, radius, tol=0.15):
    """Near-vertical holes of this radius, from horizontal slices: {side: (x, y, z0, z1)}."""
    found = {}
    for z in np.arange(mesh.bounds[0][2] + 1, mesh.bounds[1][2] - 1, 0.5):
        sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is None:
            continue
        for e in sec.discrete:
            p = np.asarray(e)[:, :2]
            c = p.mean(0)
            r = np.linalg.norm(p - c, axis=1)
            if len(p) > 8 and abs(r.mean() - radius) < tol and r.std() < 0.1:
                found.setdefault(int(np.sign(c[1])), []).append((c[0], c[1], z))
    out = {}
    for side, rows in found.items():
        rows = np.array(rows)
        if len(rows) >= 3:
            out[side] = (rows[:, 0].mean(), rows[:, 1].mean(), rows[:, 2].min(), rows[:, 2].max())
    return out


def main():
    part = trimesh.load(HERE / "head_brio_mount.stl")
    brio = trimesh.load(HERE / "brio_dummy.stl")
    print("== solid")
    print("   watertight %s, one body %s, volume %.1f cm3, %.0f g in PETG" % (
        part.is_watertight, len(part.split()) == 1, part.volume / 1000, part.volume * PETG))
    need(part.is_watertight and len(part.split()) == 1, "not one watertight body")
    print("   size %.1f x %.1f x %.1f mm" % tuple(part.extents))

    print("== head screws (Unitree: 2 x M4, 88 mm apart)")
    h = holes(part, 2.25)
    for x, y, z0, z1 in sorted(h.values()):
        print("   hole 4.5 mm at x %.1f y %.1f, z %.1f..%.1f" % (x, y, z0, z1))
    ys = sorted(row[1] for row in h.values())
    need(len(ys) == 2 and abs(ys[1] - ys[0] - 2 * hb.M4_Y) < 0.2, "M4 holes are not 88 mm apart: %s" % ys)
    if len(sys.argv) > 1:
        import cadquery as cq
        v, f = hb.unitree_back(hb.unitree_step(Path(sys.argv[1]))).val().tessellate(0.05)
        back = trimesh.Trimesh([[p.x, p.y, p.z] for p in v], f)
        keep = part.sample(40000)
        keep = keep[keep[:, 0] < 44.0]
        _, d, _ = trimesh.proximity.closest_point(back, keep)
        print("   back half (x < 44) differs from Unitree's part by at most %.3f mm" % d.max())
        need(d.max() < 0.1, "the back half no longer matches Unitree's part")

    print("== camera")
    pts = brio.sample(30000)
    inside = part.contains(pts)
    print("   Brio and plug points inside the bracket: %d of %d" % (inside.sum(), len(pts)))
    need(inside.sum() == 0, "the Brio or its plug cuts into the bracket")
    _, d, _ = trimesh.proximity.closest_point(part, pts[pts[:, 2] > hb.SEAT_Z + hb.LIP_H + 0.5])
    print("   camera above the lips: %.2f mm clear of the bracket" % d.min())
    cx = hb.SHELF_X0 + hb.LIP_T + hb.THREAD_FROM_BACK
    print("   tripod screw at x %.1f (slot +/-%.0f mm), plastic under the camera %.1f mm" % (cx, hb.SLOT_PLAY / 2, hb.SHELF_T))
    print("   camera: back face x %.1f, lens face x %.1f, underside z %.1f, top z %.1f" % (
        hb.SHELF_X0 + hb.LIP_T, hb.SHELF_X0 + hb.LIP_T + hb.CAM_D, hb.SEAT_Z, hb.SEAT_Z + hb.CAM_H))
    print("   Unitree's tray reached x 79.1, z 118.2; this bracket reaches x %.1f, z %.1f (without the camera)" % (
        part.bounds[1][0], part.bounds[1][2]))

    print("== load")
    m_part, m_cam = part.volume * PETG, BRIO_G
    com = (part.center_mass * m_part + np.array([hb.SHELF_X0 + hb.LIP_T + hb.CAM_D / 2, 0, hb.SEAT_Z + hb.CAM_H / 2]) * m_cam) / (m_part + m_cam)
    arm = com[0] - hb.M4_X
    print("   bracket %.0f g + Brio %.0f g = %.0f g, centre of mass %.0f mm in front of the M4 screws" % (m_part, m_cam, m_part + m_cam, arm))
    # bending at the thin bridge (Unitree's own section, 33 x 4.6 mm at x 30) under 3 g
    w, t = 33.0, 4.6
    moment = 3 * 9.81 * (m_cam / 1000 * (hb.SHELF_X0 + hb.LIP_T + hb.CAM_D / 2 - 30) + 0.012 * 45)  # N mm, camera + front of bracket
    stress = moment / (w * t ** 2 / 6)
    print("   bridge at x 30 under 3 g: %.1f MPa (PETG yields near 45 MPa)" % stress)
    need(stress < 15, "bridge stress %.1f MPa is high" % stress)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        fig = plt.figure(figsize=(16, 6))
        for i, (el, az, title) in enumerate(((20, -60, "front left"), (0, -90, "side"), (25, 120, "back"))):
            ax = fig.add_subplot(1, 3, i + 1, projection="3d")
            for mesh, col, a in ((part, "#8a8f98", 1.0), (brio, "#222222", 0.55)):
                m = mesh
                pc = Poly3DCollection(m.vertices[m.faces], facecolor=col, edgecolor="none", alpha=a)
                pc.set_facecolor(np.clip(np.outer(0.55 + 0.45 * np.abs(m.face_normals @ [0.3, -0.5, 0.8]), matplotlib.colors.to_rgb(col)), 0, 1))
                ax.add_collection3d(pc)
            ax.set_xlim(0, 110); ax.set_ylim(-55, 55); ax.set_zlim(70, 150)
            ax.set_box_aspect((110, 110, 80), zoom=1.5); ax.view_init(el, az); ax.set_title(title); ax.set_axis_off()
        fig.savefig(HERE / "preview_part.png", dpi=110, bbox_inches="tight")
        print("== wrote preview_part.png")
    except Exception as exc:  # the checks above don't depend on the picture
        print("== no preview: %s" % exc)

    print("ALL CLEAR" if not problems else "PROBLEMS:\n  - " + "\n  - ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
