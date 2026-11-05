-- anpc_dev targets
-- (C) by Zorman2000 aka hkzorman
--
-- Test-rig nodes + idle program for validating NPC navigation:
--
--   anpc_dev:target_red   solid block the NPC climbs/jumps ON TOP of
--   anpc_dev:target_blue  solid block the NPC walks to and stops 1 node away
--
--   anpc_dev:search_for_target  idle program:
--     * scans (core.find_node_near, nearest match) for placed targets
--       every 0.5 s (radius = @args.radius, default: the NPC's view_range)
--     * red has priority: the NPC walks to the cell ON TOP of the nearest
--       red block (the nav jumps a 1-block step)
--     * blue: executes the built-in npc:walk_to_pos program with forced
--       access resolution, which walks the NPC to the closest walkable
--       cell next to the block, i.e. it stops 1 node away
--     * when a walk finishes the engine resumes this (state) program and
--       the scan starts again
--
-- Arguments (all optional):
--   radius = number   scan radius (default: the NPC's view_range)
--
-- NOTE: the stock npc:env:node:find cannot be used for the scan: its
-- single_match branch (core.find_node_near) is clobbered by the trailing
-- unconditional minetest.find_nodes_in_area call, which throws on nil
-- min/max. Hence the small find_nearest helper below.
--
-- Placement constraints (pathfinder limits, jump_height = 1):
--   * the top of a red block must be at most 1 block above the ground the
--     NPC walks on (place it on the ground; a 2-high stack is unreachable)
--   * a blue block needs at least one open neighbour cell at its top level,
--     otherwise the access walk has no destination and the scan retries

-----------------------------------------------------------------------------------
-- Nodes
-----------------------------------------------------------------------------------

minetest.register_node("anpc_dev:target_red", {
	description = "ANPC Target (Red): NPC climbs on top",
	tiles = {"anpc_dev_target_red.png"},
	walkable = true,
	groups = {cracky = 3}
})

minetest.register_node("anpc_dev:target_blue", {
	description = "ANPC Target (Blue): NPC stops 1 node away",
	tiles = {"anpc_dev_target_blue.png"},
	walkable = true,
	groups = {cracky = 3}
})

-----------------------------------------------------------------------------------
-- Nearest-node scan instruction
-----------------------------------------------------------------------------------
-- Returns the single nearest matching node position, or nil.
npc.proc.register_instruction("anpc_dev:env:node:find_nearest", function(self, args)
	local start_pos = args.pos or vector.round(self.object:get_pos())
	local radius = args.radius or self.data.env.view_range
	return minetest.find_node_near(start_pos, radius, args.nodenames)
end)

-----------------------------------------------------------------------------------
-- anpc_dev:search_for_target
-----------------------------------------------------------------------------------
-- Instruction map (1-based):
--   1  set_proc_interval 0.5
--   2  red_pos   = find_nearest(target_red)
--   3  jump_if red_pos ~= nil -> 7
--   4  blue_pos  = find_nearest(target_blue)
--   5  jump_if blue_pos ~= nil -> 13
--   6  jump -> 2                          (no target: rescan)
--   7  red_top   = red_pos + (0,1,0)
--   8  red_done  = walk_to_pos(target_pos = red_top)   [move instruction]
--   9  jump_if red_done == nil (negate) -> 11          (nil falls to 10)
--   10 jump -> 2                          (no path: rescan, retried next scan)
--   11 jump_if red_done == false -> 2     (still walking: re-scan. The walk
--                                          is driven by the low-latency task
--                                          and re-arms with the same target;
--                                          scanning here is the only escape
--                                          if the red node is removed
--                                          mid-walk, because the now-empty
--                                          target cell still pathfinds and
--                                          the walk would never fail.)
--   12 jump -> 2                          (arrived on top: rescan)
--   13 execute npc:walk_to_pos(pos = blue_pos, force_accessing_node = true,
--                              access_node_search_method = "prefer_closest")
--      (on program end the engine restarts this state program: rescan)
--
-- NOTE on jump offsets: a npc:jump / npc:jump_if with offset = true is
-- followed by an extra +1 inside npc.proc.execute_instruction (control
-- flow instructions execute the next instruction immediately, before
-- do_step's own +1), so an offset of `pos` taken from instruction C
-- executes instruction C + 1 + pos. To land on target T from C:
-- pos = T - C - 1. (Same rule as the built-in npc:walk_to_pos re-arm:
-- from 6 with pos = -4 lands on the walk at 3.)
npc.proc.register_program("anpc_dev:search_for_target", {
	{name = "npc:set_proc_interval", args = {value = 0.5}, srcmap = 1},

	{key = "@local.red_pos", name = "anpc_dev:env:node:find_nearest",
		args = {nodenames = {"anpc_dev:target_red"}, radius = "@args.radius"}, srcmap = 2},

	{name = "npc:jump_if", args = {expr = {left = "@local.red_pos", op = "~=", right = nil},
		offset = true, negate = false, pos = 3}, srcmap = 3},

	{key = "@local.blue_pos", name = "anpc_dev:env:node:find_nearest",
		args = {nodenames = {"anpc_dev:target_blue"}, radius = "@args.radius"}, srcmap = 4},

	{name = "npc:jump_if", args = {expr = {left = "@local.blue_pos", op = "~=", right = nil},
		offset = true, negate = false, pos = 7}, srcmap = 5},

	{name = "npc:jump", args = {offset = true, pos = -5}, srcmap = 6},

	-- The red goal is the cell ON TOP of the block. The built-in
	-- npc:walk_to_pos program cannot be used for it: get_accessing_pos
	-- flattens the target to the NPC's height and a solid there resolves
	-- to a SIDE cell. So walk the top cell directly.
	{key = "@local.red_top", name = "npc:util:vector:add",
		args = {x = "@local.red_pos", y = {x = 0, y = 1, z = 0}}, srcmap = 7},

	{key = "@local.red_done", name = "npc:move:walk_to_pos",
		args = {target_pos = "@local.red_top", original_target_pos = "@local.red_pos"}, srcmap = 8},

	{name = "npc:jump_if", args = {expr = {left = "@local.red_done", op = "==", right = nil},
		offset = true, negate = true, pos = 1}, srcmap = 9},

	{name = "npc:jump", args = {offset = true, pos = -9}, srcmap = 10},

	{name = "npc:jump_if", args = {expr = {left = "@local.red_done", op = "==", right = false},
		offset = true, negate = false, pos = -10}, srcmap = 11},

	{name = "npc:jump", args = {offset = true, pos = -11}, srcmap = 12},

	{name = "npc:execute", args = {name = "npc:walk_to_pos",
		args = {pos = "@local.blue_pos", force_accessing_node = true,
			access_node_search_method = "prefer_closest"}}, srcmap = 13},
})
