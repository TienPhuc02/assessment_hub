const ASSESSMENT_STATUS_COLORS = {
	Draft: "gray",
	Published: "green",
	Archived: "orange",
};

frappe.listview_settings["Assessment"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		return [__(doc.status), ASSESSMENT_STATUS_COLORS[doc.status], "status,=," + doc.status];
	},
};
