import ast
from pathlib import Path

from frappe.tests import IntegrationTestCase

APP_ROOT = Path(__file__).resolve().parent.parent


def iter_source_files():
	for path in APP_ROOT.rglob("*.py"):
		if "__pycache__" in path.parts:
			continue
		yield path


def is_frappe_db_sql_call(node):
	if not isinstance(node, ast.Call):
		return False
	func = node.func
	if not (isinstance(func, ast.Attribute) and func.attr == "sql"):
		return False
	return isinstance(func.value, ast.Attribute) and func.value.attr == "db"


def describe_violation(query_arg):
	if isinstance(query_arg, ast.JoinedStr):
		return "f-string"
	if isinstance(query_arg, ast.BinOp):
		return "string concatenation" if isinstance(query_arg.op, ast.Add) else "% string formatting"
	if isinstance(query_arg, ast.Call) and isinstance(query_arg.func, ast.Attribute) and query_arg.func.attr == "format":
		return "str.format()"
	return None


def find_violations(path):
	tree = ast.parse(path.read_text(), filename=str(path))
	violations = []
	for node in ast.walk(tree):
		if not is_frappe_db_sql_call(node) or not node.args:
			continue
		kind = describe_violation(node.args[0])
		if kind:
			violations.append(f"{path.relative_to(APP_ROOT.parent)}:{node.lineno} builds frappe.db.sql() query via {kind}")
	return violations


class TestNoRawSql(IntegrationTestCase):
	def test_frappe_db_sql_never_builds_query_by_string_concatenation(self):
		violations = []
		for path in iter_source_files():
			violations.extend(find_violations(path))

		self.assertEqual(violations, [])
