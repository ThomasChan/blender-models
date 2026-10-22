# iMac (Retina 5K, 27-inch, 2020) -- hand-built. This is the last Intel 27" iMac: a 5 mm
# edge around a flat glass front, and the deep convex aluminium back that the 24" M1 iMac
# (already in this folder, converted from Apple's USDZ) replaced with a flat slab.
#
# Apple's archived 2020 product page has no USDZ (checked the page and the Wayback CDX for
# /105/media/us/imac/*: zero .usdz), so every number is Apple's spec sheet or measured off
# the 2020 press and iFixit photos in /tmp/imac27-ref (scale 650 mm / 1640 px = 0.39634
# mm/px on the straight-on press shot). See ## imac27 in README.md.
#
# Envelope 650 W x 203 D x 516 H. Body (display + chin) 650 x 44 x 448, sitting at z=68.
# Display active area 596.6 x 335.6, chin 60 mm, 5 mm edge, 44 mm back bulge.
#
#   Blender -b --factory-startup --python-exit-code 1 --python build_imac27.py -- .
#   Blender ... --python build_imac27.py -- . norender     # geometry only, for iteration
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else ".")
NORENDER = "norender" in argv
ONLY = next((a.split("=", 1)[1].split(",") for a in argv if a.startswith("views=")), None)
MM = 0.001
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- dimensions, plain mm
BODY_W, BODY_H, BODY_D = 650.0, 448.0, 44.0
Z_BOT, Z_TOP = 68.0, 516.0
ZC = (Z_BOT + Z_TOP) / 2                 # 292
R_PLAN = 22.0                            # front glass corner radius
EDGE_T = 5.0                             # the thin edge
FRONT_T = 0.9                            # front glass/bezel plate
CAP_Y = 1.0                              # body's front cap, 0.1 mm behind the glass
CORNER_SEG = 20
DOME_P = 1.35                            # (1-s^2)^p; p=1.35 matches the side silhouette

CHIN_H = 60.0
SCREEN_W, SCREEN_H = 596.6, 335.6
SCREEN_X0 = -SCREEN_W / 2
SCREEN_Z0 = 153.0
SCREEN_Z1 = SCREEN_Z0 + SCREEN_H         # 488.6; top bezel 27.4, bottom 25.1
LOGO_HALF_W = 12.3                       # 24.6 x ~30.3 mm mark
LOGO_Z = 100.2
CAM_Z = 504.0

# rear layout, in BACK-VIEW x (x_world = -x_back)
# Vents and the memory door sit behind the blade, between hinge and power inlet, as
# the iFixit 2020 teardown shows; the blade hides their middles and only the edges
# peek out, which is why the first pass invented vents at the top and a right door.
# 934's rear shot gives nine thin slots at ~4 mm pitch, the top one a clear 40 mm
# below the hinge bar; here 9 x 1.6 mm at 4 mm pitch keeps 13 mm to the barrel and
# 8 mm to the door seam instead of the old 7 chunky bars touching both.
VENT_Z0, VENT_N, VENT_PITCH = 241.2, 9, 4.0
VENT_COL_X, VENT_L, VENT_H = 36.0, 60.0, 1.6
PORT_Z = 129.0
# Positions from Apple's support close-up (1067 px crop, machine edge at px 3): its
# 55.5 px USB-A pitch over the 16.85 mm pitch in the angled connectivity shot gives
# 3.293 px/mm. Row shifted 25 mm left so Ethernet clears the blade by ~35 mm, and the
# headphone sits ~58 mm in from the edge as in the straight-on back render.
PORTS = [                                # name, x_back, w, h, r, depth
    ("headphone", -264.0, 6.4, 6.4, 3.2, 3.4),
    ("sdxc", -233.5, 32.5, 2.8, 1.4, 3.0),
    ("usb-a1", -201.9, 13.5, 5.8, 1.5, 3.0),
    ("usb-a2", -185.1, 13.5, 5.8, 1.5, 3.0),
    ("usb-a3", -168.3, 13.5, 5.8, 1.5, 3.0),
    ("usb-a4", -151.5, 13.5, 5.8, 1.5, 3.0),
    ("usb-c1", -136.2, 8.9, 2.6, 1.3, 2.8),
    ("usb-c2", -122.2, 8.9, 2.6, 1.3, 2.8),
    ("ethernet", -102.7, 15.5, 13.0, 1.2, 3.6),
]
# The power cord enters through a 66 mm round hole in the stand's blade and plugs into
# the C7 socket on the body behind it (iFixit's RAM guide shows both). The RAM-door
# release is a small slot just inside the hole's top rim. Power button on the right:
# flush alu dish, 19 mm, with the power symbol etched light.
POWER_BTN_XB, POWER_BTN_Z, POWER_BTN_R = 259.0, 121.0, 9.5
PWR_INLET_Z = 131.0
PWR_HOLE_R = 33.0
# Door: 150 x 60 hatch centred behind the blade, above the inlet (7.6 mm clear of
# the hole's top), below the vents (8 mm clear of their lowest slot). The 934 shot
# measures its exposed right edge at ~59 mm tall by ~15 mm wide past the blade.
RAM_XB, RAM_Z, RAM_W, RAM_H = 0.0, 202.0, 150.0, 60.0
RAM_BTN_Z, RAM_BTN_W, RAM_BTN_H = 161.0, 4.5, 2.5

# Stand. One 8 mm sheet bent into a J -- the reading the 934/379/357 traces led
# to, and the one the user confirmed. The plate is level, 196 mm wide with R30
# front corners; at its rear the sheet turns up with the front face tangent to
# the plate's top (r=20) and the back face tangent to the plate's bottom
# (r=28), both about (y 128.42, z 28). The outer arc's rear-most point is the
# stand's rear extent -- 156.42 at z=28 -- so the foot's rear edge is the bend
# itself, with no shelf behind the arm. The narrow side faces keep the sheet's
# 8 mm width through the bend (the equal-width band the user asked for); only
# their plan path flares, from the plate's +-98 in to the arm's +-70. The arm
# leaves the bend at 23.1 deg to vertical, passes the hinge (41, 294) and
# tapers 141 -> 105 mm.
#
# 357's width rows land on the bend: 151.3 mm at 3.7 mm above the plate top
# (z 11.7), 146.8 at 12.7, 141.6 at 24.6, 140.1 at 36.5. The old separate
# front-bend / heel-roll build widened the section to ~36 mm at the base,
# which fanned the side face into the skirt the user rejected.
#
# Reference chain: the bare part photos are a genuine Apple 923-0299 (the stand
# shared by A1419 2012-2017 and A2115 2019-2020) together with IT Home's 2020
# gallery (357 front, 379 side, 934/180 rear). Apple ships no 2020 27-inch USDZ;
# the 24-inch M4 asset is a *different* stand design and is not evidence here.
FOOT_TOP = 8.0
FOOT_FRONT, FOOT_BACK, FOOT_W = -47.0, 156.42, 196.0
FOOT_RF = 30.0                         # plate's front plan corners
FOOT_W_REAR = 153.0                    # plan taper: 196 at the R30 corners down
                                       # to this at the bend, so the back view is
                                       # one trapezoid instead of a flare
BEND_RI, BEND_RO = 20.0, 28.0          # front face on the plate top, back on the bottom
BEND_CZ = FOOT_TOP + BEND_RI           # bend centre height
BEND_CY = FOOT_BACK - BEND_RO          # centre y: the outer arc's crown is the rear extent
BLADE_T, EDGE_R = 8.0, 1.0             # an 8 mm sheet with a 1 mm edge round
HINGE_Y, HINGE_Z = 41.0, 294.0
ARM_W0, ARM_W1 = 141.0, 105.0          # width at the tangent, at the hinge
BODY_TILT = math.radians(12.0)         # press pose, about the hinge

ARM_R = (BEND_RI + BEND_RO) / 2.0
_VY, _VZ = HINGE_Y - BEND_CY, HINGE_Z - BEND_CZ
# Arm angle: the tangent from the hinge to the 24 mm centreline circle. The
# tangent point is where the bend hands the sheet to the straight arm.
BEND_END = math.atan2(_VZ, _VY) - math.acos(ARM_R / math.hypot(_VY, _VZ))
ARM_T = (BEND_CY + ARM_R * math.cos(BEND_END),
         BEND_CZ + ARM_R * math.sin(BEND_END))

# (theta on the bend, sheet width). 357's rows map to the bend by
# theta = asin((8 + height - 28) / 24); the last point is the arm's tangent.
# The -90 entry is the plate's rear width, not the plate's front width: the
# front view already narrows to 151.3 just above the plate, so bending a
# full-width plate up would flare the heel.
BEND_W = ((-90.0, FOOT_W_REAR), (-42.8, 151.3), (-17.7, 146.8),
          (11.0, 141.6), (math.degrees(BEND_END), ARM_W0))

def foot_width(y):
    """Plate width in plan: full FOOT_W where the R30 corners end, tapering to
    the bend's width at BEND_CY."""
    return FOOT_W + (FOOT_W_REAR - FOOT_W) * (y - FOOT_FRONT - FOOT_RF) / (
        BEND_CY - FOOT_FRONT - FOOT_RF)

def bend_width(theta):
    for (a0, w0), (a1, w1) in zip(BEND_W, BEND_W[1:]):
        if theta <= a1:
            return w0 + (w1 - w0) * max((theta - a0) / (a1 - a0), 0.0)
    return BEND_W[-1][1]

def arm_y(z):
    """Arm centreline: the tangent line through the hinge."""
    return HINGE_Y + (HINGE_Z - z) * math.tan(BEND_END)

def stand_rings():
    """(mid-surface point, sheet tangent, width, depth scale) per ring, from
    the plate's front edge along the sheet, round the bend and up the arm.
    The ring plane is perpendicular to the tangent, so the section's 8 mm
    stays radial through the bend and the side faces keep one width. The
    plate's R30 front corners are the width taper over its first 30 mm, then
    foot_width() carries 196 down to the bend's 153."""
    out = []
    for a in (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0):
        r = math.radians(a)
        out.append((Vector((0.0, -17.0 - FOOT_RF * math.cos(r), FOOT_TOP / 2)),
                    Vector((0.0, 1.0, 0.0)),
                    2.0 * (FOOT_W / 2 - FOOT_RF + FOOT_RF * math.sin(r)), 1.0))
    for y in (10.0, 40.0, 70.0, 100.0, BEND_CY):
        out.append((Vector((0.0, y, FOOT_TOP / 2)), Vector((0.0, 1.0, 0.0)),
                    foot_width(y), 1.0))
    th_end = math.degrees(BEND_END)
    angs = {-90.0 + (th_end + 90.0) * i / 12.0 for i in range(1, 13)}
    angs |= {-42.8, -17.7, 0.0, 11.0}
    for th in sorted(angs):
        a = math.radians(th)
        out.append((Vector((0.0, BEND_CY + ARM_R * math.cos(a),
                            BEND_CZ + ARM_R * math.sin(a))),
                    Vector((0.0, -math.sin(a), math.cos(a))),
                    bend_width(th), 1.0))
    t = Vector((0.0, -math.sin(BEND_END), math.cos(BEND_END)))
    for z in (60.0, 90.0, 125.0, 160.0, 195.0, 230.0, 260.0, 280.0, 291.0,
              HINGE_Z):
        u = (z - ARM_T[1]) / (HINGE_Z - ARM_T[1])
        out.append((Vector((0.0, arm_y(z), z)), t,
                    ARM_W0 + (ARM_W1 - ARM_W0) * u, 1.0))
    # Shoulder: pull the section's depth (not its width) into the body's back.
    for z_top, fd, fw in ((296.0, 0.86, 0.99), (297.5, 0.60, 0.96),
                          (298.6, 0.28, 0.91)):
        pz = z_top - BLADE_T / 2 * fd * math.sin(BEND_END)
        out.append((Vector((0.0, arm_y(pz), pz)), t, ARM_W1 * fw, fd))
    return out

# ---------------------------------------------------------------- helpers
def principled(name, color, metallic, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*color, 1.0)
    return m

# Bead-blasted aluminium: fully metallic and rough. At metallic 0.92 / rough 0.42
# the 8% dielectric specular sat on top of the metal and read as glazed ceramic.
mat_alu = principled("Aluminium", (0.70, 0.70, 0.715), 1.0, 0.56)
mat_bezel = principled("BezelGlass", (0.006, 0.006, 0.008), 0.0, 0.09)
mat_dark = principled("Dark", (0.018, 0.018, 0.022), 0.15, 0.50)
mat_logo = principled("LogoInlay", (0.010, 0.010, 0.012), 0.2, 0.28)
mat_inlet = principled("PowerInlet", (0.82, 0.82, 0.83), 0.0, 0.45)
mat_port = principled("PortInterior", (0.055, 0.055, 0.06), 0.25, 0.50)
mat_lens = principled("CameraLens", (0.008, 0.010, 0.020), 0.1, 0.05)

def plan(hw, hd, r, seg=CORNER_SEG, cy=0.0, edge=8):
    """CCW plan boundary: four corner arcs, same corner first, same direction round.

    The straight spans get `edge` segments. Subdividing them was an attempt at the
    X on the back and it did not fix it -- the kink is in the height field's
    derivative, not the tessellation (see soften_dome_normals). The extra verts
    are collinear, so this is harmless rather than load-bearing.
    """
    raw = []
    for cx, cyy, a0 in ((hw - r, -hd + r, -90), (hw - r, hd - r, 0),
                        (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            raw.append((cx + r * math.cos(a), cy + cyy + r * math.sin(a)))
    if not edge:
        return raw
    pts = []
    for i, p in enumerate(raw):
        q = raw[(i + 1) % len(raw)]
        pts.append(p)
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d > r:                      # a straight span, not a corner chord
            for k in range(1, edge):
                t = k / edge
                pts.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
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

def circle(cx, cy, r, n):
    return [(r * math.cos(2 * math.pi * i / n) + cx,
             r * math.sin(2 * math.pi * i / n) + cy) for i in range(n)]

def tri_caps(bm):
    # bmesh.ops.triangulate fans a concave cap from its first vertex and bridges the
    # Apple mark's notch with a chord; tessellate_polygon respects the outline.
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
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    for v in vs:
        v.co.x = v.co.x * s[0] + c[0]
        v.co.y = v.co.y * s[1] + c[1]
        v.co.z = v.co.z * s[2] + c[2]
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs

def cyl_y(bm, cx, cz, r, y0, y1, n=16, mi=0):
    """Cylinder along +Y; xz loop, so it shares stack()'s winding with the panel prisms."""
    pts = circle(cx, cz, r, n)
    a = [bm.verts.new((x, y0, z)) for x, z in pts]
    b = [bm.verts.new((x, y1, z)) for x, z in pts]
    return stack(bm, [a, b], mi)

def cyl_axis(bm, p, n, r, t0, t1, seg=48, mi=0):
    """Capped cylinder along arbitrary axis n: rings at signed distances t0..t1."""
    u = Vector((1.0, 0.0, 0.0))
    n = Vector(n).normalized()
    v = n.cross(u)
    p = Vector(p)
    stack(bm, [[bm.verts.new(p + n * t + (u * math.cos(2 * math.pi * i / seg)
                                          + v * math.sin(2 * math.pi * i / seg)) * r)
                for i in range(seg)] for t in (t0, t1)], mi)

def xzprism(bm, cx, cz, w, h, r, y0, y1, mi=0):
    pts = plan(w / 2, h / 2, min(r, min(w, h) / 2 - 1e-4), 20)
    return stack(bm, [[bm.verts.new((cx + px, y, cz + py)) for px, py in pts]
                      for y in (y0, y1)], mi)

def xzrect(bm, cx, cz, w, h, y0, y1, mi=0):
    pts = [(cx - w / 2, cz - h / 2), (cx + w / 2, cz - h / 2),
           (cx + w / 2, cz + h / 2), (cx - w / 2, cz + h / 2)]
    return stack(bm, [[bm.verts.new((x, y, z)) for x, z in pts] for y in (y0, y1)], mi)

def xzpoly(bm, pts, y0, y1, mi=0):
    return stack(bm, [[bm.verts.new((x, y, z)) for x, z in pts] for y in (y0, y1)], mi)

def xz_annulus(bm, cx, cz, r0, r1, surf, off, n=32, mi=0):
    """Ring in the XZ plane, bent onto surf(x, z), extruded along Y by off[0..1]."""
    outer = [(cx + r1 * math.cos(2 * math.pi * i / n),
              cz + r1 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    inner = [(cx + r0 * math.cos(2 * math.pi * i / n),
              cz + r0 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    # XZ loops, not ring() -- ring() makes XY points and put this annulus flat in
    # the XY plane at z=18, buried in the stand, invisible in every render.
    # Per-vertex surf: a flat ring spans enough dome sag to bury half of itself.
    rings = [[bm.verts.new((x, surf(x, z) + dy, z)) for x, z in pts]
             for pts, dy in ((outer, off[0]), (outer, off[1]),
                             (inner, off[1]), (inner, off[0]), (outer, off[0]))]
    return stack(bm, rings, mi, cap_bottom=False, cap_top=False)

SHARP = math.radians(33)

def smooth_by_angle(bm, sharp=SHARP):
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > sharp:
            e.smooth = False

def resharp(o):
    """Re-run the angle split on a boolean's output. The boolean's new rim edges
    inherit smooth shading, so a 12 mm hole in a 14 mm blade shaded itself into a
    40 mm funnel; finish() only ever saw the cutter, never the result."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    smooth_by_angle(bm)
    bm.to_mesh(o.data); bm.free()

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

def cut(target, build, name, mats=(mat_alu, mat_dark), op='DIFFERENCE'):
    bm = bmesh.new(); build(bm)
    o = finish(name, bm, list(mats))
    m = target.modifiers.new(name, 'BOOLEAN')
    m.operation, m.object, m.solver = op, o, 'EXACT'
    m.use_self = True
    m.material_mode = 'INDEX'
    before = len(target.data.vertices)
    with bpy.context.temp_override(object=target, active_object=target,
                                   selected_objects=[target], selected_editable_objects=[target]):
        status = bpy.ops.object.modifier_apply(modifier=name)
    after = len(target.data.vertices)
    if status != {'FINISHED'} or after <= before:
        raise RuntimeError(f"boolean {name}: {status}, verts {before} -> {after}")
    resharp(target)
    bpy.data.objects.remove(o, do_unlink=True)
    return after

# ---------------------------------------------------------------- the back's profile
BODY_PLAN = plan(BODY_W / 2, BODY_H / 2, R_PLAN)
BODY_SEGS = [(BODY_PLAN[i], BODY_PLAN[(i + 1) % len(BODY_PLAN)])
             for i in range(len(BODY_PLAN))]

def boundary_radius(ux, uz):
    """Distance from the back's centre to the rounded-rect silhouette along (ux, uz)."""
    best = 1e9
    for (x1, z1), (x2, z2) in BODY_SEGS:
        dx, dz = x2 - x1, z2 - z1
        det = ux * dz - uz * dx
        if abs(det) < 1e-9:
            continue
        t = (x1 * dz - z1 * dx) / det
        s = (x1 * uz - z1 * ux) / det
        if t > 0 and -1e-6 <= s <= 1 + 1e-6:
            best = min(best, t)
    return best

def surface_y(x, z):
    """The convex back's y at a point on the body -- y=5 at the rim, 44 at the pole."""
    dx, dz = x, z - ZC
    r = math.hypot(dx, dz)
    if r < 1e-6:
        return BODY_D
    b = boundary_radius(dx / r, dz / r)
    s = min(r / b, 1.0)
    return EDGE_T + (BODY_D - EDGE_T) * (1 - s * s) ** DOME_P

# ---------------------------------------------------------------- front outlines
def chin_outline():
    hw, h, r = BODY_W / 2, CHIN_H, R_PLAN
    pts = [(-hw + r, 0.0), (hw - r, 0.0)]
    for i in range(1, 13):
        a = math.radians(-90 + 90 * i / 12)
        pts.append((hw - r + r * math.cos(a), r + r * math.sin(a)))
    pts += [(hw, h), (-hw, h), (-hw, r)]
    for i in range(1, 12):
        a = math.radians(180 + 90 * i / 12)
        pts.append((-hw + r + r * math.cos(a), r + r * math.sin(a)))
    return [(x, z + Z_BOT) for x, z in pts]

def bezel_outline():
    hw, r = BODY_W / 2, R_PLAN
    lo, hi = CHIN_H, BODY_H
    pts = [(hw, lo), (hw, hi - r)]
    for i in range(1, 13):
        a = math.radians(90 * i / 12)
        pts.append((hw - r + r * math.cos(a), hi - r + r * math.sin(a)))
    pts += [(-hw + r, hi), (-hw, hi - r)]
    for i in range(1, 13):
        a = math.radians(90 + 90 * i / 12)
        pts.append((-hw + r + r * math.cos(a), hi - r + r * math.sin(a)))
    pts += [(-hw, lo)]
    return [(x, z + Z_BOT) for x, z in pts]

def front_prism(name, pts, y0, y1, mat):
    bm = bmesh.new()
    stack(bm, [[bm.verts.new((x, y, z)) for x, z in pts] for y in (y0, y1)])
    return finish(name, bm, [mat])

# ---------------------------------------------------------------- display wallpaper
def wallpaper():
    W, H = 1600, 900
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    U, V = np.meshgrid(u, v)
    stops_v = np.array([0.0, 0.30, 0.55, 0.72, 0.86, 1.0])
    stops_c = np.array([
        [0.035, 0.020, 0.070],   # bottom: deep plum
        [0.23, 0.07, 0.16],
        [0.72, 0.26, 0.22],
        [0.96, 0.60, 0.30],      # horizon glow
        [0.36, 0.20, 0.40],
        [0.035, 0.055, 0.155],   # top: indigo
    ])
    col = np.stack([np.interp(V, stops_v, stops_c[:, c]) for c in range(3)], axis=-1)
    band = np.sin(V * 9.5 + 1.25 * np.sin(U * 4.2 + 0.6) + 0.4)
    col *= (1.0 + 0.055 * band)[..., None]
    glow = np.exp(-(((U - 0.70) / 0.30) ** 2 + ((V - 0.66) / 0.18) ** 2))
    col += glow[..., None] * np.array([0.16, 0.05, 0.015])
    col = np.clip(col, 0.0, 0.92)
    px = np.ones((H, W, 4), dtype=np.float32); px[..., :3] = col
    img = bpy.data.images.new("DisplayWallpaper", W, H, alpha=False)
    img.pixels.foreach_set(px.ravel())
    path = os.path.join(OUT, "display-wallpaper.png")
    img.filepath_raw = path; img.file_format = 'PNG'
    img.save(); img.pack()
    return img

uimg = wallpaper()
mat_display = bpy.data.materials.new("Display"); mat_display.use_nodes = True
_dn = mat_display.node_tree
_db = _dn.nodes["Principled BSDF"]
_db.inputs["Base Color"].default_value = (0, 0, 0, 1)
_db.inputs["Metallic"].default_value = 0.0
_db.inputs["Roughness"].default_value = 0.25
_tex = _dn.nodes.new("ShaderNodeTexImage"); _tex.image = uimg
_dn.links.new(_tex.outputs["Color"], _db.inputs["Emission Color"])
_db.inputs["Emission Strength"].default_value = 1.0

# ---------------------------------------------------------------- body
def build_body():
    bm = bmesh.new()
    plan_abs = [(x, ZC + z) for x, z in BODY_PLAN]

    def rv(scale, y):
        return [bm.verts.new((x * scale, y, ZC + (z - ZC) * scale)) for x, z in plan_abs]

    rings = [rv(1.0, CAP_Y), rv(1.0, EDGE_T)]
    M = 26
    for k in range(1, M):
        s = 1 - (k / M) ** 1.6
        y = EDGE_T + (BODY_D - EDGE_T) * (1 - s * s) ** DOME_P
        rings.append(rv(s, y))
    for a, b in zip(rings, rings[1:]):
        for i in range(len(a)):
            j = (i + 1) % len(a)
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = 0
    bm.faces.new(rings[0][::-1]).material_index = 0
    pole = bm.verts.new((0, BODY_D, ZC))
    last = rings[-1]
    for i in range(len(last)):
        j = (i + 1) % len(last)
        bm.faces.new((last[i], last[j], pole)).material_index = 0
    return finish("body", bm, [mat_alu, mat_dark])

body = build_body()

# ---------------------------------------------------------------- rear cuts
def build_vent_cuts(bm):
    for xb in (-VENT_COL_X, VENT_COL_X):
        cx = -xb
        for i in range(VENT_N):
            z = VENT_Z0 + i * VENT_PITCH
            ys = [surface_y(cx + dx, z + dz)
                  for dx in (-VENT_L / 2, 0, VENT_L / 2)
                  for dz in (-VENT_H / 2, VENT_H / 2)]
            y0 = min(ys) - 3.0
            xzprism(bm, cx, z, VENT_L, VENT_H, VENT_H / 2, y0, y0 + 24, 1)

def build_port_cuts(bm):
    for _n, xb, w, h, r, depth in PORTS:
        cx = -xb
        y = surface_y(cx, PORT_Z)
        xzprism(bm, cx, PORT_Z, w, h, r, y - depth, y + 20, 1)

def build_power_cut(bm):
    # 0.35 mm saucer, alu bottom (index 0): the official button is almost flush.
    cx = -POWER_BTN_XB
    y0 = surface_y(cx, POWER_BTN_Z) - 0.35
    cyl_y(bm, cx, POWER_BTN_Z, POWER_BTN_R, y0, y0 + 40, 48, 0)

cut(body, build_vent_cuts, "vent_cut")
cut(body, build_port_cuts, "port_cut")
cut(body, build_power_cut, "power_cut")

# ---------------------------------------------------------------- front parts
chin = front_prism("chin", chin_outline(), 0.0, FRONT_T, mat_alu)
bezel = front_prism("bezel", bezel_outline(), 0.0, FRONT_T, mat_bezel)
cut(bezel, lambda bm: xzrect(bm, 0, (SCREEN_Z0 + SCREEN_Z1) / 2, SCREEN_W, SCREEN_H,
                             -0.8, FRONT_T + 0.8, 0),
    "screen_hole", mats=(mat_bezel,))

def make_display():
    bm = bmesh.new()
    box(bm, (0, 1.21, (SCREEN_Z0 + SCREEN_Z1) / 2), (SCREEN_W, 0.5, SCREEN_H), 0)
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            l[uvl].uv = ((l.vert.co.x - SCREEN_X0) / SCREEN_W,
                         (l.vert.co.z - SCREEN_Z0) / SCREEN_H)
    return finish("display", bm, [mat_display])

display = make_display()

# Apple mark on the chin
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

MARK = mark_loops(LOGO_HALF_W)
_lx = [u for loop in MARK for u, _v in loop]
_lz = [LOGO_Z - v for loop in MARK for _u, v in loop]
LOGO_SIZE = (max(_lx) - min(_lx), max(_lz) - min(_lz))

def make_logo():
    bm = bmesh.new()
    for loop in MARK:
        # mark_loops hands back the outline rotated 180 degress; undo that here.
        a = [bm.verts.new((-u, -0.06, LOGO_Z - v)) for u, v in loop]
        b = [bm.verts.new((-u, 0.14, LOGO_Z - v)) for u, v in loop]
        stack(bm, [a, b], 0)
    tri_caps(bm)
    return finish("chin_logo", bm, [mat_logo])

chin_logo = make_logo()

# The back's Apple mark sits on the dome (mirrored in x vs the chin mark, because it
# is read from behind). 60 mm wide -> the mark's own 24.6:30.3 aspect gives 73.9 tall.
BACK_LOGO_W, BACK_LOGO_Z = 60.0, 420.0

def make_back_logo():
    s = BACK_LOGO_W / LOGO_SIZE[0]
    bm = bmesh.new()
    for loop in MARK:
        outer, inner = [], []
        for u, v in loop:
            x, z = u * s, BACK_LOGO_Z - v * s
            y = surface_y(x, z)
            outer.append(bm.verts.new((x, y + 0.09, z)))
            inner.append(bm.verts.new((x, y - 0.30, z)))
        stack(bm, [inner, outer], 0)
    tri_caps(bm)
    return finish("back_logo", bm, [mat_logo])

back_logo = make_back_logo()

def make_camera():
    bm = bmesh.new(); cyl_y(bm, 0, CAM_Z, 3.5, -0.01, 0.04, 32, 0)
    r = finish("camera_ring", bm, [mat_dark])
    bm = bmesh.new(); cyl_y(bm, 0, CAM_Z, 2.2, -0.02, 0.05, 32, 0)
    l = finish("camera_lens", bm, [mat_lens])
    return r, l

cam_ring, cam_lens = make_camera()

# ---------------------------------------------------------------- stand
def blade_pts(hw, hd, r, bow, n=12, k=3):
    """CCW blade section, fixed point count at every ring: an 8 mm sheet. The
    long faces carry n segments so an optional bow would shade as a curve
    instead of one flat quad; bow is 0 here (379 reads the side flat) and 0 at
    the rolled edges, so the 1 mm edge highlight survives."""
    r = min(r, hw - 1e-4, hd - 1e-4)
    hf = hw - r

    def b(x):
        t = x / hf
        return bow * (1.0 - t * t) ** 2 if abs(t) < 1.0 else 0.0

    pts = []
    for i in range(k + 1):                       # front-right corner
        a = math.radians(-90 + 90 * i / k)
        pts.append((hf + r * math.cos(a), -hd + r + r * math.sin(a)))
    for i in range(1, k + 1):                    # right wall
        pts.append((hw, -hd + r + 2 * (hd - r) * i / k))
    for i in range(1, k + 1):                    # rear-right corner
        a = math.radians(90 * i / k)
        pts.append((hf + r * math.cos(a), hd - r + r * math.sin(a)))
    for i in range(1, n + 1):                    # rear face, leftwards
        x = hf - 2 * hf * i / n
        pts.append((x, hd + b(x)))
    for i in range(1, k + 1):                    # rear-left corner
        a = math.radians(90 + 90 * i / k)
        pts.append((-hf + r * math.cos(a), hd - r + r * math.sin(a)))
    for i in range(1, k + 1):                    # left wall
        pts.append((-hw, hd - r - 2 * (hd - r) * i / k))
    for i in range(1, k + 1):                    # front-left corner
        a = math.radians(180 + 90 * i / k)
        pts.append((-hf + r * math.cos(a), -hd + r + r * math.sin(a)))
    for i in range(1, n):                        # front face, rightwards
        x = -hf + 2 * hf * i / n
        pts.append((x, -hd + b(x)))
    return pts

def build_stand_j(bm):
    """The J sheet: one lofted stack of perpendicular sections, so the plate,
    the bend and the arm are one surface with no union seam."""
    x = Vector((1.0, 0.0, 0.0))
    rings = []
    for p, t, w, fd in stand_rings():
        v = t.cross(x)                 # u x v = t, so stack() stays outward
        pts = blade_pts(w / 2, BLADE_T / 2 * fd, EDGE_R, 0.0)
        rings.append([bm.verts.new(p + x * u + v * vv) for u, vv in pts])
    stack(bm, rings)

bm = bmesh.new(); build_stand_j(bm)
stand = finish("stand", bm, [mat_alu, mat_dark])
# The cord passes through the wing; the hole is a circle on the raked face, so its
# axis is that face's normal -- a +Y bore would read as an ellipse from behind.
PWR_N = Vector((0.0, math.cos(BEND_END), math.sin(BEND_END)))
PWR_P = Vector((0.0, arm_y(PWR_INLET_Z) + BLADE_T / 2 / math.cos(BEND_END),
                PWR_INLET_Z))
cut(stand, lambda bm: cyl_axis(bm, PWR_P, PWR_N, PWR_HOLE_R, -30.0, 20.0, 64, 0),
    "stand_power_hole")

# ---------------------------------------------------------------- rear door, button, sockets
def conforming_plate(name, cx, cz, w, h, r, off0, off1, mat):
    bm = bmesh.new()
    # edge=24: 4 mm chords, so the 0.11 mm seam band stays above the dome along
    # the 100 mm straight edges instead of sinking and fading mid-span.
    pts = plan(w / 2, h / 2, min(r, min(w, h) / 2 - 1e-4), edge=24)
    def rv(off):
        return [bm.verts.new((cx + px, surface_y(cx + px, cz + py) + off, cz + py))
                for px, py in pts]
    stack(bm, [rv(off0), rv(off1)], 0)
    tri_caps(bm)
    return finish(name, bm, [mat])

# A tight 0.45 mm shadow line, not a 1.1 mm black border: the 934 photo shows the
# door as a hairline rounded-rect outline beside the blade.
door_seam = conforming_plate("ram_door_seam", -RAM_XB, RAM_Z, RAM_W + 0.9, RAM_H + 0.9,
                             10.0, -0.045, 0.03, mat_dark)
door = conforming_plate("ram_door", -RAM_XB, RAM_Z, RAM_W, RAM_H, 9.0,
                        0.03, 0.11, mat_alu)

def add_ram_button():
    # Release slot on the body just inside the top rim of the blade's hole; iFixit
    # reaches it through the hole. A 4.5 x 2.5 dark slot, not an oval button.
    bm = bmesh.new()
    cz = RAM_BTN_Z
    pts = plan(RAM_BTN_W / 2, RAM_BTN_H / 2, RAM_BTN_H / 2 - 0.2, seg=8, edge=2)
    stack(bm, [[bm.verts.new((px, surface_y(px, cz + py) + off, cz + py))
                for px, py in pts] for off in (-0.02, 0.06)], 0)
    return finish("ram_button", bm, [mat_dark])

ram_button = add_ram_button()

def add_port_details():
    bm = bmesh.new()
    for _n, xb, w, h, _r, _d in PORTS:
        cx = -xb
        y = surface_y(cx, PORT_Z)
        if _n.startswith("usb-a"):
            box(bm, (cx, y - 1.7, PORT_Z), (10.5, 1.8, 1.05), 0)
        elif _n.startswith("usb-c"):
            box(bm, (cx, y - 1.5, PORT_Z), (5.4, 1.4, 0.7), 0)
        elif _n == "ethernet":
            box(bm, (cx, y - 2.1, PORT_Z), (11.0, 2.0, 8.5), 0)
        elif _n == "headphone":
            box(bm, (cx, y - 2.4, PORT_Z), (3.6, 1.4, 3.6), 0)
    return finish("port_details", bm, [mat_port])

port_details = add_port_details()

def add_power_inlet():
    # C7 socket on the body, seen through the blade's hole: a light grey plate with
    # two dark slots. (The 44 mm disc + black T + pins read as a socket floating in a
    # tunnel; the real inlet is a small D-shaped face.)
    bm = bmesh.new()
    cz = PWR_INLET_Z

    def plate(w, h, rr, offs, mi, dx=0.0):
        pts = plan(w / 2, h / 2, rr, seg=8, edge=2)
        stack(bm, [[bm.verts.new((dx + px, surface_y(dx + px, cz + py) + off,
                                  cz + py)) for px, py in pts] for off in offs], mi)

    plate(40.0, 32.0, 10.0, (0.02, 0.10), 0)
    for dx in (-6.0, 6.0):
        plate(4.5, 10.0, 1.6, (0.10, 0.14), 1, dx)
    return finish("power_inlet", bm, [mat_inlet, mat_port])

power_inlet = add_power_inlet()

def add_power_button():
    # Flush alu saucer with the symbol etched light; the saucer itself is the body's
    # own alu after the cut, so only the glyph is geometry here.
    bm = bmesh.new()
    cx, cz = -POWER_BTN_XB, POWER_BTN_Z
    xz_annulus(bm, cx, cz, 4.0, 4.35, surface_y, (-0.30, -0.27), 48, 0)
    b = [(cx - 0.35, cz - 0.4), (cx + 0.35, cz - 0.4),
         (cx + 0.35, cz + 5.5), (cx - 0.35, cz + 5.5)]
    stack(bm, [[bm.verts.new((x, surface_y(x, z) + off, z)) for x, z in b]
               for off in (-0.30, -0.27)], 0)
    return finish("power_button", bm, [mat_inlet])

power_button = add_power_button()

# ---------------------------------------------------------------- etched port icons
def add_icons():
    bm = bmesh.new()
    P = {n: -xb for n, xb, *_ in PORTS}
    IZ = PORT_Z + 11.5                       # etched marks sit above the openings
    def yb(x, z):
        y = surface_y(x, z)
        return y - 0.30, y + 0.06
    def rect(cx, cz, w, h):
        y0, y1 = yb(cx, cz)
        xzrect(bm, cx, cz, w, h, y0, y1, 0)
    # headphone: a ring
    hx = P["headphone"]
    xz_annulus(bm, hx, IZ, 1.45, 2.1, surface_y, (-0.30, 0.06), 32, 0)
    # USB trident above the four USB-A
    ux = (P["usb-a1"] + P["usb-a4"]) / 2
    rect(ux, IZ - 0.5, 0.55, 3.4)
    rect(ux - 0.75, IZ + 0.5, 1.4, 0.55)
    rect(ux + 0.75, IZ + 0.5, 1.4, 0.55)
    rect(ux, IZ - 2.1, 1.5, 1.5)
    # Thunderbolt bolt above the USB-C pair
    bx = (P["usb-c1"] + P["usb-c2"]) / 2
    bolt = [(bx + 0.4, IZ + 1.7), (bx - 1.1, IZ - 0.3), (bx - 0.1, IZ - 0.3),
            (bx - 0.5, IZ - 2.6), (bx + 1.1, IZ - 0.5), (bx + 0.1, IZ - 0.5)]
    y0, y1 = yb(bx, IZ - 0.5)
    xzpoly(bm, bolt, y0, y1, 0)
    # Ethernet: square outline
    ex = P["ethernet"]; ez = IZ - 0.8
    rect(ex, ez + 1.5, 4.0, 0.55); rect(ex, ez - 1.5, 4.0, 0.55)
    rect(ex - 1.72, ez, 0.55, 3.6); rect(ex + 1.72, ez, 0.55, 3.6)
    return finish("port_icons", bm, [mat_dark])

icons = add_icons()

# The glass, bezel, chin, camera and mark join the shell, so the enclosure the gate
# measures is 650 x 44 x 448 rather than a 43 mm shell behind a separate 0.9 mm front.
# The display stays its own object: joining it into the body drops its UV map (the
# joined object's active UV layer is the body's, and the body has none), so the
# wallpaper samples UV (0,0). (The stand and the rear add-ons stay separate.)
def join_into(target, objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = target
    with bpy.context.temp_override(active_object=target, object=target,
                                   selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    target.name = "body"

join_into(body, [body, bezel, chin, cam_ring, cam_lens, chin_logo])

# ---------------------------------------------------------------- dome shading normals
# The back is a scaled rounded rectangle, so its exact normal is constant along each
# straight side and turns through the 22 mm corner arcs; on a near-mirror metal that
# reads as four flat quadrants meeting in an X. The surface stays as measured; the
# shading normal comes from the same profile with the boundary radius smoothed in
# theta (8 deg), which spreads the corner turn without touching the silhouette.
_DN = 1440
_DTH = [2 * math.pi * i / _DN for i in range(_DN)]
_DBR = [boundary_radius(math.cos(t), math.sin(t)) for t in _DTH]
_DSIG = math.radians(8.0) / (2 * math.pi) * _DN
_DK = int(3 * _DSIG)
_DKERN = [math.exp(-0.5 * (k / _DSIG) ** 2) for k in range(-_DK, _DK + 1)]
_DSUM = sum(_DKERN)
_DKERN = [k / _DSUM for k in _DKERN]
_DBS = [sum(_DBR[(i + k) % _DN] * w for k, w in zip(range(-_DK, _DK + 1), _DKERN))
        for i in range(_DN)]

def smoothed_boundary(theta):
    u = (theta % (2 * math.pi)) / (2 * math.pi) * _DN
    i = int(u); f = u - i
    return _DBS[i % _DN] * (1 - f) + _DBS[(i + 1) % _DN] * f

def dome_shading_normal(x, z):
    e = 0.6
    def h(xx, zz):
        r = math.hypot(xx, zz - ZC)
        if r < 1e-6:
            return BODY_D
        s = min(r / smoothed_boundary(math.atan2(zz - ZC, xx)), 1.0)
        return EDGE_T + (BODY_D - EDGE_T) * (1 - s * s) ** DOME_P
    n = Vector((-(h(x + e, z) - h(x - e, z)) / (2 * e), 1.0,
                -(h(x, z + e) - h(x, z - e)) / (2 * e)))
    n.normalize()
    return n

def soften_dome_normals(obj):
    me = obj.data
    loopnorm = []
    changed = 0
    for l in me.loops:
        cn = l.normal.copy()
        v = me.vertices[l.vertex_index]
        if cn.y > 0.5 and v.co.y / MM > EDGE_T + 0.5:
            loopnorm.append(dome_shading_normal(v.co.x / MM, v.co.z / MM))
            changed += 1
        else:
            loopnorm.append(cn)
    me.normals_split_custom_set(loopnorm)
    me.update()
    print(f"REPORT dome_normals={changed}")

soften_dome_normals(body)

# IT Home's 379 side shot is the machine in its reclined press pose, not an
# upright body with a forward foot: pose the body (and every part cut into it)
# about the hinge. The stand stays flat on the floor.
piv = Vector((0.0, HINGE_Y * MM, HINGE_Z * MM))
R = (Matrix.Translation(piv) @ Matrix.Rotation(-BODY_TILT, 4, 'X')
     @ Matrix.Translation(-piv))
for o in sc.objects:
    if o.type == 'MESH' and o.name != "stand":
        o.matrix_world = R @ o.matrix_world

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
blo, bhi = bbox([body])
bdims = [(bhi[i] - blo[i]) / MM for i in range(3)]
print(f"REPORT body_mm=({bdims[0]:.2f}, {bdims[1]:.2f}, {bdims[2]:.2f}) "
      f"z={blo[2]/MM:.2f}..{bhi[2]/MM:.2f}")
# The body's own frame is what carries the 650 x 44 x 448 spec; the posed AABB
# above is longer/deeper by the 12 deg recline. Check both.
lv = [v.co for v in body.data.vertices]
llo = [min(v[i] for v in lv) * 1000.0 for i in range(3)]
lhi = [max(v[i] for v in lv) * 1000.0 for i in range(3)]
ldims = [lhi[i] - llo[i] for i in range(3)]
print(f"REPORT body_local_mm=({ldims[0]:.2f}, {ldims[1]:.2f}, {ldims[2]:.2f}) "
      f"z={llo[2]:.2f}..{lhi[2]:.2f}")
llo_w, llo_h = LOGO_SIZE
print(f"REPORT logo_mm=({llo_w:.2f}, {llo_h:.2f})")
print(f"REPORT back_logo_mm=({BACK_LOGO_W:.1f}, {BACK_LOGO_W * llo_h / llo_w:.1f}) "
      f"z_centre={BACK_LOGO_Z:.1f}")
if (abs(ldims[0] - BODY_W) > 0.2 or abs(ldims[1] - BODY_D) > 0.2
        or abs(ldims[2] - BODY_H) > 0.2):
    raise RuntimeError(f"body local envelope drift: {ldims}")
if abs(lo[2] / MM) > 0.1 or not (516.0 < hi[2] / MM < 521.0):
    raise RuntimeError(f"assembly height drift: {lo[2]/MM:.2f}..{hi[2]/MM:.2f}")
if abs(llo_w - 24.6) > 0.4 or abs(llo_h - 30.3) > 0.6:
    raise RuntimeError("chin logo size drift")

if NORENDER:
    print("REPORT norender=done")
    sys.exit(0)

# ---------------------------------------------------------------- studio
# The other rigs in this folder bottom out at 0.02, which reads as grey clouds on
# this machine's 650 mm satin dome: the back reflects the whole studio at once.
# A bright cyc (bottom 0.30) plus satin 0.42 aluminium is the product-photo look.
w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB"); mapr = nt.nodes.new("ShaderNodeMapRange")
mapr.inputs["From Min"].default_value = -0.45
mapr.inputs["From Max"].default_value = 0.45
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.30, 0.30, 0.31, 1)
mid = ramp.color_ramp.elements.new(0.55); mid.color = (0.50, 0.50, 0.52, 1)
ramp.color_ramp.elements[-1].position = 1.0
ramp.color_ramp.elements[-1].color = (0.60, 0.60, 0.62, 1)
nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])

WORLD, SUN = 1.35, 0.16
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
fb.inputs["Base Color"].default_value = (0.16, 0.16, 0.165, 1.0)
fb.inputs["Roughness"].default_value = 0.62
fb.inputs["Specular IOR Level"].default_value = 0.20
floor.data.materials.append(fmat)

cd = bpy.data.cameras.new("Cam"); cd.clip_start = 0.01; cd.clip_end = 100
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x = sc.render.resolution_y = 1200
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = "Standard"
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 256
sc.cycles.use_denoising = True

def frame(off, ctr, half, lens=110, fill=0.62):
    # 110 mm: the IT Home references are long-lens product shots. At 52 mm the near
    # display edge projects ~30 px ahead of the narrow foot, which reads as a display
    # overhanging a too-small base -- a projection error, not a geometry one.
    off = Vector(off).normalized()
    d = 2 * half / fill * lens / cd.sensor_width
    cd.lens = lens
    loc = Vector(ctr) + off * d
    cam.location = loc
    cam.rotation_euler = (Vector(ctr) - loc).to_track_quat('-Z', 'Y').to_euler()

CTR = (0.0, 0.09, 0.258)
HALF = 0.34
VIEWS = {
    "front":      dict(off=(0.0, -1.0, 0.045), ctr=CTR, half=HALF, fill=0.84),
    "back":       dict(off=(0.05, 1.0, 0.06), ctr=CTR, half=HALF, fill=0.84),
    # Flat-on back close-ups catch almost no specular; +EV per view, not a
    # brighter world (front/chin already clip). Mac Pro's preview-lattice precedent.
    # The close-up EVs went up ~0.07 stop when the aluminium roughened to 0.56:
    # it spreads the same energy, so the old EVs left the p99.9 under the 0.85 floor.
    # The 110 mm pass narrowed the sampled world gradient, so the flat views lost
    # their brightest 0.1%; the EVs below are re-measured, the world is untouched.
    "hero":       dict(off=(0.70, -1.0, 0.30), ctr=CTR, half=HALF, fill=0.70, exp=0.24),
    "hero-back":  dict(off=(0.72, 1.0, 0.32), ctr=CTR, half=HALF, fill=0.74, exp=0.25),
    "side":       dict(off=(-1.0, -0.02, 0.05), ctr=(0.0, 0.045, 0.258), half=0.31, fill=0.80),
    "chin":       dict(off=(0.16, -1.0, 0.14), ctr=(0.0, 0.0, 0.098), half=0.085, fill=0.90, exp=0.38),
    "top-bevel":  dict(off=(0.10, -1.0, 0.22), ctr=(0.0, 0.0, 0.497), half=0.080, fill=0.90, exp=0.20),
    "ports":      dict(off=(0.05, 1.0, 0.08), ctr=(0.183, 0.006, 0.150), half=0.100, fill=0.90, exp=1.52),
    "power":      dict(off=(0.16, 1.0, 0.05), ctr=(0.0, 0.030, 0.136), half=0.072, fill=0.92, exp=0.54),
    "ram-door":   dict(off=(0.10, 1.0, 0.04), ctr=(0.0, 0.030, 0.202), half=0.095, fill=0.92, exp=0.58),
    "vents":      dict(off=(-0.22, 1.0, 0.10), ctr=(0.0, 0.028, 0.257), half=0.075, fill=0.92, exp=0.59),
    "stand":      dict(off=(0.85, 0.70, 0.16), ctr=(0.0, 0.045, 0.150), half=0.190, fill=0.85, exp=0.11),
}
for name, v in VIEWS.items():
    if ONLY and name not in ONLY:
        continue
    frame(v["off"], v["ctr"], v["half"], fill=v.get("fill", 0.62))
    sc.view_settings.exposure = v.get("exp", 0.0)
    sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"REPORT rendered={name}")

# ---------------------------------------------------------------- export
for o in sc.objects:
    o.select_set(o.type == 'MESH' and o is not floor)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "imac27.glb"),
                          export_format='GLB', export_apply=True, use_selection=True)
print(f"REPORT glb_bytes={os.path.getsize(os.path.join(OUT, 'imac27.glb'))}")
with open(os.path.join(OUT, "imac27.json"), "w") as f:
    f.write('{ "title": "iMac (27-inch, 2020)" }\n')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "imac27.blend"))
