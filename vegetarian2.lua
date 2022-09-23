npc.proc.register_program("vegetarian:init", {
	{name = "npc:var:set", args = {key = "@global.hunger", value = 0}}
})

npc.proc.register_program("vegetarian:idle", {
	{name = "npc:move:stand", args = {}},
	{name = "npc:var:set", args = {key = "@global.hunger", value = {left = "@global.hunger", op = "+", right = 2}}},
	{name = "npc:if", {expr = {left = "@global.hunger", op = ">=", right = 60}, true_instructions = {
		{name = "npc:set_state_process", args = {name = "vegetarian:feed"}}
	},
	{name = "npc:if", {expr = {left = "@time", op = ">=", right = 20000}, true_instructions = {
		{name = "npc:execute", args = {name = "vegetarian:sleep"}}
	},
	{name = "npc:var:set", args = {key = "@local.should_ack_obj", value = false}},
	{name = "npc:for", {initial_value = 1, step_increase =  1, expr = {left = "@local.for_index", op = "<=", right = "@table.length.@objs.all"}, loop_instructions = {
		{name = "npc:if", {expr = {left = "@random.1.100", op = ">=", right = {left = 100, op = "-", right = "@args.ack_nearby_objs_chance"}}, true_instructions = {
			{name = "npc:var:set", args = {key = "@local.obj", value = @objs.@local.for_index}},
			{name = "npc:if", {expr = @local.obj ~= nil, true_instructions = {
				{key = "@local.dist", name = "npc:distance_to", args = {object = "@local.obj"}},
				{name = "npc:var:set", args = {key = "@local.should_ack_obj", value = {left = {left = "@local.dist", op = "<=", right = "@args.ack_nearby_objs_dist"}, op = "&&", right = {left = "@local.dist", op = ">", right = 0}}}}
			}
		},
		{name = "npc:if", {expr = {left = "@local.should_ack_obj", op = "==", right = true}, true_instructions = {
			{name = "npc:for", {initial_value = 1, step_increase =  1, expr = {left = "@local.for_index", op = "<=", right = "@random.15.30"}, loop_instructions = {
				{key = "@local.obj_pos", name = "npc:obj:get_pos", args = {object = "@local.obj"}},
				{name = "npc:move:rotate", args = {target_pos = "@loca.obj_pos"}}
			},
			{name = "npc:break"}
		},
		false_instructions = {
			{name = "npc:if", {expr = {left = "@random.1.10", op = "<=", right = 2}, true_instructions = {
				{name = "npc:move:walk", args = {cardinal_pos = "@random.1.7"}},
				{name = "npc:move:stand", args = {}}
			}
		}
	}
})

npc.proc.register_program("vegetarian:sleep", {
	{key = "@local.bed_pos", name = "npc:env:node:find", args = {matches = "single", radius = 35, nodenames = {"beds:bed_bottom"}}},
	{name = "npc:if", {expr = @local.bed_pos ~= nil, true_instructions = {
		{name = "npc:execute", args = {name = "builtin:walk_to_pos", args = {end_pos}}
	},
	{name = "npc:env:node:operate", args = {pos = "@local.bed_pos"}},
	{name = "npc:while", {expr = {left = {left = {left = "@time", op = ">", right = 20000}, op = "&&", right = {left = time, op = "<", right = 24000}}, op = "||", right = {left = time, op = "<", right = 6000}}, loop_instructions = {
		{name = "npc:wait", args = {time = 30}}  776t
	},
	{name = "npc:var:set", args = {key = "@global.hunger", value = 60}},
	{name = "npc:set_state_process", args = {name = "vegetarian:idle", args = {ack_nearby_objs, ack_nearby_objs_dist = 4, ack_nearby_objs_chance = 50}}}
})

