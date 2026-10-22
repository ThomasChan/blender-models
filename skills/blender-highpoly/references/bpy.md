# bpy cookbook — verified on Blender 5.2.2 LTS, macOS arm64

Everything here was run against the installed binary, not recalled. Where a
claim is version-dependent the version is stated. Re-verify anything
load-bearing against your own build — two claims that arrived from
documentation were already false (marked below).

## Invocation

```sh
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender   # capital B, inside the .app
"$BLENDER" --version
"$BLENDER" -b -E help          # the authoritative engine list for THIS build
```

```sh
"$BLENDER" -b --factory-startup --python-exit-code 1 --python build.py -- \
    --out ./out --width 127
```

| Flag | Why |
|---|---|
| `-b` / `--background` | no UI. Without it the process opens a window and a headless run hangs. |
| `--factory-startup` | ignore the user's `startup.blend`; the user's prefs must not change your geometry |
| `--python-exit-code 1` | **without this a Python exception still exits 0** and a broken build looks green |
| `--` | everything after it goes to your script, via `sys.argv` |

Read args in the script:

```python
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
```

### Put the binary on PATH with a wrapper, never a symlink

A symlink to `Blender` **breaks it**: Blender resolves `Contents/Resources/`
relative to `argv[0]`, so through `/opt/homebrew/bin/blender` it looks for
`/opt/homebrew/Resources` and dies with `Bundled Python not found`,
`No module named '_bpy_types'`, `couldn't find 'scripts/modules'`. Version
printing still works, so `blender --version` passing proves nothing.

```sh
cat > /opt/homebrew/bin/blender <<'SH'
#!/bin/sh
exec /Applications/Blender.app/Contents/MacOS/Blender "$@"
SH
chmod +x /opt/homebrew/bin/blender
```

## Environment

| | |
|---|---|
| Engine ids (5.2) | `BLENDER_EEVEE`, `BLENDER_WORKBENCH`, `CYCLES` — from `-E help`, not memory |
| EEVEE id history | `BLENDER_EEVEE` (≤4.1) → `BLENDER_EEVEE_NEXT` (4.2–4.5) → `BLENDER_EEVEE` (5.0+). Code written for 4.2–4.5 fails on 5.x and vice versa. |
| Bundled Python | 3.13.13 at `Contents/Resources/5.2/python/bin/python3.13`. `bpy` is importable **only** here. |
| `bpy.app.python_version` | **does not exist.** Use `sys.version`. |
| glTF exporter | `bpy.ops.export_scene.gltf` is available under `-b` with no `addon_enable` call. |

### Rendering headless on macOS

All three engines rendered correctly from a normal GUI Terminal session — EEVEE
included, which is the one widely reported as impossible headless. **Probe,
don't assume:** render a small still and check the pixels are not black. A black
EEVEE frame is the classic headless failure and it exits 0.

Rendering at all is not the same as rendering *correctly*. EEVEE runs headless
fine and still cannot show a metal reflection without light probes or
screen-space setup. Which engine to pick is a look decision — see `craft.md`.

```python
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 64
sc.render.resolution_x = sc.render.resolution_y = 900
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = "/abs/path/out.png"      # filepath lives on scene.render,
bpy.ops.render.render(write_still=True)       # render() has no filepath argument
sc.view_settings.view_transform = "Standard"  # 4.0+ defaults to AgX; Standard = literal colours
```

Check a render actually contains something by reading the PNG's mean luma — a
black image is a valid PNG and a zero exit code.

**`Image.pixels` is in the file's own encoding, not scene-linear.** For an
8-bit sRGB PNG it hands back raw bytes / 255. Verified by writing a PNG with
every byte at 128 and reading it back: `0.502`, not the linear `0.216`. So every
threshold in `check-model.py` and every number in `craft.md`'s exposure table is
an **sRGB display value**. Comparing one against a hand-computed linear
radiance (`albedo × irradiance / π`) shows a 2–3× gap that is not a bug in
either — it is the transfer curve.

### The camera mixes two unit systems on one object

Read off the installed build:

| Property | Default | Unit |
|---|---|---|
| `lens`, `sensor_width`, `sensor_height` | 50.0, 36.0, 24.0 | `CAMERA` — **millimetres, always** |
| `clip_start`, `clip_end` | 0.1, 1000.0 | `LENGTH` — scene units (**metres**) |
| `dof.focus_distance` | 10.0 | scene units (metres); lives under `.dof`, not on `Camera` |
| `ortho_scale` | 6.0 | unitless — scene units (metres) |

So `lens = 50` and `clip_start = 0.1` are both "correct defaults" and are two
orders of magnitude apart in intent. Setting a focal length of `0.05` because
your scene is in metres gives a 0.05 mm lens, and the subject renders a few
pixels wide. Nothing errors.

`unit_settings.system` does **not** change this — it is `METRIC` and `lens` is
still millimetres. Only a render or a look at the frame tells you the camera is
wrong; there is no geometric gate for it.

## Geometry

### Precise box with a rounded-square plan

```python
import bpy, bmesh, math
MM = 0.001
W = D = 127*MM; H = 50*MM

bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(W, D, H), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0, 0, H/2), verts=bm.verts)   # base sits on z=0

# vertical edges -> plan corner radius
vert_e = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-9]
bmesh.ops.bevel(bm, geom=bevel_geom(vert_e), offset=25*MM, offset_type='OFFSET',
                segments=6, profile=0.5, affect='EDGES', clamp_overlap=True)

bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
me = bpy.data.meshes.new("Body"); bm.to_mesh(me); bm.free()
```

```python
def bevel_geom(edges):
    """Bevel wants the edges AND their verts. A vert shared by two selected
    edges must appear ONCE or bevel raises
    'found the same (BMVert/BMEdge/BMFace) used multiple times'."""
    out = []
    for e in edges:
        out.append(e)
        for v in e.verts:
            if v not in out:
                out.append(v)
    return out
```

`bmesh.ops.bevel` signature, printed from the installed build:

```
bmesh.ops.bevel(bmesh, geom=[], offset=0.0, offset_type='OFFSET',
  profile_type='SUPERELLIPSE', segments=0, profile=0.0, affect='VERTICES',
  clamp_overlap=False, material=0, loop_slide=False, mark_seam=False,
  mark_sharp=False, harden_normals=False, face_strength_mode='NONE',
  miter_outer='SHARP', miter_inner='SHARP', spread=0.0,
  custom_profile=None, vmesh_method='ADJ')
```

- `offset_type` is a **string** here, not an int enum.
- **`affect` defaults to `'VERTICES'`** — bevel corners, not edges. Pass
  `'EDGES'` explicitly or nothing you expect happens.
- `segments` defaults to `0`.

### Two loops bridged index-to-index must start at the same corner

`bm.faces.new((a[i], a[j], b[j], b[i]))` joins loop *a* to loop *b* vertex for
vertex, so both loops have to be parametrised the same way. Build the inner one
by a different rule — a rectangle distributed by perimeter against an outer
rounded rect built corner-arc by corner-arc — and the bridge comes out a
**bowtie**: the quads cross each other and fan out from a point. On a silver
laptop deck those render as black wedges, because they are seen from behind and
catch no light. It builds clean, exports clean, and `recalc_face_normals` does
not touch it.

The fix is one function with two radii: a rectangle is
`rounded_rect(hw, hd, WELL_R≈4)` about an offset centre, and the phases then
match by construction. The symptom worth memorising: **straight-edged black
wedges fanning from a vertex across a flat panel** is a loop-phase bug, not a
normals or material bug. (A `rect_loop` helper whose docstring claims "the phase
does not show, because the two loops are coplanar" is how this one shipped.)

### After a bevel, stop selecting faces by coordinate

A bevel replaces each corner with a ring of thin faces, so **the face with the
highest average Z is no longer the top face** — it is a 0.57 mm-wide chamfer
fragment on the back rim. `inset_region` on that fragment threw vertices 2.7 mm
outside the shell and 0.5 mm above it, and the model still exported cleanly.

Select by **normal plus area** instead:

```python
top = max((f for f in bm.faces if f.normal.z > 0.9), key=lambda f: f.calc_area())
```

Any predicate of the form "the face at coordinate X" is fragile once bevels or
booleans have run. Prefer a predicate about the face's *shape and orientation*.

### Two APIs, two spellings for clamp

| | |
|---|---|
| `bmesh.ops.bevel(...)` | `clamp_overlap=` |
| `BevelModifier` (object modifier) | `use_clamp_overlap` — **`clamp_overlap` raises `AttributeError`** |

### Normals and shading

`mesh.use_auto_smooth` and `mesh.auto_smooth_angle` were **removed in 4.1**.
`Mesh.set_sharp_from_angle` **does not exist** — a plausible-looking claim that
never existed; the real options are:

- `bpy.ops.object.shade_smooth_by_angle(angle=..., keep_sharp_edges=True)`
- `bpy.ops.object.shade_auto_smooth(...)` — leaves a *modifier* in the stack that
  glTF ignores unless you export with `export_apply=True`
- do it by hand on the data API:

```python
me.attributes.new("sharp_edge", 'BOOLEAN', 'EDGE') if not me.attributes.get("sharp_edge") else None
def auto_sharp(mesh, angle_deg):
    bm = bmesh.new(); bm.from_mesh(mesh); bm.edges.ensure_lookup_table()
    sharp = set()
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            sharp.add(e.index)                       # boundary: keep crisp
        elif math.degrees(lf[0].normal.angle(lf[1].normal)) > angle_deg:
            sharp.add(e.index)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    for e in mesh.edges:
        e.use_edge_sharp = e.index in sharp
```

Measured: `shade_smooth_by_angle(30°)` and the hand-rolled version above produce
**byte-identical renders** (mean abs pixel difference 0.0000, max 0 on a 700×700
render). Either is fine; the operator is not broken. Pick the data API only if
you want to avoid operator context entirely.

## Import

A `.usdz` imports directly — it is a zip of USD, and the importer reads it:

```python
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath="/abs/asset.usdz")
bpy.context.view_layer.update()
```

The importer **keeps USD's transform hierarchy**: the asset arrives under a
root empty that may carry the unit scale (Apple's AR assets: 0.01 m/unit), and
object names are the USD prim names — hashes in a vendor export. That is why a
conversion bakes transforms before deleting the hierarchy and selects parts by
measurement rather than by name (`SKILL.md`, "Converting a vendor asset").

`primvars:normals` arrive as **custom split normals** (`mesh.has_custom_normals`
is `True`), so vendor shading survives the import. Check it rather than
assuming either way.

## Measuring

`obj.dimensions` and `obj.bound_box` are the bounding box times object scale —
they **ignore modifiers**, and `bound_box` is in **local space**. Measure the
evaluated object, and measure the whole scene, because decals and helper objects
change what you ship.

```python
bpy.context.view_layer.update()                 # or the numbers are stale
dg = bpy.context.evaluated_depsgraph_get()
for o in bpy.context.scene.objects:
    if o.type != 'MESH': continue
    ev = o.evaluated_get(dg)
    m = ev.to_mesh()
    m.calc_loop_triangles()                     # does NOT modify the mesh
    tris = len(m.loop_triangles)                # what the glTF actually carries
    faces = len(m.polygons)                     # a quad counts 1
    ngons = sum(1 for p in m.polygons if len(p.vertices) > 4)
    for c in ev.bound_box:
        w = o.matrix_world @ Vector(c)          # local -> world, do not skip
    ev.to_mesh_clear()
```

Ship-what-you-measure: `scripts/check-model.py` re-imports the exported `.glb`
rather than trusting the scene — a 6 m studio floor left in the export only
shows up on re-import.

### Reading a .glb without Blender

Accessor `min`/`max` are **mesh-local**. The Blender exporter writes the Z-up →
Y-up conversion into the *node transform*, so `accessor.max - accessor.min` is
the size of the mesh in its own space, before the node's rotation — it is not
the bounding box of the object in the scene. A 127×50×127 mm body reads as
`127 × 50 × 127` off accessors but is `127 × 127 × 50` in world space.

Walk the node hierarchy, compose the transforms down to each mesh, and
transform real vertex positions. Or hand the file to Blender and use
`matrix_world` as above, which is what `check-model.py` does.

### Boundary edges on re-import are usually not holes

A watertight mesh can report hundreds of boundary edges after a glTF round
trip: glTF has no sharp-edge concept, so the exporter writes **split normals**,
which duplicate vertices along every hard edge, and the importer does not weld
them back. Measured: a watertight 352-triangle body re-imported with 376
boundary edges and **zero** non-manifold edges.

So `boundary_edges` on an imported `.glb` is a diagnostic, not a verdict. Judge
watertightness on the source mesh, or look at whether the render has holes in
it. `check-model.py` reports the number and deliberately does not fail on it.

## Export

```python
for o in sc.objects:
    o.select_set(o.type == 'MESH' and o.name != "Floor")   # product, not studio
bpy.ops.export_scene.gltf(filepath="/abs/out.glb", export_format='GLB',
                          export_apply=True, use_selection=True)
```

- `use_selection=False` exports **everything** — lights, camera, floor. A 6 m
  ground plane becomes 6000 mm of wrong bounding box in the asset.
- `export_apply=True` applies modifiers. It does **not** bake object scale —
  apply transforms yourself (`bpy.ops.object.transform_apply(scale=True)`) or the
  asset arrives the wrong size in some viewers.
- There is no `axis_forward` / `axis_up` on the glTF exporter (those are FBX).
- **`doubleSided` is the inverse of `material.use_backface_culling`**, and
  Blender's default (culling off) exports `doubleSided: true`. glTF's own default
  is `false`, so the key is *omitted* rather than written as false — measured on
  the two assets in `blender-models/`: the Blender-built one has
  `doubleSided: true` on 3/3 materials and the converted Apple one on **0/15**,
  which is the whole of the "base cover renders as a hole" defect. A shell that
  will be looked at from behind needs culling off; a *converted* asset may have
  arrived with it on. Check the file, not the scene:
  ```sh
  python3 - <<'PY'
  import json, struct
  path = 'out/model.glb'                 # the exported file
  b = open(path, 'rb').read()
  j = json.loads(b[20:20 + struct.unpack('<I', b[12:16])[0]])
  print([(m['name'], m.get('doubleSided', False)) for m in j['materials']])
  PY
  ```
- Node and material names in the file are `obj.name` and `mat.name` — yours to
  choose. A consumer finds parts by name and has no other handle, so name them
  for what they are rather than accepting `Cube.004`.
- **A material is shared by default.** The exporter reuses one instance for every
  mesh that had it, so changing one part's material to fix a single mesh changes
  everything that used it. Check `mat.users` before editing in place, and clone
  when the change is about one part — the same trap applies on the consumer side,
  one level removed.
- Baking a node's rotation into its mesh (`mesh.transform(M)` around a pivot) is
  the deterministic way to ship a posed part: the exporter then has no transform
  to disagree with, and the part is still one named object an animator can rotate
  back. Build in the closed frame, rotate into the pose, export.
- On re-import the `sharp_edge` attribute is gone — glTF carries sharpness as
  **split normals**, and the importer splits the mesh into one object per
  material. Do not read `sharp_edges` off an imported `.glb` and conclude
  anything.

## Materials

```python
m = bpy.data.materials.new("Aluminium"); m.use_nodes = True
b = m.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.62, 0.62, 0.64, 1.0)
b.inputs["Metallic"].default_value = 0.85
b.inputs["Roughness"].default_value = 0.34
m.diffuse_color = (0.62, 0.62, 0.64, 1.0)   # what Workbench MATERIAL colour shows
```

- 4.0 renamed the sockets: `Subsurface`→`Subsurface Weight`,
  `Specular`→`Specular IOR Level`, `Transmission`→`Transmission Weight`,
  `Coat`→`Coat Weight`, `Sheen`→`Sheen Weight`, `Emission`→`Emission Color`.
- Only constant values survive glTF. Procedural textures, ColorRamps and Mix
  Shaders are dropped by the exporter.
- **Metallic without an environment renders flat grey.** See `craft.md`.
