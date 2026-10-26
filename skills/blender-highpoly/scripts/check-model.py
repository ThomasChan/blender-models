"""Measure a model, so 'it's low-poly and the right size' is evidence, not a claim.

Run inside Blender (bpy only exists there):

    blender -b --factory-startup --python check-model.py -- out.glb \
        --expect 127,127,50 --max-tris 800

Accepts a .glb/.gltf (imported) or a .blend (opened).

Verdicts are tri-state, and skipped is not pass:

    PASS         (exit 0)  every requested check ran and passed
    FAIL         (exit 1)  at least one requested check failed
    UNEVALUATED  (exit 2)  nothing failed, but a requested check could not run
                           (missing render, unreadable GLB, unsupported
                           accessor). Blender's --python-exit-code may collapse
                           2 to 1, so the printed VERDICT is authoritative.

Why import the .glb rather than measure the scene you just built: the scene is
your intent, the .glb is what ships. Unapplied scale, a modifier left in the
stack, a material that did not survive the exporter and flipped normals all look
fine in the scene and are wrong in the file.

--expect is checked twice, because they fail for different reasons:

  * the ENCLOSURE -- the largest mesh, i.e. the body -- must match it within
    --tol. This is the "is it the right size" check.
  * the WHOLE scene must fit inside it plus --proud (default 1% of the smallest
    expected dimension), for connectors that legitimately stick out a little.

Both, rather than one bbox check, because a single check cannot tell a
correctly-sized body with 0.4 mm of proud ports from a body that is 0.4 mm too
big -- and it would fail the first, which is a good model.

The GLB is also measured a second time from its own POSITION accessors, without
bpy. The second path exists so an importer normalisation or a stale export
cannot agree with itself and pass.
"""
import bpy, bmesh, sys, os, argparse, json, struct
import numpy as np            # bundled with Blender


# ---------------------------------------------------------------- second path
GLB_MAGIC = 0x46546C67
GLB_JSON = 0x4E4F534A
GLB_BIN = 0x004E4942
COMPONENTS = {
    5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
    5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4),
}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def _glb_chunks(path):
    with open(path, "rb") as f:
        magic, _version, length = struct.unpack("<III", f.read(12))
        if magic != GLB_MAGIC:
            raise ValueError("not a GLB")
        chunks = {}
        while f.tell() < length:
            head = f.read(8)
            if len(head) < 8:
                break
            clen, ctype = struct.unpack("<II", head)
            chunks[ctype] = f.read(clen)
    if GLB_JSON not in chunks:
        raise ValueError("GLB has no JSON chunk")
    return json.loads(chunks[GLB_JSON]), chunks.get(GLB_BIN, b"")


def _accessor(doc, bin_data, idx):
    acc = doc["accessors"][idx]
    if "sparse" in acc:
        raise ValueError("sparse accessor")
    bv = doc["bufferViews"][acc["bufferView"]]
    if bv.get("buffer", 0) != 0:
        raise ValueError("accessor outside the GLB buffer")
    fmt, size = COMPONENTS[acc["componentType"]]
    n = NCOMP[acc["type"]]
    count = acc["count"]
    stride = bv.get("byteStride") or size * n
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    normalized = acc.get("normalized", False)
    out = []
    for i in range(count):
        row = struct.unpack_from("<" + fmt * n, bin_data, base + i * stride)
        if normalized:
            if fmt in ("b", "h"):
                row = tuple(max(v / (127.0 if fmt == "b" else 32767.0), -1.0) for v in row)
            elif fmt in ("B", "H"):
                row = tuple(v / (255.0 if fmt == "B" else 65535.0) for v in row)
            elif fmt == "I":
                row = tuple(v / 4294967295.0 for v in row)
        out.append(row)
    return out


def _mat_mul(a, b):
    out = [0.0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4))
    return out


def _node_matrix(node):
    if "matrix" in node:
        return [float(v) for v in node["matrix"]]
    t = node.get("translation", [0.0, 0.0, 0.0])
    x, y, z, w = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    s = node.get("scale", [1.0, 1.0, 1.0])
    m = [
        1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0.0,
        2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0.0,
        2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    for c in range(3):
        for r in range(3):
            m[c * 4 + r] *= s[c]
    m[12], m[13], m[14] = t
    return m


def _apply(m, p):
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def glb_measure(path):
    """Whole-scene bounds in mm and triangle count, from the file's accessors."""
    doc, bin_data = _glb_chunks(path)
    if "EXT_meshopt_compression" in doc.get("extensionsUsed", []):
        # Accessors point at the fallback buffer, and the writer deliberately
        # stores no fallback data; the bytes on disk are meshopt-compressed.
        raise ValueError(
            "meshopt-compressed GLB: positions exist only in compressed "
            "bufferViews, which this Python path cannot decode; verify with a "
            "decoder (the repo's visual-gate does) or gate an uncompressed export")
    scene = doc.get("scenes", [{}])[doc.get("scene", 0)]
    roots = list(scene.get("nodes", []))
    if not roots:
        child = {c for n in doc.get("nodes", []) for c in n.get("children", [])}
        roots = [i for i in range(len(doc.get("nodes", []))) if i not in child]
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    tris = 0
    skinned = False
    identity = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    stack = [(n, identity) for n in roots]
    while stack:
        ni, parent = stack.pop()
        node = doc["nodes"][ni]
        world = _mat_mul(parent, _node_matrix(node))
        if "mesh" in node:
            if "skin" in node:
                skinned = True
            for prim in doc["meshes"][node["mesh"]].get("primitives", []):
                if prim.get("mode", 4) != 4:
                    raise ValueError("non-triangle primitive")
                pos = _accessor(doc, bin_data, prim["attributes"]["POSITION"])
                for v in pos:
                    p = _apply(world, v)
                    for i in range(3):
                        lo[i] = min(lo[i], p[i])
                        hi[i] = max(hi[i], p[i])
                if "indices" in prim:
                    tris += doc["accessors"][prim["indices"]]["count"] // 3
                else:
                    tris += len(pos) // 3
        for child in node.get("children", []):
            stack.append((child, world))
    if skinned:
        raise ValueError("skinned mesh; the second path only measures static meshes")
    if lo[0] == float("inf"):
        raise ValueError("no POSITION data")
    return [(hi[i] - lo[i]) * 1000.0 for i in range(3)], tris

# ---------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("path")
ap.add_argument("--expect", default=None, help="W,D,H in mm, e.g. 127,127,50")
ap.add_argument("--enclosure", default=None, metavar="NAME",
                help="which object must match --expect. Default: the largest by bounding-box "
                     "volume. Name it when the asset ships in a pose that is not the frame the "
                     "spec sheet describes -- an open lid's bbox swamps the body it hinges on.")
ap.add_argument("--tol", type=float, default=0.5, help="mm tolerance on --expect")
ap.add_argument("--proud", type=float, default=None,
                help="mm the whole scene may exceed --expect (default 1%% of the "
                     "smallest expected dimension)")
ap.add_argument("--max-tris", type=int, default=None)
ap.add_argument("--max-nonmanifold", type=int, default=None,
                help="boundary edges expected from decal plates etc.")
ap.add_argument("--render", action="append", default=[], metavar="PNG",
                help="preview render to check exposure on; repeatable")
ap.add_argument("--max-clipped", type=float, default=0.02,
                help="fraction of a render allowed to be pure white (default 0.02)")
ap.add_argument("--min-highlight", type=float, default=0.85,
                help="brightness the top 0.1%% of a render must reach (default "
                     "0.85). A high percentile, not the mean or p95: both of "
                     "those depend on how much of the frame the bright region "
                     "covers, which is a framing choice. This asks only whether "
                     "the image contains a highlight at all, which is what makes "
                     "it read as a lit object rather than a flat fill.")
a = ap.parse_args(argv)

path = os.path.abspath(os.path.expanduser(a.path))
if not os.path.exists(path):
    print(f"FAIL file not found: {path}"); sys.exit(1)

# ---------------------------------------------------------------- load
bpy.ops.wm.read_factory_settings(use_empty=True)
if path.lower().endswith((".glb", ".gltf")):
    bpy.ops.import_scene.gltf(filepath=path)
    loaded = "imported"
else:
    bpy.ops.wm.open_mainfile(filepath=path)
    loaded = "opened"

sc = bpy.context.scene
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()

tris = faces = verts = 0
ngons = 0
nonmanifold = 0
boundary = 0
lo = [1e9] * 3
hi = [-1e9] * 3
objs = 0
parts = []          # (name, dims_mm, volume) -- to find the enclosure
for o in sc.objects:
    if o.type != 'MESH':
        continue
    objs += 1
    olo = [1e9] * 3
    ohi = [-1e9] * 3
    ev = o.evaluated_get(dg)
    m = ev.to_mesh()
    m.calc_loop_triangles()
    tris += len(m.loop_triangles)
    faces += len(m.polygons)
    verts += len(m.vertices)
    ngons += sum(1 for p in m.polygons if len(p.vertices) > 4)
    bm = bmesh.new(); bm.from_mesh(m)
    for e in bm.edges:
        n = len(e.link_faces)
        if n == 1: boundary += 1
        elif n != 2: nonmanifold += 1
    bm.free()
    # The geometry's own vertices, not the eight corners of its bounding box. Those
    # corners are not on the object: transforming them measures a box that is only
    # equal to the object while the object is axis-aligned. Rotate a lid that is a
    # 1.5 mm plate -- box 59 x 215.6 mm -- and its corner box comes out 109 mm tall,
    # 42 mm below a floor the machine is standing on.
    for v in m.vertices:
        w = ev.matrix_world @ v.co
        for i in range(3):
            lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
            olo[i] = min(olo[i], w[i]); ohi[i] = max(ohi[i], w[i])
    ev.to_mesh_clear()
    od = [(ohi[i] - olo[i]) * 1000.0 for i in range(3)]
    parts.append((o.name, od, od[0] * od[1] * od[2]))

dims_mm = [(hi[i] - lo[i]) * 1000.0 for i in range(3)]
if a.enclosure:
    pick = [p for p in parts if p[0] == a.enclosure]
    if not pick:
        print(f"FAIL --enclosure {a.enclosure!r} is not in the file; "
              f"parts are {sorted(p[0] for p in parts)}")
        sys.exit(1)
    enc_name, enc_mm, _ = pick[0]
else:
    enc_name, enc_mm, _ = max(parts, key=lambda p: p[2]) if parts else ("<none>", dims_mm, 0)
mats = sorted({ms.material.name for o in sc.objects if o.type == 'MESH'
               for ms in o.material_slots if ms.material})
smooth = sum(1 for o in sc.objects if o.type == 'MESH'
             for p in o.data.polygons if p.use_smooth)
sharp = 0
for o in sc.objects:
    if o.type != 'MESH': continue
    at = o.data.attributes.get("sharp_edge")
    if at: sharp += sum(1 for i in range(len(at.data)) if at.data[i].value)

print(f"LOADED   {loaded}: {os.path.basename(path)}")
print(f"MESH     objects={objs} tris={tris} faces={faces} verts={verts}")
print(f"SHADING  smooth_faces={smooth}/{faces} sharp_edges={sharp}")
print(f"TOPOLOGY ngons={ngons} boundary_edges={boundary} nonmanifold_edges={nonmanifold}")
print(f"SIZE     {dims_mm[0]:.2f} x {dims_mm[1]:.2f} x {dims_mm[2]:.2f} mm   "
      f"z_min={lo[2]*1000:.3f} mm  (min corner {lo[0]*1000:.1f},{lo[1]*1000:.1f},{lo[2]*1000:.1f})")
print(f"ENCLOSURE {enc_mm[0]:.2f} x {enc_mm[1]:.2f} x {enc_mm[2]:.2f} mm  "
      f"(largest mesh: {enc_name})")
print(f"MATERIALS ({len(mats)}) {', '.join(mats) if mats else '<none>'}")

# ---------------------------------------------------------------- checks
fails = []
unevaluated = []

# Independent measurement of the file that ships. Blender's importer is the
# first path; this reads POSITION accessors and node transforms directly.
if path.lower().endswith(".glb"):
    try:
        gdims, gtris = glb_measure(path)
        print(f"SECOND   glb accessors: {gdims[0]:.2f} x {gdims[1]:.2f} x {gdims[2]:.2f} mm, "
              f"tris={gtris}")
        if gtris != tris:
            fails.append(f"second path: glb has {gtris} tris, Blender imported {tris}")
        gs, bs = sorted(gdims), sorted(dims_mm)
        off = [abs(gs[i] - bs[i]) for i in range(3)]
        if max(off) > max(a.tol, 0.1):
            fails.append(
                f"second path: sorted glb dims {[round(v,2) for v in gs]} disagree with "
                f"Blender's {[round(v,2) for v in bs]} mm by "
                f"{[round(v,3) for v in off]} mm -- an import/export scale drift, "
                f"not a modelling error")
    except Exception as exc:
        unevaluated.append(f"second path could not measure the glb: {exc}")
else:
    print("SECOND   skipped: the accessor path reads .glb only; gate the exported .glb")

if a.expect:
    try:
        want = [float(v) for v in a.expect.split(",")]
    except ValueError:
        print("UNEVALUATED --expect needs three comma-separated numbers")
        sys.exit(2)
    if len(want) != 3:
        print("UNEVALUATED --expect needs three comma-separated numbers")
        sys.exit(2)
    proud = a.proud if a.proud is not None else 0.01 * min(want)
    axis = "XYZ"

    off = [i for i in range(3) if abs(enc_mm[i] - want[i]) > a.tol]
    if off:
        fails.append(f"enclosure size: {enc_name} is {[round(d,2) for d in enc_mm]}, "
                     f"want {want} (off on {[axis[i] for i in off]} by "
                     f"{[round(enc_mm[i]-want[i],3) for i in off]} mm)")

    over = [i for i in range(3) if dims_mm[i] - want[i] > proud + a.tol]
    if over:
        fails.append(f"sticks out: whole scene is {[round(d,2) for d in dims_mm]}, "
                     f"more than {proud:.2f} mm past {want} on "
                     f"{[axis[i] for i in over]} "
                     f"({[round(dims_mm[i]-want[i],2) for i in over]} mm) -- a "
                     f"connector may protrude, a stray studio object may not")

    if lo[2] * 1000.0 < -a.tol:
        fails.append(f"does not sit on its base plane: lowest point is "
                     f"{lo[2]*1000:.3f} mm, below z=0 -- dropping this on a ground "
                     f"plane sinks it in")
if a.max_tris is not None and tris > a.max_tris:
    fails.append(f"tris: {tris} over budget {a.max_tris}")
if a.max_nonmanifold is not None and nonmanifold > a.max_nonmanifold:
    fails.append(f"nonmanifold edges: {nonmanifold} over {a.max_nonmanifold}")
if not mats:
    fails.append("no materials: a glTF with no material renders default white")
if tris == 0:
    fails.append("no geometry")

# ---------------------------------------------------------------- exposure
# A blown-out render does not look broken. The eye adapts to a bright image and
# reads it as "clean, bright product shot" -- so "I looked at it" is not a
# sufficient check, which is how two agents in a row shipped one. Measure it.
for rp in a.render:
    rp = os.path.abspath(os.path.expanduser(rp))
    if not os.path.exists(rp):
        unevaluated.append(f"render not found: {rp}"); continue
    try:
        img = bpy.data.images.load(rp)
        if len(img.pixels) < 4:
            raise ValueError("image has no pixels")
        buf = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(buf)
    except Exception as exc:
        unevaluated.append(f"render could not be read: {rp}: {exc}"); continue
    rgb = buf.reshape(-1, 4)[:, :3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    clipped = float((lum > 0.98).mean())
    hi = float(np.percentile(lum, 99.9))
    print(f"RENDER   {os.path.basename(rp)}  mean={lum.mean():.3f} "
          f"p95={np.percentile(lum, 95):.3f} highlight={hi:.3f} "
          f"clipped>0.98={clipped*100:.2f}% "
          f"black<0.02={float((lum < 0.02).mean())*100:.2f}%")
    if hi < a.min_highlight:
        fails.append(
            f"{os.path.basename(rp)}: the brightest 0.1% only reaches {hi:.3f}, "
            f"below {a.min_highlight:.2f} -- the frame has no highlight, so it "
            f"reads as murky rather than as a lit product. Raise the world "
            f"strength before the lights: a metal is lit almost entirely by the "
            f"world.")
    if clipped > a.max_clipped:
        fails.append(
            f"{os.path.basename(rp)}: {clipped*100:.1f}% of pixels are pure white "
            f"(limit {a.max_clipped*100:.0f}%) -- that detail is gone, not bright. "
            f"Lower the key light or the world; raise --max-clipped only if a "
            f"white background is deliberate.")
    if float((lum < 0.02).mean()) > 0.5:
        fails.append(f"{os.path.basename(rp)}: more than half the frame is black "
                     f"-- the render probably failed silently")

for f in fails:
    print("FAIL     " + f)
for f in unevaluated:
    print("UNEVALUATED " + f)
if fails:
    print("VERDICT  FAIL")
    sys.exit(1)
if unevaluated:
    print("VERDICT  UNEVALUATED")
    sys.exit(2)
print("VERDICT  PASS")
print("PASS     all requested checks ran and passed")
