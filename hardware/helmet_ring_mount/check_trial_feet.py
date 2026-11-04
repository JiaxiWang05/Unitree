"""Check the trial feet against Unitree's G1 model (torso with the rings, and the head).

    python check_trial_feet.py <folder with torso_link_23dof_rev_1_0.STL and head_link.STL>

Prints the clearance from each foot, its M5 bolt and nut to the robot, whether anything
overlaps, and how much of the head lidar's view the leg stub covers. Exits 1 on a problem.
"""
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from trial_feet import (BOLT_SEAT, BOTTOM_Z, CHEEK_IN_T, CHEEK_OUT_T, EYE_R, EYE_Z, FOOT_LEN, LEG_W, PIN_Z,
                        RING_X, RING_Y, SLOT_W)

HERE = Path(__file__).resolve().parent
MESH = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
HEAD_OFFSET = np.array([3.9635, 0.0, -44.0])   # head_joint in the torso frame, mm
LIDAR = np.array([0.28, 0.03, 405.0])          # MID-360 window centre (dome), torso frame
BOLT_D, HEAD_D, HEAD_H, BOLT_L = 5.0, 8.5, 5.0, 20.0   # ISO 4762 M5x20, head in the counterbore
NUT_AC, NUT_H = 9.24, 5.0                      # DIN 985 M5: across corners, height
NEED = {"ring": 1.0, "shoulder": 2.0, "head": 3.0, "below cheeks": 2.0}


def mm(mesh):
    mesh = mesh.copy()
    mesh.apply_scale(1000.0)
    return mesh


def near(mesh, box, pad=25.0):
    lo, hi = box[0] - pad, box[1] + pad
    c = mesh.triangles_center
    keep = np.all((c >= lo) & (c <= hi), axis=1)
    return trimesh.Trimesh(mesh.vertices, mesh.faces[keep], process=True)


def closest(pts, robot):
    """Nearest robot point and distance for each point: a dense surface sample in a KD-tree, then exact
    closest-point on the 200 nearest candidates (the minimum is what matters)."""
    tree = robot.metadata.get("tree")
    if tree is None:
        cloud = robot.sample(400000)
        tree = robot.metadata["tree"] = (cKDTree(cloud), cloud)
    kd, cloud = tree
    dist, idx = kd.query(pts)
    cp = cloud[idx]
    best = np.argsort(dist)[:200]
    ecp, edist, _ = trimesh.proximity.closest_point(robot, pts[best])
    dist[best], cp[best] = edist, ecp
    return cp, dist


def split_clearance(pts, robot, yc):
    """Smallest distance to the ring lug and to the rest of the shell, by where the nearest point is."""
    cp, dist = closest(pts, robot)
    on_ring = (np.abs(cp[:, 1] - yc) < 5.0) & (np.abs(cp[:, 0] - RING_X) < 13.0) & (cp[:, 2] > 338.5)
    big = 99.0
    return (float(dist[on_ring].min()) if on_ring.any() else big,
            float(dist[~on_ring].min()) if (~on_ring).any() else big)


def bolt_parts(side):
    yc = side * RING_Y[side]
    out_face = yc + side * (SLOT_W / 2 + CHEEK_OUT_T)
    in_face = yc - side * (SLOT_W / 2 + CHEEK_IN_T)
    axis = np.array([0.0, -side, 0.0])     # from the outside in
    rot = trimesh.geometry.align_vectors([0, 0, 1], axis)
    parts = {}
    for name, m, start, length in (
        ("bolt", trimesh.creation.cylinder(radius=BOLT_D / 2, height=BOLT_L, sections=48), out_face - side * BOLT_SEAT, BOLT_L),
        ("bolt head", trimesh.creation.cylinder(radius=HEAD_D / 2, height=HEAD_H, sections=48), out_face - side * BOLT_SEAT + side * HEAD_H, HEAD_H),
        ("nut", trimesh.creation.cylinder(radius=NUT_AC / 2, height=NUT_H, sections=6), in_face + side * NUT_H, NUT_H),
    ):
        m = m.copy()
        m.apply_transform(rot)
        m.apply_translation(np.array([RING_X, start, PIN_Z]) + axis * length / 2)
        parts[name] = m
    return parts, in_face, out_face


def below_cheeks(robot, side, in_face, out_face):
    """Vertical gap from the cheek bottoms down to the shell (rays straight down)."""
    yc = side * RING_Y[side]
    lo, hi = sorted((in_face, out_face))
    xs = np.arange(RING_X - FOOT_LEN / 2 + 1.5, RING_X + FOOT_LEN / 2 - 1.5, 0.5)
    ys = [y for y in np.arange(lo + 1.5, hi - 1.5, 0.5) if abs(y - yc) > SLOT_W / 2 + 0.1]
    gx, gy = np.meshgrid(xs, ys)
    origins = np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, BOTTOM_Z)], 1)
    ray = trimesh.ray.ray_triangle.RayMeshIntersector(robot)
    loc, idx, _ = ray.intersects_location(origins, np.tile([0, 0, -1.0], (len(origins), 1)), multiple_hits=False)
    return float((BOTTOM_Z - loc[:, 2]).min()) if len(loc) else 99.0


def main():
    torso = mm(trimesh.load(MESH / "torso_link_23dof_rev_1_0.STL"))
    head = mm(trimesh.load(MESH / "head_link.STL"))
    head.apply_translation(HEAD_OFFSET)
    ok = True
    for side, name in ((1, "left"), (-1, "right")):
        foot = trimesh.load(HERE / ("trial_foot_%s_robot_frame.stl" % name))
        yc = side * RING_Y[side]
        robot = near(torso, foot.bounds)
        pts = foot.sample(40000)
        d_ring, d_shell = split_clearance(pts, robot, yc)
        _, d_head = closest(pts, near(head, foot.bounds, pad=60))
        d_head = float(d_head.min())
        probe = robot.sample(40000)
        probe = probe[np.all((probe >= foot.bounds[0]) & (probe <= foot.bounds[1]), axis=1)]
        inside = int(foot.contains(probe).sum()) if len(probe) else 0
        parts, in_face, out_face = bolt_parts(side)
        d_below = below_cheeks(robot, side, in_face, out_face)
        print("== %s foot (ring at y %+.1f)" % (name, yc))
        print("   to the ring           %.2f mm" % d_ring)
        print("   to the shoulder shell %.2f mm" % d_shell)
        print("   below the cheeks      %.2f mm (straight down)" % d_below)
        print("   to the head           %.2f mm" % d_head)
        print("   robot surface inside the foot: %d of %d sample points within its box" % (inside, len(probe)))
        ok &= (inside == 0 and d_ring >= NEED["ring"] and d_shell >= NEED["shoulder"]
               and d_below >= NEED["below cheeks"] and d_head >= NEED["head"])
        for pname, part in parts.items():
            p = part.sample(10000)
            dl, ds = split_clearance(p, robot, yc)
            line = "   %-9s to ring %.2f, to shoulder %.2f" % (pname, dl, ds)
            if pname == "nut":
                overlap = foot.contains(p).mean()
                line += ", %.1f%% of it overlaps the foot (pocket fit)" % (100 * overlap)
                ok &= overlap < 0.01
            print(line)
            ok &= dl >= 0.8 and ds >= 1.5
        gap = EYE_R - (abs(PIN_Z - EYE_Z) + BOLT_D / 2)
        print("   bolt to the eye's round top %.2f mm; eye bottom %.2f mm below the bolt" % (gap, PIN_Z - BOLT_D / 2 - 339.5))
        ok &= gap >= 1.0
        r = math.hypot(RING_X - LIDAR[0], yc - LIDAR[1])
        print("   leg stub covers %.1f deg of the lidar's 360 deg" % (2 * math.degrees(math.atan(LEG_W / 2 / r))))
    print("ALL CLEAR" if ok else "PROBLEM")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
