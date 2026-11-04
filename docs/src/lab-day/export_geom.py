# Export the bracket, camera, screws, cable and the G1 chest as compact base64 meshes for the 3D guide
import base64, json, math, sys
import numpy as np, trimesh
BR, MESH, OUT, STL = sys.argv[1:5]
sys.path.insert(0, BR)
import brio_chest_mount as B

def enc(m):
    m = m.copy(); m.merge_vertices()
    v = np.round(np.asarray(m.vertices) / 0.05).astype(np.int16)
    f = np.asarray(m.faces).astype(np.uint32 if len(m.vertices) > 65535 else np.uint16)
    return {"v": base64.b64encode(v.tobytes()).decode(), "f": base64.b64encode(f.tobytes()).decode(), "u32": bool(f.dtype == np.uint32)}

def T(m, R=None, t=None):
    m = m.copy()
    if R is not None:
        H = np.eye(4); H[:3, :3] = R; m.apply_transform(H)
    if t is not None:
        m.apply_translation(t)
    return m

def cyl(r, h, axis, base, sections=40):
    """cylinder of radius r from base along axis for length h"""
    c = trimesh.creation.cylinder(radius=r, height=h, sections=sections)
    c.apply_translation([0, 0, h / 2])
    z = np.array([0, 0, 1.0]); a = np.asarray(axis, float) / np.linalg.norm(axis)
    R = trimesh.geometry.align_vectors(z, a)
    c.apply_transform(R); c.apply_translation(base)
    return c

def ring(ro, ri, h, axis, base, sections=40):
    a = trimesh.creation.annulus(r_min=ri, r_max=ro, height=h, sections=sections)
    a.apply_translation([0, 0, h / 2])
    R = trimesh.geometry.align_vectors([0, 0, 1.0], np.asarray(axis, float) / np.linalg.norm(axis))
    a.apply_transform(R); a.apply_translation(base)
    return a

out = {"meshes": {}, "steps": {}, "points": {}}
def put(name, m, **kw):
    out["meshes"][name] = dict(enc(m), **kw)

# robot: chest and head (decimated)
torso = trimesh.load(MESH + "/torso_link_23dof_rev_1_0.STL"); torso.apply_scale(1000)
c = torso.triangles_center
keep = np.where((c[:, 2] > 30) & (c[:, 2] < 360) & (c[:, 0] > -10) & (np.abs(c[:, 1]) < 175))[0]
chest = torso.submesh([keep], append=True)
chest = chest.simplify_quadric_decimation(face_count=14000)
put("chest", chest)
head = trimesh.load(MESH + "/head_link.STL"); head.apply_scale(1000); head.apply_translation([3.9635, 0, -44.0])
head = head.simplify_quadric_decimation(face_count=7000)
put("head", head)

# bracket (as printed)
br = trimesh.load(STL)
put("bracket", br)

# seat frame
plane, length = B.seat_plane()
u = np.array(plane.xDir.toTuple()); w = np.array(plane.zDir.toTuple()); yv = np.array([0, 1.0, 0])
P = lambda a, b, c_: np.array(plane.toWorldCoords((a, b, c_)).toTuple())
t = math.radians(B.TILT_DEG)
Rcam = np.column_stack([u, yv, w])  # camera local x = forward (u), y = width, z = up (w)

# bare camera: stadium 102 x 27 seen from the front, 26.5 deep; back face on the back stops
D, W, H = 26.5, 102.0, 27.0
body = trimesh.boolean.union([
    trimesh.creation.box(extents=[D, W - H, H]),
    cyl(H / 2, D, [1, 0, 0], [-D / 2, (W - H) / 2, 0], 48),
    cyl(H / 2, D, [1, 0, 0], [-D / 2, -(W - H) / 2, 0], 48)], engine="manifold")
cam_c = P(B.LIP_T + D / 2, 0, H / 2)
put("camera", T(body, Rcam, cam_c))
lens = cyl(7.5, 0.6, [1, 0, 0], [D / 2, 0, 0], 40)
put("lens", T(lens, Rcam, cam_c))
glass = cyl(3.2, 0.9, [1, 0, 0], [D / 2, 0, 0], 32)
put("lensdot", T(glass, Rcam, cam_c))
sock = trimesh.creation.box(extents=[0.8, 9.0, 3.5]); sock.apply_translation([-D / 2 - 0.3, 0, -H / 2 + B.USB_Z])
put("socket", T(sock, Rcam, cam_c))
clip = trimesh.creation.box(extents=[24.0, 36.0, 9.0]); clip.apply_translation([0, 0, -H / 2 - 4.5])
put("clip", T(clip, Rcam, cam_c))

# 1/4" screw + washer, from below through the slot
axis_base = P(B.screw_u(), 0, -B.GRIP)  # spot face centre
put("washer14", ring(6.0, 3.3, B.WASHER_T, -w, axis_base))
head_base = axis_base - B.WASHER_T * w
put("screw14", trimesh.util.concatenate([cyl(4.76, 6.35, -w, head_base), cyl(3.17, B.SCREW_L, w, head_base, 28)]))

# M6 screws + washers at the pads
pads = []
for side in (1, -1):
    n = np.array([B.HOLE_NORMAL[0], side * B.HOLE_NORMAL[1], B.HOLE_NORMAL[2]]); n /= np.linalg.norm(n)
    o = np.array([B.SURFACE_X, side * B.HOLE_SPACING / 2, B.HOLE_Z])
    pads.append((o, n))
    put("m6washer%d" % (side > 0), ring(6.0, 3.2, 1.6, n, o + B.SEAT_T * n))
    hb = o + (B.SEAT_T + 1.6) * n
    put("m6screw%d" % (side > 0), trimesh.util.concatenate([cyl(5.0, 6.0, n, hb), cyl(3.0, 18.0, -n, hb, 28)]))
    put("hole%d" % (side > 0), ring(5.5, 3.6, 0.6, n, o + 0.15 * n))           # marker on the chest at the hole
    put("padface%d" % (side > 0), ring(8.8, 3.9, 0.5, -n, o - 0.05 * n))      # the pad face that sits on the chest

# spot-face recess highlight (where support material must be cleared)
rec = trimesh.creation.box(extents=[B.SPOT_D + B.SLOT_PLAY, B.SPOT_D, 0.6]); rec.apply_translation([0, 0, -0.35])
put("recess", T(rec, Rcam, axis_base))

# USB-C plug, straight, out through the gap in the back stops
back_face = cam_c - D / 2 * u
sock_c = back_face + (-H / 2 + B.USB_Z) * w
plug = trimesh.creation.box(extents=[B.PLUG_L, B.PLUG_W, B.PLUG_T]); plug.apply_translation([-B.PLUG_L / 2, 0, 0])
put("plug", T(plug, Rcam, sock_c))
end = sock_c - B.PLUG_L * u
# cable: bend up (radius 22 mm in the x-z plane), then up the chest towards the neck, drifting to one side
r = 22.0; phi0 = math.pi + t
ctr = end + r * np.array([-math.sin(t), 0, math.cos(t)])
pts = []
for k in range(14):
    ph = phi0 - (phi0 - math.pi / 2) * k / 13.0
    pts.append(ctr + r * np.array([-math.sin(ph), 0, math.cos(ph)]))
top = pts[-1]
full = trimesh.load(MESH + "/torso_link_23dof_rev_1_0.STL"); full.apply_scale(1000)
for zz, yy in ((25, 0), (60, 8), (100, 20), (140, 34), (180, 46)):
    q = top + np.array([0.0, yy, zz])
    loc, _, _ = full.ray.intersects_location([[300.0, q[1], q[2]]], [[-1.0, 0, 0]], multiple_hits=False)
    if len(loc):
        q[0] = max(q[0], loc[0][0] + 4.5)  # lie on the chest, never inside it
    pts.append(q)
out["points"]["cable"] = [list(map(float, p)) for p in pts]

# where things are, for labels
out["points"].update({
    "recess": list(map(float, axis_base - 3 * w)), "seat": list(map(float, P(18, 0, 0))),
    "backgap": list(map(float, P(1.5, 0, 4))), "frontlip": list(map(float, P(length - 1.5, 0, 4))),
    "slot": list(map(float, P(B.screw_u(), 0, 0.5))), "lens": list(map(float, cam_c + (D / 2 + 1) * u)),
    "socket": list(map(float, sock_c - 2 * u)), "plugend": list(map(float, end)), "cam": list(map(float, cam_c)),
    "clip": list(map(float, cam_c - (H / 2 + 9) * w)), "screw": list(map(float, head_base - 6 * w)),
    "holeL": list(map(float, pads[0][0])), "holeR": list(map(float, pads[1][0])),
    "padL": list(map(float, pads[0][0] + 6 * pads[0][1])), "padR": list(map(float, pads[1][0] + 6 * pads[1][1])),
    "opening": list(map(float, P(-12, 0, 0) - np.array([0, 0, 2]))), "neck": list(map(float, pts[-1])),
})
out["vectors"] = {"u": list(u), "w": list(w), "n0": list(map(float, pads[0][1])), "n1": list(map(float, pads[1][1]))}
out["lens"] = {"pos": list(map(float, cam_c + D / 2 * u)), "u": list(u), "w": list(w), "tilt": B.TILT_DEG}
out["holeSpacing"] = B.HOLE_SPACING
js = "window.GEOM=" + json.dumps(out, separators=(",", ":")) + ";"
open(OUT, "w").write(js)
print("wrote %.0f kB; faces: chest %d head %d bracket %d" % (len(js) / 1024, len(chest.faces), len(head.faces), len(br.faces)))
