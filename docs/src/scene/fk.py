# Forward kinematics of the G1 URDF: every link's visual mesh placed in the pelvis frame (mm) for given joint angles
import math, xml.etree.ElementTree as ET
import numpy as np, trimesh

def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr], [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr], [-sp, cp*sr, cp*cr]])

def axis_angle(a, t):
    a = np.asarray(a, float) / np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K

def H(R, t):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t; return M

def origin(el):
    o = el.find('origin') if el is not None else None
    xyz = [float(v) for v in (o.get('xyz', '0 0 0') if o is not None else '0 0 0').split()]
    r = [float(v) for v in (o.get('rpy', '0 0 0') if o is not None else '0 0 0').split()]
    return H(rpy(*r), np.array(xyz))

def links(urdf, angles, mesh_dir):
    root = ET.parse(urdf).getroot()
    joints = {j.find('child').get('link'): j for j in root.findall('joint')}
    cache = {}
    def T(link):
        if link in cache: return cache[link]
        if link not in joints: cache[link] = np.eye(4); return cache[link]
        j = joints[link]; M = T(j.find('parent').get('link')) @ origin(j)
        if j.get('type') in ('revolute', 'continuous'):
            ax = [float(v) for v in j.find('axis').get('xyz').split()]
            M = M @ H(axis_angle(ax, angles.get(j.get('name'), 0.0)), np.zeros(3))
        cache[link] = M; return M
    out = {}
    for l in root.findall('link'):
        v = l.find('visual')
        if v is None or v.find('geometry/mesh') is None: continue
        f = v.find('geometry/mesh').get('filename').split('/')[-1]
        m = trimesh.load(mesh_dir + '/' + f)
        M = T(l.get('name')) @ origin(v); M = M.copy(); M[:3, 3] *= 1.0
        m.apply_transform(M); m.apply_scale(1000.0)
        out[l.get('name')] = m
    for c in joints: T(c)
    return out, {k: v.copy() for k, v in cache.items()}
