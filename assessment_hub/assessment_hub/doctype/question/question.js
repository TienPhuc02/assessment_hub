frappe.ui.form.on("Question", {
	setup(frm) {
		frm.set_query("assessment", () => ({
			filters: { status: ["!=", "Archived"] },
		}));
	},

	onload(frm) {
		if (!frm.is_new() || !frm.doc.assessment || frm.doc.sort_order) {
			return;
		}

		frappe.call({
			method: "assessment_hub.assessment_hub.doctype.question.question.get_suggested_sort_order",
			args: { assessment: frm.doc.assessment },
			callback(r) {
				if (r.message) {
					frm.set_value("sort_order", r.message);
				}
			},
		});
	},

	refresh(frm) {
		if (frm.is_new() || !frm.doc.assessment) {
			return;
		}

		frappe.db.get_value("Assessment", frm.doc.assessment, "status").then((r) => {
			if (r.message && r.message.status === "Archived") {
				frm.disable_form();
				frm.dashboard.set_headline_alert(
					__("This question belongs to an archived assessment and cannot be changed."),
					"orange",
					true
				);
			}
		});
	},

	assessment(frm) {
		if (!frm.doc.assessment) {
			return;
		}

		frappe.db.get_value("Assessment", frm.doc.assessment, "status").then((r) => {
			if (r.message && r.message.status === "Archived") {
				frappe.msgprint(__("Cannot add a question to an archived assessment."));
				frm.set_value("assessment", "");
			}
		});
	},
});
