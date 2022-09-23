npc.proc.register_program("vegetarian:init", {
	{name = "npc:var:set", args = {key = "hunger", value = 0, storage_type = "global"}}
})

npc.proc.register_program("vegetarian:get_hungry", {
		{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = 2}, storage_type = "global"}},
	{name = "npc:jump_if", args = {expr = {left = true, op = "==", right = true}, negate = false, offset = true, pos = -2}}, -- WHILE end [2]
})

npc.proc.register_program("vegetarian:idle", {
	{name = "npc:move:stand", args = {}},
	{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = 2}, storage_type = "global"}},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 60}, offset = true, negate = true, pos = 1}}, -- IF [3],
		{name = "npc:set_state_process", args = {name = "vegetarian:feed"}},
	{name = "npc:jump_if", args = {expr = {left = "@time", op = ">=", right = 20000}, offset = true, negate = true, pos = 1}}, -- IF [5],
		{name = "npc:execute", args = {name = "vegetarian:sleep"}},
	{name = "npc:var:set", args = {key = "should_ack_obj", value = "false", storage_type = "local"}},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}}, -- FOR start [8],
		{key = "@local._inline0", name = "npc:random", args = {start = 1, ["end"] = 100}},
		{name = "npc:jump_if", args = {expr = {left = "@local._inline0", op = ">=", right = {left = 100, op = "-", right = "@args.ack_nearby_objs_chance"}}, offset = true, negate = true, pos = 4}}, -- IF [2],
			{name = "npc:var:set", args = {key = "obj", value = "@objs.get[@local.for_index]", storage_type = "local"}},
			{name = "npc:jump_if", args = {expr = {left = "@local.obj", op = "~=", right = nil}, offset = true, negate = true, pos = 2}}, -- IF [2],
				{key = "@local.dist", name = "npc:distance_to", args = {object = "@local.obj"}},
				{name = "npc:var:set", args = {key = "should_ack_obj", value = {left = {left = "@local.dist", op = "<=", right = "@args.ack_nearby_objs_dist"}, op = "&&", right = {left = "@local.dist", op = ">", right = 0}}, storage_type = "local"}},
		{name = "npc:jump_if", args = {expr = {left = "@local.should_ack_obj", op = "==", right = true}, offset = true, negate = true, pos = 8}}, -- IF [7],
			{key = "@local._inline0", name = "npc:random", args = {start = 15, ["end"] = 30}},
			{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}}, -- FOR start [2],
				{key = "@local.obj_pos", name = "npc:obj:get_pos", args = {object = "@local.obj"}},
				{name = "npc:move:rotate", args = {target_pos = "@local.obj_pos"}},
			{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}},
			{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@local._inline0"}, negate = false, offset = true, pos = -4}}, -- FOR end [6],
			{name = "npc:break"},
		{name = "npc:jump", args = {offset = true, pos = 5}}, -- ELSE [15],
			{key = "@local._inline0", name = "npc:random", args = {start = 1, ["end"] = 10}},
			{name = "npc:jump_if", args = {expr = {left = "@local._inline0", op = "<=", right = 5}, offset = true, negate = true, pos = 3}}, -- IF [2],
				{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}},
				{name = "npc:move:walk", args = {cardinal_dir = "@local.cardinal_dir"}},
				{name = "npc:move:stand", args = {}},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@objs.all.length"}, negate = false, offset = true, pos = -22}}, -- FOR end [30]
})

npc.proc.register_program("vegetarian:sleep", {
	{key = "@local.bed_pos", name = "npc:env:node:find", args = {matches = "single", radius = 35, nodenames = {"beds:bed_bottom"}, nodenames = {"beds:bed_bottom"}}},
	{name = "npc:jump_if", args = {expr = {left = "@local.bed_pos", op = "~=", right = nil}, offset = true, negate = true, pos = 6}}, -- IF [2],
		{name = "npc:execute", args = {name = "builtin:walk_to_pos", args = {end_pos = "@local.bed_pos"}, args = {end_pos = "@local.bed_pos"}}},
		{name = "npc:env:node:operate", args = {pos = "@local.bed_pos"}},
			{name = "npc:wait", args = {time = 30}},
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, negate = false, offset = true, pos = -2}}, -- WHILE end [4],
		{name = "npc:var:set", args = {key = "hunger", value = 60, storage_type = "global"}},
		{name = "npc:set_state_process", args = {name = "vegetarian:idle", args = {ack_nearby_objs = true, ack_nearby_objs_dist = 4, ack_nearby_objs_chance = 50}, args = {ack_nearby_objs = true, ack_nearby_objs_dist = 4, ack_nearby_objs_chance = 50}}}
})

npc.proc.register_program("vegetarian:feed", {
	{key = "@local.nodes", name = "npc:env:node:find", args = {radius = 5, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}}},
	{name = "npc:jump_if", args = {expr = {left = "@local.nodes", op = ">", right = 0}, offset = true, negate = true, pos = 7}}, -- IF [2],
		{key = "@local.random_index", name = "npc:random", args = {start = 1, ["end"] = "@local.nodes.length"}},
		{name = "npc:var:set", args = {key = "chosen_node", value = "@local.nodes[@local.random_index]", storage_type = "local"}},
		{name = "npc:execute", args = {name = "builtin:walk_to_pos", args = {end_pos = "@local.chosen_node", force_accessing_node = true}, args = {end_pos = "@local.chosen_node", force_accessing_node = true}}},
		{name = "npc:env:node:dig", args = {pos = "@local.chosen_node"}},
		{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "-", right = 10}, storage_type = "global"}},
		{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = "<=", right = 0}, offset = true, negate = true, pos = 1}}, -- IF [6],
			{name = "npc:set_state_process", args = {name = "vegetarian:idle", args = {ack_nearby_objs = true, ack_nearby_objs_dist = 4, ack_nearby_objs_chance = 50}, args = {ack_nearby_objs = true, ack_nearby_objs_dist = 4, ack_nearby_objs_chance = 50}}}
})

