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
		{name = "npc:execute", args = {name = "vegetarian:feed"}},
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
		{name = "npc:jump_if", args = {expr = {left = "@local.should_ack_obj", op = "==", right = true}, offset = true, negate = true, pos = 9}}, -- IF [7],
			{key = "@local.ack_times", name = "npc:random", args = {start = 15, ["end"] = 30}},
			{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}}, -- FOR start [2],
				{key = "@local.obj_pos", name = "npc:obj:get_pos", args = {object = "@local.obj"}},
				{name = "npc:move:rotate", args = {target_pos = "@local.obj_pos"}},
			{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}},
			{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@local.ack_times"}, negate = false, offset = true, pos = -4}}, -- FOR end [6],
			{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = {left = "@local.ack_times", op = "*", right = 2}}, storage_type = "global"}},
			{name = "npc:break"},
		{name = "npc:jump", args = {offset = true, pos = 3}}, -- ELSE [16],
			{key = "@local._inline0", name = "npc:random", args = {start = 1, ["end"] = 10}},
			{name = "npc:jump_if", args = {expr = {left = "@local._inline0", op = "<=", right = 5}, offset = true, negate = true, pos = 1}}, -- IF [2],
				{name = "npc:execute", args = {name = "vegetarian:wander"}},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@objs.all.length"}, negate = false, offset = true, pos = -21}}, -- FOR end [29]
})

npc.proc.register_program("vegetarian:wander", {
	{name = "npc:var:set", args = {key = "prev_dir", value = -1, storage_type = "local"}},
	{key = "@local._inline0", name = "npc:random", args = {start = 1, ["end"] = 5}},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}}, -- FOR start [3],
		{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}},
			{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}},
		{name = "npc:jump_if", args = {expr = {left = "@local.cardinal_dir", op = "==", right = "@local.prev_dir"}, negate = false, offset = true, pos = -2}}, -- WHILE end [3],
		{name = "npc:var:set", args = {key = "prev_dir", value = "@local.cardinal_dir", storage_type = "local"}},
		{name = "npc:move:walk", args = {cardinal_dir = "@local.cardinal_dir"}},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<", right = "@local._inline0"}, negate = false, offset = true, pos = -7}}, -- FOR end [10],
	{name = "npc:move:stand", args = {}}
})

npc.proc.register_program("vegetarian:sleep", {
	{key = "@local.bed_pos", name = "npc:env:node:find", args = {matches = "single", radius = 35, nodenames = {"beds:bed_bottom"}, nodenames = {"beds:bed_bottom"}}},
	{name = "npc:jump_if", args = {expr = {left = "@local.bed_pos.length", op = ">", right = 0}, offset = true, negate = true, pos = 7}}, -- IF [2],
		{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.bed_pos[1]"}, args = {pos = "@local.bed_pos[1]"}}},
		{name = "npc:env:node:operate", args = {pos = "@local.bed_pos[1]"}},
			{key = "_prev_proc_int", name = "npc:get_proc_interval"},
			{name = "npc:set_proc_interval", args = {wait_time = 30, value = {left = 30, op = "-", right = "@local._prev_proc_int"}}},
			{name = "npc:set_proc_interval", args = {value = "@local._prev_proc_int"}},
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, negate = false, offset = true, pos = -4}}, -- WHILE end [6],
		{name = "npc:var:set", args = {key = "hunger", value = 60, storage_type = "global"}}
})

npc.proc.register_program("vegetarian:feed", {
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<=", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, offset = true, negate = true, pos = 1}}, -- IF [1],
			{name = "npc:exit"},
		{key = "@local.nodes", name = "npc:env:node:find", args = {radius = 5, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}}},
		{name = "npc:jump_if", args = {expr = {left = "@local.nodes.length", op = ">", right = 0}, offset = true, negate = true, pos = 6}}, -- IF [4],
			{key = "@local.random_index", name = "npc:random", args = {start = 1, ["end"] = "@local.nodes.length"}},
			{name = "npc:var:set", args = {key = "chosen_node", value = "@local.nodes[@local.random_index]", storage_type = "local"}},
			{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.chosen_node", force_accessing_node = true}, args = {pos = "@local.chosen_node", force_accessing_node = true}}},
			{name = "npc:env:node:dig", args = {pos = "@local.chosen_node"}},
			{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "-", right = 10}, storage_type = "global"}},
		{name = "npc:jump", args = {offset = true, pos = 1}}, -- ELSE [10],
			{name = "npc:execute", args = {name = "vegetarian:wander"}},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 0}, negate = false, offset = true, pos = -12}}, -- WHILE end [12]
})

