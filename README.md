# anpc-dev
Development documentation, tools and examples  for `anpc` Minetest mod.

For programming reference, please see [the API doc](https://github.com/hkzorman/anpc-dev/blob/main/programming_api.md)

## Web IDE

The IDE for authoring, running and debugging anpc programs against a
*running* Luanti server. Programs are written in anpcscript, compiled
to Lua by `anpc_compiler.py`, saved by the IDE into the world, and
registered + executed inside the server by the `ide_bridge` component
of this mod. The IDE backend is a single Python process that also
serves the web UI (editor + compiler + debug panel).

### Server setup

The bridge needs two settings in the **server** configuration (the
conf file passed to `luanti --server`, e.g. `server.conf`):

    secure.http_mods    = anpc_dev
    secure.trusted_mods = anpc_dev

- `secure.http_mods` lets the mod make outbound HTTP requests. Luanti
  has no inbound server sockets, so the bridge *polls* the IDE
  (`GET /luanti/command` about once per second) and reports back with
  `POST /luanti/event`.
- `secure.trusted_mods` lets the mod obtain the pre-sandbox Lua
  environment (`core.request_insecure_environment`). That is how it
  reads the program files from the world directory and executes the
  compiled code with `load(string)` - both of which the normal mod
  sandbox blocks.

Both settings name `anpc_dev` explicitly; no other mod is affected.
The trust flag is a real security exception: with it, `anpc_dev` can
execute code it reads from the world directory. Keep the world and the
IDE on machines you trust with server access.

Degraded behavior when a setting is missing:

- no `secure.http_mods` -> the bridge stays inactive (no polling)
- no `secure.trusted_mods` -> the bridge runs degraded: listing NPCs,
  breakpoints and run control still work, but program files cannot be
  read or executed (boot load is skipped, `load_program` reports an error)

### Program files

Programs live in the world, not in the mod:

    <world>/anpc_programs/
        manifest.txt   one program per line:  <program name>  <file name>
        <file name>    compiled Lua (calls npc.proc.register_program)

The IDE owns this directory: it writes `manifest.txt` and the compiled
files. On boot the bridge reads the manifest and registers every
listed program, so the world runs whatever the IDE last compiled.
(Program names contain ':' which is not a legal file name on Windows,
hence the two-column manifest.)

## Included tools
### anpcscript-interpreter
A python script that converts a `*.anpcscript` file into a Lua file

### Debugger
The debugger is a tool to use in-game in Minetest, and allows you to inspect a NPC.

### Program editor
The program editor is a tool in-game in Minetest, that allows you to see and modify (not working yet) programs in-game.

### NPC model pipeline (`tools/anpc_model`)
Builds blocky b3d NPC models + skins + animation from one Python spec (the cat is the reference NPC). Also packaged as the `anpc Blocky Model` project skill (`.opencode/skills/anpc-blocky-model/`) — ask any LLM session to "make a golem NPC using the anpc Blocky Model skill" and it writes the spec, runs the build, verifies the output and generates the mod lua. See `tools/anpc_model/README.md` for details.
