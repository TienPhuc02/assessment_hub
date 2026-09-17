import json

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.utils import (
	api_response,
	parse_bool,
	parse_datetime,
	parse_enum,
	parse_int,
	require_str,
)
from assessment_hub.exceptions import AssessmentArchivedError, InvalidParameterError, MissingRequiredFieldError


class TestApiResponse(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def get_body(self, response):
		return json.loads(response.get_data(as_text=True))

	def test_success_response_has_data_envelope(self):
		@api_response
		def handler():
			return {"id": "ASM-00001"}

		response = handler()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.get_body(response), {"data": {"id": "ASM-00001"}})

	def test_missing_required_field_maps_to_400(self):
		@api_response
		def handler():
			require_str(None, "content")

		response = handler()

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "MISSING_REQUIRED_FIELD")

	def test_invalid_parameter_maps_to_400(self):
		@api_response
		def handler():
			parse_int("abc", "page_length")

		response = handler()

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "INVALID_PARAMETER")

	def test_assessment_archived_maps_to_422(self):
		@api_response
		def handler():
			frappe.throw("nope", AssessmentArchivedError)

		response = handler()

		self.assertEqual(response.status_code, 422)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "ASSESSMENT_ARCHIVED")

	def test_generic_validation_error_maps_to_400(self):
		@api_response
		def handler():
			frappe.throw("nope", frappe.ValidationError)

		response = handler()

		self.assertEqual(response.status_code, 400)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "VALIDATION_ERROR")

	def test_authentication_error_maps_to_401(self):
		@api_response
		def handler():
			raise frappe.AuthenticationError

		response = handler()

		self.assertEqual(response.status_code, 401)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "AUTHENTICATION_FAILED")

	def test_permission_error_maps_to_403(self):
		@api_response
		def handler():
			raise frappe.PermissionError

		response = handler()

		self.assertEqual(response.status_code, 403)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "PERMISSION_DENIED")

	def test_does_not_exist_error_maps_to_404(self):
		@api_response
		def handler():
			raise frappe.DoesNotExistError

		response = handler()

		self.assertEqual(response.status_code, 404)
		self.assertEqual(self.get_body(response)["errors"][0]["code"], "NOT_FOUND")

	def test_unexpected_error_maps_to_500_without_leaking_details(self):
		@api_response
		def handler():
			raise KeyError("db_password")

		response = handler()

		self.assertEqual(response.status_code, 500)
		body = self.get_body(response)
		self.assertEqual(body["errors"][0]["code"], "INTERNAL_ERROR")
		self.assertNotIn("db_password", body["errors"][0]["message"])

	def test_response_content_type_is_json(self):
		@api_response
		def handler():
			return {}

		response = handler()

		self.assertEqual(response.content_type, "application/json; charset=utf-8")


class TestRequireStr(IntegrationTestCase):
	def test_none_is_missing(self):
		with self.assertRaises(MissingRequiredFieldError):
			require_str(None, "content")

	def test_blank_is_missing(self):
		with self.assertRaises(MissingRequiredFieldError):
			require_str("   ", "content")

	def test_wrong_type_is_invalid(self):
		with self.assertRaises(InvalidParameterError):
			require_str(123, "content")

	def test_too_long_is_invalid(self):
		with self.assertRaises(InvalidParameterError):
			require_str("x" * 11, "content", max_length=10)

	def test_valid_value_is_trimmed(self):
		self.assertEqual(require_str("  hello  ", "content"), "hello")


class TestParseInt(IntegrationTestCase):
	def test_missing_and_required_is_missing(self):
		with self.assertRaises(MissingRequiredFieldError):
			parse_int(None, "page_length", required=True)

	def test_missing_and_optional_returns_none(self):
		self.assertIsNone(parse_int(None, "page"))

	def test_missing_with_default_returns_default(self):
		self.assertEqual(parse_int(None, "page_length", default=20), 20)

	def test_boolean_is_invalid(self):
		with self.assertRaises(InvalidParameterError):
			parse_int(True, "page_length", default=20)

	def test_non_numeric_string_is_invalid(self):
		with self.assertRaises(InvalidParameterError):
			parse_int("abc", "page_length", default=20)

	def test_below_minimum_is_invalid(self):
		with self.assertRaises(InvalidParameterError):
			parse_int(-1, "start", minimum=0)

	def test_above_maximum_is_invalid(self):
		with self.assertRaises(InvalidParameterError):
			parse_int(500, "page_length", maximum=100)

	def test_valid_string_is_cast_to_int(self):
		self.assertEqual(parse_int("10", "page_length"), 10)


class TestParseEnum(IntegrationTestCase):
	def test_missing_returns_default(self):
		self.assertIsNone(parse_enum(None, "status", ["Draft", "Published"]))

	def test_invalid_option_raises(self):
		with self.assertRaises(InvalidParameterError):
			parse_enum("Foo", "status", ["Draft", "Published"])

	def test_valid_option_is_returned(self):
		self.assertEqual(parse_enum("Draft", "status", ["Draft", "Published"]), "Draft")


class TestParseBool(IntegrationTestCase):
	def test_missing_returns_default(self):
		self.assertFalse(parse_bool(None, "include_questions"))

	def test_true_variants(self):
		for value in (True, "1", "true", "True"):
			self.assertTrue(parse_bool(value, "include_questions"))

	def test_false_variants(self):
		for value in (False, "0", "false", "False"):
			self.assertFalse(parse_bool(value, "include_questions"))

	def test_invalid_value_raises(self):
		with self.assertRaises(InvalidParameterError):
			parse_bool("yes", "include_questions")


class TestParseDatetime(IntegrationTestCase):
	def test_missing_returns_none(self):
		self.assertIsNone(parse_datetime(None, "updated_since"))

	def test_invalid_string_raises(self):
		with self.assertRaises(InvalidParameterError):
			parse_datetime("not-a-date", "updated_since")

	def test_iso8601_with_offset_is_parsed(self):
		result = parse_datetime("2026-09-16T14:30:45+07:00", "updated_since")
		self.assertEqual(result.utcoffset().total_seconds(), 7 * 3600)

	def test_date_only_is_parsed(self):
		result = parse_datetime("2026-09-16", "updated_since")
		self.assertEqual((result.year, result.month, result.day), (2026, 9, 16))
