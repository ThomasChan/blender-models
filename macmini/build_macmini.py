"""Low-poly Mac mini M4 — v1.

Plan shape is a rounded square: bevel the four vertical edges of a box with a big
radius, then chamfer the top and bottom rims with a small one. Real dimensions in
metres so the model composes correctly with anything else.
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector

MM = 0.001
W = D = 127 * MM          # 127 mm square
H = 50 * MM               # 50 mm tall
CORNER_R = 25 * MM        # plan corner radius -- measured off Apple's own USDZ
                          # geometry, not eyeballed. Support function h(45)/h(0)
                          # = 1.2512 -> r/a = 0.3935 -> 25.0 mm. Product photos
                          # suggested 18 mm, which is 28% too square.
CORNER_SEG = 6            # segments around each corner arc
RIM = 1.2 * MM            # top/bottom rim chamfer
RIM_SEG = 1               # single-segment chamfer: the low-poly look, crisper
                          # highlight than a 2-segment roll, and 112 tris cheaper
                          # (was an env knob for the A/B; hardcoded so the script
                          # rebuilds what actually shipped)
HW = W/2                  # half-width; the wall is flat for |x| <= HW - CORNER_R
SEAM_Z = 6 * MM           # height of the bottom cover seam
SEAM_IN = 0.5 * MM        # how far the cover is inset at the seam
SEAM_GAP = 0.25 * MM      # height of the ledge face between the two loops

argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "/tmp/lowpoly-mine"

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'
sc.unit_settings.scale_length = 1.0

# ---------------------------------------------------------------- body
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(W, D, H), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0, 0, H/2), verts=bm.verts)

def bevel_geom(edges):
    """Bevel wants edges AND their verts, but a shared vert listed twice raises
    'found the same (BMVert/BMEdge/BMFace) used multiple times'."""
    out = []
    for e in edges:
        out.append(e)
        for v in e.verts:
            if v not in out:
                out.append(v)
    return out

# vertical edges -> the rounded-square plan
vert_e = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-9]
bmesh.ops.bevel(bm, geom=bevel_geom(vert_e),
                offset=CORNER_R, offset_type='OFFSET', segments=CORNER_SEG,
                profile=0.5, affect='EDGES', clamp_overlap=True)

# add the seam loop: bisect the side walls at SEAM_Z
geom = bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              plane_co=(0,0,SEAM_Z), plane_no=(0,0,1),
                              clear_inner=False, clear_outer=False)
seam_edges = [e for e in geom['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]

# A coplanar loop at SEAM_Z is invisible: measured dihedral 0.0 deg. A step needs
# TWO loops -- one left on the outer wall, one just below it pulled inward -- so
# the face between them is a ledge. Moving a single loop inward only tilts the
# whole wall below it, which is 0.5 mm of slope over 6 mm and reads as nothing.
bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                       plane_co=(0,0,SEAM_Z-SEAM_GAP), plane_no=(0,0,1),
                       clear_inner=False, clear_outer=False)
below = [v for v in bm.verts if v.co.z < SEAM_Z - SEAM_GAP/2]
for v in below:
    r = math.hypot(v.co.x, v.co.y)
    if r > 1e-9:
        k = max(0.0, (r - SEAM_IN)) / r
        v.co.x *= k; v.co.y *= k

# horizontal edges -> top/bottom rim chamfer (do this after the seam so the seam
# loop is not part of the rim selection)
horiz_e = [e for e in bm.edges
           if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9
           and (abs(e.verts[0].co.z - H) < 1e-9 or abs(e.verts[0].co.z) < 1e-9)]
bmesh.ops.bevel(bm, geom=bevel_geom(horiz_e),
                offset=RIM, offset_type='OFFSET', segments=RIM_SEG,
                profile=0.5, affect='EDGES', clamp_overlap=True)

bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
me = bpy.data.meshes.new("MacMini"); bm.to_mesh(me); bm.free()
body = bpy.data.objects.new("MacMini", me); sc.collection.objects.link(body)

# ---------------------------------------------------------------- materials
def principled(name, color, metallic, rough, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = 2.0
    m.diffuse_color = (*color, 1.0)
    return m

alu  = principled("Aluminium", (0.62,0.62,0.64), 0.85, 0.34)
dark = principled("PortDark",  (0.03,0.03,0.035), 0.2, 0.55)
led  = principled("LED",       (0.1,0.9,0.4), 0.0, 0.4, emit=(0.1,1.0,0.45))
body.data.materials.append(alu)
body.data.materials.append(dark)
body.data.materials.append(led)

# ---------------------------------------------------------------- ports
# Decal plates 0.15 mm proud of the wall: a port is a dark rectangle, not a
# boolean. Two triangles each, except where the plate crosses the corner arc
# and has to bend with the wall.
def wall_profile(x):
    """How far the wall stands from the centre line at abscissa x -- the same
    rounded square the body was built from."""
    a = abs(x)
    if a <= HW - CORNER_R:
        return HW
    d = a - (HW - CORNER_R)
    return (HW - CORNER_R) + math.sqrt(max(0.0, CORNER_R**2 - d*d))

def wall_cuts(x0, x1):
    """x samples for a plate spanning x0..x1. One span is correct on the flat
    face; across the arc the wall falls away from any straight chord, so sample
    it. 3 mm chords sag 0.05 mm, well inside the 0.15 mm standoff."""
    flat = HW - CORNER_R
    xs = [x0] + [t for t in (flat, -flat) if x0 < t < x1] + [x1]
    out = [xs[0]]
    for a, b in zip(xs, xs[1:]):
        # cutting at +/-flat means no span straddles the boundary: it is flat and
        # needs one quad, or it is arc and needs sampling
        n = 1 if max(abs(a), abs(b)) <= flat else max(1, int(math.ceil((b - a)/(3*MM))))
        out += [a + (b - a)*i/n for i in range(1, n+1)]
    return out

def plate(name, side, cx, z, w, h, mat_i, parent):
    """A port decal lying ON the wall. side = +1 back (+Y), -1 front (-Y).

    Not a flat quad at a fixed y: the first build put the power inlet at
    x -56.5..-43.5 on the plane y = 63.5 while the 25 mm corner arc had already
    pulled the wall back to 60.70 there, so the plate floated ~3 mm proud and
    rendered as a black rectangle hanging outside the silhouette. Apple's own
    machine has the same problem to solve -- its ports run from x -45, inside
    the curve -- so the wall has to be followed, not averaged.
    """
    bm2 = bmesh.new()
    xs = wall_cuts(cx - w/2, cx + w/2)
    col = [(bm2.verts.new((x, side*(wall_profile(x) + EPS), z - h/2)),
            bm2.verts.new((x, side*(wall_profile(x) + EPS), z + h/2))) for x in xs]
    for (a0, a1), (b0, b1) in zip(col, col[1:]):
        bm2.faces.new((a0, a1, b1, b0) if side > 0 else (a0, b0, b1, a1))
    m2 = bpy.data.meshes.new(name); bm2.to_mesh(m2); bm2.free()
    o = bpy.data.objects.new(name, m2); sc.collection.objects.link(o)
    o.data.materials.append(mat_i)
    o.parent = parent
    return o

EPS = 0.15*MM
# Port centres sit in the lower half of the wall, the way they do on the real
# machine. Grouped by function with a real gap between groups, not an even ladder
# -- an even ladder of equal-height slots is what reads as a barcode.
# Sizes are the real connector apertures, not guesses: a USB-C receptacle is about
# 8.9 x 3.2 mm, HDMI about 15 x 6, RJ45 about 16 x 13. Guessing these too tall is
# what makes a port row read as a row of bricks instead of a row of ports.
PORT_Z = 21*MM
def row(items, side, tag=""):
    for i, (cx, w, h, mat) in enumerate(items):
        plate(f"p_{'b' if side > 0 else 'f'}{tag}_{i}",
              side, cx*MM, PORT_Z, w*MM, h*MM, mat, body)

# front: 3.5 mm jack, two USB-C, then the status LED  (Apple lists these)
row([( 19, 6.0, 6.0, dark),      # 3.5 mm jack
     (  6, 8.9, 3.2, dark),      # USB-C
     ( -5, 8.9, 3.2, dark)],     # USB-C
    -1)
plate("f_led", -1, -25*MM, PORT_Z, 2.6*MM, 2.6*MM, led, body)

# back: AC power, Ethernet, HDMI, then three Thunderbolt
row([(-50, 13.0, 10.0, dark),    # IEC power inlet
     (-33, 16.0, 13.0, dark),    # RJ45
     (-14, 15.0,  6.0, dark)],   # HDMI
    +1)
row([( 10, 8.9, 3.2, dark),      # Thunderbolt x3, tight group
     ( 20, 8.9, 3.2, dark),
     ( 30, 8.9, 3.2, dark)],
    +1, "2")

# ---------------------------------------------------------------- shading
# Explicit, on the data API. bpy.ops.object.shade_smooth_by_angle() in background
# left the top face flat and its neighbours smooth and wrote no sharp_edge
# attribute at all -- a split shading state that renders as a diagonal seam
# across the top. Doing it by hand is deterministic and needs no context.
def auto_sharp(mesh, angle_deg):
    """Smooth every face; mark an edge sharp where the dihedral angle exceeds
    angle_deg. One flat face next to smooth ones shades as a seam, so this is
    all-or-nothing per edge, not per face."""
    bm2 = bmesh.new(); bm2.from_mesh(mesh); bm2.edges.ensure_lookup_table()
    sharp = set()
    for e in bm2.edges:
        lf = e.link_faces
        if len(lf) == 2:
            if math.degrees(lf[0].normal.angle(lf[1].normal)) > angle_deg:
                sharp.add(e.index)
        else:
            sharp.add(e.index)          # boundary / non-manifold: keep it crisp
    bm2.free()
    for p in mesh.polygons:
        p.use_smooth = True
    for e in mesh.edges:
        e.use_edge_sharp = e.index in sharp
    return len(sharp)

n_sharp = auto_sharp(me, 30)
print(f"REPORT sharp_edges={n_sharp} of {len(me.edges)}")

# ---------------------------------------------------------------- studio world
w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
nt = w.node_tree
bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
mapr = nt.nodes.new("ShaderNodeMapRange")
mapr.inputs["From Min"].default_value = -0.05
mapr.inputs["From Max"].default_value =  0.45
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.025, 1)
ramp.color_ramp.elements[1].position = 1.0
ramp.color_ramp.elements[1].color = (0.70, 0.71, 0.75, 1)
nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.45

# ---------------------------------------------------------------- lights
for name, rot, e in (("Key",  (math.radians(48), 0, math.radians(35)), 7.6),
                     ("Fill", (math.radians(55), 0, math.radians(25)), 2.4),
                     ("Rim",  (math.radians(118), 0, math.radians(-135)), 1.8)):
    l = bpy.data.lights.new(name, 'SUN'); l.energy = e; l.angle = 0.02
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
    o.rotation_euler = rot

# ---------------------------------------------------------------- floor
bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0, 0, 0))
floor = bpy.context.active_object; floor.name = "Floor"
fm = principled("Floor", (0.035, 0.035, 0.04), 0.0, 0.62)
# At a grazing angle the floor is a mirror: Fresnel goes to 1 regardless of base
# colour, so a dark floor still reflects the bright sky. Base colour is not the
# exposure lever here -- Specular IOR Level is. Measured on the back view:
# IOR 0.5 -> 2.24% of the frame blown; IOR 0.0 -> 0.08%. Keeping a little sheen.
fm.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.25
floor.data.materials.append(fm)

# ---------------------------------------------------------------- camera
cd = bpy.data.cameras.new("Cam"); cd.lens = 52; cd.clip_start = 0.01; cd.clip_end = 100
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
TARGET = Vector((0, 0, H*0.42))
def aim(loc):
    cam.location = loc
    cam.rotation_euler = (TARGET - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

sc.render.resolution_x = 900; sc.render.resolution_y = 900
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = "Standard"
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 64

VIEWS = {
    "hero":  ( 0.20, -0.22, 0.145),
    "front": ( 0.00, -0.28, 0.075),
    "back":  ( 0.00,  0.28, 0.075),
    "top":   ( 0.10, -0.10, 0.30),
}
os.makedirs(OUT, exist_ok=True)
for name, loc in VIEWS.items():
    aim(loc)
    sc.render.filepath = os.path.join(OUT, f"v1-{name}.png")
    bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- report + export
# Measure what ships: the whole scene, not just the body. The body-only bbox said
# 127.0 while the port plates stand 0.15 mm proud of it.
dg = bpy.context.evaluated_depsgraph_get()
total = 0
lo = [ 1e9]*3; hi = [-1e9]*3; ngons = 0; nonman = 0
for o in sc.objects:
    if o.type != 'MESH' or o.name == "Floor": continue
    ev = o.evaluated_get(dg); m2 = ev.to_mesh(); m2.calc_loop_triangles()
    total += len(m2.loop_triangles)
    ngons += sum(1 for p in m2.polygons if len(p.vertices) > 4)
    bm3 = bmesh.new(); bm3.from_mesh(m2)
    nonman += sum(1 for e in bm3.edges if len(e.link_faces) != 2)
    bm3.free()
    for c in ev.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    ev.to_mesh_clear()
dims = [hi[i]-lo[i] for i in range(3)]
print(f"REPORT tris={total} faces={len(me.polygons)} verts={len(me.vertices)}")
print(f"REPORT ngons={ngons} nonmanifold_edges={nonman}")
print(f"REPORT dims_mm=({dims[0]/MM:.2f}, {dims[1]/MM:.2f}, {dims[2]/MM:.2f})  "
      f"z_min_mm={lo[2]/MM:.3f}")
EXPECT = (127.0, 127.0, 50.0)
bad = [i for i in range(3) if abs(dims[i]/MM - EXPECT[i]) > 0.5]
print("REPORT size_check=" + ("OK" if not bad else f"OFF on axes {bad}"))

# Export the product, not the studio. The floor, the lights and the camera are
# scene furniture; the exporter takes everything in the scene unless told
# otherwise, and a 6 m ground plane in the asset is 6000 mm of wrong bounding box.
for o in sc.objects:
    o.select_set(o.type == 'MESH' and o.name != "Floor")
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "macmini-lowpoly.glb"),
                          export_format='GLB', export_apply=True, use_selection=True)
print("REPORT glb_bytes=", os.path.getsize(os.path.join(OUT, "macmini-lowpoly.glb")))

# Save LAST. Whatever exists at this point is what the .blend contains -- saving
# earlier ships a file with no camera, no lights and no floor in it.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "macmini-lowpoly.blend"))
