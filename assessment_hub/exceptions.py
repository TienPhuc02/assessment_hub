import frappe


class InvalidStatusTransitionError(frappe.ValidationError):
	pass
