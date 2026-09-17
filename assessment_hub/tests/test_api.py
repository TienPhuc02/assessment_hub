import json

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1.assessments import get_assessment, list_assessments
from assessment_hub.api.v1.questions import create_question, list_questions

VIEWER_EMAIL = "viewer@assessment-hub-test.local"


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


class TestGetAssessment(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def make_assessment(self, **kwargs):
		values = {"doctype": "Assessment", "title": "Sample Assessment"}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def make_question(self, assessment, **kwargs):
		values = {
			"doctype": "Question",
			"assessment": assessment,
			"content": "Sample question",
			"answers": [{"content": "Answer", "score": 1}],
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def body(self, response):
		return json.loads(response.get_data(as_text=True))

	def test_missing_id_is_rejected(self):
		response = get_assessment()

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["code"], "MISSING_REQUIRED_FIELD")

	def test_nonexistent_id_is_not_found(self):
		response = get_assessment(id="ASM-DOES-NOT-EXIST")

		self.assertEqual(response.status_code, 404)
		self.assertEqual(self.body(response)["errors"][0]["code"], "NOT_FOUND")

	def test_without_include_questions_has_no_questions_key(self):
		assessment = self.make_assessment()

		data = self.body(get_assessment(id=assessment.name))["data"]

		self.assertNotIn("questions", data)

	def test_include_questions_zero_has_no_questions_key(self):
		assessment = self.make_assessment()

		data = self.body(get_assessment(id=assessment.name, include_questions="0"))["data"]

		self.assertNotIn("questions", data)

	def test_invalid_include_questions_is_rejected(self):
		assessment = self.make_assessment()

		response = get_assessment(id=assessment.name, include_questions="yes")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["code"], "INVALID_PARAMETER")

	def test_include_questions_nests_questions_and_answers_in_order(self):
		assessment = self.make_assessment()
		first = self.make_question(
			assessment.name,
			content="First",
			answers=[{"content": "B", "score": 0, "sort_order": 2}, {"content": "A", "score": 1, "sort_order": 1}],
		)
		second = self.make_question(assessment.name, content="Second")

		data = self.body(get_assessment(id=assessment.name, include_questions="1"))["data"]

		self.assertEqual([q["id"] for q in data["questions"]], [first.name, second.name])
		self.assertEqual(
			[a["content"] for a in data["questions"][0]["answers"]],
			["A", "B"],
		)

	def test_question_payload_shape(self):
		assessment = self.make_assessment()
		question = self.make_question(assessment.name)

		data = self.body(get_assessment(id=assessment.name, include_questions="1"))["data"]
		item = data["questions"][0]

		self.assertEqual(item["id"], question.name)
		self.assertEqual(item["assessment_id"], assessment.name)
		self.assertEqual(item["content"], "Sample question")
		self.assertEqual(item["status"], "Active")
		answer = item["answers"][0]
		self.assertEqual(set(answer), {"id", "content", "score", "sort_order"})


class TestCreateQuestion(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_assessment(self, **kwargs):
		values = {"doctype": "Assessment", "title": "Sample Assessment"}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def body(self, response):
		return json.loads(response.get_data(as_text=True))

	def test_valid_request_creates_question_and_answers(self):
		assessment = self.make_assessment()

		response = create_question(
			assessment_id=assessment.name,
			content="What is 2 + 2?",
			answers=[{"content": "4", "score": 1}, {"content": "5", "score": 0}, {"content": "3", "score": 0}],
		)

		self.assertEqual(response.status_code, 200)
		data = self.body(response)["data"]
		self.assertEqual(data["assessment_id"], assessment.name)
		self.assertEqual(len(data["answers"]), 3)
		self.assertEqual(frappe.db.count("Question", {"assessment": assessment.name}), 1)
		self.assertEqual(frappe.db.count("Answer", {"parent": data["id"]}), 3)

	def test_empty_answer_content_is_rejected_and_nothing_persisted(self):
		assessment = self.make_assessment()

		response = create_question(
			assessment_id=assessment.name,
			content="Bad question",
			answers=[{"content": "ok", "score": 1}, {"content": "   ", "score": 0}],
		)

		self.assertEqual(response.status_code, 400)
		error = self.body(response)["errors"][0]
		self.assertEqual(error["code"], "MISSING_REQUIRED_FIELD")
		self.assertEqual(error["field"], "answers[1].content")
		self.assertEqual(frappe.db.count("Question", {"assessment": assessment.name}), 0)

	def test_answer_score_boolean_is_rejected_with_field(self):
		assessment = self.make_assessment()

		response = create_question(
			assessment_id=assessment.name, content="Bad score", answers=[{"content": "x", "score": True}]
		)

		self.assertEqual(response.status_code, 400)
		error = self.body(response)["errors"][0]
		self.assertEqual(error["code"], "INVALID_PARAMETER")
		self.assertEqual(error["field"], "answers[0].score")

	def test_answers_empty_is_rejected(self):
		assessment = self.make_assessment()

		response = create_question(assessment_id=assessment.name, content="x", answers=[])

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["field"], "answers")

	def test_answers_not_an_array_is_rejected(self):
		assessment = self.make_assessment()

		response = create_question(assessment_id=assessment.name, content="x", answers="not-json-and-not-a-list")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["code"], "INVALID_PARAMETER")

	def test_answers_as_json_string_is_parsed(self):
		assessment = self.make_assessment()

		response = create_question(
			assessment_id=assessment.name, content="x", answers=json.dumps([{"content": "y", "score": 1}])
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(self.body(response)["data"]["answers"]), 1)

	def test_archived_assessment_is_rejected(self):
		assessment = self.make_assessment()
		assessment.archive()

		response = create_question(
			assessment_id=assessment.name, content="x", answers=[{"content": "y", "score": 1}]
		)

		self.assertEqual(response.status_code, 422)
		self.assertEqual(self.body(response)["errors"][0]["code"], "ASSESSMENT_ARCHIVED")

	def test_nonexistent_assessment_is_not_found(self):
		response = create_question(
			assessment_id="ASM-DOES-NOT-EXIST", content="x", answers=[{"content": "y", "score": 1}]
		)

		self.assertEqual(response.status_code, 404)
		self.assertEqual(self.body(response)["errors"][0]["code"], "NOT_FOUND")

	def test_missing_assessment_id_is_rejected(self):
		response = create_question(content="x", answers=[{"content": "y", "score": 1}])

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.body(response)["errors"][0]["field"], "assessment_id")

	def test_sort_order_defaults_to_next_when_omitted(self):
		assessment = self.make_assessment()
		create_question(assessment_id=assessment.name, content="First", answers=[{"content": "a", "score": 1}])

		response = create_question(
			assessment_id=assessment.name, content="Second", answers=[{"content": "b", "score": 1}]
		)

		self.assertEqual(self.body(response)["data"]["sort_order"], 2)

	def test_status_defaults_from_settings_when_omitted(self):
		assessment = self.make_assessment()

		response = create_question(
			assessment_id=assessment.name, content="x", answers=[{"content": "y", "score": 1}]
		)

		self.assertEqual(self.body(response)["data"]["status"], "Active")

	def test_viewer_cannot_create_question(self):
		assessment = self.make_assessment()
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
		response = create_question(
			assessment_id=assessment.name, content="x", answers=[{"content": "y", "score": 1}]
		)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(self.body(response)["errors"][0]["code"], "PERMISSION_DENIED")

		frappe.set_user("Administrator")
		frappe.delete_doc("Assessment", assessment.name, force=True, ignore_permissions=True)
		frappe.db.commit()


class TestListQuestions(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def make_assessment(self, **kwargs):
		values = {"doctype": "Assessment", "title": "Sample Assessment"}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def make_question(self, assessment, **kwargs):
		values = {
			"doctype": "Question",
			"assessment": assessment,
			"content": "Sample question",
			"answers": [{"content": "Answer", "score": 1}],
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert()

	def body(self, response):
		return json.loads(response.get_data(as_text=True))

	def test_missing_assessment_id_is_rejected(self):
		response = list_questions()

		self.assertEqual(response.status_code, 400)
		error = self.body(response)["errors"][0]
		self.assertEqual(error["code"], "MISSING_REQUIRED_FIELD")
		self.assertEqual(error["field"], "assessment_id")

	def test_nonexistent_assessment_id_is_not_found(self):
		response = list_questions(assessment_id="ASM-DOES-NOT-EXIST")

		self.assertEqual(response.status_code, 404)
		self.assertEqual(self.body(response)["errors"][0]["code"], "NOT_FOUND")

	def test_items_sorted_by_sort_order_then_creation(self):
		assessment = self.make_assessment()
		second = self.make_question(assessment.name, content="Second", sort_order=2)
		first = self.make_question(assessment.name, content="First", sort_order=1)
		tiebreak = self.make_question(assessment.name, content="Tiebreak", sort_order=1)

		items = self.body(list_questions(assessment_id=assessment.name))["data"]["items"]

		self.assertEqual([item["id"] for item in items], [first.name, tiebreak.name, second.name])

	def test_items_do_not_include_answers(self):
		assessment = self.make_assessment()
		self.make_question(assessment.name)

		items = self.body(list_questions(assessment_id=assessment.name))["data"]["items"]

		self.assertNotIn("answers", items[0])

	def test_filters_by_status(self):
		assessment = self.make_assessment()
		active = self.make_question(assessment.name, content="Active one")
		self.make_question(assessment.name, content="Inactive one", status="Inactive")

		items = self.body(list_questions(assessment_id=assessment.name, status="Active"))["data"]["items"]

		self.assertEqual([item["id"] for item in items], [active.name])

	def test_only_returns_questions_of_the_requested_assessment(self):
		assessment = self.make_assessment()
		other = self.make_assessment(title="Other Assessment")
		question = self.make_question(assessment.name)
		self.make_question(other.name)

		items = self.body(list_questions(assessment_id=assessment.name))["data"]["items"]

		self.assertEqual([item["id"] for item in items], [question.name])
