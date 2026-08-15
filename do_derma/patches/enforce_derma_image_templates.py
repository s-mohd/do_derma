from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	add_marker_preset_field()
	update_marker_behavior_options()
	if not frappe.db.exists("DocType", "Derma Body Template"):
		return

	meta = frappe.get_meta("Derma Body Template")
	for name in frappe.get_all("Derma Body Template", pluck="name"):
		image = frappe.db.get_value("Derma Body Template", name, "image")
		values = {}
		if meta.has_field("gender"):
			gender = frappe.db.get_value("Derma Body Template", name, "gender")
			values["gender"] = gender if gender in {"Male", "Female"} else "Female"
		if not image or str(image).lower().endswith(".svg"):
			values["disabled"] = 1
			values["image"] = ""
		if values:
			frappe.db.set_value("Derma Body Template", name, values, update_modified=False)


def add_marker_preset_field():
	create_custom_fields(
		{
			"Clinical Procedure Template": [
				{
					"fieldname": "custom_derma_marker_preset_json",
					"fieldtype": "Code",
					"label": "Marker Preset JSON",
					"options": "JSON",
					"description": "Optional future-ready Excalidraw element preset for click-to-stamp charting.",
					"insert_after": "custom_derma_marker_color",
					"module": "Do Derma",
				},
			]
		},
		ignore_validate=True,
	)


def update_marker_behavior_options():
	name = frappe.db.exists(
		"Custom Field", {"dt": "Clinical Procedure Template", "fieldname": "custom_derma_marker_behavior"}
	)
	if name:
		frappe.db.set_value(
			"Custom Field",
			name,
			"options",
			"numbered_dot\nblue_dot\nthree_dots\ntriangle\ntriangle_cluster\nhatch\nfive_lines\nx_mark\ntarget\narea\nfinding_dot",
			update_modified=False,
		)
