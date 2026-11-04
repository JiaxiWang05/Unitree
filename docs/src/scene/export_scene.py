# Export the standing G1 (all links), the Brio bracket, camera and cable, in world mm (floor z = 0, robot facing +x)
import base64, json, math, sys
import numpy as np, trimesh
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import fk, brio_chest_mount as B
MESH, STL, OUT = sys.argv[3], sys.argv[4], sys.argv[5]
ANG = {'left_elbow_joint': 1.2, 'right_elbow_joint': 1.2}
L, T = fk.links(MESH + '/g1_23dof_rev_1_0.urdf', ANG, MESH)
feet = np.vstack([L[k].vertices for k in L if 'ankle_roll' in k]); lift = -feet[:, 2].min()
for m in L.values(): m.apply_translation([0, 0, lift])
torso_o = T['torso_link'][:3, 3] * 1000 + np.array([0, 0, lift])

import gzip, struct
BLOB, HEAD = [], {}
def enc(m, faces=None, crease=32):
    m = m.copy(); m.merge_vertices()
    if faces and len(m.faces) > faces: m = m.simplify_quadric_decimation(face_count=faces)
    m = trimesh.graph.smooth_shade(m, angle=np.radians(crease))
    F = np.asarray(m.faces, np.int64)
    order = np.unique(F.ravel(), return_index=True)[1]; first = F.ravel()[np.sort(order)]   # vertices by first use
    remap = np.empty(len(m.vertices), np.int64); remap[first] = np.arange(len(first))
    F = remap[F]; verts = np.asarray(m.vertices)[first]; normals = np.asarray(m.vertex_normals, float)[first]
    q = np.round(verts / 0.1).astype(np.int64)
    dq = np.diff(q, axis=0, prepend=np.zeros((1, 3), np.int64)); zq = ((dq << 1) ^ (dq >> 63)).astype(np.uint16)
    pos_planes = np.concatenate([(zq & 0xff).astype(np.uint8).T.ravel(), (zq >> 8).astype(np.uint8).T.ravel()])
    n = normals / np.maximum(np.abs(normals).sum(1, keepdims=True), 1e-9)
    ox, oy = n[:, 0].copy(), n[:, 1].copy(); neg = n[:, 2] < 0
    ox[neg], oy[neg] = (1 - np.abs(n[neg, 1])) * np.sign(n[neg, 0] + 1e-12), (1 - np.abs(n[neg, 0])) * np.sign(n[neg, 1] + 1e-12)
    oct8 = np.clip(np.round(np.stack([ox, oy], 1) * 127), -127, 127).astype(np.int8).T.ravel().view(np.uint8)
    f = F.ravel(); d = np.diff(f, prepend=0); z = ((d << 1) ^ (d >> 63)).astype(np.uint32)
    idx_planes = np.concatenate([((z >> (8 * k)) & 0xff).astype(np.uint8) for k in range(3)])
    assert z.max() < (1 << 24)
    v = verts
    return {"nv": int(len(v)), "nf": int(len(F)), "parts": [pos_planes.tobytes(), oct8.tobytes(), idx_planes.tobytes()]}
def pack(meshes):
    off, head = 0, {}
    for name, e in meshes.items():
        sizes = [len(b) for b in e["parts"]]
        head[name] = {"nv": e["nv"], "nf": e["nf"], "off": off, "sizes": sizes}
        for b in e["parts"]:
            BLOB.append(b); off += len(b)
    raw = b"".join(BLOB); gz = gzip.compress(raw, 9)
    return head, base64.b64encode(gz).decode(), len(raw), len(gz)
out = {"meshes": {}, "pts": {}}
dark = ['head_link', 'logo_link']
limbs = [m for k, m in L.items() if k not in ('torso_link', 'head_link', 'logo_link', 'pelvis', 'pelvis_contour_link')]
out["meshes"]["limbs"] = enc(trimesh.util.concatenate([m.simplify_quadric_decimation(face_count=min(len(m.faces), 3300)) for m in limbs]))
out["meshes"]["torso"] = enc(L['torso_link'], 24000)
out["meshes"]["pelvis"] = enc(trimesh.util.concatenate([L['pelvis'], L['pelvis_contour_link']]), 9000)
out["meshes"]["head"] = enc(L['head_link'], 10000)
out["meshes"]["logo"] = enc(L['logo_link'], 2000)

# bracket and Brio, from the torso frame into the world
def W(m): m = m.copy(); m.apply_translation(torso_o); return m
br = trimesh.load(STL); out["meshes"]["bracket"] = enc(W(br))
plane, length = B.seat_plane()
u = np.array(plane.xDir.toTuple()); w = np.array(plane.zDir.toTuple()); y = np.array([0, 1.0, 0])
Pw = lambda a, b, c: np.array(plane.toWorldCoords((a, b, c)).toTuple()) + torso_o
Rc = np.column_stack([u, y, w])
def place(m, c): m = m.copy(); M = np.eye(4); M[:3, :3] = Rc; m.apply_transform(M); m.apply_translation(c); return m
def cyl(r, h, axis, base, n=40):
    c = trimesh.creation.cylinder(radius=r, height=h, sections=n); c.apply_translation([0, 0, h / 2])
    c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1.0], np.asarray(axis, float) / np.linalg.norm(axis))); c.apply_translation(base); return c
Dp, Wd, Hd = 26.5, 102.0, 27.0
body = trimesh.boolean.union([trimesh.creation.box(extents=[Dp, Wd - Hd, Hd]), cyl(Hd / 2, Dp, [1, 0, 0], [-Dp / 2, (Wd - Hd) / 2, 0], 48), cyl(Hd / 2, Dp, [1, 0, 0], [-Dp / 2, -(Wd - Hd) / 2, 0], 48)], engine="manifold")
cc = Pw(B.LIP_T + Dp / 2, 0, Hd / 2)
out["meshes"]["camera"] = enc(place(body, cc))
out["meshes"]["lens"] = enc(place(cyl(7.5, 0.8, [1, 0, 0], [Dp / 2, 0, 0]), cc))
sock = cc - Dp / 2 * u + (-Hd / 2 + B.USB_Z) * w
plug = trimesh.creation.box(extents=[B.PLUG_L, B.PLUG_W, B.PLUG_T]); plug.apply_translation([-B.PLUG_L / 2, 0, 0])
out["meshes"]["plug"] = enc(place(plug, sock))
end = sock - B.PLUG_L * u
t = math.radians(B.TILT_DEG); r = 22.0; phi0 = math.pi + t
ctr = end + r * np.array([-math.sin(t), 0, math.cos(t)])
cable = [ctr + r * np.array([-math.sin(ph), 0, math.cos(ph)]) for ph in np.linspace(phi0, math.pi / 2, 14)]
top = cable[-1].copy()
torso_full = L['torso_link']
for zz, yy in ((25, 0), (60, 8), (100, 20), (140, 34), (180, 46), (215, 58)):
    q = top + np.array([0.0, yy, zz])
    loc, _, _ = torso_full.ray.intersects_location([[top[0] + 300, q[1], q[2]]], [[-1.0, 0, 0]], multiple_hits=False)
    if len(loc): q[0] = max(q[0], loc[0][0] + 4.5)
    cable.append(q)
out["pts"]["cable"] = [list(map(float, p)) for p in cable]
lens = cc + Dp / 2 * u
out["brio"] = {"pos": list(map(float, lens)), "fwd": list(map(float, u)), "up": list(map(float, w)), "vfov": 52.2, "hfov": 66.2}
d = T['d435_link'].copy(); dpos = d[:3, 3] * 1000 + np.array([0, 0, lift])
out["d435"] = {"pos": list(map(float, dpos)), "fwd": list(map(float, d[:3, 0])), "up": list(map(float, d[:3, 2])), "vfov": 58.0, "hfov": 87.0}
head = L['head_link']; out["pts"]["headTop"] = [float(head.vertices[:, 0].mean()), 0.0, float(head.vertices[:, 2].max())]
out["robotHeight"] = float(max(m.vertices[:, 2].max() for m in L.values()))
out["torsoOrigin"] = list(map(float, torso_o))
head, b64, nraw, ngz = pack(out["meshes"]); out["meshes"] = head; out["blob"] = b64
js = "window.SCENE=" + json.dumps(out, separators=(",", ":")) + ";"
print("raw %.0f kB, gzip %.0f kB" % (nraw / 1024, ngz / 1024))
open(OUT, "w").write(js)
print("wrote %.0f kB | robot height %.0f mm, torso origin z %.0f, lens %s mm, d435 %s pitch %.1f deg" % (len(js) / 1024, out["robotHeight"], torso_o[2], np.round(lens).tolist(), np.round(dpos).tolist(), math.degrees(math.asin(-d[2, 0]))))
print({k: v["nf"] for k, v in out["meshes"].items()})
