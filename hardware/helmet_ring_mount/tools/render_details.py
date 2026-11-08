"""Close-ups of the arch's details: the hidden cable channel and the hand-turned ring screws.

    python render_details.py <helmet_ring_mount folder> <g1mesh folder>
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
sys.path.insert(0, str(HERE))
import helmet_arch as ha  # noqa: E402
import trial_feet as tf  # noqa: E402

BLACK = np.array([0.16, 0.16, 0.18])
CABLE = np.array([0.10, 0.10, 0.11])


def cable_path():
    """The cable as it lies in the left leg's channel, from the plug down to where it leaves."""
    x = ha.BACK_X + ha.CH_D - 2.3
    pts = [(x, y, z) for y, z in ha.centreline(1) if z >= ha.CH_Z0][::-1]   # top of the arch down to CH_Z0
    top = pts[0]
    plug_end = ha.at(-ha.CAM_D / 2 - ha.PLUG_L, ha.USB_Z)
    lead = [plug_end, (plug_end[0] - 6, 0, plug_end[2] - 8), (top[0] - 8, 0, top[2] + 6), (top[0], 0, top[2])]
    tail = [(x - 10, pts[-1][1] + 2, ha.CH_Z0 - 18), (x - 25, pts[-1][1] - 6, ha.CH_Z0 - 50)]
    return np.array(lead + pts + tail, float)


def tube(points, r=2.2):
    parts = []
    for a, b in zip(points[:-1], points[1:]):
        if np.linalg.norm(b - a) > 0.5:
            parts.append(cyl(a, b, r, sections=16))
    for p in points[1:-1]:
        s = trimesh.creation.icosphere(subdivisions=1, radius=r)
        s.apply_translation(p)
        parts.append(s)
    return trimesh.util.concatenate(parts)


def main():
    crown = trimesh.load(HERE / "helmet_crown_robot_frame.stl")
    feet = [trimesh.load(HERE / ("helmet_foot_%s_robot_frame.stl" % n)) for n in ("left", "right")]
    brio = trimesh.load(HERE / "helmet_brio_robot_frame.stl")
    torso = trimesh.load(MESH / "torso_link_23dof_rev_1_0.STL"); torso.apply_scale(1000)
    head = trimesh.load(MESH / "head_link.STL"); head.apply_scale(1000); head.apply_translation([3.9635, 0, -44.0])
    robot = trimesh.util.concatenate([torso, head])
    c = robot.triangles_center
    robot = trimesh.Trimesh(robot.vertices, robot.faces[c[:, 2] > 255], process=True)
    screws = []
    for side in (1, -1):
        out = side * (tf.RING_Y[side] + tf.SLOT_W / 2 + tf.CHEEK_OUT_T)
        screws.append(cyl([tf.RING_X, out, tf.PIN_Z], [tf.RING_X, out - side * 25.0, tf.PIN_Z], 2.5))
        screws.append(cyl([tf.RING_X, out, tf.PIN_Z], [tf.RING_X, out + side * 9.0, tf.PIN_Z], 8.0, sections=24))
    screws = trimesh.util.concatenate(screws)
    arch = [(crown, PURPLE)] + [(f, PURPLE) for f in feet] + [(brio, BLACK), (screws, STEEL)]
    fig, axs = plt.subplots(1, 2, figsize=(15, 7.5), gridspec_kw={"width_ratios": [1.2, 1]})
    view = [0.78, -0.45, -0.32]
    axs[0].imshow(raster(arch + [(tube(cable_path()), CABLE), (robot, GREY)], view, [0, 0, 1], 0.22,
                         ([-60, -90, 300], [40, 95, 545])))
    axs[0].set_title("From behind: the cable runs hidden in the back of the left leg", fontsize=12)
    axs[1].imshow(raster(arch + [(robot, GREY)], [0.1, -1, -0.2], [0, 0, 1], 0.12, ([-30, 60, 325], [30, 100, 400])))
    axs[1].set_title("Left foot: the thumb screw turns by hand", fontsize=12)
    for ax in axs:
        ax.axis("off")
    plt.tight_layout(); plt.savefig(HERE / "preview_arch_details.png", dpi=80, facecolor="white"); plt.close()
    print("saved preview_arch_details.png")


if __name__ == "__main__":
    main()
