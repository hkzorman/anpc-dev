npc.proc.register_program("vegetarian:init", {
	{name = "npc:var:set", args = {key = "hunger", value = 0, storage_type = "global"}, srcmap = 3}
})

npc.proc.register_program("vegetarian:idle", {
	{name = "npc:move:stand", args = {}, srcmap = 11},
	{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = 2}, storage_type = "global"}, srcmap = 12},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 60}, offset = true, negate = true, pos = 1, srcmap = 14}}, -- IF [3],
		{name = "npc:execute", args = {name = "vegetarian:feed"}, srcmap = 15},
	{name = "npc:jump_if", args = {expr = {left = "@time", op = ">=", right = 20000}, offset = true, negate = true, pos = 1, srcmap = 19}}, -- IF [5],
		{name = "npc:execute", args = {name = "vegetarian:sleep"}, srcmap = 20},
	{name = "npc:var:set", args = {key = "should_ack_obj", value = "false", storage_type = "local"}, srcmap = 23},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local", srcmap = 24}}, -- FOR start [8],
		{key = "@local._inline_npc:random0", name = "npc:random", args = {start = 1, ["end"] = 100}},
		{name = "npc:jump_if", args = {expr = {left = "@local._inline_npc:random0", op = ">=", right = {left = 100, op = "-", right = "@args.ack_nearby_objs_chance"}}, offset = true, negate = true, pos = 4, srcmap = 25}}, -- IF [2],
			{name = "npc:var:set", args = {key = "obj", value = "@objs.get[@local.for_index]", storage_type = "local"}, srcmap = 26},
			{name = "npc:jump_if", args = {expr = {left = "@local.obj", op = "~=", right = nil}, offset = true, negate = true, pos = 2, srcmap = 27}}, -- IF [2],
				{key = "@local.dist", name = "npc:distance_to", args = {object = "@local.obj"}, srcmap = 28},
				{name = "npc:var:set", args = {key = "should_ack_obj", value = {left = {left = "@local.dist", op = "<=", right = "@args.ack_nearby_objs_dist"}, op = "&&", right = {left = "@local.dist", op = ">", right = 0}}, storage_type = "local"}, srcmap = 29},
		{name = "npc:jump_if", args = {expr = {left = "@local.should_ack_obj", op = "==", right = true}, offset = true, negate = true, pos = 9, srcmap = 33}}, -- IF [7],
			{key = "@local.ack_times", name = "npc:random", args = {start = 15, ["end"] = 30}, srcmap = 34},
			{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local", srcmap = 35}}, -- FOR start [2],
				{key = "@local.obj_pos", name = "npc:obj:get_pos", args = {object = "@local.obj"}, srcmap = 36},
				{name = "npc:move:rotate", args = {target_pos = "@local.obj_pos"}, srcmap = 37},
			{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local", srcmap = 35}},
			{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@local.ack_times"}, negate = false, offset = true, pos = -4, srcmap = 35}}, -- FOR end [6],
			{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = {left = "@local.ack_times", op = "*", right = 2}}, storage_type = "global"}, srcmap = 39},
			{name = "npc:break", srcmap = 40},
		{name = "npc:jump", args = {offset = true, pos = 3, srcmap = 41}}, -- ELSE [16],
			{key = "@local._inline_npc:random0", name = "npc:random", args = {start = 1, ["end"] = 10}},
			{name = "npc:jump_if", args = {expr = {left = "@local._inline_npc:random0", op = "<=", right = 5}, offset = true, negate = true, pos = 1, srcmap = 42}}, -- IF [2],
				{name = "npc:execute", args = {name = "vegetarian:wander"}, srcmap = 43},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local", srcmap = 24}},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@objs.all.length"}, negate = false, offset = true, pos = -21, srcmap = 24}}, -- FOR end [29]
})

npc.proc.register_program("vegetarian:wander", {
	{name = "npc:var:set", args = {key = "prev_dir", value = -1, storage_type = "local"}, srcmap = 52},
	{key = "@local._inline_npc:random0", name = "npc:random", args = {start = 1, ["end"] = 5}},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local", srcmap = 53}}, -- FOR start [3],
		{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}, srcmap = 54},
			{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}, srcmap = 56},
		{name = "npc:jump_if", args = {expr = {left = "@local.cardinal_dir", op = "==", right = "@local.prev_dir"}, negate = false, offset = true, pos = -2, srcmap = 55}}, -- WHILE end [3],
		{name = "npc:var:set", args = {key = "prev_dir", value = "@local.cardinal_dir", storage_type = "local"}, srcmap = 58},
		{name = "npc:move:walk", args = {cardinal_dir = "@local.cardinal_dir"}, srcmap = 59},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local", srcmap = 53}},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<", right = "@local._inline_npc:random0"}, negate = false, offset = true, pos = -7, srcmap = 53}}, -- FOR end [10],
	{name = "npc:move:stand", args = {}, srcmap = 61}
})

npc.proc.register_program("vegetarian:sleep", {
	{key = "@local.bed_pos", name = "npc:env:node:find", args = {matches = "single", radius = 35, nodenames = {"beds:bed_bottom"}, nodenames = {"beds:bed_bottom"}}, srcmap = 65},
	{name = "npc:jump_if", args = {expr = {left = "@local.bed_pos.length", op = ">", right = 0}, offset = true, negate = true, pos = 7, srcmap = 66}}, -- IF [2],
		{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.bed_pos[1]"}, args = {pos = "@local.bed_pos[1]"}}, srcmap = 67},
		{name = "npc:env:node:operate", args = {pos = "@local.bed_pos[1]"}, srcmap = 68},
			{key = "_prev_proc_int", name = "npc:get_proc_interval"},
			{name = "npc:set_proc_interval", args = {wait_time = 30, value = {left = 30, op = "-", right = "@local._prev_proc_int"}}},
			{name = "npc:set_proc_interval", args = {value = "@local._prev_proc_int"}},
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, negate = false, offset = true, pos = -4, srcmap = 69}}, -- WHILE end [6],
		{name = "npc:var:set", args = {key = "hunger", value = 60, storage_type = "global"}, srcmap = 72}
})

npc.proc.register_program("vegetarian:feed", {
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<=", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, offset = true, negate = true, pos = 1, srcmap = 80}}, -- IF [1],
			{name = "npc:exit"},
		{key = "@local.nodes", name = "npc:env:node:find", args = {radius = 5, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}}, srcmap = 84},
		{name = "npc:jump_if", args = {expr = {left = "@local.nodes.length", op = ">", right = 0}, offset = true, negate = true, pos = 6, srcmap = 85}}, -- IF [4],
			{key = "@local.random_index", name = "npc:random", args = {start = 1, ["end"] = "@local.nodes.length"}, srcmap = 86},
			{name = "npc:var:set", args = {key = "chosen_node", value = "@local.nodes[@local.random_index]", storage_type = "local"}, srcmap = 87},
			{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.chosen_node", force_accessing_node = true}, args = {pos = "@local.chosen_node", force_accessing_node = true}}, srcmap = 88},
			{name = "npc:env:node:dig", args = {pos = "@local.chosen_node"}, srcmap = 89},
			{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "-", right = 10}, storage_type = "global"}, srcmap = 90},
		{name = "npc:jump", args = {offset = true, pos = 1, srcmap = 91}}, -- ELSE [10],
			{name = "npc:execute", args = {name = "vegetarian:wander"}, srcmap = 92},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 0}, negate = false, offset = true, pos = -12, srcmap = 77}}, -- WHILE end [12]
})

npc.proc.register_program("vegetarian:own", {
	{name = "npc:env:nodes:set_owned", args = {value = "@args.value", pos = "@args.pos", categories = "@args.categories"}, srcmap = 98}
})

npc.proc.register_program("vegetarian:walk_to_owned", {
	{key = "@local.target_node", name = "npc:env:node:store:get", args = {only_one = true, categories = "@args.categories"}, srcmap = 102},
	{name = "npc:jump_if", args = {expr = {left = "@local.target_node", op = "~=", right = nil}, offset = true, negate = true, pos = 1, srcmap = 103}}, -- IF [2],
		{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.target_node.pos", force_accessing_node = true}, args = {pos = "@local.target_node.pos", force_accessing_node = true}}, srcmap = 104}
})

