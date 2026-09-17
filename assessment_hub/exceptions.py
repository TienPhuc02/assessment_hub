import frappe


class InvalidStatusTransitionError(frappe.ValidationError):
	pass


class AssessmentArchivedError(frappe.ValidationError):
	pass
