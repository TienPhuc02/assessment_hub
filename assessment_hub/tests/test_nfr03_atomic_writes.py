import ast
from pathlib import Path

from frappe.tests import IntegrationTestCase

APP_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ROLLBACK_FILE = APP_ROOT / "api" / "utils.py"
CHANGE_STATUS_FILE = APP_ROOT / "assessment_hub" / "doctype" / "assessment" / "assessment.py"


def iter_production_source_files():
	for path in APP_ROOT.rglob("*.py"):
		if "__pycache__" in path.parts or path.name.startswith("test_"):
			continue
		yield path


def is_frappe_db_call(node, attr):
	if not isinstance(node, ast.Call):
		return False
	func = node.func
	if not (isinstance(func, ast.Attribute) and func.attr == attr):
		return False
	return isinstance(func.value, ast.Attribute) and func.value.attr == "db"


def has_save_point_kwarg(node):
	return any(kw.arg == "save_point" for kw in node.keywords)


def find_commit_and_rollback_violations(path):
	tree = ast.parse(path.read_text(), filename=str(path))
	violations = []

	for node in ast.walk(tree):
		if is_frappe_db_call(node, "commit"):
			violations.append(f"{path}:{node.lineno} calls frappe.db.commit(), Frappe already commits per request")
		elif is_frappe_db_call(node, "rollback"):
			if path != ALLOWED_ROLLBACK_FILE:
				violations.append(f"{path}:{node.lineno} calls frappe.db.rollback() outside api/utils.py")
			elif not has_save_point_kwarg(node):
				violations.append(
					f"{path}:{node.lineno} calls frappe.db.rollback() without save_point, would wipe prior writes"
				)

	return violations


def find_change_status_method(tree):
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name == "change_status":
			return node
	return None


def refetches_row_with_for_update(method_node):
	for node in ast.walk(method_node):
		if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get_doc"):
			continue
		for kw in node.keywords:
			if kw.arg == "for_update" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
				return True
	return False


class TestNoUncontrolledCommitOrRollback(IntegrationTestCase):
	def test_production_code_never_commits_or_rolls_back_outside_api_response(self):
		violations = []
		for path in iter_production_source_files():
			violations.extend(find_commit_and_rollback_violations(path))

		self.assertEqual(violations, [])


class TestStatusTransitionLocksTheRow(IntegrationTestCase):
	def test_change_status_refetches_with_for_update_before_checking_transition(self):
		tree = ast.parse(CHANGE_STATUS_FILE.read_text(), filename=str(CHANGE_STATUS_FILE))
		method = find_change_status_method(tree)

		self.assertIsNotNone(method, "Assessment.change_status was not found")
		self.assertTrue(
			refetches_row_with_for_update(method),
			"change_status must re-fetch the row with for_update=True before checking the transition",
		)
