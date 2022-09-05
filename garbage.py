import re

def generate_boolean_expression(bool_expr):
	if bool_expr[:4] == "lua:":
		return bool_expr[4:]
		
	result = '{left = "'
	expr_parts = re.split(r'(\(|\)|\s+)', bool_expr)
	
	return generate_expression(expr_parts)
	
def generate_expression(parts):
	
	print("Called with parts:")
	print(parts)

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
		
		print(part)
		
		if part == "(":
			parenthesis.append(part)
			if len(parenthesis) == 1:
				subexpr_start = i
		elif part == ")":
			last_parenthesis = parenthesis.pop()
			if last_parenthesis != "(":
				pass
				#logging.error("Unmatched parenthesis")
			
			print(parenthesis)
			if len(parenthesis) == 0:
				expr_operand = generate_expression(parts[subexpr_start+1:i])
				print(expr_operand)
				operands.append(expr_operand)
				subexpr_start = -1

		 	# at the end of parenthesis, we process subexpr
		 	# once we get result, we look at operators
		 	# if operators == 0, then this is the left expression
		 	# if operators <> 0, then this is the right expression
		 	# return this
				
		elif is_operator(part) and subexpr_start < 0:
			operators.append(part)
		elif subexpr_start < 0:
			operands.append(part)
		
		if len(operands) == 2 and len(operators) == 1:
			right = operands.pop()
			left = operands.pop()
			op = operators.pop()
			
			result = '{left = "'
			result += left
			result += '", op = "'
			result += op
			result += '", right = '
			result += right
			result += '}'
			
			print("Returning: " + result)
			
			return result
		
		i = i + 1
			
	return result

def is_parenthesis(s):
	if s == "(" or s == ")":
		return True
	return False

def is_operator(s):
	if s == "==" or s == "~=" or s == "<" or s == ">" or s == "<=" or s == ">=" \
	or s == "+" or s == "-" or s == "*" or s == "/" or s == "%" \
	or s == "&" or s == "|" or s == "&&" or s == "||":
		return True
	return False

s = "(a + (b - c)) >= 2"
print(generate_boolean_expression(s))
