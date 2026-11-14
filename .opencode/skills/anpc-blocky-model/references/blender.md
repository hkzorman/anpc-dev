# Headless Blender 5.3 — quirks that matter

The pipeline builds in **headless** Blender
(`blender --background --python tools/anpc_model/blender_build.py`), not
via a live MCP session. The pipeline's Blender step is deterministic and
re-runnable; a running Blender instance is not required.

## Invoking headless

- Exe locations probed by `run_all.find_blender` (or `--blender` /
  `BLENDER_EXE`):
  `C:\Program Files\Blender Foundation\Blender <ver>\blender.exe`
  (Blender 5.x nests the version directly — `Blender Foundation\Blender 5.3\`,
  NOT `Blender Foundation\Blender\5.3\`). On this box: 5.3.0.
- **Full command line as sys.argv**: Blender 5.x passes `blender.exe` +
  every flag as the script's `sys.argv[0:]` (argv[0] = blender.exe).
  Don't rely on `sys.argv[1:]`.
- **Unknown `--flags` after `--python <script>` are swallowed by Blender
  and loaded as files** (you get "ERROR Cannot read file ..." for them).
  That is why `run_all` passes paths through **environment variables**
  `ANPC_SPEC` / `ANPC_LAYOUT` / `ANPC_OUT` instead of CLI args.
  `blender_build.py` also accepts plain `--spec/--layout/--out` when run
  directly with `python`.
- The io_scene_b3d add-on (at
  `~\AppData\Roaming\Blender Foundation\Blender\5.3\scripts\addons\io_scene_b3d-master`)
  auto-registers in a clean headless session (`bpy.ops.export_scene.b3d`
  exists); `ensure_b3d_exporter()` still has an exec-the-file fallback.

## Keyframing (Blender 5.3)

- Pose-bone properties have no working direct `keyframe_insert` in the
  exec context — key through the armature object:
  `arm.keyframe_insert(data_path='pose.bones["B"].location', frame=f)`
  (same for `rotation_euler`).
- Set `pb.rotation_mode = 'XYZ'` BEFORE writing `rotation_euler`.
- Interpolation is not LINEAR by default — set it explicitly on every
  keyframe point:
  `for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'`.
- Key EVERY frame 1..N explicitly (the pipeline's `pose(f)` hook supplies
  all frames; rest frames are real keys at zero offset, which is what
  makes non-clip frames bit-identical).

## Action API (Blender 5.x breaking change)

- **`Action.fcurves` no longer exists.** Keyframes live at
  `action.layers[].strips[].channelbags[].fcurves`. Strips are
  `ActionKeyframeStrip` and have NO `.name` attribute (don't probe it).
- Consequence: the io_scene_b3d exporter's
  `getArmatureAnimationEnd` (reads `action.fcurves`) crashes with
  `AttributeError` at export time. The pipeline fixes this WITHOUT touching
  the add-on file: `blender_build.patch_b3d_exporter()` monkeypatches the
  function in the loaded module in memory (the exporter's submodule is
  lazy-imported by the operator on first use, so the patch pre-imports it
  through the package and swaps the function). Look for the `B3D_PATCH [...]`
  line in the build output; an empty list means the patch did not find the
  module. The patched function is a dual-API shim (`hasattr(action,
  'fcurves')` → old API, else layers/strips/channelbags), so it also works
  on Blender 4.x.
- Why the original live cat export ever succeeded on 5.3 at all: that
  session had swapped the same kind of in-memory compat function into the
  loaded exporter module (its `co_filename` pointed at a since-deleted
  `Temp\opencode\b3d_parse\build_dog_dev.py`). In-memory patches die with
  the process — any fresh process (headless or restarted Blender) loads
  the unpatched module from disk and crashes. The runtime patch in the
  pipeline makes that step deterministic.
- If you ever need fcurve data directly, use:
  `action.layers[i].strips[j].channelbags[k].fcurves` —
  `fc.keyframe_points[n].co[0]` = frame, `.co[1]` = value.

## Exporter behavior (io_scene_b3d, do not "improve")

- Only select the MESH object. The armature must be attached via an
  **armature modifier** (or armature parent) — the exporter finds it there.
- Node written = mesh object name; material name = BRUS name; fps is
  hardcoded 60 in the ANIM chunk; ANIM stores frames-1.
- Export kwargs used by the pipeline (in `blender_build.export_b3d`):
  `use_local_transform=False, export_ambient=False, enable_mipmaps=False,
  use_selection=True, use_visible=False, use_collection=False,
  object_mesh=True, object_armature=True, object_light=False,
  object_camera=False, export_texcoords=True, export_materials=True,
  export_normals=True, export_colors=False`.
- **Do not modify the add-on files on disk** (they live outside the repo);
  all 5.x compatibility is patched at runtime by `blender_build.py`.

## Console / encoding

- PowerShell on this box is cp1252: printing Unicode (block glyphs, etc.)
  from Python to the console raises or mangles. Python code that emits
  non-ASCII must `sys.stdout.reconfigure(encoding='utf-8')` or write to a
  file (the pipeline's ascii preview goes to `build/ascii.txt`, not stdout).
- `blender --python-expr "..."` with nested quotes breaks in PowerShell —
  write a small probe `.py` file and pass it with `--python` instead.
- The Blender step takes ~30–60 s (221 frames × 7 bones). Give shell
  commands a generous timeout.
