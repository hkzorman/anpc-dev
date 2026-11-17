// CodeMirror 5 mode for anpcscript (see anpc_compiler.py for the language).
// Tokens: comments (--), keywords, atoms, numbers, strings, @variables with
// optional .path and [index] parts, npc:* instruction calls, operators.
(function (mod) {
	if (typeof module === "object" && module.exports) { mod(require("../../lib/codemirror")); }
	else if (typeof define === "function" && define.amd) { define(["../../lib/codemirror"], mod); }
	else { mod(CodeMirror); }
})(function (CodeMirror) {
	"use strict";

	var KEYWORDS = {
		if: 1, then: 1, else: 1, end: 1, for: 1, while: 1, do: 1,
		define: 1, program: 1, break: 1, exit: 1, return: 1, switch: 1
	};
	var ATOMS = { true: 1, false: 1, nil: 1 };
	var WORD = /[A-Za-z0-9_]/;

	function eatWhile(stream, pred) {
		while (stream.peek() && pred(stream.peek())) stream.next();
	}

	function eatVariable(stream) {
		stream.next(); // '@'
		eatWhile(stream, function (c) { return WORD.test(c); });
		for (;;) {
			var c = stream.peek();
			if (c === ".") {
				stream.next();
				eatWhile(stream, function (ch) { return WORD.test(ch); });
			} else if (c === "[") {
				stream.next();
				while (stream.next() && stream.peek() !== "]") { /* eat index */ }
			} else {
				break;
			}
		}
		return "variable-2";
	}

	function eatString(stream) {
		var q = stream.peek();
		stream.next();
		while (stream.next()) {
			var c = stream.peek();
			if (c === "\\" && stream.next()) continue; // skip escaped char
			if (c === q) { stream.next(); break; }
		}
		return "string";
	}

	CodeMirror.defineMode("anpcscript", function () {
		return {
			startState: function () { return {}; },
			token: function (stream) {
				if (stream.eatSpace()) return null;

				if (stream.match(/^--/)) { stream.skipToEnd(); return "comment"; }

				var c = stream.peek();

				if (c === "@") return eatVariable(stream);

				if (/[0-9]/.test(c)) {
					stream.match(/^[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?/);
					return "number";
				}
				if (c === '"' || c === "'") return eatString(stream);

				if (WORD.test(c)) {
					eatWhile(stream, function (ch) { return WORD.test(ch) || ch === ":"; });
					var word = stream.current();
					if (word.slice(0, 4) === "npc:" && word.indexOf(":") === 3)
						return "tag";
					if (Object.prototype.hasOwnProperty.call(KEYWORDS, word)) return "keyword";
					if (Object.prototype.hasOwnProperty.call(ATOMS, word)) return "atom";
					return null;
				}

				if (stream.match(/^(==|~=|<=|>=|&&|\|\|)/)) return "operator";
				if (stream.match(/^[+\-*/%<>=]/)) return "operator";
				if (stream.match(/^[()\[\]{};,]/)) return "bracket";

				stream.next();
				return null;
			},
			lineComments: "--",
			fold: "brace"
		};
	}, { name: "anpcscript" });

	CodeMirror.defineMIME("text/anpcscript", "text/anpcscript");
});
