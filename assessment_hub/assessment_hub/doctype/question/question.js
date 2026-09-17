frappe.ui.form.on("Question", {
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
});
