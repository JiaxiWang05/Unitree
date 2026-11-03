# Fit and view checks for the Brio chest bracket (bare camera on a tilted seat), torso frame, mm
#   python check_fit2.py <bracket dir> <cad dir> <bracket.stl> <torso.STL> <head.STL> <preview prefix>
import math, sys
import numpy as np, trimesh
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import brio_chest_mount as B
from view_step import render

br = trimesh.load(sys.argv[3]); torso = trimesh.load(sys.argv[4]); torso.apply_scale(1000)
head = trimesh.load(sys.argv[5]); head.apply_scale(1000); head.apply_translation([3.9635, 0, -44.0])
print('bracket watertight', br.is_watertight, 'bodies', len(br.split(only_watertight=False)), 'volume %.1f cm3' % (br.volume / 1000))
TORSO_Z0 = 833.0  # torso origin height when standing

# 1. gap between the bracket and the chest front, from the chest depth map
Ym, Zm, Xm = np.load(sys.argv[2] + '/chest_map.npy')
from scipy.interpolate import RegularGridInterpolator
surf = RegularGridInterpolator((Zm[:, 0], Ym[0]), Xm, bounds_error=False)
sample = br.sample(300000)
sample = sample[(np.abs(sample[:, 1]) < 90) & (sample[:, 2] > 40) & (sample[:, 2] < 330)]
gap = sample[:, 0] - surf(np.stack([sample[:, 2], sample[:, 1]], 1))
pad_zone = np.zeros(len(sample), bool)
for s_ in (1, -1):
    pad_zone |= np.hypot(sample[:, 1] - s_ * B.HOLE_SPACING / 2, sample[:, 2] - B.HOLE_Z) < B.PAD_D / 2 + 0.5
print('pad faces: gap to chest from %.2f to %.2f mm (want about 0)' % (np.nanmin(gap[pad_zone]), np.nanpercentile(gap[pad_zone], 2)))
print('rest of bracket: closest to chest %.2f mm (want > 0)' % np.nanmin(gap[~pad_zone]))

# 2. the bare Brio on its seat
front, body, tilt = B.camera_pose()
front, body = np.array(front.toTuple()), np.array(body.toTuple())
R = trimesh.transformations.rotation_matrix(math.radians(-tilt), [0, 1, 0])  # pitch the nose up
cam = trimesh.creation.box(extents=[B.CAM_D, B.CAM_W, B.CAM_H]); cam.apply_transform(R); cam.apply_translation(body)
fwd = R[:3, :3] @ [1, 0, 0]
print('Brio: lens %.0f mm in front of the torso origin, %.3f m above the floor, tilted %.0f deg up' % (front[0], (front[2] + TORSO_Z0) / 1000, tilt))
inter = trimesh.boolean.intersection([br, cam], engine='manifold')
print('camera body overlapping the bracket: %.2f mm3 (want 0)' % (inter.volume if not inter.is_empty else 0.0))
d = cam.nearest.on_surface(br.vertices)[1]
print('closest bracket vertex to the camera body: %.2f mm' % d.min())

# 2b. straight USB-C plug on the back face, USB_Z above the underside
up = R[:3, :3] @ [0, 0, 1]
back = body - B.CAM_D / 2 * fwd
sock = back + (-B.CAM_H / 2 + B.USB_Z) * up
plug = trimesh.creation.box(extents=[B.PLUG_L, B.PLUG_W, B.PLUG_T]); plug.apply_transform(R); plug.apply_translation(sock - B.PLUG_L / 2 * fwd)
pi = trimesh.boolean.intersection([br, plug], engine='manifold')
print('USB-C plug (%.0f x %.0f x %.0f mm) overlapping the bracket: %.2f mm3 (want 0)' % (B.PLUG_L, B.PLUG_W, B.PLUG_T, pi.volume if not pi.is_empty else 0.0))
print('  closest bracket point to the plug: %.2f mm' % plug.nearest.on_surface(br.sample(60000))[1].min())
pt = trimesh.boolean.intersection([torso, plug], engine='manifold') if torso.is_watertight else None
end = sock - B.PLUG_L * fwd
both = trimesh.util.concatenate([br, torso])
for lab, dvec in (('straight back', -fwd), ('level back', np.array([-1.0, 0, 0])), ('up', np.array([0, 0, 1.0])), ('back and up 45', np.array([-0.707, 0, 0.707]))):
    loc, _, _ = both.ray.intersects_location([end + 0.01 * dvec], [dvec], multiple_hits=False)
    print('  from the plug end, free %s: %s' % (lab, '%.1f mm' % np.linalg.norm(loc[0] - end) if len(loc) else 'clear'))
print('  plug end at x=%.1f z=%.1f; chest surface there x=%.1f' % (end[0], end[2], float(surf([[end[2], 0.0]])[0])))

# 3. screw: plastic along the slot axis, spot face complete, nothing breaks out
plane, length = B.seat_plane()
uc = B.screw_u()
print('screw: %.2f mm of plastic, sticks %.2f mm into the camera with one %.1f mm washer' % (B.GRIP, B.SCREW_L - B.WASHER_T - B.GRIP, B.WASHER_T))
w = np.array(plane.zDir.toTuple()); u = np.array(plane.xDir.toTuple())
seat_pt = np.array(plane.toWorldCoords((uc, 0, 0)).toTuple())
def solid_along(p0, direction, span=40.0, step=0.05):
    ts = np.arange(0, span, step)
    pts = p0[None, :] + ts[:, None] * direction[None, :]
    inside = br.contains(pts)
    return ts, inside
for du in (-B.SLOT_PLAY / 2, 0.0, B.SLOT_PLAY / 2):
    p_axis = seat_pt + du * u + 0.01 * w
    ts, ins = solid_along(p_axis, -w)
    print('  axis at %+.1f mm: solid along the axis %s (want empty: the slot)' % (du, 'none' if not ins.any() else '%.2f mm' % (ins.sum() * 0.05)))
    for ry, rlabel in ((B.SLOT_W / 2 + 0.8, 'just outside slot'), (B.SPOT_D / 2 - 0.5, 'inside spot-face rim')):
        for sgn in (1, -1):
            p = seat_pt + du * u + sgn * ry * np.array([0, 1, 0]) - 0.01 * w
            ts, ins = solid_along(p, -w)
            first_gap = ts[np.argmax(~ins)] if (~ins).any() else ts[-1]
            if sgn == 1:
                print('    %s: %.2f mm of plastic before the first gap' % (rlabel, first_gap))

# 4. does anything block the Brio's own view? (widest 90 deg diagonal setting, 16:9)
diag = math.radians(90.0); k = math.tan(diag / 2) / math.hypot(16, 9)
hx, hz = 16 * k, 9 * k
print('Brio view: %.1f deg wide x %.1f deg tall' % (2 * math.degrees(math.atan(hx)), 2 * math.degrees(math.atan(hz))))
hz_worst = math.tan(math.radians(66.3 / 2))
for lab_, hz_ in (('worst case 66 deg tall', hz_worst),):
    a_, b_ = np.meshgrid(np.linspace(-1, 1, 81), np.linspace(-1, 1, 61))
    d_ = np.stack([np.ones(a_.size), a_.ravel() * hx, b_.ravel() * hz_], 1); d_ /= np.linalg.norm(d_, axis=1)[:, None]; d_ = d_ @ R[:3, :3].T
    o_ = front + 0.5 * fwd
    for lb, mm in (('bracket', br), ('torso + head', trimesh.util.concatenate([torso, head]))):
        loc_, ri_, _ = mm.ray.intersects_location(np.tile(o_, (len(d_), 1)), d_, multiple_hits=False)
        print('  %s: rays blocked by the %s: %d of %d' % (lab_, lb, sum(np.linalg.norm(l - o_) < 3000 for l in loc_), len(d_)))
a, b = np.meshgrid(np.linspace(-1, 1, 81), np.linspace(-1, 1, 49))
dirs = np.stack([np.ones(a.size), a.ravel() * hx, b.ravel() * hz], 1); dirs /= np.linalg.norm(dirs, axis=1)[:, None]
dirs = dirs @ R[:3, :3].T
origin = front + 0.5 * fwd
c = torso.triangles_center
for label, m in (('bracket', br), ('robot torso + head', trimesh.util.concatenate([torso, head]))):
    loc, ray_i, _ = m.ray.intersects_location(np.tile(origin, (len(dirs), 1)), dirs, multiple_hits=False)
    hit = [i for i, l in zip(ray_i, loc) if np.linalg.norm(l - origin) < 3000]
    print('  rays blocked by the %s: %d of %d' % (label, len(hit), len(dirs)))
top = math.radians(tilt) + math.atan(hz); bot = math.radians(tilt) - math.atan(hz)
lz = (front[2] + TORSO_Z0) / 1000; lx = front[0] / 1000
print('  top of view %.1f deg above level, bottom %.1f deg %s level' % (math.degrees(top), abs(math.degrees(bot)), 'below' if bot < 0 else 'above'))
for h in (1.2, 1.5, 1.6, 1.75, 1.9):
    print('  a face at %.2f m is in view from %.2f m in front of the robot' % (h, lx + (h - lz) / math.tan(top)))
for dist in (1.5, 3.0, 5.0):
    print('  at %.1f m the bottom of the view is %.2f m above the floor' % (dist, lz + (dist - lx) * math.tan(bot)))

# 5. head depth camera's view of the talk spot (0.6-1.4 m ahead, +-0.6 m, floor and thigh height)
obst = trimesh.util.concatenate([br, cam, plug])
d435 = np.array([57.6235, 17.53, 429.87])
for label, h in (('floor', 0.0), ('thigh 0.45 m', 450.0)):
    X, Y = np.meshgrid(np.arange(600, 1401, 25.0), np.arange(-600, 601, 25.0))
    tgt = np.stack([X.ravel(), Y.ravel(), np.full(X.size, h - TORSO_Z0)], 1)
    dd = tgt - d435; dist_t = np.linalg.norm(dd, axis=1); dd /= dist_t[:, None]
    loc, ray_i, _ = obst.ray.intersects_location(np.tile(d435, (len(dd), 1)), dd, multiple_hits=False)
    blocked = set(int(i) for i, l in zip(ray_i, loc) if np.linalg.norm(l - d435) < dist_t[i])
    print('talk spot %s: %d of %d depth-camera sight lines blocked' % (label, len(blocked), len(dd)))
X, Y = np.meshgrid(np.arange(600, 1401, 50.0), np.arange(-600, 601, 50.0))
tgt = np.stack([X.ravel(), Y.ravel(), np.full(X.size, -TORSO_Z0)], 1)
pts = obst.sample(20000)
best = 1e9
for t_ in tgt:
    dvec = (t_ - d435) / np.linalg.norm(t_ - d435)
    rel = pts - d435; along = rel @ dvec
    perp = np.linalg.norm(rel - along[:, None] * dvec[None, :], axis=1)
    best = min(best, perp[(along > 0)].min())
print('closest a talk-spot sight line passes to the camera or bracket: %.0f mm' % best)

# 6. previews
def mesh(m, col):
    return (m.vertices, m.faces, col)
crop = torso.submesh([np.where((c[:, 2] > 40) & (c[:, 2] < 260) & (c[:, 0] > 20))[0]], append=True)
render([mesh(crop, '#b8c2cc'), mesh(br, '#2f7d4a'), mesh(cam, '#222222'), mesh(plug, '#c0392b')], sys.argv[6] + '_on_robot.png',
       views=((15, -35), (0, -90), (0, 0), (60, -60)), titles=['3/4 view', 'side', 'front', 'from above'])
render([mesh(br, '#2f7d4a')], sys.argv[6] + '_part.png', views=((25, -40), (25, 140), (0, -90), (-35, -150)),
       titles=['front 3/4', 'back 3/4 (chest side)', 'side', 'underneath (screw slot)'])
