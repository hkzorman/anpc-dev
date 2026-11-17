# test_compiler.py - unit tests for anpc_compiler.py
#
# Run from this directory:
#   python -m unittest test_compiler -v
#   or
#   python test_compiler.py
#
# Stdlib only. Covers: value/string rules, precedence, argument handling,
# inline hoisting (scope and ordering), control-flow jump offsets, the
# npc:wait expansion, srcmap stamps, lua: raw spans, var reference forms,
# diagnostics, the torcherer golden file, and the CLI.

import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anpc_compiler as C

HERE = os.path.dirname(os.path.abspath(__file__))


def comp(src, path="test.anpcscript"):
    return C.compile(src, source_path=path)


def prog(src, path="test.anpcscript"):
    r = C.compile(src, source_path=path)
    assert r.ok, "compile failed: %r" % r.diagnostics
    return r


# ---------------------------------------------------------------------------

class TestValueRules(unittest.TestCase):
    def rec(self, src):
        return prog('define program p\n\t@local.x = %s\nend\n' % src).programs[0].instructions[0]

    def test_quoted_string_kept(self):
        rec = self.rec('"Torcherer"')
        self.assertIsInstance(rec["args"]["value"], C.Str)
        self.assertEqual(rec["args"]["value"].text, '"Torcherer"')
        self.assertEqual(C.to_lua(rec["args"]["value"]), '"Torcherer"')
        self.assertEqual(rec["args"]["key"], '"x"')
        self.assertEqual(rec["args"]["storage_type"], '"local"')

    def test_bare_number_stays_bare(self):
        rec = self.rec("42")
        self.assertIsInstance(rec["args"]["value"], C.Num)
        self.assertEqual(C.to_lua(rec["args"]["value"]), "42")

    def test_float(self):
        rec = self.rec("3.5")
        self.assertIsInstance(rec["args"]["value"], C.Num)
        self.assertEqual(C.to_lua(rec["args"]["value"]), "3.5")

    def test_boolean_is_bare_true_false(self):
        rec = self.rec("false")
        self.assertIsInstance(rec["args"]["value"], C.Bool)
        self.assertEqual(C.to_lua(rec["args"]["value"]), "false")

    def test_nil_is_bare(self):
        rec = self.rec("nil")
        self.assertIsInstance(rec["args"]["value"], C.Nil)
        self.assertEqual(C.to_lua(rec["args"]["value"]), "nil")

    def test_bare_identifier_stays_bare(self):
        # A bare name is a Lua global reference; it must NOT be quoted.
        rec = self.rec("some_global")
        self.assertIsInstance(rec["args"]["value"], C.Ident)
        self.assertEqual(C.to_lua(rec["args"]["value"]), "some_global")

    def test_var_ref_is_quoted_dsl_string(self):
        r = prog('define program p\n\t@global.h = @local.hunger\nend\n')
        rec = r.programs[0].instructions[0]
        self.assertIsInstance(rec["args"]["value"], C.Var)
        self.assertEqual(rec["args"]["value"].text, "@local.hunger")
        self.assertEqual(C.to_lua(rec["args"]["value"]), '"@local.hunger"')

    def test_full_lua_exact(self):
        r = prog('define program p\n\t@global.hunger = 0\nend\n')
        self.assertEqual(r.lua,
            'npc.proc.register_program("p", {\n'
            '\t{name = "npc:var:set", args = {key = "hunger", value = 0, '
            'storage_type = "global"}, srcmap = 2}\n'
            '}, "test.anpcscript")\n')


class TestPrecedence(unittest.TestCase):
    def expr(self, src):
        return prog('define program p\n\t@local.x = %s\nend\n' % src).programs[0].instructions[0]["args"]["value"]

    def test_mul_binds_tighter_than_add(self):
        self.assertEqual(C.to_lua(self.expr("2 + 3 * 4")),
            '{left = 2, op = "+", right = {left = 3, op = "*", right = 4}}')

    def test_cmp_binds_looser_than_add(self):
        self.assertEqual(C.to_lua(self.expr("1 < 2 + 3")),
            '{left = 1, op = "<", right = {left = 2, op = "+", right = 3}}')

    def test_and_binds_looser_than_cmp(self):
        v = self.expr("a == b && c == d")
        self.assertIsInstance(v, C.Bin)
        self.assertEqual(v.op, "&&")
        self.assertEqual(v.left.op, "==")
        self.assertEqual(v.right.op, "==")

    def test_or_binds_looser_than_and(self):
        v = self.expr("a && b || c")
        self.assertIsInstance(v, C.Bin)
        self.assertEqual(v.op, "||")
        self.assertEqual(v.left.op, "&&")

    def test_left_associative(self):
        self.assertEqual(C.to_lua(self.expr("2 - 3 - 4")),
            '{left = {left = 2, op = "-", right = 3}, op = "-", right = 4}')

    def test_unary_minus_folds_on_number(self):
        self.assertEqual(C.to_lua(self.expr("-5")), "-5")

    def test_unary_minus_on_var(self):
        self.assertEqual(C.to_lua(self.expr("-@local.y")),
            '{left = 0, op = "-", right = "@local.y"}')

    def test_parentheses_override(self):
        self.assertEqual(C.to_lua(self.expr("(1 + 2) * 3")),
            '{left = {left = 1, op = "+", right = 2}, op = "*", right = 3}')

    def test_nested_boolean_expression(self):
        # Bare identifiers stay bare (Lua global references).
        self.assertEqual(C.to_lua(self.expr("(a > 1) && (b < 2)")),
            '{left = {left = a, op = ">", right = 1}, op = "&&", '
            'right = {left = b, op = "<", right = 2}}')


class TestArgs(unittest.TestCase):
    def test_key_order_preserved(self):
        r = prog('define program p\n\t'
                 'npc:execute(name = "q", args = {pos = @local.x, force = true})\n'
                 'end\n')
        rec = r.programs[0].instructions[0]
        self.assertEqual(list(rec["args"].keys()), ["name", "args"])
        inner = rec["args"]["args"]
        self.assertIsInstance(inner, C.Table)
        self.assertEqual([k for k, v in inner.items], ["pos", "force"])

    def test_reserved_word_key_is_bracketed(self):
        r = prog('define program p\n\t@local.n = npc:random(start = 1, end = 10)\nend\n')
        rec = r.programs[0].instructions[0]
        self.assertEqual(C.format_instruction(rec),
            '{key = "@local.n", name = "npc:random", '
            'args = {start = 1, ["end"] = 10}, srcmap = 2}')

    def test_table_of_vars_and_bools(self):
        r = prog('define program p\n\t'
                 'npc:execute(name = "npc:walk_to_pos", '
                 'args = {pos = @local.chosen_node, force_accessing_node = true})\n'
                 'end\n')
        rec = r.programs[0].instructions[0]
        self.assertEqual(C.to_lua(rec["args"]["args"]),
            '{pos = "@local.chosen_node", force_accessing_node = true}')

    def test_table_of_strings(self):
        r = prog('define program p\n\t'
                 '@local.nodes = npc:env:node:find(radius = 5, '
                 'nodenames = {"default:grass_1", "default:grass_2"})\n'
                 'end\n')
        rec = r.programs[0].instructions[0]
        self.assertEqual(C.to_lua(rec["args"]["nodenames"]),
            '{"default:grass_1", "default:grass_2"}')

    def test_empty_arg_list(self):
        r = prog('define program p\n\tnpc:move:stand()\nend\n')
        rec = r.programs[0].instructions[0]
        self.assertEqual(rec["args"], {})
        self.assertIn("args = {}", r.lua)


class TestInlineHoisting(unittest.TestCase):
    def test_assignment_from_call_is_single_record(self):
        r = prog('define program p\n\t@local.n = npc:random(start = 1, end = 10)\nend\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["key"], "@local.n")
        self.assertEqual(recs[0]["name"], "npc:random")

    def test_call_in_arg_hoisted_before_use(self):
        r = prog('define program p\n'
                 '\tnpc:var:set(key = "x", value = npc:random(start = 1, end = 10), '
                 'storage_type = "local")\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["key"], "@local._inline_npc:random0")
        self.assertEqual(recs[0]["name"], "npc:random")
        self.assertEqual(C.to_lua(recs[1]["args"]["value"]), '"@local._inline_npc:random0"')

    def test_counter_resets_per_statement(self):
        r = prog('define program p\n'
                 '\tnpc:var:set(key = "a", value = npc:random(start = 1, end = 1), storage_type = "local")\n'
                 '\tnpc:var:set(key = "b", value = npc:random(start = 2, end = 2), storage_type = "local")\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 4)
        self.assertEqual(recs[0]["key"], "@local._inline_npc:random0")
        self.assertEqual(recs[2]["key"], "@local._inline_npc:random0")

    def test_nested_calls_inner_first(self):
        r = prog('define program p\n'
                 '\tnpc:var:set(key = "x", value = npc:a(p = npc:b(q = 1)), '
                 'storage_type = "local")\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual([rec["name"] for rec in recs], ["npc:b", "npc:a", "npc:var:set"])
        self.assertEqual(recs[0]["key"], "@local._inline_npc:b0")
        self.assertEqual(recs[1]["key"], "@local._inline_npc:a1")
        self.assertEqual(C.to_lua(recs[1]["args"]["p"]), '"@local._inline_npc:b0"')
        self.assertEqual(C.to_lua(recs[2]["args"]["value"]), '"@local._inline_npc:a1"')

    def test_inline_in_if_condition_hoisted_before_jump(self):
        r = prog('define program p\n'
                 '\tif (npc:random(start = 1, end = 100) >= 90) then\n'
                 '\t\tnpc:var:set(key = "a", value = 1, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0]["name"], "npc:random")
        self.assertEqual(recs[1]["name"], "npc:jump_if")
        self.assertEqual(C.to_lua(recs[1]["args"]["expr"]),
            '{left = "@local._inline_npc:random0", op = ">=", right = 90}')
        self.assertEqual(recs[1]["args"]["pos"], 1)

    def test_inline_in_for_condition_hoisted_once(self):
        r = prog('define program p\n'
                 '\tfor (1; @local.for_index < npc:random(start = 1, end = 5); 1) do\n'
                 '\t\tnpc:var:set(key = "v", value = 1, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 5)
        self.assertEqual(recs[0]["name"], "npc:random")
        last = recs[-1]
        self.assertEqual(last["name"], "npc:jump_if")
        self.assertEqual(C.to_lua(last["args"]["expr"].right), '"@local._inline_npc:random0"')
        self.assertEqual(last["args"]["pos"], -3)

    def test_inline_in_loop_body_stays_inside(self):
        # Regression: hoisted inlines must NOT escape the loop body,
        # or they run unconditionally on every pass.
        r = prog('define program p\n'
                 '\twhile (@local.i < 3) do\n'
                 '\t\t@local.n = npc:random(start = 1, end = 10)\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["key"], "@local.n")
        self.assertEqual(recs[0]["name"], "npc:random")
        self.assertEqual(recs[1]["args"]["pos"], -2)


class TestControlFlow(unittest.TestCase):
    def test_if_without_else(self):
        r = prog('define program p\n'
                 '\tif (@local.x > 5) then\n'
                 '\t\tnpc:var:set(key = "a", value = 1, storage_type = "local")\n'
                 '\t\tnpc:var:set(key = "b", value = 2, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(len(recs), 3)
        ji = recs[0]
        self.assertEqual(ji["name"], "npc:jump_if")
        self.assertEqual(ji["args"]["offset"], True)
        self.assertEqual(ji["args"]["negate"], True)
        self.assertEqual(ji["args"]["pos"], 2)
        self.assertNotIn("loop_end", ji)

    def test_if_with_else_exact_lua(self):
        r = prog('define program p\n'
                 '\tif (@local.x > 5) then\n'
                 '\t\tnpc:var:set(key = "a", value = 1, storage_type = "local")\n'
                 '\t\tnpc:var:set(key = "b", value = 2, storage_type = "local")\n'
                 '\telse\n'
                 '\t\tnpc:var:set(key = "c", value = 3, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        self.assertEqual(r.lua,
            'npc.proc.register_program("p", {\n'
            '\t{name = "npc:jump_if", args = {expr = {left = "@local.x", op = ">", '
            'right = 5}, offset = true, negate = true, pos = 3}, srcmap = 2},\n'
            '\t{name = "npc:var:set", args = {key = "a", value = 1, '
            'storage_type = "local"}, srcmap = 3},\n'
            '\t{name = "npc:var:set", args = {key = "b", value = 2, '
            'storage_type = "local"}, srcmap = 4},\n'
            '\t{name = "npc:jump", args = {offset = true, pos = 1}, srcmap = 5},\n'
            '\t{name = "npc:var:set", args = {key = "c", value = 3, '
            'storage_type = "local"}, srcmap = 6}\n'
            '}, "test.anpcscript")\n')

    def test_while_exact_lua(self):
        r = prog('define program p\n'
                 '\twhile (@local.i < 3) do\n'
                 '\t\tnpc:var:set(key = "i", value = @local.i + 1, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        self.assertEqual(r.lua,
            'npc.proc.register_program("p", {\n'
            '\t{name = "npc:var:set", args = {key = "i", value = {left = "@local.i", '
            'op = "+", right = 1}, storage_type = "local"}, srcmap = 3},\n'
            '\t{name = "npc:jump_if", args = {expr = {left = "@local.i", op = "<", '
            'right = 3}, offset = true, negate = false, pos = -2}, '
            'loop_end = true, srcmap = 2}\n'
            '}, "test.anpcscript")\n')

    def test_for_exact_lua(self):
        r = prog('define program p\n'
                 '\tfor (1; @local.for_index <= 5; 2) do\n'
                 '\t\tnpc:var:set(key = "v", value = 1, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        self.assertEqual(r.lua,
            'npc.proc.register_program("p", {\n'
            '\t{name = "npc:var:set", args = {key = "for_index", value = 1, '
            'storage_type = "local"}, srcmap = 2},\n'
            '\t{name = "npc:var:set", args = {key = "v", value = 1, '
            'storage_type = "local"}, srcmap = 3},\n'
            '\t{name = "npc:var:set", args = {key = "for_index", value = {left = '
            '"@local.for_index", op = "+", right = 2}, storage_type = "local"}, '
            'srcmap = 2},\n'
            '\t{name = "npc:jump_if", args = {expr = {left = "@local.for_index", '
            'op = "<=", right = 5}, offset = true, negate = false, pos = -3}, '
            'loop_end = true, srcmap = 2}\n'
            '}, "test.anpcscript")\n')

    def test_for_default_step(self):
        r = prog('define program p\n'
                 '\tfor (1; @local.for_index <= 5) do\n'
                 '\t\tnpc:var:set(key = "v", value = 1, storage_type = "local")\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(C.to_lua(recs[2]["args"]["value"]),
            '{left = "@local.for_index", op = "+", right = 1}')
        self.assertEqual(recs[3]["args"]["pos"], -3)

    def test_break(self):
        r = prog('define program p\n'
                 '\twhile (@local.i < 3) do\n'
                 '\t\tbreak\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(recs[0], {"name": "npc:break", "srcmap": 3})
        self.assertEqual(recs[1]["name"], "npc:jump_if")
        self.assertTrue(recs[1].get("loop_end"))

    def test_exit(self):
        r = prog('define program p\n\texit\nend\n')
        self.assertEqual(r.programs[0].instructions,
                         [{"name": "npc:exit", "srcmap": 2}])

    def test_both_loop_back_jumps_carry_loop_end(self):
        r = prog('define program p\n'
                 '\tfor (1; @local.for_index <= 3; 1) do\n'
                 '\t\twhile (@local.i < 2) do\n'
                 '\t\t\tbreak\n'
                 '\t\tend\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual([rec["name"] for rec in recs],
            ["npc:var:set", "npc:break", "npc:jump_if",
             "npc:var:set", "npc:jump_if"])
        self.assertTrue(recs[2].get("loop_end"))
        self.assertTrue(recs[4].get("loop_end"))
        self.assertEqual(recs[4]["args"]["pos"], -4)


class TestWait(unittest.TestCase):
    def test_wait_expansion_exact_lua(self):
        r = prog('define program p\n\tnpc:wait(time = 2)\nend\n')
        self.assertEqual(r.lua,
            'npc.proc.register_program("p", {\n'
            '\t{key = "_prev_proc_int", name = "npc:get_proc_interval"},\n'
            '\t{name = "npc:set_proc_interval", args = {wait_time = 2, value = '
            '{left = 2, op = "-", right = "@local._prev_proc_int"}}},\n'
            '\t{name = "npc:set_proc_interval", args = {value = '
            '"@local._prev_proc_int"}}\n'
            '}, "test.anpcscript")\n')

    def test_wait_rejects_wrong_arg_name(self):
        r = comp('define program p\n\tnpc:wait(times = 2)\nend\n')
        self.assertFalse(r.ok)
        self.assertTrue(any("time" in d.message for d in r.diagnostics))

    def test_wait_rejects_extra_args(self):
        r = comp('define program p\n\tnpc:wait(time = 2, extra = 1)\nend\n')
        self.assertFalse(r.ok)


class TestSrcmap(unittest.TestCase):
    def test_srcmap_is_source_line(self):
        r = prog('define program p\n'
                 '\t@global.hunger = 0\n'
                 '\tnpc:move:stand()\n'
                 '\tif (@local.x > 1) then\n'
                 '\t\t@local.y = 2\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual([rec["srcmap"] for rec in recs], [2, 3, 4, 5])
        self.assertEqual(recs[2]["args"]["pos"], 1)

    def test_inline_srcmap_is_call_line(self):
        r = prog('define program p\n'
                 '\tnpc:var:set(key = "x", value = npc:random(start = 1, end = 1), '
                 'storage_type = "local")\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(recs[0]["srcmap"], 2)
        self.assertEqual(recs[1]["srcmap"], 2)

    def test_else_jump_srcmap_is_else_line(self):
        r = prog('define program p\n'
                 '\tif (@local.x > 5) then\n'
                 '\t\tnpc:move:stand()\n'
                 '\telse\n'
                 '\t\tnpc:move:stand()\n'
                 '\tend\n'
                 'end\n')
        recs = r.programs[0].instructions
        self.assertEqual(recs[2]["name"], "npc:jump")
        self.assertEqual(recs[2]["srcmap"], 4)
        self.assertEqual(recs[2]["args"]["pos"], 1)


class TestLuaSpan(unittest.TestCase):
    def rec(self, src):
        return prog('define program p\n\t'
                    'npc:var:set(key = "x", value = %s, storage_type = "local")\n'
                    'end\n' % src).programs[0].instructions[0]

    def test_raw_span_as_value(self):
        r = prog('define program p\n\t'
                 'npc:var:set(key = "x", value = lua: 1 + 1, storage_type = "local")\n'
                 'end\n')
        rec = r.programs[0].instructions[0]
        self.assertIsInstance(rec["args"]["value"], C.Raw)
        self.assertEqual(rec["args"]["value"].text, "1 + 1")
        self.assertIn("value = 1 + 1", r.lua)

    def test_raw_span_with_string_inside(self):
        rec = self.rec('lua: string.format("%s", 5)')
        self.assertIsInstance(rec["args"]["value"], C.Raw)
        self.assertEqual(rec["args"]["value"].text, 'string.format("%s", 5)')

    def test_raw_span_ends_at_comma(self):
        rec = self.rec("lua: 1 + 1")
        self.assertEqual(list(rec["args"].keys()), ["key", "value", "storage_type"])


class TestVarForms(unittest.TestCase):
    def assign(self, var):
        return prog('define program p\n\t@global.x = %s\nend\n' % var).programs[0].instructions[0]["args"]["value"]

    def test_string_index_quotes_stripped(self):
        v = self.assign('@local.node["name"]')
        self.assertIsInstance(v, C.Var)
        self.assertEqual(v.text, "@local.node[name]")
        self.assertEqual(C.to_lua(v), '"@local.node[name]"')

    def test_var_index(self):
        v = self.assign("@local.tbl[@local.idx]")
        self.assertIsInstance(v, C.Var)
        self.assertEqual(v.text, "@local.tbl[@local.idx]")

    def test_number_index(self):
        v = self.assign("@local.tbl[2]")
        self.assertIsInstance(v, C.Var)
        self.assertEqual(v.text, "@local.tbl[2]")

    def test_subfield(self):
        v = self.assign("@local.target.pos")
        self.assertIsInstance(v, C.Var)
        self.assertEqual(v.text, "@local.target.pos")


class TestDiagnostics(unittest.TestCase):
    def test_missing_end(self):
        r = comp('define program p\n\tbreak\n')
        self.assertFalse(r.ok)
        self.assertIsNone(r.lua)
        self.assertTrue(any("'end'" in d.message for d in r.diagnostics))

    def test_duplicate_program(self):
        r = comp('define program p\nend\ndefine program p\nend\n')
        self.assertFalse(r.ok)
        self.assertTrue(any("already defined" in d.message for d in r.diagnostics))

    def test_if_without_then(self):
        r = comp('define program p\n\tif (@local.x)\n\tend\nend\n')
        self.assertFalse(r.ok)

    def test_assign_to_storage_only(self):
        r = comp('define program p\n\t@global = 5\nend\n')
        self.assertFalse(r.ok)
        self.assertTrue(any("@storage.name" in d.message for d in r.diagnostics))

    def test_unterminated_string(self):
        r = comp('define program p\n\t@global.x = "abc\nend\n')
        self.assertFalse(r.ok)
        self.assertTrue(any("unterminated string" in d.message for d in r.diagnostics))

    def test_unexpected_character(self):
        r = comp('define program p\n\t??\nend\n')
        self.assertFalse(r.ok)
        self.assertTrue(any("unexpected character" in d.message for d in r.diagnostics))

    def test_bad_program_name(self):
        r = comp('define program 1bad\nend\n')
        self.assertFalse(r.ok)

    def test_line_numbers_reported(self):
        r = comp('define program p\n\tbreak\n\t??\nend\n')
        self.assertFalse(r.ok)
        self.assertTrue(any(d.line == 3 for d in r.diagnostics))

    def test_ok_result_invariants(self):
        r = comp('define program p\n\tbreak\nend\n')
        self.assertTrue(r.ok)
        self.assertNotEqual(r.lua, None)
        self.assertEqual(r.diagnostics, [])


class TestGolden(unittest.TestCase):
    def load(self, name):
        path = os.path.join(HERE, name + ".anpcscript")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return C.compile(text, source_path=path)

    def test_torcherer_matches_ground_truth(self):
        # torcherer.lua (test_utilities) is the known-working in-game output;
        # program set and per-program instruction counts must match it.
        r = self.load("torcherer")
        self.assertTrue(r.ok, r.diagnostics)
        self.assertEqual([p.name for p in r.programs],
            ["torcherer:init", "torcherer:find_bed", "torcherer:idle",
             "torcherer:turn_on_torches", "torcherer:wander", "torcherer:sleep"])
        self.assertEqual([len(p.instructions) for p in r.programs], [3, 4, 30, 12, 11, 9])
        self.assertEqual(sum(len(p.instructions) for p in r.programs), 69)

    def test_torcherer_idle_loop_offset(self):
        r = self.load("torcherer")
        idle = r.programs[2]
        back = [rec for rec in idle.instructions
                if rec.get("srcmap") == 42 and rec["name"] == "npc:jump_if"]
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0]["args"]["pos"], -21)
        self.assertEqual(back[0]["args"]["negate"], False)
        self.assertTrue(back[0].get("loop_end"))

    def test_torcherer_wait_expansion(self):
        r = self.load("torcherer")
        sleep = r.programs[5]
        recs = sleep.instructions
        waits = [i for i, rec in enumerate(recs) if rec.get("key") == "_prev_proc_int"]
        self.assertEqual(len(waits), 1)
        i = waits[0]
        self.assertEqual(recs[i]["name"], "npc:get_proc_interval")
        self.assertNotIn("args", recs[i])
        self.assertEqual(C.to_lua(recs[i + 1]["args"]["wait_time"]), "30")
        self.assertNotIn("srcmap", recs[i])
        self.assertNotIn("srcmap", recs[i + 1])
        self.assertNotIn("srcmap", recs[i + 2])

    def test_sedentary_and_nomad_compile(self):
        for name, n_prog, n_total in (("sedentary", 8, 97), ("nomad", 7, 66)):
            r = self.load(name)
            self.assertTrue(r.ok, (name, r.diagnostics))
            self.assertEqual(len(r.programs), n_prog, name)
            self.assertEqual(sum(len(p.instructions) for p in r.programs), n_total, name)

    def test_source_path_is_third_arg(self):
        r = C.compile('define program p\n\tbreak\nend\n',
                      source_path="C:\\x\\y.anpcscript")
        self.assertTrue(r.lua.endswith('}, "C:\\\\x\\\\y.anpcscript")\n'))

    def test_no_source_path_omitted(self):
        r = C.compile('define program p\n\tbreak\nend\n')
        self.assertTrue(r.lua.endswith('})\n'))


class TestCLI(unittest.TestCase):
    def run(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = C.main(list(args))
        return rc, out.getvalue(), err.getvalue()

    def test_compile_ok(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "x.anpcscript")
            dst = os.path.join(td, "x.lua")
            with open(src, "w", encoding="utf-8") as f:
                f.write('define program p\n\tbreak\nend\n')
            rc, out, err = self.run(src, dst)
            self.assertEqual(rc, 0, err)
            with open(dst, encoding="utf-8") as f:
                self.assertIn('npc.proc.register_program("p"', f.read())

    def test_compile_error_reports_problems(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "bad.anpcscript")
            dst = os.path.join(td, "bad.lua")
            with open(src, "w", encoding="utf-8") as f:
                f.write("not a program\n")
            rc, out, err = self.run(src, dst)
            self.assertEqual(rc, 1)
            self.assertIn("problem(s)", err)

    def test_missing_input(self):
        rc, out, err = self.run("does-not-exist.anpcscript", "out.lua")
        self.assertEqual(rc, 1)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
