# Front surface of the G1 chest as a depth map: x (mm, torso frame) for each (z, y), by casting rays backwards.
#   python chest_map.py <torso.STL> <out.npy>
import sys, numpy as np, trimesh
m = trimesh.load(sys.argv[1]); m.apply_scale(1000)
ys = np.arange(-90, 90.01, 0.5); zs = np.arange(40, 330.01, 0.5)
Ym, Zm = np.meshgrid(ys, zs)
org = np.stack([np.full(Ym.size, 300.0), Ym.ravel(), Zm.ravel()], 1)
loc, ri, _ = m.ray.intersects_location(org, np.tile([-1.0, 0, 0], (len(org), 1)), multiple_hits=False)
Xm = np.full(Ym.size, np.nan); Xm[ri] = loc[:, 0]; Xm = Xm.reshape(Ym.shape)
np.save(sys.argv[2], np.stack([Ym, Zm, Xm]))
print('chest map', Xm.shape, 'x at the hole centres (y=+-32.25, z=110):', Xm[np.argmin(abs(zs - 110)), [np.argmin(abs(ys - 32.25)), np.argmin(abs(ys + 32.25))]])
