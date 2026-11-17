// anpc IDE - frontend
// Talks to the Python backend (same origin):
//   GET  /api/state, /api/program?name=      snapshots
//   POST /api/command, /api/save, /api/create
//   GET  /api/events                          SSE stream of bridge events
//
// Line mapping: the editor shows ONE program's block (local lines). The
// engine's srcmap stamps point into the whole .anpcscript file, so
// fileLine = blockStart + localLine - 1. All server breakpoint traffic
// uses file lines; the editor works in local lines.

"use strict";

const $ = (id) => document.getElementById(id);

let programs = [];       // [{name, file}]
let npcs = [];           // [{npc_id, entity, program, instruction, paused, pos}]
let booted = false;
let stateTs = 0;        // last state snapshot applied (stale-snapshot guard)
let open = null;         // {name, file, blockStart, instructions:[{no,name,srcmap,key}], lua}
let selectedNpc = null;
let pausedInfo = null;   // last "paused" event
let bpArmed = {};        // program -> Set of FILE lines (server-confirmed)
let bpPending = {};      // program -> Set of FILE lines (UI state, sent to server)

const editorTitle = $("editor-title");
const editorStatus = $("editor-status");
const saveBtn = $("save-btn");
const compiledEl = $("compiled");
const toastEl = $("toast");

// ---------------------------------------------------------------------------
// CodeMirror
// ---------------------------------------------------------------------------

const cm = CodeMirror($("cm"), {
	value: "-- select a program on the left",
	mode: "anpcscript",
	theme: "anpc",
	lineNumbers: true,
	gutters: ["CodeMirror-linenumbers", "bp"],
	indentWithTabs: true,
	tabSize: 4,
});
// CodeMirror 5: on(type, handler); the handler receives (cm, line, gutter).
cm.on("gutterClick", (cmObj, line, gutter) => {
	if (gutter === "bp") toggleBreakpoint(line);
});
cm.on("cursorActivity", () => {
	if (!open) return;
	const line = cm.getCursor().line;
	const rec = open.instructions[line];
	editorStatus.textContent = "line " + (line + 1) + (rec ? " \u00B7 instr " + rec.no : "");
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function get(path) {
	return fetch(path).then((r) => r.json());
}
function post(path, body) {
	return fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	}).then((r) => r.json());
}
let toastTimer = null;
function toast(msg, kind) {
	toastEl.textContent = msg;
	toastEl.className = "show" + (kind ? " " + kind : "");
	clearTimeout(toastTimer);
	toastTimer = setTimeout(() => { toastEl.className = ""; }, 4000);
}
function setServer(on) {
	$("server").className = "server-indicator" + (on ? " on" : "");
	$("server-text").textContent = on ? "server linked" : "no server";
}
function timeStr() {
	const d = new Date();
	return [d.getHours(), d.getMinutes(), d.getSeconds()]
		.map((n) => String(n).padStart(2, "0")).join(":");
}
function logEvent(ev, cls) {
	const li = document.createElement("li");
	if (cls) li.className = cls;
	const detail = {
		booted: "\u2014",
		program_loaded: (ev.ok ? "loaded " : "FAILED ") + ev.name + (ev.error ? " (" + ev.error + ")" : ""),
		breakpoints_set: ev.name + ": " + (ev.breakpoints || []).length + " armed"
			+ (ev.missed && ev.missed.length ? ", missed " + ev.missed.join(",") : ""),
		// minetest.write_json serializes empty tables as null (5.18)
		npcs: (ev.npcs || []).length + " npc(s)",
		npc_state: (ev.npcs || []).map((n) => n.npc_id).join(" "),
		paused: ev.npc_id + " @ " + ev.program + " instr " + ev.instruction + " line " + ev.line,
		resumed: ev.npc_id,
		spawned: ev.npc_id + " (" + ev.entity + ")",
		error: (ev.op || "") + " " + (ev.message || ""),
	}[ev.type] || "";
	li.innerHTML = '<span class="t">' + timeStr() + "</span>" + ev.type + " " + detail;
	const ol = $("events");
	ol.appendChild(li);
	while (ol.children.length > 150) ol.removeChild(ol.firstChild);
	ol.scrollTop = ol.scrollHeight;
}

// ---------------------------------------------------------------------------
// State + event stream
// ---------------------------------------------------------------------------

function applyState(s) {
	if (!s) return;
	if (s.ts != null && s.ts < stateTs) return;  // stale snapshot (late /api/state)
	if (s.ts != null) stateTs = s.ts;
	programs = s.programs || [];
	npcs = s.npcs || [];
	booted = !!s.booted;
	$("world").textContent = s.world || "";
	renderPrograms();
	renderNpcs();
	setServer(s.recent || s.booted);
}

function handleEvent(ev) {
	logEvent(ev, ev.type === "error" ? "err" : ev.type === "paused" ? "pause" : ev.ok === false ? "err" : "ok");
	switch (ev.type) {
		case "hello":
			applyState(ev.state);
			break;
		case "booted":
			// Merge: the server's program table includes core built-ins
			// (builtin:idle, npc:follow, ...) that the manifest does not.
			for (const n of ev.programs || []) if (!programs.some((p) => p.name === n))
				programs.push({ name: n, file: "" });
			programs.sort((a, b) => a.name.localeCompare(b.name));
			npcs = ev.npcs || [];
			booted = true;
			// Outlive a concurrent /api/state (same ts) so its manifest-only
			// list cannot clobber the merged one.
			stateTs = Math.max(stateTs, Date.now() / 1000);
			renderPrograms();
			renderNpcs();
			setServer(true);
			break;
		case "programs":
			for (const n of ev.programs || []) if (!programs.some((p) => p.name === n))
				programs.push({ name: n, file: "" });
			programs.sort((a, b) => a.name.localeCompare(b.name));
			renderPrograms();
			break;
		case "program_loaded":
			if (ev.ok) {
				toast("loaded " + ev.name + " on server", "ok");
				get("/api/state").then(applyState);
				if (open && open.name === ev.name) openProgram(open.name);
			} else {
				toast("server rejected " + ev.name + ": " + (ev.error || ""), "err");
			}
			break;
		case "breakpoints_set":
			// Server-confirmed armed set (file lines) replaces the local
			// pending set; re-draw marks when this program is open.
			bpPending[ev.name] = new Set((ev.breakpoints || []).map((b) => b.srcmap));
			if (open && open.name === ev.name) refreshMarks();
			break;
		case "npcs":
			npcs = ev.npcs || [];
			renderNpcs();
			refreshMarks();
			break;
		case "npc_state":
			// Single-NPC updates merge; "npcs" replaces the whole list.
			for (const u of ev.npcs || []) {
				const i = npcs.findIndex((n) => n.npc_id === u.npc_id);
				if (i >= 0) npcs[i] = u; else npcs.push(u);
			}
			renderNpcs();
			refreshMarks();
			break;
		case "paused":
			pausedInfo = ev;
			markNpcPaused(ev.npc_id, true);
			renderNpcs();
			showDebugBar(ev);
			refreshMarks();
			break;
		case "resumed":
			pausedInfo = null;
			markNpcPaused(ev.npc_id, false);
			hideDebugBar();
			renderNpcs();
			refreshMarks();
			break;
		case "spawned":
			toast("spawned " + ev.npc_id, "ok");
			// The spawned event carries no list; ask for a full one.
			post("/api/command", { op: "state" });
			break;
		case "error":
			toast("server: " + (ev.op || "") + " " + (ev.message || ""), "err");
			break;
	}
}

function markNpcPaused(id, paused) {
	for (const n of npcs) if (n.npc_id === id) n.paused = paused;
}
function fileOf(name) {
	const p = programs.find((x) => x.name === name);
	return p ? p.file : "";
}

// ---------------------------------------------------------------------------
// Program list + editor
// ---------------------------------------------------------------------------

function renderPrograms() {
	const ul = $("program-list");
	ul.textContent = "";
	$("program-count").textContent = programs.length;
	if (!programs.length) {
		const li = document.createElement("li");
		li.className = "empty";
		li.textContent = "(none - create one)";
		ul.appendChild(li);
		return;
	}
	for (const p of programs) {
		const li = document.createElement("li");
		if (open && open.name === p.name) li.className = "active";
		li.innerHTML = "<span>" + p.name + "</span><br><span class='sub'>" + (p.file || "no source") + "</span>";
		li.onclick = () => openProgram(p.name);
		ul.appendChild(li);
	}
}

async function openProgram(name) {
	// Server-registered programs (cat:*, builtin:*, ...) have no IDE
	// source: open them as a read-only stub. Run/pause/inspect still
	// target them; breakpoints and save need a source.
	const meta = programs.find((p) => p.name === name);
	if (meta && !meta.file) {
		open = { name: name, file: "", blockStart: 1, instructions: [], lua: null };
		editorTitle.textContent = name;
		cm.setValue("-- " + name + "\n-- server-registered program (no .anpcscript source)\n-- not editable here; run/pause/inspect still work");
		cm.clearHistory();
		cm.setCursor(0, 0);
		saveBtn.disabled = true;
		compiledEl.textContent = "(no compiled output)";
		$("tab-compiled").classList.add("hidden");
		editorStatus.textContent = "read-only: server-registered, not IDE-managed";
		bpPending[name] = new Set();
		renderPrograms();
		refreshMarks();
		return;
	}
	const r = await get("/api/program?name=" + encodeURIComponent(name));
	if (!r.ok) { toast(r.error || "cannot open", "err"); return; }
	open = {
		name: r.name, file: r.file,
		blockStart: r.block ? r.block.start : 1,
		instructions: r.instructions || [],
		lua: r.lua,
	};
	editorTitle.textContent = r.name;
	cm.setValue(r.block ? r.block.text : "");
	cm.clearHistory();
	cm.setCursor(0, 0);
	cm.focus();
	saveBtn.disabled = !r.has_source;
	compiledEl.textContent = r.lua || "(no compiled output)";
	$("tab-compiled").classList.toggle("hidden", !r.lua);
	editorStatus.textContent = r.has_source
		? "source file " + (fileOf(r.name) || "?") + " \u00B7 block starts at file line " + open.blockStart
		: "read-only: no .anpcscript source (server-registered)";
	if (r.diagnostics && r.diagnostics.length)
		editorStatus.textContent = "compile: " + r.diagnostics.join("; ");
	// Server-confirmed armed lines (file lines) restore the gutter marks
	// across reloads; a later breakpoints_set event keeps it in sync.
	bpPending[r.name] = new Set(r.armed || []);
	// "paused" is a fire-once event: after a reload, re-derive a paused
	// NPC's debug info from the state (its record carries program +
	// instruction; the line comes from the compiled srcmap). Must run
	// before refreshMarks so the line gets marked.
	for (const n of npcs) {
		if (n.paused === true && n.program === r.name && n.instruction != null) {
			const rec = (r.instructions || [])[n.instruction - 1];
			if (rec && rec.srcmap != null) {
				pausedInfo = { npc_id: n.npc_id, entity: n.entity, program: n.program, instruction: n.instruction, line: rec.srcmap };
				break;
			}
		}
	}
	renderPrograms();
	refreshMarks();
	if (pausedInfo && pausedInfo.program === r.name) showDebugBar(pausedInfo);
}

function saveCurrent() {
	if (!open || saveBtn.disabled) return;
	post("/api/save", { name: open.name, block: cm.getValue() }).then((r) => {
		if (r.ok) {
			toast("saved " + open.name + " - reloading on server", "ok");
			openProgram(open.name);
		} else {
			editorStatus.textContent = (r.diagnostics || [r.error || "save failed"]).join(" \u00B7 ");
			toast((r.diagnostics || [r.error || "save failed"])[0], "err");
		}
	});
}

// ---------------------------------------------------------------------------
// Breakpoints + line marks
// ---------------------------------------------------------------------------

function toggleBreakpoint(localLine) {
	if (!open) return;
	const fileLine = open.blockStart + localLine;
	const set = bpPending[open.name] || (bpPending[open.name] = new Set());
	if (set.has(fileLine)) set.delete(fileLine);
	else set.add(fileLine);
	post("/api/command", { op: "breakpoints", name: open.name, lines: [...set] });
}

function lineLocal(fileLine) {
	return fileLine - open.blockStart;
}
function currentLineLocal() {
	if (!open) return null;
	for (const n of npcs) {
		if (n.program === open.name && n.paused !== true && n.instruction != null) {
			const rec = open.instructions[n.instruction - 1];
			return rec ? lineLocal(rec.srcmap) : null;
		}
	}
	return null;
}
function pausedLineLocal() {
	if (!open || !pausedInfo || pausedInfo.program !== open.name) return null;
	return lineLocal(pausedInfo.line);
}

function gutterMark(cls, ch) {
	// CodeMirror 5 gutter markers must be DOM elements (or {element, css}).
	const el = document.createElement("span");
	el.className = cls;
	el.textContent = ch;
	return el;
}

function refreshMarks() {
	if (!open || !cm) return;
	const n = cm.lineCount();
	// One CM operation so the display updates synchronously after the
	// last mark (event handlers don't otherwise force a render).
	cm.operation(() => {
		for (let i = 0; i < n; i++) {
			cm.setGutterMarker(i, "bp", null);
			cm.removeLineClass(i, "background", "cm-bp-line");
			cm.removeLineClass(i, "background", "cm-paused-line");
			cm.removeLineClass(i, "background", "cm-current-line");
		}
		const armed = bpPending[open.name] || new Set();
		for (const f of armed) {
			const l = lineLocal(f);
			if (l < 0 || l >= n) continue;
			cm.addLineClass(l, "background", "cm-bp-line");
			cm.setGutterMarker(l, "bp", gutterMark("bp-mark", "\u25CF"));
		}
		const cur = currentLineLocal();
		if (cur != null && cur >= 0 && cur < n)
			cm.addLineClass(cur, "background", "cm-current-line");
		const p = pausedLineLocal();
		if (p != null && p >= 0 && p < n) {
			cm.addLineClass(p, "background", "cm-paused-line");
			cm.setGutterMarker(p, "bp", gutterMark("mark-paused", "\u2758\uFE0F"));
		} else if (cur != null && cur >= 0 && cur < n) {
			cm.setGutterMarker(cur, "bp", gutterMark("mark-current", "\u25B6"));
		}
	});
}

// ---------------------------------------------------------------------------
// NPC panel
// ---------------------------------------------------------------------------

function renderNpcs() {
	const ul = $("npc-list");
	ul.textContent = "";
	$("npc-count").textContent = npcs.length;
	if (!npcs.length) {
		const li = document.createElement("li");
		li.className = "empty";
		li.textContent = "(none active - connect a client near an NPC)";
		ul.appendChild(li);
	}
	for (const n of npcs) {
		const li = document.createElement("li");
		if (n.npc_id === selectedNpc) li.className = "active";
		const badge = n.paused ? '<span class="badge paused">\u23F8 ' + (n.program || "") + "</span>"
			: '<span class="badge">' + (n.program ? n.program + " @" + n.instruction : "idle") + "</span>";
		const p = n.pos || {};
		li.innerHTML = "<b>" + n.npc_id + "</b> <span class='sub'>" + (n.entity || "") +
			"</span>" + badge +
			"<br><span class='sub'>x " + (p.x != null ? p.x : "?") + " y " +
			(p.y != null ? p.y : "?") + " z " + (p.z != null ? p.z : "?") + "</span>";
		li.onclick = () => selectNpc(n.npc_id);
		ul.appendChild(li);
	}
	if (selectedNpc && !npcs.some((n) => n.npc_id === selectedNpc)) {
		selectedNpc = null;
		$("npc-controls").classList.add("hidden");
	}
}

function selectNpc(id) {
	selectedNpc = id;
	renderNpcs();
	const n = npcs.find((x) => x.npc_id === id);
	$("npc-controls").classList.toggle("hidden", !n);
	if (n) {
		const p = n.pos || {};
		$("npc-info").textContent =
			n.npc_id + " (" + (n.entity || "?") + ")\n" +
			(n.paused ? "PAUSED at " : "running ") + (n.program || "-") +
			(n.instruction != null ? " instr " + n.instruction : "") +
			"\n" + (p.x != null ? "(" + p.x + ", " + p.y + ", " + p.z + ")" : "");
	}
}

function sendOp(op, extra) {
	const cmd = Object.assign({ op: op, npc_id: selectedNpc }, extra || {});
	if ((op === "run" || op === "execute")) {
		if (!open) { toast("open a program first", "err"); return; }
		cmd.program = open.name;
	}
	post("/api/command", cmd);
}

// ---------------------------------------------------------------------------
// Debug bar
// ---------------------------------------------------------------------------

function showDebugBar(ev) {
	if (!open || ev.program !== open.name) return;
	$("debug-bar").classList.remove("hidden");
	$("debug-info").textContent = ev.npc_id + " paused at " + ev.program +
		" instr " + ev.instruction + " \u2192 line " + (lineLocal(ev.line) + 1) +
		" (" + (ev.entity || "") + ")";
	cm.scrollTo(null, Math.max(0, (lineLocal(ev.line) - 4) * 19));
	cm.focus();
}
function hideDebugBar() { $("debug-bar").classList.add("hidden"); }

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

saveBtn.onclick = saveCurrent;
window.addEventListener("keydown", (e) => {
	if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
		e.preventDefault();
		saveCurrent();
	}
});
$("tab-source").onclick = () => {
	cm.setSize("100%", "100%");
	cm.refresh();
	$("cm").classList.remove("hidden");
	compiledEl.classList.add("hidden");
	$("tab-source").classList.add("active");
	$("tab-compiled").classList.remove("active");
};
$("tab-compiled").onclick = () => {
	$("cm").classList.add("hidden");
	compiledEl.classList.remove("hidden");
	$("tab-compiled").classList.add("active");
	$("tab-source").classList.remove("active");
};
$("new-program").onclick = () => {
	const name = prompt("new program name (e.g. mycat:dance):");
	if (!name) return;
	post("/api/create", { name: name.trim() }).then((r) => {
		if (r.ok) {
			toast("created " + r.name, "ok");
			get("/api/state").then((s) => { applyState(s); openProgram(r.name); });
		} else toast(r.error || "create failed", "err");
	});
};
$("spawn-btn").onclick = () => post("/api/command", { op: "spawn_near_player", entity: "anpc_dev:cat" });
// The bridge only posts NPC state on request (no periodic poll in 5.18),
// so the panel has a manual refresh.
$("npc-refresh").onclick = () => post("/api/command", { op: "state" });
$("debug-resume").onclick = () => { if (pausedInfo) post("/api/command", { op: "resume", npc_id: pausedInfo.npc_id }); };
for (const b of document.querySelectorAll(".btn.op")) b.onclick = () => sendOp(b.dataset.op);

// theme
const savedTheme = localStorage.getItem("anpc-theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
$("theme-toggle").onclick = () => {
	const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
	document.documentElement.dataset.theme = t;
	localStorage.setItem("anpc-theme", t);
};
// event log
$("log-toggle").onclick = () => {
	const f = $("event-log");
	f.classList.toggle("hidden");
	$("log-toggle").textContent = f.classList.contains("hidden") ? "events" : "hide";
};

// boot
get("/api/state").then((s) => applyState(s)).catch(() => setServer(false));
const es = new EventSource("/api/events");
es.onmessage = (m) => { try { handleEvent(JSON.parse(m.data)); } catch (e) { console.error("anpc ide event", e, JSON.parse(m.data)); } };
es.onerror = () => setServer(false);
