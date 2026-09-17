const QUESTION_STATUS_COLORS = {
	Active: "green",
	Inactive: "gray",
};

frappe.listview_settings["Question"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		return [__(doc.status), QUESTION_STATUS_COLORS[doc.status], "status,=," + doc.status];
	},
};
