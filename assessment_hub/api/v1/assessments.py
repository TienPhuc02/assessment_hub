import frappe
from frappe import _

from assessment_hub.api.utils import (
	api_response,
	parse_datetime,
	parse_enum,
	parse_int,
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
