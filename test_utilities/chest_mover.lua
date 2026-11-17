-- Chest mover: a simple test NPC.
-- Finds two chests within a radius and moves all items from the
-- non-empty one into the other - but the items pass through the NPC's
-- own inventory: each stack is removed from the source chest and
-- put into the NPC, then unloaded from the NPC into the destination
-- chest. This exercises every npc:inv:* form: get/put/remove with
-- pos (node inventory) and without (own inventory), inv:list, and the
-- leftover handling of put (add_item) and remove.
--
-- Nothing is lost: if the NPC's inventory fills up mid-load (or the
-- destination chest fills up mid-unload), the leftover goes back into
-- the slot it came from and the loop stops. One-shot: queued by the
-- spawner, runs to completion, then the NPC just stands.
--
-- Jump semantics used below (verified against the interpreter): an
-- offset jump at instruction N with pos=P lands at N + P + 1, i.e. P is
-- the number of instructions skipped (negative to loop back).

npc.proc.register_program("chest_mover:run", {
	{key = "@local.chests", name = "npc:env:node:find", args = {radius = "@args.radius", nodenames = {"default:chest"}}, srcmap = 1},
	{name = "npc:debug", args = {msg = "chest_mover: chests found", val = "@local.chests.length"}, srcmap = 2},
	{name = "npc:jump_if", args = {expr = {left = "@local.chests.length", op = ">=", right = 2}, offset = true, negate = true, pos = 33}, srcmap = 3}, -- need 2+ chests, else stand down -> 37
	{key = "@local.items_a", name = "npc:inv:list", args = {pos = "@local.chests[1]"}, srcmap = 4},
	{name = "npc:jump_if", args = {expr = {left = "@local.items_a.length", op = ">", right = 0}, offset = true, negate = false, pos = 3}, srcmap = 5}, -- chest 1 non-empty: it is the source, skip the empty-case pair -> 9
	-- npc:var:set takes its target key INSIDE args (bare name, no
	-- "@local." prefix) - a top-level key is the RESULT slot and would
	-- leave args.key nil (crash in set_var).
	-- Exclusive if/else: one jump_if picks the branch, one npc:jump
	-- skips over the other branch's assignments. (A single fall-through
	-- overwrite left src pointing at the EMPTY chest when chest 1 was
	-- empty - the NPC walked there, "moved" nothing, and stood.)
	{name = "npc:var:set", args = {key = "src", value = "@local.chests[2]", storage_type = "local"}, srcmap = 6}, -- empty case
	{name = "npc:var:set", args = {key = "dst", value = "@local.chests[1]", storage_type = "local"}, srcmap = 7}, -- empty case
	{name = "npc:jump", args = {pos = 2, offset = true}, srcmap = 8}, -- empty case done: skip the non-empty pair -> 11 (offset REQUIRED - a bare pos is an ABSOLUTE target and loops back to #2)
	{name = "npc:var:set", args = {key = "src", value = "@local.chests[1]", storage_type = "local"}, srcmap = 9}, -- non-empty case
	{name = "npc:var:set", args = {key = "dst", value = "@local.chests[2]", storage_type = "local"}, srcmap = 10}, -- non-empty case
	{name = "npc:var:set", args = {key = "stop", value = 0, storage_type = "local"}, srcmap = 11},
	{key = "@local.access_src", name = "npc:env:node:get_accessing_pos", args = {pos = "@local.src", force = true}, srcmap = 12},
	{name = "npc:move:walk_to_pos", args = {target_pos = "@local.access_src", original_target_pos = "@local.src"}, srcmap = 13},
	{name = "npc:var:set", args = {key = "i", value = 1, storage_type = "local"}, srcmap = 14}, -- FOR start: load source chest into own inventory
	{key = "@local.item", name = "npc:inv:get", args = {pos = "@local.src", list = "main", index = "@local.i"}, srcmap = 15},
	{name = "npc:jump_if", args = {expr = {left = "@local.item", op = "~=", right = nil}, offset = true, negate = true, pos = 4}, srcmap = 16}, -- empty slot: stop -> 21
	{name = "npc:inv:remove", args = {pos = "@local.src", list = "main", index = "@local.i"}, srcmap = 17},
	{key = "@local.left", name = "npc:inv:put", args = {item = "@local.item"}, srcmap = 18}, -- into OWN inventory (add_item -> leftover)
	{name = "npc:jump_if", args = {expr = {left = "@local.left", op = "~=", right = nil}, offset = true, negate = true, pos = 2}, srcmap = 19}, -- no leftover: continue -> 22
	{name = "npc:inv:put", args = {pos = "@local.src", list = "main", index = "@local.i", item = "@local.left"}, srcmap = 20}, -- own full: put the leftover back in its origin slot
	{name = "npc:var:set", args = {key = "stop", value = 1, storage_type = "local"}, srcmap = 21},
	{name = "npc:var:set", args = {key = "i", value = {left = "@local.i", op = "+", right = 1}, storage_type = "local"}, srcmap = 22},
	{name = "npc:jump_if", args = {expr = {left = {left = "@local.i", op = "<=", right = 32}, op = "&&", right = {left = "@local.stop", op = "==", right = 0}}, offset = true, negate = false, pos = -9}, srcmap = 23}, -- FOR end -> 15
	{key = "@local.access_dst", name = "npc:env:node:get_accessing_pos", args = {pos = "@local.dst", force = true}, srcmap = 24},
	{name = "npc:move:walk_to_pos", args = {target_pos = "@local.access_dst", original_target_pos = "@local.dst"}, srcmap = 25},
	{name = "npc:var:set", args = {key = "stop", value = 0, storage_type = "local"}, srcmap = 26}, -- reset for the second loop
	{name = "npc:var:set", args = {key = "j", value = 1, storage_type = "local"}, srcmap = 27}, -- FOR start: unload own inventory into destination chest
	{key = "@local.item", name = "npc:inv:get", args = {list = "main", index = "@local.j"}, srcmap = 28}, -- own inventory
	{name = "npc:jump_if", args = {expr = {left = "@local.item", op = "~=", right = nil}, offset = true, negate = true, pos = 4}, srcmap = 29}, -- empty slot: stop -> 34
	{name = "npc:inv:remove", args = {list = "main", index = "@local.j"}, srcmap = 30}, -- own inventory
	{key = "@local.left", name = "npc:inv:put", args = {pos = "@local.dst", list = "main", item = "@local.item"}, srcmap = 31}, -- into destination chest (add_item -> leftover)
	{name = "npc:jump_if", args = {expr = {left = "@local.left", op = "~=", right = nil}, offset = true, negate = true, pos = 2}, srcmap = 32}, -- no leftover: continue -> 35
	{name = "npc:inv:put", args = {list = "main", index = "@local.j", item = "@local.left"}, srcmap = 33}, -- dst full: leftover back into own slot
	{name = "npc:var:set", args = {key = "stop", value = 1, storage_type = "local"}, srcmap = 34},
	{name = "npc:var:set", args = {key = "j", value = {left = "@local.j", op = "+", right = 1}, storage_type = "local"}, srcmap = 35},
	{name = "npc:jump_if", args = {expr = {left = {left = "@local.j", op = "<=", right = 32}, op = "&&", right = {left = "@local.stop", op = "==", right = 0}}, offset = true, negate = false, pos = -9}, srcmap = 36}, -- FOR end -> 28
	{name = "npc:move:stand", srcmap = 37},
})

minetest.register_craftitem("anpc_dev:chest_mover_spawner", {
	description = "Chest Mover Spawner",
	inventory_image = "default_chest_front.png",
	on_use = function(itemstack, user, pointed_thing)
		if not pointed_thing or not pointed_thing.under then
			minetest.log("anpc_dev:chest_mover_spawner: no valid pointed position, ignoring use")
			return itemstack
		end
		local spawn_pos = minetest.pointed_thing_to_face_pos(user, pointed_thing)
		local entity = minetest.add_entity(spawn_pos, "anpc_dev:chest_mover_npc")
		if entity then
			minetest.log("anpc_dev:chest_mover_spawner: spawning chest mover")
			npc.proc.execute_program(entity:get_luaentity(), "chest_mover:run", {radius = 30})
		end
	end
})

minetest.register_entity("anpc_dev:chest_mover_npc", {
	hp_max = 1,
	visual = "mesh",
	mesh = "character_anpc.b3d",
	textures = {
		"default_male.png",
	},
	visual_size = {x = 1, y = 1, z = 1},
	-- This engine build rests the collision box 0.5 sunk into the
	-- supporting node; lift the model back to the node top.
	visual_offset = {x = 0, y = 0.5, z = 0},
	collisionbox = {-0.20,0,-0.20, 0.20,1.8,0.20},
	stepheight = 0.6,
	physical = true,
	on_activate = npc.on_activate,
	get_staticdata = npc.get_staticdata,
	on_deactivate = npc.on_deactivate,
	on_step = npc.do_step,
})
