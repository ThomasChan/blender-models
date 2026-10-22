# iMac (24-inch, M4, silver) -- converted from Apple's own AR asset, not hand-built.
#
# The Mac mini in this folder arrived the same way and that is the point: Apple ships a USDZ
# with every Mac's product page ("View in your space", under /105/media/us/<product>/<year>/
# <uuid>/ar/), and a USDZ beats anything hand-modelled here -- real panel curvature, real port
# bores, real anodised colour, and the display lit with Apple's own wallpaper image. The
# MacBook Pro in this folder was hand-built because nobody looked for one of these; there is
# one at /105/media/us/macbook-pro/2025/785e1bc4-d1bd-4cf4-b1b3-94b9411c9e74/ar/
# macbook-pro-14-in-space-black-variant.usdz -- an M5 machine, where the folder's is M4.
#
#   curl -o imac-silver.usdz 'https://www.apple.com/105/media/us/imac/2024/\
#   e1d50c6b-bc34-47bd-850d-379149b71fb8/ar/imac-with-accessories-silver.usdz'
#
# The colour is only this filename: the same UUID ships all seven (blue, green, pink, silver,
# yellow, orange, purple), and swapping the word is the whole difference between them.
#
# What the conversion has to decide, and nothing else:
#
#   * The asset is a DESK SET: iMac + Magic Keyboard (28 meshes, 79,901 tris) + Magic Mouse
#     (23 meshes, 11,732 tris), three top-level groups. Only the machine ships. Kept by a
#     measured predicate -- the widest group over 500 mm -- rather than by its name, which is
#     a hash, and a different one per colour: lIVVxKJprGSeXRu for the machine in this silver
#     asset, lXCRCNUacPtLDKW for the same group in the blue one.
#   * 81 meshes joined into one. Their names are all hashes, so nothing legible is lost, and
#     one enclosure object is what lets the export gate size the thing: that gate compares
#     the largest mesh against the spec sheet, and an assembly of 81 has no such mesh.
#   * Blender's USD importer carries the primvars:normals (faceVarying) through as custom
#     split normals -- 132 of 132 meshes arrive with them -- so this asset needs none of the
#     crease/normalScale repair the Mac mini's sidecar JSON asks the viewer for. It is not a
#     converter that lost the shading; it is the original shading.
#
#   Blender -b --factory-startup --python-exit-code 1 --python convert_imac.py -- .
import bpy, bmesh, math, os, sys
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else ".")
HERE = os.path.dirname(os.path.abspath(__file__))
USDZ = os.path.join(HERE, "imac-silver.usdz")
HELLO = os.path.join(HERE, "hello-screen.png")
MM = 0.001

# Apple's spec page, for the record. In METRES of the real machine: 547 x 461 x 147. The last
# one is the STAND's depth ("Stand depth: 5.8 inches"), not the machine's overall depth, which
# Apple does not publish -- the stand's foot stops 77 mm in front of the origin and the back's
# bulge reaches 100 mm behind it, so the shipped envelope is deeper than the sheet's 147.
PUB_W, PUB_H, PUB_STAND_D, PUB_STAND_W = 547.0, 461.0, 147.0, 130.0
# The panel: 4480 x 2520 at 218 ppi = 521.9 x 293.6 mm of active area. Everything about the
# front (the bezel's 12.9 mm, the chin) follows from it and the 547 mm width.
PANEL_W, PANEL_H = 4480 / 218 * 25.4, 2520 / 218 * 25.4

if not os.path.exists(USDZ):
    print(f"FAIL source asset not found: {USDZ}\n     fetch it with the curl line in the header")
    sys.exit(1)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.wm.usd_import(filepath=USDZ)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- vertices, not bound_box
def bbox(objs):
    """The world extent of these objects from their VERTICES.
    `object.bound_box` is the eight corners of a box that only equals the object while the
    object is axis-aligned -- and it is the box the mesh had when it was last evaluated, so a
    freshly built mesh answers with a stale one. Both traps have bitten in this repo."""
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in objs:
        if o.type != 'MESH':
            continue
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        for v in m.vertices:
            w = ev.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
        ev.to_mesh_clear()
    return lo, hi

def subtree(o):
    out = [o]
    for k in [x for x in sc.objects if x.parent is o]:
        out += subtree(k)
    return out

# ---------------------------------------------------------------- the machine, not the desk set
# The importer wraps everything in one empty named after the USD's defaultPrim, so "top level"
# is not the asset's top level: the three groups are that wrapper's children. Descend through
# any link in the chain that holds only one child with geometry in it, and stop where it forks.
def unwrap(o):
    kids = [x for x in sc.objects if x.parent is o
            and any(y.type == 'MESH' for y in subtree(x))]
    return unwrap(kids[0]) if len(kids) == 1 else (kids or [o])

groups = []
for r in [o for o in sc.objects if o.parent is None]:
    for g in unwrap(r):
        objs = subtree(g)
        meshes = [o for o in objs if o.type == 'MESH']
        lo, hi = bbox(objs)
        groups.append((g.name, objs, meshes, [(hi[i] - lo[i]) / MM for i in range(3)]))
        print(f"REPORT group={g.name} meshes={len(meshes)} dims_mm="
              f"({', '.join(f'{d:.1f}' for d in groups[-1][3])})")

machine = [g for g in groups if g[3][0] > 500.0 and g[3][2] > 400.0]
if len(machine) != 1:
    print(f"FAIL expected exactly one group to be the machine (wider than 500 mm and taller "
          f"than 400 mm); found {len(machine)} of {len(groups)}")
    sys.exit(1)
# ---------------------------------------------------------------- one enclosure
# Join and bake BEFORE anything is deleted. The whole asset hangs off a root empty that carries
# the 0.01 metres-per-unit scale, so a world matrix read after that empty is gone is a world
# matrix with the unit conversion thrown away -- the mesh lands 100x too big and 100x too far
# from the origin, which measures as 54758.75 mm and renders as a machine the camera is inside.
# Order matters, and the failure looks like a geometry bug rather than a transform one.
keep = set(machine[0][1])
meshes = [o for o in keep if o.type == 'MESH']
for o in sc.objects:
    o.select_set(o in meshes)
bpy.context.view_layer.objects.active = max(meshes, key=lambda o: len(o.data.vertices))
bpy.ops.object.join()
imac = bpy.context.active_object
imac.name = imac.data.name = "imac"
w = imac.matrix_world.copy()
imac.parent = None
imac.data.transform(w)
imac.matrix_world = Matrix.Identity(4)
for o in [x for x in sc.objects if x is not imac]:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.update()

# Apple authors the front cover glass as transmission 1 with a BLACK diffuse -- which is how USD
# says "this surface has no diffuse". Clearing the base colour makes Cycles show the panel
# through it, but the web viewer draws ANY transmissive surface through a separate transmission
# render target, and the page underneath comes out Gaussian-blurred: roughness is not the knob
# (0.12 and 0.0 measure the same softness, and three.js's transmission shader samples the target
# with a roughness-derived LOD of 0 here). The panel is what this model is for, so the cover is
# dropped outright. Predicate unchanged -- full transmission plus a black base; the camera lens
# and the glass Apple mark on the back (transmission 0.5, 0.77 grey on this machine) are not
# touched. The cover's faces sit inside the rear housing's extent, so no measured size moves.
glass_slots = set()
for i, ms in enumerate(imac.material_slots):
    m = ms.material
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) \
        if m and m.node_tree else None
    if b and b.inputs['Transmission Weight'].default_value > 0 and \
            max(b.inputs['Base Color'].default_value[:3]) == 0.0:
        glass_slots.add(i)
if not glass_slots:
    print("FAIL front-cover glass not found -- the material layout changed")
    sys.exit(1)
bm = bmesh.new()
bm.from_mesh(imac.data)
drop = [f for f in bm.faces if f.material_index in glass_slots]
bmesh.ops.delete(bm, geom=drop, context='FACES')
bm.to_mesh(imac.data)
bm.free()
imac.data.update()
# only the materials the surviving faces use -- the cover's slot is still on the object
mats = [imac.material_slots[i].material for i in sorted({p.material_index for p in imac.data.polygons})]
print(f"REPORT removed_cover_glass_faces={len(drop)} slots={sorted(glass_slots)}")

# The asset ships the display lit with Apple's wallpaper. Swap that one image for the real
# hello screen -- the same drawing the MacBook Pro uses, at this panel's 16:9 aspect. The
# screen is one quad whose UVs span the whole image, so nothing else has to move. Find the
# image by walking upstream from Emission Color: the exporter/import turns the connection
# into a chain, and matching on the node's name would be matching on an importer's guess.
def lit_image(m):
    if not m.use_nodes:
        return None
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not b or not b.inputs['Emission Color'].is_linked:
        return None
    todo, seen = [b.inputs['Emission Color'].links[0].from_node], set()
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        if n.type == 'TEX_IMAGE' and n.image:
            return n
        todo += [l.from_node for i in n.inputs for l in i.links]
    return None

hello = bpy.data.images.load(HELLO, check_existing=True)
hello.colorspace_settings.name = 'sRGB'
lit = [(m, lit_image(m)) for m in mats if lit_image(m)]
for m, n in lit:
    n.image = hello
    # The panel is emission-only. Its broad specular sheen used to be hidden by the cover
    # glass; with the cover gone the studio's key light washes the page and clips its white.
    b = next(x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED')
    b.inputs['Specular IOR Level'].default_value = 0.0
print(f"REPORT hello_screen_materials={[m.name for m, _ in lit]}")
if len(lit) != 1:
    print(f"FAIL expected exactly one emissive image (the display); found {len(lit)}")
    sys.exit(1)

lo, hi = bbox([imac])
dims = [(hi[i] - lo[i]) / MM for i in range(3)]
tris = sum(len(p.vertices) - 2 for p in imac.data.polygons)
print(f"REPORT part=imac tris={tris} verts={len(imac.data.vertices)} "
      f"materials={len(mats)} custom_normals={imac.data.has_custom_normals} "
      f"uv_layers={[l.name for l in imac.data.uv_layers]}")
print(f"REPORT envelope_mm=({dims[0]:.2f}, {dims[1]:.2f}, {dims[2]:.2f})  z_min_mm={lo[2]/MM:.3f}")
print(f"REPORT published_mm=(547.00, 461.00, 147.00 stand depth)  "
      f"off: W {dims[0]-PUB_W:+.2f}  H {dims[2]-PUB_H:+.2f}  "
      f"(no published overall depth to be off against)")

# ---------------------------------------------------------------- studio
# Lifted from build_macbookpro.py, where each number was swept and written down with its
# reasoning: the same three suns, the same graded ramp, the same floor, re-exposed for a
# much brighter machine -- and the exposure gate reads these renders.
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

# Both dials come down from the MacBook Pro's rig, because this machine's own albedo is what
# blows it out: its housing is 0.784/0.789/0.800 metal 0.6, its chin 0.674, its bezel 0.95 --
# against a space-black laptop (0.05) and even against the blue variant of THIS machine, whose
# housing is 0.17/0.433/1.0, i.e. 1.9x darker. Measured on the stand close-up at the laptop's
# rig: 21.4% of the frame pure white; at 0.35 of the key, 10.3%; here 1.8%.
#
# The world goes too, 1.66 -> 1.45, and that is the one number not shared with the other
# folders. It had to: the world, not the suns, is what lights the metal (no sun sits where it
# could specular off a back panel), so a bright machine is over-lit by it even with the suns
# at half, and the stop that fixes the sun does nothing for a flat up-facing foot. Swept
# together -- (1.66, 0.18) still returns 2.8% on the stand, (1.45, 0.20) returns 1.8% with
# the side view's highlight at 0.910 against the gate's 0.85 floor. The lens, the graded ramp
# and the floor are the laptop's unchanged; only the exposure is this machine's.
#
# The cover glass went away after that sweep (see above), and it had been attenuating the
# front: with it the chin close-up clipped 0.46%, without it 4.85%, and the page 3.52%. The
# panel is now emission-only and the suns come down to 0.16: chin 0.11%, screen 0.49%. The
# side highlight does not move (0.909) because the metal is lit by the world, not the suns.
WORLD, SUN = 1.45, 0.16
bg.inputs["Strength"].default_value = WORLD
for name, rot, e in (("Key", (math.radians(48), 0, math.radians(35)), 7.6 * SUN),
                     ("Fill", (math.radians(55), 0, math.radians(25)), 2.4 * SUN),
                     ("Rim", (math.radians(118), 0, math.radians(-135)), 1.8 * SUN)):
    l = bpy.data.lights.new(name, 'SUN'); l.energy = e; l.angle = math.radians(12)
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

cd = bpy.data.cameras.new("Cam"); cd.clip_start = 0.01; cd.clip_end = 100
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x = sc.render.resolution_y = 1200
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = "Standard"
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 96
sc.cycles.use_denoising = True

# Aim and distance from the object's own vertices: the machine is 461 mm tall and the stand
# reaches 77 mm forward of centre, so a target and a distance typed in by hand frame one view
# and crop the next. `fill` is the fraction of the frame the longer in-plane extent takes.
def frame(off, ctr, half, lens=52, fill=0.62):
    off = Vector(off).normalized()
    d = 2 * half / fill * lens / cd.sensor_width
    cd.lens = lens
    loc = Vector(ctr) + off * d
    cam.location = loc
    cam.rotation_euler = (Vector(ctr) - loc).to_track_quat('-Z', 'Y').to_euler()

ctr = [(lo[i] + hi[i]) / 2 for i in range(3)]
half = max(hi[i] - lo[i] for i in range(3)) / 2
# The chin (z 89.9 .. 144.4) and the panel (157.2 .. 455.2) are Apple's own numbers, read off
# this asset's meshes: the front glass stops at 144.4 and the chin plate runs from the bottom
# edge of the case up to it. Close-ups are aimed at those, not at a fraction of the height.
CHIN = (0.0, -0.030, 0.117)
SCREEN = (0.0, -0.020, 0.306)
# The four Thunderbolt openings, found by casting rays at the back and keeping the ones that
# land deeper than the surrounding panel: pairs of walls at x = 146/148, 161/163, 176/178,
# 191/193 mm, so four ports on a 15 mm pitch, 6.5 mm deep, with modelled cavities inside.
PORTS = (0.1695, -0.010, 0.116)
STAND = (0.0, -0.010, 0.095)
VIEWS = {
    "hero":   dict(off=(0.62, -0.86, 0.30), ctr=ctr),
    "front":  dict(off=(0.0, -1.0, 0.05), ctr=ctr),
    "side":   dict(off=(-1.0, -0.06, 0.05), ctr=ctr),
    "back":   dict(off=(0.30, 0.92, 0.26), ctr=ctr),
    # The chin, for its colour and the glass's sheen -- NOT for a mark. The 24-inch iMac has
    # none on the front: this asset's chin is one plain 39-face plate under the cover glass,
    # and Apple's own product photography of the machine shows the same bare chin.
    "chin":   dict(off=(0.0, -1.0, 0.12), ctr=CHIN, half=0.045, fill=0.55),
    "screen": dict(off=(0.0, -1.0, 0.10), ctr=SCREEN, half=0.165, fill=0.84),
    "stand":  dict(off=(0.34, -0.80, 0.30), ctr=STAND, half=0.075, fill=0.70),
    # Head-on to the port bores, which face back and 8 degrees up (the whole machine is a slab
    # tilted 8 degrees, front and back alike -- so "straight at the back" is 8 degrees off).
    "port":   dict(off=(0.16, 1.0, 0.16), ctr=PORTS, half=0.032, fill=0.75),
}
os.makedirs(OUT, exist_ok=True)
for name, v in VIEWS.items():
    frame(v["off"], v.get("ctr", ctr), v.get("half", half), fill=v.get("fill", 0.62))
    sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"REPORT rendered={name}")

# ---------------------------------------------------------------- export
for o in sc.objects:
    o.select_set(o is imac)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "imac.glb"),
                          export_format='GLB', export_apply=True, use_selection=True)
print(f"REPORT glb_bytes={os.path.getsize(os.path.join(OUT, 'imac.glb'))}")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "imac.blend"))
