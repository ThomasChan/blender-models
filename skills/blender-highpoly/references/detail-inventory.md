# Detail inventory

Fill this **before** the first line of geometry. The inventory is what stops a
model from being "the right silhouette with the wrong face": every detail the
eye will use to name the object gets a row, and every row names the field that
carries it.

A detail that exists only in prose is not built. "The front looks like the
photo" is not a row.

## The table

| # | zone | detail | kind | lands in | verified by |
|---|------|--------|------|----------|-------------|
| 1 | stand | circular cable hole, through | hole | boolean cutter `cable_hole` | render from the back; see through it |
| 2 | chin | Apple wordmark, centred | decal | material `logo` + alpha map | hero render at 1:1 |
| 3 | shell | 0.4 mm chamfer on the front lip | bevel | bevel modifier, width constant | side render, edge highlight |
| 4 | keys | keycap legends | linework | material atlas | close render of the layout |

`lands in` must be a real thing in the build: an object name, a material name,
a modifier, a boolean cutter, a vertex group, a material value. If the cell says
"modelled" or "looks right", it is empty.

## Kinds worth scanning for

`gloss` · `bevel` · `fastener` · `linework` · `contour` · `seam` · `stitch` ·
`stain` · `scratch` · `chip` · `decal` · `emissive` · `hole` · `groove` ·
`ridge`

The list is a scan aid, not a quota. A groove that is not there is a row with
"absent on this variant" and the reference crop that proves it.

## How to scan a reference

Pick one method and finish it; switching methods halfway leaves cells unread.

- **component-zones** — split the object into named zones (screen, chin, stand,
  ports, back) and sweep each zone at full resolution.
- **grid-3x3 / grid-4x4** — overlay the grid on the reference and record what is
  in each cell. Use it when the object has no obvious part boundaries.

Record the reference crop next to every row. "I remember seeing a seam" is not
evidence, and the crop is what the next person checks when the render disagrees.

## Rules that catch the usual misses

- **A hole needs a second row: what is visible through it.** A disc in the bore
  leaves the boolean valid and the hole plugged. The row is only done when a
  render shows the background through the opening.
- **A seam is two rows, one per side, plus the gap.** "Seam" with no gap width
  is a line drawn on a face.
- **A gloss difference is a material row, not a geometry row.** If the only way
  to see it is the reflection, the check is a render with a known light.
- **A detail on a curved surface follows the curve.** A flat decal projected
  onto a cylinder reads as a sticker at every edge.
- **Absent is a valid entry.** Marking "no screw on this variant" with the
  reference crop prevents a later pass from adding one from a sibling model.

The inventory is complete when every zone or grid cell has been read, not when
the list feels long enough. Attach it to the build script's directory so the
next change starts from the same list.

Adapted from img2threejs' `grimoire/intake/detail_inventory.md` (Apache-2.0);
see `THIRD_PARTY_NOTICES.md` at the repository root.
