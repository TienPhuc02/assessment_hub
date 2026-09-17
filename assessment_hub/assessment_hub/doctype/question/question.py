import math

import frappe
from frappe import _
from frappe.model.document import Document

CONTENT_MAX_LENGTH = 10_000

MIN_ANSWERS = 1
MAX_ANSWERS = 50


class Question(Document):
	def before_insert(self):
		self.set_default_sort_order()

	def validate(self):
		self.validate_content()
		self.set_default_status()
		self.validate_answers()

	def validate_content(self):
		self.content = (self.content or "").strip()

		if not self.content:
			frappe.throw(_("Content is required."), frappe.ValidationError)

		if len(self.content) > CONTENT_MAX_LENGTH:
			frappe.throw(
				_("Content cannot be longer than {0} characters.").format(CONTENT_MAX_LENGTH),
				frappe.ValidationError,
			)

	def set_default_status(self):
		if self.status:
			return

		self.status = frappe.db.get_single_value("Assessment Hub Settings", "default_question_status")

	def validate_answers(self):
		answers = self.answers or []

		if not (MIN_ANSWERS <= len(answers) <= MAX_ANSWERS):
			frappe.throw(
				_("A question must have between {0} and {1} answers.").format(MIN_ANSWERS, MAX_ANSWERS),
				frappe.ValidationError,
			)

		for answer in answers:
			self.validate_answer(answer)

	def validate_answer(self, answer):
		answer.content = (answer.content or "").strip()

		if not answer.content:
			frappe.throw(_("Row #{0}: Answer content is required.").format(answer.idx), frappe.ValidationError)

		if (
			answer.score is None
			or isinstance(answer.score, bool)
			or not isinstance(answer.score, int | float)
		):
			frappe.throw(_("Row #{0}: Score must be a number.").format(answer.idx), frappe.ValidationError)

		if not math.isfinite(answer.score):
			frappe.throw(
				_("Row #{0}: Score must be a finite number.").format(answer.idx), frappe.ValidationError
			)

		if not answer.sort_order:
			answer.sort_order = answer.idx

	def set_default_sort_order(self):
		if self.sort_order:
			return

		last_sort_order = frappe.db.get_value(
			"Question", {"assessment": self.assessment}, "sort_order", order_by="sort_order desc"
		)

		self.sort_order = (last_sort_order or 0) + 1
