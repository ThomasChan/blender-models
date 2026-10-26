---
name: blender-highpoly
description: Use when modelling a real object — a product, device, or piece of hardware — as a high-precision, high-poly or converted 3D asset in Blender, headless from the command line, or exporting .glb/.gltf for the web or three.js — and when such an asset is shown apart, opened, lifted or exploded (分件) by whatever consumes it. Also use before hand-building a shipping product: the vendor may already ship an AR asset (USDZ) worth converting. Triggers on 建模, 建个模型, 3D 模型, 高精度模型, 高质量模型, 高多边形, 细节模型, high poly, high-poly, 低多边形, low poly, .blend, .glb, glTF, bpy, USDZ, AR 模型, 转换模型, 拆开, 分件, exploded view, or a request to model a specific physical thing.
---

# High-precision modelling in Blender

## Overview

Model the **object**, not just its silhouette. The target is an asset someone
can inspect — open the lid, look into a port, read the keycap legends, see the
display lit — and that is what "high-precision" means here: measured
dimensions, real cutouts, the details the eye actually uses to name the thing.
Triangle count is a budget, not the goal. The silhouette rule is the floor, not
the target. Every detail the eye will use to name the object gets a row in
`references/detail-inventory.md`; a detail that exists only in prose is not
built.

The order is the lesson this skill learned the hard way: a 362-triangle Mac
mini passed every silhouette check and was still **"认不出是 macmini"**; the
73,710-triangle version was the one called usable. Detail is not waste once the
asset will be looked at closely. See "The silhouette was right and the model
was unusable" below.

One rule overrides the rest:

**You cannot see the model from the script.** Every failure in this skill's
history printed nothing to the console and was obvious the moment someone
looked at a render. A geometry change that produces no error, no warning and a
valid file has still very likely broken something.

The same applies one level up, and this skill has been burned by it: **you
cannot see whether the thing is recognisable either.** No gate measures
identity.

## First: convert, or build?

Before writing geometry, check whether the vendor already modelled the
object. Apple, for instance, publishes an AR USDZ on Mac product pages at

```
https://www.apple.com/105/media/us/<product>/<year>/<uuid>/ar/<name>.usdz
```

(verified on Mac mini, iMac and MacBook Pro; `curl -I` the URL before
building a pipeline around it). An earlier MacBook Pro here was hand-built on
the premise that no Mac USDZ existed; one did. Treat "there is no vendor
asset" as a claim to test. A converted USDZ carries real panel
curvature, real port bores, the real anodised colour and a lit display with
the vendor's own wallpaper — detail a hand build reaches only by becoming a
different project. The iMac in `blender-models/` is 66,889 triangles
converted from Apple's asset; the hand-built MacBook Pro is 55,682 and took
far more work.

The silhouette-first, low-poly approach still holds for props, generic objects
and anything with no vendor asset. For a shipping product that has one,
**converting is the smaller job and the better asset** — and the work moves
from making geometry to deciding what to throw away.

**A vendor asset is a reference only for the exact thing it models.** The iMac
USDZ carries a desk set, but a 24-inch iMac's stand is not a reference for the
27-inch's — same family, same anodised finish, a different part. Pin model,
year and variant before the first line of geometry; a sibling product's part, a
photo, or a converted asset is a *hypothesis* about the reference, not the
reference. If the person who will judge the model can name the photo set, use
that set.

## Workflow

Write **one** build script. Sections in this order — the order is load-bearing,
because whatever exists when you `save_as_mainfile` is what the `.blend`
contains:

```
1. clean scene  (--factory-startup, then delete default cube/camera/light)
2. detail inventory (every visible detail names its field)  ← detail-inventory.md
3. REAL DIMENSIONS as constants, plain millimetres, converted once  ← craft.md
4. geometry        (bmesh; one object per material class)
5. materials
6. studio rig      (world, lights, camera, render settings)
7. render all preview angles
8. export .glb     (explicitly selected objects only)
9. save .blend     ← LAST. Saving earlier ships a file with no camera in it.
```

Step 2 is not a mood board. Each row must name a real object, material,
modifier, boolean or material value that carries the detail. If the row has no
field, add the field or drop the detail; do not leave it as prose and hope the
geometry pass remembers it.

If the source is photographs rather than a vendor asset, read
`references/reference-image.md` before the blockout: no millimetres without
calibration, one IoU per view, and a missing view is UNEVALUATED, not a pass.

## Converting a vendor asset

A conversion has a short, fixed list of decisions, and each one is somewhere
the asset can be silently wrong. `blender-models/imac/convert_imac.py` is the
worked example; read it beside this list.

- **Which objects ship.** AR assets are often a whole set: the iMac USDZ is
  the machine (81 meshes) + Magic Keyboard (28, 79,901 tris) + Magic Mouse
  (23, 11,732 tris). Select by a measured predicate — here, the only group
  wider than 500 mm and taller than 400 mm — **never by node name**. The
  names are hashes and they are not stable even between colour variants: the
  same machine group is `lXCRCNUacPtLDKW` in the blue asset and
  `lIVVxKJprGSeXRu` in the silver one.
- **A colour is a filename, not a separate asset.** One iMac UUID ships seven
  USDZs differing only in the trailing word (blue, green, pink, silver,
  yellow, orange, purple; all seven verified 200). Swapping that word and
  re-running is the whole change — but expect the node hashes to move with
  it.
- **Bake the hierarchy before deleting it.** The asset hangs off a root empty
  that carries the unit scale (0.01 m/unit). Join the meshes and apply
  `matrix_world` to the data *before* removing anything; delete first and the
  mesh ships 100× too big and 100× too far from the origin. That measures as
  54,758 mm and renders as a camera inside the machine — it looks like a
  geometry bug, not a transform one.
- **USD's "no diffuse" is black base colour plus transmission.** Apple writes
  the front glass as `transmission = 1` with a black diffuse. Principled tints
  transmitted light by Base Color, so black absorbs every ray: the whole front
  renders as a flat dark slab, and edge-on the panel is a white sheet. Both
  read as design decisions. Rewrite only materials matching
  `Transmission Weight > 0 and max(Base Color) == 0` to a white base — that
  leaves the camera lens and the smoked Apple mark their own colours. The same
  trap exists in three.js, which is why the fix belongs in the asset, not the
  viewer.
- **One object, or named parts — pick one.** Join to a single named object
  when the gate or the consumer needs an enclosure (81 anonymous meshes have
  none), as the iMac does. Keep and rename the parts when the consumer
  animates or explodes them; a join destroys the names, and hashes are not
  names.
- **Check the shading arrived.** Blender's USD importer carries
  `primvars:normals` through as custom split normals (132/132 meshes on the
  iMac), so this asset needs none of the crease repair a third-party
  converter's file does. Verify; do not assume it either way.
- **Different variants of the same product can differ in size.** The blue
  iMac exports at 547.59 × 177.20 × 460.93 mm and the silver at
  548.86 × 177.08 × 462.34 — identical 46,742 verts, 66,889 tris and 81
  meshes, and the per-axis ratios differ (1.0023, 1.0031, 0.9993), so it is
  a re-author, not a scale. The rear housing itself is 547.57 wide in blue
  and 548.84 in silver. Before touching the converter, compare counts and
  per-mesh positions like for like; then widen `--tol` for that asset and
  write down that the tolerance is for the vendor's own spread.

Then run the same export gate, on the same studio rig. Conversion changes
where the model came from, not what "finished" means.

## The traps

Each of these was hit by a competent agent that had already built a passing
model. They are the reason this skill exists.

### A mixed unit builds a wrong-sized model and reports nothing

`CORNER_R - 1.5` — millimetres subtracted from a metre-valued constant —
produced a negative corner radius and a 3 m model. It built clean, exported
clean, and passed the checks the build made on itself. Blender has no units: a
number is a number, and no stage of the pipeline can notice a mixed one.

The same trap has a second form, on the camera: `camera.data.lens` is in
**millimetres** by definition while `clip_start`, `clip_end` and
`dof.focus_distance` are in **scene units**, on the same object. A focal length
set to `0.05` for a metre-scale scene renders the subject a few pixels wide and
raises nothing. `bpy.md` has the table.

Keep the constants plain millimetres and convert at the single point of use
(`craft.md` shows the shape). Nothing catches the geometry form except
re-importing the finished file and measuring it; nothing catches the camera form
except looking at the render.

### Light power must scale with the subject

Blender is unitless and a 13 cm object in a 3 m scene gets a room-sized rig.
220 W area lights on a 127 mm subject render pure white — roughly 20× too hot,
and the failure looks like a broken material, not a broken light.

- **Preferred: use `SUN` for key and fill.** Sun energy is irradiance (W/m²) —
  no distance falloff, so the same single-digit key lights a 13 cm product and a
  13 m building identically. Scale-free, one less thing to get wrong.
- If you want `AREA`/`POINT` (softer, better falloff), derive the wattage:
  `watts ≈ 100 × (subject_size / 1 m)²`. A 13 cm subject gets single-digit
  watts. Retune by looking at the render, but start in the right decade.

### A white subject is exposed with the sun, not the world

A rig that is right for a metal machine is too hot for white plastic. The
accessories' white keycaps and mouse top reused the iMac's cyc unchanged —
world 1.45 and `SUN` 0.16 — and the white diffuse landed at world 0.84 + sun
0.37 ≈ **1.2**: the keyboard top clipped 3.4%, the mouse top 14.9%, the mouse
close-up 34.9%. Whole faces lost their shading and read as flat white cut-outs.

The obvious lever is wrong. Lowering the world dims the aluminium, which is
lit almost entirely by the world and has no diffuse to spare. Cut the **sun**
instead — it is what the white diffuse is made of — and narrow its angle as the
energy drops (0.16 → 0.04, 12° → 6°) so the metal keeps a concentrated
specular glint. Result: clipping ≤0.11% across all 12 frames, p99.9 highlight
0.886–0.945 against the gate's 0.85 floor. Read the subject first: which
surfaces are white diffuse, which are metal, and which light feeds each.

### A protrusion reads as "glued on" above ~2% of body height

Ports, buttons and connectors stop looking like part of the object and start
looking like bricks stuck to it. Measured on a 50 mm-tall case:

| Proud by | Reads as |
|---|---|
| 1.5 mm (3% of height) | blocks glued on ✗ |
| 0.4 mm (0.8%) | an inset port strip ✓ |
| 0.15 mm (0.3%) | an inset port strip ✓ |

Rule: cap protrusions at **≈1% of the object's smallest dimension**, or recess
them. Two independent builds converged here from opposite directions.

### The silhouette was right and the model was unusable

The low-poly premise — model the silhouette, and if it reads at thumbnail size
more detail is waste — is necessary and **not sufficient**, and the gap is
where the worst outcome in this skill's history lives.

A 362-triangle Mac mini was built to the letter of this file: 127 × 127 × 50 mm,
25 mm plan corners measured off Apple's own geometry rather than eyeballed, ports
at their real apertures, the wall profile followed around the corner arc, the
export gate green on all four views. The verdict from the person who asked for it
was **"认不出是 macmini"** — unrecognisable — against a 73,710-triangle asset of
the same machine that the same person called the usable one.

Everything the gate could see was correct. Nothing in the pipeline could see the
one thing that decides this, and neither could the author.

The leading explanation, and it is **not yet tested**: identity for this class of
object comes from a *marking*, not from an outline. A rounded square box is the
silhouette of a dozen small computers; what names a Mac mini is the **Apple logo
on the top face**, and the low-poly build had none. Under that reading the rule
is: after the silhouette reads, ask **what does the eye actually use to name this
thing?** If the answer is a marking — a logo, a badge, a distinctive face, a
control layout — that marking is the cheapest identifying geometry in the whole
model and it belongs in it whether or not it touches the outline. A logo is a
handful of triangles; a rim chamfer is dozens, and it identifies nothing.

Two habits follow, and neither is optional:

- **Show it to a human before calling it done**, at the size they will use it.
  "Recognisable" is not a property the author can assess, any more than exposure
  is — the same reason this file already says to open the render instead of
  trusting the numbers.
- **Do not promise a triangle budget is the win.** "200× fewer triangles and it
  reads the same" was written into `craft.md` on the strength of the author's own
  eye and it was false. A face count is a cost, not a result.

### Moving geometry can bury geometry, silently

In that same build, sinking the ports to fix the above pushed a 4 mm-deep LED
box 0.1 mm *inside* the 5 mm shell. Nothing errored; the LED simply stopped
existing visually.

**Re-render after every change that moves anything along the camera axis, and
look at the render.** Cheap, and it is the only detector this class of bug has.

### A decal on a curved wall has to follow the curve

A port plate is two triangles — but only where the wall under it is flat. The
Mac mini's plan corners have a 25 mm radius, so its wall is straight only for
`|x| ≤ 38.5 mm`. The power inlet sat at `x −56.5…−43.5` on the plane
`y = 63.5` while the arc had already pulled the wall back to **55.9 mm**, so a
black rectangle hung ~3 mm off the corner — outside the silhouette, and the
first thing the eye found in the render.

You cannot dodge it by moving the port inboard: the real connector complement
(13 + 16 + 15 + 3×8.9 mm) does not fit in 77 mm of flat wall, and Apple's own
ports run to `x = −45`, inside the arc. Follow the profile — sample the arc at
~3 mm (a 3 mm chord on r = 25 sags 0.05 mm, well inside a 0.15 mm standoff) and
keep flat spans at a single quad, or every port pays for subdivision it does
not need.

### A reference for the wrong variant is worse than no reference

The 2020 27-inch iMac's stand was first built from the **24-inch** iMac's
converted USDZ — same family, same anodised finish, a different part. Eight
rounds of geometry went into correcting a shape measured against the wrong
object before the person stopped the work: "先给我找对支架模型参考" (find the
right reference first). The 27-inch stand is one 8 mm sheet bent into a J; the
24-inch one is not.

Pin model, year and variant before the first line of geometry. A vendor asset,
a photo, or a sibling product is a **hypothesis** about the reference, not the
reference. When the person who will judge the model names a photo set, that set
is the reference; ask for it before building.

### Shading is not shape — trace the outline

A width step was "corrected" more than once off a shadow band in a phone photo:
"你好像是把阴影错误以为是不等宽了" (you mistook the shadow for a width
change). At thumbnail size a 2 mm step and a soft shadow are the same value.

- Build the comparator at the **first** shape complaint, not after several:
  same camera position and focal length as the reference, subject height
  normalised, mirrored when the reference is from the other side. Then **trace
  the outline you believe** onto the comparison. The person asked for exactly
  this ("你自己在特定角度截图做对比", "把你认为的形状描边描出来") before the
  harness existed; the method was right the round it was offered.
- Turn the silhouette into a number: band the axis the person named — width per
  5 mm of height, plan width per 20 mm of depth — and print the table. A
  disagreement that can be printed ends the argument.

### A swept section is continuous only if its seam is

The J stand is lofted from 41 rings. Foot, bend and arm each carried their own
width schedule, and the schedules met at 196 → 153 mm: a C0 break at the seam.
The envelope did not move — 196.00 × 203.42 × 298.60 mm before and after — and
every gate stayed green. What changed was a pair of wings visible only from
behind: "从背面看它应该是一个梯形" (from the back it should be one trapezoid).
The only numeric tell was the volume drop, 607,610 → 579,212 mm³, exactly the
two wings.

- For a one-piece read, adjacent sections' width and thickness must be **equal
  at the seam** (and ideally agree in slope). Audit the first and last entry of
  every schedule; that is where seams live.
- Think in the **flat blank**: a bent sheet is cut in plan first and bent
  second. The trapezoid is a one-line plan taper, not a correction applied
  inside the bend.
- Add a banded profile line to the build report — width per z band, plan width
  per y band. The AABB is invariant to exactly this failure.

### A through-hole is not open until you can see through it

The stand's Ø66 cable bore was cut clean through and still read as opaque: a
previous round had sunk a Ø64.8 disc into it after reading a highlight in a
photo as a flush plug. "你现在不是开孔状态，至少我看起来是不透明的" (it doesn't
look open to me). Removing the disc left the 8 mm bore wall and the C7 inlet
75 mm behind as the depth cue.

- Judge a hole by what a render shows through it, not by the boolean's success.
- Cables, plugs and other accessories are **scene, not product**. When a
  low-resolution photo reads either way, take the functional reading — a hole
  is a hole — and let the person override it.

### Separate objects interpenetrate with every per-object check green

The stand's shoulder passed through the body's vent slots. Manifold, n-gon and
envelope checks cannot see it: each mesh is valid on its own. The person found
it — "穿模了，把散热口穿模了" — and the stand and the vents are two independent
objects.

Inter-object clearance is a measurement: the gap between the stand and the vent
bank, between the shoulder and the back shell. Put it in the build report beside
the envelope.

### A change that does not move the render is the wrong change

Not a subtle one — the *wrong property*. The studio floor's base colour went
0.09 → 0.055 → 0.035 (2.6× darker) and the render did not move, because at a
grazing angle the floor is a mirror: its brightness comes from the sky it
reflects, and albedo is not an input to that pixel. `Specular IOR Level` was
the lever, and one controlled render settled it.

**Two changes to the same property with no visible effect: stop, and A/B a
different property.** A third nudge slightly further along a dead axis costs the
same render and teaches nothing. Every rendered value has one dominant input;
guessing which is cheap only if you check after the first guess.

**The same rule applies one level up, to a shape verdict.** If the person who
asked says "still wrong" twice after two fixes, the premise is wrong — the
reference, the view, or the property being measured — not the last parameter.
Stop editing geometry and re-establish what is being compared.

### Only constant material values survive glTF

Procedural textures, `ColorRamp`s and `Mix Shader`s are dropped by the
exporter. Bake, or use flat colours plus geometry.

And a metal needs **both** an environment and the right engine: EEVEE can only
show a reflection it has been handed, so without light probes a metal renders
flat grey — which reads as a broken material and sends you tuning colours that
were never wrong. Use Cycles for anything metallic. See `craft.md`.

### Measure in the space that ships

`obj.dimensions` / `obj.bound_box` are local and ignore modifiers. On the glTF
side, accessor `min`/`max` are **mesh-local** — the exporter writes the Y-up
conversion into node transforms, so a raw parse of accessors gives the wrong
number. Either walk the node hierarchy and transform real vertices, or let
Blender import the file and measure `matrix_world`-transformed bounds. Both
work; reading accessors directly does not.

### Export the product, not the studio

The glTF exporter takes the whole scene unless told otherwise. A 6 m ground
plane becomes 6000 mm of bounding box in the asset. Select the product meshes
and pass `use_selection=True`.

### The asset gets shown in a pose you did not model

Everything above assumes the model is seen whole, from outside, in the pose you
built it in. The Mac mini in this file's history is the counter-example: it went
into a page whose settings panel *takes it apart* — the shell lifts, the base
drops to the bottom of an exploded stack — and the asset had been authored for
exactly one pose, lid shut. Three defects came out of the same asset, and not
one of them was a modelling error in the pose it was built for:

| What the person saw | What it actually was |
|---|---|
| a black slab hanging out of the aluminium | the liner is 10% **taller than the shell it lines** (47.0 against 42.5 mm) and 3.8 mm below the shell's middle — free while shut, and past the shell's bottom edge the moment the shell lifts |
| the base as a hole with an outline round it | the base cover is a shell facing **down**; opened, it is looked at from above, the material culls the back face, and what is left is the housing's black floor showing through |
| the interior as silhouettes with no form in them | the occlusion atlas was baked **with the lid on**, so every interior part samples fully occluded |

So ask **which poses the asset will be shown in** — shut, open, hinged, lifted,
exploded, on its side — before the geometry exists. It is a one-line question
with a cheap answer then and an expensive one later; this one cost a debugging
session on an asset that had passed every gate this file gives you. When the
answer is "more than one pose":

- **Name every part, in the file, at build time.** Parts get found by name, and
  the names of a converted asset are opaque: the page's JS hardcodes
  `TJFYvIgzkMAsKoH` and `AeCrpVLtKBipayc` beside a comment reading "re-export the
  GLB and both names may move". That comment is the invoice for shipping an asset
  without names. One `lowercase-with-dashes` name per part costs nothing at build
  time and *is* the part's contract with whoever animates it.
- **A part hidden in one pose has to be designed for the pose that exposes it.**
  Ask what each part looks like with whatever stands in front of it taken away —
  and then whether it needs to be that shape at all, because the liner's overhang
  was only ever a free way to save a little geometry.
- **A shell gets looked at from both sides.** Verified at the file level on the
  two assets in `blender-models/`: the Blender-built one carries
  `doubleSided: true` on **3/3** materials, the converted Apple one on **0/15**.
  Single-sided is what the see-through-back failure is made of, and it does not
  look like a missing part — it looks like a **hole onto the page**, which reads
  as a bug in the viewer and sends you debugging the viewer. `bpy.md` has the
  flag and how to check it.
- **Before shrinking a part, check what it backs.** That same liner also stands
  behind the machine's ports and slots, so a footprint that shrinks opens two
  white holes in the back of the case (measured: hiding the mesh outright leaves
  the ports as holes onto the page). The overhang was fixed in the thin axis
  *only*, and the footprint was left alone because of this.
- **Do not fix a pose with a visibility toggle in the consumer.** `visible =
  open < 0.02` on the base cover was the earlier fix for the same hole, and it
  made the base transparent in the open pose instead. The real problem was one
  mesh trying to serve two contradictory readings; if a part has to be hidden to
  look right, the part is wrong.
- **Judge in the part's own frame.** Under yaw and tilt a world-space AABB
  inflates until the offender looks innocent; the liner's overhang was only
  measurable in the untilted machine frame (19.31…57.86 inside a shell of
  17.06…59.59). Same rule as "measure in the space that ships", one level down.

## Verify — this gate is not optional

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  --python-exit-code 1 \
  --python ~/.agents/skills/blender-highpoly/scripts/check-model.py -- \
  out/model.glb --expect 127,127,50 --max-tris 800 \
  --render out/hero.png --render out/ports.png
```

Add `--enclosure <part>` when the asset ships in a pose that is not the frame
the spec sheet describes. `--expect` is checked against the *enclosure* — by
default the largest object by **bounding-box volume** — and that default breaks
exactly there: an open lid's bbox (312.6 × 59.3 × 216.1 mm) is six times the body
it hinges on, so the gate measured an open lid against the closed spec sheet and
failed a model whose closed envelope was exact to 0.01 mm. Naming the part that
actually carries the envelope (`--enclosure base`) restores the check. This is
why "name every part" is worth doing at build time: the gate can only be pointed
at a name.

The verdict is three-state: `PASS` (exit 0), `FAIL` (exit 1), `UNEVALUATED`
(exit 2). A missing preview, an unreadable GLB or any other requested check that
could not run is UNEVALUATED, never PASS. Blender's `--python-exit-code 1` may
collapse 2 to 1, so read the printed `VERDICT` line. An UNEVALUATED run is not
a build you can report as done.

It re-imports the exported `.glb` — measuring what ships, not what you intended
— and fails loudly on tri budget, n-gon count, non-manifold edges, dimension
drift, missing materials, a render that came out black, one with no highlight
headroom left, and one with no highlight to speak of. It also measures the same
file a second time from its POSITION accessors, without bpy, and fails if the
two paths disagree on dimensions or triangle count. Re-running the same bbox
code would only confirm its own bug. Run it before you claim the model is done.

The accessor path reads uncompressed GLBs. A meshopt-compressed export keeps
no fallback data on disk, so that path cannot run and the verdict is
UNEVALUATED. Do not wave it through: measure it with a meshopt-capable decoder
(the repository's `scripts/visual-gate.mjs` does, before it renders) or gate an
uncompressed export.

Then **open every preview PNG and look at it.** Reading the numbers is not
looking. If you changed geometry after rendering, the renders are stale. The
gate checks exposure, not framing: a straight-on view framed with `half=0.085`
was 218 mm across a 279.5 mm keyboard and cut both ends off, with every number
green. Frame width is `2 × half / fill`; check it against the largest
dimension before rendering.

**When a stray triangle is somewhere it should not be, tag it by material.**
Give every non-body material a distinct saturated colour, screenshot once, and
read the offender's colour off the legend. Bounding boxes will not do it — a
tilted pose inflates them until every part looks innocent. Two traps: avoid a
grey tag (indistinguishable from bare aluminium, so it matches the whole body),
and read the tag from *one object per material*, since the importer splits a
mesh into one object per material and the last one assigned wins.

Both halves are required and neither substitutes for the other. The checker
cannot see an occluded LED or an ugly highlight. Your eye cannot see that 3.6%
of the frame is pure white — a blown render reads as "bright and clean", not as
a defect, and that is how a build shipped one while its author reported the
exposure as correct. `craft.md` has the target numbers.

### Assembly audit

A clean bounding box is not a clean assembly. When the asset is more than one
part, check the relationships the bbox cannot see:

- **Floaters.** Every mesh must touch, overlap or be contained by another.
  Sharing a bounding box is not contact.
- **Interference.** Look for unintended overlap, and keep a named `hidden_ok`
  allow-list for the overlaps that are deliberate (a liner inside a shell). An
  unnamed exception is a defect.
- **Contact / gap / contained.** Assert the intended relationship for each
  pair. "Close enough" is not a relationship.
- **AABB is a first pass only.** A rotated interface (an open lid at 100°) must
  be measured in its local interface frame; a world-space AABB inflates until
  the offender looks innocent. This is "measure in the space that ships" one
  level down.

Adapted from dsh-blender-plugin's `skills/blender-modeling/references/验收清单.md`
(BSD-3-Clause); see `THIRD_PARTY_NOTICES.md` at the repository root.

## Reference

| File | |
|---|---|
| `references/craft.md` | tri budgets, silhouette, bevels, shading, port sizing, studio setup |
| `references/detail-inventory.md` | pre-geometry detail list; prose-only detail is not built |
| `references/reference-image.md` | calibration, per-view IoU, and reference-photo traps |
| `references/bpy.md` | verified 5.2 API/CLI facts, sorted by the version they changed in |
| `scripts/check-model.py` | the export gate (PASS / FAIL / UNEVALUATED) |

## Common mistakes

| | |
|---|---|
| Guessing real-world dimensions | Look them up. A Mac mini is 127 mm square; a "127 mm" guess that is actually 120 is a visibly wrong asset. |
| Modelling one pose and shipping it into something that opens the model | The Mac mini's liner, base cover and interior all failed in a pose the asset was never checked in. Ask which poses it will be shown in, then look at every part in every one of them. |
| Letting the gate pick the enclosure on a posed asset | Its default is the largest bounding box, which an open lid wins by 6×, so `--expect` gets compared against the wrong part. Pass `--enclosure <part>`; the closed envelope is yours to assert in the build. |
| Building the inner loop of a ring by a different rule than the outer | The bridge becomes a bowtie: black wedges fanning across a flat panel, no error, no gate. Same function, two radii — see `bpy.md`. |
| Leaving parts named `TJFYvIgzkMAsKoH` and `AeCrpVLtKBipayc` | Whoever animates the model ends up hardcoding those strings, with a comment admitting they will move. Name every part at build time; it is free. |
| Assuming a documented API exists | Two claims that read perfectly plausible were false on the real binary. Check the build. |
| Trusting `blender --version` that the binary works | It passes through a broken symlink. Run a real script. |
| Rendering and not opening the image | A black frame is a valid PNG and a zero exit code. |
| Counting faces instead of triangles | A quad is 1 face and 2 triangles; only triangles matter to the GPU. |
| Hand-building a product that ships an AR USDZ | The vendor's mesh is free, real and more detailed than the build script will reach. Check `/105/media/us/<product>/…/ar/*.usdz` before writing geometry. |
| Selecting parts by node name in a converted asset | The names are hashes and move between exports — the same iMac group is `lXCRCNUacPtLDKW` in blue and `lIVVxKJprGSeXRu` in silver. Select by a measured predicate. |
| Blaming the converter for a size mismatch between vendor variants | Blue and silver iMac exports differ by 1.9 mm in width with identical topology. Compare counts and per-mesh positions before touching the code. |
| Reusing the previous subject's exposure | A rig is tuned to an albedo. This machine was 1.9× brighter than its sibling and clipped 21.4% of one frame. Re-sweep the world and the suns together. |
| Substituting a font for a brand wordmark | Snell Roundhand stood in for the Mac "hello" and is a different drawing — high-contrast calligraphy against a monoline looped script. The real strokes ship on the machine in `Hello.appex/…/Languages/en.json` (`"Macintosh 3D"`), and `Assets.car` has the rendered reference. Trace the vendor's own art before reaching for a lookalike. |
| Using a sibling product's part as the reference | The 24-inch iMac's stand is not the 27-inch's; part of a two-day rework measured a shape against the wrong object. Pin model, year and variant first. |
| Reading a width step off shading | A shadow band and a 2 mm step look identical in a phone photo. Trace the silhouette and band-measure it. |
| Treating "one piece" as a topology claim only | A single swept sheet can still break width at a seam, and the AABB will not show it. Equal widths at the seam, plus a banded profile table. |
| Calling a through-hole open without looking through it | A disc in the bore leaves the boolean valid and the hole plugged. The render has to show what is behind it. |
| Checking meshes but not the gaps between them | Separate valid meshes interpenetrate silently; measure clearances explicitly. |
