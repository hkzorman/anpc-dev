npc.proc.register_program("vegetarian:init", {
	{name = "npc:var:set", args = {key = "hunger", value = 0, storage_type = "global"}, srcmap = 6},
	{name = "npc:execute", args = {name = "sedentary:build"}, srcmap = 7}
})

npc.proc.register_program("sedentary:build", {
	{name = "npc:var:set", args = {key = "walls_schematic", value = {{x=-1, y=0, z=0},{x=-2, y=0, z=0}, {x=-2, y=0, z=1},{x=-2, y=0, z=2}, {x=-2, y=0, z=3}, {x=-2, y=0, z=4},{x=-1, y=0, z=4},{x=0, y=0, z=4},{x=1, y=0, z=4},{x=2, y=0, z=4},{x=2, y=0, z=3},{x=2, y=0, z=2},{x=2, y=0, z=1},{x=2, y=0, z=0}, {x=1, y=0, z=0}}, storage_type = "local"}, srcmap = 18},
	{name = "npc:var:set", args = {key = "furnace_pos", value = {x=1, y=1, z=2}, storage_type = "local"}, srcmap = 19},
	{name = "npc:var:set", args = {key = "chest_pos", value = {x=1, y=1, z=3}, storage_type = "local"}, srcmap = 20},
	{name = "npc:var:set", args = {key = "bed_pos", value = {x=-1, y=1, z=2}, storage_type = "local"}, srcmap = 21},
	{key = "@local.nodes", name = "npc:env:node:find", args = {radius = 5, nodenames = {"default:diamondblock"}, nodenames = {"default:diamondblock"}}, srcmap = 23},
	{name = "npc:jump_if", args = {expr = {left = "@local.nodes.length", op = ">", right = 0}, offset = true, negate = true, pos = 23}, srcmap = 24}, -- IF [6],
		{key = "@local.random_index", name = "npc:random", args = {start = 1, ["end"] = "@local.nodes.length"}, srcmap = 25},
		{name = "npc:var:set", args = {key = "chosen_node", value = "@local.nodes[@local.random_index]", storage_type = "local"}, srcmap = 26},
		{name = "npc:move:walk_to_pos_ll", args = {target_pos = "@local.chosen_node", force_accessing_node = true}, srcmap = 27},
		{name = "npc:env:node:place", args = {pos = "@local.chosen_node", node = "doors:door_wood_a", param2 = 0}, srcmap = 30},
		{key = "@local.above", name = "npc:util:vector:add", args = {x = "@local.chosen_node", y = {x = 0, y = 1, z = 0}, y = {x = 0, y = 1, z = 0}}, srcmap = 31},
		{name = "npc:env:node:place", args = {pos = "@local.above", node = "doors:hidden", param2 = 0}, srcmap = 32},
		{name = "npc:var:set", args = {key = "start_y", value = 0, storage_type = "local"}, srcmap = 35},
			{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}, srcmap = 37}, -- FOR start [1],
				{name = "npc:var:set", args = {key = "schematic_pos", value = "@local.walls_schematic[@local.for_index]", storage_type = "local"}, srcmap = 38},
				{name = "npc:var:set", args = {key = "schematic_pos[y]", value = {left = "@local.schematic_pos[y]", op = "+", right = 1}, storage_type = "local"}, srcmap = 39},
				{key = "@local.next_pos", name = "npc:util:vector:add", args = {x = "@local.chosen_node", y = "@local.schematic_pos"}, srcmap = 40},
				{name = "npc:env:node:place", args = {pos = "@local.next_pos", node = "default:wood"}, srcmap = 42},
			{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}, srcmap = 37},
			{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@local.walls_schematic.length"}, negate = false, offset = true, pos = -6}, srcmap = 37}, -- FOR end [7],
			{name = "npc:var:set", args = {key = "start_y", value = {left = "@local.start_y", op = "+", right = 1}, storage_type = "local"}, srcmap = 44},
		{name = "npc:jump_if", args = {expr = {left = "@local.start_y", op = "<", right = 3}, negate = false, offset = true, pos = -9}, srcmap = 36}, -- WHILE end [16],
		{key = "@local.next_pos", name = "npc:util:vector:add", args = {x = "@local.chosen_node", y = "@local.bed_pos"}, srcmap = 48},
		{name = "npc:env:node:place", args = {pos = "@local.next_pos", node = "beds:bed_bottom"}, srcmap = 49},
		{key = "@local.next_pos", name = "npc:util:vector:add", args = {x = "@local.chosen_node", y = "@local.furnace_pos"}, srcmap = 50},
		{name = "npc:env:node:place", args = {pos = "@local.next_pos", node = "default:furnace"}, srcmap = 51},
		{key = "@local.next_pos", name = "npc:util:vector:add", args = {x = "@local.chosen_node", y = "@local.chest_pos"}, srcmap = 52},
		{name = "npc:env:node:place", args = {pos = "@local.next_pos", node = "default:chest"}, srcmap = 53},
	{name = "npc:jump", args = {offset = true, pos = 1}, srcmap = 54}, -- ELSE [29],
		{name = "npc:execute", args = {name = "vegetarian:wander"}, srcmap = 55}
})

npc.proc.register_program("vegetarian:idle", {
	{name = "npc:move:stand", args = {}, srcmap = 64},
	{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = 2}, storage_type = "global"}, srcmap = 65},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 60}, offset = true, negate = true, pos = 1}, srcmap = 67}, -- IF [3],
		{name = "npc:execute", args = {name = "vegetarian:feed"}, srcmap = 68},
	{name = "npc:jump_if", args = {expr = {left = "@time", op = ">=", right = 20000}, offset = true, negate = true, pos = 1}, srcmap = 72}, -- IF [5],
		{name = "npc:execute", args = {name = "vegetarian:sleep"}, srcmap = 73},
	{name = "npc:var:set", args = {key = "should_ack_obj", value = "false", storage_type = "local"}, srcmap = 76},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}, srcmap = 77}, -- FOR start [8],
		{key = "@local._inline_npc:random0", name = "npc:random", args = {start = 1, ["end"] = 100}},
		{name = "npc:jump_if", args = {expr = {left = "@local._inline_npc:random0", op = ">=", right = {left = 100, op = "-", right = "@args.ack_nearby_objs_chance"}}, offset = true, negate = true, pos = 4}, srcmap = 78}, -- IF [2],
			{name = "npc:var:set", args = {key = "obj", value = "@objs.get[@local.for_index]", storage_type = "local"}, srcmap = 79},
			{name = "npc:jump_if", args = {expr = {left = "@local.obj", op = "~=", right = nil}, offset = true, negate = true, pos = 2}, srcmap = 80}, -- IF [2],
				{key = "@local.dist", name = "npc:distance_to", args = {object = "@local.obj"}, srcmap = 81},
				{name = "npc:var:set", args = {key = "should_ack_obj", value = {left = {left = "@local.dist", op = "<=", right = "@args.ack_nearby_objs_dist"}, op = "&&", right = {left = "@local.dist", op = ">", right = 0}}, storage_type = "local"}, srcmap = 82},
		{name = "npc:jump_if", args = {expr = {left = "@local.should_ack_obj", op = "==", right = true}, offset = true, negate = true, pos = 9}, srcmap = 86}, -- IF [7],
			{key = "@local.ack_times", name = "npc:random", args = {start = 15, ["end"] = 30}, srcmap = 87},
			{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}, srcmap = 88}, -- FOR start [2],
				{key = "@local.obj_pos", name = "npc:obj:get_pos", args = {object = "@local.obj"}, srcmap = 89},
				{name = "npc:move:rotate", args = {target_pos = "@local.obj_pos"}, srcmap = 90},
			{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}, srcmap = 88},
			{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@local.ack_times"}, negate = false, offset = true, pos = -4}, srcmap = 88}, -- FOR end [6],
			{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "+", right = {left = "@local.ack_times", op = "*", right = 2}}, storage_type = "global"}, srcmap = 92},
			{name = "npc:break", srcmap = 93},
		{name = "npc:jump", args = {offset = true, pos = 3}, srcmap = 94}, -- ELSE [16],
			{key = "@local._inline_npc:random0", name = "npc:random", args = {start = 1, ["end"] = 10}},
			{name = "npc:jump_if", args = {expr = {left = "@local._inline_npc:random0", op = "<=", right = 5}, offset = true, negate = true, pos = 1}, srcmap = 95}, -- IF [2],
				{name = "npc:execute", args = {name = "vegetarian:wander"}, srcmap = 96},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}, srcmap = 77},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<=", right = "@objs.all.length"}, negate = false, offset = true, pos = -21}, srcmap = 77}, -- FOR end [29]
})

npc.proc.register_program("vegetarian:wander", {
	{name = "npc:var:set", args = {key = "prev_dir", value = -1, storage_type = "local"}, srcmap = 105},
	{key = "@local._inline_npc:random0", name = "npc:random", args = {start = 1, ["end"] = 5}},
	{name = "npc:var:set", args = {key = "for_index", value = 1, storage_type = "local"}, srcmap = 106}, -- FOR start [3],
		{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}, srcmap = 107},
			{key = "@local.cardinal_dir", name = "npc:random", args = {start = 0, ["end"] = 7}, srcmap = 109},
		{name = "npc:jump_if", args = {expr = {left = "@local.cardinal_dir", op = "==", right = "@local.prev_dir"}, negate = false, offset = true, pos = -2}, srcmap = 108}, -- WHILE end [3],
		{name = "npc:var:set", args = {key = "prev_dir", value = "@local.cardinal_dir", storage_type = "local"}, srcmap = 111},
		{name = "npc:move:walk", args = {cardinal_dir = "@local.cardinal_dir"}, srcmap = 112},
	{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = 1}, storage_type = "local"}, srcmap = 106},
	{name = "npc:jump_if", args = {expr = {left = "@local.for_index", op = "<", right = "@local._inline_npc:random0"}, negate = false, offset = true, pos = -7}, srcmap = 106}, -- FOR end [10],
	{name = "npc:move:stand", args = {}, srcmap = 114}
})

npc.proc.register_program("vegetarian:sleep", {
	{key = "@local.bed_pos", name = "npc:env:node:find", args = {matches = "single", radius = 35, nodenames = {"beds:bed_bottom"}, nodenames = {"beds:bed_bottom"}}, srcmap = 118},
	{name = "npc:jump_if", args = {expr = {left = "@local.bed_pos.length", op = ">", right = 0}, offset = true, negate = true, pos = 7}, srcmap = 119}, -- IF [2],
		{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.bed_pos[1]"}, args = {pos = "@local.bed_pos[1]"}}, srcmap = 120},
		{name = "npc:env:node:operate", args = {pos = "@local.bed_pos[1]"}, srcmap = 121},
			{key = "_prev_proc_int", name = "npc:get_proc_interval"},
			{name = "npc:set_proc_interval", args = {wait_time = 30, value = {left = 30, op = "-", right = "@local._prev_proc_int"}}},
			{name = "npc:set_proc_interval", args = {value = "@local._prev_proc_int"}},
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, negate = false, offset = true, pos = -4}, srcmap = 122}, -- WHILE end [6],
		{name = "npc:var:set", args = {key = "hunger", value = 60, storage_type = "global"}, srcmap = 125}
})

npc.proc.register_program("vegetarian:feed", {
		{name = "npc:jump_if", args = {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = "@time", op = "<=", right = 24000}}, op = "||", right = {left = "@time", op = "<", right = 6000}}, offset = true, negate = true, pos = 1}, srcmap = 133}, -- IF [1],
			{name = "npc:exit"},
		{key = "@local.nodes", name = "npc:env:node:find", args = {radius = 5, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}, nodenames = {"default:grass_1", "default:grass_2", "default:grass_3", "default:grass_4", "default:grass_5"}}, srcmap = 137},
		{name = "npc:jump_if", args = {expr = {left = "@local.nodes.length", op = ">", right = 0}, offset = true, negate = true, pos = 6}, srcmap = 138}, -- IF [4],
			{key = "@local.random_index", name = "npc:random", args = {start = 1, ["end"] = "@local.nodes.length"}, srcmap = 139},
			{name = "npc:var:set", args = {key = "chosen_node", value = "@local.nodes[@local.random_index]", storage_type = "local"}, srcmap = 140},
			{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.chosen_node", force_accessing_node = true}, args = {pos = "@local.chosen_node", force_accessing_node = true}}, srcmap = 141},
			{name = "npc:env:node:dig", args = {pos = "@local.chosen_node"}, srcmap = 142},
			{name = "npc:var:set", args = {key = "hunger", value = {left = "@global.hunger", op = "-", right = 10}, storage_type = "global"}, srcmap = 143},
		{name = "npc:jump", args = {offset = true, pos = 1}, srcmap = 144}, -- ELSE [10],
			{name = "npc:execute", args = {name = "vegetarian:wander"}, srcmap = 145},
	{name = "npc:jump_if", args = {expr = {left = "@global.hunger", op = ">=", right = 0}, negate = false, offset = true, pos = -12}, srcmap = 130}, -- WHILE end [12]
})

npc.proc.register_program("vegetarian:own", {
	{name = "npc:env:nodes:set_owned", args = {value = "@args.value", pos = "@args.pos", categories = "@args.categories"}, srcmap = 151}
})

npc.proc.register_program("vegetarian:walk_to_owned", {
	{key = "@local.target_node", name = "npc:env:node:store:get", args = {only_one = true, categories = "@args.categories"}, srcmap = 155},
	{name = "npc:jump_if", args = {expr = {left = "@local.target_node", op = "~=", right = nil}, offset = true, negate = true, pos = 1}, srcmap = 156}, -- IF [2],
		{name = "npc:execute", args = {name = "npc:walk_to_pos", args = {pos = "@local.target_node.pos", force_accessing_node = true}, args = {pos = "@local.target_node.pos", force_accessing_node = true}}, srcmap = 157}
})

