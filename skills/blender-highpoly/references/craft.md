# Low-poly craft

The judgment calls, as opposed to the API. Read this before writing geometry.

## Budget

Triangles are the only currency the GPU spends. Faces are not — a quad is one
face and two triangles, so always count `loop_triangles`.

| Use | Budget | |
|---|---|---|
| background / instanced prop, seen at distance | 100–500 | |
| hero desk object, turntable on the web | 1k–5k | |
| detailed hero, close camera | 5k–50k | |
| AR Quick Look ceiling (USDZ) | ~100k | a ceiling, not a target |

For scale: the "Mac mini" this skill's example replaced was a **73,710-triangle
downloaded asset**.

**Its hand-built 352-triangle replacement was rejected as unrecognisable.** That
is the most important number in this file. 200× fewer triangles is not
automatically a win — it was bought here partly by dropping the Apple logo, and
the logo is what named the object. Read "The silhouette was right and the model
was unusable" in `SKILL.md` before aiming at the bottom of any row above.

Budget is a constraint on *where* you spend, not a target to fill. What it is
supposed to buy is **recognisability**, and no row in this table measures that.

## Silhouette first

Block the object at its real dimensions before any detail. Squint at the
render: if the outline does not identify the object, nothing else will rescue
it. But a correct outline does **not** mean the object is identified — that is
the one direction this rule does not cover, and it is the direction that has
actually cost a shipped model (`SKILL.md`). Necessary, not sufficient.

Detail lives *inside* the silhouette and earns its triangles in one of two
ways: it changes how the outline reads from the second-best angle, **or** it is
the thing that names the object. A logo is a handful of triangles and can be
the entire difference; a rim chamfer is dozens and identifies nothing.

Corollary: spend your triangles on **curvature and corners**, not flat faces.
A flat face is 2 triangles whether it is 1 mm or 100 mm across. A rounded
corner needs segments. This is why every object with a rounded-square footprint
is cheap and every object with a smooth dome is not.

## Dimensions come from the real object

Look them up, and **keep every constant a plain number of millimetres**,
converting to Blender's metres at the single point where geometry is made.
Storing metres in the constants is what produces the silent unit mix below.

```python
W = D = 127.0      # Mac mini M4 is 127.0 mm square, 50.0 mm tall
H = 50.0
CORNER_R = 25.0    # plan-view corner radius -- measured, not eyeballed (below)
MM = 0.001         # the ONLY conversion, and it happens here:

bmesh.ops.scale(bm, vec=(W * MM, D * MM, H * MM), verts=bm.verts)
```

### Some dimensions are not published — measure them off reference geometry

127 × 127 × 50 mm is a spec sheet number. The **corner radius is not**, and
eyeballing it off product photos got 18 mm, which is 28% too square and visibly
wrong next to the real thing. The fix is a measurement that does not care how
the reference mesh is tessellated: the **support function** `h(θ) =
max(v · d̂)` over the vertices. It needs no vertex correspondence and no
centring, and it separates the radius cleanly —

```
h(45°)/h(0°) for a rounded square = (a(√2−1) + r(√2·π/4 − 1)) / a
measured 1.2512  ->  r/a = 0.3935  ->  r = 25.0 mm on a = 63.5 mm
```

Two cautions, both hit for real. **Centre on the bounding box, not the vertex
centroid** — a mesh with dense port geometry and sparse flat walls has a
centroid that is pulled toward the detail, and the same measurement then reads
27.0 mm. And **self-validate the method** before trusting it: build your own
model at the value you measured and re-measure it the same way (predicted
1.23809, measured 1.2381 — the method is unbiased, the 27 mm reading was not).
Final agreement against Apple's own geometry: 24.99 mm vs 25.00 mm.

### When it is neither published nor measurable, say so next to the constant

The method has a precondition: the vendor has to ship geometry. The 14-inch
MacBook Pro's plan corner radius was assumed because the author believed no
Mac USDZ existed — **that premise was wrong** (see "First: convert, or
build?"). Apple publishes one, the body is unchanged from M4 to M5, and the
assumption has not been re-measured. It still ships as a guess.

So write the assumption down where the number lives, say what it costs, and
note what would settle it:

```python
BODY_W, BODY_D, BODY_H = 312.6, 221.2, 15.5   # Apple's published envelope
CORNER_R = 14.0    # ASSUMED, NOT MEASURED. The premise it was written under --
                   # "no Mac USDZ exists" -- was wrong: Apple's M5 14-inch USDZ
                   # lives at /105/media/us/macbook-pro/2025/785e1bc4-.../ar/,
                   # and the body is unchanged from M4, so this is measurable
                   # with the support function above. Until then: a corner arc on
                   # a 312.6 mm body -- 4.5% of the width against the Mac mini's
                   # 20% -- so an error is a soft corner, not a wrong silhouette.
```

An annotated guess is usable by whoever comes next; an unannotated one is a fact
they will trust.

### Mixing the two units builds a wrong model and reports nothing

Observed: `CORNER_R - 1.5` subtracted millimetres from a metre-valued constant
and produced a **negative** corner radius. It built clean, exported clean, and
passed every check it made on itself. Only re-importing the `.glb` and measuring
that caught it.

Blender has no units — a number is a number, and nothing in the pipeline can
notice a mixed one. A gate that re-imports the finished file is the only
detector this failure class has. Run it.

**Decide the datum and write it down.** Base at `z = 0` and centred on x/y
means the asset drops onto a ground plane without a transform. Anything else
means whoever uses it does algebra.

Ports have published dimensions — use them, do not eyeball. What you want is
the **panel opening**: the hole in the case, which is larger than the plug that
goes into it. A USB-C plug is 8.25 × 2.4 mm but its opening is ~8.95 × 3.16 mm;
modelling the plug size gives a port that looks too tight.

| Connector | Panel opening |
|---|---|
| USB-C / Thunderbolt | 8.9 × 3.2 mm |
| HDMI | 15 × 6 mm |
| RJ45 ethernet | 16 × 13 mm |
| 3.5 mm headphone jack | ⌀6 mm |
| USB-A | 13 × 5.7 mm |

A port row is a rhythm: uniform height, evenly spaced, small gaps. Getting the
heights roughly right is most of what makes it read as a port row rather than a
barcode — the first attempt at the example model had every port 2–3× too tall.

## Bevels are for shading, not detail

A bevel's job is to put a **highlight line** on an edge so the eye reads it as a
machined edge instead of a mathematical one. That is a shading effect, and it
saturates almost immediately.

- **One segment, ~45°, is the low-poly chamfer.** Measured on the example:
  296 tris single-segment vs 408 multi-segment for the same rim, and the
  single-segment version has the crisper highlight.
- Multi-segment only where a real fillet is the point — a corner radius visible
  in silhouette (the Mac mini's 25 mm plan corners: 6 segments), or an edge
  that catches a specular sweep.
- Bevel **before** you finalise topology, and re-check the bounding box
  afterwards: bevels on an outer edge grow nothing, but a bevel on the *inside*
  of a corner can and clamping changes what you get.

## Shading

Flat shading on a curved surface shows every facet — sometimes that is the
look, usually it is not. Auto-smooth by angle is the default treatment: smooth
everything, then mark edges sharp where the dihedral angle exceeds a threshold.

- 30° is a good default for hard-surface. It smooths a 6-segment corner
  (30° per facet) while keeping every 90° edge crisp.
- **All-or-nothing per edge.** One flat face next to smooth ones shades as a
  visible seam, so do not flat-shade "just this panel".
- glTF has no sharp-edge concept — the exporter writes **split normals**. That
  is fine, but it means an imported `.glb` has no `sharp_edge` attribute to
  inspect; do not read one and conclude the shading was lost.

### A coplanar loop is invisible

An edge loop only shows if the surface actually turns there. A panel seam built
as a single inset loop on a flat wall measured **0.0° dihedral** — coplanar, and
invisible in the render. A step needs **two** loops: one left on the outer
surface, one just inside it, with the face between them forming a real ledge.
Moving a single loop inward just tilts the whole wall below it.

## Parts and poses

A model is a set of parts, and each part is judged in the pose that exposes it.
Two habits keep that from being an afterthought; the failure modes are in
`SKILL.md`.

**One object per material class, and a name that says what the part is.** The
topology rule and the consumer's rule point the same way: `keyboard-well`, `lid`,
`trackpad` — not `Cube.004`. A converted asset does not arrive this way (the
Mac mini ships nodes called `NSIYUnWzVKBbqgR` and `pLIBxYhikmjgkTo`) and the
page using it pays in hardcoded strings; renaming during the conversion is the
cheap place to fix it (`SKILL.md`, "Converting a vendor asset"). Naming is also
how *you* find the part later: every fix in that debugging session started by
naming the mesh it was about.

**A hidden part still has a value, and still has a shape.** Interior geometry
authored to be invisible gets authored *as* invisible — the Mac mini's interior
parts measure 75, 63 and 89 out of 255 on screen with no form inside them,
because their occlusion atlas was baked with the lid on. Three consequences:

- Bake AO for the pose the asset will be **shown** in, or ship it as an atlas the
  consumer can drop. An atlas baked for a shut box is the shadow of a lid that is
  not there the moment the box opens.
- Give an interior part its own albedo and real form rather than leaning on
  occlusion to hide it. If it is worth modelling, it is worth reading as a shape.
- Parts that are **half** interior are the expensive ones. The Mac mini's bottom
  housing is the skirt on the outside and the tray inside; optimising its
  interior reading cost the *closed* pose its shading, and closed is the pose the
  page is in almost always. Check the pose you are not optimising for.
- **A decal plate may be open; a shell may not.** A flat plate — a port strip, a
  logo, a screen face — is legitimately an open surface, and the gate reports its
  boundary edges without failing. A *shell* with a hole is a different thing. The
  MacBook Pro's display recess was capped by a separate black prism, which looked
  identical from every angle and left the lid carrying **28 boundary edges**
  round an open ring: invisible until someone hides the bezel, which is the first
  thing an exploded view does. Folding the bezel into the lid as its recess floor
  removed a part *and* closed the frame. Test: hide the thing in front and ask
  what the part behind it is now.

And the pose decision is a **dimension** decision, not just a look: an asset
whose enclosure must measure true may have to be built in its closed frame and
opened by a rotation applied afterwards. Build in one frame, rotate into the
pose, and measure both — the closed envelope against the spec sheet, the shipped
one against what the gate can actually see.

## Studio setup

The model is half the asset; the preview is how anyone judges it.

- **World**: a vertical gradient, not a flat colour. TexCoord → Separate XYZ →
  MapRange (−0.05 … 0.45) → ColorRamp (dark 0.02 → light **0.70**) →
  Background, Strength **1.45**. This gives the metals something to reflect,
  which is what makes a metal read as metal. **Those numbers are in the space
  they are used in** — a `Generated` Z is `sin(elevation)` over **−1 … 1**,
  already signed, not remapped to 0 … 1. Remap as if it were 0 … 1 and the whole
  visible sky clamps to the dark end, giving a hard black band across the
  background. (A light end of 0.42 with strength 1.0 measurably renders the same
  subject murky — mean 0.36 against a target of 0.6.)
- **The world is what lights a metal, not the suns.** A `metallic 0.85` surface
  has essentially no diffuse response, so key and fill barely move it — raising
  both suns by 1.6× took the frame only from 0.36 to 0.45. The world did the
  rest (0.45 → 0.58). If
  a metal looks too dark, reach for the Background strength first.
- **…unless the subject's big surfaces face sideways.** Which end of the
  gradient matters depends on orientation: a squat box's dominant face points at
  the zenith, so strength is the lever (the Mac mini). A laptop is two large
  **vertical** panels, and a vertical panel mirrors the *horizon*, which sits
  mid-gradient — so strength is the wrong lever. Measured on the 14-inch
  MacBook Pro: at strength 1.45 the lid read murky (hero p99.9 **0.833**,
  under the 0.85 floor); raising strength to 1.9 fixed the lid and blew the
  up-facing deck from p95 0.871 → **0.964**, a flat white sheet that every
  number still passed. The fix was the window, not the level: MapRange
  **−0.45 … 0.35** (horizon mid-ramp, zenith still saturating) at the original
  1.45, giving hero 0.867 with the deck back at 0.872. Two symptoms, opposite
  fixes, one world.
- **Engine: Cycles for anything metallic.** EEVEE can only show a reflection it
  has been given — a light probe, a reflection plane, screen-space data — and
  with none of that set up a metal renders flat grey, which reads as a broken
  material and sends you tuning colours that were never the problem. Cycles
  takes the world gradient straight and gets brushed aluminium right on the
  first frame. Cost on a 127 mm subject at 900×900: three frames in 34 s, so
  EEVEE's speed buys nothing at preview size.
- **Lights**: `SUN` key ≈ **8 W/m²**, `SUN` fill ≈ **1.8 W/m²** from the
  opposite side, as a *set with the world above* — the two are coupled, and a
  5 W key under this world renders a stop dark. Suns are scale-free; see
  SKILL.md on why that matters. Area lights are softer but their wattage must
  be derived from the subject size. Land the pair by measuring the render, not
  by trusting either number.
- **Camera**: 50–55 mm equivalent. Long enough that a box does not look
  distorted, short enough to feel like a product photo. Three angles is a good
  default: hero 3/4, a second from the port side, one low grazing angle.
- **`view_transform = "Standard"`**. Blender 4.0+ defaults to AgX, which
  desaturates and rolls off highlights — it will make your colours look wrong
  and your exposure look fine. Standard for a product render.
- **Film**: transparent if the preview is going on a page; a visible ground
  plane if the object needs to sit on something. A ground plane occupies much of
  the frame, so it does set the exposure — but **not through its albedo**, which
  is the part that misleads. On a studio sweep the camera is low and the plane
  runs past the frame edge, so most of the visible floor is at a **grazing
  angle, where Fresnel goes to 1 and the floor mirrors the sky whatever colour
  you give it.** Measured on the 127 mm example: base colour 0.09 → 0.055 →
  0.035 (2.6× darker) changed the render by **nothing visible**; setting
  `Specular IOR Level` 0.5 → 0.0 at the *same* base colour took the floor from
  mean 0.504 / 2.24% blown to 0.333 / 0.08%. If a floor is blowing out, reach
  for `Specular IOR Level` (≈**0.25** keeps a sheen without clipping) or
  roughness — not the base colour. Three albedo changes in a row is the
  signature of tuning the wrong property.

### The preview is the deliverable's evidence

Render, then **open the PNG and look at it** — at thumbnail size first, because
that is how the asset will actually be seen. A render that took ten seconds to
produce and was never opened has verified nothing.

Then **measure** it, because looking is not enough for exposure. A render with a
few percent of its pixels at pure white does not look wrong — the eye adapts and
calls it a clean bright product shot. One build reported its exposure as correct
while 3.57% of the hero frame was already clipped.

**Judge exposure by the extremes, not by the mean.** Five renders measured:

| subject | mean | p95 | clipped > 0.98 | |
|---|---|---|---|---|
| Mac mini | 0.64 | 0.80 | 0.00% | well exposed |
| Mac mini | 0.58 | 0.84 | 0.10% | well exposed |
| keyboard | 0.38 | 0.90 | 0.42% | well exposed |
| Mac mini | 0.36 | 0.59 | 0.03% | murky |
| Mac mini | 0.74 | 0.96 | 3.57% | blown |

The mean is not a usable target: two correctly-exposed renders of different
subjects sit at 0.38 and 0.64, because the mean depends on how much of the frame
the background fills and how light the product is. The keyboard at 0.38 is a
bright white product on a mid-grey sweep; the Mac mini at 0.36 is uniformly dim.

p95 separates those five — but it is **composition-sensitive**, because it asks
what the brightest 5% of the frame is doing, and that is a framing choice. A
flat-on front view whose only bright feature is a thin chamfer line covering
under 5% of the frame measures p95 **0.687** while looking perfectly lit. The
gate therefore uses **p99.9** (`--min-highlight`, default 0.85): "does the frame
contain a highlight at all" does not depend on how much of the frame it covers.

Aim for **p95 ≈ 0.8–0.9, clipped ≈ 0**. `check-model.py --render` prints mean,
p95, p99.9 and the clipped fraction; it fails above 2% clipped and below
`--min-highlight` 0.85. Both directions were run on real renders: the current
build passes every view (p99.9 1.000 / 1.000 / 1.000 / 0.942), while the same
model with the world gradient at 0.42 and strength 1.0 — the pair this file used
to recommend — **exits 1**, caught on the top view at 0.825. Note it is a gate
over the *set*: in that murky build the hero still measured 0.868 and passed
alone, so read the per-view numbers rather than the exit code.

### Re-expose for the subject — both dials

A rig is tuned to one subject's albedo. The iMac's housing is
0.784/0.789/0.800 at metal 0.6, its chin 0.674, its bezel 0.95 — 1.9× the
luminance of the *blue variant of the same machine*, and far above the
space-black laptop this rig was swept on. Reused unchanged, the stand
close-up put **21.4% of the frame at pure white**; turning the key down to
0.35× still left 10.3%.

The world is a dial too, because it — not the suns — is what lights the
metal. At 0.35× the key the flat, up-facing stand foot did not move. Sweep
the pair `(world strength, key multiplier)`: `(1.66, 0.18)` still returned
2.8% clipped; `(1.45, 0.20)` returned 1.8% while the side view's p99.9 held
at 0.910. **Carry the previous subject's rig numbers, never its exposure
numbers.**

### A lit screen's white is content

Before underexposing a product because its screen view clips, render that
view with world strength 0 and every sun hidden. The iMac still measured
**2.50% pure white** — Apple's own wallpaper, which is the thing being
photographed. What survives the probe is the rig's share. Write the probe
next to the exemption instead of re-lighting the product to satisfy a
metric.

### A tight macro falls under the p99.9 floor

The gate samples the brightest 0.1% of the frame — 1,440 px at 1200². The
iMac's port macro has a real specular on all four bores, but it covers 74 px
(peak 0.957, 0.005% over 0.85), so p99.9 never reaches it and
`--min-highlight` fails a view that is correctly exposed. Pulling the camera
back to a 150 mm frame would pass the gate and put a small object in a lot
of empty floor. Keep the shot and record the pixel count as the exemption.
**A metric that cannot see the subject does not get to compose the shot.**

## The test that is not a test

Every number in `check-model.py` can pass on a model that looks wrong. The
checker catches topology, budget and dimension drift; it cannot catch an
occluded LED, a port row that reads as bricks, or an ugly highlight. Budget a
look at every render. When something looks off, form a hypothesis and test it
with a controlled change — the baseline agent that found a dark sliver at the
silhouette deleted the suspect part and re-rendered, which is exactly right:
it proved the part was innocent instead of guessing.
