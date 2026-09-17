import frappe


class InvalidStatusTransitionError(frappe.ValidationError):
	pass


class AssessmentArchivedError(frappe.ValidationError):
	pass


class MissingRequiredFieldError(frappe.ValidationError):
	pass


class InvalidParameterError(frappe.ValidationError):
	pass
