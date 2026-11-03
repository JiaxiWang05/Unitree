# Minimal shaded renders of triangle meshes with matplotlib: render([(V, F, colour), ...], out.png, views, titles)
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.colors import to_rgb

def render(meshes, out, views=((20, -50),), titles=None, size=4.2):
    allv = np.vstack([V for V, F, c in meshes]); lo, hi = allv.min(0), allv.max(0); mid = (lo + hi) / 2; r = (hi - lo).max() / 2
    fig = plt.figure(figsize=(size * len(views), size))
    light = np.array([0.4, -0.5, 0.8]); light /= np.linalg.norm(light)
    for k, (el, az) in enumerate(views):
        ax = fig.add_subplot(1, len(views), k + 1, projection='3d')
        for V, F, c in meshes:
            tri = V[F]; n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
            shade = 0.45 + 0.55 * np.abs(n @ light)
            cols = np.clip(np.array(to_rgb(c))[None, :] * shade[:, None], 0, 1)
            ax.add_collection3d(Poly3DCollection(tri, facecolors=cols, edgecolors='none', linewidths=0))
        ax.set_xlim(mid[0] - r, mid[0] + r); ax.set_ylim(mid[1] - r, mid[1] + r); ax.set_zlim(mid[2] - r, mid[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(el, az); ax.set_axis_off()
        if titles: ax.set_title(titles[k], fontsize=10)
    plt.tight_layout(); plt.savefig(out, dpi=110); plt.close(fig)
