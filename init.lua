-- anpc_dev tools
-- (C) by Zorman2000 aka hkzorman

npc_dev = {}
npc_dev.source = ""
npc_dev.target = {}

local _npc_dev = {
	program_name_list = {},
	debugger = {
		selected_tab = 1,
		selected_instr_idx = 1,
		selected_arg_idx = 1,
		args_by_index = {},
		breakpoint_idxs = {}
	},
	selector = {
		selected_program = ""
	},
	table_editor = {
		keys_by_index = {},
		current_table = {},
		selected_idx = 1,
		supported_types = {
			"string",
			"number",
			"boolean",
			"table"
		}
	}
}

local env = minetest.request_insecure_environment()

minetest.register_craftitem("anpc_dev:debugger", {
	description = "ANPC Debugger\n(Punch NPC with tool equipped to use)",
	inventory_image = "debugger.png",
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
	if not entity.debug.pause then execute_btn_label = "pause.png" else execute_btn_label = "play.png" end
	local current_program = entity.process.current.name
	local current_instruction = entity.process.current.instruction
	
	-- Generate data tabs
	local data_section = ""
	if entity.debug.pause then
		local data = ""
		if _npc_dev.debugger.selected_tab == 1 then
			data = minetest.formspec_escape(dump(entity.data))
		elseif _npc_dev.debugger.selected_tab == 2 then
			data = minetest.formspec_escape(dump(entity.process))
		elseif _npc_dev.debugger.selected_tab == 3 then
			data = minetest.formspec_escape(dump(entity.timers))
		end
		
		data_section = table.concat({
			"tabheader[0.25,1.5;6,0.5;data_tabheader;Data,Process,Timers;1;false;true]",
			"textarea[0.25,1.5;6,10;;;"..data.."]"
		})
	end
	
	local instruction_names = ""
	local args = ""
	local args_section = ""
	
	-- Overrides current instruction if in pause mode
	local selected_instr = current_instruction
	if _npc_dev.debugger.selected_instr_idx > 0 and entity.debug.pause then
		selected_instr = _npc_dev.debugger.selected_instr_idx
	else
		_npc_dev.debugger.selected_instr_idx = -1
	end
	
	if current_program then
		--minetest.log(dump(npc.proc.program_table[current_program]))
		for index, instr in pairs(npc.proc.program_table[current_program].instructions) do
			local color = "#ffffff"
			local breakpoint = ""
			if instr.breakpoint == true then
				color = "#bf4040"
				breakpoint = "•"
			end
				
			instruction_names = instruction_names..color..","..breakpoint..","..index..","..minetest.formspec_escape(instr.name)..","
		end
		
		if selected_instr then
			local instruction = npc.proc.program_table[current_program].instructions[selected_instr]
			-- Generate args viewer
			if instruction then
			
				local instr_args = instruction.args
				_npc_dev.debugger.args_by_index = {}
		
				local keys = ""
				if instr_args and type(instr_args) == "table" then
					for k,v in pairs(instr_args) do
						table.insert(_npc_dev.debugger.args_by_index, k)
						if type(v) ~= "function" and type(v) ~= "userdata" then
							keys = keys..minetest.formspec_escape(k).." ("..type(v):sub(1,1).."),"
						end
					end
				end
				
				local selected_arg_idx = _npc_dev.debugger.selected_arg_idx
				
				-- Get editor for value
				local selected_key = _npc_dev.debugger.args_by_index[selected_arg_idx]
				minetest.log("Sekected key: "..dump(selected_key))
				local selected_val = minetest.write_json(instr_args[selected_key], true)
				
				local args_list_height = 10
				if entity.debug.pause then args_list_height = 5 end
				args_section = "textlist[12.75,1.75;5,"..args_list_height..";arguments;"..keys..";"..selected_arg_idx.."]"
				if entity.debug.pause then
					args_section = args_section.."textarea[12.75,6.75;5,5;;;"..selected_val.."]"
				end
			end
		end
	end
	--
		
	local entitydata = minetest.formspec_escape(dump(entity_ref:get_luaentity()))

	local program_names = ""
	for program_name, instr_list in pairs(npc.proc.program_table) do
		table.insert(_npc_dev.program_name_list, program_name)
		program_names = program_names..minetest.formspec_escape(program_name)..","
	end

	local formspec = table.concat({
		"size[18,12,true]",
		"real_coordinates[true]",
		-- Top toolbar
		"box[0,0;18,0.95;#c0c0c0]",
		"label[0.25,0.5;Debugger - "..entity.npc_id.."]",
		"image_button[3.5,0.1;0.75,0.75;"..execute_btn_label..";execute;]",
		"tooltip[execute;Click to run/pause current program]",
		"image_button[4.35,0.1;0.75,0.75;execute.png;exec_program;]",
		"tooltip[exec_program;Click to execute a program from the registered list]",
		"image_button[5.2,0.1;0.75,0.75;step_over.png;step_over;]",
		"tooltip[step_over;Click to execute current instruction and move to the next]",
		"label[13.25,0.5;Process Interval]",
		"field[15.75,0.25;0.75,0.5;proc_interval;;]",
		"image_button_exit[17.15,0.1;0.75,0.75;close.png;exit_btn;]",
		-- Data
		data_section,
		-- Process
		"label[8,1.5;"..dump(current_program).."]",
		"label[12,1.5;Instr pointer: "..dump(current_instruction).."]",
		"tablecolumns[color;text;text,width=2.0;text]",
		"table[8,1.75;4.5,10;instructions;"..instruction_names..";"..selected_instr.."]",
		args_section
	  },'')
	  
	  minetest.show_formspec(player:get_player_name(), "anpc_dev:debugger", formspec)

end

function show_editor_formspec(player, program_contents)
	_npc_dev.program_name_list = {}
	local program_names = ""
	for program_name, instr_list in pairs(npc.proc.program_table) do
		table.insert(_npc_dev.program_name_list, program_name)
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

function generate_program_selection_widget(x, y, w, h, selected_idx)

	program_name_list = {}
	local program_names = ""
	for program_name, instr_list in pairs(npc.proc.program_table) do
		table.insert(program_name_list, program_name)
		program_names = program_names..minetest.formspec_escape(program_name)..","
	end

	return "textlist["..x..","..y..";"..w..","..h..";program_list;"..program_names.."]"
end

function show_table_editor_dialog(player, selected_idx)
	minetest.show_formspec(player:get_player_name(), "anpc_dev:table_editor", generate_table_editor_widget(0.25, 0.25, 8, _npc_dev.table_editor.current_table, selected_idx))
end

function show_select_program_dialog(player)
	local formspec = table.concat({
		"size[10,9,true]",
		"real_coordinates[true]",
		"label[0.25,0.25;Select program and arguments]",
		generate_program_selection_widget(0.25, 0.75, 4.5, 7.25, 1),
		"label[5,0.25;Arguments]",
		"textarea[5,0.75;4.75,7.25;arguments;;]",
		"button_exit[5.5,8.25;2,0.5;cancel_btn;Cancel]",
		"button_exit[7.75,8.25;2,0.5;execute_btn;Execute]"
	  },'')
	minetest.show_formspec(player:get_player_name(), "anpc_dev:program_selector", formspec)
end

minetest.register_on_player_receive_fields(function(player, formname, fields)
	
	-- Handle signals for debugger screen
	if formname == "anpc_dev:debugger" then
		minetest.log("Fields: "..dump(fields))
		
		if fields["data_tabheader"] then
			_npc_dev.debugger.selected_tab = tonumber(fields["data_tabheader"])
			npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
		end
		
		if fields["execute"] then
			local entity = npc_dev.target:get_luaentity()
			-- Check if the current instruction has a breakpoint.
			-- If it does, we will not remove the breakpoint, but override it
			-- so execution can continue.
			if entity.debug.pause then
				local instruction = npc.proc.program_table[entity.process.current.name].instructions[entity.process.current.instruction]
				
				if instruction and instruction.breakpoint == true then
					instruction.override = true
				end
			end
			
			-- Toggle execution
			local interval = entity.timers.proc_int
			entity.debug.pause = not entity.debug.pause
			
			npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
		end
		
		if fields["step_over"] then
			local entity = npc_dev.target:get_luaentity()
			-- Check if the current instruction has a breakpoint.
			-- If it does, we will not remove the breakpoint, but override it
			-- so execution can continue.
			if entity.debug.pause then
				
				-- First, allow override of current instruction
				local current_instr_idx = entity.process.current.instruction
				local current_instruction = npc.proc.program_table[entity.process.current.name].instructions[current_instr_idx]
				
				if current_instruction.pause == true then
					current_instruction.override = true
				end
				
				-- Then, see if there are more instructions. If there is,
				-- the "pause" flag will be added 
				local next_instruction = npc.proc.program_table[entity.process.current.name].instructions[current_instr_idx + 1]
				if next_instruction ~= nil then
					next_instruction.paise = true
				end
				
				-- Finally remove the pause
				entity.debug.pause = true
				npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
			end
		end
		
		if fields["exec_program"] then
			npc.set_debug(npc_dev.target:get_luaentity(), false)			
			show_select_program_dialog(npc_dev.source)
		end
		
		-- Handle instructions table
		if fields["instructions"] then
			local event = minetest.explode_table_event(fields["instructions"])
			if event.type == "CHG" then
				_npc_dev.debugger.selected_instr_idx = event.row
				_npc_dev.debugger.selected_arg_idx = 1
			-- Double-clicking a row sets a 
			elseif event.type == "DCL" then
				local current_program = npc_dev.target:get_luaentity().process.current.name
				local instruction = npc.proc.program_table[current_program].instructions[event.row]
				if instruction.breakpoint == true then
					instruction.breakpoint = false
					instruction.pause = false
				else
					instruction.breakpoint = true
					instruction.pause = true
				end
			end
			
			npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
		end
		
		if fields["arguments"] then
			local event = minetest.explode_textlist_event(fields["arguments"])
			if event.type == "CHG" then
				_npc_dev.debugger.selected_arg_idx = event.index
				npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
			end
		end
		
		-- Exit button
		if fields["quit"] == "true" then
			npc.set_debug(npc_dev.target:get_luaentity(), false)
			npc_dev.source = nil
			npc_dev.target = nil
		end
	end
	
	-- Handle signal for editor screen
	if formname == "anpc_dev:editor" then
		if fields["program_list"] then
			local event = minetest.explode_textlist_event(fields["program_list"])
			if event.type == "DCL" then
				local program_name = program_name_list[event.index]
				
				local program = npc.proc.program_table[program_name]
				minetest.log(dump(program))
				local contents = dump(program.instructions)
				if not program.source_file then contents = "This program doesn't have an associated source code file. Please re-run interpreter with '--enable-debug' flag" end
				show_editor_formspec(player, contents)
				return
			end
		end
	end
	
	-- Handle signal for program selection dialog
	if formname == "anpc_dev:program_selector" then
		if fields["quit"] == "true" then
			-- Execute the program
			local self = npc_dev.target:get_luaentity()
			if fields["execute_btn"] then
				local processed_args = {}
				minetest.log(fields["arguments"])
				if fields["arguments"] then
					local args = minetest.deserialize(fields["arguments"]) or {}
					for arg_key,arg_value in pairs(args) do
						processed_args[arg_key] = npc.eval(
							self, arg_value, args, self.data.proc[self.process.current.id])
					end
					minetest.log("Processed args: "..dump(processed_args))
				end
				self.process.current.called_execute = true
				npc.proc.execute_program(self, _npc_dev.selector.selected_program, processed_args)
			end
			
			npc.set_debug(self, true)
			npc_dev.show_debug_formspec(npc_dev.source, npc_dev.target)
		end
		
		if fields["program_list"] then
			local event = minetest.explode_textlist_event(fields["program_list"])
			if event.type == "CHG" then
				_npc_dev.selector.selected_program = _npc_dev.program_name_list[event.index]
				minetest.log("Selected program: "..dump(_npc_dev.selector.selected_program))
				return
			end
		end
	end
end)

-- Relatively good stuff that could be used in the future
-- but it is a little overblown and not needed right now
--[[
-- Generates a table editor that supports editing tables
-- Doesn't show userdata or functions
function generate_table_editor_widget(x, y, h, table_obj, selected_idx)
	_npc_dev.table_editor.current_table = table_obj
	if not selected_idx then selected_idx = 1 end
	_npc_dev.table_editor.selected_idx = selected_idx
	
	local keys = ""
	if table_obj and type(table_obj) == "table" then
		for k,v in pairs(table_obj) do
			table.insert(_npc_dev.table_editor.keys_by_index, k)
			if type(v) ~= "function" and type(v) ~= "userdata" then
				keys = keys..minetest.formspec_escape(k).."("..type(v):sub(1,1).."),"
			end
		end
	end
	
	-- Get editor for value
	local selected_key = _npc_dev.table_editor.keys_by_index[selected_idx]
	local selected_val = minetest.write_json(table_obj[selected_key], true)
	local formspec = table.concat({
		"size[8.5,"..(h + 0.5).."]",
		"real_coordinates[true]",
		"container["..x..","..y.."]",
		"textlist[0,0;4,"..h..";keys;"..keys..";"..selected_idx.."]",
		"field[]",
		"button[4.1,0;3.9,0.75;add_key_btn;Add]",
		--"dropdown[4.1,0.85;3.9,0.75;string,number,boolean,table;]",
		"textarea[4.1,0.85;3.9,"..(h - 1.7)..";edited_value;;"..selected_val.."]",
		"button[4.1,"..(h - 0.75)..";1.9,0.75;set_value_btn;Set]",
		"button[6.1,"..(h - 0.75)..";1.9,0.75;del_key_btn;Delete]",
		"container_end[]"
	}, "")
	
	return formspec
end

function handle_table_editor_fields(player, fields)
	if fields["keys"] then
		local event = minetest.explode_textlist_event(fields["keys"])
		if event.type == "CHG" then
			_npc_dev.table_editor.selected_idx = event.index
			show_table_editor_dialog(player, event.index)
			--_npc_dev.selector.selected_program = _npc_dev.program_name_list[event.index]
			--minetest.log("Selected program: "..dump(_npc_dev.selector.selected_program))
			return
		end
	end
	
	if fields["set_value_btn"] then
		local key = _npc_dev.table_editor.keys_by_index[_npc_dev.table_editor.selected_idx]
		_npc_dev.table_editor.current_table[key] = minetest.parse_json(fields["edited_value"])
		show_table_editor_dialog(player, _npc_dev.table_editor.selected_idx) 
	end
	
	if fields["del_value_btn"] then
	end
end

minetest.register_craftitem("anpc_dev:table_editor", {
	description = "ANPC Table Editor\n(Punch anywhere to use)",
	inventory_image = "default_book.png",
	on_use = function(itemstack, user, pointed_thing)
		_npc_dev.table_editor.current_table = {
		key1 = "hello",
		key2 = 1,
		key3 = true,
		key4 = {
			subkey1 = "someg"
		}
	}
		show_table_editor_dialog(user)
	end
})

]]--
