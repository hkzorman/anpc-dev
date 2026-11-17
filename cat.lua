-- anpc_dev cat
--
-- A small blocky tabby cat (Minecraft-style look) with an idle/wander
-- behavior modeled on anpc's vegetarian NPC:
--   * stands idle and gets hungrier over time
--   * hungry  -> eats (plays the head-dip "mine_once" gesture)
--   * night   -> naps on its side (lay animation) until morning
--   * otherwise occasionally wanders a few steps to a random direction
--
-- Model + skin (built from scratch, see cat_work/ scripts):
--   models/cat.b3d  220 frames @ 60 fps:
--     stand 0-79 | lay 162-166 | walk 168-187 | mine_once 192-196
--   textures/cat.png  64x64 single atlas, 4 px per model unit
--
-- NOTE on jump offsets: a npc:jump / npc:jump_if with offset = true is
-- followed by an extra +1 inside npc.proc.execute_instruction, so an
-- offset of `pos` taken from instruction C executes instruction C + 1 + pos.

-- Animations
npc.model.register_animation("cat.b3d", "stand", {
	start_frame = 0,
	end_frame = 79,
	speed = 30,
	loop = true
})

npc.model.register_animation("cat.b3d", "lay", {
	start_frame = 162,
	end_frame = 166,
	loop = true
})

npc.model.register_animation("cat.b3d", "walk", {
	start_frame = 168,
	end_frame = 187,
	loop = true
})

npc.model.register_animation("cat.b3d", "mine_once", {
	start_frame = 192,
	end_frame = 196,
	speed = 15,
	loop = false,
	animation_after = "stand"
})

-- Programs
-- Init is self-contained: it sets up the globals cat:idle needs, does an
-- initial walk, and arms cat:idle as the persistent state process - so the
-- cat is fully operational from a single program run, however it spawned.
-- (set_default_program must stay last: it clears the process queue, which
-- would drop any instructions after it.)
npc.proc.register_program("cat:init", {
	{name = "npc:var:set", args = {key = "hunger", value = 0, storage_type = "global"}, srcmap = 1},
	{name = "npc:execute", args = {name = "cat:wander"}, srcmap = 2},
	{name = "npc:set_default_program", args = {name = "cat:idle"}, srcmap = 3}
})

-- State program: the cat's daily loop. Instruction map (1-based):
--   1  stand
--   2  hunger += 2
--   3  jump_if hunger >= 60 (negate) -> 5     (not hungry: skip the eat)
--   4  execute cat:eat
--   5  jump_if night (negate) -> 7            (day: skip the nap)
--   6  execute cat:nap
--   7  r = random 1..15
--   8  jump_if r == 1 (negate) -> 10          (no wander this pass)
--   9  execute cat:wander
--  10  (end: the engine restarts this state program)
npc.proc.register_program("cat:idle", {
	{name = "npc:move:stand", args = {}, srcmap = 1},
	{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = 2}, storage_type = "global"}, srcmap = 2},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 60}, offset = true, negate = true, pos = 1}, srcmap = 3},
	{name = "npc:execute", args = {name = "cat:eat"}, srcmap = 4},
	{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<=", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, offset = true, negate = true, pos = 1}, srcmap = 5},
	{name = "npc:execute", args = {name = "cat:nap"}, srcmap = 6},
	{key = "@local.r", name = "npc:random", args = {start = 1, ["end"] = 15}, srcmap = 7},
	{name = "npc:jump_if", args = {expr = {left = "@local.r", op = "==", right = 1}, offset = true, negate = true, pos = 1}, srcmap = 8},
	{name = "npc:execute", args = {name = "cat:wander"}, srcmap = 9}
})

-- Eats: slows the proc loop just past the one-shot mine_once length
-- (4 frames @ 15 fps = 0.27 s) so the head dip is actually visible,
-- restores the default 0.5 s interval, resets hunger and wanders off.
npc.proc.register_program("cat:eat", {
	{name = "npc:set_proc_interval", args = {value = 0.4}, srcmap = 1},
	{name = "npc:model:set_animation", args = {name = "mine_once"}, srcmap = 2},
	{name = "npc:set_proc_interval", args = {value = 0.5}, srcmap = 3},
	{name = "npc:var:set", args = {key = "hunger", value = 0, storage_type = "global"}, srcmap = 4},
	{name = "npc:execute", args = {name = "cat:wander"}, srcmap = 5}
})

-- Nap: lies on its side (looped lay animation) at a slow 30 s proc
-- interval, re-checking the time of day until morning, then stands up.
npc.proc.register_program("cat:nap", {
	{name = "npc:set_proc_interval", args = {value = 30}, srcmap = 1},
	{name = "npc:model:set_animation", args = {name = "lay"}, srcmap = 2},
	-- Back-jump lands at N+P+1 (fast-path +1), so to loop back to instr 1
	-- (re-set the 30 s interval + lay anim, re-check the time) P = 1-3-1 = -3.
	-- (P was -1, which landed on instr 3 = itself: an infinite fast-path
	-- recursion -> "stack overflow" every night while napping.)
	{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<=", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, offset = true, negate = false, pos = -3}, srcmap = 3},
	{name = "npc:set_proc_interval", args = {value = 0.5}, srcmap = 4},
	{name = "npc:move:stand", args = {}, srcmap = 5}
})

-- Wander: 1..5 straight-line steps, each a fresh random cardinal
-- direction (never the same one twice in a row), then stand.
npc.proc.register_program("cat:wander", {
	{name = "npc:var:set", args = {key = "prev_dir", value = -1, storage_type = "local"}, srcmap = 1},
	{key = "@local.steps", name = "npc:random", args = {start = 1, ["end"] = 5}, srcmap = 2},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}, srcmap = 3},
	{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}, srcmap = 4},
	{name = "npc:jump_if", args = {expr = {left = "@local.cardinal_dir", op = "==", right = "@local.prev_dir"}, negate = false, offset = true, pos = -2}, srcmap = 5},
	{name = "npc:var:set", args = {key = "prev_dir", value = "@local.cardinal_dir", storage_type = "local"}, srcmap = 6},
	{name = "npc:move:walk", args = {cardinal_dir = "@local.cardinal_dir", speed = 1.5}, srcmap = 7},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}, srcmap = 8},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<", right = "@local.steps"}, negate = false, offset = true, pos = -6}, srcmap = 9},
	{name = "npc:move:stand", args = {}, srcmap = 10}
})

-- NPC
minetest.register_entity("anpc_dev:cat", {
	hp_max = 1,
	visual = "mesh",
	mesh = "cat.b3d",
	-- Multiple textures: the engine picks one at random per entity.
	-- Pin a single variant here if you want a fixed color.
	textures = {
		"cat.png",
		"cat_gray.png",
		"cat_black.png",
	},
	visual_size = {x = 1, y = 1, z = 1},
	-- This engine build rests the collision box 0.5 sunk into the
	-- supporting node; lift the model back to the node top.
	visual_offset = {x = 0, y = 0.5, z = 0},
	-- Square cross-section: side = the model's width (0.3 blocks - the head
	-- is the widest part), height = the model's height (0.7, to the ear tips).
	-- Reference anpc NPCs do the same (0.4 x 0.4 for the 1.8-tall humanoid);
	-- keep the box near-square so the pathfinder sees a one-block obstacle.
	collisionbox = {-0.15, 0, -0.15, 0.15, 0.7, 0.15},
	stepheight = 0.5,
	physical = true,
	on_activate = function(self, staticdata)
		npc.on_activate(self, staticdata)
		-- Fresh spawn (no saved state): cat:init is self-contained -
		-- it sets the globals, does an initial walk and arms cat:idle
		-- as the state process. Restored entities keep their saved
		-- process (re-running cat:init on an inert one re-arms it).
		if staticdata == nil or staticdata == "" then
			npc.proc.execute_program(self, "cat:init")
		end
	end,
	get_staticdata = npc.get_staticdata,
	on_step = npc.do_step,
	on_rightclick = function(self, puncher)
		-- Debug aid: right-click the cat with any item to log its
		-- current state program + hunger.
		if puncher == nil or puncher:get_player_name() == nil then
			return
		end
		local state = self.process and self.process.state
		local hunger = self.data and self.data.global and self.data.global.hunger
		minetest.log("anpc_dev cat: state=" .. tostring(state and state.name)
			.. " hunger=" .. tostring(hunger)
			.. " proc_int=" .. tostring(self.timers and self.timers.proc_int))
	end,
})

-- Spawner item
minetest.register_craftitem("anpc_dev:cat_spawner", {
	description = "Cat Spawner",
	inventory_image = "cat_spawner.png",
	on_use = function(itemstack, user, pointed_thing)
		-- The entity self-initializes (cat:init + cat:idle) when it
		-- activates, so just place it.
		local spawn_pos = minetest.pointed_thing_to_face_pos(user, pointed_thing)
		minetest.add_entity(spawn_pos, "anpc_dev:cat")
	end
})
