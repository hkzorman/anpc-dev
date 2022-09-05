-- anpc_dev tools
-- (C) by Zorman2000 aka hkzorman

local program_name_list = {}

local env = minetest.request_insecure_environment()

minetest.register_craftitem("anpc_dev:debugger", {
	description = "ANPC Debugger\n(Punch NPC with tool equipped to use)",
	inventory_image = "default_apple.png",
	on_use = function(itemstack, user, pointed_thing)
		if pointed_thing.type == "object" then
		
			local entitydata = minetest.formspec_escape(dump(pointed_thing.ref:get_luaentity()))
		
			local formspec = table.concat({
				"size[12,8,true]",
				"real_coordinates[true]",
				"textarea[0.25,0.75;11.5,6;all_data;NPC Data;"..entitydata.."]",
				"button_exit[9.75,7;2,0.75;;Done]"
			  },'')
			  
			  minetest.log(dump(pointed_thing.ref:get_luaentity()))
			  
			  minetest.show_formspec(user:get_player_name(), "anpc_dev:debugger", formspec)
		  
		
			--local meta = user:get_meta()
			--local pos = minetest.deserialize(meta:get_string("target_pos"))
			--npc.proc.execute_program(pointed_thing.ref:get_luaentity(), "vegetarian:own", {
			--	value = true,
			--	pos = pos, 
			--	categories = {"sign"}
			--})
			--minetest.log("self.data.env.nodes: "..dump(pointed_thing.ref:get_luaentity().data))
		elseif pointed_thing.type == "node" then
			local meta = user:get_meta()
			minetest.log("Pointed thing: "..dump(pointed_thing))
			minetest.log("The pointed: "..dump(minetest.get_node(pointed_thing.under)))
			meta:set_string("target_pos", minetest.serialize(pointed_thing.under))
		end
	end
})

minetest.register_craftitem("anpc_dev:program_editor", {
	description = "ANPC Program Editor\n(Punch anywhere to use)",
	inventory_image = "default_book.png",
	on_use = function(itemstack, user, pointed_thing)
		show_editor_formspec(user, nil)
	end
})

minetest.register_on_player_receive_fields(function(player, formname, fields)
	
	if formname == "anpc_dev:debugger" then
	
	end
	
	if formname == "anpc_dev:editor" then
		if fields["program_list"] then
			local event = minetest.explode_textlist_event(fields["program_list"])
			if event.type == "DCL" then
				local program_name = program_name_list[event.index]
				
				local program = npc.proc.program_table[program_name]
				local contents = dump(program.instructions)
				if not program.source_file then contents = "This program doesn't have an associated source code file. Please re-run interpreter with '--enable-debug' flag" end
				show_editor_formspec(player, contents)
				return
			end
		end
	end
end)

function show_editor_formspec(player, program_contents)
	program_name_list = {}
	local program_names = ""
	for program_name, instr_list in pairs(npc.proc.program_table) do
		table.insert(program_name_list, program_name)
		program_names = program_names..minetest.formspec_escape(program_name)..","
	end
	
	minetest.log("Program contents: "..dump(program_contents))
	
	local text_area_name = ""
	if not program_contents then
		text_area_name = ""
		program_contents = "Select a program from the list on the left to display here"
	end

	local formspec = table.concat({
		"size[16.5,10,true]",
		"real_coordinates[true]",
		"textlist[0.25,0.25;4,8.5;program_list;"..program_names.."]",
		"textarea[4.5,0.25;11.75,8.5;"..text_area_name..";;"..minetest.formspec_escape(program_contents).."]",
		"button_exit[14.25,9;2,0.75;;Close]"
	  },'')
	  
	  minetest.show_formspec(player:get_player_name(), "anpc_dev:editor", formspec)
end


