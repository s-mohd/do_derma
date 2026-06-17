from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	add_clinical_procedure_template_variable_field()
	update_marker_behavior_options()
	update_body_template_metadata()
	update_derma_procedure_template_variable_sources()


def add_clinical_procedure_template_variable_field():
	if not frappe.db.exists("DocType", "Annotation Treatment"):
		return
	create_custom_fields(
		{
			"Clinical Procedure Template": [
				{
					"fieldname": "custom_derma_annotation_treatment",
					"fieldtype": "Link",
					"label": "Annotation Treatment Variables",
					"options": "Annotation Treatment",
					"description": "Optional variable schema reused from the annotation app.",
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


def update_derma_procedure_template_variable_sources():
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return
	meta = frappe.get_meta("Clinical Procedure Template")
	if not meta.has_field("custom_derma_annotation_treatment"):
		return
	for row in frappe.get_all(
		"Clinical Procedure Template",
		filters={"custom_derma_category": ["is", "set"]},
		fields=["name", "custom_derma_category"],
	):
		source = "Laser" if row.custom_derma_category == "Laser" else "Injection" if row.custom_derma_category in {"Botox", "Filler"} else ""
		if source and frappe.db.exists("Annotation Treatment", source):
			frappe.db.set_value("Clinical Procedure Template", row.name, "custom_derma_annotation_treatment", source, update_modified=False)
