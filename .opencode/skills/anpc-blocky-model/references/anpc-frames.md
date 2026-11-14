# anpc frame math, programs, and the entity pattern

## Frame math

- b3d KEYS frames are **1-based**; anpc animation frames are **0-based**.
  **b3d frame = anpc frame + 1.** The spec's `clips` and
  `npc.model.register_animation` both use 0-based anpc frames — the spec
  values can be pasted into the lua unchanged.
- The b3d `ANIM` header stores `frames - 1` (e.g. 221 KEYS frames → ANIM
  says 220).
- **All frames outside the clips must be one and the same neutral rest
  pose** (bit-identical in the file). anpc's `animation_after` hand-off and
  generic idle frames live there. The spec's `pose(f)` must return rest
  (all zeros) outside the clip ranges. Note: a clip may START on the rest
  pose (the cat's stand loop does at anpc frame 0, because one of its sine
  terms has a phase offset) — "clip frame 1 must move" is NOT a valid check.

## register_animation

```lua
npc.model.register_animation("golem.b3d", "stand", {
    start_frame = 0,      -- 0-based anpc frame
    end_frame   = 79,     -- inclusive
    speed       = 30,     -- frames per second of playback
    loop        = true,
    -- loop = false REQUIRES animation_after (default "stand" if omitted):
    animation_after = "stand",
})
```

- `speed` is playback fps, independent of the model's 60 fps authoring rate.
  A clip of (end-start+1) frames at `speed` s lasts
  `(end-start+1)/speed` seconds.
- For `loop = false` + `animation_after`, the engine schedules the hand-off
  via `minetest.after((end-start+1)/speed, ...)` and replays the named
  animation (which is looped by default). It liveness-checks the entity
  first, so it is safe if the NPC dies/gets removed mid-animation.
- `npc:model:set_animation {name = X}` (and `npc:move:stand` /
  `npc:move:walk`) play the registered animation. `npc:move:stand` plays
  the looped `stand`; `npc:move:walk` plays `walk` while moving
  (`cardinal_dir` 0..7, `speed` blocks/s).

## Programs and state processes

- `npc.proc.register_program(name, {instr, ...})` — each instruction needs
  `srcmap` (1-based map for debug output); optional `key` to capture an
  expression into a local variable (e.g. `key = "@local.r"` on
  `npc:random`).
- **State program**: set with `npc.proc.set_state_process(luarentity,
  "name")`. The engine RESTARTS it from instruction 1 after it reaches the
  end — so a state program is a loop by construction (the cat's `cat:idle`
  ends by falling off the end).
- **Helper programs** are pushed onto the stack with `npc:execute`; when
  the helper finishes, the state program resumes its loop (a new pass
  from instruction 1 — not "continue where it left off").
- `npc:set_proc_interval {value = seconds}` slows/speeds up how often the
  current program's instructions execute. Use it to keep a one-shot
  animation visible (e.g. the cat's eat: 4 frames @ 15 fps = 0.27 s →
  interval 0.4 s) or to sit in a looping animation for a long time (nap:
  30 s interval while looping `lay`).
- Expressions: `@global.x`, `@local.x`, `@time` (= minetest local time ×
  24000; a full day is 0..24000, night ≈ 20000–24000 ∪ 0–6000), nested
  `{left=..., op="+", right=...}` trees, ops: `+ - * / == != < <= > >= && ||`.
- **`npc:jump_if` offset semantics (the classic trap)**: with
  `offset = true`, the engine adds an extra +1 inside
  `npc.proc.execute_instruction`, so instruction C with `pos = N` jumps to
  **C + 1 + N** (not C + N). With `offset = false` it jumps to
  C + N. The cat's daily-loop jumps (e.g. instruction 3, `pos = 1`,
  offset → instruction 5) follow this — copy the arithmetic, don't
  re-derive it.
- `negate = true` inverts the condition (used for "skip the next
  instruction(s)" patterns).
- `npc:var:set {key, value, storage_type}` — value can be a number, a
  `@var` reference, or an expression tree; `storage_type` is `local` or
  `global` (global survives program restarts and is persisted by anpc).
- `npc:random {start, end}` (inclusive) → store with `key = "@local.x"`.

## Entity registration pattern (copy from cat.lua)

```lua
minetest.register_entity("anpc_dev:<name>", {
    hp_max = 1,
    visual = "mesh",
    mesh = "<name>.b3d",
    textures = { "<name>.png", "<name>_gray.png" },  -- random per spawn;
                                                     -- pin by listing one
    visual_size = {x = 1, y = 1, z = 1},
    visual_offset = {x = 0, y = 0.5, z = 0},
    -- THIS ENGINE BUILD rests the collision box 0.5 sunk into the
    -- supporting node; the offset lifts the model back to node top.
    collisionbox = {-0.15, 0, -0.5, 0.15, 1.1, 0.5},  -- tune to the model
    stepheight = 0.5,
    physical = true,
    on_activate = npc.on_activate,
    get_staticdata = npc.get_staticdata,
    on_step = npc.do_step,
    on_rightclick = function(self, puncher) ... end,  -- optional debug
})
```

- `visual_offset y = 0.5` is required on this engine build (the 0.5
  collision sink). Forgetting it makes the NPC stand half a block inside
  the ground node.
- **collisionbox rule (all anpc mods)**: square cross-section whose side
  equals the model's width, and height equal to the model's height. The
  reference NPCs follow it (0.4 × 0.4 × 1.8 for the 1.8-tall humanoid);
  the cat is `{-0.15, 0, -0.15, 0.15, 0.7, 0.15}` (0.3 wide head, 0.7 to
  the ear tips). A box deeper/wider than the model blocks pathfinding in
  one-block gaps the model visually fits through.
- `on_rightclick` debug aid: log `self.process.state.name`,
  `self.data.global.<var>` and `self.timers.proc_int` — the fastest way to
  verify a behavior loop in game.

## Spawner item pattern

```lua
minetest.register_craftitem("anpc_dev:<name>_spawner", {
    description = "...",
    inventory_image = "<name>_spawner.png",   -- the spec's icon(pal) output
    on_use = function(itemstack, user, pointed_thing)
        local spawn_pos = minetest.pointed_thing_to_face_pos(user, pointed_thing)
        local entity = minetest.add_entity(spawn_pos, "anpc_dev:<name>")
        if entity then
            npc.proc.execute_program(entity:get_luaentity(), "<name>:init")
            npc.proc.set_state_process(entity:get_luaentity(), "<name>:idle")
        end
    end,
})
```

The `<name>:init` program sets any starting globals (e.g. hunger = 0) and
executes an initial helper if needed; the state process is the daily loop.

## Behavior template (vegetarian-style, the cat's shape)

State loop: stand (looped) → grow a hunger global → if hungry: execute
eat helper (slow interval, one-shot animation with `animation_after =
stand`, reset hunger) → if night: execute nap helper (slow interval,
looped `lay`, re-check time each pass, stand up at morning) → random
chance of wander helper (1–5 steps, fresh random cardinal direction each
step, never the same direction twice in a row, stand at the end).
No bed/grass logic. `cat.lua` in the mod root is the working reference.
