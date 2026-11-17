-- Test/debug utility items, extracted from anpc/api.lua (the old
-- "stuff for testing" section) during the test-code cleanup.
-- Names moved from "anpc:*" to "anpc_dev:*" because the engine
-- enforces the registering mod's name prefix; the player
-- inventories of the anpc-ai-test world were migrated to match.
-- (Old "anpc:*" items left in the world show as unknown objects.)
--
-- All four only act on anpc engine NPCs (the pointed object must
-- have the proc machinery set up by npc.on_activate).

minetest.register_craftitem("anpc_dev:npc_spawner", {
	description = "Spawner",
	inventory_image = "default_apple.png",
	on_use = function(itemstack, user, pointed_thing)
		local spawn_pos = minetest.pointed_thing_to_face_pos(user, pointed_thing)
		spawn_pos.y = spawn_pos.y
		local entity = minetest.add_entity(spawn_pos, "anpc:npc")
		if entity then
			npc.proc.set_state_process(entity:get_luaentity(), "builtin:idle", {
				ack_nearby_objs = true,
				ack_nearby_objs_dist = 4,
				ack_nearby_objs_chance = 50
			})
		else
			minetest.remove_entity(entity)
		end
	end
})

-- Follow test item: left-click an anpc NPC with it to make that NPC
-- follow the clicking player (runs the "npc:follow" state process,
-- block-middle walking, 2 cells behind, walking speed = the
-- player's walk speed minus 0.25 m/s with catch-up at 4 cells,
-- immediate door closing).
-- Left-click the same NPC with it again to stop following and
-- restore the NPC's previous state process. Only works on engine
-- NPCs (the pointed object must have the proc machinery).
minetest.register_craftitem("anpc_dev:follow_item", {
	description = "Follow (test)",
	inventory_image = "default_footprint.png",
	on_use = function(itemstack, user, pointed_thing)
		if user == nil or pointed_thing == nil
			or pointed_thing.type ~= "object" then
			return itemstack
		end
		local npc_ent = pointed_thing.ref:get_luaentity()
		-- Only engine NPCs: they have the data/process tables set up
		-- in npc.on_activate.
		if npc_ent == nil or npc_ent.data == nil
			or npc_ent.process == nil or npc_ent.process.state == nil then
			return itemstack
		end
		local state = npc_ent.process.state
		if state.name == "npc:follow" then
			-- Stop following: restore the previous state process.
			local prev = npc_ent.data.follow_prev_state
			npc_ent.data.follow_prev_state = nil
			if prev ~= nil and prev.name ~= nil then
				npc.proc.set_state_process(npc_ent, prev.name, prev.args, true)
			end
		else
			-- Start following the clicking player. The leader is
			-- resolved by player name each pass (@objs.get in the
			-- npc:follow program), so the NPC tracks the player even
			-- while the goal cell stays static for one walk.
			npc_ent.data.follow_prev_state = {
				name = state.name,
				args = state.args,
			}
			npc.proc.set_state_process(npc_ent, "npc:follow", {
				object = user:get_player_name(),
				follow_mode = "behind",
				follow_distance = 2,
			}, true)
		end
		return itemstack
	end
})

-- Punch test item: left-click an anpc NPC with it to make that NPC
-- punch the clicking player (5 m reach, so it works from a normal
-- click distance; the swing plays the model's mine_once animation
-- until a real "punch" animation is registered). Only works on
-- engine NPCs (the pointed object must have the proc machinery).
-- The result status is logged on the server.
minetest.register_craftitem("anpc_dev:punch_item", {
	description = "Punch (test)",
	inventory_image = "default_bow.png",
	on_use = function(itemstack, user, pointed_thing)
		if user == nil or pointed_thing == nil
			or pointed_thing.type ~= "object" then
			return itemstack
		end
		local npc_ent = pointed_thing.ref:get_luaentity()
		-- Only engine NPCs: they have the data/process tables set up
		-- in npc.on_activate.
		if npc_ent == nil or npc_ent.data == nil
			or npc_ent.process == nil or npc_ent.process.state == nil then
			return itemstack
		end
		local result = _npc.obj.punch(npc_ent, {
			name = user:get_player_name(),
			max_reach = 5,
		})
		minetest.log("[anpc] punch test: " .. tostring(result))
		return itemstack
	end
})

-- Inventory test item: left-click an anpc NPC with it to stock its
-- inventory - adds 5 default:wood to the main list (if none there
-- yet) and wields 1 (the hand list is data only in this build). The
-- uid, main-list contents and any leftover are logged on the server.
-- Used to verify the inventory round-trips across restarts.
minetest.register_craftitem("anpc_dev:inv_test_item", {
	description = "Inventory test (test)",
	inventory_image = "default_chest_locked.png",
	on_use = function(itemstack, user, pointed_thing)
		if user == nil or pointed_thing == nil
			or pointed_thing.type ~= "object" then
			return itemstack
		end
		local npc_ent = pointed_thing.ref:get_luaentity()
		-- Only engine NPCs: they have the data/process tables set up
		-- in npc.on_activate.
		if npc_ent == nil or npc_ent.data == nil
			or npc_ent.process == nil or npc_ent.process.state == nil then
			return itemstack
		end
		local inv = npc.inv.get(npc_ent)
		if inv == nil then
			minetest.log("[anpc] inv test: no inventory")
			return itemstack
		end
		local leftover
		if _npc.inv.contains(inv, "main", "default:wood", nil) ~= true then
			leftover = inv:add_item("main", _npc.inv.to_stack("default:wood 5"))
		end
		inv:set_stack("hand", 1, ItemStack("default:wood"))
		npc.inv.update_wield(npc_ent)
		local main = inv:get_list("main")
		local child = npc_ent.wield_visual
		local visual = "none"
		if child ~= nil and child:is_valid() then
			visual = "attached:" .. tostring((child:get_attach() or {}).bone or "?")
		end
		minetest.log("[anpc] inv test: uid=" .. tostring(npc_ent.data.inv.uid)
			.. " main_slots=" .. tostring(#main)
			.. " handedness=" .. tostring(npc_ent.data.global.handedness)
			.. " wield_visual=" .. visual
			.. " leftover=" .. (leftover ~= nil and leftover:to_string() or "none"))
		return itemstack
	end
})
