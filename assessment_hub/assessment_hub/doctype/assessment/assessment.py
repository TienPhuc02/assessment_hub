import frappe
from frappe import _
from frappe.model.document import Document

from assessment_hub.exceptions import InvalidStatusTransitionError

DRAFT = "Draft"
PUBLISHED = "Published"
ARCHIVED = "Archived"

TITLE_MAX_LENGTH = 140

ALLOWED_TRANSITIONS = {
	DRAFT: (PUBLISHED, ARCHIVED),
	PUBLISHED: (ARCHIVED,),
	ARCHIVED: (),
}

TRANSITION_ROLES = ("Assessment Manager", "System Manager")


class Assessment(Document):
	def before_insert(self):
		self.status = DRAFT

	def validate(self):
		self.validate_title()
		self.validate_status_transition()

	def validate_title(self):
		self.title = (self.title or "").strip()

		if not self.title:
			frappe.throw(_("Title is required."), frappe.ValidationError)

		if len(self.title) > TITLE_MAX_LENGTH:
			frappe.throw(
				_("Title cannot be longer than {0} characters.").format(TITLE_MAX_LENGTH),
				frappe.ValidationError,
			)

	def validate_status_transition(self):
		previous = self.get_doc_before_save()

		if previous is None or previous.status == self.status:
			return

		if self.status not in ALLOWED_TRANSITIONS.get(previous.status, ()):
			frappe.throw(
				_("Cannot change status from {0} to {1}.").format(_(previous.status), _(self.status)),
				InvalidStatusTransitionError,
			)

	@frappe.whitelist()
	def publish(self):
		return self.change_status(PUBLISHED)

	@frappe.whitelist()
	def archive(self):
		return self.change_status(ARCHIVED)

	def change_status(self, new_status):
		frappe.only_for(TRANSITION_ROLES)

		current = frappe.get_doc(self.doctype, self.name, for_update=True)

		if new_status not in ALLOWED_TRANSITIONS.get(current.status, ()):
			frappe.throw(
				_("Cannot change status from {0} to {1}.").format(_(current.status), _(new_status)),
				InvalidStatusTransitionError,
			)

		current.status = new_status
		current.save()

		self.reload()

		return self.status
