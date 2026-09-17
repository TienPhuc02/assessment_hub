import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.exceptions import InvalidStatusTransitionError

VIEWER_EMAIL = "viewer@assessment-hub-test.local"


class TestAssessment(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make(self, **kwargs):
		values = {"doctype": "Assessment", "title": "Sample Assessment"}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def test_title_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(title="   ")

	def test_title_length_is_capped(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(title="x" * 141)

	def test_title_is_trimmed(self):
		doc = self.make(title="  Python Fundamentals  ")
		self.assertEqual(doc.title, "Python Fundamentals")

	def test_new_assessment_is_always_draft(self):
		doc = self.make(status="Published")
		self.assertEqual(doc.status, "Draft")

	def test_name_uses_naming_series(self):
		doc = self.make()
		self.assertTrue(doc.name.startswith("ASM-"))

	def test_draft_can_be_published(self):
		doc = self.make()
		doc.publish()
		self.assertEqual(doc.status, "Published")

	def test_draft_can_be_archived(self):
		doc = self.make()
		doc.archive()
		self.assertEqual(doc.status, "Archived")

	def test_published_can_be_archived(self):
		doc = self.make()
		doc.publish()
		doc.archive()
		self.assertEqual(doc.status, "Archived")

	def test_published_cannot_go_back_to_draft(self):
		doc = self.make()
		doc.publish()
		doc.status = "Draft"
		with self.assertRaises(InvalidStatusTransitionError):
			doc.save()

	def test_archived_is_terminal(self):
		doc = self.make()
		doc.archive()
		with self.assertRaises(InvalidStatusTransitionError):
			doc.publish()

	def test_viewer_cannot_publish(self):
		doc = self.make()
		frappe.db.commit()

		if not frappe.db.exists("User", VIEWER_EMAIL):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": VIEWER_EMAIL,
					"first_name": "Assessment Viewer",
					"send_welcome_email": 0,
					"roles": [{"role": "Assessment Viewer"}],
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()

		frappe.set_user(VIEWER_EMAIL)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Assessment", doc.name).publish()

		frappe.set_user("Administrator")
		frappe.delete_doc("Assessment", doc.name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def test_cannot_delete_assessment_with_questions(self):
		doc = self.make()
		frappe.get_doc(
			{
				"doctype": "Question",
				"assessment": doc.name,
				"content": "Sample question",
				"sort_order": 1,
				"status": "Active",
				"answers": [{"content": "Answer", "score": 1, "sort_order": 1}],
			}
		).insert()

		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("Assessment", doc.name)
