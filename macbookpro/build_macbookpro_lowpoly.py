# MacBook Pro (14-inch, M4) — low-poly, lid open, parts named for a consumer.
#
# Envelope from Apple's spec sheet (support.apple.com/121552): 312.6 x 221.2 x 15.5 mm.
# ONE number here is not published and not measurable; it is marked ASSUMED below.
#
# Built in the CLOSED frame and opened by a rotation of the lid group afterwards, so the
# closed envelope can still be checked against the spec sheet while the shipped pose gets
# checked against everything else. Parts are named for what they are: whoever animates
# this finds `lid`, not `Cube.004`.
#
#   Blender -b --factory-startup --python-exit-code 1 --python build_macbookpro_lowpoly.py -- ./out-lowpoly
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "/tmp/macbookpro"

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- dimensions, plain mm
BODY_W, BODY_D, BODY_H = 312.6, 221.2, 15.5   # Apple: 12.31 x 8.71 x 0.61 in
BASE_H = 9.5        # 15.5 splits into the lower chassis and the lid; the lid is thinner
LID_H = BODY_H - BASE_H
CORNER_R = 14.0     # ASSUMED. Not published, and there is no Mac anywhere in Apple's
                    # Quick Look gallery to measure it off (the Mac mini's 25 mm came from
                    # its product page's USDZ; this has no equivalent). It is a corner arc
                    # on a 312.6 mm body -- 4.5% of the width against the mini's 20% -- so
                    # an error here is a soft corner, not a wrong silhouette.
CORNER_SEG = 6
HW, HD = BODY_W / 2, BODY_D / 2               # 156.3, 110.6

KEY_U = 17.5                                  # key unit: the well is 15u = 262.5 wide
WELL_HW = 7.5 * KEY_U                         # 131.25
WELL_Y0, WELL_Y1 = -6.6, 105.2                # pocket front/back edges
ROW_PITCH = (WELL_Y1 - WELL_Y0) / 6
WELL_DEPTH, KEY_GAP, KEY_RISE = 1.2, 1.1, 0.75
WELL_R = 4.0                                  # key wells have rounded corners; this is why

TP_W, TP_D, TP_Y0 = 133.0, 84.0, -98.6        # 84 deep leaves 12 mm of palm rest
TP_REVEAL, TP_RISE = 0.30, 0.25

PANEL_INSET, PANEL_RECESS = 1.3, 0.4          # lid rim width, and how far the glass sits in
DISP_W, DISP_H = 302.5, 196.5                 # 14.2" 3024x1964 at a 360.68 mm diagonal
DISP_R = 12.0
DISP_TOP = -(HD - PANEL_INSET) + 3.75         # side bezel == top bezel == 3.75 off the rim
NOTCH_W, NOTCH_D = 7.5, 5.05

EPS = 0.12                                    # port plates stand this proud of the wall
LOGO_R, LOGO_RISE = 13.0, 0.12
HINGE_Y0, HINGE_Z1 = 103.0, 14.6
PIVOT_Y, PIVOT_Z = 104.0, 9.0                 # hinge axis, inside the base
LID_OPEN = -104.0                             # degrees: past vertical, Apple's angle

MM = 0.001                                    # the ONLY conversion, applied in finish()

# ---------------------------------------------------------------- helpers
def finish(name, bm, mats):
    """One object per part, material slots in call order, mm -> m at this single point."""
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-3)   # weld the shared seams
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.scale(bm, vec=(MM, MM, MM), verts=list(bm.verts))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    for m in mats:
        me.materials.append(m)
    return o

def rounded_rect(hw, hd, r, seg=CORNER_SEG, cy=0.0):
    """Plan boundary, CCW, four corner arcs of `seg` facets, starting at the same corner
    every time. Straight edges are implicit -- and a `r` near zero is how you get a
    rectangle. Two loops meant to be bridged by `ring()` MUST both come from here: `ring()`
    joins index to index, so loops that start at different corners bridge into bowties
    that cross the surface they were supposed to cover."""
    pts = []
    for cx, cyy, a0 in ((hw - r, -hd + r, -90), (hw - r, hd - r, 0),
                        (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            pts.append((cx + r * math.cos(a), cy + cyy + r * math.sin(a)))
    return pts

def ring(bm, outer, inner, z_out, z_in, mi):
    """Bridge two equal-length CCW loops with quads."""
    ov = [bm.verts.new((x, y, z_out)) for x, y in outer]
    iv = [bm.verts.new((x, y, z_in)) for x, y in inner]
    n = len(ov)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ov[i], ov[j], iv[j], iv[i])).material_index = mi
    return ov, iv

def poly(bm, pts, z, mi):
    bm.faces.new([bm.verts.new((x, y, z)) for x, y in pts]).material_index = mi

def box(bm, x0, x1, y0, y1, z0, z1, mi):
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for idx in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([v[i] for i in idx]).material_index = mi

def wall_at(y):
    """How far the side wall stands from the centre line at abscissa y."""
    a = abs(y)
    if a <= HD - CORNER_R:
        return HW
    d = a - (HD - CORNER_R)
    return (HD - CORNER_R) + math.sqrt(max(0.0, CORNER_R ** 2 - d * d))

# ---------------------------------------------------------------- materials
def principled(name, color, metallic, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*color, 1.0)          # what Workbench MATERIAL colour shows
    return m

mat_alu   = principled("Aluminium",  (0.62, 0.62, 0.64), 0.95, 0.34)    # bead-blasted
mat_dark  = principled("Dark",       (0.018, 0.018, 0.022), 0.15, 0.52) # well, ports, hinge
mat_key   = principled("Keycap",     (0.038, 0.038, 0.043), 0.0, 0.42)
mat_glass = principled("Trackpad",   (0.02, 0.02, 0.024), 0.0, 0.08)
mat_bezel = principled("BezelBlack", (0.012, 0.012, 0.014), 0.0, 0.30)
mat_disp  = principled("Screen",     (0.035, 0.055, 0.10), 0.0, 0.12)   # a dark desktop
mat_logo  = principled("LogoInlay",  (0.30, 0.30, 0.32), 1.0, 0.07)     # polished inlay

# ---------------------------------------------------------------- base: chassis + pocket
bm = bmesh.new()
plan = rounded_rect(HW, HD, CORNER_R)
well = rounded_rect(WELL_HW, (WELL_Y1 - WELL_Y0) / 2, WELL_R, cy=(WELL_Y0 + WELL_Y1) / 2)
ov, iv = ring(bm, plan, well, BASE_H, BASE_H, 0)        # the deck, pocket cut out of it
ring(bm, well, well, BASE_H, BASE_H - WELL_DEPTH, 1)    # pocket wall, in shadow
poly(bm, well, BASE_H - WELL_DEPTH, 1)                  # pocket floor
poly(bm, plan, 0.0, 0)                                  # underside
bv = [bm.verts.new((x, y, 0.0)) for x, y in plan]
for i in range(len(bv)):                                # side walls
    j = (i + 1) % len(bv)
    bm.faces.new((bv[i], bv[j], ov[j], ov[i])).material_index = 0
base = finish("base", bm, [mat_alu, mat_dark])

# ---------------------------------------------------------------- lid: rim + glass recess
bm = bmesh.new()
lplan = rounded_rect(HW, HD, CORNER_R)
panel = rounded_rect(HW - PANEL_INSET, HD - PANEL_INSET, CORNER_R - PANEL_INSET)
lp_ov, lp_iv = ring(bm, lplan, panel, BASE_H, BASE_H, 0)      # inner rim, seen open
ring(bm, panel, panel, BASE_H, BASE_H + PANEL_RECESS, 1)      # the glass sits this far in
poly(bm, panel, BASE_H + PANEL_RECESS, 1)                     # recess floor == the bezel
poly(bm, lplan, BODY_H, 0)                                    # the lid's top
lv = [bm.verts.new((x, y, BODY_H)) for x, y in lplan]
for i in range(len(lv)):
    j = (i + 1) % len(lv)
    bm.faces.new((lv[i], lv[j], lp_ov[j], lp_ov[i])).material_index = 0
lid = finish("lid", bm, [mat_alu, mat_bezel])

# ---------------------------------------------------------------- display: the glass
# The bezel is not its own object: it is the lid's recess floor. A separate prism capping
# the same hole looked identical and left the lid open -- 28 boundary edges round a ring
# that a consumer hiding the bezel (an exploded view, say) would read as a hole onto the
# page. One object per part means the lid is a closed frame when the display is lifted out.
bm = bmesh.new()
disp = [(x, y + DISP_TOP + DISP_H / 2)
        for x, y in rounded_rect(DISP_W / 2, DISP_H / 2, DISP_R, 8)]
poly(bm, disp, BASE_H + PANEL_RECESS + 0.05, 0)
# The notch is the one bit of a laptop screen that says which laptop: it hangs into the
# panel from the top edge, its depth matching the top bezel.
poly(bm, [(-NOTCH_W / 2, DISP_TOP), (NOTCH_W / 2, DISP_TOP),
          (NOTCH_W / 2, DISP_TOP + NOTCH_D), (-NOTCH_W / 2, DISP_TOP + NOTCH_D)],
     BASE_H + PANEL_RECESS + 0.09, 1)
screen = finish("screen", bm, [mat_disp, mat_bezel])

# ---------------------------------------------------------------- keys: 77 caps, one mesh
# Row weights in key units, back row first. Each row is normalised to the well width, so a
# row that does not sum to 15u still lands inside it -- and the widest key in a row is the
# real one's wide key (delete, return, shift, space).
ROWS = [("fn",    [1] * 14),
        ("num",   [1] * 13 + [2]),
        ("tab",   [2] + [1] * 13),
        ("caps",  [1.75] + [1] * 11 + [2.25]),
        ("shift", [2.25] + [1] * 10 + [2.75]),
        ("space", [1, 1.25, 1.25, 1.5, 4.25, 1.5, 1.25, 0.75, 0.75, 0.75, 0.75])]
bm = bmesh.new()
kz0 = BASE_H - WELL_DEPTH + 0.15
for r, (_, weights) in enumerate(ROWS):
    scale = (2 * WELL_HW) / sum(weights)
    x = -WELL_HW
    yc = WELL_Y1 - (r + 0.5) * ROW_PITCH
    for w in weights:
        w *= scale
        box(bm, x + KEY_GAP / 2, x + w - KEY_GAP / 2, yc - ROW_PITCH / 2 + KEY_GAP / 2,
            yc + ROW_PITCH / 2 - KEY_GAP / 2, kz0, kz0 + KEY_RISE, 0)
        x += w
keys = finish("keys", bm, [mat_key])

# ---------------------------------------------------------------- trackpad: glass + seam
bm = bmesh.new()
box(bm, -TP_W / 2 - TP_REVEAL, TP_W / 2 + TP_REVEAL, TP_Y0 - TP_REVEAL,
    TP_Y0 + TP_D + TP_REVEAL, BASE_H, BASE_H + 0.04, 1)
box(bm, -TP_W / 2, TP_W / 2, TP_Y0, TP_Y0 + TP_D, BASE_H, BASE_H + TP_RISE, 0)
trackpad = finish("trackpad", bm, [mat_glass, mat_dark])

# ---------------------------------------------------------------- grille, ports, hinge
bm = bmesh.new()
for s in (-1, 1):
    box(bm, s * 134.5, s * 152.0, -20.0, 102.0, BASE_H - 0.05, BASE_H + 0.03, 0)
grille = finish("grille", bm, [mat_dark])

# Real connector apertures, not guesses: MagSafe 3 ~6x3, USB-C 8.9x3.2, HDMI 15x6, SDXC
# 24x2.7, 3.5 mm jack 6x6. The 14-inch layout -- MagSafe, two Thunderbolt and the jack on
# the left, HDMI, SDXC and one Thunderbolt on the right -- and every one of them clear of
# the corner arc, which is why each plate is a single quad on a flat wall. The assert is
# the guard: a port moved past it needs the wall sampled, not a flat chord.
PORTS = [(-1, 86.0, 6.0, 3.0), (-1, 60.0, 8.9, 3.2), (-1, 38.0, 8.9, 3.2),
         (-1, 8.0, 6.0, 6.0),
         (1, 88.0, 15.0, 6.0), (1, 56.0, 24.0, 2.7), (1, 26.0, 8.9, 3.2)]
PORT_Z = 4.75
bm = bmesh.new()
for sx, cy, w, h in PORTS:
    assert abs(cy) + w / 2 <= HD - CORNER_R, f"port at y={cy} crosses the corner arc"
    x = sx * (wall_at(cy) + EPS)
    v = [bm.verts.new((x, cy - w / 2, PORT_Z - h / 2)), bm.verts.new((x, cy + w / 2, PORT_Z - h / 2)),
         bm.verts.new((x, cy + w / 2, PORT_Z + h / 2)), bm.verts.new((x, cy - w / 2, PORT_Z + h / 2))]
    bm.faces.new(v if sx < 0 else v[::-1])
ports = finish("ports", bm, [mat_dark])

bm = bmesh.new()
box(bm, -142.0, 142.0, HINGE_Y0, HD, 7.5, HINGE_Z1, 0)   # vent band, the visible hinge
hinge = finish("hinge", bm, [mat_dark])

# ---------------------------------------------------------------- logo: the marking
# Identity for this class of object is a MARKING, not an outline: a rounded slab is the
# silhouette of every laptop made since 2006. It is ~90 triangles, the cheapest
# identifying geometry in the file, and it sits on the OUTSIDE of the lid -- so it is only
# visible from behind once the lid is open, which is why there is a logo view.
bm = bmesh.new()
R, N = LOGO_R, 36
BC_U, BC_V, BR = 0.62 * R, 0.06 * R, 0.46 * R                # the bite
body = []
for i in range(N):
    a = 2 * math.pi * i / N
    u, v = R * math.cos(a), R * math.sin(a)
    if u > 0:
        du, dv = u - BC_U, v - BC_V
        d = math.hypot(du, dv)
        if d < BR:                                            # carve: push out onto the bite
            u, v = BC_U + BR * du / d, BC_V + BR * dv / d
    body.append((u, 3.0 - v))                                 # -y is the lid's "up"
poly(bm, body, BODY_H + LOGO_RISE, 0)                         # concave n-gon: ear-clipped on export
LA, LU, LV = math.radians(-28), 0.30 * R, 0.16 * R            # the leaf
leaf = []
for i in range(12):
    a = 2 * math.pi * i / 12
    eu, ev = LU * math.cos(a), LV * math.sin(a)
    leaf.append((0.10 * R + eu * math.cos(LA) - ev * math.sin(LA),
                 3.0 - (1.32 * R + eu * math.sin(LA) + ev * math.cos(LA))))
poly(bm, leaf, BODY_H + LOGO_RISE, 0)
logo = finish("logo", bm, [mat_logo])

# ---------------------------------------------------------------- open the lid
# The lid's rear corner ends up inside the base's hollow -- hidden, rather than poking out
# behind the hinge. The closed envelope is measured BEFORE this runs, because that is the
# number the spec sheet has.
LID_GROUP = [lid, screen, logo]
def dims_mm(objs):
    bpy.context.view_layer.update()
    d = bpy.context.evaluated_depsgraph_get()
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in objs:
        ev = o.evaluated_get(d)
        for c in ev.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    return [(hi[i] - lo[i]) / MM for i in range(3)]

closed = dims_mm([base, lid])
ok = all(abs(a - b) < 0.05 for a, b in zip(closed, (BODY_W, BODY_D, BODY_H)))
print(f"REPORT closed_envelope_mm=({closed[0]:.2f}, {closed[1]:.2f}, {closed[2]:.2f})  "
      f"want (312.60, 221.20, 15.50)  {'OK' if ok else 'OFF'}")

M = (Matrix.Translation(Vector((0.0, PIVOT_Y * MM, PIVOT_Z * MM)))
     @ Matrix.Rotation(math.radians(LID_OPEN), 4, 'X')
     @ Matrix.Translation(Vector((0.0, -PIVOT_Y * MM, -PIVOT_Z * MM))))
for o in LID_GROUP:
    o.data.transform(M)

# ---------------------------------------------------------------- shading
# Explicit, on the data API: bpy.ops.object.shade_smooth_by_angle() in background left a
# split shading state and wrote no sharp_edge attribute. One flat face beside smooth ones
# shades as a seam, so this is all-or-nothing per edge.
def auto_sharp(mesh, angle_deg):
    bm2 = bmesh.new(); bm2.from_mesh(mesh); bm2.edges.ensure_lookup_table()
    sharp = set()
    for e in bm2.edges:
        lf = e.link_faces
        if len(lf) == 2:
            if math.degrees(lf[0].normal.angle(lf[1].normal)) > angle_deg:
                sharp.add(e.index)
        else:
            sharp.add(e.index)
    bm2.free()
    for p in mesh.polygons:
        p.use_smooth = True
    for e in mesh.edges:
        e.use_edge_sharp = e.index in sharp
    return len(sharp)

for o in sc.objects:
    if o.type == 'MESH':
        auto_sharp(o.data, 30)

# ---------------------------------------------------------------- studio
w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
nt = w.node_tree
bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
mapr = nt.nodes.new("ShaderNodeMapRange")
# Those numbers are in the space they are used in: a Generated Z is sin(elevation) over
# -1..1, already signed. Remap as if it were 0..1 and the whole visible sky clamps dark.
# The window is wider than the Mac mini's (-0.05..0.45) on purpose: that rig was tuned on a
# squat box whose dominant face points at the zenith, this is a laptop, whose two big
# panels are VERTICAL and mirror the horizon. Raising the strength to fix them blew the
# up-facing deck to white -- which is what says the zenith was already right and the
# horizon was the dark one. So the window moves and the strength goes back.
mapr.inputs["From Min"].default_value = -0.45
mapr.inputs["From Max"].default_value = 0.35
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.025, 1)
ramp.color_ramp.elements[1].position = 1.0
ramp.color_ramp.elements[1].color = (0.70, 0.71, 0.75, 1)
nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.45

for name, rot, e in (("Key",  (math.radians(48), 0, math.radians(35)), 7.6),
                     ("Fill", (math.radians(55), 0, math.radians(25)), 2.4),
                     ("Rim",  (math.radians(118), 0, math.radians(-135)), 1.8)):
    l = bpy.data.lights.new(name, 'SUN'); l.energy = e; l.angle = 0.02
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
    o.rotation_euler = rot

bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0, 0, 0))
floor = bpy.context.active_object; floor.name = "Floor"
fm = principled("Floor", (0.035, 0.035, 0.04), 0.0, 0.62)
# A grazing floor is a mirror: its brightness is the sky it reflects, so the base colour
# is not the exposure lever. Specular IOR Level is. 0.25 keeps a sheen without clipping.
fm.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.25
floor.data.materials.append(fm)

cd = bpy.data.cameras.new("Cam"); cd.lens = 52; cd.clip_start = 0.01; cd.clip_end = 100
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
TARGET = Vector((0.0, 0.02, 0.075))
def aim(loc):
    cam.location = loc
    cam.rotation_euler = (TARGET - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

sc.render.resolution_x = 900; sc.render.resolution_y = 900
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = "Standard"
# Cycles for anything metallic: EEVEE can only show a reflection it was handed, and this
# model is bead-blasted aluminium with a glossy screen.
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 64
sc.cycles.use_denoising = True

VIEWS = {
    "hero":  (0.40, -0.62, 0.34),      # the pose Apple shoots it in
    "deck":  (0.05, -0.34, 0.66),      # keyboard, trackpad, screen layout
    "left":  (-0.62, -0.30, 0.14),     # MagSafe, two Thunderbolt, jack
    "right": (0.64, -0.26, 0.13),      # HDMI, SDXC, Thunderbolt
    "logo":  (0.42, 0.58, 0.36),       # from behind: the marking, and the open lid
}
os.makedirs(OUT, exist_ok=True)
for name, loc in VIEWS.items():
    aim(loc)
    sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"REPORT rendered={name}")

# ---------------------------------------------------------------- report + export
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
total = 0; ngons = 0; nonman = 0; parts = 0
lo, hi = [1e9] * 3, [-1e9] * 3
for o in sc.objects:
    if o.type != 'MESH' or o.name == "Floor":
        continue
    parts += 1
    ev = o.evaluated_get(dg); m2 = ev.to_mesh(); m2.calc_loop_triangles()
    total += len(m2.loop_triangles)
    ngons += sum(1 for p in m2.polygons if len(p.vertices) > 4)
    bm3 = bmesh.new(); bm3.from_mesh(m2)
    nonman += sum(1 for e in bm3.edges if len(e.link_faces) != 2)
    bm3.free()
    for c in ev.bound_box:
        w2 = o.matrix_world @ Vector(c)
        for i in range(3):
            lo[i] = min(lo[i], w2[i]); hi[i] = max(hi[i], w2[i])
    ev.to_mesh_clear()
dims = [(hi[i] - lo[i]) / MM for i in range(3)]
print(f"REPORT tris={total} parts={parts} names={[o.name for o in sc.objects if o.type == 'MESH' and o.name != 'Floor']}")
print(f"REPORT ngons={ngons} nonmanifold_edges={nonman}")
print(f"REPORT shipped_dims_mm=({dims[0]:.2f}, {dims[1]:.2f}, {dims[2]:.2f})  "
      f"z_min_mm={lo[2]/MM:.3f}")

# Export the product, not the studio: floor, lights and camera are scene furniture, and a
# 6 m ground plane in the asset is 6000 mm of wrong bounding box.
for o in sc.objects:
    o.select_set(o.type == 'MESH' and o.name != "Floor")
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "macbookpro.glb"),
                          export_format='GLB', export_apply=True, use_selection=True)
print("REPORT glb_bytes=", os.path.getsize(os.path.join(OUT, "macbookpro.glb")))

# Save LAST: whatever exists now is what the .blend contains.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "macbookpro.blend"))
