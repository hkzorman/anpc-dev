-- anpc_dev IDE bridge
--
-- Two-way bridge between a running Luanti server and the anpc IDE
-- backend (Python, same machine). Luanti has outbound-only HTTP
-- (secure.http_mods), so the bridge *polls*:
--
--   GET  <ide>/luanti/command   one JSON command per call ("null" = none)
--   POST <ide>/luanti/event     state reports, results, errors
--
-- Program storage: the IDE owns <world>/anpc_programs/
-- (manifest.txt + one .lua file per program). At boot the bridge reads
-- the manifest and executes each file with the pre-sandbox load(), so
-- the server always runs whatever the IDE last compiled.
--
-- manifest.txt format, one program per line:
--   <program name>  <file name>
-- (two columns, whitespace-separated; program names contain ':' which
-- is not a legal filename character on Windows, so the IDE chooses the
-- file name and the manifest is the single source of truth)
--
-- Server configuration (see README.md):
--   secure.http_mods    = anpc_dev   outbound HTTP
--   secure.trusted_mods = anpc_dev   pre-sandbox environment (file + load)
--
-- Without the trust flag the bridge runs degraded: NPC listing,
-- breakpoints and run control still work, but program files cannot be
-- read or executed (boot load skipped, load_program reports an error).
-- Without HTTP access at all, the bridge stays inactive.
--
-- This file is dofile'd from init.lua and returns one function, which
-- init.lua calls as ide_bridge(insecure_env, http_api). The security
-- APIs must be called at init.lua's own main scope (their
-- anti-spoofing check only passes from the mod's init top level), so
-- the results are passed in rather than requested here.
--
-- Commands (JSON, "op" selects the handler; responses arrive as events):
--   hello                        -> booted
--   load_program {name, code}    -> program_loaded
--   breakpoints {name, lines}    -> breakpoints_set
--   list_programs                -> programs
--   list_npcs                    -> npcs
--   spawn {entity, init, state, pos} -> spawned
--   spawn_near_player {entity, init, state} -> spawned
--   run {npc_id, program}        -> npc_state   (state program)
--   execute {npc_id, program}    -> npc_state   (one-shot program)
--   pause {npc_id}               -> npc_state
--   resume {npc_id}              -> resumed
--   stop {npc_id}                -> npc_state
--   unregister {name}            -> program_unregistered
--   vars {npc_id}                -> npc_vars
--   state                        -> npc_state
--
-- Events (JSON, posted to /luanti/event):
--   booted {trusted, http, programs, npcs,
--           breakpoints = {{name, breakpoints = {{index, srcmap}}}}}
--   programs {programs}
--   program_loaded {name, ok, error, instructions, programs}
--   program_unregistered {name, programs}
--   breakpoints_set {name, breakpoints = {{index, srcmap}}, missed = {lines}}
--   npcs {npcs}
--   npc_state {npcs}
--   npc_vars {npc_id, program, instruction, vars = {proc, global}}
--   spawned {npc_id, entity, pos}
--   paused {npc_id, entity, program, instruction, line}
--   resumed {npc_id}
--   error {op, message}
--
-- NPC record: {npc_id, entity, program, instruction, paused, pos}

return function(ie, http_api)
	local IDE_URL = "http://127.0.0.1:8765"
	local POLL_INTERVAL = 1 -- seconds

	-- ie: insecure environment (nil = mod not trusted -> degraded)
	-- http_api: HTTP API table (nil = no HTTP access -> inactive)

	local programs_dir = core.get_worldpath() .. DIR_DELIM .. "anpc_programs"

	local function log(msg)
		minetest.log("anpc_dev| IDE bridge: " .. msg)
	end

	-----------------------------------------------------------------------------------
	-- Program files
	-----------------------------------------------------------------------------------

	local function read_file(path)
		if ie == nil then return nil end
		local f, err = ie.io.open(path, "r")
		if not f then
			log("cannot read " .. path .. ": " .. tostring(err))
			return nil
		end
		local data = f:read("*a")
		f:close()
		return data
	end

	-- Execute compiled program code (a chunk of register_program calls).
	-- Returns ok, error_message.
	local function load_program_code(code)
		if ie == nil then
			return false, "mod not in secure.trusted_mods - cannot execute program code"
		end
		local chunk, err = ie.load(code)
		if type(chunk) ~= "function" then
			return false, tostring(err)
		end
		local ok, err2 = pcall(chunk)
		if not ok then
			return false, tostring(err2)
		end
		return true
	end

	-- Boot load: read the manifest, execute every listed program file.
	-- One bad file must not break the others.
	local function boot_load()
		if ie == nil then
			log("not trusted (secure.trusted_mods missing) - program file loading disabled")
			return
		end
		local manifest = read_file(programs_dir .. DIR_DELIM .. "manifest.txt")
		if manifest == nil then
			return -- IDE has not written any programs yet
		end
		local loaded, failed = 0, 0
		for line in manifest:gmatch("[^\r\n]+") do
			local name, filename = line:match("^%s*(.-)%s+(.-)%s*$")
			if name and filename then
				local code = read_file(programs_dir .. DIR_DELIM .. filename)
				local ok, err
				if code == nil then
					ok, err = false, "file not found: " .. filename
				else
					ok, err = load_program_code(code)
				end
				if ok then
					loaded = loaded + 1
				else
					failed = failed + 1
					log("failed to load '" .. name .. "' (" .. filename .. "): " .. tostring(err))
				end
			else
				log("bad manifest line: " .. line)
			end
		end
		log("boot load: " .. loaded .. " program(s) loaded, " .. failed .. " failed")
	end

	-----------------------------------------------------------------------------------
	-- NPC introspection
	-----------------------------------------------------------------------------------

	local function list_programs()
		local names = {}
		for name in pairs(npc.proc.program_table or {}) do
			names[#names + 1] = name
		end
		table.sort(names)
		return names
	end

	-- 5.18 has no get_objects(); the area query below is the equivalent
	-- (the world box is finite; +/-32767 covers any real world).
	local WORLD_MIN = { x = -32767, y = -32767, z = -32767 }
	local WORLD_MAX = { x = 32767, y = 32767, z = 32767 }

	-- The luaentity *instance* (get_luaentity returns the instance in
	-- this engine, so npc_id/process/debug are readable directly on it).
	local function each_npc(fn)
		for _, ref in ipairs(core.get_objects_in_area(WORLD_MIN, WORLD_MAX)) do
			local ent = ref:get_luaentity()
			if ent and ent.npc_id ~= nil then
				fn(ent)
			end
		end
	end

	local function find_npc(npc_id)
		local found
		each_npc(function(ent)
			if ent.npc_id == npc_id then
				found = ent
			end
		end)
		return found
	end

	-- 5.18 ObjectRef has no get_name(); resolve the entity type via
	-- the registered-entity table the instance's metatable points to.
	-- Built lazily on first use: that happens after all mods have
	-- finished loading (the poll loop only runs via core.after).
	local entity_names
	local function entity_name(ent)
		if entity_names == nil then
			entity_names = {}
			for name, props in pairs(core.registered_entities or {}) do
				entity_names[props] = name
			end
		end
		return entity_names[getmetatable(ent)]
	end

	local function npc_record(ent)
		local p = ent.process
		local pos
		local ok, pos2 = pcall(function() return ent.object:get_pos() end)
		if ok and pos2 then
			pos = {
				x = math.floor(pos2.x * 1000) / 1000,
				y = math.floor(pos2.y * 1000) / 1000,
				z = math.floor(pos2.z * 1000) / 1000
			}
		end
		return {
			npc_id = ent.npc_id,
			entity = entity_name(ent),
			program = p.current.name,
			instruction = p.current.instruction,
			paused = ent.debug and ent.debug.pause == true,
			pos = pos
		}
	end

	local function list_npcs()
		local npcs = {}
		each_npc(function(ent)
			npcs[#npcs + 1] = npc_record(ent)
		end)
		return npcs
	end

	-- Source line of the NPC's current instruction (nil when unknown).
	local function current_line(ent)
		local p = ent.process
		local program = npc.proc.program_table and npc.proc.program_table[p.current.name]
		local instruction = program and program.instructions[p.current.instruction]
		return instruction and instruction.srcmap or nil
	end

	-----------------------------------------------------------------------------------
	-- Events
	-----------------------------------------------------------------------------------

	local function post_event(event)
		if http_api == nil then
			return
		end
		local ok, err = pcall(function()
			http_api.fetch({
				url = IDE_URL .. "/luanti/event",
				method = "POST",
				data = minetest.write_json(event),
				extra_headers = { "Content-Type: application/json" },
				user_agent = "anpc-dev-ide-bridge/1",
				quiet = true,
				timeout = 5,
			}, function() end)
		end)
		if not ok then
			log("event post failed: " .. tostring(err))
		end
	end

	local function post_error(op, message)
		log(op .. ": " .. message)
		post_event({ type = "error", op = op, message = message })
	end

	-----------------------------------------------------------------------------------
	-- Run control helpers
	-----------------------------------------------------------------------------------

	-- Unpause an NPC, stepping over a breakpoint that stopped it (the
	-- engine's "override" flag; the engine clears it after the next pass,
	-- so the breakpoint stays armed for future hits).
	local function release_pause(ent)
		local p = ent.process
		local program = npc.proc.program_table and npc.proc.program_table[p.current.name]
		local instruction = program and program.instructions[p.current.instruction]
		if instruction and instruction.pause == true then
			instruction.override = true
		end
		if ent.debug then
			ent.debug.pause = false
		end
	end

	-----------------------------------------------------------------------------------
	-- Command handlers
	-----------------------------------------------------------------------------------

	-- Shared spawn logic; posts the "spawned" event on success.
	local function spawn_npc(entity, init, state, pos, op)
		local unknown
		for _, prog in ipairs({ init, state }) do
			if prog ~= nil and npc.proc.program_table[prog] == nil then
				unknown = prog
				break
			end
		end
		if unknown ~= nil then
			return post_error(op, "unknown program: " .. tostring(unknown))
		end
		local ref = minetest.add_entity(pos, entity)
		if not ref or not ref:is_valid() then
			return post_error(op, "add_entity failed for " .. tostring(entity))
		end
		local ent = ref:get_luaentity()
		-- State first, then init: set_state_process(clear_queue=true)
		-- would wipe a just-queued init. A fresh entity's queue holds
		-- only self-initialization work from on_activate, which must
		-- run, so do not clear it here.
		if state ~= nil then
			npc.proc.set_state_process(ent, state, nil, false)
		end
		if init ~= nil then
			npc.proc.execute_program(ent, init)
		end
		post_event({
			type = "spawned",
			npc_id = ent.npc_id,
			entity = entity,
			pos = npc_record(ent).pos
		})
	end

	local handlers = {

		hello = function(cmd)
			-- Include armed breakpoints so an IDE backend restart
			-- (which keeps no in-memory state) can restore the gutter
			-- marks. Empty per program => omitted.
			local bps = {}
			for _, name in ipairs(list_programs()) do
				local list = npc.proc.list_breakpoints(name)
				if #list > 0 then
					bps[#bps + 1] = { name = name, breakpoints = list }
				end
			end
			post_event({
				type = "booted",
				trusted = ie ~= nil,
				http = true,
				programs = list_programs(),
				npcs = list_npcs(),
				breakpoints = bps
			})
		end,

		load_program = function(cmd)
			local ok, err = load_program_code(cmd.code)
			local program = npc.proc.program_table[cmd.name]
			post_event({
				type = "program_loaded",
				name = cmd.name,
				ok = ok,
				error = err,
				instructions = program and #program.instructions or nil,
				programs = list_programs()
			})
		end,

		breakpoints = function(cmd)
			local program = npc.proc.program_table[cmd.name]
			if program == nil then
				return post_error("breakpoints", "unknown program: " .. tostring(cmd.name))
			end
			local resolved, missed = {}, {}
			for _, line in ipairs(cmd.lines or {}) do
				local idx
				for i = 1, #program.instructions do
					if program.instructions[i].srcmap == line then
						idx = i
						break
					end
				end
				if idx then
					resolved[#resolved + 1] = idx
				else
					missed[#missed + 1] = line
				end
			end
			npc.proc.clear_breakpoints(cmd.name)
			for _, idx in ipairs(resolved) do
				npc.proc.set_breakpoint(cmd.name, idx, true)
			end
			post_event({
				type = "breakpoints_set",
				name = cmd.name,
				breakpoints = npc.proc.list_breakpoints(cmd.name),
				missed = missed
			})
		end,

		list_programs = function(cmd)
			post_event({ type = "programs", programs = list_programs() })
		end,

		list_npcs = function(cmd)
			post_event({ type = "npcs", npcs = list_npcs() })
		end,

		spawn = function(cmd)
			local pos = cmd.pos
			if pos == nil then
				return post_error("spawn", "pos is required (5.18 has no world-spawn API)")
			end
			spawn_npc(cmd.entity, cmd.init, cmd.state, pos, "spawn")
		end,

		-- "Spawn next to me": beside the first connected player
		-- (5.18 has no world-spawn API; the IDE can always pass an
		-- explicit pos via "spawn" instead).
		spawn_near_player = function(cmd)
			local players = core.get_connected_players()
			if #players == 0 then
				return post_error("spawn_near_player", "no players connected")
			end
			local p = players[1]:get_pos()
			spawn_npc(cmd.entity, cmd.init, cmd.state,
				{x = p.x + 1.5, y = p.y, z = p.z}, "spawn_near_player")
		end,

		run = function(cmd)
			local ent = find_npc(cmd.npc_id)
			if ent == nil then
				return post_error("run", "unknown npc: " .. tostring(cmd.npc_id))
			end
			if npc.proc.program_table[cmd.program] == nil then
				return post_error("run", "unknown program: " .. tostring(cmd.program))
			end
			release_pause(ent)
			-- clear_queue: a fresh run from the IDE starts clean
			npc.proc.set_state_process(ent, cmd.program, nil, true)
			-- A fresh run also starts at the default step cadence:
			-- one-shot programs may change it (cat:nap sets 30 s and
			-- only restores 0.5 s when morning comes), so a run after
			-- an interrupted nap would otherwise inherit the 30 s.
			ent.timers.proc_int = 0.5
			post_event({ type = "npc_state", npcs = { npc_record(ent) } })
		end,

		-- Execute a one-shot program (queued in front of the others;
		-- the state program is untouched). This is how init/helper
		-- programs run from the IDE.
		execute = function(cmd)
			local ent = find_npc(cmd.npc_id)
			if ent == nil then
				return post_error("execute", "unknown npc: " .. tostring(cmd.npc_id))
			end
			if npc.proc.program_table[cmd.program] == nil then
				return post_error("execute", "unknown program: " .. tostring(cmd.program))
			end
			npc.proc.execute_program(ent, cmd.program)
			post_event({ type = "npc_state", npcs = { npc_record(ent) } })
		end,

		pause = function(cmd)
			local ent = find_npc(cmd.npc_id)
			if ent == nil then
				return post_error("pause", "unknown npc: " .. tostring(cmd.npc_id))
			end
			if ent.debug then
				ent.debug.pause = true
			end
			post_event({ type = "npc_state", npcs = { npc_record(ent) } })
		end,

		resume = function(cmd)
			local ent = find_npc(cmd.npc_id)
			if ent == nil then
				return post_error("resume", "unknown npc: " .. tostring(cmd.npc_id))
			end
			release_pause(ent)
			-- Confirmation is an npc_state like the other control ops;
			-- the "resumed" event itself comes from transition polling
			-- (a second post here would duplicate it).
			post_event({ type = "npc_state", npcs = { npc_record(ent) } })
		end,

		-- Stop all programs on the NPC (state, queue and current process).
		stop = function(cmd)
			local ent = find_npc(cmd.npc_id)
			if ent == nil then
				return post_error("stop", "unknown npc: " .. tostring(cmd.npc_id))
			end
			release_pause(ent)
			local p = ent.process
			p.state.id = -1
			p.state.name = nil
			p.current = { id = -1, name = nil, args = {}, instruction = -1 }
			p.queue = {}
			p.queue_head = 1
			p.queue_tail = 0
			-- A hard stop also resets the step interval (same nap
			-- hazard as run above).
			ent.timers.proc_int = 0.5
			post_event({ type = "npc_state", npcs = { npc_record(ent) } })
		end,

		-- Remove a program from the running server (IDE delete). Refused
		-- while any NPC is running it, has it queued, or it is their
		-- state program: an in-flight process faults on its
		-- program_table lookup if the program disappears under it.
		unregister = function(cmd)
			if npc.proc.program_table[cmd.name] == nil then
				return post_error("unregister", "unknown program: " .. tostring(cmd.name))
			end
			local in_use = {}
			each_npc(function(ent)
				local p = ent.process
				local busy = (p.current and p.current.name == cmd.name)
					or (p.state and p.state.name == cmd.name)
				if not busy then
					for i = 1, p.queue_tail or 0 do
						if p.queue[i] and p.queue[i].name == cmd.name then
							busy = true
							break
						end
					end
				end
				if busy then
					in_use[#in_use + 1] = ent.npc_id
				end
			end)
			if #in_use > 0 then
				return post_error("unregister",
					"in use by " .. table.concat(in_use, ", "))
			end
			npc.proc.unregister_program(cmd.name)
			post_event({
				type = "program_unregistered",
				name = cmd.name,
				programs = list_programs()
			})
		end,

		-- The selected NPC's variable storage (IDE watch panel):
		-- proc = the current process's locals, global = global vars.
		-- Values are plain JSON (tables/strings/numbers/bools); userdata
		-- is stored as tracking records or itemstrings, so it serializes.
		vars = function(cmd)
			local ent = find_npc(cmd.npc_id)
			if ent == nil then
				return post_error("vars", "unknown npc: " .. tostring(cmd.npc_id))
			end
			local p = ent.process
			local cur_id = p.current and p.current.id
			local proc_vars = (ent.data and ent.data.proc and cur_id ~= nil)
				and ent.data.proc[cur_id] or {}
			local global_vars = (ent.data and ent.data.global) or {}
			post_event({
				type = "npc_vars",
				npc_id = ent.npc_id,
				program = p.current and p.current.name,
				instruction = p.current and p.current.instruction,
				vars = { proc = proc_vars, global = global_vars }
			})
		end,

		state = function(cmd)
			post_event({ type = "npc_state", npcs = list_npcs() })
		end
	}

	-----------------------------------------------------------------------------------
	-- Poll loop (core.after is the only timer primitive in 5.18)
	-----------------------------------------------------------------------------------

	local busy = false

	-- Liveness ping: the SPA's staleness detector queues a hello only
	-- after the bridge goes SILENT (server restart / down), so on a quiet
	-- world the bridge must prove it is alive: one cheap event per 30 s.
	local alive_acc = 0

	-- Track debug.pause transitions so the IDE is told when an NPC hits
	-- a breakpoint (false -> true) or is resumed (true -> false).
	local last_pause = {}

	local function poll_pause_transitions()
		local seen = {}
		each_npc(function(ent)
			local id = ent.npc_id
			seen[id] = true
			local paused = ent.debug and ent.debug.pause == true or false
			local was = last_pause[id]
			if was == false and paused then
				post_event({
					type = "paused",
					npc_id = id,
					entity = npc_record(ent).entity,
					program = ent.process.current.name,
					instruction = ent.process.current.instruction,
					line = current_line(ent)
				})
			elseif was == true and not paused then
				post_event({ type = "resumed", npc_id = id })
			end
			last_pause[id] = paused
		end)
		for id in pairs(last_pause) do
			if not seen[id] then
				last_pause[id] = nil -- NPC gone
			end
		end
	end

	local function poll()
		-- Liveness tick (runs even while a fetch is in flight): one
		-- "alive" event per 30 s. post_event is a no-op without HTTP.
		alive_acc = alive_acc + POLL_INTERVAL
		if alive_acc >= 30 then
			alive_acc = 0
			post_event({ type = "alive" })
		end
		local ok, err = pcall(function()
			poll_pause_transitions()
			if busy or http_api == nil then
				return
			end
			busy = true
			http_api.fetch({
				url = IDE_URL .. "/luanti/command",
				method = "GET",
				user_agent = "anpc-dev-ide-bridge/1",
				quiet = true,
				timeout = 5,
			}, function(res)
				busy = false
				if res and res.succeeded and res.data and res.data ~= "" then
					local cmd = minetest.parse_json(res.data)
					-- "null" = nothing queued; a real command is a table
					if cmd ~= nil then
						if type(cmd) == "table" and cmd.op ~= nil and handlers[cmd.op] then
							local ok2, err2 = pcall(handlers[cmd.op], cmd)
							if not ok2 then
								post_error(cmd.op, tostring(err2))
							end
						else
							log("unhandled command: " .. tostring(res.data))
						end
					end
				end
			end)
		end)
		if not ok then
			log("poll error: " .. tostring(err))
		end
	end

	local function schedule()
		core.after(POLL_INTERVAL, function()
			poll()
			schedule()
		end)
	end

	-----------------------------------------------------------------------------------
	-- Start
	-----------------------------------------------------------------------------------

	if npc == nil or npc.proc == nil then
		log("anpc core not found - bridge inactive")
	elseif http_api == nil then
		log("no HTTP access (secure.http_mods / secure.trusted_mods missing) - bridge inactive")
	else
		boot_load()
		log("started (trusted=" .. tostring(ie ~= nil) .. ", " .. IDE_URL .. ")")
		schedule()
	end
end
