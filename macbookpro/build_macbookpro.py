# MacBook Pro (14-inch, M4) -- high-precision build. The 1,530-triangle version is
# build_macbookpro_lowpoly.py; this is the same machine at production density.
#
# What "high precision" means here, precisely: denser surfaces and real cutouts -- a lofted
# edge-fillet profile, 20-segment plan corners, 1,152 speaker perforations, real port wells,
# a camera in the notch. NOT CAD fidelity. Apple publishes the envelope, the port apertures
# and the panel's active area; everything else is derived or an ASSUMED number, and there is
# no Mac USDZ in Apple's Quick Look gallery to measure against.
#
# Booleans, not hand-bridged rings: a cutout this dense is a cutter object and one
# DIFFERENCE per part -- which is also why the keyboard well needs no ring topology here.
#
# Built in the CLOSED frame and opened by a rotation afterwards, so the closed envelope is
# still checkable against the spec sheet.
#
#   Blender -b --factory-startup --python-exit-code 1 --python build_macbookpro.py -- .
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
# Defaults to the current directory rather than /tmp: run bare from this folder it rewrites
# the files that ship here, which is what a bare run should do. (The first version wrote to
# /tmp/macbookpro-hi and every measurement of "the defect is still there" was of a stale
# ./out-hi/macbookpro.blend that no run had touched.)
OUT = os.path.abspath(argv[0] if argv else ".")
HERE = os.path.dirname(os.path.abspath(__file__))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- dimensions, plain mm
BODY_W, BODY_D, BODY_H = 312.6, 221.2, 15.5   # Apple spec sheet
HW, HD = BODY_W / 2, BODY_D / 2
BASE_H = 9.5          # the deck plane
LID_IN = 10.0         # the lid's inner face: a keycap's height above the deck, which is
                      # what lets the keys stand PROUD of the deck and still shut
CORNER_R = 14.0       # ASSUMED. Not published, and there is no Mac USDZ anywhere in
                      # Apple's gallery to measure it off. 4.5% of the body width against
                      # the Mac mini's 20%, so an error here is a softer corner, not a wrong
                      # silhouette. The one guessed number in the file.
CORNER_SEG = 20       # the low-poly build used 6; this is the loudest precision tell
SEAM = 0.15           # the lid's skirt sits this far inboard of the deck's edge
FOOT_H = 0.45         # the feet stand the body this far off the desk

WELL_Y0, WELL_Y1 = -6.6, 105.2
WELL_HW = 131.25
WELL_R, WELL_DEPTH = 4.0, 1.00
KEY_GAP, KEY_CROWN = 1.05, 0.45
ROW_PITCH = (WELL_Y1 - WELL_Y0) / 6

TP_W, TP_D, TP_Y0 = 133.0, 84.0, -98.6
TP_RECESS, TP_R, TP_SEAM, TP_PROUD = 0.55, 7.0, 0.35, 0.10

PANEL_INSET, PANEL_DEEP, PANEL_R, GLASS_T = 1.6, 0.45, 9.0, 0.38
# The 14.2" panel is 3024x1964 over a 302.4 x 196.4 mm active area. The black border around
# it is a uniform ~3.5 mm on all four sides (Apple's published figure; straight-on hands-on
# photos measure ~20 px at 5.46 px/mm on the sides and bottom, and the top reads a little
# thicker only because the lid's top chamfer is in the same dark band). The glass plate is
# therefore active + 2*BEZEL = 309.4 x 203.4 mm, leaving a 1.6 mm aluminium lip to the lid
# edge. The lit image is inset to the active area: it must NOT reach the glass edge, because
# the border is part of the hardware.
BEZEL = 3.5
SCREEN_W, SCREEN_H = 302.4, 196.4          # the 14.2" panel's active area; the image's aspect
# Top-anchored: PANEL_INSET of aluminium, then the glass plate (BEZEL + active area + BEZEL).
# The leftover lid depth below the glass is the aluminium strip over the hinge.
PANEL_TOP = -(HD - PANEL_INSET)
PANEL_HALF = (BEZEL + SCREEN_H + BEZEL) / 2
PANEL_CY = PANEL_TOP + PANEL_HALF

def panel_plan():
    return plan(HW - PANEL_INSET, PANEL_HALF, PANEL_R, cy=PANEL_CY)

def screen_plan():
    # The active area: the glass plan inset by the bezel, so the corner radius comes down
    # with it and the black border stays a true 3.5 mm all the way round the corners.
    return plan(SCREEN_W / 2, SCREEN_H / 2, PANEL_R - BEZEL, cy=PANEL_CY)

def notch_pts(y_top, depth, n=8):
    """The notch's U contour, walked left to right: open at `y_top`, straight sides, and
    rounded bottom corners. Used for both the glass cut and the screen's bite, so the two
    cannot drift apart."""
    x, r, yb = NOTCH_W / 2, NOTCH_R, y_top + depth
    pts = [(-x, y_top)]
    for i in range(n + 1):                       # bottom-left quarter
        a = math.radians(180 - 90 * i / n)
        pts.append((-(x - r) + r * math.cos(a), (yb - r) + r * math.sin(a)))
    for i in range(n + 1):                       # bottom-right quarter
        a = math.radians(90 - 90 * i / n)
        pts.append(((x - r) + r * math.cos(a), (yb - r) + r * math.sin(a)))
    pts.append((x, y_top))
    return pts

# The notch is a 37 mm-wide tab, not a 7.4 mm slot: hands-on 14" photos give a 204 px dark
# run against a ~1670 px active width at the notch row = 36.8 mm, and its bottom corners are
# rounded at ~2.8 mm. It drops 6.4 mm below the active area's top edge -- macOS's 32 pt
# (6.4 mm at 2x) safeAreaInsets.top and the photo's ~35 px both say so; the 74 px figure is
# the whole menu-bar strip, not the cutout. The glass cut is the same U plus the 3.5 mm top
# bezel, so its bottom lands on the same line as the screen's bite.
NOTCH_W, NOTCH_D, NOTCH_R, CAM_R = 37.0, 6.4, 2.8, 1.1

GRILLE_X0, GRILLE_X1 = 135.5, 151.5
GRILLE_Y0, GRILLE_Y1 = -24.0, 100.0
HOLE_R, HOLE_PITCH, HOLE_DEEP = 0.42, 1.95, 0.75

# side, y, opening w x h, corner radius. The layout is the real one -- MagSafe 3 and HDMI at
# the back of their edge, the jack at the front of the left one, Thunderbolt ports 15 mm apart
# on centre -- and the openings are the real shapes: a stadium for USB-C, round for the jack.
# Positions are read off Apple's press shots; like CORNER_R there is no Mac USDZ to measure.
PORTS = [(-1, 92.0, 6.6, 3.4, 1.6), (-1, 73.0, 9.0, 3.2, 1.5), (-1, 58.0, 9.0, 3.2, 1.5),
         (-1, 12.0, 4.2, 4.2, 2.1),
         (1, 92.0, 15.6, 6.4, 0.9), (1, 60.0, 24.4, 3.4, 0.8), (1, 30.0, 9.0, 3.2, 1.5)]
PORT_Z, PORT_LIP, PORT_BORE = 4.6, 2.0, 4.0

LOGO_W, LOGO_RISE = 9.75, 0.10      # half-width of the mark's body
# The hinge cover sits under the shut lid's inner face (LID_IN + PANEL_DEEP), so it reads as a
# strip of the deck rather than a bar standing in the display's way.
HINGE_Y0, HINGE_HW, HINGE_Z0, HINGE_Z1 = 104.5, 147.5, 6.5, 10.40
VENT_Y0, VENT_D, VENT_DEEP = 107.6, 1.6, 0.70      # the exhaust slot, behind the cover
# The hinge axis IS the deck's rear edge, and that is a measurement, not a preference: it is
# the one axis about which the display's own bottom-rear corner does not move. Put it anywhere
# lower or further forward and that corner arcs down through the deck -- at (104.0, 9.0) it
# finished 7.65 mm inside the base, which is the screen-inside-the-base the renders showed.
PIVOT_Y, PIVOT_Z = HD - SEAM, BASE_H
LID_OPEN = -104.0

MM = 0.001

# ---------------------------------------------------------------- helpers
def plan(hw, hd, r, seg=CORNER_SEG, cy=0.0):
    """CCW plan boundary: four corner arcs, always the same corner first, same direction
    round. Two loops meant to be bridged MUST both come from here -- loops built by
    different rules bridge into a bowtie and render as black wedges on a flat panel."""
    pts = []
    for cx, cyy, a0 in ((hw - r, -hd + r, -90), (hw - r, hd - r, 0),
                        (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            pts.append((cx + r * math.cos(a), cy + cyy + r * math.sin(a)))
    return pts

def stack(bm, rings, mi=0, cap_bottom=True, cap_top=True):
    """Bridge a list of vertex rings, in order, into a solid."""
    for a, b in zip(rings, rings[1:]):
        for i in range(len(a)):
            j = (i + 1) % len(a)
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mi
    if cap_bottom:
        bm.faces.new(rings[0][::-1]).material_index = mi
    if cap_top:
        bm.faces.new(rings[-1]).material_index = mi
    return rings

def ring(bm, pts, z):
    return [bm.verts.new((x, y, z)) for x, y in pts]

def prism(bm, pts, z0, z1, mi=0):
    """Closed plate. n-gon caps: a rounded-rect n-gon costs 4*(seg+1) triangles where a fan
    costs hundreds, and the gate prints n-gon counts without ever failing on them."""
    return stack(bm, [ring(bm, pts, z0), ring(bm, pts, z1)], mi)

def annulus(bm, outer, inner, z0, z1, mi=0):
    """A closed ring solid: the lid's rim, which drops the 0.5 mm to the deck while the
    display sits a keycap's height above it."""
    return stack(bm, [ring(bm, outer, z0), ring(bm, outer, z1),
                      ring(bm, inner, z1), ring(bm, inner, z0), ring(bm, outer, z0)], mi,
                 cap_bottom=False, cap_top=False)

def loft(bm, levels, mi=0):
    """The body: a side wall following a vertical profile. `levels` is [(z, inset), ...] and
    each level is the plan inset by that much -- concentric arcs, so insetting a rounded
    rect is r - inset and the corner radius stays true. This is how a machined edge gets
    modelled: a radius in the vertical profile, not a bevel bolted on afterwards."""
    return stack(bm, [ring(bm, plan(HW - i, HD - i, max(CORNER_R - i, CORNER_R * 0.2)), z)
                      for z, i in levels], mi)

def slot(bm, cx, cy, w, d, z0, z1, r, crown, mi=0):
    """One keycap: walls, a chamfer, a flat top. The chamfer is what makes a cap catch a
    highlight instead of reading as a grey tile."""
    return stack(bm, [ring(bm, [(x + cx, y + cy) for x, y in plan(w / 2, d / 2, r, 4)], z)
                      for z in (z0, z1 - crown)] +
                 [ring(bm, [(x + cx, y + cy) for x, y in
                            plan(w / 2 - crown, d / 2 - crown, max(r - crown, r * 0.3), 4)], z1)],
                 mi)

def rect(bm, cx, cy, w, d, z0, z1, mi=0):
    return prism(bm, [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2),
                      (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)], z0, z1, mi)

def port(bm, cx, cy, cz, depth, w, h, r, mi=0):
    """A port opening: a rounded rect in the wall's plane, extruded sideways through it.
    plan() builds in XY, and its X must become the world's Y (width along the edge) for the
    loop to keep its winding -- a reflected loop is inside out, and an inside-out shell inside
    a many-shell cutter is exactly what silently removed nothing from the Apple pocket."""
    pts = plan(w / 2, h / 2, min(r, min(w, h) / 2 - 1e-4), 5)
    return stack(bm, [[bm.verts.new((cx + d * depth / 2, cy + px, cz + py))
                       for px, py in pts] for d in (-1, 1)], mi)

def circle(cx, cy, r, n):
    return [(r * math.cos(2 * math.pi * i / n) + cx, r * math.sin(2 * math.pi * i / n) + cy)
            for i in range(n)]

def tri_caps(bm):
    """Triangulate the n-gon caps before the boolean. One hole cut into an 84-gon re-clips
    the entire face and costs thousands of triangles; the same hole in a triangle costs a
    handful. 1,152 holes is the difference between 15k triangles and 200k."""
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])

def finish(name, bm, mats):
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-3)
    bmesh.ops.scale(bm, vec=(MM, MM, MM), verts=list(bm.verts))
    # No recalc_face_normals: with many disjoint islands -- the base's cutter has 1169 -- it
    # picks the wrong side, and an inside-out operand makes DIFFERENCE delete the whole
    # target rather than erroring. Every builder here winds outward by construction, so the
    # signed volume both proves it and repairs it if a builder is ever wrong.
    vol = bm.calc_volume(signed=True)
    if vol < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    for m in mats:
        me.materials.append(m)
    print(f"REPORT part={name} volume_mm3={abs(vol) / MM ** 3:.1f} flipped={vol < 0}")
    return o

def cut(target, build, name):
    """One boolean per part, every one of that part's cutouts in a single operand. bmesh has
    no boolean, so the modifier is the tool -- and it is applied immediately, because a
    modifier left in the stack means the .blend lies about the geometry."""
    bm = bmesh.new()
    n = build(bm)
    # The operand goes through finish() too: it must be in metres like its target (a cutter
    # left in millimetres is 1000x too big and misses entirely -- DIFFERENCE then returns the
    # target unchanged and reports FINISHED), and its normals must point outward.
    o = finish(name, bm, [])
    m = target.modifiers.new(name, 'BOOLEAN')
    m.operation, m.object, m.solver = 'DIFFERENCE', o, 'EXACT'
    # An operand of overlapping shells is self-intersecting by construction -- each port is a
    # lip box that overlaps its bore box -- and EXACT assumes it is not unless told. Untold,
    # it resolved the 1169-shell operand to "delete the entire target" and returned FINISHED.
    m.use_self = True
    bpy.context.view_layer.objects.active = target
    before = len(target.data.vertices)
    bmx = bmesh.new(); bmx.from_mesh(o.data)
    vs = [v.co[:] for v in o.data.vertices]
    print(f"REPORT cutter={name} verts={len(vs)} faces={len(o.data.polygons)} "
          f"volume_mm3={bmx.calc_volume() / MM ** 3:.1f} "
          f"lo_mm={[round(min(v[i] for v in vs) / MM, 2) for i in range(3)]} "
          f"hi_mm={[round(max(v[i] for v in vs) / MM, 2) for i in range(3)]}")
    bmx.free()
    with bpy.context.temp_override(object=target, active_object=target,
                                   selected_objects=[target],
                                   selected_editable_objects=[target]):
        status = bpy.ops.object.modifier_apply(modifier=name)
    after = len(target.data.vertices)
    # A cutter needs no selection to exist, and modifier_apply returns CANCELLED -- not an
    # exception -- when its context is short. The first version of this file built a base
    # with no well, no ports and no perforations and printed a perforation count anyway.
    if status != {'FINISHED'} or after <= before:
        raise RuntimeError(f"boolean {name}: {status}, verts {before} -> {after}")
    bpy.data.objects.remove(o, do_unlink=True)
    return n

def paint(o, pred, mi):
    """Reassign a material by predicate rather than trusting the boolean to carry the
    cutter's slot across: a predicate can be checked in the render, a slot mapping cannot."""
    n = 0
    for p in o.data.polygons:
        if p.material_index != mi and pred(p.center):
            p.material_index = mi
            n += 1
    return n

def probe_ray(tag, to_mesh=None):
    """What a viewer's ray meets above the panel centre, named in build coordinates. The
    first hit must be glass/Glass at LID_IN+0.06: anything ahead of it is a sheet the
    recess cut failed to remove, and no amount of face counting says which."""
    dg = bpy.context.evaluated_depsgraph_get()
    o, d = Vector((0.0, 0.0, 8.0 * MM)), Vector((0.0, 0.0, 1.0))
    if to_mesh is not None:
        o, d = to_mesh @ o, (to_mesh.to_3x3() @ d).normalized()
    inv = None if to_mesh is None else to_mesh.inverted()
    out = []
    for _ in range(5):
        hit, loc, nrm, idx, obj, _ = bpy.context.scene.ray_cast(dg, o, d, distance=0.5)
        if not hit:
            break
        m = obj.data.materials[obj.data.polygons[idx].material_index]
        z = (inv @ loc if inv else loc).z / MM
        out.append(f"{obj.name}/{m.name if m else '-'}@{z:.3f}")
        o = loc + d * 1e-6
    print(f"REPORT ray[{tag}]= " + "  ".join(out))

def principled(name, color, metallic, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*color, 1.0)
    return m

def emissive_image(name, path, strength=1.0):
    """The lit display: an image through an Image Texture node, not a procedural gradient --
    glTF drops every procedural shading node, and the exported model would come back black.
    The image is packed into the GLB by the exporter; the file next to this script is a source
    asset, generated by ../hello_screen.py from the drawing in Apple's Hello bundle."""
    m = principled(name, (0.0, 0.0, 0.0), 0.0, 0.5)
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.image.colorspace_settings.name = 'sRGB'
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Emission Color"])
    nt.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = strength
    return m

mat_alu   = principled("Aluminium", (0.62, 0.62, 0.64), 0.95, 0.32)
mat_dark  = principled("Dark",      (0.018, 0.018, 0.022), 0.15, 0.50)
mat_key   = principled("Keycap",    (0.020, 0.020, 0.024), 0.0, 0.50)
mat_glass = principled("Glass",     (0.012, 0.012, 0.016), 0.0, 0.22)
# The notch is a hole through the glass. Behind it the lid's Dark floor is glossy enough to
# catch the studio world and read grey; this matte plate makes the cutout read black.
mat_notch = principled("Notch",     (0.004, 0.004, 0.005), 0.0, 0.92)
# Bright and near-mirror. The lid's outer face is metallic 0.95 / roughness 0.32, so it reads
# as whatever it reflects -- pale against the sky, near-black against the floor. An inlay
# darker than that disappears whenever the panel goes dark (it did, in preview-logo, at both
# 0.05 and 0.16 roughness). Light and polished, it keeps a highlight at every angle.
mat_logo  = principled("LogoInlay", (0.30, 0.30, 0.32), 1.0, 0.07)
# Bare glass, colour-matched to the body it sits in -- which is what a silver MacBook's trackpad
# is: the same pale grey as the aluminium, a shade darker and far glossier. It was near-black
# (0.010) on the theory that a trackpad mirrors the way the display does; the render said
# otherwise, and so does the machine. The trackpad is the one panel Apple does NOT contrast.
# It is also the one panel here that lies face up, and that is what 0.58 got wrong. The deck's
# other surfaces are METAL: they only reflect, so they come out grey whatever the sky does. This
# one is a dielectric facing the light, so it takes all three suns as diffuse on top of the sky
# -- about 3.4 in radiance terms -- and 0.58 of that clipped flat white, brighter than the
# aluminium it is meant to match. 0.24 x 3.4 lands on the palm rest's own 0.8, and roughness
# 0.16 keeps the glassy highlight that says trackpad rather than painted panel.
mat_tp    = principled("Trackpad",  (0.24, 0.24, 0.26), 0.0, 0.16)
mat_leg   = principled("Legend",    (0.36, 0.36, 0.38), 0.0, 0.45)
mat_scr   = emissive_image("Screen", os.path.join(HERE, "hello-screen.png"))
# A flat glossy dielectric mirrors the sky whatever its albedo, so a 0.02 keycap read as a
# light grey tile and a 0.012 screen as bare aluminium. The lever is the specular, not the
# base colour -- the same lesson the studio floor taught, one surface over.
for _m in (mat_key, mat_glass):
    _m.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.20

# ---------------------------------------------------------------- base
bm = bmesh.new()
loft(bm, [(0.00, 1.30), (0.30, 0.72), (0.62, 0.30), (1.05, 0.06), (1.55, 0.00),
          (7.60, 0.00), (8.10, 0.10), (8.58, 0.40), (8.98, 0.82), (9.30, 1.28),
          (BASE_H, SEAM)], 0)
tri_caps(bm)
base = finish("base", bm, [mat_alu, mat_dark])

IN_WELL = lambda x, y: abs(x) <= WELL_HW + 0.2 and WELL_Y0 - 0.2 <= y <= WELL_Y1 + 0.2
IN_TP   = lambda x, y: abs(x) <= TP_W / 2 + TP_SEAM + 0.2 and TP_Y0 - 0.2 <= y <= TP_Y0 + TP_D + 0.2
IN_GRIL = lambda x, y: GRILLE_X0 - 0.6 <= abs(x) <= GRILLE_X1 + 0.6 and GRILLE_Y0 - 0.2 <= y <= GRILLE_Y1 + 0.2
IN_VENT = lambda x, y: abs(x) <= HINGE_HW - 0.8 and VENT_Y0 - 0.2 <= y <= VENT_Y0 + VENT_D + 0.2

def base_cut(bm):
    prism(bm, plan(WELL_HW, (WELL_Y1 - WELL_Y0) / 2, WELL_R, 8, (WELL_Y0 + WELL_Y1) / 2),
          BASE_H - WELL_DEPTH, BASE_H + 1.0)                      # keyboard well
    prism(bm, plan(TP_W / 2 + TP_SEAM, TP_D / 2 + TP_SEAM, TP_R, 6, TP_Y0 + TP_D / 2),
          BASE_H - TP_RECESS, BASE_H + 1.0)                       # trackpad recess
    prism(bm, plan(HINGE_HW - 1.0, VENT_D / 2, 0.8, 4, VENT_Y0 + VENT_D / 2),
          BASE_H - VENT_DEEP, BASE_H + 1.0)                       # exhaust vent at the hinge
    n = 0
    for sx in (-1, 1):                                            # speaker perforations
        x, col = GRILLE_X0, 0
        while x <= GRILLE_X1:
            y = GRILLE_Y0 + (HOLE_PITCH / 2 if col % 2 else 0.0)
            while y <= GRILLE_Y1:
                prism(bm, circle(sx * x, y, HOLE_R, 6), BASE_H - HOLE_DEEP, BASE_H + 1.0)
                n += 1; y += HOLE_PITCH
            x += HOLE_PITCH; col += 1
    for sx, cy, w, h, r in PORTS:                        # chamfered mouth, then connector bore
        port(bm, sx * (HW - 0.8), cy, PORT_Z, PORT_LIP, w + 0.7, h + 0.7, r + 0.35)
        port(bm, sx * (HW - 3.2), cy, PORT_Z, PORT_BORE, w, h, r)
    return n

holes = cut(base, base_cut, "base_cut")

# Everything a cutter opened looks into the machine. The z floor keeps the underside out of
# it: the base's bottom face is ONE face whose centre lands inside the keyboard well's
# footprint, so without it the whole underside turns black and nothing says so.
paint(base, lambda c: 4.0 < c.z * 1000 < BASE_H - 0.15 and
      (IN_WELL(c.x * 1000, c.y * 1000) or IN_TP(c.x * 1000, c.y * 1000) or
       IN_GRIL(c.x * 1000, c.y * 1000) or IN_VENT(c.x * 1000, c.y * 1000)), 1)
for sx, cy, w, h, r in PORTS:
    # The bore only: that is the connector's own cavity. The mouth's chamfer is machined into the
    # aluminium and stays aluminium, which also means the box has to stop short of it. This box
    # used to be 4 mm deep in x on either side of the wall, so it caught the OUTER wall around
    # every opening -- a black rectangle the size of the port, with a bright sliver through it
    # wherever a face's centre fell outside the box. That is what the power inlet's rendering
    # problem was: not the inlet. The chamfer's inner end is at HW - 1.8.
    paint(base, lambda c, cy=cy, w=w, h=h:
          abs(c.x * 1000) <= HW - 1.7 and abs(c.y * 1000 - cy) < w / 2 + 0.6
          and abs(c.z * 1000 - PORT_Z) < h / 2 + 0.6, 1)

# ---------------------------------------------------------------- feet
bm = bmesh.new()
for sx in (-1, 1):
    for sy in (-1, 1):
        prism(bm, circle(sx * 118.0, sy * 88.0, 5.6, 20), 0.02, FOOT_H + 0.05, 0)
feet = finish("feet", bm, [mat_dark])

# ---------------------------------------------------------------- lid
bm = bmesh.new()
loft(bm, [(LID_IN, SEAM), (10.30, 0.20), (10.75, 0.00), (13.85, 0.00), (14.35, 0.10),
          (14.80, 0.34), (15.16, 0.66), (15.42, 1.05), (BODY_H, 1.42)], 0)
annulus(bm, plan(HW - SEAM, HD - SEAM, CORNER_R - SEAM),
        panel_plan(), BASE_H, LID_IN + 0.05, 0)
tri_caps(bm)
lid = finish("lid", bm, [mat_alu, mat_logo, mat_dark])

FONT = bpy.data.fonts.load("/System/Library/Fonts/SFNS.ttf")

def mark_loops(half_w):
    """The mark's own outlines, out of Apple's artwork: U+F8FF in the system font. Two versions
    of this were built by hand out of discs and both read as a snowman -- blob() unions circles,
    so the leaf came out a blunt oval where a leaf is a lens, and the whole mark came out 1.87
    times as tall as it is wide where the published one is 1.23 (814 x 1000). The glyph is
    exact, and the system font is where Apple keeps it.
    Orientation, settled by the machine rather than by argument: the mark reads upright for
    whoever sees the back of the OPEN screen. That is who a lit mark was ever for -- the audience,
    not the user, who is looking at the display. Up for that reader is the display's top, and the
    display's top is the lid's -y edge (shut, it comes down to the front lip). So the glyph is
    turned end for end: both axes negated, which is a rotation and keeps the winding. The first
    version left the glyph on its own axes -- leaf at +y, towards the hinge -- and the render was
    upside down from behind the open lid. A y-only flip, which is what the hand-built ones did,
    mirrors rather than turns and put the leaf on the wrong side of the bite."""
    cu = bpy.data.curves.new("mark", 'FONT')
    cu.font, cu.body, cu.size = FONT, "", 1.0
    cu.resolution_u, cu.align_x, cu.align_y = 5, 'CENTER', 'CENTER'
    ob = bpy.data.objects.new("mark", cu); sc.collection.objects.link(ob)
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)   # the outline only closes welded
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    s = half_w / ((max(xs) - min(xs)) / 2)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    nxt = {l.vert: l.link_loop_next.vert for f in bm.faces for l in f.loops
           if len(l.edge.link_faces) == 1}
    # Two cycles, not one: the leaf is its own contour, 170 verts of body and 60 of leaf. A walk
    # from one start would take the body and leave the leaf behind without saying so.
    loops, seen = [], set()
    while len(seen) < len(nxt):
        v0 = next(v for v in nxt if v not in seen)
        v, loop = v0, []
        while True:
            seen.add(v); loop.append((-(v.co.x - cx) * s, -(v.co.y - cy) * s))
            v = nxt[v]
            if v is v0:
                break
        loops.append(loop)
    if sum(map(len, loops)) != len(nxt):
        raise RuntimeError(f"mark: walked {sum(map(len, loops))} of {len(nxt)} boundary verts")
    bm.free()
    return loops

def lid_cut(bm):
    # The recess is cut into the lid's INNER face, one PANEL_DEEP deep, so the glass
    # (LID_IN+0.06 .. LID_IN+PANEL_DEEP-0.01) shows through the bezel ring's opening and the
    # lid keeps its back wall. Cutting the other way -- from the floor up to BODY_H -- takes
    # that wall out instead: the display area becomes a hole through the lid, so the front
    # shows the inner skin (a flat silver "screen") and the back shows the dark recess floor
    # through the hole, ringed by bare metal.
    # The cut starts below the bezel ring's own bottom face: stopping at the inner skin leaves
    # the loft's bottom cap 50 um inside the cutter, and the solver keeps that cap -- the
    # glass stays hidden behind a sheet of aluminium and nothing reports it.
    prism(bm, panel_plan(),
          BASE_H - 0.20, LID_IN + PANEL_DEEP)                      # display recess
    return 0
cut(lid, lid_cut, "lid_cut")
probe_ray("after lid_cut")
# and the display recess's floor is what shows through the notch, which is black
paint(lid, lambda c: abs(c.z * 1000 - (LID_IN + PANEL_DEEP)) < 0.06, 2)

# The marking is an insert laid on the lid's back, not a pocket cut into it. The pocket
# version removed nothing, and said nothing: the same cutter carried the display recess, so
# the vertex count still grew and a ray straight down the apple's centre met bare aluminium
# at BODY_H. Painting its floor was no better -- p.center is a centroid, so the window
# caught the 0.26 mm band of the lid's own edge instead and polished a rim onto it. An
# insert is what the real lid carries, and it needs no boolean to get one.
MARK = mark_loops(LOGO_W)
bm = bmesh.new()
for loop in MARK:
    prism(bm, loop, BODY_H - 0.05, BODY_H + LOGO_RISE, 0)
tri_caps(bm)
logo = finish("logo", bm, [mat_logo])

# ---------------------------------------------------------------- screen, camera
bm = bmesh.new()
prism(bm, panel_plan(),
      LID_IN + 0.06, LID_IN + PANEL_DEEP - 0.01, 0)
glass = finish("glass", bm, [mat_glass])
# The notch is at the display's TOP, and that is the lid's -y edge: shutting the lid brings the
# display's top down to the front lip and leaves the hinge at the chin, which is the bezel the
# 2015 machines printed "MacBook Pro" on. Cut at +y it lands at the bottom of the OPEN screen,
# 4 mm off the deck -- which is where it was, and no render said so: the notch's floor is 0.018
# grey against the switched-off panel's 0.012, and the camera sits inside it on the same wall.
notch_top = PANEL_TOP - 1.0
notch_bottom = PANEL_TOP + BEZEL + NOTCH_D
cut(glass, lambda bm: prism(bm, notch_pts(notch_top, notch_bottom - notch_top),
                            LID_IN - 0.1, BODY_H, 0) and 0, "glass_cut")

bm = bmesh.new()
cyy = PANEL_TOP + BEZEL / 2       # centred in the top bezel, inside the widened notch
prism(bm, circle(0.0, cyy, CAM_R, 20), LID_IN + PANEL_DEEP - 0.30, LID_IN + PANEL_DEEP - 0.12, 0)
prism(bm, circle(0.0, cyy, CAM_R * 0.5, 16), LID_IN + PANEL_DEEP - 0.12,
      LID_IN + PANEL_DEEP - 0.06, 1)
# Matte backing just behind the camera, wider than the cutout; the glass hides its edges.
rect(bm, 0.0, (notch_top + notch_bottom) / 2, NOTCH_W + 4.0,
     notch_bottom - notch_top + 2.0, LID_IN + PANEL_DEEP - 0.11,
     LID_IN + PANEL_DEEP - 0.09, 2)
camera = finish("camera", bm, [mat_dark, mat_glass, mat_notch])

# ---------------------------------------------------------------- the screen
# The real macOS hello page, as one emissive face on the glass. The wordmark is not a font:
# Apple's own two-stroke drawing ("Macintosh 3D", in the Hello screensaver bundle) is
# rasterised by ../hello_screen.py, with the blurred wallpaper behind it. Snell Roundhand
# stood in here first, and it is a different shape -- high-contrast calligraphy where the real
# mark is monoline with looped ascenders.
#
# The face is the active area, inset BEZEL from every glass edge, with the same U-shaped
# notch bite as the glass cut, so the image stops at the black border and the camera still
# shows through. Its aspect matches hello-screen.png's, so the UVs are the full 0..1: no crop
# and no stretch. The face, not extruded glyphs, is also what a display is: a lit rectangle.
# Switching it off stays the same one object scaled to zero, in the animation below.
bm = bmesh.new()
uv = bm.loops.layers.uv.new("UVMap")
z = LID_IN + 0.05
x0, x1 = -SCREEN_W / 2, SCREEN_W / 2
y0, y1 = PANEL_TOP + BEZEL, PANEL_TOP + BEZEL + SCREEN_H   # y0 is the display's top
pts = screen_plan() + notch_pts(y0, NOTCH_D)
f = bm.faces.new([bm.verts.new((x, y, z)) for x, y in pts])
f.normal_update()
for l in f.loops:
    x, y = l.vert.co.x, l.vert.co.y
    l[uv].uv = ((x - x0) / SCREEN_W, (y1 - y) / SCREEN_H)
if f.normal.z > 0:
    # The panel's face is -z in this frame; a viewer that culls backfaces shows a dark screen.
    bmesh.ops.reverse_faces(bm, faces=[f])
screen = finish("screen", bm, [mat_scr])

# ---------------------------------------------------------------- keys: 78, the real layout
# Units per key, back row first: runs of identical keys, gaps, and the one stacked column
# (the arrows are left/up-down/right across three units, up over down at half height each).
# The fn row is the real one -- esc, four groups of four function keys with gaps, and the
# function keys really are narrower than the letter keys -- Touch ID at the end.
ROWS = [
    [("k", 1.0), ("g", 0.5), ("r", 0.88, 4), ("g", 0.5), ("r", 0.88, 4), ("g", 0.5),
     ("r", 0.88, 4), ("g", 0.5), ("k", 1.5)],
    [("r", 1.0, 13), ("k", 2.0)],
    [("k", 1.5), ("r", 1.0, 12), ("k", 1.5)],
    [("k", 1.75), ("r", 1.0, 11), ("k", 2.25)],
    [("k", 2.25), ("r", 1.0, 10), ("k", 2.75)],
    [("k", 1.0), ("k", 1.0), ("k", 1.25), ("k", 1.5), ("k", 5.0), ("k", 1.25), ("k", 1.0),
     ("a", 3.0)],
]
# US ANSI, in build order -- the shifted symbol over the digit where the cap carries two, the
# modifier glyphs where it carries glyphs, nothing on the space bar or Touch ID.
LEGENDS = ["esc", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", None,
           "~\n`", "!\n1", "@\n2", "#\n3", "$\n4", "%\n5", "^\n6", "&\n7", "*\n8", "(\n9", ")\n0",
           "_\n-", "+\n=", "⌫",
           "⇥", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "{\n[", "}\n]", "|\n\\",
           "⇪", "A", "S", "D", "F", "G", "H", "J", "K", "L", ":\n;", "\"\n'", "⏎",
           "⇧", "Z", "X", "C", "V", "B", "N", "M", "<\n,", ">\n.", "?\n/", "⇧",
           "fn", "⌃", "⌥", "⌘", None, "⌘", "⌥", "←", "↓", "→", "↑"]
bm = bmesh.new()
kz0, kz1 = BASE_H - WELL_DEPTH + 0.12, BASE_H + KEY_CROWN
nkeys = 0
TOPS = []                        # every cap's top face, in build order, for the legend pass
def key(cx, cy, w, d):
    global nkeys
    slot(bm, cx, cy, w - KEY_GAP, d - KEY_GAP, kz0, kz1, 1.5, 0.35)
    TOPS.append((cx, cy, (w - KEY_GAP) / 2 - 0.35, (d - KEY_GAP) / 2 - 0.35))
    nkeys += 1
for r, spec in enumerate(ROWS):
    unit = (2 * WELL_HW) / sum(e[1] * (e[2] if e[0] == "r" else 1) for e in spec)
    x, yc = -WELL_HW, WELL_Y1 - (r + 0.5) * ROW_PITCH
    for e in spec:
        if e[0] == "g":
            x += e[1] * unit; continue
        w = e[1] * unit          # one key, not the whole run
        if e[0] == "r":
            for k in range(e[2]):
                key(x + w * (k + 0.5), yc, w, ROW_PITCH)
        elif e[0] == "a":        # the arrow block: ← ↓ → along the bottom half of three units,
            uw = w / 3           # and a lone ↑ over the middle column
            for k in range(3):
                key(x + uw * (k + 0.5), yc - ROW_PITCH / 4, uw, ROW_PITCH / 2)
            key(x + uw * 1.5, yc + ROW_PITCH / 4, uw, ROW_PITCH / 2)
        else:
            key(x + w / 2, yc, w, ROW_PITCH)
        x += w * (e[2] if e[0] == "r" else 1)
keys = finish("keys", bm, [mat_key])
if len(TOPS) != len(LEGENDS):
    # A legend off by one mislabels every cap after it and nothing else would say so.
    raise RuntimeError(f"legends: {len(TOPS)} caps, {len(LEGENDS)} legends")

# ---------------------------------------------------------------- legends, as geometry
bm = bmesh.new()                     # finish() freed the keys' bmesh when it made the mesh
# Glyph outlines rather than a texture atlas: a key costs ~20 triangles, there is no UV channel
# to add, no image to pack and no material graph that has to survive glTF, and the legends
# cannot drift out of register with the caps they label.
# Flat, not extruded. An extruded glyph's walls pinch wherever the outline touches itself -- the
# apex of "A", the arrowhead of the return key -- and the weld that closes the shell then leaves
# four faces on an edge: 156 non-manifold edges across the 76 legends, and 710 edges left open
# where a face failed to build. The cap alone is clean for every glyph tested, and a legend is
# printed flat on the cap anyway.
for (cx, cy, hw, hd), text in zip(TOPS, LEGENDS):
    if not text:
        continue
    lines = text.split("\n")
    size = 3.3 if len(lines) > 1 else 3.6 if len(text) > 2 else 4.4
    cu = bpy.data.curves.new("legend", 'FONT')
    cu.font = FONT                       # SFNS: Bfont has no ⌘ ⌥ ⇧ ⌃ and draws boxes for them
    cu.body, cu.size = text, size        # no extrude: the legend is a decal, and see below
    cu.resolution_u, cu.align_x, cu.align_y = 5, 'CENTER', 'CENTER'
    lo = bpy.data.objects.new("legend", cu); sc.collection.objects.link(lo)
    bpy.context.view_layer.update()
    ev = lo.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    if me.vertices:
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        s = min(1.0, (2 * hw * 0.88) / max(max(xs) - min(xs), 1e-6),
                (2 * hd * 0.78) / max(max(ys) - min(ys), 1e-6))   # a two-line legend is tall
        me.transform(Matrix.Translation((cx, cy, kz1 + 0.02)) @ Matrix.Scale(s, 4))
        bm.from_mesh(me)                 # the glyph as Blender built it, faces and all
    ev.to_mesh_clear()
    bpy.data.objects.remove(lo, do_unlink=True)
    bpy.data.curves.remove(cu)
if sum(f.normal.z for f in bm.faces) < 0:
    # A decal is a sheet: calc_volume() is 0, so finish() cannot tell an upside-down one, and
    # Cycles shades both sides -- the render would hide the mistake while a viewer that culls
    # backfaces, which is what this ships into, would show a blank keycap.
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
legend = finish("legend", bm, [mat_leg])

# ---------------------------------------------------------------- trackpad, hinge
bm = bmesh.new()
prism(bm, plan(TP_W / 2 + TP_SEAM, TP_D / 2 + TP_SEAM, TP_R, 6, TP_Y0 + TP_D / 2),
      BASE_H - TP_RECESS, BASE_H, 1)
prism(bm, plan(TP_W / 2, TP_D / 2, TP_R, 6, TP_Y0 + TP_D / 2), BASE_H, BASE_H + TP_PROUD, 0)
trackpad = finish("trackpad", bm, [mat_tp, mat_dark])

bm = bmesh.new()
prism(bm, plan(HINGE_HW, 3.0, 2.4, 6, HINGE_Y0 + 3.0), HINGE_Z0, HINGE_Z1, 0)
hinge = finish("hinge", bm, [mat_dark])

# ---------------------------------------------------------------- open the lid
LID_GROUP = [lid, glass, camera, logo, screen]
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

closed = dims_mm([base, lid, keys, trackpad])
ok = all(abs(a - b) < 0.05 for a, b in zip(closed, (BODY_W, BODY_D, BODY_H)))
print(f"REPORT closed_envelope_mm=({closed[0]:.2f}, {closed[1]:.2f}, {closed[2]:.2f})  "
      f"want (312.60, 221.20, 15.50)  {'OK' if ok else 'OFF'}")

M = (Matrix.Translation(Vector((0.0, PIVOT_Y * MM, PIVOT_Z * MM)))
     @ Matrix.Rotation(math.radians(LID_OPEN), 4, 'X')
     @ Matrix.Translation(Vector((0.0, -PIVOT_Y * MM, -PIVOT_Z * MM))))
for o in LID_GROUP:
    o.data.transform(M)

# Lift the body onto its feet. Everything above was built with the body's underside at z=0,
# which is the frame the spec sheet's height lives in; the asset has to rest on z=0 or it
# sinks through the studio floor. The envelope above is a difference, so the shift leaves it
# alone.
LIFT = Matrix.Translation(Vector((0.0, 0.0, FOOT_H * MM)))
# Every mesh in the scene rather than a hand-kept list of part names. A part left off that
# list sits 0.45 mm low and nothing says so -- which is what the legends did through two
# builds, 0.43 mm under the caps they label, in every render and every clearance number.
for o in sc.objects:
    if o.type == 'MESH' and o is not feet:      # the feet are built in the resting frame
        o.data.transform(LIFT)

# The display's own bottom edge is the closest thing to the deck, and this is its gap. It is
# the check whose absence let a lid 7.65 mm inside the base ship: every other test here -- the
# envelope, the topology, the ray -- passes just as happily on a machine that is inside itself.
clear = min((v.co.z / MM for o in LID_GROUP for v in o.data.vertices
             if abs(v.co.x / MM) <= HW - 0.15 and abs(v.co.y / MM) <= HD - 0.15), default=1e9)
print(f"REPORT lid_clearance_mm={clear - (BASE_H + FOOT_H):.3f}  (0.000 = the hinge line, "
      f"which is where the display meets the deck)")
if clear < BASE_H + FOOT_H - 0.05:
    raise RuntimeError(f"the open display is {BASE_H + FOOT_H - clear:.2f} mm inside the base")

print(f"REPORT perforations={holes} keys={nkeys} legends={sum(1 for t in LEGENDS if t)}")
# The mark's proportions are the one thing about it that can be checked against a published
# number: the artwork is 814 x 1000, so 1.2299. The hand-built version came out 1.87, which is
# what "the Apple logo is wrong" looked like in numbers.
mxs = [p[0] for lo in MARK for p in lo]
mys = [p[1] for lo in MARK for p in lo]
mw, mh = max(mxs) - min(mxs), max(mys) - min(mys)
print(f"REPORT mark_mm={mw:.2f}x{mh:.2f} aspect={mh / mw:.4f} loops={len(MARK)} (published 1.2299)")

# ---------------------------------------------------------------- open, hello, shut, repeat
# The lid group's meshes were turned in place above, so there is nothing left to rotate: the
# hinge becomes an empty at the lifted pivot and the parts hang off it, one rotation channel
# instead of five. Closing is +LID_OPEN about that same axis, and it lands where a shut MacBook
# lands -- the lid's inner face stopping on the keycaps.
#
# The screen is switched by scaling it to nothing, which glTF can animate and an emission
# strength cannot: glTF animation drives node transforms only, never materials. That is why the
# origin below moves to the screen's own centre first -- scale is about the origin, and left at
# the world origin the word would slide towards the hinge as it shrank.
# 10 s awake and 10 s shut, both exact: the awake hold is the 240 frames from the lid reaching
# open to the lid starting to shut, and the shut hold is what is left of the loop after the shut
# animation, where the next cycle's opening is 21 frames of it.
FPS, OPEN_F, CLOSE_F, LOOP_F = 24, 21, 261, 500
SHUT_F = CLOSE_F + 20
pivot = bpy.data.objects.new("lid_pivot", None)
sc.collection.objects.link(pivot)
pivot.location = Vector((0.0, PIVOT_Y * MM, (PIVOT_Z + FOOT_H) * MM))
for o in LID_GROUP:
    o.parent = pivot                                     # inverse = -pivot: world stays put
    o.matrix_parent_inverse = Matrix.Translation(-pivot.location)
# The centre comes from the vertices, not from `bound_box`: those eight corners are the box
# the mesh had when it was last evaluated, and a mesh built this frame has not been. Read off
# the corners the origin landed 128 mm off the glyph -- which puts the shrunken screen 97 mm
# below the floor while the lid is shut, and the export gate found it there.
vs = [v.co for v in screen.data.vertices]
ctr = Vector([(min(v[i] for v in vs) + max(v[i] for v in vs)) / 2 for i in range(3)])
screen.data.transform(Matrix.Translation(-ctr))
screen.location = ctr
sc.frame_start, sc.frame_end, sc.render.fps = 1, LOOP_F, FPS

for f, v in ((1, math.radians(-LID_OPEN)), (OPEN_F, 0.0), (CLOSE_F, 0.0),
             (SHUT_F, math.radians(-LID_OPEN)), (LOOP_F, math.radians(-LID_OPEN))):
    pivot.rotation_euler[0] = v
    pivot.keyframe_insert("rotation_euler", index=0, frame=f)
for f, v in ((1, 0.0), (OPEN_F - 1, 0.0), (OPEN_F, 1.0), (CLOSE_F, 1.0), (SHUT_F, 0.0),
             (LOOP_F, 0.0)):
    screen.scale = (v, v, v)
    screen.keyframe_insert("scale", frame=f)
print(f"REPORT loop={LOOP_F / FPS:.2f}s at {FPS} fps  hello "
      f"{(CLOSE_F - OPEN_F) / FPS:.2f}s  lid_shut {(LOOP_F + OPEN_F - SHUT_F) / FPS:.2f}s")

# ---------------------------------------------------------------- shading
def auto_sharp(mesh, angle_deg):
    bm2 = bmesh.new(); bm2.from_mesh(mesh); bm2.edges.ensure_lookup_table()
    sharp = set()
    for e in bm2.edges:
        lf = e.link_faces
        if len(lf) != 2 or math.degrees(lf[0].normal.angle(lf[1].normal)) > angle_deg:
            sharp.add(e.index)
    bm2.free()
    for p in mesh.polygons:
        p.use_smooth = True
    for e in mesh.edges:
        e.use_edge_sharp = e.index in sharp
    return len(sharp)

sharp_edges = sum(auto_sharp(o.data, 33) for o in sc.objects if o.type == 'MESH')

# ---------------------------------------------------------------- studio
w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB"); mapr = nt.nodes.new("ShaderNodeMapRange")
# Window measured on this subject rather than inherited: a laptop is two big VERTICAL panels
# and they mirror the horizon, which the low-poly build's -0.05 .. 0.45 window left murky.
mapr.inputs["From Min"].default_value = -0.45
mapr.inputs["From Max"].default_value = 0.35
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.025, 1)
# Three stops, not two: the horizon lands at Fac 0.5625 so it keeps the 0.40 it had, while
# the top came down 0.70 -> 0.58. 0.70 x 1.45 = 1.015 clipped the zenith, and every
# up-facing surface in the machine (the deck, the screen, the trackpad) mirrors it.
# A dimmer top then wants a stronger world to stay lit: at 1.45 the brightest 0.1% of the
# hero frame reached only 0.83 and the shot read murky, and the macro -- 90% matte keycap,
# which is the darkest frame in the set -- needed the whole way to 1.66 to clear 0.85.
# 0.58 x 1.66 = 0.96: the zenith is the ceiling here, and it still does not clip.
mid = ramp.color_ramp.elements.new(0.55)
mid.color = (0.40, 0.405, 0.43, 1)
ramp.color_ramp.elements[-1].position = 1.0
ramp.color_ramp.elements[-1].color = (0.58, 0.59, 0.62, 1)
nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.66

for name, rot, e in (("Key", (math.radians(48), 0, math.radians(35)), 7.6),
                     ("Fill", (math.radians(55), 0, math.radians(25)), 2.4),
                     ("Rim", (math.radians(118), 0, math.radians(-135)), 1.8)):
    # 12 degrees, not the 1.15 a default sun gives. Every smooth surface here mirrors its light
    # source, and a mirror of a point is a point: the trackpad at roughness 0.07 reflected
    # nothing but the flat sky and read as a grey plastic tile. A source with real area is what
    # puts a highlight on it -- and on the lid, the caps and the port mouths.
    l = bpy.data.lights.new(name, 'SUN'); l.energy = e; l.angle = math.radians(12)
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
    o.rotation_euler = rot

bpy.ops.mesh.primitive_plane_add(size=6.0)
floor = bpy.context.active_object; floor.name = "Floor"
fm = principled("Floor", (0.035, 0.035, 0.04), 0.0, 0.62)
fm.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.25
floor.data.materials.append(fm)

cd = bpy.data.cameras.new("Cam"); cd.clip_start = 0.01; cd.clip_end = 100
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
TARGET = Vector((0.0, 0.02, 0.08))
def aim(loc, lens, target=TARGET):
    cd.lens = lens
    cam.location = loc
    cam.rotation_euler = (target - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

sc.render.resolution_x = sc.render.resolution_y = 1200
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = "Standard"
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 96
sc.cycles.use_denoising = True

def face_view(ob, off, lens=85, fill=0.40):
    """Where a small part actually is, seen from `off` and framed so its longer side is `fill`
    of the frame. Two rounds of the mark's numbers were typed in off a render and both went
    stale the moment the mark changed -- a view of the mark that misses the mark is a check
    that cannot fail. `off` is a unit direction, and it is a constant only because the lid's
    open angle is one: 10 degrees off the mark's normal so the insert's own relief catches
    light, and square on the display for the hello.

    The mark's frame is the one view the export gate is not asked about. A highlight in it is not
    merely missing but impossible: the mark's normal tilts 14 degrees down, so every camera that
    can see the lid's back also makes the insert mirror the floor, and the mirror of a sun sits
    below the horizon, where the floor shadows it. Reaching the world's bright band means getting
    the lid's top edge -- 110 mm away -- into frame, which shrinks the mark to 130 px, and the
    point of this view is to judge the mark. The other views carry the exposure check."""
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    corner = [ob.matrix_world @ Vector(c) for c in ev.bound_box]
    ctr = sum(corner, Vector()) / 8
    # Framed by whichever in-plane extent is the larger, not by height: a word three times
    # wider than it is tall, framed by height, is cropped at both ends -- which is what the
    # first hello render was. The two axes are `off` crossed with the world's up and the
    # result crossed back, which is the camera's own right and up to within the roll.
    right = off.cross(Vector((0.0, 0.0, 1.0)))
    right = right.normalized() if right.length > 1e-6 else Vector((1.0, 0.0, 0.0))
    up = right.cross(off).normalized()
    half = max(abs((c - ctr).dot(v)) for c in corner for v in (right, up))
    return ctr + off * (2 * half / fill * lens / cd.sensor_width), lens, ctr

# The stills are the open hold, and the frame has to move before the views are measured: a
# bound_box read at frame 1 is the shut machine's, and the two close-ups below are aimed by one.
sc.frame_set(OPEN_F + 10)
VIEWS = {                    # (location, lens, target) -- the macro is the density evidence
    "hero":  ((0.40, -0.62, 0.36), 52, TARGET),
    "deck":  ((0.05, -0.34, 0.68), 52, TARGET),
    "left":  ((-0.62, -0.30, 0.16), 52, TARGET),
    "right": ((0.64, -0.26, 0.15), 52, TARGET),
    "back":  ((0.42, 0.58, 0.38), 52, TARGET),
    # the mark itself, close enough to judge -- at the back view's 52 mm it was 35 px tall.
    "logo":  face_view(logo, Vector((0.0683, 0.99465, -0.0771))),
    # and the hello square on the display, which is the display's own normal once the lid is
    # open: (0, 0, -1) turned by the lid's -104 degrees.
    "hello": face_view(screen, Vector((0.0, -0.9703, 0.2419)), fill=0.50),
    # the density evidence: speaker perforations, keycap chamfers, a port lip and bore
    "macro": ((0.28, -0.10, 0.075), 85, Vector((0.132, 0.02, 0.010))),
    # both port rows head on, because a port is a shape and a row's rhythm is legible or not
    "port-left":  ((-0.85, -0.02, 0.07), 85, Vector((-0.156, 0.050, 0.005))),
    "port-right": ((0.85, -0.02, 0.07), 85, Vector((0.156, 0.058, 0.005))),
}
os.makedirs(OUT, exist_ok=True)
for name, (loc, lens, tgt) in VIEWS.items():
    aim(loc, lens, tgt)
    sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"REPORT rendered={name}")

# The other half of the loop: the shut machine, which is also the one view of the mark that a
# person reads from the front. Its own angle -- the hero's is aimed at an open display and looks
# over a shut one.
sc.frame_set(1)
aim((0.30, -0.50, 0.40), 52, Vector((0.0, 0.01, 0.008)))
sc.render.filepath = os.path.join(OUT, "preview-closed.png")
bpy.ops.render.render(write_still=True)
print("REPORT rendered=closed")
sc.frame_set(OPEN_F + 10)                     # the pose the rest pose and the numbers are read in

# ---------------------------------------------------------------- report + export
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
total = ngons = nonman = parts = 0
lo, hi = [1e9] * 3, [-1e9] * 3
for o in sc.objects:
    if o.type != 'MESH' or o.name == "Floor":
        continue
    parts += 1
    ev = o.evaluated_get(dg); m2 = ev.to_mesh(); m2.calc_loop_triangles()
    total += len(m2.loop_triangles)
    ngons += sum(1 for p in m2.polygons if len(p.vertices) > 4)
    bm3 = bmesh.new(); bm3.from_mesh(m2)
    nonman += sum(1 for e in bm3.edges if len(e.link_faces) > 2)
    bm3.free()
    for c in ev.bound_box:
        w2 = o.matrix_world @ Vector(c)
        for i in range(3):
            lo[i] = min(lo[i], w2[i]); hi[i] = max(hi[i], w2[i])
    ev.to_mesh_clear()
dims = [(hi[i] - lo[i]) / MM for i in range(3)]
print(f"REPORT tris={total} parts={parts} sharp_edges={sharp_edges} "
      f"names={[o.name for o in sc.objects if o.type == 'MESH' and o.name != 'Floor']}")
print(f"REPORT ngons={ngons} nonmanifold_edges={nonman}")
print(f"REPORT shipped_dims_mm=({dims[0]:.2f}, {dims[1]:.2f}, {dims[2]:.2f})  z_min_mm={lo[2]/MM:.3f}")

probe_ray("before save", LIFT @ M)

for o in sc.objects:
    # The pivot empty too: it is the parent of everything on the lid, and a selection that drops
    # it drops the lid's place in the world with it. SCENE mode is what puts the lid's rotation
    # and the screen's scale in ONE animation -- ACTIONS mode would ship two, and a viewer that
    # plays the first clip would open the lid and leave the screen dark.
    o.select_set(o.name == "lid_pivot" or (o.type == 'MESH' and o.name != "Floor"))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "macbookpro.glb"),
                          export_format='GLB', export_apply=True, use_selection=True,
                          export_animation_mode='SCENE')
print("REPORT glb_bytes=", os.path.getsize(os.path.join(OUT, "macbookpro.glb")))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "macbookpro.blend"))
