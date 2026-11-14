# anpc_model — spec-driven b3d NPC pipeline

One Python spec → `models/<name>.b3d` + skin atlas(es) + spawner icon +
verification report. Built for the anpc/Luanti workflow; the cat is the
reference implementation and regression baseline.

## Project skill: `anpc Blocky Model`

The pipeline is also packaged as a project skill at
`.opencode/skills/anpc-blocky-model/` — it carries all the conventions
(b3d/UV/skin rules, the winding trap, anpc frame math, the collisionbox
square rule, Blender 5.3 exporter patch) so an LLM session can build a new
NPC without rediscovering anything.

- **Ability:** turns a request like "make a golem" into a spec-driven
  build — writes `specs/<name>.py` (from the cat template), runs
  `run_all.py`, checks the skin audit + 14 verify checks, pastes the
  report's `collisionbox:` line, and wires `<name>.lua` (programs,
  spawner, entity registration) from the cat template.
- **Triggers:** "make an anpc NPC", rebuild/adjust the model, skin, layout
  or animation of an existing one, or run/fix this pipeline.
- **Use:** just ask. Example prompt:
  > "Using the anpc Blocky Model skill, make a golem NPC: stone body, slow
  > idle + wander, about 1 block tall, with a spawner. Save the spec as
  > `specs/golem.py`."

Detailed references live in the skill:
`references/conventions.md` (b3d/UV/skin + winding),
`references/anpc-frames.md` (frame math, programs, spawner, collisionbox
rule), `references/blender.md` (headless 5.3 quirks + exporter patch).

## Quickstart

```powershell
# Build a spec (out = mod root so models/ + textures/ land correctly)
python tools\anpc_model\run_all.py tools\anpc_model\specs\<name>.py --out .
#   --palettes a,b     build only some palettes
#   --no-blender       skip Blender (reuse existing .b3d; spec/skin-only work)
#   --blender <path>   or set BLENDER_EXE

# Regression gate: rebuild the cat, require structural identity with the
# shipped cat.b3d + pixel-identical cat.png
python tools\anpc_model\selftest.py
```

Read `build/report.txt` (or the console output): layout, blender summary,
skin audits (`bad` must be 0), 14 verify checks (incl. face winding), and
the `collisionbox:` line for the mod lua. `build/ascii.txt` has the
ASCII atlas preview + any spec `preview(img)` output.

## Files

| File | Role |
|---|---|
| `specs/cat.py` | reference spec: cat model, 3 palettes, pose/skin/icon/preview hooks |
| `run_all.py` | orchestrator: layout → blender → skins → verify → report |
| `blender_build.py` | headless Blender: mesh + armature + keyframes → export .b3d |
| `box_uv.py` | part list → verts/UVs/quads/vertex groups |
| `layout_pack.py` | explicit layout validation + shelf auto-pack |
| `skin.py` | atlas painter (`Atlas`), mirror_right auto-fill, coverage audit |
| `b3d.py` | from-scratch BB3D parser (no model assumptions) |
| `verify_b3d.py` | 14 spec-driven checks on the exported file |
| `preview.py` | ASCII atlas rendering (+ spec `preview(img)` hook) |
| `selftest.py` | regression gate vs shipped cat assets |
| `selftest_out/` | selftest build dir (regenerated each run; git-ignored) |

## Env vars

- `ANPC_SPEC` / `ANPC_LAYOUT` / `ANPC_OUT` — how `run_all` passes paths to
  the Blender subprocess (Blender 5.x swallows unknown CLI flags after
  `--python` and tries to load them as files — see the skill's
  `references/blender.md`).
- `BLENDER_EXE` — blender executable override.
- `B3D_ADDON` — add-on dir for the fallback exporter load (rarely needed).
