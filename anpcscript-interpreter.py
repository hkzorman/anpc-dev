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
def generate_arguments_for_instruction(args_str):
	result = "{"
	if not args_str.strip():
		return "{}"

	keyvalue_pairs = args_str.split(",")
	pairs_count = len(keyvalue_pairs)
	for i in range(pairs_count):
		key_value = keyvalue_pairs[i].split("=")
		key = key_value[0].strip()
		value = key_value[1].strip()

		if value[0] == "@":
			value = f'"{value}"'

		result = result + key + " = " + value
		if i < pairs_count - 1:
			result = result + ", "
		
	return result + "}"


def process_expression(expr):
	# If expression is a lua function, return function
	if expr[:4] == "lua:":
		return expr[4:]
		
	# If expression contains an arithmetic character, process
	if re.search(r'(==|!=|<|>|<=|>=|\+|-|\*|/|%|&&|\|\|)', expr, re.I|re.M):
		expr_parts = re.split(r'(\(|\)|\s+)', expr)
		return generate_expression(expr_parts)
		
	# Else just return whatever we were given
	return expr

	
def generate_expression(parts):
	parenthesis = []
	operators = []
	operands = []
	
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
				expr_operand = generate_expression(parts[subexpr_start+1:i])
				operands.append(expr_operand)
				subexpr_start = -1
		elif is_operator(part) and subexpr_start < 0:
			operators.append(part)
		elif subexpr_start < 0:
			operands.append(part)
		
		if len(operands) == 2 and len(operators) == 1:
			right = operands.pop()
			left = operands.pop()
			op = operators.pop()
			
			if left[0] == "@":
				left = f'"{left}"'
				
			if right[0] == "@":
				right = f'"{right}"'
					
			result = '{left = '
			result += left
			result += ', op = "'
			result += op
			result += '", right = '
			result += right
			result += '}'
			
			return result
		
		i = i + 1
			
	return result


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
def parse_variable_assignment(line, line_number, nesting, result):
	variable = re.search(r'@[a-z]*.[a-z_]*', line, re.I)
	if not variable:
		logging.error(f"Error on line {line_number}: variable expected but not found")

	assignment = re.search(r'=\s.+', line, re.I)
	if not assignment:
		logging.error(f"Error on line {line_number}: expected assignment to variable {variable.group(0)}")

	variable_name = variable.group(0)
	# Remove '= ' from assignment match
	assignment_expr = assignment.group(0)[2:]
	
	# Check if the assigned value is an instruction
	if re.search(r'[a-zA-Z0-9:_]+\(.*\)', assignment_expr, re.I|re.M):
		parenthesis_start = assignment_expr.find("(")
		parenthesis_end = assignment_expr.find(")")
		instr_name = assignment_expr[:parenthesis_start]
		args_str = assignment_expr[parenthesis_start + 1:parenthesis_end]
		result.append((nesting*"\t") + f'{{key = "{variable_name}", name = "{instr_name}", args = {generate_arguments_for_instruction(args_str)}}}')
	else:
		assignment_expr = process_expression(assignment_expr)
		result.append((nesting*"\t") + f'{{name = "npc:var:set", args = {{key = "{variable_name}", value = {assignment_expr}}}}}')

# This function parses a line where a single instruction is contained
def parse_instruction(line, nesting, result):
	parenthesis_start = line.find("(")
	parenthesis_end = line.find(")")
	if parenthesis_start > -1 and parenthesis_end > -1 and parenthesis_end > parenthesis_start:
		instr_name = line[:parenthesis_start]
		args_str = line[parenthesis_start + 1:parenthesis_end]
				
		result.append((nesting*"\t") + f'{{name = "{instr_name}", args = {generate_arguments_for_instruction(args_str)}}}')


###################################################################
## File parsers
###################################################################
def parse_file(filename, debug, lines):
	result = []
	program_names = []

	for i in range(len(lines)):
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
					lua_code_lines = parse_instructions(program_lines, 1)
					for k in range(len(lua_code_lines)):
						result.append(f'{lua_code_lines[k]}{"," if k < len(lua_code_lines) - 1 else ""}')
					result.append(f'}}, "{filename}")\n' if debug == True else "})\n")

					logging.info(f'Successfully parsed program "{program_name}" ({j-i-1} lines of code)')
					i = i + j
					break
				else:
					program_lines.append(lines[j])

	return result

def parse_instructions(lines, nesting):
	logging.debug('Executing "parse_instructions" with lines:\n' + "".join(lines))
	result = []

	lines_count = len(lines)
	i = 0
	while (i < lines_count):
		line = lines[i].strip()
		logging.debug(f'Line: {lines[i]}, {i}')

		###################################################################
		# Check for "variable assignment" line
		if re.search(r'^\s*@[a-z]*.[a-z_0-9A-Z]*\s=\s.*$', line, re.M|re.I):
			parse_variable_assignment(line, i, nesting, result)
		
		###################################################################
		# Check for control instruction line
		elif re.search(r'^\s*(while|for|if)\s\(.*\)\s(do|then)$', line, re.M|re.I):
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
			parenthesis_start = line.find("(")
			parenthesis_end = re.search(r'\)\s*(do|then)$', line, re.M|re.I).span()[0]
			if parenthesis_start > -1 and parenthesis_end > -1 and parenthesis_end > parenthesis_start:
				bool_expr_str = line[parenthesis_start+1:parenthesis_end]
				if control_instr == "for":
					# The step increase is optional, defaults to 1
					parts = bool_expr_str.split(";")
					initial_value = process_expression(parts[0])
					step_increase = 1
					if len(parts) == 3:
						step_increase = process_expression(parts[2])
						
					args_prefix_str = '{initial_value = ' + str(initial_value) \
					+ ', step_increase = ' + str(step_increase) \
					+ ', expr = ' \
					+ process_expression(parts[1])
				else:
					bool_expr_str = process_expression(bool_expr_str)
					args_prefix_str = "{expr = " + bool_expr_str
				
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
				
				else_instr = re.search(r'\s*else\s*', sub_line, re.M|re.I)
				if else_instr:
					last_control = control_stack.pop()
					if last_control != "if":
						logging.error(f'Found "else" keyword without corresponding "if" at: line {i+j+1}')
						sys.exit(1)

					# These are the true_instructions
					if len(control_stack) == 0:
						control_stack.append("else")
						loop_instructions = lines[i+1:j+1]
						else_index = j
						continue

				end_instr = re.search(r'\s*end\s*', sub_line, re.M|re.I)
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
			processed_loop_instrs = parse_instructions(loop_instructions, nesting + 1)
			processed_false_instrs = parse_instructions(false_instructions, nesting + 1)
			
			instructions_name = "true_instructions" if control_instr == "if" else "loop_instructions"
			loop_instr = (nesting*"\t") + '{name = "npc:' + control_instr \
			+ '", ' + args_prefix_str + ', ' + instructions_name \
			+ ' = {\n' + ",\n".join(processed_loop_instrs) + '\n' + (nesting*"\t") + '}'
			
			if processed_false_instrs:
				loop_instr = loop_instr + ',\n' + (nesting*"\t") + 'false_instructions = {\n' \
				+ ",\n".join(processed_false_instrs) + '\n' + (nesting*"\t") + '}'
			
			result.append(loop_instr)
			
			logging.debug(f'loop: {processed_loop_instrs}')
			logging.debug(f'false: {processed_false_instrs}')
		
		###################################################################
		# Check for single-line instructions
		elif re.search(r'^(?!.*(\sif\s|\swhile\s|\sfor\s|.*=.*\(.*\))).*\(.*\)$', line, re.M|re.I):
			parse_instruction(line, nesting, result)
		
		###################################################################
		# Check for break instruction
		elif re.search(r'^\s*break\s*$', line, re.M|re.I):
			result.append((nesting*"\t") + f'{{name = "npc:break"}}')

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
