"""Check the full head arch against Unitree's G1 model.

    python check_helmet_arch.py <folder with torso_link_23dof_rev_1_0.STL and head_link.STL>

Run helmet_arch.py first. Prints clearances (head, shoulder shell, rings, screws), the saddle's
foam gap, whether the Brio's view and the head depth camera's view of the talk spot are clear,
the head lidar's shadow, mass, centre of mass, lens height, print sizes and overhangs, then
ALL CLEAR or the problems.
"""
import math
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_trial_feet as ctf  # noqa: E402
import helmet_arch as ha  # noqa: E402
import trial_feet as tf  # noqa: E402

MESH = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
FLOOR_Z = -836.0                         # floor in the torso frame, robot standing
D435 = np.array([57.6235, 17.53, 429.87])  # URDF d435_joint, torso frame, mm
D435_PITCH = math.degrees(0.8307767)       # 47.6 deg down
LIDAR = ctf.LIDAR
PETG = 1.27e-3                            # g per mm3
BED = 256.0
problems = []


def need(ok, msg):
    if not ok:
        problems.append(msg)


def ray_hits(meshes, origins, dirs, max_len):
    """True for each ray that hits any mesh within max_len."""
    hit = np.zeros(len(origins), bool)
    for m in meshes:
        r = trimesh.ray.ray_triangle.RayMeshIntersector(m)
        loc, idx, _ = r.intersects_location(origins, dirs, multiple_hits=False)
        if len(idx):
            d = np.linalg.norm(loc - origins[idx], axis=1)
            hit[idx[d < max_len]] = True
    return hit


def main():
    torso = ctf.mm(trimesh.load(MESH / "torso_link_23dof_rev_1_0.STL"))
    head = ctf.mm(trimesh.load(MESH / "head_link.STL"))
    head.apply_translation(ctf.HEAD_OFFSET)
    feet = {s: trimesh.load(HERE / ("helmet_foot_%s_robot_frame.stl" % n)) for s, n in ((1, "left"), (-1, "right"))}
    crown = trimesh.load(HERE / "helmet_crown_robot_frame.stl")
    brio = trimesh.load(HERE / "helmet_brio_robot_frame.stl")
    pieces = [feet[1], feet[-1], crown]

    print("== feet and rings (as check_trial_feet)")
    for side, name in ((1, "left"), (-1, "right")):
        foot = feet[side]
        yc = side * tf.RING_Y[side]
        t_near = ctf.near(torso, foot.bounds)
        pts = foot.sample(60000)
        d_ring, d_shell = ctf.split_clearance(pts, t_near, yc)
        print("   %-5s foot: ring %.2f mm, shoulder shell %.2f mm" % (name, d_ring, d_shell))
        need(d_ring >= 1.0, "%s foot only %.2f mm from its ring" % (name, d_ring))
        need(d_shell >= 2.0, "%s foot only %.2f mm from the shoulder" % (name, d_shell))
        parts, _, _ = ctf.bolt_parts(side)
        for pname, part in parts.items():
            dl, ds = ctf.split_clearance(part.sample(20000), t_near, yc)
            print("         %-9s ring %.2f, shoulder %.2f" % (pname, dl, ds))
            need(dl >= 0.8 and ds >= 1.5, "%s %s too close (ring %.2f, shoulder %.2f)" % (name, pname, dl, ds))

    print("== head")
    pts, fi = trimesh.sample.sample_surface(crown, 150000)
    nz = crown.face_normals[fi][:, 2]
    cp, dist = ctf.closest(pts, ctf.near(head, crown.bounds, pad=20))
    in_block = ((pts[:, 0] >= ha.BACK_X - 0.5) & (pts[:, 0] <= ha.FRONT_X + 0.5)
                & (np.abs(pts[:, 1]) <= ha.BLOCK_W / 2 + 0.5) & (pts[:, 2] < 500))
    saddle = in_block & (nz < -0.5) & (dist < 10.0)          # the block's underside, facing the head
    rest = ~in_block
    i = np.argmin(np.where(rest, dist, 1e9))
    print("   crown outside the camera block: %.2f mm from the head (closest at x %.0f y %.0f z %.0f)" % (dist[i], *pts[i]))
    need(dist[i] >= 6.0, "the crown comes %.2f mm from the head away from the saddle" % dist[i])
    j = np.argmin(np.where(in_block & ~saddle, dist, 1e9))
    print("   camera block sides: %.2f mm from the head" % dist[j])
    g = dist[saddle]
    print("   saddle underside to head (3 mm foam goes here): min %.2f, median %.2f, 90%% %.2f, max %.2f mm; %.0f mm2 of it within 4 mm" % (
        g.min(), np.median(g), np.percentile(g, 90), g.max(), crown.area * (saddle & (dist <= 4.0)).sum() / len(pts)))
    need(1.8 <= g.min() and np.percentile(g, 90) <= 4.5, "saddle gap %.2f-%.2f mm doesn't suit 3 mm foam" % (g.min(), np.percentile(g, 90)))
    for side, name in ((1, "left"), (-1, "right")):
        _, d, _ = trimesh.proximity.closest_point(ctf.near(head, feet[side].bounds, pad=40), feet[side].sample(30000))
        print("   %s foot to the head %.2f mm" % (name, d.min()))
        need(d.min() >= 6.0, "%s foot %.2f mm from the head" % (name, d.min()))
    _, d, _ = trimesh.proximity.closest_point(ctf.near(head, brio.bounds, pad=40), brio.sample(30000))
    print("   Brio and plug to the head %.2f mm" % d.min())
    need(d.min() >= 3.0, "Brio or plug %.2f mm from the head" % d.min())
    t_crown = ctf.near(torso, crown.bounds, pad=10)
    if len(t_crown.faces):
        _, d, _ = trimesh.proximity.closest_point(t_crown, crown.sample(60000))
        print("   crown to the torso %.2f mm" % d.min())
        need(d.min() >= 3.0, "crown %.2f mm from the torso" % d.min())

    print("== Brio view (66 x 52 deg, tilted %.0f deg up)" % ha.TILT)
    lens = np.array(ha.lens())
    u, w = np.array(ha.U), np.array(ha.W)
    left = np.cross(w, u)
    dirs = []
    for a in np.linspace(-33, 33, 45):
        for e in np.linspace(-26, 26, 35):
            d = u + math.tan(math.radians(a)) * left + math.tan(math.radians(e)) * w
            dirs.append(d / np.linalg.norm(d))
    dirs = np.array(dirs)
    orig = lens + dirs * 0.5
    blocked = ray_hits([head, torso] + pieces, orig, dirs, 3000.0)
    print("   lens at x %.1f z %.1f: %.0f mm above the floor; %d of %d view rays blocked" % (
        lens[0], lens[2], lens[2] - FLOOR_Z, blocked.sum(), len(dirs)))
    need(blocked.sum() == 0, "%d of the Brio's view rays are blocked" % blocked.sum())
    bottom = math.degrees(math.asin(np.min(dirs[:, 2])))
    print("   view edges: %.0f deg below to %.0f deg above level" % (-bottom, math.degrees(math.asin(np.max(dirs[:, 2])))))

    print("== head depth camera's view of the talk spot")
    targets = []
    for x in np.arange(600, 1401, 50):
        for y in np.arange(-600, 601, 50):
            for h in (0.0, 300.0, 550.0):
                targets.append((x, y, FLOOR_Z + h))
    targets = np.array(targets)
    vec = targets - D435
    L = np.linalg.norm(vec, axis=1)
    dirs = vec / L[:, None]
    blocked = ray_hits(pieces + [brio], np.repeat(D435[None], len(dirs), 0), dirs, 1e9)
    blocked &= True
    helmet_pts = np.vstack([p.sample(20000) for p in pieces] + [brio.sample(10000)])
    rel = helmet_pts - D435
    proj = rel @ dirs[::7].T
    near_line = np.min(np.linalg.norm(rel[:, None, :] - proj[:, :, None] * dirs[::7][None], axis=2)[proj > 0]) \
        if (proj > 0).any() else float("inf")
    print("   %d sight lines, %d blocked; the arch is never in front of the depth camera (closest %.0f mm from a line)" % (
        len(dirs), blocked.sum(), near_line))
    need(blocked.sum() == 0, "%d depth-camera sight lines to the talk spot are blocked" % blocked.sum())

    print("== head lidar (MID-360, mounted upside down and pitched 2.9 deg: sees -7..+52 deg in its own frame)")
    ang = 0.05112069379091391
    cy, sy = math.cos(ang), math.sin(ang)
    R = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @ np.diag([1.0, -1.0, -1.0])   # URDF rpy (pi, 0.0511, 0)
    vis_meshes = [torso, head]
    names = (("left foot", feet[1]), ("right foot", feet[-1]), ("crown", crown))
    covered = {1: set(), -1: set()}
    covered_legs = {1: set(), -1: set()}
    for name, p in names:
        q = p.sample(12000)
        rel = q - LIDAR
        loc = rel @ R                                  # lidar frame
        el = np.degrees(np.arctan2(loc[:, 2], np.hypot(loc[:, 0], loc[:, 1])))
        inband = (el >= -7) & (el <= 52)
        if not inband.any():
            continue
        q, rel = q[inband], rel[inband]
        dist_ = np.linalg.norm(rel, axis=1)
        dirs = rel / dist_[:, None]
        start = LIDAR + dirs * 25.0                    # outside the lidar's own window
        occluded = np.zeros(len(q), bool)
        for m in vis_meshes:
            r = trimesh.ray.ray_triangle.RayMeshIntersector(m)
            loc_h, idx, _ = r.intersects_location(start, dirs, multiple_hits=False)
            if len(idx):
                dh = np.linalg.norm(loc_h - start[idx], axis=1)
                occluded[idx[dh < dist_[idx] - 25.0 - 0.5]] = True
        az = np.degrees(np.arctan2(rel[:, 1], rel[:, 0]))
        for side in (1, -1):
            sel = (~occluded) & (np.sign(az) == side)
            covered[side] |= set(np.floor(az[sel] / 0.5).astype(int))
            if name == "crown":
                covered_legs[side] |= set(np.floor(az[sel & (q[:, 2] > 364)] / 0.5).astype(int))
    for side, name in ((1, "left"), (-1, "right")):
        print("   %-5s side: the leg casts %.1f deg of new shadow; with the foot, %.1f deg" % (
            name, len(covered_legs[side]) * 0.5, len(covered[side]) * 0.5))
        need(len(covered_legs[side]) * 0.5 <= 12.0, "lidar shadow of the %s leg is %.1f deg" % (name, len(covered_legs[side]) * 0.5))
    print("   (the feet sit 25-42 deg below the lidar, so their extra shadow falls on the floor 1.4-2.7 m out to")
    print("   each side; the arms, which this check doesn't include, already block part of that)")

    print("== mass and balance (printed solid in PETG; infill makes it lighter)")
    total, mom = 0.0, np.zeros(3)
    for name, p in (("left foot", feet[1]), ("right foot", feet[-1]), ("crown", crown)):
        m = p.volume * PETG
        total += m
        mom += m * p.center_mass
        print("   %-10s %5.1f g" % (name, m))
    print("   printed total %.0f g, centre of mass x %.1f y %.1f z %.1f" % (total, *(mom / total)))
    print("   with the Brio (about 63 g) the load on the head is about %.0f g" % (total + 63))

    print("== printing (bed %.0f mm)" % BED)
    for name in ("helmet_crown", "helmet_foot_left", "helmet_foot_right"):
        m = trimesh.load(HERE / (name + ".stl"))
        ext = m.extents
        n = m.face_normals
        bed = m.triangles_center[:, 2] < 2.0          # the first 2 mm print on the bed's squish
        over = (n[:, 2] < -0.707) & ~bed
        print("   %-18s %.0f x %.0f x %.0f mm, %s; faces steeper than 45 deg overhang (above 2 mm): %.0f mm2" % (
            name, *ext, "watertight" if m.is_watertight else "NOT watertight", m.area_faces[over].sum()))
        need(ext.max() <= BED and m.is_watertight, "%s doesn't fit the bed or isn't watertight" % name)

    print("ALL CLEAR" if not problems else "PROBLEMS:\n- " + "\n- ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
