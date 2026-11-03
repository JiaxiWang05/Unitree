# Trade-off: shelf height and length vs the D435's talk-spot view, plug clearance and room to bend the cable up
import math, sys, importlib
import numpy as np, trimesh
sys.path.insert(0, sys.argv[1])
import brio_chest_mount as B
torso = trimesh.load(sys.argv[2]); torso.apply_scale(1000)
c = torso.triangles_center
torso = torso.submesh([np.where((c[:, 2] > 40) & (c[:, 2] < 330) & (c[:, 0] > 20))[0]], append=True)
d435 = np.array([57.6235, 17.53, 429.87]); Z0 = 833.0
X, Y = np.meshgrid(np.arange(600, 1401, 50.0), np.arange(-600, 601, 50.0))
tgt = np.stack([X.ravel(), Y.ravel(), np.full(X.size, -Z0)], 1)
dirs_t = (tgt - d435) / np.linalg.norm(tgt - d435, axis=1)[:, None]

def tomesh(wp):
    v = wp.val(); vs, fs = v.tessellate(0.1, 0.2)
    return trimesh.Trimesh([p.toTuple() for p in vs], fs)

def run(shelf_z, shelf_d):
    B.SHELF_Z, B.SHELF_D = shelf_z, shelf_d
    br = tomesh(B.build())
    front, body, tilt = B.camera_pose(); body = np.array(body.toTuple()); front = np.array(front.toTuple())
    R = trimesh.transformations.rotation_matrix(math.radians(-tilt), [0, 1, 0])
    fwd, up = R[:3, :3] @ [1, 0, 0], R[:3, :3] @ [0, 0, 1]
    cam = trimesh.creation.box(extents=[B.CAM_D, B.CAM_W, B.CAM_H]); cam.apply_transform(R); cam.apply_translation(body)
    sock = body - B.CAM_D / 2 * fwd + (-B.CAM_H / 2 + B.USB_Z) * up
    plug = trimesh.creation.box(extents=[B.PLUG_L, B.PLUG_W, B.PLUG_T]); plug.apply_transform(R); plug.apply_translation(sock - B.PLUG_L / 2 * fwd)
    obst = trimesh.util.concatenate([br, cam, plug]); pts = obst.sample(30000)
    best = 1e9
    for dv in dirs_t:
        rel = pts - d435; al = rel @ dv; perp = np.linalg.norm(rel - al[:, None] * dv[None], axis=1); best = min(best, perp[al > 0].min())
    plug_gap = plug.nearest.on_surface(br.sample(40000))[1].min()
    # cable: 4.5 mm thick, leaves the plug end heading back-down at the tilt, bends up with radius r in the x-z plane
    end = sock - B.PLUG_L * fwd; solid = trimesh.util.concatenate([br, torso])
    rmax = 0
    for r in np.arange(8, 40.1, 1.0):
        phi0 = math.radians(180 + tilt)  # heading back and down
        ctr = end + r * np.array([math.cos(phi0 - math.pi / 2), 0, math.sin(phi0 - math.pi / 2)]) * -1
        phis = np.linspace(phi0, math.radians(90 + 360), 60) if False else np.linspace(math.radians(180 + tilt), math.radians(90), 60)
        # heading phi (x-z angle); centre is to the heading's left-up side for a turn towards up (clockwise from back-down to up)
        hx, hz = math.cos(phis[0]), math.sin(phis[0]); nx, nz = hz, -hx  # right normal
        ctr = end + r * np.array([-nx, 0, -nz]) if (end + r * np.array([-nx, 0, -nz]))[2] > end[2] else end + r * np.array([nx, 0, nz])
        ang0 = math.atan2(end[2] - ctr[2], end[0] - ctr[0])
        arc = [ctr + r * np.array([math.cos(a), 0, math.sin(a)]) for a in np.linspace(ang0, ang0 - math.radians(110), 40)]
        arc = np.array(arc) if np.array(arc)[-1][2] > end[2] else np.array([ctr + r * np.array([math.cos(a), 0, math.sin(a)]) for a in np.linspace(ang0, ang0 + math.radians(110), 40)])
        d = solid.nearest.on_surface(arc)[1]; inside = solid.contains(arc) if solid.is_watertight else np.zeros(len(arc), bool)
        if d.min() > 2.3 and not inside.any():
            rmax = r
        else:
            break
    lens_h = (front[2] + Z0) / 1000
    print('SHELF_Z %5.1f SHELF_D %5.1f | lens %.3f m, %3.0f mm ahead | D435 margin %4.1f mm | plug to bracket %4.1f mm | cable can bend up at R <= %2.0f mm | %.1f cm3'
          % (shelf_z, shelf_d, lens_h, front[0], best, plug_gap, rmax, br.volume / 1000))

for z in (125.0, 120.0):
    for d in (92.7, 96.7):
        run(z, d)
