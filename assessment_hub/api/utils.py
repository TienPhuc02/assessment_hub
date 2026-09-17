import functools

import frappe
from frappe import _
from frappe.utils import get_datetime
from werkzeug.wrappers import Response

from assessment_hub.exceptions import (
	AssessmentArchivedError,
	InvalidParameterError,
	MissingRequiredFieldError,
)

ERROR_STATUS_CODES = {
	MissingRequiredFieldError: (400, "MISSING_REQUIRED_FIELD"),
	InvalidParameterError: (400, "INVALID_PARAMETER"),
	AssessmentArchivedError: (422, "ASSESSMENT_ARCHIVED"),
	frappe.ValidationError: (400, "VALIDATION_ERROR"),
	frappe.AuthenticationError: (401, "AUTHENTICATION_FAILED"),
	frappe.PermissionError: (403, "PERMISSION_DENIED"),
	frappe.DoesNotExistError: (404, "NOT_FOUND"),
}


def api_response(fn):
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			result = fn(*args, **kwargs)
		except Exception as exc:
			frappe.db.rollback()
			return build_error_response(exc)

		return build_json_response({"data": result}, 200)

	return wrapper


def build_error_response(exc):
	resolved = resolve_error(exc)

	if resolved is None:
		frappe.log_error(title="Assessment Hub API Error")
		return build_json_response(
			{"errors": [{"message": _("Something went wrong. Please try again later."), "code": "INTERNAL_ERROR"}]},
			500,
		)

	status_code, code = resolved

	return build_json_response({"errors": [{"message": str(exc), "code": code}]}, status_code)


def resolve_error(exc):
	for exc_type in type(exc).__mro__:
		if exc_type in ERROR_STATUS_CODES:
			return ERROR_STATUS_CODES[exc_type]

	return None


def build_json_response(payload, status_code):
	return Response(frappe.as_json(payload), status=status_code, content_type="application/json; charset=utf-8")


def require_str(value, field, *, max_length=None):
	if value is None or value == "":
		frappe.throw(_("{0} is required.").format(field), MissingRequiredFieldError)

	if not isinstance(value, str):
		frappe.throw(_("{0} must be a string.").format(field), InvalidParameterError)

	value = value.strip()

	if not value:
		frappe.throw(_("{0} is required.").format(field), MissingRequiredFieldError)

	if max_length and len(value) > max_length:
		frappe.throw(
			_("{0} cannot be longer than {1} characters.").format(field, max_length), InvalidParameterError
		)

	return value


def parse_int(value, field, *, default=None, minimum=None, maximum=None):
	if value is None or value == "":
		if default is None:
			frappe.throw(_("{0} is required.").format(field), MissingRequiredFieldError)
		return default

	if isinstance(value, bool) or not isinstance(value, (int, str)):
		frappe.throw(_("{0} must be an integer.").format(field), InvalidParameterError)

	try:
		value = int(value)
	except ValueError:
		frappe.throw(_("{0} must be an integer.").format(field), InvalidParameterError)

	if minimum is not None and value < minimum:
		frappe.throw(_("{0} must be at least {1}.").format(field, minimum), InvalidParameterError)

	if maximum is not None and value > maximum:
		frappe.throw(_("{0} must be at most {1}.").format(field, maximum), InvalidParameterError)

	return value


def parse_enum(value, field, options, *, default=None):
	if value is None or value == "":
		return default

	if value not in options:
		frappe.throw(
			_("{0} must be one of {1}.").format(field, ", ".join(options)), InvalidParameterError
		)

	return value


def parse_bool(value, field, *, default=False):
	if value is None or value == "":
		return default

	if isinstance(value, bool):
		return value

	if isinstance(value, str):
		normalized = value.strip().lower()

		if normalized in ("1", "true"):
			return True

		if normalized in ("0", "false"):
			return False

	frappe.throw(_("{0} must be a boolean.").format(field), InvalidParameterError)


def parse_datetime(value, field):
	if value is None or value == "":
		return None

	try:
		return get_datetime(value)
	except (ValueError, TypeError):
		frappe.throw(
			_("{0} must be a valid ISO 8601 or YYYY-MM-DD date.").format(field), InvalidParameterError
		)
