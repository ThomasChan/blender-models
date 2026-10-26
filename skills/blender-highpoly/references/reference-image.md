# Modelling from a reference image

A photograph is evidence of a projection, not of a shape. Use it to ask
questions, and write down which question each measurement answers.

## Calibration comes first

- **The S0 blockout contains no millimetres and no mesh counts.** Until a
  dimension is calibrated, the only honest unit is the pixel. A blockout that
  says "127 mm" before calibration has invented its scale.
- **No scale reference means pixel units only.** Do not infer millimetres from
  a product name, a sibling model, or "it looks like the 27-inch".
- **A four-point homography is valid only on the plane of those four points.**
  It does not recover depth. The error grows with distance from that plane:
  at a camera distance of 8 m, a 5 cm depth change can move a projected point
  by about 52 mm. If the object has real depth, rectify one plane at a time.
- **Calibrate each view separately.** A front view and a side view have
  different camera positions; reusing one homography across views is a scale
  bug that looks like a modelling bug.

## Silhouette and IoU

- **Compute IoU per view, never one aggregate.** A good front score hides a
  bad side. Record the reference crop and the render beside each score.
- **IoU can disprove a silhouette; it cannot prove likeness.** A blank box can
  score well against a boxy object. Use IoU as a veto, not as acceptance.
- **A missing view is `unevaluated`, not a pass.** If the reference has no back
  view, say so; do not average the views you have and call it complete.
- **A reference for the wrong variant is worse than no reference.** Pin the
  model, year and variant before measuring. The 27-inch iMac stand is not a
  reference for the 24-inch's.

## Gates

- `degraded`, `skipped`, `analyzed=false`, `unresolved` never count as pass.
  The same tri-state rule as `check-model.py`: PASS, FAIL, UNEVALUATED.
- For every view, keep: the reference crop, the render, the IoU, and the
  visible mismatches. "Looks close" is not a record.
- If the only evidence is a number you computed with the same code that drove
  the geometry, add a second path. A gate that confirms its own input is not a
  gate.

Adapted from dsh-blender-plugin's
`skills/blender-modeling/references/参考图通用还原SOP.md` (BSD-3-Clause); see
`THIRD_PARTY_NOTICES.md` and `LICENSES/BSD-3-Clause.txt` at the repository
root.
