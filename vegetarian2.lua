npc.proc.register_program("test", {
	{key = "@local.pos", name = "somegarbage", args = {pos = "@local.garb", avoid_g = true, donot_care = "@local.garbage"}},
	{name = "npc:var:set", args = {key = "@local.pos", value = "a"}},
	{name = "npc:var:set", args = {key = "@local.pos", value = @local.pos1 + 1}},
	{name = "npc:var:set", args = {key = "@local.pos", value = true}},
	{name = "npc:if", args = {expr = {left = "@local.nonsense", op = "==", right = "g"}, true_instructions = {
		{name = "executenonsense", args = {nonsense = "@local.nonsense"}}
	},
	false_instructions = {
		{name = "executesense", args = {}}
	},
	{name = "npc:while", args = {expr = function(self, args) return minetest.get_time_of_day() == 2000 end, loop_instructions = {
		{name = "haha", args = {}},
		{name = "npc:if", args = {expr = {left = "@local.pos", op = "==", right = "a"}, true_instructions = {
			{name = "hahahaha", args = {}},
			{name = "npc:break"}
		}
	},
	{name = "hahahahahaha", args = {}}
}, "/home/hfranqui/minetest/mods/anpc_dev/vegetarian.anpcscript")

npc.proc.register_program("feed", {
	{name = "npc:var:set", args = {key = "@local.do_something", value = false}},
	{name = "npc:while", args = {expr = {left = "@local.do_something", op = "==", right = true}, loop_instructions = {
		{name = "nothing_at_all", args = {something = false}}
	}
}, "/home/hfranqui/minetest/mods/anpc_dev/vegetarian.anpcscript")

