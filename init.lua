-- anpc_dev tools
-- (C) by Zorman2000 aka hkzorman

npc_dev = {}
npc_dev.source = ""
npc_dev.target = {}

local program_name_list = {}

local env = minetest.request_insecure_environment()

minetest.register_craftitem("anpc_dev:debugger", {
	description = "ANPC Debugger\n(Punch NPC with tool equipped to use)",
	inventory_image = "default_apple.png",
	on_use = function(itemstack, user, pointed_thing)
		if pointed_thing.type == "object" then
		
			local entity_ref = pointed_thing.ref
			npc_dev.source = user
			npc_dev.target = entity_ref
			npc.set_debug(entity_ref:get_luaentity(), true)
		
			--local entitydata = minetest.formspec_escape(dump(pointed_thing.ref:get_luaentity()))
			--minetest.log(dump(pointed_thing.ref:get_luaentity()))
			--minetest.show_formspec(user:get_player_name(), "anpc_dev:debugger", formspec)
			
			npc_dev.show_debug_formspec(user, entity_ref)
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

npc_dev.show_debug_formspec = function(player, entity_ref)

	local entity = entity_ref:get_luaentity()
	local execute_btn_label = ""
	if not entity.debug.pause then execute_btn_label = "Pause" else execute_btn_label = "Run" end
	local current_program = entity.process.current.name
	local current_instruction = entity.process.current.instruction
	
	local data_section = ""
	if entity.debug.pause then
		local data = minetest.formspec_escape(dump(entity.data))
		data_section = "textarea[0.25,1.5;5.5,10;;;"..data.."]"
	end
	
	local instruction_names = ""
	local args = ""
	
	if current_program then
		--minetest.log(dump(npc.proc.program_table[current_program]))
		for index, instr in pairs(npc.proc.program_table[current_program].instructions) do
			instruction_names = instruction_names..index..","..minetest.formspec_escape(instr.name)..","
		end
		
		if current_instruction then
			local instruction = npc.proc.program_table[current_program].instructions[current_instruction]
			if instruction and instruction.args then
				for k,v in pairs(instruction.args) do
					if type(v) == "table" then
						-- TODO: Support expression objects
						-- TODO: Support viewing object args in the screen with separate textarea
						v = "object"	
					end
					args = args..minetest.formspec_escape(k..": "..tostring(v))..","
				end
			end
		end
		--minetest.log("Instruction names: "..dump(instruction_names))
	end
	--
		
	local entitydata = minetest.formspec_escape(dump(entity_ref:get_luaentity()))

	local program_names = ""
	for program_name, instr_list in pairs(npc.proc.program_table) do
		table.insert(program_name_list, program_name)
		program_names = program_names..minetest.formspec_escape(program_name)..","
	end

	--minetest.log(dump(entity.process.current))
	--local current_instruction = entity.process.current.

	local formspec = table.concat({
		"size[18,12,true]",
		"real_coordinates[true]",
		-- Top toolbar
		"button[0.25,0.25;3,0.5;execute;"..execute_btn_label.."]",
		"label[12,0.25;Proc Interval]",
		"field[15,0.25;0.75,0.5;proc_interval;;]",
		"button_exit[16.5,0.25;1.25,0.5;exit_btn;Close]",
		-- Data
		data_section,
		--"textarea[0.25,1.75;5,6;;Memory;"..entitydata.."]",
		-- Process
		"label[8,1.5;"..dump(current_program).."]",
		"label[12,1.5;Instr pointer: "..dump(current_instruction).."]",
		"tablecolumns[text,width=2.0;text]",
		"table[8,1.75;4.5,10;instructions;"..instruction_names..";"..current_instruction.."]",
		-- Garbage
		"textlist[12.75,1.75;5,10;arguments;"..args.."]",
		--"textarea[6,2.25;5.75,6;;"..dump(npc.proc.program_table[current_program]).."]",
		
	  },'')
	  
	  minetest.show_formspec(player:get_player_name(), "anpc_dev:debugger", formspec)

end

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
		"button_exit[14.25,9;2,0.75;exit_btn;Close]"
	  },'')
	  
	  minetest.show_formspec(player:get_player_name(), "anpc_dev:editor", formspec)
end

minetest.register_on_player_receive_fields(function(player, formname, fields)
	
	if formname == "anpc_dev:debugger" then
		minetest.log("Fields: "..dump(fields))
		if fields["execute"] then
			local interval = npc_dev.target:get_luaentity().timers.proc_int
			npc_dev.target:get_luaentity().debug.pause = not npc_dev.target:get_luaentity().debug.pause
			npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
		end
		
		-- Exit button
		if fields["quit"] == "true" then
			npc.set_debug(npc_dev.target:get_luaentity(), false)
			npc_dev.source = nil
			npc_dev.target = nil
		end
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


