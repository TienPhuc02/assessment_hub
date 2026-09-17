import frappe

APP_ROLES = ("Assessment Manager", "Assessment Viewer")

SETTINGS_DEFAULTS = {
	"default_page_length": 20,
	"max_page_length": 100,
	"default_question_status": "Active",
}


def after_install():
	create_roles()
	seed_settings()


def before_uninstall():
	remove_role_references()
	delete_roles()


def create_roles():
	for role_name in APP_ROLES:
		if frappe.db.exists("Role", role_name):
			continue

		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)


def seed_settings():
	settings = frappe.get_single("Assessment Hub Settings")

	changed = False
	for fieldname, default_value in SETTINGS_DEFAULTS.items():
		if not settings.get(fieldname):
			settings.set(fieldname, default_value)
			changed = True

	if changed:
		settings.save(ignore_permissions=True)


def remove_role_references():
	frappe.db.delete("Has Role", {"role": ("in", APP_ROLES)})
	frappe.db.delete("Custom DocPerm", {"role": ("in", APP_ROLES)})


def delete_roles():
	for role_name in APP_ROLES:
		if not frappe.db.exists("Role", role_name):
			continue

		frappe.delete_doc("Role", role_name, ignore_permissions=True, force=True)
