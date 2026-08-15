from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	add_clinical_procedure_template_preset_field()
	update_marker_behavior_options()
	update_body_template_metadata()
	remove_obsolete_annotation_treatment_field()


def add_clinical_procedure_template_preset_field():
	create_custom_fields(
		{
			"Clinical Procedure Template": [
				{
					"fieldname": "custom_derma_variables_json",
					"fieldtype": "Code",
					"label": "Derma Variables JSON",
					"options": "JSON",
					"description": "Procedure variables shown in the derma annotation studio. Use fieldname, label, fieldtype, options, and required.",
					"insert_after": "custom_derma_allowed_body_regions",
					"module": "Do Derma",
				},
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


def remove_obsolete_annotation_treatment_field():
	name = frappe.db.exists(
		"Custom Field",
		{"dt": "Clinical Procedure Template", "fieldname": "custom_derma_annotation_treatment"},
	)
	if not name:
		return
	frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.clear_cache(doctype="Clinical Procedure Template")


def update_body_template_metadata():
	if not frappe.db.exists("DocType", "Derma Body Template"):
		return
	for name in frappe.get_all("Derma Body Template", pluck="name"):
		values = {}
		if frappe.get_meta("Derma Body Template").has_field("gender"):
			values["gender"] = "Female"
		if frappe.get_meta("Derma Body Template").has_field("is_standard"):
			values["is_standard"] = 1
		image = frappe.db.get_value("Derma Body Template", name, "image")
		if image and image.lower().endswith(".svg"):
			values["disabled"] = 1
			values["image"] = ""
		if values:
			frappe.db.set_value("Derma Body Template", name, values, update_modified=False)


def update_marker_behavior_options():
	for fieldname in ["custom_derma_marker_behavior"]:
		name = frappe.db.exists("Custom Field", {"dt": "Clinical Procedure Template", "fieldname": fieldname})
		if name:
			frappe.db.set_value(
				"Custom Field",
				name,
				"options",
				"numbered_dot\nblue_dot\nthree_dots\ntriangle\ntriangle_cluster\nhatch\nfive_lines\nx_mark\ntarget\narea\nfinding_dot",
				update_modified=False,
			)
