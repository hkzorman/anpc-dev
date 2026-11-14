# b3d / UV / skin conventions

Everything here was discovered empirically while building the cat from
scratch. Do not re-derive or "fix" signs — the pipeline and the shipped
cat.b3d agree with it, and the selftest enforces it.

## File (.b3d) coordinate and UV conventions

- The exporter (io_scene_b3d, `write_node_mesh_vrts`) swaps axes:
  **file = (Bx, Bz, By)** — determinant −1. Blender Y-up→Z is file Z→Y, etc.
- **File UV: u left→right, v with v=0 at the image TOP** (pixel row / atlas
  size, like PIL). The exporter writes `(u, 1 - v_blender)`, so the Blender
  UV stored in the mesh is `(u, 1 - pixel_row/atlas)`. This flip lives in
  `box_uv.box_geom` — removing it silently moves every face to the
  vertically-mirrored region of the atlas.
- Triangle tessellation per quad (vertex order per part is 24, 4 per face):
  `(v0+2, v0+1, v0)` then `(v0+3, v0+2, v0)`.
- Face order per part (both in `box_uv.FACE_ORDER` and in the skin):
  `+Y (front), -Y (back), +X (right), -X (left), +Z (top), -Z (bottom)`
  for a part facing +Y.
- **Triangle winding (the invisible-top-face trap)**: each face's 4-vertex
  loop is defined in `box_uv._FACE_LOOPS` as (3D corner, texture corner)
  pairs. The side faces sweep `[BL, BR, TR, TL]`; the top/bottom faces must
  sweep `[BL, TL, TR, BR]`. The exporter reverses the quad winding and the
  axis swap (det −1) flips it back, so all six faces land in the same
  file-space convention the engine's backface culling expects. The naive
  `[BL, BR, TR, TL]` sweep on +Z/−Z winds those quads inward and the engine
  culls the top/bottom faces — they render invisible. The pairing (which
  pixels land on which 3D corner) is identical to the naive sweep, so only
  the winding changes, never the skin look.
- Face pixel size = part size along the face's (u-axis, v-axis) ×
  px_per_unit: front/back (x,z), sides (y,z), top/bottom (x,y). Override per
  face with `face_px` (the cat's head front/back are deliberately squished
  to 10 px wide instead of the derived 12).
- Symmetric parts (the cat's ears, legs, tail segments) **share one set of
  regions** — one painted set of face pixels is used by every part that
  lists the same region names. This keeps the atlas small and the look
  consistent.

## b3d node structure (as exported by this exporter)

- Select the **mesh object only** for export. The exporter's mesh branch
  finds the armature through the **armature modifier** and merges
  everything into ONE node named after the mesh object:
  `MESH` (raw rest verts — not evaluated pose — with per-vertex bone
  weights from vertex groups), `ANIM` header, and one child NODE per bone
  (each with `KEYS` frames 1..N and a `BONE` weight table listing ALL
  verts, weight 0 for unweighted).
- ANIM header = (flags 0, **frames-1**, fps) — the exporter hardcodes
  **fps 60** in the chunk. Keep spec `fps: 60`.
- If you select more than one mesh, a `ROOT` wrapper node appears — don't.
- The armature object itself is NOT a separate node; its name only matters
  inside Blender.
- Material with no image node → `BRUS` with texture id **[-1]** and the
  material's name. The skin is supplied at runtime by the entity's
  `textures` property (the reference anpc NPC works the same way). The
  material name becomes the BRUS name in the file — match `object_name`.
  Blender's default base color (0.8, 0.8, 0.8) is what lands in the BRUS
  rgba.

## Skin atlas conventions

- Grid orientation per face rect (row 0 = top of rect, col 0 = left):
  - front/back: **col 0 = +X = the model's RIGHT side**
  - left face: col 0 = +Y = the model's FRONT
  - right face: before the auto-flip its col 0 is the BACK; the flip
    corrects the axis direction
  - top/bottom: col 0 = model left, row 0 = model back (top face) / front
    (bottom face)
- **Mirror rule**: a part's +X (right) face is auto-filled as the
  horizontal flip of its −X (left) face — because the +X face samples its
  texture from the back of the box, a symmetric marking must be mirrored
  to look symmetric in 3D. `mirror_right: False` + explicit paint only
  when the right face must differ.
- Painter contract: draw only the canonical faces (front, back, left, top,
  bottom of each region). `skin.make_atlas` fills right faces, then audits:
  every pixel inside every layout rect must be opaque, every pixel outside
  must be transparent. `bad` in the report must be 0.
- Variants are palettes, not geometry: first palette → `<name>.png`,
  others → `<name>_<palette>.png`. The entity's `textures` list may hold
  all of them (engine picks randomly per spawn; pin by listing one).
- `layout` rects: `(px0, py0, w, h)` with **py0 from the image top** (PIL
  convention, matches file-v). Auto-pack = shelf FFD (first-fit-decreasing
  by height then width), no gutters — touching rects are fine because UVs
  land exactly on borders. Explicit `spec['layout']` wins and is validated
  (bounds + no overlaps + sizes must match the derived face sizes).

## Model space

- Blender Z-up. Model faces +Y; +X is the model's right side.
- Feet at z=0 (authoring choice — the exporter preserves it).
- 1 model unit = 0.1 in-game block (cat body ≈ 2.5×4.0×2.5 units).
- Bones: head/tail in model space, parent links for hierarchy. Rest pose
  = all local offsets zero; the file's non-clip frames carry the
  rest-pose bone matrices (NOT zeros) — see the verifier's
  "rest frames neutral" check, which compares non-clip frames against each
  other.
