"""Draw Unitree's mount, this bracket, and this bracket with the camera, from the same angle.

    python render_compare.py <folder with Unitree's STEP>     # writes preview_compare.png
"""
import sys
from pathlib import Path

import cadquery as cq
import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import head_brio_mount as hb  # noqa: E402

LIGHT = np.array([0.45, -0.35, 0.82])


def add(ax, mesh, colour, alpha=1.0):
    shade = 0.45 + 0.55 * np.clip(mesh.face_normals @ LIGHT, 0, 1)
    pc = Poly3DCollection(mesh.vertices[mesh.faces], edgecolor="none", alpha=alpha)
    pc.set_facecolor(np.clip(np.outer(shade, matplotlib.colors.to_rgb(colour)), 0, 1))
    ax.add_collection3d(pc)


def main():
    step = hb.unitree_step(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "unitree_ref")
    v, f = cq.importers.importStep(str(step)).rotate((0, 0, 0), (0, 0, 1), 180).val().tessellate(0.05, 0.1)
    official = trimesh.Trimesh([[p.x, p.y, p.z] for p in v], f)
    ours = trimesh.load(HERE / "head_brio_mount.stl")
    brio = trimesh.load(HERE / "brio_dummy.stl")
    cols = (("Unitree's mount (stereo board tray, 49° down)", [(official, "#4a4e57", 1.0)]),
            ("This bracket (level Brio seat)", [(ours, "#7a52d6", 1.0)]),
            ("This bracket with the Brio", [(ours, "#7a52d6", 1.0), (brio, "#1c1e22", 0.85)]))
    views = (("from behind, as in Unitree's picture", 24, 152), ("from the left side; front is to the right", 0, -90))
    fig = plt.figure(figsize=(18, 11))
    for r, (vname, elev, azim) in enumerate(views):
        for i, (title, parts) in enumerate(cols):
            ax = fig.add_subplot(2, 3, r * 3 + i + 1, projection="3d")
            for mesh, colour, alpha in parts:
                add(ax, mesh, colour, alpha)
            ax.set_xlim(0, 112); ax.set_ylim(-56, 56); ax.set_zlim(64, 150)
            ax.set_box_aspect((112, 112, 86), zoom=1.08)
            ax.view_init(elev, azim)
            ax.set_title(title + "\n" + vname, fontsize=12)
            ax.set_axis_off()
    fig.savefig(HERE / "preview_compare.png", dpi=95, bbox_inches="tight")
    print("wrote preview_compare.png")


if __name__ == "__main__":
    main()
