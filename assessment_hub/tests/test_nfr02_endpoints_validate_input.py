import ast
from pathlib import Path

from frappe.tests import IntegrationTestCase

API_V1_DIR = Path(__file__).resolve().parent.parent / "api" / "v1"


def decorator_names(node):
	names = []
	for decorator in node.decorator_list:
		target = decorator.func if isinstance(decorator, ast.Call) else decorator
		if isinstance(target, ast.Attribute):
			names.append(target.attr)
		elif isinstance(target, ast.Name):
			names.append(target.id)
	return names


def is_whitelisted_endpoint(node):
	return isinstance(node, ast.FunctionDef) and "whitelist" in decorator_names(node)


def find_violations(path):
	tree = ast.parse(path.read_text(), filename=str(path))
	violations = []
	for node in ast.walk(tree):
		if not is_whitelisted_endpoint(node):
			continue
		if "api_response" not in decorator_names(node):
			violations.append(
				f"{path.name}:{node.lineno} {node.name} is @frappe.whitelist without @api_response"
			)
	return violations


class TestEndpointsAlwaysWrapErrors(IntegrationTestCase):
	def test_every_whitelisted_v1_endpoint_uses_api_response(self):
		violations = []
		for path in API_V1_DIR.glob("*.py"):
			violations.extend(find_violations(path))

		self.assertEqual(violations, [])
