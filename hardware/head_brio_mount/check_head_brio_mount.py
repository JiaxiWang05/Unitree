"""Check the head Brio bracket: printable solid, the M4 holes as Unitree's, the camera's fit,
how it sits in Unitree's public head model, the depth camera's view past it, and the load.
Run head_brio_mount.py first.

    python check_head_brio_mount.py <folder with Unitree's STEP> <folder with head_link.STL>

The second folder is the one docs/src/fetch_g1_model.py fills. Without it the head checks are
skipped. Also writes preview_part.png and preview_in_head.png.
"""
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "helmet_ring_mount"))
import head_brio_mount as hb  # noqa: E402

PETG = 1.27e-3  # g per mm3
BRIO_G = 63.0   # Brio without its clip
FLOOR_Z = -836.0  # floor in the torso frame, robot standing (as check_helmet_arch.py)
SHIFT = np.array(hb.HEAD_SHIFT)
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


class Occupancy:
    """Which 1.5 mm cells around the brow are inside the head: fast 'is this point in the head'."""

    def __init__(self, head, lo=(-40.0, -66.0, 372.0), hi=(140.0, 66.0, 486.0), h=1.5):
        import shapely

        self.lo, self.h = np.array(lo), h
        self.n = np.ceil((np.array(hi) - self.lo) / h).astype(int)
        gx, gy, gz = [self.lo[i] + (np.arange(self.n[i]) + 0.5) * h for i in range(3)]
        grid = np.stack(np.meshgrid(gx, gy, indexing="ij"), -1).reshape(-1, 2)
        self.occ = np.zeros(self.n, bool)
        for k, z in enumerate(gz):
            sec = head.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            if sec is None:
                continue
            planar, to3d = sec.to_2D()
            p3 = np.c_[grid, np.full(len(grid), z), np.ones(len(grid))]
            p2 = (np.linalg.inv(to3d) @ p3.T).T[:, :2]
            poly = shapely.unary_union(list(planar.polygons_full))
            self.occ[:, :, k] = shapely.contains_xy(poly, p2[:, 0], p2[:, 1]).reshape(self.n[0], self.n[1])

    def inside(self, pts):
        i = np.floor((pts - self.lo) / self.h).astype(int)
        ok = ((i >= 0) & (i < self.n)).all(1)
        out = np.zeros(len(pts), bool)
        out[ok] = self.occ[i[ok, 0], i[ok, 1], i[ok, 2]]
        return out


def blocked(meshes, origin, targets):
    """True for each sight line from origin to a target that hits any of the meshes."""
    dirs = targets - origin
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    start = origin + dirs * 8.0  # the lens sits a few mm behind the brow surface in the model
    hit = np.zeros(len(targets), bool)
    for m in meshes:
        _, idx, _ = trimesh.ray.ray_triangle.RayMeshIntersector(m).intersects_location(start, dirs, multiple_hits=False)
        hit[idx] = True
    return hit


def head_checks(part, brio, official, mesh_dir):
    import check_trial_feet as ctf

    head = ctf.mm(trimesh.load(mesh_dir / "head_link.STL"))
    head.apply_translation(ctf.HEAD_OFFSET)
    occ = Occupancy(head)
    print("== in Unitree's public head model (torso frame = bracket frame + %s)" % (hb.HEAD_SHIFT,))
    # 1. is the placement right? Unitree's own mount must fit there, and nowhere higher
    pts = official.sample(20000)
    fits = {(dx, dz): int(occ.inside(pts + SHIFT + [dx, 0, dz]).sum()) for dx in (-3, 0, 3) for dz in (0, 2, 4)}
    print("   Unitree's mount: %d of 20000 points in the head here; 2 mm higher %d; 3 mm back %d; 3 mm forward %d" % (
        fits[(0, 0)], fits[(0, 2)], fits[(-3, 2)], fits[(3, 2)]))
    need(fits[(0, 0)] <= 30, "Unitree's own mount does not fit at HEAD_SHIFT")
    need(min(fits[(0, 2)], fits[(-3, 2)], fits[(3, 2)]) > 60, "Unitree's mount also fits higher: HEAD_SHIFT is not pinned down")
    # 2. this bracket and the camera
    world = {"bracket": part.copy(), "Brio and adapter": brio.copy(), "Unitree's mount": official.copy()}
    for m in world.values():
        m.apply_translation(SHIFT)
    for name in ("bracket", "Brio and adapter"):
        p = world[name].sample(40000)
        n_in = int(occ.inside(p).sum())
        print("   %s: %d of 40000 points in the head" % (name, n_in))
        need(n_in <= 40, "%s cuts into the head (%d points)" % (name, n_in))
    front = world["bracket"].sample(60000)
    front = front[front[:, 0] > hb.BAR_X1 + SHIFT[0] + 3.0]  # the new part in front of the crossbar
    for name, pts in (("bracket in front of the crossbar", front), ("Brio and adapter", world["Brio and adapter"].sample(20000))):
        _, d, _ = trimesh.proximity.closest_point(head, pts)
        print("   %s: %.1f mm clear of the head" % (name, d.min()))
        need(d.min() >= 3.0, "%s only %.1f mm from the head" % (name, d.min()))
    # 3. the depth camera's view of the talk spot (0.6-1.4 m ahead, 0.6 m to each side), from both imagers
    xs, ys = np.meshgrid(np.linspace(600, 1400, 41), np.linspace(-600, 600, 61))
    spot = np.c_[xs.ravel(), ys.ravel(), np.full(xs.size, FLOOR_Z)]
    left = np.array(hb.DEPTH_CAM)
    eyes = {"left imager": left, "right imager": left - [0, hb.DEPTH_BASELINE, 0], "midway": left - [0, hb.DEPTH_BASELINE / 2, 0]}
    print("== depth camera's sight lines to the talk spot (%d per imager)" % len(spot))
    for name, eye in eyes.items():
        ours = blocked([world["bracket"], world["Brio and adapter"]], eye, spot.copy())
        theirs = blocked([world["Unitree's mount"]], eye, spot.copy())
        print("   %-13s blocked by this bracket and the Brio: %4d   by Unitree's own mount: %4d" % (name + ":", ours.sum(), theirs.sum()))
        need(ours.sum() == 0, "%d talk-spot sight lines from the %s are blocked" % (ours.sum(), name))
    # the whole depth image, for the record (58 deg tall, 87 deg wide, pitched 47.6 deg down)
    el = np.radians(47.6 + np.linspace(-29, 29, 41))[:, None]
    az = np.radians(np.linspace(-43.5, 43.5, 61))[None, :]
    d = np.stack([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), -np.sin(el) * np.ones_like(az)], -1).reshape(-1, 3)
    whole = blocked([world["bracket"], world["Brio and adapter"]], left, left + d * 1000.0)
    print("   whole depth image from the left imager: %.1f%% of it shows the bracket or the camera" % (100 * whole.mean()))
    lens = SHIFT + [hb.SHELF_X0 + hb.LIP_T + hb.CAM_D, 0, hb.SEAT_Z + hb.CAM_H / 2]
    print("   Brio lens: %.0f mm in front of the torso origin, %.2f m above the floor" % (lens[0], (lens[2] - FLOOR_Z) / 1000))
    return head, world


def picture(path, meshes, lim, views, title=None):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(6 * len(views), 6))
    for i, (el, az, name) in enumerate(views):
        ax = fig.add_subplot(1, len(views), i + 1, projection="3d")
        for mesh, col, alpha in meshes:
            pc = Poly3DCollection(mesh.vertices[mesh.faces], edgecolor="none", alpha=alpha)
            shade = 0.5 + 0.5 * np.abs(mesh.face_normals @ [0.3, -0.5, 0.8])
            pc.set_facecolor(np.clip(np.outer(shade, matplotlib.colors.to_rgb(col)), 0, 1))
            ax.add_collection3d(pc)
        (x0, x1), (y0, y1), (z0, z1) = lim
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_zlim(z0, z1)
        ax.set_box_aspect((x1 - x0, y1 - y0, z1 - z0), zoom=1.15)
        ax.view_init(el, az); ax.set_title(name); ax.set_axis_off()
    if title:
        fig.suptitle(title, fontsize=11)
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)


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
    official = None
    if len(sys.argv) > 1:
        import cadquery as cq

        step = hb.unitree_step(Path(sys.argv[1]))
        v, f = hb.unitree_back(step).val().tessellate(0.05)
        back = trimesh.Trimesh([[p.x, p.y, p.z] for p in v], f)
        keep = part.sample(40000)
        keep = keep[keep[:, 0] < 44.0]
        _, d, _ = trimesh.proximity.closest_point(back, keep)
        print("   back half (x < 44) differs from Unitree's part by at most %.3f mm" % d.max())
        need(d.max() < 0.1, "the back half no longer matches Unitree's part")
        v, f = cq.importers.importStep(str(step)).rotate((0, 0, 0), (0, 0, 1), 180).val().tessellate(0.1, 0.2)
        official = trimesh.Trimesh([[p.x, p.y, p.z] for p in v], f)

    print("== camera")
    pts = brio.sample(30000)
    inside = part.contains(pts)
    print("   Brio and adapter points inside the bracket: %d of %d" % (inside.sum(), len(pts)))
    need(inside.sum() == 0, "the Brio or its adapter cuts into the bracket")
    cx = hb.SHELF_X0 + hb.LIP_T + hb.THREAD_FROM_BACK
    print("   tripod screw at x %.1f (slot +/-%.0f mm), plastic under the camera %.1f mm" % (cx, hb.SLOT_PLAY / 2, hb.SHELF_T))
    print("   camera: back face x %.1f, lens face x %.1f, underside z %.1f, top z %.1f" % (
        hb.SHELF_X0 + hb.LIP_T, hb.SHELF_X0 + hb.LIP_T + hb.CAM_D, hb.SEAT_Z, hb.SEAT_Z + hb.CAM_H))

    print("== load")
    m_part, m_cam = part.volume * PETG, BRIO_G
    cam_x = hb.SHELF_X0 + hb.LIP_T + hb.CAM_D / 2
    com = (part.center_mass * m_part + np.array([cam_x, 0, hb.SEAT_Z + hb.CAM_H / 2]) * m_cam) / (m_part + m_cam)
    print("   bracket %.0f g + Brio %.0f g = %.0f g, centre of mass %.0f mm in front of the M4 screws" % (
        m_part, m_cam, m_part + m_cam, com[0] - hb.M4_X))
    # bending at Unitree's thin bridge (33 x 4.6 mm at x 30) under 3 g: everything in front of it
    ahead = part.slice_plane([30, 0, 0], [1, 0, 0], cap=True)
    moment = 3 * 9.81e-3 * (m_cam * (cam_x - 30) + ahead.volume * PETG * (ahead.center_mass[0] - 30))  # N mm
    stress = moment / (33.0 * 4.6 ** 2 / 6)
    print("   Unitree's bridge at x 30 under 3 g: %.1f MPa (PETG yields near 45 MPa)" % stress)
    need(stress < 12, "bridge stress %.1f MPa is high" % stress)

    views = ((20, -60, "front left"), (0, -90, "left side; front is right"), (25, 120, "back"))
    world = None
    if official is not None and len(sys.argv) > 2:
        head, world = head_checks(part, brio, official, Path(sys.argv[2]))
    else:
        print("== head checks skipped (give both folders)")
    try:
        picture(HERE / "preview_part.png", [(part, "#7a52d6", 1.0), (brio, "#1c1e22", 0.9)], ((0, 130), (-65, 65), (60, 160)), views)
        if world:
            picture(HERE / "preview_in_head.png",
                    [(head, "#b9bdc6", 0.35), (world["bracket"], "#7a52d6", 1.0), (world["Brio and adapter"], "#1c1e22", 0.95)],
                    ((-70, 140), (-105, 105), (330, 500)), ((14, -52, "front left"), (0, -90, "left side; front is right"), (18, 38, "front right")),
                    "In Unitree's public head model (approximate: the model has no screw holes)")
        print("== wrote the previews")
    except Exception as exc:  # the checks above don't depend on the pictures
        print("== no preview: %s" % exc)

    print("ALL CLEAR" if not problems else "PROBLEMS:\n  - " + "\n  - ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
