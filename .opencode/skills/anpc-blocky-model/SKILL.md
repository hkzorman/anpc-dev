---
name: anpc Blocky Model
description: Build or change a blocky b3d NPC model + skin + anpc behavior in this Luanti mod from a Python spec. Use when asked to make an anpc NPC (e.g. "make a golem"), or to rebuild/adjust the model, skin, layout, or animation of an existing one, or to run/fix the tools/anpc_model pipeline.
---

# anpc Blocky Model Pipeline

Spec-driven pipeline in `tools/anpc_model/`: a Python **spec module** is the
single source of truth for model + skin + animation. One command produces
`models/<name>.b3d`, skin atlas(es), spawner icon, an ASCII preview and a
verification report.

Reference implementation: `tools/anpc_model/specs/cat.py` + the shipped
`models/cat.b3d`, `textures/cat*.png`, `cat.lua`. When in doubt, diff against
the cat.

## Workflow (new NPC, e.g. "golem")

1. **Read the references** (relative to this skill):
   - `references/conventions.md` — b3d/UV/skin conventions and gotchas
   - `references/anpc-frames.md` — anpc frame math, programs, spawner pattern
   - `references/blender.md` — headless Blender 5.3 quirks (only when the
     Blender step fails or the tooling itself changes)
2. **Write the spec** `tools/anpc_model/specs/<name>.py` — a plain Python
   module (schema below). Copy `specs/cat.py` and change parts/bones/pose/
   painter. Omit `layout` to get auto-packed UVs; set `atlas` if you want a
   fixed size.
3. **Build**:
   ```
   python tools\anpc_model\run_all.py tools\anpc_model\specs\<name>.py --out <mod root>
   ```
   (`--out` = the mod root so `models/` and `textures/` land correctly.
   `--palettes a,b` to build a subset; `--no-blender` to skip the Blender
   step for a spec/skin-only change.)
4. **Read the report** `build/report.txt`: layout size, Blender summary,
   skin audit (`covered` / `bad` must be `bad=0`), 14 verify checks (all
   PASS — includes the face-winding check), and a `collisionbox:` line
   derived from the spec's model bounds (square-rule, for the mod lua).
   Fix the spec and re-run until `RUN_ALL PASS`.
   Also open `build/ascii.txt` (atlas + optional front-view preview) and
   `read` the produced PNG to check the skin visually.
5. **Wire the mod** (`<name>.lua`, model on `cat.lua`):
   - `npc.model.register_animation("<name>.b3d", ...)` for every clip in the
     spec (0-based anpc frames, straight from the spec's `clips`).
   - Programs (`npc:init`, state program, helpers), the
     `minetest.register_entity` block (paste the report's `collisionbox:`
     line), and the spawner craftitem.
     See `references/anpc-frames.md` for the frame math and jump-offset
     rules.
   - Dofile it from `init.lua` after the anpc dofiles.
6. **In-game checklist**: spawn it (right-click spawner on a block top),
   watch idle/walk/one-shot animations, verify `textures` list behavior
   (random per spawn unless pinned), right-click debug log, save/reload
   persistence.

## Rebuild / tweak an existing NPC

Change the spec, re-run step 3 with the same `--out`. The output files are
overwritten in place. If the change touched shared pipeline code (anything
outside `specs/`), prove it is lossless with the regression gate:

```
python tools\anpc_model\selftest.py        # must print SELFTEST PASS
```

It rebuilds the cat from `specs/cat.py` into `tools/anpc_model/selftest_out/`
and asserts structural identity vs shipped `cat.b3d` + pixel-identical
`cat.png`. Never hand-edit the shipped `cat.b3d`/`cat.png` to make a test
pass — fix the spec or the pipeline.

## Spec module contract

```python
SPEC = {
    "name": "golem",            # file base: models/golem.b3d, textures/golem.png
    "object_name": ...,         # optional: b3d node/material name (default: name)
    "armature": ...,            # optional: Blender armature object name
    "px_per_unit": 4.0,         # skin pixels per model unit
    "atlas": 64,                # optional: fixed atlas size (else auto power of two)
    "layout": {...},            # optional: explicit {region: (x, y, w, h)}, py from
                                # image TOP; omit for shelf auto-pack
    "parts": [
        {"name": "Body", "center": (0, 0, 2.5), "size": (2, 3, 2), "group": "Body",
         "faces": {...},        # optional: face -> region name (default: <part>_<suffix>)
         "face_px": {...},      # optional: face -> (w, h) px override
         "mirror_right": True}  # default True: +X face = horizontal flip of -X face
    ],
    "bones": [
        {"name": "Body", "head": (0, 0, 1), "tail": (0, 0, 4), "parent": None}
    ],
    "animation": {
        "frames": 221,          # b3d KEYS frames 1..N
        "fps": 60,              # exporter hardcodes 60 - keep it
        "clips": [              # 0-based anpc frames (b3d frame = anpc frame + 1)
            {"name": "stand", "start": 0, "end": 79, "speed": 30, "loop": True},
        ],
    },
    "palettes": {               # >= 1; first = <name>.png, rest = <name>_<pal>.png
        "base": {"A": (r, g, b), "B": (r, g, b), ...},
    },
}

paint(A)     # required: draw canonical faces (front/back/left/top/bottom of
             # every region); A.grid(name) / A.put(name, grid) / A.band /
             # A.rows_of / A.full_row; right faces auto-flipped unless the
             # part sets mirror_right=False
pose(f)      # optional: b3d frame f (1-based) -> {bone: ((lx,ly,lz), (rx,ry,rz))}
             # local offsets; omit a bone for rest. Default: all rest.
icon(pal)    # optional: 16x16 RGBA Image -> <name>_spawner.png
preview(img) # optional: extra ascii lines (e.g. assembled front view)
PALETTE_ORDER = [...]  # optional: palette name order (first -> <name>.png)
```

Geometry conventions (do not re-derive; details in `references/conventions.md`):
feet at z=0, model faces +Y, +X = model right, 1 unit = 0.1 block, each part
is a box with 24 unshared verts, UVs computed from the layout, vertex groups
= bone names.

## Rules

- Frames outside all clips must be the identical neutral rest pose (anpc
  `animation_after` hand-offs rely on it) — the verifier enforces this.
- Non-looping clips need `animation_after` (defaults to "stand").
- No image node on the Blender material — the skin comes from the entity's
  `textures` property (BRUS tex [-1] trick).
- If you change anything in `tools/anpc_model/` outside `specs/`, re-run
  `selftest.py` and keep it green.
