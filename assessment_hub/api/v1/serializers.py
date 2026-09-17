import frappe

from assessment_hub.api.utils import to_iso8601


def serialize_assessment(row):
	return {
		"id": row.name,
		"title": row.title,
		"description": row.description,
		"status": row.status,
		"created_at": to_iso8601(row.creation),
		"updated_at": to_iso8601(row.modified),
	}


def serialize_question(row, answers=None):
	data = {
		"id": row.name,
		"assessment_id": row.assessment,
		"content": row.content,
		"sort_order": row.sort_order,
		"status": row.status,
	}

	if answers is not None:
		data["answers"] = [serialize_answer(answer) for answer in answers]

	return data


def serialize_answer(row):
	return {
		"id": row.name,
		"content": row.content,
		"score": row.score,
		"sort_order": row.sort_order,
	}


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
