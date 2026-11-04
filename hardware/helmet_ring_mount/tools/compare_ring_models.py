"""Measure the shoulder lifting rings in each of Unitree's official G1 torso models.

    python compare_ring_models.py <folder from docs/src/fetch_g1_model.py --extra>

Rays across each ring give its height above the shoulder shell, front-back width, the eye's
width and height, the plate's thickness and its distance from the centre line. The 23-DoF
and 29-DoF rev 1.0 models agree; the head arch is drawn from those numbers.
"""

import sys
from pathlib import Path

import numpy as np
import trimesh

MODELS = {  # file, rough z of the ring's top in that model's torso frame (mm)
    "23-DoF rev 1.0 (this robot)": ("torso_link_23dof_rev_1_0.STL", 355.9),
    "29-DoF rev 1.0": ("torso_link_rev_1_0.STL", 311.5),
    "torso with 2-DoF head": ("torso_link_with_2dof_head.STL", 319.8),
    "original G1": ("torso_link.STL", 284.8),
}


def measure(mesh: trimesh.Trimesh, top: float, side: int) -> str:
    ray = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)
    X = np.arange(-16.0, 16.01, 0.25)
    Z = np.arange(top - 30, top + 3, 0.25)
    GX, GZ = np.meshgrid(X, Z)
    n = GX.size

    def first(y0, dy):
        origins = np.stack([GX.ravel(), np.full(n, side * y0), GZ.ravel()], 1)
        out = np.full(n, np.nan)
        loc, idx, _ = ray.intersects_location(origins, np.tile([0, side * dy, 0.0], (n, 1)), multiple_hits=False)
        if len(idx):
            out[idx] = np.abs(loc[:, 1])
        return out

    inner, outer = first(60.0, 1.0), first(96.0, -1.0)
    hit = (inner < 92) & (inner > 60)
    grid = hit.reshape(GX.shape)
    full = [i for i in range(len(Z)) if grid[i].sum() > 0.9 * len(X)]
    base = Z[max(full)] if full else Z[0]
    ring = (GZ.ravel() > base + 1.5) & hit & (outer > 60)
    if not ring.any():
        return "no ring"
    zz, xx = GZ.ravel()[ring], GX.ravel()[ring]
    thick, centre = outer[ring] - inner[ring], (outer[ring] + inner[ring]) / 2
    eye_w, eye_rows = 0.0, []
    for i in range(len(Z)):
        if Z[i] <= base + 1.5:
            continue
        mat = np.nonzero(grid[i])[0]
        gaps = [(mat[k] + 1, mat[k + 1] - 1) for k in range(len(mat) - 1) if mat[k + 1] - mat[k] > 1]
        if gaps:
            a, b = max(gaps, key=lambda g: g[1] - g[0])
            w = (b - a + 1) * 0.25
            if w > 2:
                eye_rows.append(Z[i])
                eye_w = max(eye_w, w)
    eye_h = max(eye_rows) - min(eye_rows) + 0.25 if eye_rows else 0.0
    return ("stands %.1f mm | %.1f wide front-back | eye %.1f wide x %.1f tall | plate %.1f thick (max %.1f) | centre %.2f mm from the centre line"
            % (zz.max() - base, xx.max() - xx.min(), eye_w, eye_h, np.median(thick), np.percentile(thick, 98), np.median(centre)))


def main() -> None:
    folder = Path(sys.argv[1])
    for name, (file, top) in MODELS.items():
        path = folder / file
        if not path.exists():
            print("== %s: %s not found" % (name, file))
            continue
        mesh = trimesh.load(path)
        mesh.apply_scale(1000.0)
        print("== %s (%s)" % (name, file))
        for side, label in ((1, "left "), (-1, "right")):
            print("   %s %s" % (label, measure(mesh, top, side)))


if __name__ == "__main__":
    main()
