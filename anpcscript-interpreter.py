# Very inflexible, rudimentary and basic interpreter for anpc-script
# (C) by Zorman2000
#
# Please don't use this as an example of good Python code :)

import logging
import os
import re
import sys

logging.basicConfig(level=logging.INFO)

###################################################################
## Helper functions
###################################################################
def escape_lua_keyword(key_str):
	if re.search(r'^(end|else|if|for|and|or)$', key_str, re.M|re.I):
		return f'["{key_str}"]'
	return key_str

def find_key_value_pairs(args_str):
	keyvalue_pairs = []
	prev_comma = 0
	brace_stack = []
	for i in range(len(args_str)):
		if args_str[i] == "," and len(brace_stack) == 0:
			keyvalue_pairs.append(args_str[prev_comma:i].strip())
			logging.debug("Found a , arg: " + args_str[prev_comma:i+1])
			prev_comma = i + 1
		elif args_str[i] == "{":
			brace_stack.append(args_str[i])
		elif args_str[i] == "}":
			last_brace = brace_stack.pop()
			if last_brace != "{":
				logging.error('Found unmatching "}", but no respective "{" found at: "' + args_str + '"') 
				sys.exit(1)
			if len(brace_stack) == 0:
				keyvalue_pairs.append(args_str[prev_comma:i+1].strip())
				logging.debug("Found a { arg: " + args_str[prev_comma:i+1])
	
	keyvalue_pairs.append(args_str[prev_comma:])
	
	return keyvalue_pairs

def decorate_value(value_str):
	result = value_str
	if value_str[0] == "@":
		result = f'"{value_str}"'
		
	# If we find something like this: "{key1 = val1, key2 = val2, ...}"
	# then we need to process
	logging.debug("Decorate given value: " + value_str[1:len(value_str)-1])
	if value_str.find("=") > -1:
		result = "{"
		sub_keyvalue_pairs = find_key_value_pairs(value_str[1:len(value_str)-1])
		#print("Sub kv")
		#print(sub_keyvalue_pairs)
		for i in range(len(sub_keyvalue_pairs)):
			parts = sub_keyvalue_pairs[i].split("=", 1)
			logging.debug("PARTS:")
			logging.debug(parts)
			key = escape_lua_keyword(parts[0].strip())
			value = decorate_value(parts[1].strip())
			result = result + key + " = " + value
			if i < len(sub_keyvalue_pairs) - 1:
				result = result + ", "
		result = result + "}"
		
	return result

# TODO: Allow instructions on arguments
def generate_arguments_for_instruction(args_str):
	result = "{"
	args_str = args_str.strip()
	if not args_str:
		return "{}"
		
	keyvalue_pairs = find_key_value_pairs(args_str)
	
	pairs_count = len(keyvalue_pairs)
	for i in range(pairs_count):
		key_value = keyvalue_pairs[i].split("=", 1)
		key = escape_lua_keyword(key_value[0].strip())
		value = decorate_value(key_value[1].strip())

		result = result + key + " = " + value

		if i < pairs_count - 1:
			result = result + ", "
		
	return result + "}"


def process_expression(expr, inline_instructions):
	# If expression is a lua function, return function
	if expr[:4] == "lua:":
		return expr[4:]
		
	# If expression contains an arithmetic character, process
	if re.search(r'(==|~=|<|>|<=|>=|\+|-|\*|/|%|&&|\|\|)', expr, re.I|re.M):
		expr_parts = re.split(r'(\(|\)|\s+)', expr)
		return generate_expression(expr_parts, inline_instructions)

	# Else we checkjust return whatever we were given
	if re.search(r'[0-9]+', expr, re.I|re.M):
		return expr
	else:
		return '"' + expr + '"'

	
def generate_expression(parts, inline_instructions):
	#print("Parts: " + "".join(parts))
	parenthesis = []
	operators = []
	operands = []
	
	if len(parts) == 1:
		return parts[0]
	
	i = 0
	subexpr_start = -1
	while i < len(parts):
		part = parts[i].strip()
		if not part:
			i = i + 1
			continue

		if part == "(":
			parenthesis.append(part)
			if len(parenthesis) == 1:
				subexpr_start = i
		elif part == ")":
			last_parenthesis = parenthesis.pop()
			if last_parenthesis != "(":
				logging.error(f'Unmatched parenthesis found on expression: {"".join(parts)}')
				sys.exit(1)
			
			if len(parenthesis) == 0:
				expr_operand = generate_expression(parts[subexpr_start+1:i], inline_instructions)
				operands.append(expr_operand)
				subexpr_start = -1
		elif is_operator(part) and subexpr_start < 0:
			#print("Found operator: " + part)
			operators.append(part)
		elif subexpr_start < 0:
			#if re.search(r'[a-zA-Z0-9:_]+\(.*\)', part, re.I|re.M):
			if re.search(r'[a-zA-Z0-9]+:[a-zA-Z0-9]+', part, re.I|re.M):
				index = len(inline_instructions)
				operands.append(f'@local._inline_{part}{index}')
				
				# Find all arguments: notice that arguments *cannot* be instructions
				instr_args = "{"
				k = i + 1
				while k < len(parts):
					sub_part = parts[k]
					# Identify if this is a value and decorate if needed
					if k > 1 and (parts[k - 1] == "=" or parts[k - 2] == "="):
						sub_part = decorate_value(sub_part)
					# Identify if this is a key and escape as needed
					if re.search(r'(end|else|if|for|and|or)', sub_part, re.M|re.I) and k < len(parts) - 2 and (parts[k + 1] == "=" or parts[k + 2] == "="):
						sub_part = f'["{sub_part}"]'
					if not sub_part or sub_part == "(":
						k = k + 1
						continue
					if sub_part == ")":
						break
					
					instr_args = instr_args + sub_part
					k = k + 1
				instr_args = instr_args + "}"
				
				i = k
				inline_instructions.append(f'{{key = "@local._inline_{part}{index}", name = "{part}", args = {instr_args}}}')
				logging.debug(f'Found inline instruction "{part}" with args: {instr_args}') 
			else:
				#print("Found operand: " + part)
				operands.append(part)
		
		if len(operands) == 2 and len(operators) == 1:
			
			right = operands.pop()
			left = operands.pop()
			op = operators.pop()
			
			if left[0] == "@":
				left = f'"{left}"'
				
			if right[0] == "@":
				right = f'"{right}"'
			
			# Generate expression as string
			result = '{left = '
			result += left
			result += ', op = "'
			result += op
			result += '", right = '
			result += right
			result += '}'
			
			#print("We are ready: " + result)
			return result
		
		i = i + 1
	
	#print("These were the parts: " + "".join(parts))
	return 


def is_operator(s):
	if s == "==" or s == "~=" or s == "<" or s == ">" or s == "<=" or s == ">=" \
	or s == "+" or s == "-" or s == "*" or s == "/" or s == "%" \
	or s == "&" or s == "|" or s == "&&" or s == "||":
		return True
	return False


###################################################################
## Single-line parsers
###################################################################
# This function parses a line where a variable assignment is contained
# TODO: Add support for inline functions inside args for instructions
def parse_variable_assignment(line, line_number, nesting, result):
	variable = re.search(r'@[a-z]*.[a-z_]*', line, re.I)
	if not variable:
		logging.error(f"Error on line {line_number}: variable expected but not found")

	assignment = re.search(r'=\s.+', line, re.I)
	if not assignment:
		logging.error(f"Error on line {line_number}: expected assignment to variable {variable.group(0)}")

	# Parse the variable expression. This could be of the type:
	# @<storage_type>.<var_name>[<table_key>]
	variable_expr = variable.group(0)
	storage_type = ""
	var_name = ""
	table_key = ""
	if variable_expr[0] == "@":
		parts = variable_expr.split(".")
		storage_type = parts[0][1:] # Don't include the @
		index_bracket_open = parts[1].find("[")
		if index_bracket_open > -1:
			index_bracket_close = variable_expr.find("]")
			table_key = variable_expr[index_bracket_open + 1:index_bracket_close]
			var_name = parts[1][0:index_bracket_open]
		else:
			var_name = parts[1]

	# Remove '= ' from assignment match
	assignment_expr = assignment.group(0)[2:]
	
	# Check if the assigned value is an instruction
	if re.search(r'[a-zA-Z0-9:_]+\(.*\)', assignment_expr, re.I|re.M):
		parenthesis_start = assignment_expr.find("(")
		parenthesis_end = assignment_expr.find(")")
		instr_name = assignment_expr[:parenthesis_start]
		args_str = assignment_expr[parenthesis_start + 1:parenthesis_end]
		result.append((nesting*"\t") + f'{{key = "{variable_expr}", name = "{instr_name}", args = {generate_arguments_for_instruction(args_str)}, srcmap = {line_number}}}')
	else:
		extra_instructions = []
		assignment_expr = process_expression(assignment_expr, extra_instructions)
		if len(extra_instructions) > 0:
			for k in range(len(extra_instructions)):
				result.append((nesting*"\t") + extra_instructions[k])
		result.append((nesting*"\t") + f'{{name = "npc:var:set", args = {{key = "{var_name}", value = {assignment_expr}, storage_type = "{storage_type}"}}, srcmap = {line_number}}}')

# This function parses a line where a single instruction is contained
def parse_instruction(line, nesting, result, source_line_number):
	parenthesis_start = line.find("(")
	parenthesis_end = line.find(")")
	if parenthesis_start > -1 and parenthesis_end > -1 and parenthesis_end > parenthesis_start:	
		instr_name = line[:parenthesis_start]
		args_str = line[parenthesis_start + 1:parenthesis_end]
		
		# Support npc:wait instruction
		if instr_name == "npc:wait":
			# Only one argument expected - "time"
			wait_value = args_str.split("=", 1)[1].strip()
			result.append((nesting*"\t") + '{key = "_prev_proc_int", name = "npc:get_proc_interval"}')
			result.append((nesting*"\t") + '{name = "npc:set_proc_interval", args = {wait_time = ' \
				+ wait_value + ', value = {left = ' + wait_value + ', op = "-", right = "@local._prev_proc_int"}}}')
			result.append((nesting*"\t") + '{name = "npc:set_proc_interval", args = {value = "@local._prev_proc_int"}}')
		else:	
			result.append((nesting*"\t") + f'{{name = "{instr_name}", args = {generate_arguments_for_instruction(args_str)}, srcmap = {source_line_number}}}')


###################################################################
## File parsers
###################################################################
def parse_file(filename, debug, lines):
	result = []
	program_names = []

	for i in range(len(lines)):
		# If line is a comment just ignore it
		if re.search(r'^\s*--.*$', lines[i], re.M|re.I):
			continue
			
		if re.search(r'^(define program).*$', lines[i], re.M|re.I):
			# Found a program definition, now collect all lines inside the program
			program_name = lines[i].split("define program")[1].strip()
			logging.info(f'Found program "{program_name}" definition starting at line {i+1}')
			if program_name in program_names:
				logging.error(f'Parsing error: Program with name "{program_name}" is already defined.')
				sys.exit(1)
			
			program_names.append(program_name)
			program_lines = []

			for j in range(i + 1, len(lines), 1):
				if re.search(r'^end$', lines[j], re.M|re.I):
					# Found definition end, parse this program and continue
					result.append(f'npc.proc.register_program("{program_name}", {{')
					# Original line number is i + 2 to because:
					#   1. i starts at 0, but lines start at 1
					#   2. we skip one the program definition line to start of the instructions
					lua_code_lines = parse_instructions(program_lines, 1, i + 2)
					for k in range(len(lua_code_lines)):
						result.append(f'{lua_code_lines[k]}{"," if k < len(lua_code_lines) - 1 else ""}')
					result.append(f'}}, "{filename}", {i + 2}, {j})\n' if debug == True else "})\n")

					logging.info(f'Successfully parsed program "{program_name}" ({j-i-1} lines of code)')
					i = i + j
					break
				else:
					program_lines.append(lines[j])

	return result

def parse_instructions(lines, nesting, original_line_number):
	logging.debug('Executing "parse_instructions" with lines:\n' + "".join(lines))
	result = []

	lines_count = len(lines)
	i = 0
	while (i < lines_count):
		line = lines[i].strip()
		logging.debug(f'Line: {lines[i]}, {i}')
		
		# If line is a comment just ignore it
		if re.search(r'^\s*--.*$', lines[i], re.M|re.I):
			i = i + 1
			continue

		###################################################################
		# Check for "variable assignment" line
		if re.search(r'^\s*@[a-z]*.[a-z_0-9A-Z]*\s=\s.*$', line, re.M|re.I):
			parse_variable_assignment(line, original_line_number + i, nesting, result)
		
		###################################################################
		# Check for control instruction line
		elif re.search(r'^\s*(while|for|if)\s\(.*\)\s(do|then)$', line, re.M|re.I):
			control_starting_line = i
			control_stack = []
					
			# Find the control instruction
			control_instr = re.search(r'(while|for|if)', line, re.M|re.I) \
			.group(0) \
			.strip()
			control_stack.append(control_instr)
			# Find the start for the control instruction
			control_start_instr = re.search(r'(do|then)', line, re.M|re.I).group(0).strip()
			# Find the boolean expression
			args_prefix_str = ""
			bool_expr_str = ""
			step_increase = 0
			initial_value = 0
			parenthesis_start = line.find("(")
			parenthesis_end = re.search(r'\)\s*(do|then)$', line, re.M|re.I).span()[0]
			extra_instructions = []
			if parenthesis_start > -1 and parenthesis_end > -1 and parenthesis_end > parenthesis_start:
				bool_expr_str = line[parenthesis_start+1:parenthesis_end]
				extra_instructions = []
				if control_instr == "for":
					# The step increase is optional, defaults to 1
					parts = bool_expr_str.split(";")
					initial_value = process_expression(parts[0].strip(), extra_instructions)
					step_increase = 1
					if len(parts) == 3:
						step_increase = process_expression(parts[2].strip(), extra_instructions)
					
					
					bool_expr_str = process_expression(parts[1], extra_instructions)
				else:
					bool_expr_str = process_expression(bool_expr_str, extra_instructions)
					
				if len(extra_instructions) > 0:
					for k in range(len(extra_instructions)):
						result.append((nesting*"\t") + extra_instructions[k])
				
			# Find all instructions that are part of the control
			# For 'if', we need to search for an else as well.
			loop_instructions = []
			false_instructions = []
			else_index = -1
			for j in range(i + 1, len(lines), 1):
				sub_line = lines[j].strip()
				logging.debug("subline: " + sub_line)
				
				other_control_instr = re.search(r'^\s*(for|while|if)\s*\(.*', sub_line, re.I|re.M)
				if other_control_instr:
					instr = re.search(r'(for|if|while)', sub_line, re.I|re.M)
					control_stack.append(instr.group(0))
				
				else_instr = re.search(r'^\s*else\s*$', sub_line, re.M|re.I)
				if else_instr:
					last_control = control_stack.pop()
					if last_control != "if":
						logging.error(f'Found "else" keyword without corresponding "if" at: line {j}')
						sys.exit(1)

					# These are the true_instructions
					if len(control_stack) == 0:
						control_stack.append("else")
						loop_instructions = lines[i+1:j+1]
						else_index = j
						continue

				end_instr = re.search(r'^\s*end\s*$', sub_line, re.M|re.I)
				if end_instr:
					last_control = control_stack.pop()
					if last_control == "else" and len(control_stack) == 0:
						# These are the false instructions
						false_instructions = lines[else_index+1:j+1]
					elif len(control_stack) == 0:
						# These are the true/loop instructions
						loop_instructions = lines[i+1:j+1]
						
					if len(control_stack) == 0:
						# Increase counter to avoid processing lines which are inside controls
						logging.debug(f"Old i: {i}")
						i = j
						logging.debug(f"New i: {i}")
						break
					elif j == len(lines) - 1 and len(control_stack) > 0:
						logging.error('Expected "end", but reached EOF')
						sys.exit(1)
			# Now, process all the instructions that we found
			if not loop_instructions:
				logging.warning(f'Found control structure "{control_instr}" without any instructions at: line {j+1}')
			processed_loop_instrs = parse_instructions(loop_instructions, nesting, original_line_number + control_starting_line + 1)
			processed_false_instrs = parse_instructions(false_instructions, nesting, original_line_number + control_starting_line + len(loop_instructions) + 1)
			
			# Add the primitive control instructions
			if control_instr == "if":
				# Add jump to skip if expression is false
				offset = 1 if len(processed_false_instrs) > 0 else 0
				jump_index = len(processed_loop_instrs) + offset
				result.append((nesting*"\t") + '{name = "npc:jump_if", args = {expr = ' + bool_expr_str \
					+ ', offset = true, negate = true, pos = ' + str(jump_index) \
					+ '}, srcmap = ' + str(original_line_number + control_starting_line) + '}, -- IF [' + str(len(result) + 1) + ']')
					
				# Add true instructions
				for instr in processed_loop_instrs:
					result.append((nesting*"\t") + instr)

				# Add jump to skip if expression is true
				if len(processed_false_instrs) > 0:
					jump_index = len(processed_false_instrs)
					result.append((nesting*"\t") + '{name = "npc:jump", args = {offset = true, pos = ' \
						+ str(jump_index) + '}, srcmap = ' \
						+ str(original_line_number + control_starting_line + len(loop_instructions)) \
						+ '}, -- ELSE [' + str(len(result) + 1) + ']')

					# Add false instructions
					for instr in processed_false_instrs:
						result.append((nesting*"\t") + instr)

			elif control_instr == "while":
				# Add loop instructions
				loop_start = len(processed_loop_instrs) + 1
				for instr in processed_loop_instrs:
					result.append((nesting*"\t") + instr)
					
				# Add jump to start of loop if expression is true
				result.append((nesting*"\t") + '{name = "npc:jump_if", args = {expr = ' + bool_expr_str \
					+ ', negate = false, offset = true, pos = ' + str(loop_start * -1) + '}, srcmap = ' + str(original_line_number + control_starting_line) + '}, -- WHILE end [' + str(len(result) + 1) + ']')
					
			elif control_instr == "for":
				for_instr_src_line_number = str(original_line_number + control_starting_line)
				# Add instruction to set for value to initial value
				result.append((nesting*"\t") + '{name = "npc:var:set", args = {key = "for_index", value = ' + str(initial_value) + ', storage_type = "local"}, srcmap = ' + for_instr_src_line_number + '}, -- FOR start [' + str(len(result) + 1) + ']')
				
				# Add loop instructions
				loop_start = len(processed_loop_instrs) + 2
				for instr in processed_loop_instrs:
					result.append((nesting*"\t") + instr)
					
				# Add instruction to increment value of for index
				result.append((nesting*"\t") + '{name = "npc:var:set", args = {key = "for_index", value = {left = "@local.for_index", op = "+", right = ' + str(step_increase) + '}, storage_type = "local"}, srcmap = ' + for_instr_src_line_number + '}')
				
				# Add jump to go back to start of loop if expression is true
				result.append((nesting*"\t") + '{name = "npc:jump_if", args = {expr = ' + bool_expr_str \
					+ ', negate = false, offset = true, pos = ' + str(loop_start * -1) + '}, srcmap = ' + for_instr_src_line_number + '}, -- FOR end [' + str(len(result) + 1) + ']')
			
			
			logging.debug(f'loop: {processed_loop_instrs}')
			logging.debug(f'false: {processed_false_instrs}')
		
		###################################################################
		# Check for single-line instructions
		elif re.search(r'^(?!.*(\sif\s|\swhile\s|\sfor\s|.*=.*\(.*\))).*\(.*\)$', line, re.M|re.I):
			parse_instruction(line, nesting, result, original_line_number + i)
		
		###################################################################
		# Check for break keyword
		elif re.search(r'^\s*break\s*$', line, re.M|re.I):
			result.append((nesting*"\t") + '{name = "npc:break", srcmap = ' + str(original_line_number + i) + '}')
			
		###################################################################
		# Check for exit keyword
		elif re.search(r'^\s*exit\s*$', line, re.M|re.I):
			result.append((nesting*"\t") + '{name = "npc:exit"}')

		i = i + 1

	logging.debug("Returning Lua code lines:\n" + "\n".join(result))
	return result


###################################################################
## Main
###################################################################
def main():
	if len(sys.argv) < 3:
		print("anpcscript-interpreter.py v1.0")
		print("This python script converts a anpc-script file into Lua code")
		print("understandable by the anpc Minetest mod\n")
		print('Usage: "python3 anpcscript-interpreter.py <input-file> <output-file> <enable-debug=false>"\n')
		sys.exit(0)

	lines = []
	input_name = sys.argv[1]
	output_name = sys.argv[2]
	logging.info(f'Starting parsing file "{input_name}"')
	with open(input_name, "r") as file:
		for line in file:
			lines.append(line)

	logging.info(f'Successfully parsed file "{input_name}" generating {len(lines)} lines of Lua code')

	# Enable debug mode if flag is on
	debug = False
	input_full_path = ""
	if "--enable-debug" in sys.argv:
		input_full_path = f'{os.path.join(os.getcwd(), input_name)}'
		debug = True

	lua_code = parse_file(input_full_path, debug, lines)
	logging.info(f'Writing Lua file at "{output_name}"')
	with open(output_name, "w") as file:
		for i in range(len(lua_code)):
			file.write(lua_code[i] + "\n")

	logging.info(f'Successfully writed Lua source code file "{output_name}"')
	return

if __name__ == "__main__":
	main()
