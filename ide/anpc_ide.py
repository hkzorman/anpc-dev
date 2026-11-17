# anpc web IDE backend
#
# Python (stdlib only) backend for the anpc web IDE.
#   python anpc_ide.py [world directory]
#
# One process does three jobs on 127.0.0.1:8765:
#   1. Serves the SPA (web/) to the browser.
#   2. Speaks the frozen bridge contract with the Luanti server:
#        GET  /luanti/command  -> next queued command (JSON) or "null"
#        POST /luanti/event    -> event posted by the anpc_dev bridge
#      Commands queued by the SPA (POST /api/command) drain through the
#      same queue the bridge polls.
#   3. Owns the program store in the world directory:
#        <world>/anpc_programs/           manifest.txt + compiled .lua (server side)
#        <world>/anpc_programs_src/      .anpcscript sources (IDE side, first
#                                        run seeds from the source paths the
#                                        compiler stamped into the .lua files)
#
# Saving a program recompiles the whole source file (one .lua can hold
# several programs), rewrites the .lua + manifest, and queues a
# load_program command so the running server upserts it without restart.

import json
import mimetypes
import os
import queue
import re
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

IDE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(IDE_DIR, "web")
sys.path.insert(0, os.path.dirname(IDE_DIR))  # anpc-dev/ (anpc_compiler lives there)

import anpc_compiler  # noqa: E402

PORT = 8765
WORLD = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\hecto\Luanti\worlds\anpc-ai-test"
PROGRAMS_DIR = os.path.join(WORLD, "anpc_programs")
SRC_DIR = os.path.join(WORLD, "anpc_programs_src")
MANIFEST = os.path.join(PROGRAMS_DIR, "manifest.txt")

lock = threading.Lock()
cmd_queue = []           # command dicts waiting for the bridge poll
events_recent = []       # in-memory event log (cap 500), for /api/state debug
sse_conns = set()        # queue.Queue per connected browser


def publish(ev):
    """Fan an event out to all connected browsers."""
    for q in list(sse_conns):
        q.put(ev)

latest = {
    "booted": False,
    "npcs": [],
    "last_event": 0,
}
# Last server-confirmed armed breakpoints per program (file lines), from
# breakpoints_set events. Survives SPA reloads; the server itself keeps
# them armed until told otherwise.
armed_bp = {}


# ---------------------------------------------------------------------------
# Program store
# ---------------------------------------------------------------------------

def read_manifest():
    """[(name, file), ...]"""
    entries = []
    try:
        with open(MANIFEST, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
                m = re.match(r"^\s*(\S+)\s+(\S+)\s*$", line)
                if m:
                    entries.append((m.group(1), m.group(2)))
    except FileNotFoundError:
        pass
    return entries


def write_manifest(entries):
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        for name, fname in entries:
            f.write("%s %s\n" % (name, fname))


def manifest_for(name):
    for n, fname in read_manifest():
        if n == name:
            return fname
    return None


def unescape_lua_string(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in ("n", "t", "r"):
                out.append({"n": "\n", "t": "\t", "r": "\r"}[nxt])
            else:  # \\, \" and friends
                out.append(nxt)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def first_source_path(lua_text):
    """The .anpcscript path stamped as the 3rd arg of register_program.

    The compiler separates program blocks with a blank line; the path is
    the trailing  `}, "<path>")`  of the first block.
    """
    head = lua_text.split("\n\n", 1)[0]
    m = re.search(r'\},\s*"((?:[^"\\]|\\.)*)"\s*\)\s*$', head, re.M)
    return unescape_lua_string(m.group(1)) if m else None


def seed_sources():
    """First run: copy the compiler-stamped .anpcscript sources into SRC_DIR.

    Never overwrites an existing IDE source (the IDE owns edits from then
    on; the mod's .anpcscript files become irrelevant to the world).
    """
    os.makedirs(SRC_DIR, exist_ok=True)
    seeded = 0
    for name, fname in read_manifest():
        stem = os.path.splitext(fname)[0]
        target = os.path.join(SRC_DIR, stem + ".anpcscript")
        if os.path.exists(target):
            continue
        try:
            with open(os.path.join(PROGRAMS_DIR, fname), "r", encoding="utf-8") as f:
                src_path = first_source_path(f.read())
            if src_path and os.path.isfile(src_path):
                shutil.copyfile(src_path, target)
                seeded += 1
        except OSError:
            pass
    return seeded


def compile_src(fname, source_path):
    """Compile <SRC_DIR>/<fname>.anpcscript; returns (CompileResult, src_text)."""
    path = os.path.join(SRC_DIR, fname)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return anpc_compiler.compile(text, source_path=os.path.abspath(path)), text


def dominant_eol(text):
    return "\r\n" if text.count("\r\n") > text.count("\n") - text.count("\r\n") else "\n"


def save_program(name, block_text):
    """Splice the editor's program block into the source file, recompile the
    whole file, rewrite .lua + manifest, queue load_program. Returns a dict."""
    with lock:
        fname = manifest_for(name)
        if fname is None:
            return {"ok": False, "error": "unknown program: %s" % name}
        stem = os.path.splitext(fname)[0]
        src_file = os.path.join(SRC_DIR, stem + ".anpcscript")
        if not os.path.exists(src_file):
            return {"ok": False,
                    "error": "no .anpcscript source for %s (file %s is not IDE-managed)"
                             % (name, fname)}
        with open(src_file, "r", encoding="utf-8") as f:
            cur = f.read()
        eol = dominant_eol(cur)
        cur_n = cur.replace("\r\n", "\n")

        res_cur = anpc_compiler.compile(cur_n, source_path=os.path.abspath(src_file))
        if not res_cur.ok:
            return {"ok": False, "error": "current source does not compile - fix it before saving",
                    "diagnostics": [str(d) for d in res_cur.diagnostics]}
        cp = next((p for p in res_cur.programs if p.name == name), None)
        if cp is None:
            return {"ok": False, "error": "program %s not found in source file" % name}

        lines = cur_n.split("\n")
        new_lines = lines[:cp.define_line - 1] + block_text.replace("\r\n", "\n").split("\n") \
            + lines[cp.end_line:]
        new_src = "\n".join(new_lines)

        res = anpc_compiler.compile(new_src, source_path=os.path.abspath(src_file))
        if not res.ok:
            return {"ok": False,
                    "diagnostics": [str(d) for d in res.diagnostics]}

        with open(src_file, "w", encoding="utf-8", newline="") as f:
            f.write(new_src.replace("\n", eol))
        with open(os.path.join(PROGRAMS_DIR, fname), "w", encoding="utf-8", newline="") as f:
            f.write(res.lua.replace("\n", eol))

        entries = [e for e in read_manifest() if e[1] != fname]
        entries.extend((p.name, fname) for p in res.programs)
        write_manifest(entries)

        # Upsert in the running server (no restart): the code is the whole
        # recompiled file, so every program in it is re-registered.
        cmd_queue.append({"op": "load_program", "name": name, "code": res.lua})
        # Engine breakpoints survive re-registration (kept per program
        # name, keyed by instruction index), so re-arm each program from
        # the last server-confirmed lines: the bridge re-resolves them
        # against the new instructions and reports dropped ones as missed
        # (an empty list clears any stale ones).
        for p in res.programs:
            cmd_queue.append({"op": "breakpoints", "name": p.name,
                              "lines": list(armed_bp.get(p.name, []))})
        return {"ok": True, "programs": [p.name for p in res.programs], "file": fname}


def create_program(name):
    with lock:
        if not anpc_compiler.PROGRAM_NAME_RE.match(name or ""):
            return {"ok": False,
                    "error": "invalid program name (use letters/digits/underscore, optional ':suffix')"}
        if manifest_for(name) is not None:
            return {"ok": False, "error": "program already exists: %s" % name}
        base, i = name.replace(":", "_"), 2
        while os.path.exists(os.path.join(SRC_DIR, base + ".anpcscript")) \
                or os.path.exists(os.path.join(PROGRAMS_DIR, base + ".lua")):
            base, i = "%s_%d" % (name.replace(":", "_"), i), i + 1
        fname = base + ".lua"
        src_file = os.path.join(SRC_DIR, base + ".anpcscript")
        src = "define program %s\n\t-- new program\nend\n" % name
        res = anpc_compiler.compile(src, source_path=os.path.abspath(src_file))
        if not res.ok:  # the skeleton always compiles; this is a tripwire
            return {"ok": False, "diagnostics": [str(d) for d in res.diagnostics]}
        os.makedirs(SRC_DIR, exist_ok=True)
        os.makedirs(PROGRAMS_DIR, exist_ok=True)
        with open(src_file, "w", encoding="utf-8", newline="") as f:
            f.write(src)
        with open(os.path.join(PROGRAMS_DIR, fname), "w", encoding="utf-8", newline="") as f:
            f.write(res.lua)
        write_manifest(read_manifest() + [(name, fname)])
        cmd_queue.append({"op": "load_program", "name": name, "code": res.lua})
        return {"ok": True, "name": name, "file": fname}


# ---------------------------------------------------------------------------
# Bridge state (from posted events)
# ---------------------------------------------------------------------------

def on_bridge_event(ev):
    t = ev.get("type")
    events_recent.append((time.time(), ev))
    if len(events_recent) > 500:
        del events_recent[:len(events_recent) - 500]
    if t == "booted":
        latest["booted"] = True
        latest["npcs"] = ev.get("npcs") or []
        # Restore armed breakpoints after a cold backend start: the
        # server (not the backend) is the one keeping them armed.
        for bp in ev.get("breakpoints") or []:
            name = bp.get("name")
            if name is not None:
                armed_bp[name] = [b.get("srcmap") for b in (bp.get("breakpoints") or [])
                                  if b.get("srcmap") is not None]
    elif t == "npcs":
        latest["npcs"] = ev.get("npcs") or []
    elif t == "npc_state":
        # Single-NPC updates (run/pause/...) must merge, not replace:
        # the full list only comes back with "npcs"/"booted".
        cur = latest["npcs"]
        for u in ev.get("npcs") or []:
            for i, n in enumerate(cur):
                if n.get("npc_id") == u.get("npc_id"):
                    cur[i] = u
                    break
            else:
                cur.append(u)
    elif t == "paused":
        for n in latest["npcs"]:
            if n.get("npc_id") == ev.get("npc_id"):
                n["paused"] = True
                n["program"] = ev.get("program")
                n["instruction"] = ev.get("instruction")
    elif t == "resumed":
        for n in latest["npcs"]:
            if n.get("npc_id") == ev.get("npc_id"):
                n["paused"] = False
    elif t == "breakpoints_set":
        # Remember the server-confirmed armed lines so a reloaded SPA can
        # restore its gutter marks (the server keeps them armed itself).
        name = ev.get("name")
        if name is not None:
            lines = [b.get("srcmap") for b in (ev.get("breakpoints") or [])
                     if b.get("srcmap") is not None]
            armed_bp[name] = lines
    latest["last_event"] = time.time()
    publish(ev)


def state_payload():
    with lock:
        manifest = read_manifest()
    return {
        "world": WORLD,
        "booted": latest["booted"],
        "recent": latest["last_event"] > 0 and time.time() - latest["last_event"] < 5,
        "ts": latest["last_event"],
        "programs": [{"name": n, "file": f} for n, f in manifest],
        "npcs": latest["npcs"],
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class H(BaseHTTPRequestHandler):
    server_version = "anpc-ide/1"

    def _send(self, body, code=200, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj), code)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return None

    # -- bridge contract (frozen) -------------------------------------------

    def handle_luanti_command(self):
        with lock:
            cmd = cmd_queue.pop(0) if cmd_queue else None
        self._send(json.dumps(cmd))  # "null" when empty - the bridge ignores it

    def handle_luanti_event(self):
        body = self._body()
        if isinstance(body, dict):
            on_bridge_event(body)
        self._json({"stored": True})

    # -- SPA API --------------------------------------------------------------

    def api_state(self):
        self._json(state_payload())

    def api_program(self, name):
        with lock:
            manifest = read_manifest()
        fname = dict((n, f) for n, f in manifest).get(name)
        if fname is None:
            return self._json({"ok": False, "error": "unknown program: %s" % name}, 404)
        stem = os.path.splitext(fname)[0]
        src_file = os.path.join(SRC_DIR, stem + ".anpcscript")
        out = {"ok": True, "name": name, "file": fname, "has_source": os.path.exists(src_file)}
        if out["has_source"]:
            res, text = compile_src(stem + ".anpcscript", os.path.abspath(src_file))
            cp = next((p for p in res.programs if p.name == name), None) if res.ok else None
            if cp is not None:
                lines = text.replace("\r\n", "\n").split("\n")
                out["block"] = {
                    "text": "\n".join(lines[cp.define_line - 1:cp.end_line]),
                    "start": cp.define_line,
                    "end": cp.end_line,
                }
                out["instructions"] = [
                    {"no": i + 1, "name": rec.get("name"),
                     "srcmap": rec.get("srcmap"), "key": rec.get("key")}
                    for i, rec in enumerate(cp.instructions)
                ]
            out["lua"] = res.lua if res.ok else None
            out["diagnostics"] = [str(d) for d in res.diagnostics]
        out["armed"] = armed_bp.get(name, [])
        self._json(out)

    def api_save(self):
        body = self._body()
        if not isinstance(body, dict) or not body.get("name"):
            return self._json({"ok": False, "error": "missing name"}, 400)
        self._json(save_program(body["name"], body.get("block", "")))

    def api_create(self):
        body = self._body()
        if not isinstance(body, dict) or not body.get("name"):
            return self._json({"ok": False, "error": "missing name"}, 400)
        r = create_program(body["name"])
        self._json(r, 200 if r["ok"] else 400)

    def api_command(self):
        body = self._body()
        if not isinstance(body, dict) or "op" not in body:
            return self._json({"ok": False, "error": "missing op"}, 400)
        with lock:
            cmd_queue.append(body)
        self._json({"queued": True})

    def api_events(self):
        # Server-Sent Events: one bootstrap snapshot, then every bridge event.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = queue.Queue()
        sse_conns.add(q)
        # Re-arm the "booted" snapshot for this connection: the bridge
        # only posts state in response to commands, so after a backend
        # restart the in-memory state is cold until something answers.
        # One cheap hello per page load (bridge replies with booted).
        cmd_queue.append({"op": "hello"})
        try:
            self.wfile.write(("data: %s\n\n" % json.dumps(
                {"type": "hello", "state": state_payload()})).encode("utf-8"))
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=15)
                    self.wfile.write(("data: %s\n\n" % json.dumps(ev)).encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            sse_conns.discard(q)

    def api_static(self, rel):
        path = os.path.normpath(os.path.join(WEB_DIR, rel.lstrip("/")))
        if not path.startswith(WEB_DIR) or not os.path.isfile(path):
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            self._send(f.read(), ctype=ctype)

    # -- routing ---------------------------------------------------------------

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/luanti/command":
            return self.handle_luanti_command()
        if p == "/api/state":
            return self.api_state()
        if p == "/api/events":
            return self.api_events()
        if p == "/api/program":
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            name = ""
            for kv in qs.split("&"):
                if kv.startswith("name="):
                    from urllib.parse import unquote
                    name = unquote(kv[5:])
            return self.api_program(name)
        if p == "/":
            return self.api_static("index.html")
        if p.startswith("/static/"):
            return self.api_static(p[len("/static/"):])
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        if p == "/luanti/event":
            return self.handle_luanti_event()
        if p in ("/api/command", "/test/command"):  # /test/command: driver alias
            return self.api_command()
        if p == "/api/save":
            return self.api_save()
        if p == "/api/create":
            return self.api_create()
        self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        # quiet: only errors
        if args and "404" not in str(args[0]):
            sys.stderr.write("[anpc-ide] %s\n" % (fmt % args))


def main():
    os.makedirs(PROGRAMS_DIR, exist_ok=True)
    seeded = seed_sources()
    if seeded:
        print("seeded %d anpcscript source(s) into %s" % (seeded, SRC_DIR), flush=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("anpc web IDE on http://127.0.0.1:%d (world: %s)" % (PORT, WORLD), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
