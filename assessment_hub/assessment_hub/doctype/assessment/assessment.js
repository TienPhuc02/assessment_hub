frappe.ui.form.on("Assessment", {
	refresh(frm) {
		set_status_buttons(frm);
		set_archived_alert(frm);
	},
});

function set_status_buttons(frm) {
	if (frm.is_new() || !frm.perm[0].write) {
		return;
	}

	if (frm.doc.status === "Draft") {
		frm.add_custom_button(__("Publish"), () => publish(frm), __("Status"));
	}

	if (frm.doc.status === "Draft" || frm.doc.status === "Published") {
		frm.add_custom_button(__("Archive"), () => archive(frm), __("Status"));
	}
}

function publish(frm) {
	frappe.confirm(__("Publish {0}?", [frappe.utils.escape_html(frm.doc.title)]), () => {
		frm.call("publish").then(() => {
			frm.reload_doc();
			frappe.show_alert({ message: __("Assessment published"), indicator: "green" });
		});
	});
}

function archive(frm) {
	frappe.confirm(
		__("Archive {0}? This cannot be undone.", [frappe.utils.escape_html(frm.doc.title)]),
		() => {
			frm.call("archive").then(() => frm.reload_doc());
		}
	);
}

function set_archived_alert(frm) {
	if (frm.doc.status === "Archived") {
		frm.dashboard.set_headline_alert(__("This assessment is archived."), "orange", true);
	}
}
