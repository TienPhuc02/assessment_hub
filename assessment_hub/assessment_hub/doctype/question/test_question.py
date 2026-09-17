import frappe
from frappe.tests import IntegrationTestCase


class TestQuestion(IntegrationTestCase):
	def setUp(self):
		self.assessment = frappe.get_doc({"doctype": "Assessment", "title": "Sample Assessment"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def make(self, **kwargs):
		values = {
			"doctype": "Question",
			"assessment": self.assessment.name,
			"content": "Sample question",
			"answers": [{"content": "Answer", "score": 1, "sort_order": 1}],
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def test_assessment_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(assessment=None)

	def test_assessment_must_exist(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(assessment="ASM-DOES-NOT-EXIST")

	def test_content_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(content="   ")

	def test_content_is_trimmed(self):
		doc = self.make(content="  What is 2 + 2?  ")
		self.assertEqual(doc.content, "What is 2 + 2?")

	def test_content_length_is_capped(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(content="x" * 10_001)

	def test_sort_order_defaults_to_next_in_assessment(self):
		first = self.make()
		second = self.make()
		self.assertEqual(first.sort_order, 1)
		self.assertEqual(second.sort_order, 2)

	def test_sort_order_cannot_be_negative(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(sort_order=-1)

	def test_status_defaults_from_settings(self):
		doc = self.make(status=None)
		self.assertEqual(doc.status, "Active")

	def test_status_must_be_a_valid_option(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(status="Deleted")

	def test_answers_are_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(answers=[])

	def test_answers_cannot_exceed_the_maximum(self):
		answers = [{"content": f"Answer {i}", "score": 0, "sort_order": i} for i in range(51)]
		with self.assertRaises(frappe.ValidationError):
			self.make(answers=answers)
