import json
import math

import frappe
from frappe import _

from assessment_hub.api.utils import api_response, parse_enum, parse_int, raise_error, require_str
from assessment_hub.api.v1.serializers import serialize_question
from assessment_hub.assessment_hub.doctype.question.question import CONTENT_MAX_LENGTH, MAX_ANSWERS, MIN_ANSWERS
from assessment_hub.exceptions import InvalidParameterError, MissingRequiredFieldError

STATUS_OPTIONS = ("Active", "Inactive")


@frappe.whitelist(methods=["POST"])
@api_response
def create_question(assessment_id=None, content=None, sort_order=None, status=None, answers=None):
	frappe.has_permission("Question", "create", throw=True)

	assessment_id = require_str(assessment_id, "assessment_id")
	content = require_str(content, "content", max_length=CONTENT_MAX_LENGTH)
	sort_order = parse_int(sort_order, "sort_order", minimum=0)
	status = parse_enum(status, "status", STATUS_OPTIONS)
	answers = parse_answers(answers)

	if not frappe.db.exists("Assessment", assessment_id):
		frappe.throw(_("Assessment {0} not found.").format(assessment_id), frappe.DoesNotExistError)

	doc = frappe.get_doc(
		{
			"doctype": "Question",
			"assessment": assessment_id,
			"content": content,
			"sort_order": sort_order,
			"status": status,
			"answers": answers,
		}
	)
	doc.insert()

	return serialize_question(doc, doc.answers)


@frappe.whitelist(methods=["GET"])
@api_response
def list_questions(assessment_id=None, status=None, page_length=None, start=None, page=None):
	assessment_id = require_str(assessment_id, "assessment_id")

	assessment = frappe.get_doc("Assessment", assessment_id)
	assessment.check_permission("read")

	settings = frappe.get_cached_doc("Assessment Hub Settings")

	status = parse_enum(status, "status", STATUS_OPTIONS)
	page_length = parse_int(
		page_length,
		"page_length",
		default=settings.default_page_length,
		minimum=1,
		maximum=settings.max_page_length,
	)
	page = parse_int(page, "page", minimum=1)
	start = (page - 1) * page_length if page else parse_int(start, "start", default=0, minimum=0)

	filters = {"assessment": assessment_id}
	if status:
		filters["status"] = status

	rows = frappe.get_list(
		"Question",
		filters=filters,
		fields=["name", "assessment", "content", "sort_order", "status"],
		order_by="sort_order asc, creation asc",
		offset=start,
		limit=page_length + 1,
	)

	has_more = len(rows) > page_length
	rows = rows[:page_length]

	return {
		"items": [serialize_question(row) for row in rows],
		"pagination": {"start": start, "page_length": page_length, "has_more": has_more},
	}


def parse_answers(value):
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			raise_error(InvalidParameterError, _("answers must be a valid JSON array."), "answers")

	if not isinstance(value, list) or not (MIN_ANSWERS <= len(value) <= MAX_ANSWERS):
		raise_error(
			InvalidParameterError,
			_("answers must be an array of {0} to {1} items.").format(MIN_ANSWERS, MAX_ANSWERS),
			"answers",
		)

	return [parse_answer(item, idx) for idx, item in enumerate(value)]


def parse_answer(raw, idx):
	if not isinstance(raw, dict):
		raise_error(InvalidParameterError, _("answers[{0}] must be an object.").format(idx), f"answers[{idx}]")

	content = raw.get("content")
	if not isinstance(content, str) or not content.strip():
		raise_error(MissingRequiredFieldError, _("Answer content is required"), f"answers[{idx}].content")

	score = raw.get("score")
	if (
		score is None
		or isinstance(score, bool)
		or not isinstance(score, (int, float))
		or not math.isfinite(score)
	):
		raise_error(InvalidParameterError, _("Answer score must be a finite number"), f"answers[{idx}].score")

	answer = {"content": content.strip(), "score": score}

	sort_order = raw.get("sort_order")
	if sort_order is not None:
		if isinstance(sort_order, bool) or not isinstance(sort_order, int) or sort_order < 0:
			raise_error(
				InvalidParameterError,
				_("Answer sort_order must be a non-negative integer"),
				f"answers[{idx}].sort_order",
			)
		answer["sort_order"] = sort_order

	return answer
