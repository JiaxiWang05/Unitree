"""Previews of the full head arch on Unitree's model and of its print pieces.

    python render_helmet.py <helmet_ring_mount folder> <g1mesh folder> [quick]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_feet import GREY, PURPLE, STEEL, cyl, raster  # noqa: E402

HERE, MESH = Path(sys.argv[1]), Path(sys.argv[2])
QUICK = len(sys.argv) > 3
BLACK = np.array([0.16, 0.16, 0.18])
RES = 0.45 if QUICK else 0.25


def main():
    torso = trimesh.load(MESH / "torso_link_23dof_rev_1_0.STL"); torso.apply_scale(1000)
    head = trimesh.load(MESH / "head_link.STL"); head.apply_scale(1000); head.apply_translation([3.9635, 0, -44.0])
    robot = trimesh.util.concatenate([torso, head])
    c = robot.triangles_center
    robot = trimesh.Trimesh(robot.vertices, robot.faces[c[:, 2] > 250], process=True)
    parts = [trimesh.load(HERE / (n + "_robot_frame.stl")) for n in ("helmet_foot_left", "helmet_foot_right", "helmet_crown")]
    brio = trimesh.load(HERE / "helmet_brio_robot_frame.stl")
    bolts = []
    for side, yc in ((1, 71.2), (-1, 73.6)):
        out_face = side * (yc + 8.5 / 2 + 6.0)
        y = lambda d: out_face - side * d  # noqa: E731
        bolts += [cyl([-0.9, y(2.0), 347.0], [-0.9, y(22.0), 347.0], 2.5), cyl([-0.9, y(2.0), 347.0], [-0.9, y(-3.0), 347.0], 4.25)]
    items = [(robot, GREY)] + [(p, PURPLE) for p in parts] + [(brio, BLACK)] + [(b, STEEL) for b in bolts]
    box = ([-90, -120, 300], [110, 120, 565])
    fig, axs = plt.subplots(1, 3, figsize=(18, 7))
    for ax, (title, view) in zip(axs, (("From behind", [1, 0, -0.12]), ("From the left side", [0.05, -1, -0.15]),
                                       ("From the front, a little above", [-1, 0.45, -0.35]))):
        ax.imshow(raster(items, view, [0, 0, 1], RES, box)); ax.set_title(title, fontsize=12); ax.axis("off")
    plt.tight_layout(); plt.savefig(HERE / "preview_arch_on_robot.png", dpi=80, facecolor="white"); plt.close()

    crown = trimesh.load(HERE / "helmet_crown.stl")
    fl, fr = trimesh.load(HERE / "helmet_foot_left.stl"), trimesh.load(HERE / "helmet_foot_right.stl")
    fl.apply_translation([0, 95, 0]); fr.apply_translation([0, 125, 0])
    fig, axs = plt.subplots(1, 2, figsize=(16, 6.5))
    for ax, (title, items_, view) in zip(axs, (
            ("Crown, printed lying on its flat back", [(crown, PURPLE)], [-0.35, 0.25, -1]),
            ("The two feet, printed standing (as the trial feet)", [(fl, PURPLE), (fr, PURPLE)], [-0.55, 0.75, -0.62]))):
        ax.imshow(raster(items_, view, [0, 0, 1] if "feet" in title else [1, 0, 0], RES * 0.4)); ax.set_title(title, fontsize=12); ax.axis("off")
    plt.tight_layout(); plt.savefig(HERE / "preview_arch_parts.png", dpi=80, facecolor="white"); plt.close()
    print("saved")


if __name__ == "__main__":
    main()
