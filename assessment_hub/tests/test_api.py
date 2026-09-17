import json

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1.assessments import list_assessments


class TestListAssessments(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def make(self, **kwargs):
		values = {"doctype": "Assessment", "title": "Sample Assessment"}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def body(self, response):
		return json.loads(response.get_data(as_text=True))

	def test_no_params_returns_200_with_pagination(self):
		self.make()

		response = list_assessments()

		self.assertEqual(response.status_code, 200)
		data = self.body(response)["data"]
		self.assertIn("items", data)
		self.assertEqual(data["pagination"], {"start": 0, "page_length": 20, "has_more": False})

	def test_default_sort_is_modified_desc(self):
		first = self.make(title="First")
		second = self.make(title="Second")

		items = self.body(list_assessments())["data"]["items"]
		ids = [item["id"] for item in items]

		self.assertLess(ids.index(second.name), ids.index(first.name))

	def test_filters_by_status(self):
		self.make(title="Draft One")
		published = self.make(title="Published One")
		published.publish()

		items = self.body(list_assessments(status="Published"))["data"]["items"]

		self.assertEqual([item["id"] for item in items], [published.name])

	def test_invalid_status_is_rejected(self):
		response = list_assessments(status="Foo")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["code"], "INVALID_PARAMETER")

	def test_search_matches_title_case_insensitively(self):
		self.make(title="Python Fundamentals")
		self.make(title="JavaScript Basics")

		items = self.body(list_assessments(search="python"))["data"]["items"]

		self.assertEqual([item["title"] for item in items], ["Python Fundamentals"])

	def test_search_escapes_percent_and_underscore(self):
		self.make(title="100% Ready")
		self.make(title="100X Ready")

		items = self.body(list_assessments(search="100%"))["data"]["items"]

		self.assertEqual([item["title"] for item in items], ["100% Ready"])

	def test_search_too_long_is_rejected(self):
		response = list_assessments(search="x" * 141)

		self.assertEqual(response.status_code, 400)

	def test_page_length_over_maximum_is_rejected(self):
		response = list_assessments(page_length="500")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["code"], "INVALID_PARAMETER")

	def test_page_takes_priority_over_start(self):
		for i in range(3):
			self.make(title=f"Assessment {i}")

		data = self.body(list_assessments(page_length="1", page="2", start="0"))["data"]

		self.assertEqual(data["pagination"]["start"], 1)
		self.assertTrue(data["pagination"]["has_more"])

	def test_updated_since_filters_and_sorts_ascending(self):
		old = self.make(title="Old")
		frappe.db.set_value(
			"Assessment", old.name, "modified", "2020-01-01 00:00:00", update_modified=False
		)

		new = self.make(title="New")

		items = self.body(list_assessments(updated_since="2025-01-01T00:00:00+07:00"))["data"]["items"]
		ids = [item["id"] for item in items]

		self.assertNotIn(old.name, ids)
		self.assertIn(new.name, ids)
