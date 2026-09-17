import frappe
from frappe import _

from assessment_hub.api.utils import (
	api_response,
	parse_bool,
	parse_datetime,
	parse_enum,
	parse_int,
	require_str,
	to_iso8601,
)
from assessment_hub.exceptions import InvalidParameterError

STATUS_OPTIONS = ("Draft", "Published", "Archived")
SEARCH_MAX_LENGTH = 140


@frappe.whitelist(methods=["GET"])
@api_response
def list_assessments(status=None, search=None, updated_since=None, page_length=None, start=None, page=None):
	settings = frappe.get_cached_doc("Assessment Hub Settings")

	status = parse_enum(status, "status", STATUS_OPTIONS)
	search = parse_search(search)
	updated_since = parse_datetime(updated_since, "updated_since")
	page_length = parse_int(
		page_length,
		"page_length",
		default=settings.default_page_length,
		minimum=1,
		maximum=settings.max_page_length,
	)
	page = parse_int(page, "page", minimum=1)
	start = (page - 1) * page_length if page else parse_int(start, "start", default=0, minimum=0)

	filters = []

	if status:
		filters.append(["status", "=", status])

	if search:
		escaped_search = search.replace("%", "\\%").replace("_", "\\_")
		filters.append(["title", "like", f"%{escaped_search}%"])

	if updated_since:
		filters.append(["modified", ">=", updated_since])

	order_by = "modified asc, name asc" if updated_since else "modified desc, name desc"

	rows = frappe.get_list(
		"Assessment",
		filters=filters,
		fields=["name", "title", "description", "status", "creation", "modified"],
		order_by=order_by,
		offset=start,
		limit=page_length + 1,
	)

	has_more = len(rows) > page_length
	rows = rows[:page_length]

	return {
		"items": [serialize_assessment(row) for row in rows],
		"pagination": {"start": start, "page_length": page_length, "has_more": has_more},
	}


@frappe.whitelist(methods=["GET"])
@api_response
def get_assessment(id=None, include_questions=None):
	id = require_str(id, "id")
	include_questions = parse_bool(include_questions, "include_questions", default=False)

	doc = frappe.get_doc("Assessment", id)
	doc.check_permission("read")

	result = serialize_assessment(doc)

	if include_questions:
		result["questions"] = get_questions_with_answers(id)

	return result


def get_questions_with_answers(assessment_id):
	questions = frappe.get_list(
		"Question",
		filters={"assessment": assessment_id},
		fields=["name", "assessment", "content", "sort_order", "status"],
		order_by="sort_order asc, creation asc",
	)

	if not questions:
		return []

	answers_by_question = get_answers_by_question([question.name for question in questions])

	return [
		serialize_question(question, answers_by_question.get(question.name, [])) for question in questions
	]


def get_answers_by_question(question_names):
	answer = frappe.qb.DocType("Answer")

	rows = (
		frappe.qb.from_(answer)
		.select(answer.name, answer.parent, answer.content, answer.score, answer.sort_order)
		.where(answer.parenttype == "Question")
		.where(answer.parent.isin(question_names))
		.orderby(answer.parent)
		.orderby(answer.sort_order)
		.run(as_dict=True)
	)

	answers_by_question = {}
	for row in rows:
		answers_by_question.setdefault(row.parent, []).append(row)

	return answers_by_question


def serialize_question(row, answers):
	return {
		"id": row.name,
		"assessment_id": row.assessment,
		"content": row.content,
		"sort_order": row.sort_order,
		"status": row.status,
		"answers": [serialize_answer(answer) for answer in answers],
	}


def serialize_answer(row):
	return {
		"id": row.name,
		"content": row.content,
		"score": row.score,
		"sort_order": row.sort_order,
	}


def parse_search(value):
	if not value:
		return None

	value = value.strip()

	if not value:
		return None

	if len(value) > SEARCH_MAX_LENGTH:
		frappe.throw(
			_("search cannot be longer than {0} characters.").format(SEARCH_MAX_LENGTH), InvalidParameterError
		)

	return value


def serialize_assessment(row):
	return {
		"id": row.name,
		"title": row.title,
		"description": row.description,
		"status": row.status,
		"created_at": to_iso8601(row.creation),
		"updated_at": to_iso8601(row.modified),
	}
