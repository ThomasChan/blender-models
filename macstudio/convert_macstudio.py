# Mac Studio -- converted from Apple's own AR asset, not hand-built, same road as the Mac
# mini and the iMac in this folder. Apple publishes a USDZ for every Mac product page
# ("View in your space"): https://www.apple.com/105/media/us/<product>/<year>/<uuid>/ar/
#
#   curl -o mac-studio.usdz 'https://www.apple.com/105/media/us/mac-studio/2026/\
#   e5b92529-6fd3-439c-9461-9d111718310f/ar/mac-studio-studio.usdz'
#
# The same UUID also ships *-studio-display-xdr-accessories.usdz (the machine with a
# Studio Display and XDR display); this one is the machine alone, which is what this
# folder wants. One root empty, 13 groups, 95 meshes, 38,717 polygons.
#
# What the conversion has to decide, and nothing else:
#
#   * NOTHING IS THROWN AWAY. The iMac's asset was a desk set and the Mac mini's a
#     machine plus a stand; this one is just the machine, and the two groups that look
#     like helper geometry are product:
#       - jDZMTXhHVKklSvD, a 152.9 mm ring lying at z 0..0.7: the dark trim around the
#         circular bottom intake. It is the lowest part of the machine, so it is also
#         what makes the measured height 94.9 against the sheet's 95.
#       - oRzOLQPEygsIIAt, a flat up-facing decal at z 94.94, 49.3 x 60.6 mm: the Apple
#         mark on the top face. Its aspect 0.8135 is the mark's 814 x 1000 drawing
#         (0.8140), and it is what names this machine at thumbnail size.
#   * 95 meshes joined into one. Their names are hashes, so nothing legible is lost, and
#     one enclosure object is what lets the export gate size the thing.
#   * Blender's USD importer carries primvars:normals through as custom split normals,
#     so this asset needs none of the crease/normalScale repair a third-party converter's
#     file does. The script prints whether they arrived; it does not assume.
#   * No transmissive material exists in this asset, so unlike the iMac there is no cover
#     glass to remove and no display to swap. Nothing here is re-authored.
#
#   Blender -b --factory-startup --python-exit-code 1 --python convert_macstudio.py -- .
import bpy, math, os, sys
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else ".")
HERE = os.path.dirname(os.path.abspath(__file__))
USDZ = os.path.join(HERE, "mac-studio.usdz")
MM = 0.001

# Apple's spec page, in millimetres: 197 x 197 x 95. The asset measures 196.4 x 196.4 x
# 94.9 -- 0.6 short on the plan and 0.1 on the height, Apple's own model against Apple's
# own sheet, with nothing in this script scaling it. The gate's --tol is 1.0 for that
# reason: it still catches a model scaled by the wrong unit, and it does not report the
# vendor's 0.3% as this converter's bug.
PUB_W, PUB_D, PUB_H = 197.0, 197.0, 95.0

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
    object is axis-aligned, and it is the box the mesh had when it was last evaluated, so a
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

# ---------------------------------------------------------------- one enclosure
# Join and bake BEFORE anything is deleted. The whole asset hangs off a root empty that
# carries the 0.01 metres-per-unit scale, so a world matrix read after that empty is gone
# is a world matrix with the unit conversion thrown away -- the mesh lands 100x too big
# and 100x too far from the origin, which measures as 19642.04 mm and renders as a camera
# inside the machine. Order matters, and the failure looks like a geometry bug.
meshes = [o for o in sc.objects if o.type == 'MESH']
print(f"REPORT imported_meshes={len(meshes)} faces={sum(len(o.data.polygons) for o in meshes)}")
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = max(meshes, key=lambda o: len(o.data.vertices))
bpy.ops.object.join()
mac = bpy.context.active_object
mac.name = mac.data.name = "macstudio"
w = mac.matrix_world.copy()
mac.parent = None
mac.data.transform(w)
mac.matrix_world = Matrix.Identity(4)
for o in [x for x in sc.objects if x is not mac]:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.update()

lo, hi = bbox([mac])
dims = [(hi[i] - lo[i]) / MM for i in range(3)]
tris = sum(len(p.vertices) - 2 for p in mac.data.polygons)
mats = [ms.material for ms in mac.material_slots if ms.material]
print(f"REPORT part=macstudio tris={tris} verts={len(mac.data.vertices)} "
      f"materials={len(mats)} custom_normals={mac.data.has_custom_normals} "
      f"uv_layers={[l.name for l in mac.data.uv_layers]}")
print(f"REPORT envelope_mm=({dims[0]:.2f}, {dims[1]:.2f}, {dims[2]:.2f})  z_min_mm={lo[2]/MM:.3f}")
print(f"REPORT published_mm=(197.00, 197.00, 95.00)  "
      f"off: W {dims[0]-PUB_W:+.2f}  D {dims[1]-PUB_D:+.2f}  H {dims[2]-PUB_H:+.2f}")

# ---------------------------------------------------------------- studio
# The iMac's rig, unchanged in structure: three suns over a graded world, a dark floor for
# the contact shadow, Standard view transform. Its exposure was swept for a housing at
# 0.784/0.789/0.800 metal 0.6; this machine's shell is 0.661/0.677/0.692 metal 0.8 -- a
# little darker and more mirror-like. At the iMac's WORLD 1.45 the 3/4 hero's brightest
# 0.1% reached only 0.822 against the gate's 0.85 floor, while every other frame sat at
# 0.86-0.90: a metal is lit by the world, so the world is the knob. It takes 1.62 -- the
# hero's p99.9 climbs about 0.023 per 0.1 of world -- to put the hero at 0.86 and the
# head-on views at 0.94-0.95, with still under 0.05% of any frame above 0.98.
# The numbers that have to hold are the gate's: under 2% pure white, p99.9 over 0.85.
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

WORLD, SUN = 1.62, 0.16
bg.inputs["Strength"].default_value = WORLD
for name, rot, e in (("Key", (math.radians(48), 0, math.radians(35)), 7.6 * SUN),
                     ("Fill", (math.radians(55), 0, math.radians(25)), 2.4 * SUN),
                     ("Rim", (math.radians(118), 0, math.radians(-135)), 1.8 * SUN)):
    l = bpy.data.lights.new(name, 'SUN'); l.energy = e; l.angle = math.radians(12)
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
    o.rotation_euler = rot

# The bottom intake ring sits exactly at z = 0, so the floor goes 0.3 mm lower: at the same
# plane the two surfaces would z-fight in the contact shadow, and 0.3 mm is invisible.
bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, -0.0003))
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

# Aim and distance from the object's own vertices. `fill` is the fraction of the frame the
# longer in-plane extent takes.
def frame(off, ctr, half, lens=52, fill=0.62):
    off = Vector(off).normalized()
    d = 2 * half / fill * lens / cd.sensor_width
    cd.lens = lens
    loc = Vector(ctr) + off * d
    cam.location = loc
    cam.rotation_euler = (Vector(ctr) - loc).to_track_quat('-Z', 'Y').to_euler()

ctr = [(lo[i] + hi[i]) / 2 for i in range(3)]
half = max(hi[i] - lo[i] for i in range(3)) / 2
# The back is +y. Its two horizontal bands are read off this asset's meshes: the port strip
# at z 15.5..32.9 (Ethernet and the power button at the far -x end, four Thunderbolt at
# x 37.6..67.1), and the perforated exhaust grille above it at z 41.6..90.8.
PORTS = (0.052, 0.094, 0.0243)   # the four Thunderbolt bores
VENT = (0.0, 0.0945, 0.0700)     # the grille, for its hole density
FRONT = (-0.038, -0.096, 0.0243) # two USB-C + the SD slot + the white power LED
TOP = (0.0, 0.0, 0.0949)         # the Apple mark's plane
VIEWS = {
    "hero":  dict(off=(0.62, -0.86, 0.34), ctr=ctr),
    "front": dict(off=(0.0, -1.0, 0.08), ctr=ctr),
    "side":  dict(off=(-1.0, -0.05, 0.08), ctr=ctr),
    "back":  dict(off=(0.10, 1.0, 0.10), ctr=ctr),
    "top":   dict(off=(0.05, -0.22, 1.0), ctr=TOP, half=0.10, fill=0.92),
    "port":  dict(off=(0.02, 1.0, 0.10), ctr=PORTS, half=0.035, fill=0.80),
    "vent":  dict(off=(0.0, 1.0, 0.12), ctr=VENT, half=0.040, fill=0.90),
    "frontport": dict(off=(0.0, -1.0, 0.10), ctr=FRONT, half=0.042, fill=0.85),
}
os.makedirs(OUT, exist_ok=True)
for name, v in VIEWS.items():
    frame(v["off"], v.get("ctr", ctr), v.get("half", half), fill=v.get("fill", 0.62))
    sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"REPORT rendered={name}")

# ---------------------------------------------------------------- export
for o in sc.objects:
    o.select_set(o is mac)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "macstudio.glb"),
                          export_format='GLB', export_apply=True, use_selection=True)
print(f"REPORT glb_bytes={os.path.getsize(os.path.join(OUT, 'macstudio.glb'))}")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "macstudio.blend"))
