# anpc-dev
Development documentation, tools and examples  for `anpc` Minetest mod.

For programming reference, please see [the API doc](https://github.com/hkzorman/anpc-dev/blob/main/programming_api.md)

## Included tools
### anpcscript-interpreter
A python script that converts a `*.anpcscript` file into a Lua file

### Debugger
The debugger is a tool to use in-game in Minetest, and allows you to inspect a NPC.

### Program editor
The program editor is a tool in-game in Minetest, that allows you to see and modify (not working yet) programs in-game.

### NPC model pipeline (`tools/anpc_model`)
Builds blocky b3d NPC models + skins + animation from one Python spec (the cat is the reference NPC). Also packaged as the `anpc Blocky Model` project skill (`.opencode/skills/anpc-blocky-model/`) — ask any LLM session to "make a golem NPC using the anpc Blocky Model skill" and it writes the spec, runs the build, verifies the output and generates the mod lua. See `tools/anpc_model/README.md` for details.
