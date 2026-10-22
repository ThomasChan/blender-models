# Mac Pro (2023, tower) -- hand-built. Apple publishes no USDZ for this machine, so unlike
# the Mac mini / iMac / Mac Studio in this folder there is nothing to convert: every number
# below is either Apple's spec sheet or measured off the press and iFixit photographs in
# /tmp/macpro-ref (see ## macpro in README.md).
#
# The 2023 machine reuses the 2019 enclosure, so the 2019 press images are the reference.
# Envelope 218 W x 450 D x 529 H (handle top to foot bottom); housing 218 x 450 x 429.5,
# standing on four 44.2 mm feet.
#
#   Blender -b --factory-startup --python-exit-code 1 --python build_macpro.py -- .
#   Blender ... --python build_macpro.py -- . norender     # geometry only, for iteration
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else ".")
NORENDER = "norender" in argv
MM = 0.001

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- dimensions, plain mm
HW, HD = 109.0, 225.0                  # half width, half depth
Z_BOT, Z_TOP = 44.2, 473.7             # housing; the feet make up 0..44.2
R_PLAN = 30.0                          # measured from the top-view silhouette: r = 61 px
CORNER_SEG = 20
TOP_FIL, BOT_FIL = 6.0, 4.0
WALL_F, WALL_R = 8.0, 12.0             # front / rear plate (the rear carries the deep ports)
WALL_X, WALL_T, WALL_B = 8.0, 8.0, 6.0
CAV_CY = (WALL_F - WALL_R) / 2          # +2? front inner -217, rear inner +213 -> -2

# front/rear lattice: 21 rows, staggered, 158 dishes per face
ROW_Z0, ROW_DZ = 60.75, 19.82
PITCH_X = 22.9
ROW_N = 21
DISH_RIM, DISH_DEPTH = 11.3, 4.5        # 0.15 mm land between neighbouring rims
DISH_R = (DISH_RIM ** 2 + DISH_DEPTH ** 2) / (2 * DISH_DEPTH)   # 16.44
DISH_OFF = DISH_R - DISH_DEPTH                                   # 11.94
HOLE_R, HOLE_ORBIT = 4.6, 6.3           # three trefoil holes per dish, ~1.7 mm Y web

# rear I/O panel, measured: x -55.2..52.9, z 57..355
PANEL_CX, PANEL_CZ = 0.0, 206.0
PANEL_W, PANEL_H = 108.0, 298.0
PANEL_R = 8.0
FRAME_W, FRAME_H, FRAME_R, FRAME_D = 113.0, 303.0, 10.5, 1.2
PANEL_DEEP = 5.2
POCKET_Y = HD - PANEL_DEEP               # 219.8
PORT_Y = POCKET_Y - 5.5                  # 214.3; 1.3 mm of wall left in front of the void

TB4_Z, TB4_PITCH = 327.7, 16.3
TB4_X = [1.45 + (i - 2.5) * TB4_PITCH for i in range(6)]
ROW2_Z = 308.3
# Measured off the rear press shot. A rear view is seen from +Y, so its screen-left is +X:
# audio sits at +41, USB-A at -17/-37. An earlier pass had this row mirrored.
AUDIO_X = 41.0
HDMI_X = [24.6, 3.4]
USBA_X = [-17.1, -36.7]
SLOT_Z0, SLOT_DZ, SLOT_N, SLOT_H = 293.4, 20.08, 10, 5.6
C13_XZ = (-1.2, 80.5)
RJ45_XZ = [(-29.3, 86.3), (-29.3, 71.1)]
REAR_LED = (36.9, 77.7)

# top face
TOP_Y_PORTS, TOP_Y_BTN, TOP_Y_LED = 125.0, 125.3, 125.7
TOP_PORT_X = [-49.0, -33.9]
LATCH_R = 50.0
D_RECESS_R, D_RECESS_DEEP = 34.0, 1.8
HANDLE_Y, HANDLE_LEN, HANDLE_W = 195.5, 193.0, 26.0
HANDLE_LEG_X, HANDLE_BAR_Z, HANDLE_R = 82.5, 524.0, 5.0
FOOT_XY = [(79.8, 185.0), (-79.8, 185.0), (79.8, -185.0), (-79.8, -185.0)]
LOGO_W, LOGO_Z = 48.6, 262.0            # half-width; 97.2 x 119.5 mm mark

# ---------------------------------------------------------------- helpers
def principled(name, color, metallic, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*color, 1.0)
    return m

mat_alu = principled("Aluminium", (0.62, 0.62, 0.64), 0.95, 0.32)
mat_dark = principled("Dark", (0.018, 0.018, 0.022), 0.15, 0.50)
mat_steel = principled("Steel", (0.80, 0.80, 0.82), 1.0, 0.12)
mat_logo = principled("LogoInlay", (0.010, 0.010, 0.012), 0.2, 0.30)
mat_tongue = principled("ConnectorMetal", (0.35, 0.35, 0.36), 0.9, 0.35)
# The press photos show dark USB-C / USB-A tongues, not the blue of a generic USB 3 port.
mat_port = principled("PortInterior", (0.055, 0.055, 0.06), 0.25, 0.50)
mat_socket = principled("SocketPlastic", (0.55, 0.55, 0.56), 0.0, 0.45)
mat_led = principled("LED", (1.0, 1.0, 1.0), 0.0, 0.3)
mat_led.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 1, 1, 1)
mat_led.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.0

def plan(hw, hd, r, seg=CORNER_SEG, cy=0.0):
    """CCW plan boundary: four corner arcs, same corner first, same direction round."""
    pts = []
    for cx, cyy, a0 in ((hw - r, -hd + r, -90), (hw - r, hd - r, 0),
                        (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            pts.append((cx + r * math.cos(a), cy + cyy + r * math.sin(a)))
    return pts

def stack(bm, rings, mi=0, cap_bottom=True, cap_top=True):
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
    return stack(bm, [ring(bm, pts, z0), ring(bm, pts, z1)], mi)

def rect(bm, cx, cy, w, d, z0, z1, mi=0):
    return prism(bm, [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2),
                      (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)], z0, z1, mi)

def circle(cx, cy, r, n):
    return [(r * math.cos(2 * math.pi * i / n) + cx,
             r * math.sin(2 * math.pi * i / n) + cy) for i in range(n)]

def annulus(bm, outer, inner, z0, z1, mi=0):
    return stack(bm, [ring(bm, outer, z0), ring(bm, outer, z1),
                      ring(bm, inner, z1), ring(bm, inner, z0), ring(bm, outer, z0)],
                 mi, cap_bottom=False, cap_top=False)

def tri_caps(bm):
    # bmesh.ops.triangulate fans a concave cap from its first vertex, which bridges the
    # logo's bottom notch with a flat chord; tessellate_polygon respects the outline.
    from mathutils.geometry import tessellate_polygon
    for f in [f for f in bm.faces if len(f.verts) > 4]:
        vs = list(f.verts)
        tris = tessellate_polygon([[v.co.copy() for v in vs]])
        nrm, mi = f.normal.copy(), f.material_index
        bm.faces.remove(f)
        for a, b, c in tris:
            tri = bm.faces.new((vs[a], vs[b], vs[c]))
            tri.material_index = mi
            if tri.normal.dot(nrm) < 0:
                tri.normal_flip()

def box(bm, c, s, mi=0):
    """Axis-aligned box, outward wound by the primitive."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    for v in vs:
        v.co.x = v.co.x * s[0] + c[0]
        v.co.y = v.co.y * s[1] + c[1]
        v.co.z = v.co.z * s[2] + c[2]
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs

def cyl_z(bm, cx, cy, r, z0, z1, n=24, mi=0):
    return stack(bm, [ring(bm, circle(cx, cy, r, n), z0),
                      ring(bm, circle(cx, cy, r, n), z1)], mi)

def cyl_y(bm, cx, cz, r, y0, y1, n=16, mi=0):
    """Cylinder along +Y; xz loop, so it shares stack()'s winding with the panel prisms."""
    pts = circle(cx, cz, r, n)
    a = [bm.verts.new((x, y0, z)) for x, z in pts]
    b = [bm.verts.new((x, y1, z)) for x, z in pts]
    return stack(bm, [a, b], mi)

def xzprism(bm, cx, cz, w, h, r, y0, y1, mi=0):
    """Rounded rect in the rear wall's plane, extruded along Y."""
    pts = plan(w / 2, h / 2, min(r, min(w, h) / 2 - 1e-4), 20)
    return stack(bm, [[bm.verts.new((cx + px, y, cz + py)) for px, py in pts]
                      for y in (y0, y1)], mi)

def xzrect(bm, cx, cz, w, h, y0, y1, mi=0):
    """Plain rect in the rear wall's plane. Same winding plane as xzprism, so the two can
    share a cutter object: a box() here would be wound the other way round and the
    object's signed volume would flip the wrong islands."""
    pts = [(cx - w / 2, cz - h / 2), (cx + w / 2, cz - h / 2),
           (cx + w / 2, cz + h / 2), (cx - w / 2, cz + h / 2)]
    return stack(bm, [[bm.verts.new((x, y, z)) for x, z in pts] for y in (y0, y1)], mi)

def xzpoly(bm, pts, y0, y1, mi=0):
    return stack(bm, [[bm.verts.new((x, y, z)) for x, z in pts] for y in (y0, y1)], mi)

SHARP = math.radians(33)

def smooth_by_angle(bm, sharp=SHARP):
    """Smooth shading with hard creases where the surface actually turns. Flat shading made
    every dish bowl read as a faceted fan in the close renders."""
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > sharp:
            e.smooth = False

def finish(name, bm, mats):
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-3)
    bmesh.ops.scale(bm, vec=(MM, MM, MM), verts=list(bm.verts))
    vol = bm.calc_volume(signed=True)
    if vol < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    smooth_by_angle(bm)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    for m in mats:
        me.materials.append(m)
    print(f"REPORT part={name} volume_mm3={abs(vol) / MM ** 3:.1f} flipped={vol < 0}")
    return o

def cut(target, build, name, mats=(mat_alu, mat_dark)):
    bm = bmesh.new(); build(bm)
    o = finish(name, bm, list(mats))
    m = target.modifiers.new(name, 'BOOLEAN')
    m.operation, m.object, m.solver = 'DIFFERENCE', o, 'EXACT'
    m.use_self = True
    m.material_mode = 'INDEX'
    before = len(target.data.vertices)
    with bpy.context.temp_override(object=target, active_object=target,
                                   selected_objects=[target], selected_editable_objects=[target]):
        status = bpy.ops.object.modifier_apply(modifier=name)
    after = len(target.data.vertices)
    if status != {'FINISHED'} or after <= before:
        raise RuntimeError(f"boolean {name}: {status}, verts {before} -> {after}")
    bpy.data.objects.remove(o, do_unlink=True)
    return after

def sweep(bm, pts, radius, n=16, closed=False, mi=0):
    """Circular tube along a polyline, parallel-transported frame."""
    P = [Vector(p) for p in pts]
    T = []
    for i in range(len(P)):
        if closed:
            t = P[(i + 1) % len(P)] - P[i - 1]
        elif i == 0:
            t = P[1] - P[0]
        elif i == len(P) - 1:
            t = P[-1] - P[-2]
        else:
            t = P[i + 1] - P[i - 1]
        T.append(t.normalized())
    up = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = (up - T[0] * up.dot(T[0])).normalized()
    rings = []
    for i, p in enumerate(P):
        if i > 0:
            axis = T[i - 1].cross(T[i])
            if axis.length > 1e-9:
                nrm = (nrm * math.cos(T[i - 1].angle(T[i]))
                       + axis.normalized().cross(nrm) * math.sin(T[i - 1].angle(T[i]))
                       + axis.normalized() * axis.normalized().dot(nrm) * (1 - math.cos(T[i - 1].angle(T[i]))))
            nrm = (nrm - T[i] * nrm.dot(T[i])).normalized()
        b = T[i].cross(nrm)
        rings.append([bm.verts.new(p + radius * (math.cos(2 * math.pi * k / n) * nrm
                                                + math.sin(2 * math.pi * k / n) * b))
                      for k in range(n)])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mi
    if closed:
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((rings[-1][i], rings[-1][j], rings[0][j], rings[0][i])).material_index = mi
    else:
        bm.faces.new(rings[0][::-1]).material_index = mi
        bm.faces.new(rings[-1]).material_index = mi
    return rings

def arc_band(bm, r0, r1, a0, a1, z0, z1, n=24, mi=0, cx=0.0, cy=0.0):
    """Flat annular sector, outward wound."""
    ang = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
    o0 = [bm.verts.new((cx + r1 * math.cos(a), cy + r1 * math.sin(a), z0)) for a in ang]
    o1 = [bm.verts.new((cx + r1 * math.cos(a), cy + r1 * math.sin(a), z1)) for a in ang]
    i0 = [bm.verts.new((cx + r0 * math.cos(a), cy + r0 * math.sin(a), z0)) for a in ang]
    i1 = [bm.verts.new((cx + r0 * math.cos(a), cy + r0 * math.sin(a), z1)) for a in ang]
    for i in range(n):
        j = i + 1
        bm.faces.new((o0[i], o0[j], o1[j], o1[i])).material_index = mi      # outer wall
        bm.faces.new((i0[i], i1[i], i1[j], i0[j])).material_index = mi      # inner wall
        bm.faces.new((o1[i], o1[j], i1[j], i1[i])).material_index = mi      # top
        bm.faces.new((o0[i], i0[i], i0[j], o0[j])).material_index = mi      # bottom
    bm.faces.new((o0[0], o1[0], i1[0], i0[0])).material_index = mi
    bm.faces.new((o0[n], i0[n], i1[n], o1[n])).material_index = mi

# ---------------------------------------------------------------- honeycomb backing
def honeycomb_image():
    """A seamless pointy-top hex lattice, 0.78 mm bright walls on a near-black cell.
    The bright Y-junctions seen through each dish hole are this backing, not front metal."""
    W, H = 666, 384
    pitch_x, pitch_y = 222.0, 192.0
    apothem = pitch_x / 2.0
    xs = np.arange(W)[None, :].astype(np.float64)
    ys = np.arange(H)[:, None].astype(np.float64)
    jf = ys / pitch_y
    f = xs / pitch_x - jf / 2.0
    j0 = np.floor(jf).astype(int)
    i0 = np.floor(f).astype(int)
    best = np.full((H, W), 1e9)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            jj = j0 + dj
            ii = i0 + di
            cx = (ii + jj / 2.0) * pitch_x
            cy = jj * pitch_y
            px = xs - cx
            py = ys - cy
            d = np.maximum(np.maximum(np.abs(px),
                                      np.abs(px * 0.5 + py * math.sqrt(3) / 2)),
                           np.abs(px * 0.5 - py * math.sqrt(3) / 2)) - apothem
            best = np.minimum(best, d)
    val = np.zeros((H, W, 4), dtype=np.float32)
    wall = 18.0
    lum = np.where(np.abs(best) < wall,
                   0.55 + 0.25 * (1.0 - np.minimum(np.abs(best), wall) / wall),
                   0.012)
    val[:, :, 0] = lum * 0.98
    val[:, :, 1] = lum
    val[:, :, 2] = lum * 1.01
    val[:, :, 3] = 1.0
    img = bpy.data.images.new("honeycomb", W, H, alpha=False)
    img.pixels.foreach_set(val.ravel())
    path = os.path.join(OUT, "honeycomb.png")
    img.filepath_raw = path; img.file_format = 'PNG'; img.save(); img.pack()
    m = bpy.data.materials.new("Honeycomb"); m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    # The cavity is lit only through its own holes, so a lit-only backing renders black.
    # A little emission is what makes the mesh legible inside the dishes, as in the photos.
    nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.3
    b.inputs["Metallic"].default_value = 0.7
    b.inputs["Roughness"].default_value = 0.38
    print(f"REPORT texture={path} {W}x{H}")
    return m

mat_honey = honeycomb_image()

# ---------------------------------------------------------------- lattice cells
def face_cells():
    out = []
    for row in range(ROW_N):
        z = ROW_Z0 + row * ROW_DZ
        if row % 2 == 0:
            xs = [-80.15, -57.25, -34.35, -11.45, 11.45, 34.35, 57.25, 80.15]
        else:
            xs = [-68.7, -45.8, -22.9, 0.0, 22.9, 45.8, 68.7]
        out += [(x, z) for x in xs]
    return out

FRONT_CELLS = face_cells()
# The rear panel replaces the central columns; cells whose dish would land on the frame
# are omitted rather than cut, so no half-dish and no hole is left in the pocket floor.
REAR_CELLS = [(x, z) for x, z in FRONT_CELLS
              if not (abs(x) <= 57.3 and 45.0 < z < 367.0)]
print(f"REPORT cells front={len(FRONT_CELLS)} rear={len(REAR_CELLS)}")

def place_face(bm, front):
    vs = list(bm.verts)
    if front:
        bmesh.ops.translate(bm, vec=(0, -HD, 0), verts=vs)
    else:
        bmesh.ops.scale(bm, vec=(1, -1, 1), verts=vs)
        bmesh.ops.translate(bm, vec=(0, HD, 0), verts=vs)

def build_dishes(cells, front):
    def build(bm):
        for cx, cz in cells:
            rim = circle(cx, cz, DISH_RIM, 24)
            outer = [bm.verts.new((x, -0.5, z)) for x, z in rim]
            rings = [outer, [bm.verts.new((x, 0.0, z)) for x, z in rim]]
            for k in range(1, 8):
                phi = math.acos(DISH_OFF / DISH_R) * (1 - k / 8.0)
                rad = DISH_R * math.sin(phi)
                y = DISH_R * math.cos(phi) - DISH_OFF
                rings.append([bm.verts.new((x, y, z)) for x, z in circle(cx, cz, rad, 24)])
            stack(bm, rings, 0, cap_bottom=False, cap_top=False)
            bm.faces.new(outer[::-1]).material_index = 0
            pole = bm.verts.new((cx, DISH_DEPTH, cz))
            last = rings[-1]
            for i in range(24):
                bm.faces.new((last[i], last[(i + 1) % 24], pole)).material_index = 0
        place_face(bm, front)
        return 0
    return build

def build_holes(cells, front):
    def build(bm):
        for cx, cz in cells:
            for a in (90.0, 210.0, 330.0):
                hx = cx + HOLE_ORBIT * math.cos(math.radians(a))
                hz = cz + HOLE_ORBIT * math.sin(math.radians(a))
                cyl_y(bm, hx, hz, HOLE_R, -0.5, 14.0, 16, 1)
        place_face(bm, front)
        return 0
    return build

# ---------------------------------------------------------------- housing
def shell_levels():
    lev = []
    for i in range(5):
        h = BOT_FIL * i / 4
        lev.append((Z_BOT + h, BOT_FIL - math.sqrt(max(0.0, BOT_FIL ** 2 - (BOT_FIL - h) ** 2))))
    lev.append((Z_TOP - TOP_FIL, 0.0))
    for i in range(1, 7):
        h = TOP_FIL * i / 6
        lev.append((Z_TOP - TOP_FIL + h,
                    TOP_FIL - math.sqrt(max(0.0, TOP_FIL ** 2 - h * h))))
    return [(z, round(ins, 4)) for z, ins in lev]

bm = bmesh.new()
stack(bm, [ring(bm, plan(HW - ins, HD - ins, max(R_PLAN - ins, 2.0)), z)
           for z, ins in shell_levels()], 0)
housing = finish("housing", bm, [mat_alu, mat_dark])
print(f"REPORT housing_verts={len(housing.data.vertices)}")

def build_cavity(bm):
    prism(bm, plan(101.0, 215.0, 22.0, cy=CAV_CY), Z_BOT + WALL_B, Z_TOP - WALL_T, 1)
    return 0
cut(housing, build_cavity, "cavity")

cut(housing, build_dishes(FRONT_CELLS, True), "dishes_front")
cut(housing, build_holes(FRONT_CELLS, True), "holes_front")
cut(housing, build_dishes(REAR_CELLS, False), "dishes_rear")
cut(housing, build_holes(REAR_CELLS, False), "holes_rear")

def build_panel_step(bm):
    xzprism(bm, PANEL_CX, PANEL_CZ, FRAME_W, FRAME_H, FRAME_R,
            HD - FRAME_D, HD + 1.0, 0)
    return 0
cut(housing, build_panel_step, "panel_step")

def build_panel(bm):
    xzprism(bm, PANEL_CX, PANEL_CZ, PANEL_W, PANEL_H, PANEL_R, POCKET_Y, HD + 1.0, 1)
    for x in TB4_X:
        xzprism(bm, x, TB4_Z, 8.25, 2.5, 1.0, PORT_Y, HD + 0.6, 1)
    cyl_y(bm, AUDIO_X, ROW2_Z - 0.8, 3.2, POCKET_Y - 1.5, HD + 0.6, 20, 1)
    cyl_y(bm, AUDIO_X, ROW2_Z - 0.8, 1.7, PORT_Y, HD + 0.6, 20, 1)
    for x in HDMI_X:
        xzprism(bm, x, ROW2_Z, 14.0, 5.6, 1.0, PORT_Y, HD + 0.6, 1)
    for x in USBA_X:
        xzprism(bm, x, ROW2_Z, 12.8, 5.8, 0.8, PORT_Y, HD + 0.6, 1)
    for k in range(SLOT_N):
        z = SLOT_Z0 - k * SLOT_DZ
        xzrect(bm, PANEL_CX, z, 100.0, SLOT_H, POCKET_Y - 1.6, POCKET_Y + 0.1, 1)
    c13x, c13z = C13_XZ
    xzprism(bm, c13x, c13z, 27.0, 19.5, 2.0, PORT_Y, HD + 0.6, 1)
    for x, z in RJ45_XZ:
        xzprism(bm, x, z, 15.5, 12.8, 1.2, PORT_Y, HD + 0.6, 1)
    tri_caps(bm)
    return 0
cut(housing, build_panel, "panel")

def build_handle_recess(bm):
    for s in (-1, 1):
        prism(bm, plan(HANDLE_LEN / 2, HANDLE_W / 2, HANDLE_W / 2, 20, cy=s * HANDLE_Y),
              Z_TOP - 4.1, Z_TOP + 0.3, 0)
    return 0
cut(housing, build_handle_recess, "handle_recess")

def build_top_cuts(bm):
    for x in TOP_PORT_X:
        pts = [(x + px, TOP_Y_PORTS + py) for px, py in plan(1.5, 4.4, 1.2, 8)]
        prism(bm, pts, Z_TOP - 6.5, Z_TOP + 0.3, 1)
    prism(bm, circle(0.0, TOP_Y_BTN, 8.2, 32), Z_TOP - 0.8, Z_TOP + 0.3, 1)
    return 0
cut(housing, build_top_cuts, "top_cuts")

def build_latch_circle(bm):
    annulus(bm, circle(0.0, 0.0, LATCH_R + 0.4, 64), circle(0.0, 0.0, LATCH_R - 0.4, 64),
            Z_TOP - 0.5, Z_TOP + 0.1, 0)
    return 0
cut(housing, build_latch_circle, "latch_circle")

def build_latch_cross(bm):
    rect(bm, 0.0, 0.0, 2 * LATCH_R, 1.6, Z_TOP - 0.5, Z_TOP + 0.1, 0)
    dpts = [(D_RECESS_R * math.cos(math.radians(a)), D_RECESS_R * math.sin(math.radians(a)))
            for a in range(180, 361, 5)]
    prism(bm, dpts, Z_TOP - D_RECESS_DEEP, Z_TOP + 0.1, 0)
    return 0
cut(housing, build_latch_cross, "latch_cross")
bm = bmesh.new(); bm.from_mesh(housing.data)
smooth_by_angle(bm)
bm.to_mesh(housing.data); bm.free()
print(f"REPORT housing_after_cuts verts={len(housing.data.vertices)} "
      f"faces={len(housing.data.polygons)}")

# ---------------------------------------------------------------- honeycomb plates
def plate(name, y, front):
    bm = bmesh.new()
    x0, x1, z0, z1 = -100.5, 100.5, Z_BOT + 6.3, Z_TOP - 8.5
    vs = [bm.verts.new((x0, y, z0)), bm.verts.new((x1, y, z0)),
          bm.verts.new((x1, y, z1)), bm.verts.new((x0, y, z1))]
    f = bm.faces.new(vs if front else vs[::-1])
    uv = bm.loops.layers.uv.new("UVMap")
    for l in f.loops:
        # ~3 mm cells: the photos show 3-4 cells across a single 9 mm hole.
        l[uv].uv = (l.vert.co.x / 9.0, l.vert.co.z / 5.2)
    return finish(name, bm, [mat_honey])

honey_front = plate("honeycomb_front", -(HD - WALL_F) + 4.0, True)
honey_rear = plate("honeycomb_rear", HD - WALL_R - 4.0, False)

# ---------------------------------------------------------------- handles
def handle(name, cy):
    r, xl, xb, zb = HANDLE_R, HANDLE_LEG_X, HANDLE_LEG_X - 11.0, HANDLE_BAR_Z
    pts = [(-xl, cy, 468.0 + i * (zb - 11 - 468.0) / 6.0) for i in range(7)]
    for i in range(1, 10):
        a = math.radians(180 - 90 * i / 9)
        pts.append((-(xl - 11) + 11 * math.cos(a), cy, zb - 11 + 11 * math.sin(a)))
    for i in range(1, 9):
        pts.append((-xb + (2 * xb) * i / 8, cy, zb))
    for i in range(1, 10):
        a = math.radians(90 - 90 * i / 9)
        pts.append((xb + 11 * math.cos(a), cy, zb - 11 + 11 * math.sin(a)))
    pts += [(xl, cy, zb - 11 - i * (zb - 11 - 468.0) / 6.0) for i in range(1, 7)]
    bm = bmesh.new()
    sweep(bm, pts, r, 16)
    return finish(name, bm, [mat_steel])

handle("handle_front", -HANDLE_Y)
handle("handle_rear", HANDLE_Y)

def bezel(name, cy):
    bm = bmesh.new()
    annulus(bm, plan(HANDLE_LEN / 2 + 1.0, HANDLE_W / 2 + 1.0, HANDLE_W / 2 + 1.0, 20, cy=cy),
            plan(HANDLE_LEN / 2, HANDLE_W / 2, HANDLE_W / 2, 20, cy=cy),
            Z_TOP - 0.05, Z_TOP + 0.25, 0)
    tri_caps(bm)
    return finish(name, bm, [mat_steel])
bezel("bezel_front", -HANDLE_Y)
bezel("bezel_rear", HANDLE_Y)

# ---------------------------------------------------------------- latch handle
def dring():
    bm = bmesh.new()
    # The folded handle is a solid D-shaped plate lying in the pocket: the press shot
    # shows the semicircular pocket filled, with only a thin gap around it. An open
    # ring (the earlier build) reads as a handle standing proud of the top.
    r = 32.8
    pts = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
           for a in range(180, 361, 5)]
    prism(bm, pts, Z_TOP - 1.75, Z_TOP - 0.45, 0)
    tri_caps(bm)
    return finish("latch_ring", bm, [mat_alu])
dring()

# ---------------------------------------------------------------- button and markings
bm = bmesh.new()
cyl_z(bm, 0.0, TOP_Y_BTN, 7.9, Z_TOP - 0.85, Z_TOP - 0.08, 40, 0)
button = finish("power_button", bm, [mat_alu])

BOLT = [(0.55, 2.2), (-0.8, -0.5), (0.05, -0.5), (-0.55, -2.2),
        (0.8, 0.5), (-0.05, 0.5)]

bm = bmesh.new()
# The arc is centered on the button; without cx/cy it landed at the panel origin.
arc_band(bm, 2.9, 3.9, math.radians(200), math.radians(520),
         Z_TOP - 0.07, Z_TOP - 0.04, 40, 0, cx=0.0, cy=TOP_Y_BTN)
box(bm, (-2.5, TOP_Y_BTN, Z_TOP - 0.055), (3.4, 0.9, 0.03), 0)
# The two top ports carry the same bolt mark as the rear row, long axis across the width.
prism(bm, [((TOP_PORT_X[0] + TOP_PORT_X[1]) / 2 + v, TOP_Y_PORTS + u) for u, v in BOLT],
      Z_TOP - 0.05, Z_TOP + 0.03, 0)
for c in ((-2.0, -55.0), (51.0, 0.0)):
    cyl_z(bm, c[0], c[1], 0.7, Z_TOP + 0.005, Z_TOP + 0.03, 20, 0)
finish("top_markings", bm, [mat_logo])

bm = bmesh.new()
cyl_z(bm, 32.2, TOP_Y_LED, 1.25, Z_TOP - 0.02, Z_TOP + 0.05, 20, 0)
finish("led_top", bm, [mat_led])

# ---------------------------------------------------------------- ports and connectors
bm = bmesh.new()
for x in HDMI_X:
    box(bm, (x, POCKET_Y - 2.3, ROW2_Z), (9.0, 4.0, 1.0), 0)
finish("tongues_metal", bm, [mat_tongue])

bm = bmesh.new()
for x in TB4_X:
    box(bm, (x, POCKET_Y - 2.3, TB4_Z), (5.6, 4.0, 0.6), 0)
for x in USBA_X:
    box(bm, (x, POCKET_Y - 2.3, ROW2_Z + 1.1), (7.5, 4.0, 1.4), 0)
for x in TOP_PORT_X:
    box(bm, (x, TOP_Y_PORTS, Z_TOP - 3.3), (1.0, 5.5, 0.6), 0)
finish("tongues_dark", bm, [mat_port])

bm = bmesh.new()
for x, z in RJ45_XZ:
    box(bm, (x, POCKET_Y - 3.0, z + 2.0), (9.0, 4.0, 4.0), 0)
finish("rj45_bodies", bm, [mat_port])

# White C13 shell around a dark socket face, as in the press shot: the light frame is
# what makes the power inlet read as an inlet rather than another dark rectangle.
c13x, c13z = C13_XZ
bm = bmesh.new()
xzprism(bm, c13x, c13z, 24.0, 16.6, 2.2, POCKET_Y - 2.4, POCKET_Y - 1.0, 0)
finish("c13_face", bm, [mat_socket])
bm = bmesh.new()
xzprism(bm, c13x, c13z, 19.0, 12.6, 1.8, POCKET_Y - 1.05, POCKET_Y - 0.92, 0)
finish("c13_inner", bm, [mat_dark])

bm = bmesh.new()
c13x, c13z = C13_XZ
for c in ((c13x - 4.5, c13z + 4.0), (c13x + 4.5, c13z + 4.0), (c13x, c13z - 4.0)):
    box(bm, (c[0], POCKET_Y - 1.8, c[1]), (1.6, 3.5, 1.6), 0)
finish("connector_pins", bm, [mat_steel])

bm = bmesh.new()
xzpoly(bm, [(TB4_X[2] + (TB4_X[3] - TB4_X[2]) / 2 + x, TB4_Z + z) for x, z in BOLT],
       POCKET_Y - 0.05, POCKET_Y + 0.06, 0)
finish("thunderbolt_mark", bm, [mat_tongue])

bm = bmesh.new()
cyl_y(bm, REAR_LED[0], REAR_LED[1], 0.8, POCKET_Y - 0.02, POCKET_Y + 0.05, 16, 0)
finish("led_rear", bm, [mat_led])

# ---------------------------------------------------------------- feet
# Reference feet are a flat washer-like disc with a thin straight stem, not a bell:
# disc 55 mm x 5 mm, stem 15.2 mm, concave 9 mm flare where the stem meets the disc.
bm = bmesh.new()
prof = [(0.0, 26.8), (0.4, 27.3), (1.2, 27.5), (2.9, 27.5), (3.9, 27.1),
        (4.6, 26.0), (5.0, 24.2), (5.3, 22.0), (5.3, 17.0),
        (6.0, 12.4), (7.0, 9.6), (8.6, 8.3), (11.0, 7.75), (14.0, 7.6),
        (Z_BOT + 0.8, 7.6)]
for cx, cy in FOOT_XY:
    stack(bm, [ring(bm, circle(cx, cy, r, 24), z) for z, r in prof], 0)
finish("feet", bm, [mat_steel])

# ---------------------------------------------------------------- side Apple marks
FONT = bpy.data.fonts.load("/System/Library/Fonts/SFNS.ttf")

def mark_loops(half_w):
    cu = bpy.data.curves.new("mark", 'FONT')
    cu.font, cu.body, cu.size = FONT, "", 1.0
    cu.resolution_u, cu.align_x, cu.align_y = 5, 'CENTER', 'CENTER'
    ob = bpy.data.objects.new("mark", cu); sc.collection.objects.link(ob)
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    bm2 = bmesh.new(); bm2.from_mesh(me)
    bmesh.ops.remove_doubles(bm2, verts=bm2.verts, dist=1e-4)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in bm2.verts]
    ys = [v.co.y for v in bm2.verts]
    s = half_w / ((max(xs) - min(xs)) / 2)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    nxt = {l.vert: l.link_loop_next.vert for f in bm2.faces for l in f.loops
           if len(l.edge.link_faces) == 1}
    loops, seen = [], set()
    while len(seen) < len(nxt):
        v0 = next(v for v in nxt if v not in seen)
        v, loop = v0, []
        while True:
            seen.add(v); loop.append((-(v.co.x - cx) * s, -(v.co.y - cy) * s))
            v = nxt[v]
            if v == v0:
                break
        loops.append(loop)
    if sum(map(len, loops)) != len(nxt):
        raise RuntimeError(f"mark: walked {sum(map(len, loops))} of {len(nxt)}")
    bm2.free()
    return loops

MARK = mark_loops(LOGO_W)

def logo(name, s):
    bm = bmesh.new()
    for loop in MARK:
        # mark_loops' outline comes back rotated 180 degrees from the font; undo that here.
        inner = [bm.verts.new((s * 108.4, -s * u, LOGO_Z - v)) for u, v in loop]
        outer = [bm.verts.new((s * 109.3, -s * u, LOGO_Z - v)) for u, v in loop]
        stack(bm, [inner, outer], 0)
    tri_caps(bm)
    return finish(name, bm, [mat_logo])
logo("logo_left", -1)
logo("logo_right", 1)

# ---------------------------------------------------------------- report envelopes
def bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in objs:
        ev = o.evaluated_get(dg); m = ev.to_mesh()
        for v in m.vertices:
            w = ev.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
        ev.to_mesh_clear()
    return lo, hi

parts = [o for o in sc.objects if o.type == 'MESH']
lo, hi = bbox(parts)
dims = [(hi[i] - lo[i]) / MM for i in range(3)]
print(f"REPORT envelope_mm=({dims[0]:.2f}, {dims[1]:.2f}, {dims[2]:.2f}) "
      f"z={lo[2]/MM:.2f}..{hi[2]/MM:.2f}")
hlo, hhi = bbox([housing])
hdims = [(hhi[i] - hlo[i]) / MM for i in range(3)]
print(f"REPORT housing_mm=({hdims[0]:.2f}, {hdims[1]:.2f}, {hdims[2]:.2f}) "
      f"z={hlo[2]/MM:.2f}..{hhi[2]/MM:.2f}")
if abs(hdims[0] - 218) > 0.2 or abs(hdims[1] - 450) > 0.2 or abs(hdims[2] - 429.5) > 0.2:
    raise RuntimeError(f"housing envelope drift: {hdims}")
if abs(hi[2] / MM - 529.0) > 0.6 or abs(lo[2] / MM) > 0.1:
    raise RuntimeError(f"assembly height drift: {lo[2]/MM:.2f}..{hi[2]/MM:.2f}")

if NORENDER:
    print("REPORT norender=done")
    sys.exit(0)

# ---------------------------------------------------------------- studio
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

def frame(off, ctr, half, lens=52, fill=0.62):
    off = Vector(off).normalized()
    d = 2 * half / fill * lens / cd.sensor_width
    cd.lens = lens
    loc = Vector(ctr) + off * d
    cam.location = loc
    cam.rotation_euler = (Vector(ctr) - loc).to_track_quat('-Z', 'Y').to_euler()

CTR = (0.0, 0.0, 0.2645)
HALF = 0.2645
VIEWS = {
    "hero":    dict(off=(0.62, -0.86, 0.34), ctr=CTR, half=HALF, fill=0.68),
    "front":   dict(off=(0.0, -1.0, 0.07), ctr=CTR, half=HALF, fill=0.80),
    "back":    dict(off=(0.05, 1.0, 0.07), ctr=CTR, half=HALF, fill=0.80),
    "side":    dict(off=(-1.0, -0.04, 0.06), ctr=CTR, half=HALF, fill=0.82),
    "top":     dict(off=(0.04, -0.22, 1.0), ctr=(0, 0, 0.4737), half=0.219, fill=0.92),
    "lattice": dict(off=(0.28, -1.0, 0.14), ctr=(0.0, -0.225, 0.30), half=0.060, fill=0.90,
                    exp=-0.35),
    "ports":   dict(off=(0.03, 1.0, 0.06), ctr=(-0.001, 0.2198, 0.21), half=0.16, fill=0.88),
    "topio":   dict(off=(0.02, -0.18, 1.0), ctr=(0.0, 0.125, 0.4737), half=0.058, fill=0.90),
    "handle":  dict(off=(0.45, -0.85, 0.30), ctr=(0.0, -0.1955, 0.50), half=0.08, fill=0.90),
    "latch":   dict(off=(0.08, -0.30, 1.0), ctr=(0.0, -0.004, 0.4737), half=0.06, fill=0.90),
}
os.makedirs(OUT, exist_ok=True)
for name, v in VIEWS.items():
    frame(v["off"], v["ctr"], v["half"], fill=v.get("fill", 0.62))
    # The lattice macro is 1/3 stop down: at the set exposure the dish lips blow to white
    # over 2.47% of the frame; -0.35 EV puts them at 1.80% without touching the product.
    sc.view_settings.exposure = v.get("exp", 0.0)
    sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"REPORT rendered={name}")

# ---------------------------------------------------------------- export
for o in sc.objects:
    o.select_set(o.type == 'MESH' and o is not floor)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "macpro.glb"),
                          export_format='GLB', export_apply=True, use_selection=True)
print(f"REPORT glb_bytes={os.path.getsize(os.path.join(OUT, 'macpro.glb'))}")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "macpro.blend"))
