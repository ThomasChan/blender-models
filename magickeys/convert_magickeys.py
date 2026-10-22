# Magic Keyboard (2024, compact, Touch ID) + Magic Mouse (2024, USB-C)
# converted from Apple's desk-set USDZ, not hand-built.
#
# The set ships in imac/imac-silver.usdz -- the same asset the iMac conversion keeps only the
# machine out of. Its three top-level groups are the machine (81 meshes), the keyboard
# (28 meshes, 79,901 tris, 279.5 x 115.1 x 10.9 mm) and the mouse (23 meshes, 11,732 tris,
# 57.2 x 113.9 x 21.7 mm). Selection is by measured predicate, never by node name: the
# names are hashes and move between exports.
#
# Variant check, because it decides the whole asset: this is the COMPACT keyboard (no numeric
# keypad) with Touch ID, and the USB-C Magic Mouse. The 2020 27-inch iMac's pair is a
# different variant (418.7 mm with a numeric keypad, Lightning mouse); do not substitute one
# for the other. Published sizes: keyboard 278.9 x 114.9 x 10.9, mouse 57.1 x 113.5 x 21.6.
#
#   Blender -b --factory-startup --python-exit-code 1 --python convert_magickeys.py -- .
import bpy, math, os, sys
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else ".")
HERE = os.path.dirname(os.path.abspath(__file__))
USDZ = os.path.abspath(os.path.join(HERE, "..", "imac", "imac-silver.usdz"))
MM = 0.001

PUB = {"magic-keyboard": (278.9, 114.9, 10.9), "magic-mouse": (57.1, 113.5, 21.6)}

if not os.path.exists(USDZ):
    print(f"FAIL source asset not found: {USDZ}")
    sys.exit(1)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.wm.usd_import(filepath=USDZ)
bpy.context.view_layer.update()


# ---------------------------------------------------------------- measurement
def bbox(objs):
    """World extent from VERTICES. bound_box is stale on a freshly built mesh and only equals
    the object while the object is axis-aligned; both traps have bitten in this repo."""
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in objs:
        if o.type != 'MESH':
            continue
        ev = o.evaluated_get(dg)
        m = ev.to_mesh()
        for v in m.vertices:
            w = ev.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        ev.to_mesh_clear()
    return lo, hi


def subtree(o):
    out = [o]
    for k in [x for x in sc.objects if x.parent is o]:
        out += subtree(k)
    return out


def unwrap(o):
    """The importer wraps the set in one empty; the three groups are its children. Descend
    through any link that holds a single child with geometry, stop where it forks."""
    kids = [x for x in sc.objects if x.parent is o
            and any(y.type == 'MESH' for y in subtree(x))]
    return unwrap(kids[0]) if len(kids) == 1 else (kids or [o])


groups = []
for r in [o for o in sc.objects if o.parent is None]:
    for g in unwrap(r):
        objs = subtree(g)
        meshes = [o for o in objs if o.type == 'MESH']
        lo, hi = bbox(objs)
        dims = [(hi[i] - lo[i]) / MM for i in range(3)]
        groups.append((g, objs, meshes, dims))
        print(f"REPORT group={g.name} meshes={len(meshes)} "
              f"dims_mm=({dims[0]:.1f}, {dims[1]:.1f}, {dims[2]:.1f})")


def only_one(pred, what):
    hits = [g for g in groups if pred(g[3])]
    if len(hits) != 1:
        print(f"FAIL expected exactly one {what}; found {len(hits)} of {len(groups)}")
        sys.exit(1)
    return hits[0]


# The three groups are 279.5 / 57.2 / 548.9 mm wide, so each predicate isolates one.
KEYBOARD = only_one(lambda d: 250.0 < d[0] < 350.0 and 100.0 < d[1] < 130.0 and 5.0 < d[2] < 25.0,
                    "compact keyboard")
MOUSE = only_one(lambda d: 40.0 < d[0] < 80.0 and 90.0 < d[1] < 130.0 and 15.0 < d[2] < 30.0,
                 "mouse")


# ---------------------------------------------------------------- one object each
def bake(group, name):
    """Join, then apply the world matrix to the data BEFORE the hierarchy is deleted: the
    asset hangs off an empty carrying the 0.01 m/unit scale, so a matrix read after the empty
    is gone ships the mesh 100x too big. Finally centre x/y and stand it on z=0."""
    meshes = [o for o in group[1] if o.type == 'MESH']
    for o in sc.objects:
        o.select_set(o in meshes)
    bpy.context.view_layer.objects.active = max(meshes, key=lambda o: len(o.data.vertices))
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = o.data.name = name
    w = o.matrix_world.copy()
    o.parent = None
    o.data.transform(w)
    o.matrix_world = Matrix.Identity(4)
    lo, hi = bbox([o])
    o.data.transform(Matrix.Translation(Vector((-(lo[0] + hi[0]) / 2,
                                               -(lo[1] + hi[1]) / 2,
                                               -lo[2]))))
    o.data.update()
    return o


kb = bake(KEYBOARD, "magic-keyboard")
ms = bake(MOUSE, "magic-mouse")
for o in [x for x in sc.objects if x not in (kb, ms)]:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.update()

for o in (kb, ms):
    lo, hi = bbox([o])
    dims = [(hi[i] - lo[i]) / MM for i in range(3)]
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    mats = sorted({ms2.material.name for ms2 in o.material_slots if ms2.material})
    pub = PUB[o.name]
    print(f"REPORT part={o.name} tris={tris} verts={len(o.data.vertices)} "
          f"materials={len(mats)} custom_normals={o.data.has_custom_normals}")
    print(f"REPORT {o.name} dims_mm=({dims[0]:.2f}, {dims[1]:.2f}, {dims[2]:.2f}) "
          f"z_min=0  published=({pub[0]}, {pub[1]}, {pub[2]})  "
          f"off=({dims[0]-pub[0]:+.2f}, {dims[1]-pub[1]:+.2f}, {dims[2]-pub[2]:+.2f})")

# Any black+transmission material would be USD's "no diffuse" spelling (the iMac's cover
# glass); on the accessories there should be none, and if one appears it is a real material
# that must not be dropped silently.
for o in (kb, ms):
    bad = []
    for slot in o.material_slots:
        m = slot.material
        if not m or not m.use_nodes:
            continue
        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b and b.inputs['Transmission Weight'].default_value > 0 and \
                max(b.inputs['Base Color'].default_value[:3]) == 0.0:
            bad.append(m.name)
    print(f"REPORT {o.name} black_transmission={bad}")

# ---------------------------------------------------------------- studio
# The iMac conversion's cove rig, re-exposed for white aluminium: same graded world, same
# three suns, same floor. The accessories are smaller but the rig is scale-free (SUN), so the
# only number that moves is the framing.
w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB"); mapr = nt.nodes.new("ShaderNodeMapRange")
mapr.inputs["From Min"].default_value = -0.45
mapr.inputs["From Max"].default_value = 0.35
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.025, 1)
mid = ramp.color_ramp.elements.new(0.55); mid.color = (0.40, 0.405, 0.43, 1)
ramp.color_ramp.elements[-1].position = 1.0
ramp.color_ramp.elements[-1].color = (0.58, 0.59, 0.62, 1)
nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])

# The iMac's rig re-exposed for a WHITE subject. The machine is mostly metal, which is lit
# almost entirely by the world; the accessories' keycaps and mouse top are white diffuse.
# At the iMac's SUN=0.16 a white top renders ~1.2 (world 0.84 + sun diffuse 0.37): the
# keyboard top clipped 3.4% and the mouse 14.9%, with whole faces losing their shading.
# Lowering the world would also dim the metal, so the sun carries the cut instead: world
# stays, sun drops to a quarter. The sun angle narrows with it to keep a specular glint,
# which is what the gate's 0.85 highlight floor asks for.
WORLD, SUN = 1.45, 0.04
bg.inputs["Strength"].default_value = WORLD
for name, rot, e in (("Key", (math.radians(48), 0, math.radians(35)), 7.6 * SUN),
                     ("Fill", (math.radians(55), 0, math.radians(25)), 2.4 * SUN),
                     ("Rim", (math.radians(118), 0, math.radians(-135)), 1.8 * SUN)):
    l = bpy.data.lights.new(name, 'SUN'); l.energy = e; l.angle = math.radians(6)
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
    o.rotation_euler = rot

bpy.ops.mesh.primitive_plane_add(size=8.0)
floor = bpy.context.active_object; floor.name = "Floor"
fmat = bpy.data.materials.new("Floor"); fmat.use_nodes = True
fb = fmat.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.035, 0.035, 0.04, 1.0)
fb.inputs["Roughness"].default_value = 0.62
fb.inputs["Specular IOR Level"].default_value = 0.25
floor.data.materials.append(fmat)

cd = bpy.data.cameras.new("Cam"); cd.clip_start = 0.005; cd.clip_end = 100
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x = sc.render.resolution_y = 1200
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = "Standard"
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 128
sc.cycles.use_denoising = True


def frame(off, ctr, half, lens=100, fill=0.66):
    off = Vector(off).normalized()
    d = 2 * half / fill * lens / cd.sensor_width
    cd.lens = lens
    loc = Vector(ctr) + off * d
    cam.location = loc
    cam.rotation_euler = (Vector(ctr) - loc).to_track_quat('-Z', 'Y').to_euler()


def centre_half(o):
    lo, hi = bbox([o])
    ctr = Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
    return ctr, max(hi[i] - lo[i] for i in range(3)) / 2


# The keyboard's Touch ID key sits at the far right of the function row. Its own box, after
# centring: x ~ +0.10, y ~ +0.035, z ~ +0.011 (the deck is 10.9 mm at the back).
VIEWS = {
    "magic-keyboard": {
        "kb-hero":   dict(off=(0.60, -0.80, 0.50)),
        "kb-top":    dict(off=(0.0, -0.02, 1.0)),
        # half=0.085 framed 218 mm across a 279.5 mm keyboard and cut both ends off.
        # A straight-on view is there to show the whole front edge; 0.40 m across
        # leaves the body at 70% of the frame.
        "kb-front":  dict(off=(0.0, -1.0, 0.22), half=0.16, fill=0.80),
        "kb-side":   dict(off=(-1.0, -0.10, 0.18)),
        "kb-rear":   dict(off=(0.25, 1.0, 0.35)),
        "kb-touchid": dict(off=(0.15, -0.90, 0.55), ctr=(0.100, 0.035, 0.010),
                           half=0.045, fill=0.80),
    },
    "magic-mouse": {
        "ms-hero":   dict(off=(0.55, -0.80, 0.45)),
        "ms-top":    dict(off=(0.0, -0.02, 1.0)),
        "ms-front":  dict(off=(0.0, -1.0, 0.18)),
        "ms-side":   dict(off=(-1.0, -0.05, 0.15)),
        "ms-rear":   dict(off=(0.20, 1.0, 0.30)),
        "ms-detail": dict(off=(0.40, -0.85, 0.50), ctr=(0.0, 0.010, 0.018),
                          half=0.035, fill=0.80),
    },
}

os.makedirs(OUT, exist_ok=True)
for o in (kb, ms):
    other = ms if o is kb else kb
    o.hide_render, other.hide_render = False, True
    ctr, half = centre_half(o)
    for name, v in VIEWS[o.name].items():
        frame(v["off"], v.get("ctr", ctr), v.get("half", half), fill=v.get("fill", 0.66))
        sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"REPORT rendered={name}")
kb.hide_render = ms.hide_render = False

# ---------------------------------------------------------------- export
# Each GLB carries one product at the world origin. The .blend keeps them side by side on
# the desk.
def export(o, filename):
    for x in sc.objects:
        x.select_set(x is o)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, filename),
                              export_format='GLB', export_apply=True, use_selection=True)
    print(f"REPORT glb={filename} bytes={os.path.getsize(os.path.join(OUT, filename))}")


export(kb, "magic-keyboard.glb")
export(ms, "magic-mouse.glb")

ms.matrix_world = Matrix.Translation(Vector((0.32, 0.03, 0.0)))
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "magickeys.blend"))
