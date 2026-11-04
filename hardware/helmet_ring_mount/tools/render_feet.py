"""Preview images for the trial feet: the print plate, and the left foot on Unitree's model.

    python render_feet.py <helmet_ring_mount folder> <g1mesh folder>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

HERE, MESH = Path(sys.argv[1]), Path(sys.argv[2])
PURPLE, GREY, STEEL = np.array([0.50, 0.36, 0.86]), np.array([0.80, 0.81, 0.84]), np.array([0.55, 0.57, 0.60])
LIGHT = np.array([-0.35, -0.55, 0.76]); LIGHT /= np.linalg.norm(LIGHT)


def raster(items, view, up, res, box=None):
    """items: list of (mesh, rgb). Orthographic z-buffer with simple diffuse + rim shading."""
    d = np.asarray(view, float); d /= np.linalg.norm(d)
    u = np.asarray(up, float); u = u - d * (u @ d); u /= np.linalg.norm(u)
    r = np.cross(d, u)
    allv = np.vstack([m.vertices for m, _ in items])
    if box is not None:   # frame a world-space box instead of everything
        lo, hi = np.asarray(box[0], float), np.asarray(box[1], float)
        allv = np.array([[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])])
    P = np.stack([allv @ r, allv @ u], 1)
    x0, y0 = P.min(0) - 3; x1, y1 = P.max(0) + 3
    W, H = int((x1 - x0) / res), int((y1 - y0) / res)
    zb = np.full((H, W), np.inf); img = np.ones((H, W, 3))
    for mesh, rgb in items:
        V = mesh.vertices; F = mesh.faces; N = mesh.face_normals
        px = (V @ r - x0) / res; py = (V @ u - y0) / res; pz = V @ d
        lam = np.clip(N @ (-LIGHT), 0, 1); facing = np.clip(-(N @ d), 0, 1)
        shade = 0.38 + 0.47 * lam + 0.15 * facing
        for fi in np.nonzero(facing > 0)[0]:
            t = F[fi]; xs, ys, zs = px[t], py[t], pz[t]
            xa, xb = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max())))
            ya, yb = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
            if xb < xa or yb < ya:
                continue
            gx, gy = np.meshgrid(np.arange(xa, xb + 1) + .5, np.arange(ya, yb + 1) + .5)
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-12:
                continue
            w1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            w2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            w3 = 1 - w1 - w2
            inside = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
            if not inside.any():
                continue
            z = w1 * zs[0] + w2 * zs[1] + w3 * zs[2]
            sub = zb[ya:yb + 1, xa:xb + 1]; im = img[ya:yb + 1, xa:xb + 1]
            upd = inside & (z < sub)
            sub[upd] = z[upd]; im[upd] = np.clip(rgb * shade[fi], 0, 1)
    # thin dark outline where depth jumps, so edges read
    edge = np.zeros((H, W), bool)
    for a, b in ((zb[1:, :], zb[:-1, :]), (zb[:, 1:], zb[:, :-1])):
        jump = np.abs(np.where(np.isinf(a), 1e9, a) - np.where(np.isinf(b), 1e9, b)) > 2.0
        if a.shape[0] < H:
            edge[1:, :] |= jump
        else:
            edge[:, 1:] |= jump
    img[edge] = img[edge] * 0.45
    return img[::-1]


def cyl(p0, p1, rad, sections=40):
    m = trimesh.creation.cylinder(radius=rad, segment=[p0, p1], sections=sections)
    return m


def main():
    plate = trimesh.load(HERE / "trial_feet_plate.stl")
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    for ax, (title, view) in zip(axs, (("Print plate from above (arrows point forward)", [-0.55, 0.75, -0.62]),
                                       ("From below: slot mouths, screw holes, nut pockets", [-0.6, -0.7, 0.55]))):
        ax.imshow(raster([(plate, PURPLE)], view, [0, 0, 1], 0.08)); ax.set_title(title, fontsize=11); ax.axis("off")
    plt.tight_layout(); plt.savefig(HERE / "preview_part.png", dpi=90, facecolor="white"); plt.close()

    torso = trimesh.load(MESH / "torso_link_23dof_rev_1_0.STL"); torso.apply_scale(1000)
    head = trimesh.load(MESH / "head_link.STL"); head.apply_scale(1000); head.apply_translation([3.9635, 0, -44.0])
    robot = trimesh.util.concatenate([torso, head])
    c = robot.triangles_center
    robot = trimesh.Trimesh(robot.vertices, robot.faces[c[:, 2] > 255], process=True)   # cut well below the frame
    items = [(robot, GREY)]
    for side, name, yc in ((1, "left", 71.2), (-1, "right", 73.6)):
        foot = trimesh.load(HERE / ("trial_foot_%s_robot_frame.stl" % name))
        out_face = side * (yc + 8.5 / 2 + 6.0)
        y = lambda d: out_face - side * d   # noqa: E731
        bolt = trimesh.util.concatenate([cyl([-0.9, y(2.0), 347.0], [-0.9, y(22.0), 347.0], 2.5),
                                         cyl([-0.9, y(2.0), 347.0], [-0.9, y(-3.0), 347.0], 4.25)])
        items += [(foot, PURPLE), (bolt, STEEL)]
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.2), gridspec_kw={"width_ratios": [1.25, 1]})
    views = (("Both feet on their rings, from behind", [1, 0, -0.12], ([-90, -115, 305], [90, 115, 500])),
             ("Left foot from the side, with its M5 screw", [0.08, -1, -0.12], ([-95, 40, 305], [105, 100, 500])))
    for ax, (title, view, box) in zip(axs, views):
        ax.imshow(raster(items, view, [0, 0, 1], 0.2, box)); ax.set_title(title, fontsize=11); ax.axis("off")
    plt.tight_layout(); plt.savefig(HERE / "preview_on_robot.png", dpi=90, facecolor="white"); plt.close()
    print("saved")


if __name__ == "__main__":
    main()
